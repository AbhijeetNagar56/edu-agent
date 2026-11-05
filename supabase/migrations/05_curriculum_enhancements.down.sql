-- 05_curriculum_enhancements.down.sql
-- Rollback for EduAgents Curriculum Enhancements Migration (Day 2)

ALTER TABLE public.concept_edges DROP COLUMN IF EXISTS created_at;

DO $$
BEGIN
  ALTER TABLE public.concepts DROP CONSTRAINT IF EXISTS concepts_difficulty_check;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

ALTER TABLE public.concepts DROP COLUMN IF EXISTS difficulty;
ALTER TABLE public.concepts DROP COLUMN IF EXISTS category;

DROP INDEX IF EXISTS public.idx_courses_faculty;
ALTER TABLE public.courses DROP COLUMN IF EXISTS description;
