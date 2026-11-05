# EduAgents — Day 3 Final Database Hardening Report

## Executive Summary

As part of the **Day 3 Final Database Hardening** phase, Migration 06 (`06_assignment_concept_mapping.up.sql` and `down.sql`), database triggers, Row-Level Security (RLS) policies, backend services, and frontend modals were audited, hardened, and verified. 

All silent exception handling (`EXCEPTION WHEN OTHERS THEN NULL`) has been eliminated, making migration failures explicit and deterministic. A single authoritative mapping table (`public.assignment_criterion_concepts`) was established by removing the redundant `rubric_criteria.concept_id` column. Strict integrity triggers now prevent criterion mapping without an associated rubric, reject invalid criteria or cross-course concepts, and guard against incompatible rubric updates. Newly created assignments now default strictly to `draft` while preserving existing published assignments. Finally, submissions are strictly validated at both trigger and RLS levels for student identity, published status, course enrollment, and course/rubric consistency.

Every change has been empirically verified against live PostgreSQL (PostgreSQL 17.2 on port 5433), the complete `pytest` test suite (63/63 passing), and a production Next.js build.

---

## 1. Audit Findings and Corrective Actions

| Issue Area | Previous State | Hardened State |
| :--- | :--- | :--- |
| **Silent Exception Handling** | Constraints and triggers wrapped in `DO $$ BEGIN ... EXCEPTION WHEN OTHERS THEN NULL; END $$;` | Completely removed broad exception catch blocks. Constraints and triggers drop/create directly. Failures halt migrations immediately. Post-migration assertion block verifies state. |
| **Criterion Mapping Integrity** | Allowed criterion mappings if assignment had no rubric (`IF v_assign_rubric IS NOT NULL THEN`). Allowed clearing rubrics while criterion mappings remained. | `check_assignment_criterion_concept_match()` now explicitly raises an exception if `v_assign_rubric IS NULL`. New trigger `trg_check_assignment_rubric_change` rejects clearing or changing rubrics if incompatible with existing mappings. |
| **Authoritative Mapping Source** | Both `rubric_criteria.concept_id` and `assignment_criterion_concepts` existed, creating competing mapping sources. | `rubric_criteria.concept_id` was dropped. `assignment_criterion_concepts` is the single authoritative source of truth. |
| **Assignment Publication Defaults** | Assignments defaulted to `published` upon creation. | Column default changed to `draft`. Pydantic models default to `draft`. Frontend modal defaults to `draft`. Existing published rows preserved. |
| **Submission Consistency** | Validations in backend, but database trigger lacked deep checks on enrollment, course_id, and rubric_id match. | Database trigger `check_submission_consistency` and RLS policy enforce: student `auth.uid()`, assignment published, student enrolled, `course_id` and `rubric_id` matching assignment. Auto-sets course/rubric IDs if NULL. |

---

## 2. Hardened Database Architecture

### 2.1 Schema Definition & Constraints
```sql
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'draft';
ALTER TABLE public.assignments ALTER COLUMN status SET DEFAULT 'draft';
ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS max_points NUMERIC NOT NULL DEFAULT 100.0;
ALTER TABLE public.assignments ALTER COLUMN due_date SET DEFAULT (NOW() + INTERVAL '14 days');

ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_status_check;
ALTER TABLE public.assignments ADD CONSTRAINT assignments_status_check
  CHECK (status IN ('draft', 'published', 'archived'));

ALTER TABLE public.assignments DROP CONSTRAINT IF EXISTS assignments_max_points_check;
ALTER TABLE public.assignments ADD CONSTRAINT assignments_max_points_check
  CHECK (max_points > 0);
```

### 2.2 Authoritative Join Table & Redundancy Removal
```sql
DROP INDEX IF EXISTS public.idx_rubric_criteria_concept;
ALTER TABLE public.rubric_criteria DROP COLUMN IF EXISTS concept_id;

CREATE TABLE IF NOT EXISTS public.assignment_criterion_concepts (
  assignment_id UUID NOT NULL REFERENCES public.assignments(id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL,
  concept_id UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (assignment_id, criterion_id, concept_id)
);
```

