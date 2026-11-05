-- 06_assignment_concept_mapping.down.sql
-- Rollback for EduAgents Assignment Management and Curriculum Concept Mapping (Day 3 Hardened)
-- Reverts status, max_points, assignment_criterion_concepts, triggers, functions, and RLS policies.
-- Fully deterministic, explicit, and free of broad silent exception handlers.

-- 1. Revert Realtime Publication conditionally
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'assignments'
  ) THEN
    ALTER PUBLICATION supabase_realtime DROP TABLE public.assignments;
  END IF;
END $$;

-- 2. Drop Submission Consistency Trigger and Function
DROP TRIGGER IF EXISTS trg_check_submission_consistency ON public.submissions;
DROP FUNCTION IF EXISTS public.check_submission_consistency();

-- 3. Revert Submissions RLS to Day 2 Baseline
DROP POLICY IF EXISTS "student create own pending submission" ON public.submissions;
CREATE POLICY "student create own pending submission"
  ON public.submissions FOR INSERT
  TO authenticated
  WITH CHECK (
    student_id = auth.uid() AND
    status = 'pending' AND
    attempts = 1 AND
    (assignment_id IS NULL OR EXISTS (
      SELECT 1 FROM public.assignments a
      JOIN public.enrollments e ON e.course_id = a.course_id
      WHERE a.id = assignment_id AND e.student_id = auth.uid()
    ))
  );

-- 4. Drop Assignment Rubric/Course Change Trigger and Function
DROP TRIGGER IF EXISTS trg_check_assignment_rubric_change ON public.assignments;
DROP FUNCTION IF EXISTS public.check_assignment_rubric_change();

-- 5. Drop Assignment Criterion Concepts Policies, Triggers, Function, and Table
DROP POLICY IF EXISTS "faculty manage assignment criterion concepts" ON public.assignment_criterion_concepts;
DROP POLICY IF EXISTS "view assignment criterion concepts" ON public.assignment_criterion_concepts;
DROP TRIGGER IF EXISTS trg_check_assignment_criterion_concept_match ON public.assignment_criterion_concepts;
DROP FUNCTION IF EXISTS public.check_assignment_criterion_concept_match();
DROP TABLE IF EXISTS public.assignment_criterion_concepts;

-- 6. Revert Assignment Concepts RLS
DROP POLICY IF EXISTS "view assignment concepts" ON public.assignment_concepts;
CREATE POLICY "view assignment concepts"
  ON public.assignment_concepts FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.can_access_course(a.course_id)
    )
  );

-- 7. Revert Assignments RLS
DROP POLICY IF EXISTS "view assignments" ON public.assignments;
CREATE POLICY "view assignments"
  ON public.assignments FOR SELECT
  TO authenticated
  USING (public.can_access_course(course_id));

-- 8. Clean up any leftover rubric criteria concept column or index
DROP INDEX IF EXISTS public.idx_rubric_criteria_concept;
ALTER TABLE public.rubric_criteria DROP COLUMN IF EXISTS concept_id;

-- 9. Drop Assignments Columns, Indexes, and Constraints
DROP INDEX IF EXISTS public.idx_assignments_course_status;
DROP INDEX IF EXISTS public.idx_assignments_status;

ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_max_points_check;
ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_status_check;

ALTER TABLE public.assignments DROP COLUMN IF EXISTS max_points;
ALTER TABLE public.assignments DROP COLUMN IF EXISTS status;

-- 10. Post-Rollback Verification Assertions
DO $$
DECLARE
  v_col_exists BOOLEAN;
  v_tbl_exists BOOLEAN;
  v_trg_exists BOOLEAN;
BEGIN
  -- Verify assignments.status column removed
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'assignments' AND column_name = 'status'
  ) INTO v_col_exists;

  IF v_col_exists THEN
    RAISE EXCEPTION 'POST-ROLLBACK ASSERTION FAILED: assignments.status column still exists.';
  END IF;

  -- Verify assignment_criterion_concepts table removed
  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'assignment_criterion_concepts'
  ) INTO v_tbl_exists;

  IF v_tbl_exists THEN
    RAISE EXCEPTION 'POST-ROLLBACK ASSERTION FAILED: assignment_criterion_concepts table still exists.';
  END IF;

  -- Verify triggers removed
  SELECT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname IN (
      'trg_check_assignment_criterion_concept_match',
      'trg_check_assignment_rubric_change',
      'trg_check_submission_consistency'
    ) AND NOT tgisinternal
  ) INTO v_trg_exists;

  IF v_trg_exists THEN
    RAISE EXCEPTION 'POST-ROLLBACK ASSERTION FAILED: Day 3 hardening triggers still exist.';
  END IF;

  RAISE NOTICE 'Migration 06 Rollback Verification Passed: All Day 3 artifacts removed cleanly.';
END $$;
