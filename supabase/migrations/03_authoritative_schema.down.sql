-- 03_authoritative_schema.down.sql
-- Rollback for 03_authoritative_schema.up.sql

DROP VIEW IF EXISTS public.submissions_v2;
DROP TABLE IF EXISTS public.faculty_overrides CASCADE;
DROP TABLE IF EXISTS public.student_concept_mastery CASCADE;
DROP TABLE IF EXISTS public.submission_concept_feedback CASCADE;
DROP TABLE IF EXISTS public.criterion_evaluations CASCADE;
DROP TABLE IF EXISTS public.evaluations CASCADE;
DROP TABLE IF EXISTS public.grading_jobs CASCADE;
DROP TABLE IF EXISTS public.submissions CASCADE;
DROP TABLE IF EXISTS public.assignment_concepts CASCADE;
DROP TABLE IF EXISTS public.assignments CASCADE;
DROP TABLE IF EXISTS public.rubric_criteria CASCADE;
DROP TABLE IF EXISTS public.rubrics CASCADE;
DROP TABLE IF EXISTS public.concept_edges CASCADE;
DROP TABLE IF EXISTS public.concepts CASCADE;
DROP TABLE IF EXISTS public.enrollments CASCADE;
DROP TABLE IF EXISTS public.courses CASCADE;
DROP FUNCTION IF EXISTS public.check_assignment_concept_course_match();
DROP FUNCTION IF EXISTS public.check_concept_edge_cycles();
DROP FUNCTION IF EXISTS public.set_updated_at();
