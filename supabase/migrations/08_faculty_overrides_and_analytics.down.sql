-- ============================================================================
-- Migration 08: Rollback
-- ============================================================================

DROP INDEX IF EXISTS idx_faculty_overrides_target;
DROP INDEX IF EXISTS idx_faculty_overrides_student;
DROP INDEX IF EXISTS idx_faculty_overrides_concept;

ALTER TABLE public.faculty_overrides DROP CONSTRAINT IF EXISTS faculty_overrides_target_type_check;
ALTER TABLE public.faculty_overrides DROP COLUMN IF EXISTS student_id;
ALTER TABLE public.faculty_overrides DROP COLUMN IF EXISTS concept_id;
ALTER TABLE public.faculty_overrides DROP COLUMN IF EXISTS target_type;