### 2.3 Criterion Mapping Integrity Trigger
```sql
CREATE OR REPLACE FUNCTION public.check_assignment_criterion_concept_match()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_assign_course UUID;
  v_assign_rubric TEXT;
  v_concept_course UUID;
  v_crit_exists BOOLEAN;
BEGIN
  SELECT course_id, rubric_id INTO v_assign_course, v_assign_rubric
  FROM public.assignments WHERE id = NEW.assignment_id;

  IF v_assign_course IS NULL THEN
    RAISE EXCEPTION 'Referenced assignment % does not exist.', NEW.assignment_id;
  END IF;

  IF v_assign_rubric IS NULL THEN
    RAISE EXCEPTION 'Cannot map criterion concept: assignment % does not have an associated rubric.',
      NEW.assignment_id;
  END IF;

  SELECT course_id INTO v_concept_course
  FROM public.concepts WHERE id = NEW.concept_id;

  IF v_concept_course IS NULL THEN
    RAISE EXCEPTION 'Referenced concept % does not exist.', NEW.concept_id;
  END IF;

  IF v_assign_course <> v_concept_course THEN
    RAISE EXCEPTION 'Assignment criterion concept course mismatch: Assignment belongs to course % but Concept belongs to course %.',
      v_assign_course, v_concept_course;
  END IF;

  SELECT EXISTS(
    SELECT 1 FROM public.rubric_criteria
    WHERE rubric_id = v_assign_rubric AND id = NEW.criterion_id
  ) INTO v_crit_exists;

  IF NOT v_crit_exists THEN
    RAISE EXCEPTION 'Criterion % does not belong to assignment rubric %.',
      NEW.criterion_id, v_assign_rubric;
  END IF;

  RETURN NEW;
END;
$$;
```

### 2.4 Rubric & Course Modification Integrity Trigger
```sql
CREATE OR REPLACE FUNCTION public.check_assignment_rubric_change()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF OLD.rubric_id IS DISTINCT FROM NEW.rubric_id THEN
    IF NEW.rubric_id IS NULL AND EXISTS (
      SELECT 1 FROM public.assignment_criterion_concepts WHERE assignment_id = NEW.id
    ) THEN
      RAISE EXCEPTION 'Cannot remove rubric from assignment % while criterion concept mappings exist. Remove criterion mappings first.',
        NEW.id;
    END IF;

    IF NEW.rubric_id IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.assignment_criterion_concepts acc
      WHERE acc.assignment_id = NEW.id
        AND NOT EXISTS (
          SELECT 1 FROM public.rubric_criteria rc
          WHERE rc.rubric_id = NEW.rubric_id AND rc.id = acc.criterion_id
        )
    ) THEN
      RAISE EXCEPTION 'Cannot change assignment % rubric to %: existing criterion mappings are incompatible with the new rubric.',
        NEW.id, NEW.rubric_id;
    END IF;
  END IF;

  IF OLD.course_id IS DISTINCT FROM NEW.course_id THEN
    IF EXISTS (
      SELECT 1 FROM public.assignment_concepts ac
      JOIN public.concepts c ON c.id = ac.concept_id
      WHERE ac.assignment_id = NEW.id AND c.course_id <> NEW.course_id
    ) OR EXISTS (
      SELECT 1 FROM public.assignment_criterion_concepts acc
      JOIN public.concepts c ON c.id = acc.concept_id
      WHERE acc.assignment_id = NEW.id AND c.course_id <> NEW.course_id
    ) THEN
      RAISE EXCEPTION 'Cannot change course for assignment %: existing concept mappings belong to the previous course.',
        NEW.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;
```

