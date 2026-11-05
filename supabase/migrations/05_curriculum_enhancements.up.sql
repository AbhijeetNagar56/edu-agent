-- 05_curriculum_enhancements.up.sql
-- EduAgents Curriculum Enhancements Migration (Day 2)
-- Adds course description, concept category and difficulty, and faculty indexes.
-- Safe, deterministic, and idempotent.

-- ============================================================================
-- 1. COURSES TABLE ENHANCEMENTS
-- ============================================================================
ALTER TABLE public.courses ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_courses_faculty ON public.courses(faculty_id);

-- ============================================================================
-- 2. CONCEPTS TABLE ENHANCEMENTS
-- ============================================================================
ALTER TABLE public.concepts ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT '';
ALTER TABLE public.concepts ADD COLUMN IF NOT EXISTS difficulty TEXT NOT NULL DEFAULT 'intermediate';
ALTER TABLE public.concepts ADD COLUMN IF NOT EXISTS pos_x DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE public.concepts ADD COLUMN IF NOT EXISTS pos_y DOUBLE PRECISION NOT NULL DEFAULT 0.0;

DO $$
BEGIN
  ALTER TABLE public.concepts DROP CONSTRAINT IF EXISTS concepts_difficulty_check;
  ALTER TABLE public.concepts ADD CONSTRAINT concepts_difficulty_check
    CHECK (difficulty IN ('beginner', 'intermediate', 'advanced'));
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================================================
-- 3. CONCEPT EDGES TABLE ENHANCEMENTS
-- ============================================================================
ALTER TABLE public.concept_edges ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
