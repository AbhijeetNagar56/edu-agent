# Day 3 Execution Report: Assignment Management and Curriculum Concept Mapping

**Date:** November 5, 2026  
**Project:** Human-AI Co-Learning Agent (EduAgents)  
**Role:** Senior Full-Stack Architect, PostgreSQL/Supabase Database Engineer, and Application Security Engineer  

---

## 1. Executive Summary

Day 3 of the EduAgents roadmap successfully implemented the assignment-management workflow connecting canonical faculty curriculum graphs to student assessments:

```
Course ──► Assignment ──► Rubric ──► Rubric Criteria ──► Curriculum Concepts ──► Student Submission
```

### Key Deliverables Completed:
1. **Repository Audit & Implementation Plan**: Inspected existing tables, migrations, RLS policies, backend routers, and frontend views. Documented in [DAY3_IMPLEMENTATION_PLAN.md](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/docs/DAY3_IMPLEMENTATION_PLAN.md).
2. **PostgreSQL Migration 06**: Created versioned, idempotent migrations [06_assignment_concept_mapping.up.sql](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/supabase/migrations/06_assignment_concept_mapping.up.sql) and rollback [06_assignment_concept_mapping.down.sql](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/supabase/migrations/06_assignment_concept_mapping.down.sql), adding `status`, `max_points`, and `assignment_criterion_concepts`.
3. **Database Consistency Triggers**: Implemented `check_assignment_criterion_concept_match()` and enforced `trg_check_assignment_concept_course_match` ensuring cross-course concept mappings and invalid rubric criteria are strictly rejected at the database level.
4. **Hardened RLS Policies**: Enforced that draft assignments and their concepts are invisible to students; students can only view published assignments for enrolled courses; submissions to draft assignments or un-enrolled courses are blocked.
5. **Backend Data Layer & Routers**:
   - Pydantic models in [assignment.py](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/app/models/assignment.py).
   - Authoritative repository methods in [repository.py](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/app/services/repository.py) supporting dual modes (PostgreSQL/Supabase and InMemory).
   - Faculty assignment management in [faculty_assignments.py](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/app/routers/faculty_assignments.py).
   - Student assignment endpoints in [students.py](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/app/routers/students.py).
   - Ingestion guards in [uploads.py](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/backend/app/routers/uploads.py) rejecting submissions to draft assignments or non-enrolled courses.