### 2.5 Submission Consistency Trigger
```sql
CREATE OR REPLACE FUNCTION public.check_submission_consistency()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_assign RECORD;
  v_enrolled BOOLEAN;
BEGIN
  IF NEW.assignment_id IS NOT NULL THEN
    SELECT course_id, rubric_id, status INTO v_assign
    FROM public.assignments WHERE id = NEW.assignment_id;

    IF v_assign IS NULL THEN
      RAISE EXCEPTION 'Referenced assignment % does not exist.', NEW.assignment_id;
    END IF;

    IF v_assign.status <> 'published' THEN
      RAISE EXCEPTION 'Cannot submit to assignment %: status is % (must be published).',
        NEW.assignment_id, v_assign.status;
    END IF;

    SELECT EXISTS (
      SELECT 1 FROM public.enrollments
      WHERE course_id = v_assign.course_id AND student_id = NEW.student_id
    ) INTO v_enrolled;

    IF NOT v_enrolled THEN
      RAISE EXCEPTION 'Student % is not enrolled in course % for assignment %.',
        NEW.student_id, v_assign.course_id, NEW.assignment_id;
    END IF;

    IF NEW.course_id IS NOT NULL AND NEW.course_id <> v_assign.course_id THEN
      RAISE EXCEPTION 'Submission course_id % does not match assignment course_id %.',
        NEW.course_id, v_assign.course_id;
    ELSIF NEW.course_id IS NULL THEN
      NEW.course_id := v_assign.course_id;
    END IF;

    IF NEW.rubric_id IS NOT NULL AND v_assign.rubric_id IS NOT NULL AND NEW.rubric_id <> v_assign.rubric_id THEN
      RAISE EXCEPTION 'Submission rubric_id % does not match assignment rubric_id %.',
        NEW.rubric_id, v_assign.rubric_id;
    ELSIF NEW.rubric_id IS NULL THEN
      NEW.rubric_id := v_assign.rubric_id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;
```

### 2.6 Hardened RLS Policy for Submissions
```sql
DROP POLICY IF EXISTS "student create own pending submission" ON public.submissions;
CREATE POLICY "student create own pending submission"
  ON public.submissions FOR INSERT
  TO authenticated
  WITH CHECK (
    student_id = auth.uid() AND
    status = 'pending' AND
    attempts = 1 AND
    (
      assignment_id IS NULL OR EXISTS (
        SELECT 1 FROM public.assignments a
        JOIN public.enrollments e ON e.course_id = a.course_id
        WHERE a.id = assignment_id
          AND a.status = 'published'
          AND e.student_id = auth.uid()
          AND (public.submissions.course_id IS NULL OR public.submissions.course_id = a.course_id)
          AND (public.submissions.rubric_id IS NULL OR public.submissions.rubric_id = a.rubric_id)
      )
    )
  );
```

### 2.7 Post-Migration Verification Assertions
```sql
DO $$
DECLARE
  v_col_default TEXT;
  v_crit_col_exists BOOLEAN;
  v_tbl_exists BOOLEAN;
  v_trg1_exists BOOLEAN;
  v_trg2_exists BOOLEAN;
  v_trg3_exists BOOLEAN;
BEGIN
  SELECT column_default INTO v_col_default
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'assignments' AND column_name = 'status';

  IF v_col_default IS NULL OR v_col_default NOT LIKE '%draft%' THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: assignments.status default is %, expected ''draft''.', v_col_default;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'rubric_criteria' AND column_name = 'concept_id'
  ) INTO v_crit_col_exists;

  IF v_crit_col_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: rubric_criteria.concept_id column still exists.';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'assignment_criterion_concepts'
  ) INTO v_tbl_exists;

  IF NOT v_tbl_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: assignment_criterion_concepts table does not exist.';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_check_assignment_criterion_concept_match' AND NOT tgisinternal
  ) INTO v_trg1_exists;
  IF NOT v_trg1_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: trg_check_assignment_criterion_concept_match trigger is missing.';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_check_assignment_rubric_change' AND NOT tgisinternal
  ) INTO v_trg2_exists;
  IF NOT v_trg2_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: trg_check_assignment_rubric_change trigger is missing.';
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_check_submission_consistency' AND NOT tgisinternal
  ) INTO v_trg3_exists;
  IF NOT v_trg3_exists THEN
    RAISE EXCEPTION 'POST-MIGRATION ASSERTION FAILED: trg_check_submission_consistency trigger is missing.';
  END IF;

  RAISE NOTICE 'Migration 06 Post-Migration Verification Passed: All tables, columns, constraints, and triggers verified successfully.';
END $$;
```

---

## 3. Verification Test Evidence

