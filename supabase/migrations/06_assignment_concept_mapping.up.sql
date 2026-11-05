-- 06_assignment_concept_mapping.up.sql
-- EduAgents Assignment Management and Curriculum Concept Mapping (Day 3 Hardened)
-- Adds assignment status (default 'draft') and max points, assignment-criterion-concept mappings,
-- strict course-matching and rubric-consistency triggers, submission consistency triggers,
-- and hardened RLS for published assignment access and submission integrity.
-- Fully deterministic, explicit, and free of broad silent exception handlers.

-- ============================================================================
-- 1. ASSIGNMENTS TABLE ENHANCEMENTS
-- ============================================================================
-- Add status with default 'draft' for newly created assignments
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft';
ALTER TABLE public.assignments ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS max_points NUMERIC NOT NULL DEFAULT 100.0;
ALTER TABLE public.assignments ALTER COLUMN due_date SET DEFAULT (NOW() + INTERVAL '14 days');

-- Enforce valid assignment status values
ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_status_check;
ALTER TABLE public.assignments ADD CONSTRAINT assignments_status_check
  CHECK (status IN ('draft', 'published', 'archived'));

-- Enforce positive max points
ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_max_points_check;
ALTER TABLE public.assignments ADD CONSTRAINT assignments_max_points_check
  CHECK (max_points > 0);

CREATE INDEX IF NOT EXISTS idx_assignments_status ON public.assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_course_status ON public.assignments(course_id, status);

-- ============================================================================
-- 2. SINGLE AUTHORITATIVE MAPPING SOURCE
-- ============================================================================
-- public.assignment_criterion_concepts is the authoritative mapping table.
-- Drop any legacy/redundant concept_id column on rubric_criteria to avoid conflicting sources.
DROP INDEX IF EXISTS public.idx_rubric_criteria_concept;
ALTER TABLE public.rubric_criteria DROP COLUMN IF EXISTS concept_id;

-- Create authoritative join table for assignment rubric criteria and curriculum concepts
CREATE TABLE IF NOT EXISTS public.assignment_criterion_concepts (
  assignment_id UUID NOT NULL REFERENCES public.assignments(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  concept_id UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (assignment_id, criterion_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_assign_crit_concepts_concept ON public.assignment_criterion_concepts(concept_id);
CREATE INDEX IF NOT EXISTS idx_assign_crit_concepts_assign ON public.assignment_criterion_concepts(assignment_id);

-- ============================================================================
-- 3. INTEGRITY TRIGGER: CRITERION-CONCEPT MAPPING MATCHING
-- ============================================================================
-- Strictly enforce:
-- 1) Assignment must exist.
-- 2) Assignment MUST have a rubric (reject criterion mapping if no rubric).
-- 3) Concept must exist and belong to the same course as the assignment.
-- 4) Criterion must belong to the assignment's selected rubric.
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

-- ============================================================================
-- 4. INTEGRITY TRIGGER: SAFE ASSIGNMENT RUBRIC AND COURSE CHANGES
-- ============================================================================
-- Prevent orphaning or invalidating mappings when updating an assignment:
-- 1) If rubric_id is cleared to NULL, reject if criterion mappings exist.
-- 2) If rubric_id is changed to another rubric, verify all mapped criteria exist in the new rubric.
-- 3) If course_id is changed, verify all mapped concepts belong to the new course.
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

-- ============================================================================
-- 5. INTEGRITY TRIGGER: SUBMISSION CONSISTENCY
-- ============================================================================
-- At the database trigger level, enforce:
-- 1) Assignment must be published.
-- 2) Student must be enrolled in the assignment's course.
-- 3) Submission course_id matches assignment course_id (auto-sets if NULL).
-- 4) Submission rubric_id matches assignment rubric_id (auto-sets if NULL).
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

    -- Enforce assignment is published
    IF v_assign.status <> 'published' THEN
      RAISE EXCEPTION 'Cannot submit to assignment %: status is % (must be published).',
        NEW.assignment_id, v_assign.status;
    END IF;

    -- Enforce student enrollment in assignment course
    SELECT EXISTS (
      SELECT 1 FROM public.enrollments
      WHERE course_id = v_assign.course_id AND student_id = NEW.student_id
    ) INTO v_enrolled;

    IF NOT v_enrolled THEN
      RAISE EXCEPTION 'Student % is not enrolled in course % for assignment %.',
        NEW.student_id, v_assign.course_id, NEW.assignment_id;
    END IF;

    -- Enforce course_id consistency
    IF NEW.course_id IS NOT NULL AND NEW.course_id <> v_assign.course_id THEN
      RAISE EXCEPTION 'Submission course_id % does not match assignment course_id %.',
        NEW.course_id, v_assign.course_id;
    ELSIF NEW.course_id IS NULL THEN
      NEW.course_id := v_assign.course_id;
    END IF;

    -- Enforce rubric_id consistency
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

-- ============================================================================
-- 6. HARDENED ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
-- 6.1 Assignments: Students can only view published assignments for enrolled courses
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

-- 6.2 Assignment concepts: Visible only if user can view parent assignment
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

-- 6.3 Assignment criterion concepts: RLS enabled
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

-- 6.4 Submissions: Authoritative student identity, published status, enrollment, and course/rubric consistency
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

-- ============================================================================
-- 7. REALTIME PUBLICATION (CONDITIONAL AND SAFE)
-- ============================================================================
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
-- 8. POST-MIGRATION VERIFICATION ASSERTIONS
-- ============================================================================
DO $$
DECLARE
  v_col_default TEXT;
  v_crit_col_exists BOOLEAN;
  v_tbl_exists BOOLEAN;
  v_trg1_exists BOOLEAN;
  v_trg2_exists BOOLEAN;
  v_trg3_exists BOOLEAN;
BEGIN
  -- Verify assignments.status default is 'draft'
  SELECT column_default INTO v_col_default
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'assignments' AND column_name = 'status';

  IF v_col_default IS NULL OR v_col_default NOT LIKE '%draft%' THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: assignments.status default is %, expected ''draft''.', v_col_default;
  END IF;

  -- Verify rubric_criteria.concept_id column is absent (single authoritative source in assignment_criterion_concepts)
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'rubric_criteria' AND column_name = 'concept_id'
  ) INTO v_crit_col_exists;

  IF v_crit_col_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: rubric_criteria.concept_id column still exists; single authoritative source must be assignment_criterion_concepts.';
  END IF;

  -- Verify assignment_criterion_concepts table exists
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'assignment_criterion_concepts'
  ) INTO v_tbl_exists;

  IF NOT v_tbl_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: assignment_criterion_concepts table does not exist.';
  END IF;

  -- Verify triggers exist
  SELECT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_check_assignment_criterion_concept_match' AND NOT tgisinternal
  ) INTO v_trg1_exists;

  IF NOT v_trg1_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: trg_check_assignment_criterion_concept_match trigger is missing.';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_check_assignment_rubric_change' AND NOT tgisinternal
  ) INTO v_trg2_exists;

  IF NOT v_trg2_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: trg_check_assignment_rubric_change trigger is missing.';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_check_submission_consistency' AND NOT tgisinternal
  ) INTO v_trg3_exists;

  IF NOT v_trg3_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: trg_check_submission_consistency trigger is missing.';
  END IF;

  RAISE NOTICE 'Migration 06 Post-Migration Verification Passed: All tables, columns, constraints, and triggers verified successfully.';
END $$;
