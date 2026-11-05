-- 07_evaluation_mastery_pipeline.down.sql
-- Rollback for EduAgents Day 4: AI Evaluation and Concept Mastery Engine Schema Enhancements

-- 1. Drop Atomic Job Claiming RPC
DROP FUNCTION IF EXISTS public.claim_grading_job(TEXT, INTERVAL);

-- 2. Drop RLS Policies
DROP POLICY IF EXISTS "view submission concept feedback" ON public.submission_concept_feedback;
DROP POLICY IF EXISTS "view criterion evaluations" ON public.criterion_evaluations;
DROP POLICY IF EXISTS "view evaluations" ON public.evaluations;

-- 3. Revert Grading Jobs Enhancements
DROP INDEX IF EXISTS public.idx_grading_jobs_status_locked;

ALTER TABLE public.grading_jobs DROP CONSTRAINT IF EXISTS grading_jobs_status_check;
ALTER TABLE public.grading_jobs ADD CONSTRAINT grading_jobs_status_check
  CHECK (status IN ('pending', 'processing', 'done', 'failed', 'flagged'));

ALTER TABLE public.grading_jobs DROP CONSTRAINT IF EXISTS grading_jobs_max_retries_check;
ALTER TABLE public.grading_jobs DROP COLUMN IF EXISTS max_retries;
ALTER TABLE public.grading_jobs DROP COLUMN IF EXISTS locked_by;
ALTER TABLE public.grading_jobs DROP COLUMN IF EXISTS locked_at;

-- 4. Revert Submissions Status Check
ALTER TABLE public.submissions DROP CONSTRAINT IF EXISTS submissions_status_check;
ALTER TABLE public.submissions ADD CONSTRAINT submissions_status_check
  CHECK (status IN ('pending', 'processing', 'graded', 'done', 'failed', 'flagged'));

-- 5. Revert Submission Concept Feedback Enhancements
DROP INDEX IF EXISTS public.idx_sub_concept_fb_crit;
DROP INDEX IF EXISTS public.idx_sub_concept_fb_eval;
DROP INDEX IF EXISTS public.idx_sub_concept_fb_student;

ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_confidence_check;
ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_score_ratio_check;
ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_sub_concept_crit_key;

-- Restore baseline unique constraint (submission_id, concept_id)
ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_submission_id_concept_id_key;
ALTER TABLE public.submission_concept_feedback ADD CONSTRAINT submission_concept_feedback_submission_id_concept_id_key
  UNIQUE (submission_id, concept_id);

ALTER TABLE public.submission_concept_feedback DROP COLUMN IF EXISTS confidence;
ALTER TABLE public.submission_concept_feedback DROP COLUMN IF EXISTS score_ratio;
ALTER TABLE public.submission_concept_feedback DROP COLUMN IF EXISTS evidence;
ALTER TABLE public.submission_concept_feedback DROP COLUMN IF EXISTS evaluation_id;
ALTER TABLE public.submission_concept_feedback DROP COLUMN IF EXISTS criterion_id;
ALTER TABLE public.submission_concept_feedback DROP COLUMN IF EXISTS student_id;

-- 6. Revert Criterion Evaluations Enhancements
ALTER TABLE public.criterion_evaluations DROP CONSTRAINT IF EXISTS criterion_evaluations_score_ratio_check;
ALTER TABLE public.criterion_evaluations DROP COLUMN IF EXISTS score_ratio;
ALTER TABLE public.criterion_evaluations DROP COLUMN IF EXISTS evidence;
ALTER TABLE public.criterion_evaluations DROP COLUMN IF EXISTS reasoning;

-- 7. Post-Rollback Verification Assertions
DO $$
DECLARE
  v_col_exists BOOLEAN;
  v_rpc_exists BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'criterion_evaluations' AND column_name = 'reasoning'
  ) INTO v_col_exists;

  IF v_col_exists THEN
    RAISE EXCEPTION 'POST-ROLLBACK ASSERTION FAILED: criterion_evaluations.reasoning column still exists.';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'claim_grading_job'
  ) INTO v_rpc_exists;

  IF v_rpc_exists THEN
    RAISE EXCEPTION 'POST-ROLLBACK ASSERTION FAILED: claim_grading_job function still exists.';
  END IF;

  RAISE NOTICE 'Migration 07 Rollback Verification Passed: All Day 4 artifacts removed cleanly.';
END $$;

ALTER TABLE public.student_concept_mastery DROP CONSTRAINT IF EXISTS student_concept_mastery_student_concept_uidx;

ALTER TABLE public.student_concept_mastery DROP CONSTRAINT IF EXISTS student_concept_mastery_mastery_score_check;
ALTER TABLE public.student_concept_mastery DROP CONSTRAINT IF EXISTS student_concept_mastery_confidence_score_check;
ALTER TABLE public.student_concept_mastery DROP CONSTRAINT IF EXISTS student_concept_mastery_evidence_count_check;
