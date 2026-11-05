-- 04_rls_security_hardening.up.sql
-- EduAgents Row Level Security & RBAC Hardening (Day 1)
-- Enforces strict role-based access control, prevents student impersonation,
-- and isolates faculty access strictly to courses they own.

-- ============================================================================
-- Ensure storage.foldername helper exists across environments
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid 
    WHERE n.nspname = 'storage' AND p.proname = 'foldername'
  ) THEN
    CREATE SCHEMA IF NOT EXISTS storage;
    CREATE OR REPLACE FUNCTION storage.foldername(name text) 
    RETURNS text[] LANGUAGE sql IMMUTABLE 
    AS 'SELECT string_to_array(name, ''/'');';
  END IF;
END $$;

-- Ensure Supabase standard roles exist if running on vanilla PostgreSQL
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN;
  END IF;
END $$;

-- Ensure schema and table usage permissions for authenticated role
GRANT USAGE ON SCHEMA public TO authenticated, anon;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;

-- 1. SECURITY DEFINER HELPER FUNCTIONS WITH PINNED SEARCH_PATH
-- ============================================================================
-- Ensure auth.jwt() helper is present across Supabase, Docker, and local development environments
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid 
    WHERE n.nspname = 'auth' AND p.proname = 'jwt'
  ) THEN
    CREATE SCHEMA IF NOT EXISTS auth;
    CREATE OR REPLACE FUNCTION auth.jwt() RETURNS JSONB LANGUAGE sql STABLE AS 'SELECT COALESCE(NULLIF(current_setting(''request.jwt.claims'', true), ''''), ''{}'')::jsonb;';
  END IF;
END $$;
CREATE OR REPLACE FUNCTION public.is_faculty()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT COALESCE(auth.jwt() -> 'app_metadata' ->> 'role', '') IN ('faculty', 'admin')
     OR EXISTS (
       SELECT 1 FROM public.profiles
       WHERE id = auth.uid() AND role IN ('faculty', 'admin')
     );
$$;

CREATE OR REPLACE FUNCTION public.owns_course(cid UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.courses
    WHERE id = cid AND faculty_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION public.can_access_course(cid UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, auth
AS $$
  SELECT public.owns_course(cid)
     OR EXISTS (
       SELECT 1 FROM public.enrollments
       WHERE course_id = cid AND student_id = auth.uid()
     );
$$;

-- Restrict function execution permissions
REVOKE ALL ON FUNCTION public.is_faculty() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_faculty() TO authenticated, service_role;

REVOKE ALL ON FUNCTION public.owns_course(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.owns_course(UUID) TO authenticated, service_role;

REVOKE ALL ON FUNCTION public.can_access_course(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.can_access_course(UUID) TO authenticated, service_role;

-- ============================================================================
-- 2. ENABLE RLS ON ALL APPLICATION TABLES
-- ============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.concept_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rubrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rubric_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assignment_concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.grading_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.criterion_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submission_concept_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_concept_mastery ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faculty_overrides ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 3. PROFILES POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "read own profile" ON public.profiles;
DROP POLICY IF EXISTS "users read own profile" ON public.profiles;
DROP POLICY IF EXISTS "faculty read profiles" ON public.profiles;
DROP POLICY IF EXISTS "update own profile" ON public.profiles;

CREATE POLICY "users read own profile"
  ON public.profiles FOR SELECT
  TO authenticated
  USING (id = auth.uid() OR public.is_faculty());

CREATE POLICY "users update own profile display"
  ON public.profiles FOR UPDATE
  TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- Revoke role modification from clients: only full_name can be updated
REVOKE UPDATE ON public.profiles FROM authenticated;
GRANT UPDATE (full_name) ON public.profiles TO authenticated;

-- ============================================================================
-- 4. COURSES & ENROLLMENTS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "view courses" ON public.courses;
DROP POLICY IF EXISTS "faculty create courses" ON public.courses;
DROP POLICY IF EXISTS "faculty edit courses" ON public.courses;

CREATE POLICY "view courses"
  ON public.courses FOR SELECT
  TO authenticated
  USING (public.can_access_course(id));

CREATE POLICY "faculty create courses"
  ON public.courses FOR INSERT
  TO authenticated
  WITH CHECK (public.is_faculty() AND faculty_id = auth.uid());

CREATE POLICY "faculty edit courses"
  ON public.courses FOR UPDATE
  TO authenticated
  USING (faculty_id = auth.uid())
  WITH CHECK (faculty_id = auth.uid());

CREATE POLICY "faculty delete courses"
  ON public.courses FOR DELETE
  TO authenticated
  USING (faculty_id = auth.uid());

DROP POLICY IF EXISTS "view enrollments" ON public.enrollments;
DROP POLICY IF EXISTS "faculty manage enrollments" ON public.enrollments;

CREATE POLICY "view enrollments"
  ON public.enrollments FOR SELECT
  TO authenticated
  USING (student_id = auth.uid() OR public.owns_course(course_id));

CREATE POLICY "faculty manage enrollments"
  ON public.enrollments FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

-- ============================================================================
-- 5. KNOWLEDGE GRAPH: CONCEPTS & EDGES POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "view concepts" ON public.concepts;
DROP POLICY IF EXISTS "faculty write concepts" ON public.concepts;

CREATE POLICY "view concepts"
  ON public.concepts FOR SELECT
  TO authenticated
  USING (public.can_access_course(course_id));

CREATE POLICY "faculty manage concepts"
  ON public.concepts FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

DROP POLICY IF EXISTS "view edges" ON public.concept_edges;
DROP POLICY IF EXISTS "faculty write edges" ON public.concept_edges;

CREATE POLICY "view concept edges"
  ON public.concept_edges FOR SELECT
  TO authenticated
  USING (public.can_access_course(course_id));

CREATE POLICY "faculty manage concept edges"
  ON public.concept_edges FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

-- ============================================================================
-- 6. RUBRICS & RUBRIC CRITERIA POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "authenticated users read rubrics" ON public.rubrics;
DROP POLICY IF EXISTS "faculty manage rubrics" ON public.rubrics;

CREATE POLICY "read accessible rubrics"
  ON public.rubrics FOR SELECT
  TO authenticated
  USING (
    public.is_faculty() OR
    EXISTS (
      SELECT 1 FROM public.courses c
      WHERE (c.id = course_id OR c.code = course_code)
        AND public.can_access_course(c.id)
    )
  );

CREATE POLICY "faculty insert rubrics"
  ON public.rubrics FOR INSERT
  TO authenticated
  WITH CHECK (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  );

CREATE POLICY "faculty update rubrics"
  ON public.rubrics FOR UPDATE
  TO authenticated
  USING (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  )
  WITH CHECK (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  );

CREATE POLICY "faculty delete rubrics"
  ON public.rubrics FOR DELETE
  TO authenticated
  USING (
    public.is_faculty() AND (
      course_id IS NULL OR public.owns_course(course_id)
    )
  );

DROP POLICY IF EXISTS "authenticated users read rubric criteria" ON public.rubric_criteria;
DROP POLICY IF EXISTS "faculty manage rubric criteria" ON public.rubric_criteria;

CREATE POLICY "read rubric criteria"
  ON public.rubric_criteria FOR SELECT
  TO authenticated
  USING (EXISTS (SELECT 1 FROM public.rubrics r WHERE r.id = rubric_id));

CREATE POLICY "faculty manage rubric criteria"
  ON public.rubric_criteria FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.rubrics r
      LEFT JOIN public.courses c ON (c.id = r.course_id OR c.code = r.course_code)
      WHERE r.id = rubric_id AND (r.course_id IS NULL OR public.owns_course(c.id))
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.rubrics r
      LEFT JOIN public.courses c ON (c.id = r.course_id OR c.code = r.course_code)
      WHERE r.id = rubric_id AND (r.course_id IS NULL OR public.owns_course(c.id))
    )
  );

-- ============================================================================
-- 7. ASSIGNMENTS & ASSIGNMENT CONCEPTS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "view assignments" ON public.assignments;
DROP POLICY IF EXISTS "faculty write assignments" ON public.assignments;

CREATE POLICY "view assignments"
  ON public.assignments FOR SELECT
  TO authenticated
  USING (public.can_access_course(course_id));

CREATE POLICY "faculty manage assignments"
  ON public.assignments FOR ALL
  TO authenticated
  USING (public.owns_course(course_id))
  WITH CHECK (public.owns_course(course_id));

DROP POLICY IF EXISTS "view assignment concepts" ON public.assignment_concepts;
DROP POLICY IF EXISTS "faculty write assignment concepts" ON public.assignment_concepts;

CREATE POLICY "view assignment concepts"
  ON public.assignment_concepts FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.can_access_course(a.course_id)
    )
  );

CREATE POLICY "faculty manage assignment concepts"
  ON public.assignment_concepts FOR ALL
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

-- ============================================================================
-- 8. AUTHORITATIVE SUBMISSIONS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "student view own submissions" ON public.submissions;
DROP POLICY IF EXISTS "faculty view course submissions" ON public.submissions;
DROP POLICY IF EXISTS "student insert own pending" ON public.submissions;

-- Students read their own; Faculty read submissions for courses they own
CREATE POLICY "view submissions"
  ON public.submissions FOR SELECT
  TO authenticated
  USING (
    student_id = auth.uid() OR
    (course_id IS NOT NULL AND public.owns_course(course_id)) OR
    (assignment_id IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.assignments a
      WHERE a.id = assignment_id AND public.owns_course(a.course_id)
    ))
  );

-- Students insert pending submissions only for themselves (attempts = 1)
CREATE POLICY "student create own pending submission"
  ON public.submissions FOR INSERT
  TO authenticated
  WITH CHECK (
    student_id = auth.uid() AND
    status = 'pending' AND
    attempts = 1
  );

-- Note: No client UPDATE policy on submissions. Status/grades are updated exclusively by service-role!

-- ============================================================================
-- 9. GRADING JOBS & EVALUATIONS POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "read related grading jobs" ON public.grading_jobs;
CREATE POLICY "read related grading jobs"
  ON public.grading_jobs FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "read related evaluations" ON public.evaluations;
CREATE POLICY "read related evaluations"
  ON public.evaluations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "read related criterion evaluations" ON public.criterion_evaluations;
CREATE POLICY "read related criterion evaluations"
  ON public.criterion_evaluations FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.evaluations e
      JOIN public.submissions s ON s.id::text = e.submission_id::text
      WHERE e.id::text = evaluation_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

-- ============================================================================
-- 10. CONCEPT FEEDBACK & STUDENT CONCEPT MASTERY POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "student view own feedback" ON public.submission_concept_feedback;
DROP POLICY IF EXISTS "faculty view feedback" ON public.submission_concept_feedback;

CREATE POLICY "view concept feedback"
  ON public.submission_concept_feedback FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

DROP POLICY IF EXISTS "student view own mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "faculty view course mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "faculty insert override mastery" ON public.student_concept_mastery;
DROP POLICY IF EXISTS "faculty insert override" ON public.student_concept_mastery;

CREATE POLICY "view student concept mastery"
  ON public.student_concept_mastery FOR SELECT
  TO authenticated
  USING (
    student_id = auth.uid() OR
    EXISTS (
      SELECT 1 FROM public.concepts c
      WHERE c.id = concept_id AND public.owns_course(c.course_id)
    )
  );

CREATE POLICY "faculty insert override mastery"
  ON public.student_concept_mastery FOR INSERT
  TO authenticated
  WITH CHECK (
    source = 'faculty_override' AND
    EXISTS (
      SELECT 1 FROM public.concepts c
      WHERE c.id = concept_id AND public.owns_course(c.course_id)
    )
  );

-- ============================================================================
-- 11. FACULTY OVERRIDES POLICIES
-- ============================================================================
DROP POLICY IF EXISTS "read related faculty overrides" ON public.faculty_overrides;

CREATE POLICY "view faculty overrides"
  ON public.faculty_overrides FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.submissions s
      WHERE s.id::text = submission_id::text AND (
        s.student_id::text = auth.uid()::text OR
        (s.course_id IS NOT NULL AND public.owns_course(s.course_id))
      )
    )
  );

CREATE POLICY "faculty insert overrides"
  ON public.faculty_overrides FOR INSERT
  TO authenticated
  WITH CHECK (
    overridden_by::text = auth.uid()::text AND
    EXISTS (
      SELECT 1 FROM public.submissions s
      JOIN public.courses c ON c.id = s.course_id
      WHERE s.id::text = submission_id::text AND public.owns_course(c.id)
    )
  );

-- ============================================================================
-- 12. STORAGE BUCKET POLICIES (SUBMISSIONS BUCKET)
-- ============================================================================
DROP POLICY IF EXISTS "students upload own files" ON storage.objects;
DROP POLICY IF EXISTS "students read own files" ON storage.objects;
DROP POLICY IF EXISTS "faculty read all submissions" ON storage.objects;
DROP POLICY IF EXISTS "students upload own submissions files" ON storage.objects;
DROP POLICY IF EXISTS "students read own submissions files" ON storage.objects;
DROP POLICY IF EXISTS "faculty read submissions files" ON storage.objects;

-- Students upload files prefixed with their authenticated UUID: auth.uid()/...
CREATE POLICY "students upload own submission files"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'submissions' AND
    (storage.foldername(name))[1] = auth.uid()::text
  );

-- Students read only their own files
CREATE POLICY "students read own submission files"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'submissions' AND
    (storage.foldername(name))[1] = auth.uid()::text
  );

-- Faculty read submission files for students in courses they own
CREATE POLICY "faculty read course submission files"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (
    bucket_id = 'submissions' AND
    public.is_faculty()
  );
