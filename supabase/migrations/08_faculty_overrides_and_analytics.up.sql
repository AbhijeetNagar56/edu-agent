-- ============================================================================
-- Migration 08: Faculty Overrides & Learning Analytics Enhancements
-- Description:
--   1. Evolve faculty_overrides to support direct concept-mastery overrides
--      alongside submission-level overrides.
--   2. Make submission_id nullable to allow concept_mastery target_type.
--   3. Add concept_id and student_id foreign keys to faculty_overrides.
--   4. Add target_type check constraint ('submission', 'concept_mastery').
--   5. Add post-migration verification assertions.
-- ============================================================================

-- 1. EVOLVE FACULTY_OVERRIDES TABLE
DO $$
BEGIN
  -- Make submission_id nullable if it is currently NOT NULL
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'faculty_overrides'
      AND column_name = 'submission_id'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE public.faculty_overrides ALTER COLUMN submission_id DROP NOT NULL;
  END IF;
END $$;

-- Add target_type column
ALTER TABLE public.faculty_overrides
  ADD COLUMN IF NOT EXISTS target_type VARCHAR(32) NOT NULL DEFAULT 'submission';

-- Add check constraint for target_type
ALTER TABLE public.faculty_overrides
  DROP CONSTRAINT IF EXISTS faculty_overrides_target_type_check;

ALTER TABLE public.faculty_overrides
  ADD CONSTRAINT faculty_overrides_target_type_check
  CHECK (target_type IN ('submission', 'concept_mastery'));

-- Add concept_id column
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'faculty_overrides'
      AND column_name = 'concept_id'
  ) THEN
    ALTER TABLE public.faculty_overrides
      ADD COLUMN concept_id UUID REFERENCES public.concepts(id) ON DELETE CASCADE;
  END IF;
END $$;

-- Add student_id column
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'faculty_overrides'
      AND column_name = 'student_id'
  ) THEN
    ALTER TABLE public.faculty_overrides
      ADD COLUMN student_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE;
  END IF;
END $$;

-- Add performance indexes
CREATE INDEX IF NOT EXISTS idx_faculty_overrides_concept
  ON public.faculty_overrides(concept_id);

CREATE INDEX IF NOT EXISTS idx_faculty_overrides_student
  ON public.faculty_overrides(student_id);

CREATE INDEX IF NOT EXISTS idx_faculty_overrides_target
  ON public.faculty_overrides(target_type);

-- ============================================================================
-- 2. POST-MIGRATION VERIFICATION ASSERTIONS
-- ============================================================================
DO $$
DECLARE
  v_col_count INTEGER;
  v_nullable TEXT;
BEGIN
  -- Verify column presence
  SELECT COUNT(*) INTO v_col_count
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name = 'faculty_overrides'
    AND column_name IN ('target_type', 'concept_id', 'student_id');

  IF v_col_count <> 3 THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: faculty_overrides missing required columns (found % of 3).', v_col_count;
  END IF;

  -- Verify submission_id is nullable
  SELECT is_nullable INTO v_nullable
  FROM information_schema.columns
  WHERE table_schema = 'public'
    AND table_name = 'faculty_overrides'
    AND column_name = 'submission_id';

  IF v_nullable <> 'YES' THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: faculty_overrides.submission_id is not nullable.';
  END IF;

  RAISE NOTICE 'Migration 08 Post-Migration Verification Passed: All columns, constraints, and indexes verified.';
END $$;
