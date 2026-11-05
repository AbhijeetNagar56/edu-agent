-- 03_authoritative_schema.up.sql
-- EduAgents Authoritative Schema Migration (Day 1)
-- Consolidates Schema 1 (Knowledge Graph) and Schema 2 (API / Evaluator) into a single authoritative model.
-- Safe, deterministic, and idempotent.

-- ============================================================================
-- 1. EXTENSIONS & UTILITIES
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Reusable timestamp trigger function
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- ============================================================================
-- 2. IDENTITY: PROFILES
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT,
  role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'faculty', 'admin')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure role check includes 'admin' if profiles was already created
DO $$
BEGIN
  ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_role_check;
  ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check
    CHECK (role IN ('student', 'faculty', 'admin'));
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Auth trigger to ensure profile creation on sign-up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
  v_role TEXT := 'student';
  v_name TEXT := '';
BEGIN
  -- Read role strictly from app_metadata or default to student (never trust user_metadata for role)
  IF (NEW.raw_app_meta_data->>'role') IN ('student', 'faculty', 'admin') THEN
    v_role := NEW.raw_app_meta_data->>'role';
  END IF;

  v_name := COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1));

  INSERT INTO public.profiles (id, email, full_name, role)
  VALUES (NEW.id, COALESCE(NEW.email, ''), v_name, v_role)
  ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email,
        full_name = COALESCE(public.profiles.full_name, EXCLUDED.full_name);

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
  CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================================================
-- 3. ACADEMIC STRUCTURE: COURSES & ENROLLMENTS
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.courses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  faculty_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure code has a unique index
CREATE UNIQUE INDEX IF NOT EXISTS courses_code_idx ON public.courses(code);