### 3.1 Live PostgreSQL Verification (`scratch/test_postgres_day3_hardening.py`)
```text
Setting up test fixtures...
--- Executing SQL File: supabase/migrations/06_assignment_concept_mapping.up.sql ---
--- Finished: supabase/migrations/06_assignment_concept_mapping.up.sql ---
Migration 06 up.sql applied successfully!
TEST 1 PASSED: assignments.status default is 'draft'
TEST 2 PASSED: rubric_criteria.concept_id is absent (authoritative table is assignment_criterion_concepts)
TEST 3 PASSED: Direct assignment insert defaulted status to 'draft'
TEST 4 PASSED: Rejected criterion mapping when assignment has no rubric
TEST 5 PASSED: Rejected invalid criterion mapping
TEST 6 PASSED: Rejected cross-course concept mapping
TEST 7 PASSED: Valid criterion concept mapping succeeded
TEST 8A PASSED: Rejected clearing rubric while criterion mappings exist
TEST 8B PASSED: Rejected incompatible rubric change
TEST 9A PASSED: Rejected submission to draft assignment
TEST 9B PASSED: Rejected submission from unenrolled student
TEST 9C PASSED: Rejected submission with mismatched course_id
TEST 9D PASSED: Rejected submission with mismatched rubric_id
TEST 9E PASSED: Valid submission auto-populated course_id and rubric_id
Testing Row-Level Security (RLS)...
TEST 10.1 PASSED: Published assignment visible, draft assignment hidden from student
TEST 10A PASSED: RLS/Trigger blocked submission on behalf of another student
TEST 10B PASSED: RLS blocked non-pending submission
TEST 10C PASSED: RLS/Trigger blocked submission to draft assignment
Testing Migration Rollback (down.sql)...
--- Executing SQL File: supabase/migrations/06_assignment_concept_mapping.down.sql ---
--- Finished: supabase/migrations/06_assignment_concept_mapping.down.sql ---
Rollback executed cleanly!
TEST 11A PASSED: Table assignment_criterion_concepts dropped cleanly
TEST 11B PASSED: assignments.status column dropped cleanly
Testing Migration Reapplication (up.sql)...
--- Executing SQL File: supabase/migrations/06_assignment_concept_mapping.up.sql ---
--- Finished: supabase/migrations/06_assignment_concept_mapping.up.sql ---
TEST 11C PASSED: Migration 06 reapplied cleanly with 0 errors!

ALL POSTGRESQL MIGRATION AND INTEGRITY TESTS PASSED SUCCESSFULLY!
```

### 3.2 Pytest Suite (`backend/tests`)
```text
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\mitta\OneDrive\Desktop\AgenticAI\eduagents
plugins: anyio-4.15.1, langsmith-0.4.34, asyncio-1.2.0, cov-4.1.0
collected 63 items

backend/tests/test_ai_pipeline.py::test_stage_1_document_extraction PASSED [  1%]
backend/tests/test_ai_pipeline.py::test_stage_2_rubric_evaluation PASSED [  3%]
backend/tests/test_assignments.py::test_faculty_list_course_assignments PASSED [  4%]
backend/tests/test_assignments.py::test_faculty_create_assignment_with_concepts_and_criteria PASSED [  6%]
backend/tests/test_assignments.py::test_faculty_cannot_map_cross_course_concepts PASSED [  7%]
backend/tests/test_assignments.py::test_faculty_cannot_map_invalid_rubric_criterion PASSED [  9%]
backend/tests/test_assignments.py::test_faculty_course_isolation_on_assignments PASSED [ 11%]
backend/tests/test_assignments.py::test_faculty_update_assignment_publish_toggle PASSED [ 12%]
backend/tests/test_assignments.py::test_faculty_delete_assignment PASSED [ 14%]
backend/tests/test_assignments.py::test_student_list_published_assignments PASSED [ 15%]
backend/tests/test_assignments.py::test_student_cannot_view_draft_assignment_details PASSED [ 17%]
backend/tests/test_assignments.py::test_student_cannot_view_assignment_for_non_enrolled_course PASSED [ 19%]
backend/tests/test_assignments.py::test_submission_to_draft_assignment_rejected PASSED [ 20%]
backend/tests/test_assignments.py::test_submission_to_non_enrolled_course_assignment_rejected PASSED [ 22%]
backend/tests/test_assignments.py::test_submission_to_published_assignment_succeeds PASSED [ 23%]
backend/tests/test_assignments.py::test_faculty_cannot_map_criterion_without_rubric PASSED [ 25%]
backend/tests/test_assignments.py::test_create_assignment_defaults_to_draft_when_status_omitted PASSED [ 26%]
backend/tests/test_assignments.py::test_faculty_cannot_remove_rubric_while_criterion_mappings_exist PASSED [ 28%]
backend/tests/test_assignments.py::test_faculty_cannot_change_to_incompatible_rubric PASSED [ 30%]
backend/tests/test_curriculum.py::test_faculty_can_list_owned_courses PASSED [ 31%]
backend/tests/test_curriculum.py::test_faculty_can_create_course PASSED  [ 33%]
backend/tests/test_curriculum.py::test_duplicate_course_code_is_rejected PASSED [ 34%]
backend/tests/test_curriculum.py::test_faculty_cannot_access_another_facultys_curriculum PASSED [ 36%]
backend/tests/test_curriculum.py::test_student_cannot_modify_curriculum PASSED [ 38%]
backend/tests/test_curriculum.py::test_unauthenticated_requests_rejected PASSED [ 39%]
backend/tests/test_curriculum.py::test_concept_crud_lifecycle_and_cascade_edge_deletion PASSED [ 41%]
backend/tests/test_curriculum.py::test_prerequisite_edge_dag_cycle_rejection PASSED [ 42%]
backend/tests/test_curriculum.py::test_cross_course_prerequisite_edge_rejection PASSED [ 44%]
backend/tests/test_curriculum.py::test_duplicate_prerequisite_edge_rejection PASSED [ 46%]
backend/tests/test_curriculum.py::test_save_curriculum_layout_batch_update PASSED [ 47%]
backend/tests/test_curriculum.py::test_student_read_only_curriculum_learning_graph PASSED [ 49%]
backend/tests/test_edge_cases.py::test_file_size_exceeds_limit PASSED    [ 50%]
backend/tests/test_edge_cases.py::test_faculty_submissions_filtering PASSED [ 52%]
backend/tests/test_edge_cases.py::test_rubrics_filter_by_course PASSED   [ 53%]
backend/tests/test_edge_cases.py::test_queue_rate_limit_retry_handling[asyncio] PASSED [ 55%]
backend/tests/test_edge_cases.py::test_queue_rate_limit_retry_handling[trio] PASSED [ 57%]
backend/tests/test_faculty.py::test_list_faculty_submissions_and_meta PASSED [ 58%]
backend/tests/test_faculty.py::test_faculty_override_grade PASSED        [ 60%]
backend/tests/test_faculty.py::test_rubrics_crud_lifecycle PASSED        [ 61%]
backend/tests/test_health.py::test_health_check PASSED                   [ 63%]
backend/tests/test_internal_jobs.py::test_process_jobs_unauthorized_without_secret PASSED [ 65%]
backend/tests/test_internal_jobs.py::test_process_jobs_unauthorized_with_wrong_secret PASSED [ 66%]
backend/tests/test_internal_jobs.py::test_process_jobs_authorized_success PASSED [ 68%]
backend/tests/test_security_auth.py::test_authenticated_student_can_submit_assignment PASSED [ 69%]
backend/tests/test_security_auth.py::test_student_cannot_submit_on_behalf_of_another_student PASSED [ 71%]
backend/tests/test_security_auth.py::test_student_cannot_read_another_students_submission PASSED [ 73%]
backend/tests/test_security_auth.py::test_student_cannot_read_another_students_mastery_records PASSED [ 74%]
backend/tests/test_security_auth.py::test_faculty_cannot_access_courses_they_do_not_own PASSED [ 76%]
backend/tests/test_security_auth.py::test_faculty_can_access_their_authorized_course_submissions PASSED [ 77%]
backend/tests/test_security_auth.py::test_faculty_override_identity_is_derived_from_authentication PASSED [ 79%]
backend/tests/test_security_auth.py::test_unauthenticated_requests_rejected_with_401 PASSED [ 80%]
backend/tests/test_security_auth.py::test_production_configuration_cannot_activate_mock_auth PASSED [ 82%]
backend/tests/test_security_auth.py::test_evaluation_persistence_authoritative_schema_and_mastery PASSED [ 84%]
backend/tests/test_security_auth.py::test_mastery_boundary_values_and_multiple_evidence PASSED [ 85%]
backend/tests/test_security_auth.py::test_jwt_security_rejection_forged_expired_invalid PASSED [ 87%]
backend/tests/test_faculty_override_uuid_and_display_name_separation PASSED [ 88%]
backend/tests/test_security_auth.py::test_realtime_subscription_targets_authoritative_submissions PASSED [ 90%]
backend/tests/test_submissions.py::test_create_submission_text_content PASSED [ 92%]
backend/tests/test_submissions.py::test_create_submission_pdf_file PASSED [ 93%]
backend/tests/test_submissions.py::test_create_submission_invalid_file_extension PASSED [ 95%]
backend/tests/test_submissions.py::test_list_student_submissions PASSED  [ 96%]
backend/tests/test_submissions.py::test_get_submission_detail PASSED     [ 98%]
backend/tests/test_submissions.py::test_get_nonexistent_submission_404 PASSED [100%]

======================== 63 passed, 1 warning in 2.98s ========================
```

### 3.3 Next.js Production Build
```text
> frontend@0.1.0 build
> next build

▲ Next.js 16.3.6 (Turbopack)
✓ Running next.config.ts took 53ms

  Creating an optimized production build ...
✓ Compiled successfully in 2.4s
  Running TypeScript ...
  Finished TypeScript in 8.4s ...
  Collecting page data using 11 workers ...
  Generating static pages using 11 workers (9/9) in 2.6s
  Finalizing page optimization ...

Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /admin
├ ○ /architecture
├ ○ /faculty
├ ƒ /faculty/courses/[courseId]/assignments
├ ƒ /faculty/courses/[courseId]/curriculum
├ ○ /faculty/rubrics
└ ○ /student

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

---

## 4. Modified and Created Files

| File | Type | Changes Description |
| :--- | :--- | :--- |
| [`supabase/migrations/06_assignment_concept_mapping.up.sql`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/supabase/migrations/06_assignment_concept_mapping.up.sql) | SQL Migration | Removed `EXCEPTION WHEN OTHERS THEN NULL` blocks; defaulted status to `draft`; dropped redundant `rubric_criteria.concept_id`; added `check_assignment_rubric_change` and `check_submission_consistency` triggers; added post-migration verification assertions. |
| [`supabase/migrations/06_assignment_concept_mapping.down.sql`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/supabase/migrations/06_assignment_concept_mapping.down.sql) | SQL Migration | Clean, exception-free rollback of all Day 3 triggers, functions, policies, and columns with post-rollback verification assertions. |
| [`supabase/console_setup.sql`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/supabase/console_setup.sql) | SQL Setup | Updated Section 13 to match hardened Migration 06 specifications. |
| [`backend/app/models/assignment.py`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/app/models/assignment.py) | Python Model | Updated default assignment status from `"published"` to `"draft"`. |
| [`backend/app/services/repository.py`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/app/services/repository.py) | Python Repository | Enforced rubric requirement when mapping criterion concepts; validated rubric changes to reject incompatible criterion mappings; populated `course_id` and `rubric_id` on submissions from assignments. |
| [`frontend/components/AssignmentEditorModal.tsx`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/frontend/components/AssignmentEditorModal.tsx) | React Component | Defaulted form status to `'draft'`; added clear UI guidance when no rubric is selected. |
| [`backend/tests/test_assignments.py`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/tests/test_assignments.py) | Test Suite | Added unit tests verifying rejection of criterion mapping without rubric, draft status default, and rejection of incompatible rubric updates. |
| [`scratch/test_postgres_day3_hardening.py`](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/scratch/test_postgres_day3_hardening.py) | Test Script | Automated test suite verifying live PostgreSQL triggers, constraints, RLS policies, rollback, and reapplication. |
