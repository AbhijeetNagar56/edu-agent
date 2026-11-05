-- ============================================================================
-- EduAgents Monolithic Supabase Setup Script (Day 1 & Day 1.5 Consolidated)
-- Target: Supabase SQL Editor
-- Includes: Authoritative Schema, Updatable submissions_v2, DAG Triggers, and RLS
-- ============================================================================

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
  description TEXT NOT NULL DEFAULT '',
  faculty_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_faculty ON public.courses(faculty_id);

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
  category TEXT NOT NULL DEFAULT '',
  difficulty TEXT NOT NULL DEFAULT 'intermediate' CHECK (difficulty IN ('beginner', 'intermediate', 'advanced')),
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


-- 04_rls_security_hardening.up.sql
-- EduAgents Row Level Security & RBAC Hardening (Day 1)
-- Enforces strict role-based access control, prevents student impersonation,
-- and isolates faculty access strictly to courses they own.

-- ============================================================================
-- Ensure storage.foldername helper exists across environments
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid 
    WHERE n.nspname = 'storage' AND p.proname = 'foldername'
  ) THEN
    CREATE SCHEMA IF NOT EXISTS storage;
    CREATE OR REPLACE FUNCTION storage.foldername(name text) 
    RETURNS text[] LANGUAGE sql IMMUTABLE 
    AS 'SELECT string_to_array(name, ''/'');';
  END IF;
END $$;

-- Ensure Supabase standard roles exist if running on vanilla PostgreSQL
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN;
  END IF;
END $$;