6. **Frontend User Experience**:
   - Course assignments management page: [page.tsx](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/frontend/app/faculty/courses/[courseId]/assignments/page.tsx).
   - Assignment editor modal with concept and criterion mapping: [AssignmentEditorModal.tsx](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/frontend/components/AssignmentEditorModal.tsx).
   - Updated student portal with assigned course work cards: [page.tsx](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/frontend/app/student/page.tsx).
   - Enhanced upload component with concept visualization: [StudentUpload.tsx](file:///c:/Users/mitta/OneDrive/Desktop/AgenticAI/eduagents/frontend/components/StudentUpload.tsx).
7. **Empirical Verification**:
   - **59/59 pytest unit and integration tests passing** (including 13 new comprehensive assignment lifecycle and security tests).
   - **5/5 live PostgreSQL tests passing** on port 5433 verifying triggers, RLS, and migration rollback.
   - **Next.js production build succeeded** with 0 errors across all routes.
   - Live visual screenshots captured and verified in [DAY3_SCREENSHOTS.md](file:///C:/Users/mitta/.gemini/antigravity/brain/6c3f1dca-9a88-43da-9c78-1f4aa10c9695/DAY3_SCREENSHOTS.md).

---

## 2. Database Schema & Migration Invariants

### 2.1 Schema Additions (Migration 06)
- **`public.assignments`**:
  - `status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'published', 'archived'))`
  - `max_points NUMERIC NOT NULL DEFAULT 100.0 CHECK (max_points > 0)`
  - `due_date TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '14 days')`
  - Index: `idx_assignments_course_status ON public.assignments(course_id, status)`
- **`public.rubric_criteria`**:
  - `concept_id UUID REFERENCES public.concepts(id) ON DELETE SET NULL`
  - Index: `idx_rubric_criteria_concept ON public.rubric_criteria(concept_id)`
- **`public.assignment_criterion_concepts`**:
  - Composite Primary Key: `(assignment_id, criterion_id, concept_id)`
  - Foreign keys with `ON DELETE CASCADE` to assignments and concepts.

### 2.2 Database Consistency Trigger
```sql
CREATE OR REPLACE FUNCTION public.check_assignment_criterion_concept_match()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
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

  SELECT course_id INTO v_concept_course
  FROM public.concepts WHERE id = NEW.concept_id;

  IF v_concept_course IS NULL THEN
    RAISE EXCEPTION 'Referenced concept % does not exist.', NEW.concept_id;
  END IF;

  IF v_assign_course <> v_concept_course THEN
    RAISE EXCEPTION 'Assignment criterion concept course mismatch: Assignment belongs to course % but Concept belongs to course %.',
      v_assign_course, v_concept_course;
  END IF;

  IF v_assign_rubric IS NOT NULL THEN
    SELECT EXISTS(
      SELECT 1 FROM public.rubric_criteria
      WHERE rubric_id = v_assign_rubric AND id = NEW.criterion_id
    ) INTO v_crit_exists;

    IF NOT v_crit_exists THEN
      RAISE EXCEPTION 'Criterion % does not belong to assignment rubric %.',
        NEW.criterion_id, v_assign_rubric;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;
```

---

## 3. API Contract Specifications

### 3.1 Faculty Endpoints (`/api/v1/faculty`)

| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/courses/{course_id}/assignments` | Faculty (Course Owner) | Lists all assignments (published & draft) with mapped concepts and criteria mappings. |
| `POST` | `/courses/{course_id}/assignments` | Faculty (Course Owner) | Creates an assignment, validating course concept isolation and rubric criteria consistency. |
| `GET` | `/assignments/{assignment_id}` | Faculty (Course Owner) | Retrieves complete assignment details, rubric criteria, and concept mappings. |
| `PUT` | `/assignments/{assignment_id}` | Faculty (Course Owner) | Updates title, description, due date, max marks, status (publish/unpublish), or concept mappings. |
| `DELETE` | `/assignments/{assignment_id}` | Faculty (Course Owner) | Deletes an assignment and associated join records. |

### 3.2 Student Endpoints (`/api/v1/students`)

| Method | Path | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/assignments` | Enrolled Student | Lists all published assignments for courses the student is enrolled in. Draft assignments strictly excluded. |
| `GET` | `/assignments/{assignment_id}` | Enrolled Student | Retrieves details of a published assignment. Draft returns 404; non-enrolled returns 403. |

### 3.3 Submission Endpoint (`/api/v1/submissions`)

| Method | Path | Guardrails Enforced |
|---|---|---|
| `POST` | `/api/v1/submissions` | Validates file type/size; verifies assignment exists; verifies `assignment.status == 'published'` (rejects draft with 400); verifies student is enrolled in assignment course (rejects with 403). Authoritatively binds `assignmentTitle`, `courseCode`, `rubricId`. |

---

## 4. Verification Evidence

### 4.1 Automated Backend Pytest Suite
Ran 59 tests covering all modules:
```
backend\tests\test_ai_pipeline.py ..                                     [  3%]
backend\tests\test_assignments.py .............                          [ 25%]
backend\tests\test_curriculum.py ............                            [ 45%]
backend\tests\test_edge_cases.py .....                                   [ 54%]
backend\tests\test_faculty.py ...                                        [ 59%]
backend\tests\test_health.py .                                           [ 61%]
backend\tests\test_internal_jobs.py ...                                  [ 66%]
backend\tests\test_security_auth.py ..............                       [ 89%]
backend\tests\test_submissions.py ......                                 [100%]

======================== 59 passed, 1 warning in 2.88s ========================
```

### 4.2 Empirical PostgreSQL Suite Output
Executed against test PostgreSQL cluster on port 5433:
```
============================================================
EDUAGENTS DAY 3 — POSTGRESQL EMPIRICAL TEST SUITE
============================================================
1. Applying migration: supabase\migrations\06_assignment_concept_mapping.up.sql
   -> Migration 06 applied successfully.
2. Verifying schema invariants on assignments and rubric_criteria...
   -> assignments.status and assignments.max_points exist with defaults.
   -> rubric_criteria.concept_id exists.
   -> public.assignment_criterion_concepts table verified.
3. Testing course-concept isolation triggers...
   -> PASS: Valid assignment_concept insertion succeeded.
   -> PASS: Cross-course concept correctly rejected by trg_check_assignment_concept_course_match.
   -> PASS: Valid assignment_criterion_concept insertion succeeded.
   -> PASS: Cross-course criterion concept correctly rejected by trg_check_assignment_criterion_concept_match.
   -> PASS: Non-existent criterion correctly rejected by trigger.
4. Testing Row-Level Security policies...
   -> PASS: Student sees published assignments (1) and draft assignments are hidden by RLS.
   -> PASS: Student submission to draft assignment blocked by RLS WITH CHECK.
5. Testing migration rollback (down.sql) and re-application...
   -> Rollback verified cleanly.
   -> Migration 06 re-applied cleanly.
============================================================
ALL 5 POSTGRESQL SUITE STEPS PASSED WITH 100% SUCCESS!
============================================================
```

### 4.3 Frontend TypeScript & Next.js Build
```
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

✓ Compiled successfully in 7.4s
✓ Generating static pages using 11 workers (9/9) in 2.5s
Build error count: 0
```

---

## 5. Security & Invariant Checklist

| Security Requirement | Status | Verification Evidence |
|---|---|---|
| Zero Client-Supplied Identity Trust | Verified | `user.id` strictly derived from Supabase JWT in `get_current_user`. |
| Course Ownership on Assignment CRUD | Verified | `is_course_owner_by_id` checks `courses.faculty_id == user.id`. Tested in `test_faculty_course_isolation_on_assignments`. |
| Cross-Course Concept Rejection | Verified | Enforced in backend repository and PostgreSQL trigger `trg_check_assignment_concept_course_match`. Tested in `test_faculty_cannot_map_cross_course_concepts`. |
| Rubric Criterion Consistency | Verified | Trigger `trg_check_assignment_criterion_concept_match` checks `criterion_id` in `rubric_criteria`. Tested in `test_faculty_cannot_map_invalid_rubric_criterion`. |
| Draft Assignments Hidden from Students | Verified | RLS `view assignments` and student endpoint filter `status = 'published'`. Tested in `test_student_list_published_assignments` and `test_student_cannot_view_draft_assignment_details`. |
| Submission Guardrails | Verified | Submissions to draft assignments or un-enrolled courses rejected with 400/403. Tested in `test_submission_to_draft_assignment_rejected` and `test_submission_to_non_enrolled_course_assignment_rejected`. |
| Migration Rollback Safety | Verified | `06_assignment_concept_mapping.down.sql` executed and verified on live PostgreSQL cluster. |

---

## 6. Next Steps for Day 4 (AI Evaluation Pipeline)

1. **Criterion-to-Concept Mastery Propagation**:
   - Downstream Gemini Flash grading will read `assignment_criterion_concepts` to directly map criterion scores (`scoreAwarded / maxPoints`) to concept evidence records.
2. **Dynamic Knowledge Graph State Updates**:
   - When a submission is graded, update `student_concept_mastery` and dispatch Realtime broadcast to student knowledge graph.
3. **Faculty Feedback & Overrides**:
   - Connect criterion score overrides to concept mastery recalibration.