DO $$
BEGIN
  DROP TRIGGER IF EXISTS trg_courses_updated_at ON public.courses;
  CREATE TRIGGER trg_courses_updated_at
    BEFORE UPDATE ON public.courses
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS public.enrollments (
  course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (course_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_enrollments_student ON public.enrollments(student_id);

-- ============================================================================
-- 4. KNOWLEDGE GRAPH: CONCEPTS & EDGES (WITH CYCLE PREVENTION)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.concepts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  pos_x DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  pos_y DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_concepts_course ON public.concepts(course_id);

CREATE TABLE IF NOT EXISTS public.concept_edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
  from_concept UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  to_concept UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (from_concept, to_concept),
  CHECK (from_concept <> to_concept)
);

CREATE INDEX IF NOT EXISTS idx_concept_edges_course ON public.concept_edges(course_id);
CREATE INDEX IF NOT EXISTS idx_concept_edges_from ON public.concept_edges(from_concept);
CREATE INDEX IF NOT EXISTS idx_concept_edges_to ON public.concept_edges(to_concept);

-- Trigger to prevent cycles in prerequisite DAG
CREATE OR REPLACE FUNCTION public.check_concept_edge_cycles()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.from_concept = NEW.to_concept THEN
    RAISE EXCEPTION 'Concept cannot have a prerequisite edge to itself (concept_id: %).', NEW.from_concept;
  END IF;

  -- Verify both concepts belong to the same course
  IF (SELECT course_id FROM public.concepts WHERE id = NEW.from_concept) <>
     (SELECT course_id FROM public.concepts WHERE id = NEW.to_concept) THEN
    RAISE EXCEPTION 'Prerequisite edges can only connect concepts within the same course.';
  END IF;

  -- Check if a path from NEW.to_concept to NEW.from_concept already exists
  IF EXISTS (
    WITH RECURSIVE path AS (
      SELECT NEW.to_concept AS current_node
      UNION
      SELECT e.to_concept
      FROM public.concept_edges e
      JOIN path p ON e.from_concept = p.current_node
    )
    SELECT 1 FROM path WHERE current_node = NEW.from_concept
  ) THEN
    RAISE EXCEPTION 'Cycle detected: Adding prerequisite edge from % to % forms a circular dependency.',
      NEW.from_concept, NEW.to_concept;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  DROP TRIGGER IF EXISTS trg_prevent_concept_edge_cycles ON public.concept_edges;
  CREATE TRIGGER trg_prevent_concept_edge_cycles
    BEFORE INSERT OR UPDATE ON public.concept_edges
    FOR EACH ROW EXECUTE FUNCTION public.check_concept_edge_cycles();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================================================
-- 5. RUBRICS & RUBRIC CRITERIA
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.rubrics (
  id TEXT PRIMARY KEY,
  course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
  course_code TEXT NOT NULL,
  assignment_title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  total_points NUMERIC NOT NULL DEFAULT 100.0 CHECK (total_points > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evolve existing rubrics table if created from legacy 02 migration
ALTER TABLE public.rubrics ADD COLUMN IF NOT EXISTS course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE;
ALTER TABLE public.rubrics ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_rubrics_course_code ON public.rubrics(course_code);
CREATE INDEX IF NOT EXISTS idx_rubrics_course_id ON public.rubrics(course_id);

CREATE TABLE IF NOT EXISTS public.rubric_criteria (
  id TEXT PRIMARY KEY,
  rubric_id TEXT NOT NULL REFERENCES public.rubrics(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  max_points NUMERIC NOT NULL CHECK (max_points >= 0),
  weight_percent NUMERIC,
  order_index INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_rubric_criteria_rubric_order ON public.rubric_criteria(rubric_id, order_index);

-- ============================================================================
-- 6. ASSIGNMENTS & ASSIGNMENT CONCEPTS
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id UUID NOT NULL REFERENCES public.courses(id) ON DELETE CASCADE,
  rubric_id TEXT REFERENCES public.rubrics(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  due_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '14 days'),
  created_by UUID REFERENCES public.profiles(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evolve existing assignments table if created from legacy 01 migration
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS rubric_id TEXT REFERENCES public.rubrics(id) ON DELETE SET NULL;
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES public.profiles(id);
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_assignments_course ON public.assignments(course_id);
CREATE INDEX IF NOT EXISTS idx_assignments_rubric ON public.assignments(rubric_id);

CREATE TABLE IF NOT EXISTS public.assignment_concepts (
  assignment_id UUID NOT NULL REFERENCES public.assignments(id) ON DELETE CASCADE,
  concept_id UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  PRIMARY KEY (assignment_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_assignment_concepts_concept ON public.assignment_concepts(concept_id);

-- Enforce that assignment concepts belong to the same course as the assignment
CREATE OR REPLACE FUNCTION public.check_assignment_concept_course_match()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_assign_course UUID;
  v_concept_course UUID;
BEGIN
  SELECT course_id INTO v_assign_course FROM public.assignments WHERE id = NEW.assignment_id;
  SELECT course_id INTO v_concept_course FROM public.concepts WHERE id = NEW.concept_id;

  IF v_assign_course IS NULL OR v_concept_course IS NULL THEN
    RAISE EXCEPTION 'Referenced assignment or concept does not exist.';
  END IF;

  IF v_assign_course <> v_concept_course THEN
    RAISE EXCEPTION 'Assignment concept course mismatch: Assignment belongs to course % but Concept belongs to course %.',
      v_assign_course, v_concept_course;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  DROP TRIGGER IF EXISTS trg_check_assignment_concept_course_match ON public.assignment_concepts;
  CREATE TRIGGER trg_check_assignment_concept_course_match
    BEFORE INSERT OR UPDATE ON public.assignment_concepts
    FOR EACH ROW EXECUTE FUNCTION public.check_assignment_concept_course_match();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================================================
-- 7. AUTHORITATIVE SUBMISSIONS TABLE CONSOLIDATION
-- ============================================================================
-- Create or evolve the authoritative public.submissions table
CREATE TABLE IF NOT EXISTS public.submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id UUID REFERENCES public.assignments(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
  rubric_id TEXT REFERENCES public.rubrics(id) ON DELETE SET NULL,
  file_path TEXT NOT NULL DEFAULT '',
  file_name TEXT NOT NULL DEFAULT 'submission.pdf',
  file_size TEXT NOT NULL DEFAULT '0 B',
  file_type TEXT NOT NULL DEFAULT 'pdf' CHECK (file_type IN ('pdf', 'markdown', 'text')),
  file_url TEXT,
  content_preview TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'graded', 'done', 'failed', 'flagged')),
  processing_step TEXT CHECK (processing_step IN ('queued', 'extracting', 'grading', 'synced')),
  attempts INTEGER NOT NULL DEFAULT 1 CHECK (attempts >= 1),
  processing_started_at TIMESTAMPTZ,
  overall_score NUMERIC CHECK (overall_score IS NULL OR overall_score >= 0),
  feedback_summary TEXT,
  error_message TEXT,
  is_late BOOLEAN DEFAULT FALSE,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure all required columns exist on public.submissions
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE;
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS rubric_id TEXT REFERENCES public.rubrics(id) ON DELETE SET NULL;
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS file_name TEXT NOT NULL DEFAULT 'submission.pdf';
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS file_size TEXT NOT NULL DEFAULT '0 B';
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS file_type TEXT NOT NULL DEFAULT 'pdf';
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS file_url TEXT;
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS content_preview TEXT;
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS processing_step TEXT;
ALTER TABLE public.submissions ALTER COLUMN assignment_id DROP NOT NULL;
ALTER TABLE public.submissions ALTER COLUMN file_path DROP NOT NULL;
ALTER TABLE public.submissions ALTER COLUMN file_path SET DEFAULT '';
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE public.submissions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Evolve status check constraint to encompass all lifecycle states
DO $$
BEGIN
  ALTER TABLE public.submissions DROP CONSTRAINT IF EXISTS submissions_status_check;
  ALTER TABLE public.submissions ADD CONSTRAINT submissions_status_check
    CHECK (status IN ('pending', 'processing', 'graded', 'done', 'failed', 'flagged'));
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Single active submission constraint for MVP (assignment_id + student_id)
DO $$
BEGIN
  ALTER TABLE public.submissions DROP CONSTRAINT IF EXISTS submissions_assignment_student_unique;
  ALTER TABLE public.submissions DROP CONSTRAINT IF EXISTS submissions_assignment_id_student_id_key;
  CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_active_student_assignment
    ON public.submissions (assignment_id, student_id) WHERE assignment_id IS NOT NULL;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_submissions_student_submitted ON public.submissions(student_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_submissions_course_status ON public.submissions(course_id, status);
CREATE INDEX IF NOT EXISTS idx_submissions_rubric ON public.submissions(rubric_id);
CREATE INDEX IF NOT EXISTS idx_submissions_status_created ON public.submissions(status, created_at);

DO $$
BEGIN
  DROP TRIGGER IF EXISTS trg_submissions_updated_at ON public.submissions;
  CREATE TRIGGER trg_submissions_updated_at
    BEFORE UPDATE ON public.submissions
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================================================
-- 8. QUEUE: GRADING JOBS
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.grading_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'failed', 'flagged')),
  retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
  error_log TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evolve existing grading_jobs table if created from legacy 02 migration
ALTER TABLE public.grading_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE public.grading_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_grading_jobs_status ON public.grading_jobs(status, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_grading_jobs_submission ON public.grading_jobs(submission_id);

DO $$
BEGIN
  DROP TRIGGER IF EXISTS trg_grading_jobs_updated_at ON public.grading_jobs;
  CREATE TRIGGER trg_grading_jobs_updated_at
    BEFORE UPDATE ON public.grading_jobs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================================================
-- 9. EVALUATIONS & CRITERION EVALUATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL UNIQUE REFERENCES public.submissions(id) ON DELETE CASCADE,
  score NUMERIC NOT NULL CHECK (score >= 0),
  max_score NUMERIC NOT NULL DEFAULT 100.0 CHECK (max_score > 0),
  percentage NUMERIC NOT NULL CHECK (percentage BETWEEN 0 AND 100),
  summary_feedback TEXT NOT NULL DEFAULT '',
  strengths JSONB NOT NULL DEFAULT '[]'::jsonb,
  improvements JSONB NOT NULL DEFAULT '[]'::jsonb,
  ai_model_extraction TEXT DEFAULT 'Gemini Flash-Lite',
  ai_model_grading TEXT DEFAULT 'Gemini Flash',
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evaluations_submission ON public.evaluations(submission_id);

CREATE TABLE IF NOT EXISTS public.criterion_evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evaluation_id UUID NOT NULL REFERENCES public.evaluations(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  score_awarded NUMERIC NOT NULL CHECK (score_awarded >= 0),
  max_points NUMERIC NOT NULL CHECK (max_points >= 0),
  feedback TEXT NOT NULL DEFAULT '',
  strengths TEXT,
  improvements TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_criterion_evaluations_eval ON public.criterion_evaluations(evaluation_id);

-- ============================================================================
-- 10. CONCEPT FEEDBACK & STUDENT CONCEPT MASTERY
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.submission_concept_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
  concept_id UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  mastery_percentage NUMERIC CHECK (mastery_percentage BETWEEN 0 AND 100),
  feedback_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (submission_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_sub ON public.submission_concept_feedback(submission_id);
CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_concept ON public.submission_concept_feedback(concept_id);

CREATE TABLE IF NOT EXISTS public.student_concept_mastery (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  concept_id UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  submission_id UUID REFERENCES public.submissions(id) ON DELETE SET NULL,
  mastery_score NUMERIC(5, 4) NOT NULL DEFAULT 0.0 CHECK (mastery_score >= 0.0 AND mastery_score <= 1.0),
  confidence_score NUMERIC(5, 4) NOT NULL DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
  source VARCHAR(32) NOT NULL DEFAULT 'ai_evaluation' CHECK (source IN ('ai_evaluation', 'faculty_override', 'diagnostic_quiz', 'manual_adjustment')),
  evidence_count INT NOT NULL DEFAULT 1 CHECK (evidence_count >= 1),
  last_evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (student_id, concept_id)
);

-- Migration / Upgrade logic for pre-existing tables that had mastery_percentage
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'student_concept_mastery' AND column_name = 'mastery_percentage'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'student_concept_mastery' AND column_name = 'mastery_score'
  ) THEN
    ALTER TABLE public.student_concept_mastery ADD COLUMN mastery_score NUMERIC(5, 4) DEFAULT 0.0;
    UPDATE public.student_concept_mastery SET mastery_score = LEAST(1.0, GREATEST(0.0, ROUND(mastery_percentage / 100.0, 4)));
    ALTER TABLE public.student_concept_mastery ALTER COLUMN mastery_score SET NOT NULL;
  END IF;

  -- Add computed/backward-compatible mastery_percentage column if not present
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'public' AND table_name = 'student_concept_mastery' AND column_name = 'mastery_percentage'
  ) THEN
    ALTER TABLE public.student_concept_mastery ADD COLUMN mastery_percentage NUMERIC(5, 2) 
      GENERATED ALWAYS AS (ROUND(mastery_score * 100.0, 2)) STORED;
  END IF;

  -- Ensure evidence_count, confidence_score, and updated_at exist
  ALTER TABLE public.student_concept_mastery ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5, 4) DEFAULT 0.5;
  ALTER TABLE public.student_concept_mastery ADD COLUMN IF NOT EXISTS evidence_count INT DEFAULT 1;
  ALTER TABLE public.student_concept_mastery ADD COLUMN IF NOT EXISTS last_evaluated_at TIMESTAMPTZ DEFAULT NOW();
  ALTER TABLE public.student_concept_mastery ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_student_concept_mastery_lookup
  ON public.student_concept_mastery(student_id, concept_id, created_at DESC);

-- ============================================================================
-- 11. HUMAN OVERSIGHT: FACULTY OVERRIDES
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.faculty_overrides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id UUID NOT NULL REFERENCES public.submissions(id) ON DELETE CASCADE,
  is_overridden BOOLEAN NOT NULL DEFAULT TRUE,
  original_score NUMERIC NOT NULL,
  overridden_score NUMERIC NOT NULL CHECK (overridden_score >= 0),
  overridden_by UUID NOT NULL REFERENCES public.profiles(id),
  overridden_by_name TEXT NOT NULL,
  override_reason TEXT NOT NULL,
  criterion_adjustments JSONB,
  overridden_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evolve existing faculty_overrides table if created from legacy 02 migration
ALTER TABLE public.faculty_overrides ADD COLUMN IF NOT EXISTS overridden_by_name TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_faculty_overrides_submission_date
  ON public.faculty_overrides(submission_id, overridden_at DESC);

-- ============================================================================
-- 12. COMPATIBILITY LAYER: SUBMISSIONS_V2 VIEW WITH INSTEAD-OF TRIGGERS
-- ============================================================================
-- If submissions_v2 exists as a legacy physical table, migrate data and drop it
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'submissions_v2' AND table_type = 'BASE TABLE'
  ) THEN
    -- Migrate any rows from physical submissions_v2 into submissions
    INSERT INTO public.submissions (
      id, student_id, file_name, file_size, file_type, file_url, content_preview, rubric_id, status, processing_step, submitted_at
    )
    SELECT
      CASE WHEN v2.id ~ '^[0-9a-fA-F-]{36}$' THEN v2.id::UUID ELSE gen_random_uuid() END,
      CASE WHEN v2.student_id ~ '^[0-9a-fA-F-]{36}$' THEN v2.student_id::UUID 
           ELSE (SELECT id FROM public.profiles WHERE id::text = v2.student_id OR email = v2.student_email LIMIT 1) 
      END,
      v2.file_name, v2.file_size, v2.file_type, v2.file_url, v2.content_preview, v2.rubric_id, v2.status, v2.processing_step, v2.submitted_at
    FROM public.submissions_v2 v2
    WHERE CASE WHEN v2.student_id ~ '^[0-9a-fA-F-]{36}$' THEN v2.student_id::UUID 
               ELSE (SELECT id FROM public.profiles WHERE id::text = v2.student_id OR email = v2.student_email LIMIT 1) 
          END IS NOT NULL
    ON CONFLICT (id) DO NOTHING;

    DROP TABLE public.submissions_v2 CASCADE;
  END IF;
END $$;

-- Preserve backward-compatibility for Next.js frontend and legacy callers
CREATE OR REPLACE VIEW public.submissions_v2 AS
SELECT
  s.id::text AS id,
  s.student_id::text AS student_id,
  COALESCE(p.full_name, 'Student') AS student_name,
  COALESCE(p.email, '') AS student_email,
  COALESCE(s.assignment_id::text, s.rubric_id, 'assignment') AS assignment_id,
  COALESCE(a.title, r.assignment_title, 'Assignment') AS assignment_title,
  COALESCE(c.code, r.course_code, 'CS101') AS course_code,
  s.file_name,
  s.file_size,
  s.file_type,
  s.file_url,
  s.content_preview,
  s.rubric_id,
  s.status,
  s.processing_step,
  s.submitted_at,
  s.student_id AS owner_id
FROM public.submissions s
LEFT JOIN public.profiles p ON p.id = s.student_id
LEFT JOIN public.assignments a ON a.id = s.assignment_id
LEFT JOIN public.courses c ON c.id = s.course_id
LEFT JOIN public.rubrics r ON r.id = s.rubric_id;

-- Enable genuine INSERT, UPDATE, and DELETE operations against submissions_v2
CREATE OR REPLACE FUNCTION public.trg_submissions_v2_io_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_course_id UUID;
  v_student_id UUID;
  v_assignment_id UUID;
  v_sub_id UUID;
BEGIN
  -- Resolve student_id
  IF NEW.student_id IS NOT NULL AND NEW.student_id ~ '^[0-9a-fA-F-]{36}$' THEN
    v_student_id := NEW.student_id::UUID;
  ELSE
    SELECT id INTO v_student_id FROM public.profiles 
    WHERE id::text = NEW.student_id OR email = NEW.student_email LIMIT 1;
    IF v_student_id IS NULL THEN
      v_student_id := auth.uid();
    END IF;
  END IF;

  -- Resolve course_id
  IF NEW.course_code IS NOT NULL THEN
    SELECT id INTO v_course_id FROM public.courses WHERE code = NEW.course_code LIMIT 1;
  END IF;

  -- Resolve assignment_id if UUID
  IF NEW.assignment_id IS NOT NULL AND NEW.assignment_id ~ '^[0-9a-fA-F-]{36}$' THEN
    v_assignment_id := NEW.assignment_id::UUID;
  END IF;

  v_sub_id := COALESCE(NULLIF(NEW.id, '')::UUID, gen_random_uuid());

  INSERT INTO public.submissions (
    id,
    assignment_id,
    student_id,
    course_id,
    rubric_id,
    file_name,
    file_size,
    file_type,
    file_url,
    content_preview,
    status,
    processing_step,
    submitted_at
  ) VALUES (
    v_sub_id,
    v_assignment_id,
    v_student_id,
    v_course_id,
    NEW.rubric_id,
    COALESCE(NEW.file_name, 'submission.pdf'),
    COALESCE(NEW.file_size, '0 B'),
    COALESCE(NEW.file_type, 'pdf'),
    NEW.file_url,
    NEW.content_preview,
    COALESCE(NEW.status, 'pending'),
    COALESCE(NEW.processing_step, 'queued'),
    COALESCE(NEW.submitted_at, NOW())
  )
  ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    processing_step = EXCLUDED.processing_step,
    file_name = EXCLUDED.file_name,
    file_size = EXCLUDED.file_size,
    file_type = EXCLUDED.file_type,
    file_url = EXCLUDED.file_url,
    content_preview = EXCLUDED.content_preview,
    updated_at = NOW();

  NEW.id := v_sub_id::text;
  NEW.student_id := v_student_id::text;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.trg_submissions_v2_io_update()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.submissions SET
    status = COALESCE(NEW.status, status),
    processing_step = COALESCE(NEW.processing_step, processing_step),
    file_name = COALESCE(NEW.file_name, file_name),
    file_size = COALESCE(NEW.file_size, file_size),
    file_type = COALESCE(NEW.file_type, file_type),
    file_url = COALESCE(NEW.file_url, file_url),
    content_preview = COALESCE(NEW.content_preview, content_preview),
    rubric_id = COALESCE(NEW.rubric_id, rubric_id),
    updated_at = NOW()
  WHERE id = OLD.id::UUID;

  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.trg_submissions_v2_io_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  DELETE FROM public.submissions WHERE id = OLD.id::UUID;
  RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS trg_submissions_v2_insert ON public.submissions_v2;
CREATE TRIGGER trg_submissions_v2_insert
  INSTEAD OF INSERT ON public.submissions_v2
  FOR EACH ROW EXECUTE FUNCTION public.trg_submissions_v2_io_insert();

DROP TRIGGER IF EXISTS trg_submissions_v2_update ON public.submissions_v2;
CREATE TRIGGER trg_submissions_v2_update
  INSTEAD OF UPDATE ON public.submissions_v2
  FOR EACH ROW EXECUTE FUNCTION public.trg_submissions_v2_io_update();

DROP TRIGGER IF EXISTS trg_submissions_v2_delete ON public.submissions_v2;
CREATE TRIGGER trg_submissions_v2_delete
  INSTEAD OF DELETE ON public.submissions_v2
  FOR EACH ROW EXECUTE FUNCTION public.trg_submissions_v2_io_delete();

-- ============================================================================
-- 13. REALTIME PUBLICATIONS
-- ============================================================================
DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE public.submissions;
EXCEPTION WHEN DUPLICATE_OBJECT THEN NULL; WHEN UNDEFINED_OBJECT THEN NULL;
END $$;

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE public.student_concept_mastery;
EXCEPTION WHEN DUPLICATE_OBJECT THEN NULL; WHEN UNDEFINED_OBJECT THEN NULL;
END $$;

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE public.rubrics;
EXCEPTION WHEN DUPLICATE_OBJECT THEN NULL; WHEN UNDEFINED_OBJECT THEN NULL;
END $$;