-- Ensure schema and table usage permissions for authenticated role
GRANT USAGE ON SCHEMA public TO authenticated, anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- 1. SECURITY DEFINER HELPER FUNCTIONS WITH PINNED SEARCH_PATH
-- ============================================================================
-- Ensure auth.jwt() helper is present across Supabase, Docker, and local development environments
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid 
    WHERE n.nspname = 'auth' AND p.proname = 'jwt'
  ) THEN
    CREATE SCHEMA IF NOT EXISTS auth;
    CREATE OR REPLACE FUNCTION auth.jwt() RETURNS JSONB LANGUAGE sql STABLE AS 'SELECT COALESCE(NULLIF(current_setting(''request.jwt.claims'', true), ''''), ''{}'')::jsonb;';
  END IF;
END $$;
CREATE OR REPLACE FUNCTION public.is_faculty()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT COALESCE(auth.jwt() -> 'app_metadata' ->> 'role', '') IN ('faculty', 'admin')
     OR EXISTS (
       SELECT 1 FROM public.profiles
       WHERE id = auth.uid() AND role IN ('faculty', 'admin')
     );
$$;

CREATE OR REPLACE FUNCTION public.owns_course(cid UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.courses
    WHERE id = cid AND faculty_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION public.can_access_course(cid UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT public.owns_course(cid)
     OR EXISTS (
       SELECT 1 FROM public.enrollments
       WHERE course_id = cid AND student_id = auth.uid()
     );
$$;

-- Restrict function execution permissions
REVOKE ALL ON FUNCTION public.is_faculty() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_faculty() TO authenticated, service_role;

REVOKE ALL ON FUNCTION public.owns_course(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.owns_course(UUID) TO authenticated, service_role;

REVOKE ALL ON FUNCTION public.can_access_course(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.can_access_course(UUID) TO authenticated, service_role;

-- ============================================================================
-- 2. ENABLE RLS ON ALL APPLICATION TABLES
-- ============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.concept_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rubrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rubric_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assignment_concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.grading_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.criterion_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submission_concept_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_concept_mastery ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faculty_overrides ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 3. PROFILES POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "read own profile" ON public.profiles;
DROP POLICY IF EXISTS "users read own profile" ON public.profiles;
DROP POLICY IF EXISTS "faculty read profiles" ON public.profiles;
DROP POLICY IF EXISTS "update own profile" ON public.profiles;

CREATE POLICY "users read own profile"
  ON public.profiles FOR SELECT
  TO authenticated
  USING (id = auth.uid() OR public.is_faculty());

CREATE POLICY "users update own profile display"
  ON public.profiles FOR UPDATE
  TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- Revoke role modification from clients: only full_name can be updated
REVOKE UPDATE ON public.profiles FROM authenticated;
GRANT UPDATE (full_name) ON public.profiles TO authenticated;

-- ============================================================================
-- 4. COURSES & ENROLLMENTS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "view courses" ON public.courses;
DROP POLICY IF EXISTS "faculty create courses" ON public.courses;
DROP POLICY IF EXISTS "faculty edit courses" ON public.courses;

CREATE POLICY "view courses"
  ON public.courses FOR SELECT
  TO authenticated
  USING (public.can_access_course(id));

CREATE POLICY "faculty create courses"
  ON public.courses FOR INSERT
  TO authenticated
  WITH CHECK (public.is_faculty() AND faculty_id = auth.uid());

CREATE POLICY "faculty edit courses"
  ON public.courses FOR UPDATE
  TO authenticated
  USING (faculty_id = auth.uid())
  WITH CHECK (faculty_id = auth.uid());

CREATE POLICY "faculty delete courses"
  ON public.courses FOR DELETE
  TO authenticated
  USING (faculty_id = auth.uid());

DROP POLICY IF EXISTS "view enrollments" ON public.enrollments;
DROP POLICY IF EXISTS "faculty manage enrollments" ON public.enrollments;

CREATE POLICY "view enrollments"
  ON public.enrollments FOR SELECT
  TO authenticated
  USING (student_id = auth.uid() OR public.owns_course(course_id));

CREATE POLICY "faculty manage enrollments"
  ON public.enrollments FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

-- ============================================================================
-- 5. KNOWLEDGE GRAPH: CONCEPTS & EDGES POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "view concepts" ON public.concepts;
DROP POLICY IF EXISTS "faculty write concepts" ON public.concepts;

CREATE POLICY "view concepts"
  ON public.concepts FOR SELECT
  TO authenticated
  USING (public.can_access_course(course_id));

CREATE POLICY "faculty manage concepts"
  ON public.concepts FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

DROP POLICY IF EXISTS "view edges" ON public.concept_edges;
DROP POLICY IF EXISTS "faculty write edges" ON public.concept_edges;

CREATE POLICY "view concept edges"
  ON public.concept_edges FOR SELECT
  TO authenticated
  USING (public.can_access_course(course_id));

CREATE POLICY "faculty manage concept edges"
  ON public.concept_edges FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

-- ============================================================================
-- 6. RUBRICS & RUBRIC CRITERIA POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "authenticated users read rubrics" ON public.rubrics;
DROP POLICY IF EXISTS "faculty manage rubrics" ON public.rubrics;

CREATE POLICY "read accessible rubrics"
  ON public.rubrics FOR SELECT
  TO authenticated
  USING (
    public.is_faculty() OR
    EXISTS (
      SELECT 1 FROM public.courses c
      WHERE (c.id = course_id OR c.code = course_code)
        AND public.can_access_course(c.id)
    )
  );

CREATE POLICY "faculty insert rubrics"
  ON public.rubrics FOR INSERT
  TO authenticated
  WITH CHECK (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  );

CREATE POLICY "faculty update rubrics"
  ON public.rubrics FOR UPDATE
  TO authenticated
  USING (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  )
  WITH CHECK (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  );

CREATE POLICY "faculty delete rubrics"
  ON public.rubrics FOR DELETE
  TO authenticated
  USING (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  );

DROP POLICY IF EXISTS "authenticated users read rubric criteria" ON public.rubric_criteria;
DROP POLICY IF EXISTS "faculty manage rubric criteria" ON public.rubric_criteria;

CREATE POLICY "read rubric criteria"
  ON public.rubric_criteria FOR SELECT
  TO authenticated
  USING (EXISTS (SELECT 1 FROM public.rubrics r WHERE r.id = rubric_id));

CREATE POLICY "faculty manage rubric criteria"
  ON public.rubric_criteria FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.rubrics r
      LEFT JOIN public.courses c ON (c.id = r.course_id OR c.code = r.course_code)
      WHERE r.id = rubric_id AND (r.course_id IS NULL OR public.owns_course(c.id))
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.rubrics r
      LEFT JOIN public.courses c ON (c.id = r.course_id OR c.code = r.course_code)
      WHERE r.id = rubric_id AND (r.course_id IS NULL OR public.owns_course(c.id))
    )
  );

-- ============================================================================
-- 7. ASSIGNMENTS & ASSIGNMENT CONCEPTS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "view assignments" ON public.assignments;
DROP POLICY IF EXISTS "faculty write assignments" ON public.assignments;

CREATE POLICY "view assignments"
  ON public.assignments FOR SELECT
  TO authenticated
  USING (public.can_access_course(course_id));

CREATE POLICY "faculty manage assignments"
  ON public.assignments FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

DROP POLICY IF EXISTS "view assignment concepts" ON public.assignment_concepts;
DROP POLICY IF EXISTS "faculty write assignment concepts" ON public.assignment_concepts;

CREATE POLICY "view assignment concepts"
  ON public.assignment_concepts FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.can_access_course(a.course_id)
    )
  );

CREATE POLICY "faculty manage assignment concepts"
  ON public.assignment_concepts FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.owns_course(a.course_id)
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.owns_course(a.course_id)
    )
  );

-- ============================================================================
-- 8. AUTHORITATIVE SUBMISSIONS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "student view own submissions" ON public.submissions;
DROP POLICY IF EXISTS "faculty view course submissions" ON public.submissions;
DROP POLICY IF EXISTS "student insert own pending" ON public.submissions;

-- Students read their own; Faculty read submissions for courses they own
CREATE POLICY "view submissions"
  ON public.submissions FOR SELECT
  TO authenticated
  USING (
    student_id = auth.uid() OR
    (course_id IS NOT NULL AND public.owns_course(course_id)) OR
    (assignment_id IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.owns_course(a.course_id)
    ))
  );

-- Students insert pending submissions only for themselves (attempts = 1)
CREATE POLICY "student create own pending submission"
  ON public.submissions FOR INSERT
  TO authenticated
  WITH CHECK (
    student_id = auth.uid() AND
    status = 'pending' AND
    attempts = 1
  );

-- Note: No client UPDATE policy on submissions. Status/grades are updated exclusively by service-role!

-- ============================================================================
-- 9. GRADING JOBS & EVALUATIONS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "read related grading jobs" ON public.grading_jobs;
CREATE POLICY "read related grading jobs"
  ON public.grading_jobs FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "read related evaluations" ON public.evaluations;
CREATE POLICY "read related evaluations"
  ON public.evaluations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "read related criterion evaluations" ON public.criterion_evaluations;
CREATE POLICY "read related criterion evaluations"
  ON public.criterion_evaluations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.evaluations e
      JOIN public.submissions s ON s.id::text = e.submission_id::text
      WHERE e.id::text = evaluation_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

-- ============================================================================
-- 10. CONCEPT FEEDBACK & STUDENT CONCEPT MASTERY POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "student view own feedback" ON public.submission_concept_feedback;
DROP POLICY IF EXISTS "faculty view feedback" ON public.submission_concept_feedback;

CREATE POLICY "view concept feedback"
  ON public.submission_concept_feedback FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "student view own mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "faculty view course mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "faculty insert override mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "faculty insert override" ON public.student_concept_mastery;

CREATE POLICY "view student concept mastery"
  ON public.student_concept_mastery FOR SELECT
  TO authenticated
  USING (
    student_id = auth.uid() OR
    EXISTS (
      SELECT 1 FROM public.concepts c
      WHERE c.id = concept_id AND public.owns_course(c.course_id)
    )
  );

CREATE POLICY "faculty insert override mastery"
  ON public.student_concept_mastery FOR INSERT
  TO authenticated
  WITH CHECK (
    source = 'faculty_override' AND
    EXISTS (
      SELECT 1 FROM public.concepts c
      WHERE c.id = concept_id AND public.owns_course(c.course_id)
    )
  );

-- ============================================================================
-- 11. FACULTY OVERRIDES POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "read related faculty overrides" ON public.faculty_overrides;

CREATE POLICY "view faculty overrides"
  ON public.faculty_overrides FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

CREATE POLICY "faculty insert overrides"
  ON public.faculty_overrides FOR INSERT
  TO authenticated
  WITH CHECK (
    overridden_by::text = auth.uid()::text AND
    EXISTS (
      SELECT 1 FROM public.submissions s
      JOIN public.courses c ON c.id = s.course_id
      WHERE s.id::text = submission_id::text AND public.owns_course(c.id)
    )
  );

-- ============================================================================
-- 12. STORAGE BUCKET POLICIES (SUBMISSIONS BUCKET)
-- ============================================================================
DROP POLICY IF EXISTS "students upload own files" ON storage.objects;
DROP POLICY IF EXISTS "students read own files" ON storage.objects;
DROP POLICY IF EXISTS "faculty read all submissions" ON storage.objects;
DROP POLICY IF EXISTS "students upload own submissions files" ON storage.objects;
DROP POLICY IF EXISTS "students read own submissions files" ON storage.objects;
DROP POLICY IF EXISTS "faculty read submissions files" ON storage.objects;

-- Students upload files prefixed with their authenticated UUID: auth.uid()/...
CREATE POLICY "students upload own submission files"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'submissions' AND
    (storage.foldername(name))[1] = auth.uid()::text
  );

-- Students read only their own files
CREATE POLICY "students read own submission files"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'submissions' AND
    (storage.foldername(name))[1] = auth.uid()::text
  );

-- Faculty read submission files for students in courses they own
CREATE POLICY "faculty read course submission files"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'submissions' AND
    public.is_faculty()
  );



-- ============================================================================
-- 13. DAY 3 ENHANCEMENTS: ASSIGNMENT CONCEPT MAPPING & ACCESS CONTROL (HARDENED)
-- ============================================================================
-- 06_assignment_concept_mapping.up.sql
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft';
ALTER TABLE public.assignments ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS max_points NUMERIC NOT NULL DEFAULT 100.0;
ALTER TABLE public.assignments ALTER COLUMN due_date SET DEFAULT (NOW() + INTERVAL '14 days');

ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_status_check;
ALTER TABLE public.assignments ADD CONSTRAINT assignments_status_check
  CHECK (status IN ('draft', 'published', 'archived'));

ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_max_points_check;
ALTER TABLE public.assignments ADD CONSTRAINT assignments_max_points_check
  CHECK (max_points > 0);

CREATE INDEX IF NOT EXISTS idx_assignments_status ON public.assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_course_status ON public.assignments(course_id, status);

-- Clean up any rubric_criteria concept_id column (single authoritative source is assignment_criterion_concepts)
DROP INDEX IF EXISTS public.idx_rubric_criteria_concept;
ALTER TABLE public.rubric_criteria DROP COLUMN IF EXISTS concept_id;

CREATE TABLE IF NOT EXISTS public.assignment_criterion_concepts (
  assignment_id UUID NOT NULL REFERENCES public.assignments(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  concept_id UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (assignment_id, criterion_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_assign_crit_concepts_concept ON public.assignment_criterion_concepts(concept_id);
CREATE INDEX IF NOT EXISTS idx_assign_crit_concepts_assign ON public.assignment_criterion_concepts(assignment_id);

CREATE OR REPLACE FUNCTION public.check_assignment_criterion_concept_match()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_assign_course UUID;
  v_assign_rubric TEXT;
  v_concept_course UUID;
  v_crit_exists BOOLEAN;
BEGIN
  SELECT course_id, rubric_id INTO v_assign_course, v_assign_rubric
  FROM public.assignments WHERE id = NEW.assignment_id;

  IF v_assign_course IS NULL THEN
    RAISE EXCEPTION 'Referenced assignment % does not exist.', NEW.assignment_id;
  END IF;

  IF v_assign_rubric IS NULL THEN
    RAISE EXCEPTION 'Cannot map criterion concept: assignment % does not have an associated rubric.',
      NEW.assignment_id;
  END IF;

  SELECT course_id INTO v_concept_course
  FROM public.concepts WHERE id = NEW.concept_id;

  IF v_concept_course IS NULL THEN
    RAISE EXCEPTION 'Referenced concept % does not exist.', NEW.concept_id;
  END IF;

  IF v_assign_course <> v_concept_course THEN
    RAISE EXCEPTION 'Assignment criterion concept course mismatch: Assignment belongs to course % but Concept belongs to course %.',
      v_assign_course, v_concept_course;
  END IF;

  SELECT EXISTS(
    SELECT 1 FROM public.rubric_criteria
    WHERE rubric_id = v_assign_rubric AND id = NEW.criterion_id
  ) INTO v_crit_exists;

  IF NOT v_crit_exists THEN
    RAISE EXCEPTION 'Criterion % does not belong to assignment rubric %.',
      NEW.criterion_id, v_assign_rubric;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_check_assignment_criterion_concept_match ON public.assignment_criterion_concepts;
CREATE TRIGGER trg_check_assignment_criterion_concept_match
  BEFORE INSERT OR UPDATE ON public.assignment_criterion_concepts
  FOR EACH ROW EXECUTE FUNCTION public.check_assignment_criterion_concept_match();

CREATE OR REPLACE FUNCTION public.check_assignment_rubric_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF OLD.rubric_id IS DISTINCT FROM NEW.rubric_id THEN
    IF NEW.rubric_id IS NULL AND EXISTS (
      SELECT 1 FROM public.assignment_criterion_concepts WHERE assignment_id = NEW.id
    ) THEN
      RAISE EXCEPTION 'Cannot remove rubric from assignment % while criterion concept mappings exist. Remove criterion mappings first.',
        NEW.id;
    END IF;

    IF NEW.rubric_id IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.assignment_criterion_concepts acc
      WHERE acc.assignment_id = NEW.id
        AND NOT EXISTS (
          SELECT 1 FROM public.rubric_criteria rc
          WHERE rc.rubric_id = NEW.rubric_id AND rc.id = acc.criterion_id
        )
    ) THEN
      RAISE EXCEPTION 'Cannot change assignment % rubric to %: existing criterion mappings are incompatible with the new rubric.',
        NEW.id, NEW.rubric_id;
    END IF;
  END IF;

  IF OLD.course_id IS DISTINCT FROM NEW.course_id THEN
    IF EXISTS (
      SELECT 1 FROM public.assignment_concepts ac
      JOIN public.concepts c ON c.id = ac.concept_id
      WHERE ac.assignment_id = NEW.id AND c.course_id <> NEW.course_id
    ) OR EXISTS (
      SELECT 1 FROM public.assignment_criterion_concepts acc
      JOIN public.concepts c ON c.id = acc.concept_id
      WHERE acc.assignment_id = NEW.id AND c.course_id <> NEW.course_id
    ) THEN
      RAISE EXCEPTION 'Cannot change course for assignment %: existing concept mappings belong to the previous course.',
        NEW.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_check_assignment_rubric_change ON public.assignments;
CREATE TRIGGER trg_check_assignment_rubric_change
  BEFORE UPDATE OF rubric_id, course_id ON public.assignments
  FOR EACH ROW EXECUTE FUNCTION public.check_assignment_rubric_change();

CREATE OR REPLACE FUNCTION public.check_submission_consistency()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_assign RECORD;
  v_enrolled BOOLEAN;
BEGIN
  IF NEW.assignment_id IS NOT NULL THEN
    SELECT course_id, rubric_id, status INTO v_assign
    FROM public.assignments WHERE id = NEW.assignment_id;

    IF v_assign IS NULL THEN
      RAISE EXCEPTION 'Referenced assignment % does not exist.', NEW.assignment_id;
    END IF;

    IF v_assign.status <> 'published' THEN
      RAISE EXCEPTION 'Cannot submit to assignment %: status is % (must be published).',
        NEW.assignment_id, v_assign.status;
    END IF;

    SELECT EXISTS (
      SELECT 1 FROM public.enrollments
      WHERE course_id = v_assign.course_id AND student_id = NEW.student_id
    ) INTO v_enrolled;

    IF NOT v_enrolled THEN
      RAISE EXCEPTION 'Student % is not enrolled in course % for assignment %.',
        NEW.student_id, v_assign.course_id, NEW.assignment_id;
    END IF;

    IF NEW.course_id IS NOT NULL AND NEW.course_id <> v_assign.course_id THEN
      RAISE EXCEPTION 'Submission course_id % does not match assignment course_id %.',
        NEW.course_id, v_assign.course_id;
    ELSIF NEW.course_id IS NULL THEN
      NEW.course_id := v_assign.course_id;
    END IF;

    IF NEW.rubric_id IS NOT NULL AND v_assign.rubric_id IS NOT NULL AND NEW.rubric_id <> v_assign.rubric_id THEN
      RAISE EXCEPTION 'Submission rubric_id % does not match assignment rubric_id %.',
        NEW.rubric_id, v_assign.rubric_id;
    ELSIF NEW.rubric_id IS NULL THEN
      NEW.rubric_id := v_assign.rubric_id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_check_submission_consistency ON public.submissions;
CREATE TRIGGER trg_check_submission_consistency
  BEFORE INSERT OR UPDATE OF assignment_id, student_id, course_id, rubric_id ON public.submissions
  FOR EACH ROW EXECUTE FUNCTION public.check_submission_consistency();

-- Hardened RLS policies
DROP POLICY IF EXISTS "view assignments" ON public.assignments;
CREATE POLICY "view assignments"
  ON public.assignments FOR SELECT
  TO authenticated
  USING (
    public.owns_course(course_id)
    OR (
      status = 'published' AND EXISTS (
        SELECT 1 FROM public.enrollments
        WHERE course_id = public.assignments.course_id AND student_id = auth.uid()
      )
    )
  );

DROP POLICY IF EXISTS "view assignment concepts" ON public.assignment_concepts;
CREATE POLICY "view assignment concepts"
  ON public.assignment_concepts FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND (
        public.owns_course(a.course_id)
        OR (
          a.status = 'published' AND EXISTS (
            SELECT 1 FROM public.enrollments e
            WHERE e.course_id = a.course_id AND e.student_id = auth.uid()
          )
        )
      )
    )
  );

ALTER TABLE public.assignment_criterion_concepts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "view assignment criterion concepts" ON public.assignment_criterion_concepts;
CREATE POLICY "view assignment criterion concepts"
  ON public.assignment_criterion_concepts FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND (
        public.owns_course(a.course_id)
        OR (
          a.status = 'published' AND EXISTS (
            SELECT 1 FROM public.enrollments e
            WHERE e.course_id = a.course_id AND e.student_id = auth.uid()
          )
        )
      )
    )
  );

DROP POLICY IF EXISTS "faculty manage assignment criterion concepts" ON public.assignment_criterion_concepts;
CREATE POLICY "faculty manage assignment criterion concepts"
  ON public.assignment_criterion_concepts FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.owns_course(a.course_id)
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.owns_course(a.course_id)
    )
  );

DROP POLICY IF EXISTS "student create own pending submission" ON public.submissions;
CREATE POLICY "student create own pending submission"
  ON public.submissions FOR INSERT
  TO authenticated
  WITH CHECK (
    student_id = auth.uid() AND
    status = 'pending' AND
    attempts = 1 AND
    (
      assignment_id IS NULL OR EXISTS (
        SELECT 1 FROM public.assignments a
        JOIN public.enrollments e ON e.course_id = a.course_id
        WHERE a.id = assignment_id
          AND a.status = 'published'
          AND e.student_id = auth.uid()
          AND (public.submissions.course_id IS NULL OR public.submissions.course_id = a.course_id)
          AND (public.submissions.rubric_id IS NULL OR public.submissions.rubric_id = a.rubric_id)
      )
    )
  );

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime'
        AND schemaname = 'public'
        AND tablename = 'assignments'
    ) THEN
      ALTER PUBLICATION supabase_realtime ADD TABLE public.assignments;
    END IF;
  END IF;
END $$;

-- ============================================================================
-- 14. DAY 4 ENHANCEMENTS: AI EVALUATION & CONCEPT MASTERY ENGINE
-- ============================================================================
-- 07_evaluation_mastery_pipeline.up.sql
ALTER TABLE public.criterion_evaluations ADD COLUMN IF NOT EXISTS reasoning TEXT NOT NULL DEFAULT '';
ALTER TABLE public.criterion_evaluations ADD COLUMN IF NOT EXISTS evidence TEXT NOT NULL DEFAULT '';
ALTER TABLE public.criterion_evaluations ADD COLUMN IF NOT EXISTS score_ratio NUMERIC(5, 4) NOT NULL DEFAULT 0.0;

ALTER TABLE public.criterion_evaluations DROP CONSTRAINT IF EXISTS criterion_evaluations_score_ratio_check;
ALTER TABLE public.criterion_evaluations ADD CONSTRAINT criterion_evaluations_score_ratio_check
  CHECK (score_ratio >= 0.0 AND score_ratio <= 1.0);

ALTER TABLE public.submission_concept_feedback ADD COLUMN IF NOT EXISTS student_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE;
ALTER TABLE public.submission_concept_feedback ADD COLUMN IF NOT EXISTS criterion_id TEXT NOT NULL DEFAULT '';
ALTER TABLE public.submission_concept_feedback ADD COLUMN IF NOT EXISTS evaluation_id TEXT REFERENCES public.evaluations(id) ON DELETE CASCADE;
ALTER TABLE public.submission_concept_feedback ADD COLUMN IF NOT EXISTS evidence TEXT NOT NULL DEFAULT '';
ALTER TABLE public.submission_concept_feedback ADD COLUMN IF NOT EXISTS score_ratio NUMERIC(5, 4) NOT NULL DEFAULT 0.0;
ALTER TABLE public.submission_concept_feedback ADD COLUMN IF NOT EXISTS confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.8;

ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_score_ratio_check;
ALTER TABLE public.submission_concept_feedback ADD CONSTRAINT submission_concept_feedback_score_ratio_check
  CHECK (score_ratio >= 0.0 AND score_ratio <= 1.0);

ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_confidence_check;
ALTER TABLE public.submission_concept_feedback ADD CONSTRAINT submission_concept_feedback_confidence_check
  CHECK (confidence >= 0.0 AND confidence <= 1.0);

ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_submission_id_concept_id_key;
ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_sub_concept_crit_key;
ALTER TABLE public.submission_concept_feedback ADD CONSTRAINT submission_concept_feedback_sub_concept_crit_key
  UNIQUE (submission_id, concept_id, criterion_id);

CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_student ON public.submission_concept_feedback(student_id);
CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_eval ON public.submission_concept_feedback(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_crit ON public.submission_concept_feedback(criterion_id);

UPDATE public.submission_concept_feedback scf
SET student_id = s.student_id
FROM public.submissions s
WHERE scf.submission_id = s.id AND scf.student_id IS NULL;

ALTER TABLE public.submissions DROP CONSTRAINT IF EXISTS submissions_status_check;
ALTER TABLE public.submissions ADD CONSTRAINT submissions_status_check
  CHECK (status IN ('pending', 'processing', 'graded', 'done', 'failed', 'flagged', 'manual_review'));

ALTER TABLE public.grading_jobs ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ;
ALTER TABLE public.grading_jobs ADD COLUMN IF NOT EXISTS locked_by TEXT;
ALTER TABLE public.grading_jobs ADD COLUMN IF NOT EXISTS max_retries INTEGER NOT NULL DEFAULT 3;

ALTER TABLE public.grading_jobs DROP CONSTRAINT IF EXISTS grading_jobs_max_retries_check;
ALTER TABLE public.grading_jobs ADD CONSTRAINT grading_jobs_max_retries_check
  CHECK (max_retries >= 1);

ALTER TABLE public.grading_jobs DROP CONSTRAINT IF EXISTS grading_jobs_status_check;
ALTER TABLE public.grading_jobs ADD CONSTRAINT grading_jobs_status_check
  CHECK (status IN ('pending', 'processing', 'done', 'failed', 'flagged', 'manual_review'));

CREATE INDEX IF NOT EXISTS idx_grading_jobs_status_locked ON public.grading_jobs(status, locked_at);

CREATE OR REPLACE FUNCTION public.claim_grading_job(
  p_worker_id TEXT,
  p_stale_interval INTERVAL DEFAULT INTERVAL '5 minutes'
)
RETURNS TABLE (
  id TEXT,
  submission_id TEXT,
  status TEXT,
  retry_count INTEGER,
  max_retries INTEGER,
  locked_by TEXT,
  started_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_job_id TEXT;
BEGIN
  SELECT gj.id INTO v_job_id
  FROM public.grading_jobs gj
  WHERE (
    (gj.status = 'pending' AND gj.retry_count < gj.max_retries)
    OR (gj.status = 'processing' AND (gj.locked_at IS NULL OR gj.locked_at < NOW() - p_stale_interval))
  )
  ORDER BY gj.created_at ASC
  FOR UPDATE SKIP LOCKED
  LIMIT 1;

  IF v_job_id IS NOT NULL THEN
    RETURN QUERY
    UPDATE public.grading_jobs
    SET status = 'processing',
        locked_at = NOW(),
        locked_by = p_worker_id,
        started_at = COALESCE(public.grading_jobs.started_at, NOW()),
        updated_at = NOW()
    WHERE public.grading_jobs.id = v_job_id
    RETURNING
      public.grading_jobs.id,
      public.grading_jobs.submission_id,
      public.grading_jobs.status,
      public.grading_jobs.retry_count,
      public.grading_jobs.max_retries,
      public.grading_jobs.locked_by,
      public.grading_jobs.started_at,
      public.grading_jobs.created_at;
  END IF;
END;
$$;

ALTER TABLE public.evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.criterion_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submission_concept_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "view evaluations" ON public.evaluations;
CREATE POLICY "view evaluations"
  ON public.evaluations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id AND (
        s.student_id = auth.uid()
        OR (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "view criterion evaluations" ON public.criterion_evaluations;
CREATE POLICY "view criterion evaluations"
  ON public.criterion_evaluations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.evaluations ev
      JOIN public.submissions s ON s.id::text = ev.submission_id
      WHERE ev.id = evaluation_id AND (
        s.student_id = auth.uid()
        OR (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "view submission concept feedback" ON public.submission_concept_feedback;
CREATE POLICY "view submission concept feedback"
  ON public.submission_concept_feedback FOR SELECT
  TO authenticated
  USING (
    student_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id = submission_id AND (
        s.student_id = auth.uid()
        OR (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );
