-- 07_evaluation_mastery_pipeline.up.sql
-- EduAgents Day 4: AI Evaluation and Concept Mastery Engine Schema Enhancements
-- Adds granular criterion evidence/reasoning, concept feedback enrichment,
-- atomic queue locking with abandoned job recovery, and manual_review support.
-- Fully deterministic, explicit, and free of broad silent exception handlers.

-- ============================================================================
-- 1. CRITERION EVALUATIONS ENHANCEMENTS
-- ============================================================================
ALTER TABLE public.criterion_evaluations ADD COLUMN IF NOT EXISTS reasoning TEXT NOT NULL DEFAULT '';
ALTER TABLE public.criterion_evaluations ADD COLUMN IF NOT EXISTS evidence TEXT NOT NULL DEFAULT '';
ALTER TABLE public.criterion_evaluations ADD COLUMN IF NOT EXISTS score_ratio NUMERIC(5, 4) NOT NULL DEFAULT 0.0;

ALTER TABLE public.criterion_evaluations DROP CONSTRAINT IF EXISTS criterion_evaluations_score_ratio_check;
ALTER TABLE public.criterion_evaluations ADD CONSTRAINT criterion_evaluations_score_ratio_check
  CHECK (score_ratio >= 0.0 AND score_ratio <= 1.0);

-- ============================================================================
-- 2. SUBMISSION CONCEPT FEEDBACK ENHANCEMENTS
-- ============================================================================
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

-- Evolve unique constraint to allow granular criterion-level feedback per concept
ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_submission_id_concept_id_key;
ALTER TABLE public.submission_concept_feedback DROP CONSTRAINT IF EXISTS submission_concept_feedback_sub_concept_crit_key;
ALTER TABLE public.submission_concept_feedback ADD CONSTRAINT submission_concept_feedback_sub_concept_crit_key
  UNIQUE (submission_id, concept_id, criterion_id);

CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_student ON public.submission_concept_feedback(student_id);
CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_eval ON public.submission_concept_feedback(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_sub_concept_fb_crit ON public.submission_concept_feedback(criterion_id);

-- Backfill student_id on existing rows if any
UPDATE public.submission_concept_feedback scf
SET student_id = s.student_id
FROM public.submissions s
WHERE scf.submission_id = s.id AND scf.student_id IS NULL;

-- ============================================================================
-- 3. SUBMISSIONS & GRADING JOBS STATUS ENHANCEMENTS ('manual_review')
-- ============================================================================
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

-- ============================================================================
-- 3.5. UNIQUE CONSTRAINT ON student_concept_mastery
-- ============================================================================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'student_concept_mastery_student_concept_uidx'
  ) THEN
    ALTER TABLE public.student_concept_mastery
      ADD CONSTRAINT student_concept_mastery_student_concept_uidx UNIQUE (student_id, concept_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'student_concept_mastery_mastery_score_check'
  ) THEN
    ALTER TABLE public.student_concept_mastery
      ADD CONSTRAINT student_concept_mastery_mastery_score_check CHECK (mastery_score >= 0.0 AND mastery_score <= 1.0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'student_concept_mastery_confidence_score_check'
  ) THEN
    ALTER TABLE public.student_concept_mastery
      ADD CONSTRAINT student_concept_mastery_confidence_score_check CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'student_concept_mastery_evidence_count_check'
  ) THEN
    ALTER TABLE public.student_concept_mastery
      ADD CONSTRAINT student_concept_mastery_evidence_count_check CHECK (evidence_count >= 0);
  END IF;
END $$;

-- ============================================================================
-- 4. ATOMIC GRADING JOB CLAIMING STORED PROCEDURE
-- ============================================================================
-- Atomically selects, locks, and transitions the next eligible job.
-- Automatically claims pending jobs or recovers stale jobs abandoned by crashed workers.
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
  -- Lock exactly one eligible job:
  -- 1) pending and below max retries
  -- 2) processing but abandoned past stale interval
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

-- ============================================================================
-- 5. RLS POLICIES FOR ENRICHED EVALUATIONS & CONCEPT FEEDBACK
-- ============================================================================
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

-- ============================================================================
-- 6. POST-MIGRATION VERIFICATION ASSERTIONS
-- ============================================================================
DO $$
DECLARE
  v_col_count INTEGER;
  v_rpc_exists BOOLEAN;
  v_check_sub BOOLEAN;
BEGIN
  -- Verify criterion_evaluations columns
  SELECT COUNT(*) INTO v_col_count
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name = 'criterion_evaluations'
    AND column_name IN ('reasoning', 'evidence', 'score_ratio');

  IF v_col_count <> 3 THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: criterion_evaluations missing required Day 4 columns (found % of 3).', v_col_count;
  END IF;

  -- Verify submission_concept_feedback columns
  SELECT COUNT(*) INTO v_col_count
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name = 'submission_concept_feedback'
    AND column_name IN ('student_id', 'criterion_id', 'evaluation_id', 'evidence', 'score_ratio', 'confidence');

  IF v_col_count <> 6 THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: submission_concept_feedback missing required Day 4 columns (found % of 6).', v_col_count;
  END IF;

  -- Verify claim_grading_job function
  SELECT EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'claim_grading_job'
  ) INTO v_rpc_exists;

  IF NOT v_rpc_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: claim_grading_job stored procedure is missing.';
  END IF;

  -- Verify unique constraint on student_concept_mastery
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'student_concept_mastery_student_concept_uidx'
  ) THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: unique constraint on student_concept_mastery is missing.';
  END IF;

  RAISE NOTICE 'Migration 07 Post-Migration Verification Passed: All Day 4 columns, constraints, RLS policies, and RPCs verified successfully.';
END $$;
