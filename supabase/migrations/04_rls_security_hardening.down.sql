-- 04_rls_security_hardening.down.sql
-- Rollback for 04_rls_security_hardening.up.sql

DROP POLICY IF EXISTS "faculty read course submission files" ON storage.objects;
DROP POLICY IF EXISTS "students read own submission files" ON storage.objects;
DROP POLICY IF EXISTS "students upload own submission files" ON storage.objects;
DROP POLICY IF EXISTS "faculty insert overrides" ON public.faculty_overrides;
DROP POLICY IF EXISTS "view faculty overrides" ON public.faculty_overrides;
DROP POLICY IF EXISTS "faculty insert override mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "view student concept mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "view concept feedback" ON public.submission_concept_feedback;
DROP POLICY IF EXISTS "read related criterion evaluations" ON public.criterion_evaluations;
DROP POLICY IF EXISTS "read related evaluations" ON public.evaluations;
DROP POLICY IF EXISTS "read related grading jobs" ON public.grading_jobs;
DROP POLICY IF EXISTS "student create own pending submission" ON public.submissions;
DROP POLICY IF EXISTS "view submissions" ON public.submissions;
DROP POLICY IF EXISTS "faculty manage assignment concepts" ON public.assignment_concepts;
DROP POLICY IF EXISTS "view assignment concepts" ON public.assignment_concepts;
DROP POLICY IF EXISTS "faculty manage assignments" ON public.assignments;
DROP POLICY IF EXISTS "view assignments" ON public.assignments;
DROP POLICY IF EXISTS "faculty manage rubric criteria" ON public.rubric_criteria;
DROP POLICY IF EXISTS "read rubric criteria" ON public.rubric_criteria;
DROP POLICY IF EXISTS "faculty delete rubrics" ON public.rubrics;
DROP POLICY IF EXISTS "faculty update rubrics" ON public.rubrics;
DROP POLICY IF EXISTS "faculty insert rubrics" ON public.rubrics;
DROP POLICY IF EXISTS "read accessible rubrics" ON public.rubrics;
DROP POLICY IF EXISTS "faculty manage concept edges" ON public.concept_edges;
DROP POLICY IF EXISTS "view concept edges" ON public.concept_edges;
DROP POLICY IF EXISTS "faculty manage concepts" ON public.concepts;
DROP POLICY IF EXISTS "view concepts" ON public.concepts;
DROP POLICY IF EXISTS "faculty manage enrollments" ON public.enrollments;
DROP POLICY IF EXISTS "view enrollments" ON public.enrollments;
DROP POLICY IF EXISTS "faculty delete courses" ON public.courses;
DROP POLICY IF EXISTS "faculty edit courses" ON public.courses;
DROP POLICY IF EXISTS "faculty create courses" ON public.courses;
DROP POLICY IF EXISTS "view courses" ON public.courses;
DROP POLICY IF EXISTS "users update own profile display" ON public.profiles;
DROP POLICY IF EXISTS "users read own profile" ON public.profiles;
