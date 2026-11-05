# Day 3 Implementation Plan: Assignment Management & Curriculum Concept Mapping

## 1. Executive Summary & Objective

The objective of Day 3 is to implement the end-to-end assignment-management and curriculum-mapping workflow connecting the canonical faculty curriculum DAG to student assessments:

```
Course ──► Assignment ──► Rubric ──► Rubric Criteria ──► Curriculum Concepts ──► Student Submission
```

This plan bridges canonical course concepts created in Day 2 to assignments and rubrics, exposes published assignments to enrolled students, and ensures submission ingestion strictly respects assignment publication status and student enrollment.

---

## 2. Repository Audit & Reusable Assets

### 2.1 Database & Migrations
- **`public.courses` & `public.concepts`**: Canonical courses and concepts created in Migrations 03 and 05.
- **`public.assignments`**: Created in `03_authoritative_schema.up.sql` with columns `id`, `course_id`, `rubric_id`, `title`, `description`, `due_date`, `created_by`, `created_at`, `updated_at`.
  - *Identified Gaps*: Missing `status` (`'draft'`, `'published'`, `'archived'`) and `max_points` (`NUMERIC NOT NULL DEFAULT 100.0`).
- **`public.assignment_concepts`**: Join table exists `(assignment_id UUID, concept_id UUID, PRIMARY KEY (assignment_id, concept_id))`.
  - Database trigger `trg_check_assignment_concept_course_match` already enforces that assigned concepts belong to the assignment's course.
- **`public.rubrics` & `public.rubric_criteria`**: Reusable rubric schema with `course_code`, `assignment_title`, `description`, `total_points`, and criteria `(id, rubric_id, title, description, max_points, weight_percent, order_index)`.
  - *Identified Gaps*: Need join table `public.assignment_criterion_concepts` to explicitly map individual rubric criteria to course concepts per assignment, and optional `concept_id` on `rubric_criteria`.
- **`public.submissions` & `public.submissions_v2`**: Consolidated table with columns `id`, `assignment_id`, `student_id`, `course_id`, `rubric_id`, `file_name`, `file_size`, `file_type`, `file_url`, `content_preview`, `status`, `processing_step`, `submitted_at`.
- **`public.enrollments`**: Course enrollment table `(course_id, student_id, enrolled_at)`.

### 2.2 Backend Modules
- **`backend/app/models/course.py` & `curriculum.py`**: Pydantic models for courses, concepts, and DAG edges.
- **`backend/app/models/rubric.py`**: Pydantic models for rubrics and criteria (`Rubric`, `RubricCriterion`, `RubricCreate`, `RubricUpdate`).
- **`backend/app/models/submission.py`**: Pydantic models for submission metadata and ingest forms.
- **`backend/app/routers/faculty_courses.py`**: Course and curriculum management with verified course ownership.
- **`backend/app/routers/uploads.py`**: Student submission endpoint (`POST /api/v1/submissions`).
  - *Identified Gaps*: Lacks checks that the assignment exists, is in `'published'` status, and that the authenticated student is enrolled in the course.
- **`backend/app/routers/students.py`**: Student learning graph and mastery endpoints.
- **`backend/app/services/repository.py`**: Authoritative repository supporting dual modes (PostgreSQL/Supabase and InMemory).
  - *Identified Gaps*: `InMemoryDatabase` and `Repository` currently lack full assignment CRUD, assignment concept mapping, and criterion concept mapping.

### 2.3 Frontend Modules
- **`frontend/app/faculty/page.tsx`**: Course cards with concepts and assignments counter, plus curriculum link.
- **`frontend/app/faculty/rubrics/page.tsx`**: Rubric manager with list, create, edit, delete, and view modals.
- **`frontend/app/student/page.tsx`**: Student dashboard displaying recent submissions, class average, and upload widget.
- **`frontend/components/StudentUpload.tsx`**: File dropzone and text submission component. Currently synthesizes course and assignment dropdowns from rubrics cache.
- **`frontend/lib/storage.ts`**: Client storage and API layer. Needs first-class assignment methods.

---

## 3. Database Migration Plan (Migration 06)

We will create versioned migration files:
`supabase/migrations/06_assignment_concept_mapping.up.sql` and `06_assignment_concept_mapping.down.sql`.

### 3.1 Schema Additions
1. **Assignments Enhancements**:
   - `ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'published', 'archived'));`
   - `ALTER TABLE public.assignments ADD COLUMN IF NOT EXISTS max_points NUMERIC NOT NULL DEFAULT 100.0 CHECK (max_points > 0);`
   - `CREATE INDEX IF NOT EXISTS idx_assignments_course_status ON public.assignments(course_id, status);`

2. **Rubric Criteria Concept Extension**:
   - `ALTER TABLE public.rubric_criteria ADD COLUMN IF NOT EXISTS concept_id UUID REFERENCES public.concepts(id) ON DELETE SET NULL;`

3. **Assignment Criterion Concepts Join Table**:
   ```sql
   CREATE TABLE IF NOT EXISTS public.assignment_criterion_concepts (
     assignment_id UUID NOT NULL REFERENCES public.assignments(id) ON DELETE CASCADE,
     criterion_id TEXT NOT NULL,
     concept_id UUID NOT NULL REFERENCES public.concepts(id) ON DELETE CASCADE,
     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     PRIMARY KEY (assignment_id, criterion_id, concept_id)
   );
   CREATE INDEX IF NOT EXISTS idx_assign_crit_concepts_concept ON public.assignment_criterion_concepts(concept_id);
   ```

4. **Consistency Triggers**:
   - Enforce that any concept mapped to an assignment or to an assignment's rubric criterion strictly belongs to the same course as the assignment.
   - If the assignment references a rubric, enforce that `criterion_id` belongs to `rubric_criteria` of that rubric.

5. **RLS Policy Adjustments**:
   - Update `assignments` `SELECT` policy:
     - Faculty who own the course can view ALL assignments (including drafts).
     - Students can only view assignments where `status = 'published'` AND the student is enrolled in that course (`can_access_course(course_id)`).
   - Update `assignment_concepts` & `assignment_criterion_concepts` `SELECT` policy:
     - Visible only if user can view the parent assignment.
   - Update `submissions` `INSERT` policy:
     - Enforce that the student can only submit if `status = 'pending'`, `attempts = 1`, student is enrolled in the course, and `assignment.status = 'published'`.

---

## 4. Backend Implementation Plan

### 4.1 Models (`backend/app/models/assignment.py`)
- `AssignmentStatus = Literal["draft", "published", "archived"]`
- `AssignmentBase`: `title`, `description`, `due_date`, `max_points`, `status`, `rubric_id`
- `AssignmentCreate`: `AssignmentBase` + `concept_ids: List[str]` + `criterion_concepts: Dict[str, str]` (mapping criterion ID -> concept UUID)
- `AssignmentUpdate`: Optional fields for title, description, due_date, max_points, status, rubric_id, concept_ids, criterion_concepts
- `CriterionConceptMapping`: `criterion_id`, `concept_id`, `concept_name`
- `Assignment`: Full model with `id`, `course_id`, `created_by`, `created_at`, `updated_at`, `concept_ids`, `concepts: List[Concept]`, `criterion_concepts: List[CriterionConceptMapping]`
- `StudentAssignment`: Sanitized student view with submission status (`unsubmitted`, `pending`, `graded`, `submitted_at`, `score`).

### 4.2 Repository Layer (`backend/app/services/repository.py`)
Implement in both PostgreSQL/Supabase and InMemory stores:
- `get_assignments_for_course(course_id: str, status_filter: Optional[str] = None) -> List[Assignment]`
- `get_assignment_by_id(assignment_id: str) -> Optional[Assignment]`
- `create_assignment(course_id: str, assignment_in: AssignmentCreate, faculty_id: str) -> Assignment`
- `update_assignment(assignment_id: str, update_in: AssignmentUpdate) -> Optional[Assignment]`
- `delete_assignment(assignment_id: str) -> bool`
- `get_student_assignments(student_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]`
- `is_student_enrolled(course_id: str, student_id: str) -> bool`
- Enforce validation rules:
  - Rejection of cross-course concept mappings with HTTP 400.
  - Rejection of non-existent rubric criteria mappings with HTTP 400.
  - Automatic synchronization of course assignment counts.

### 4.3 Routers
1. **`backend/app/routers/faculty_assignments.py`**:
   - `GET /api/v1/faculty/courses/{course_id}/assignments`: List assignments for a course. Requires course ownership.
   - `POST /api/v1/faculty/courses/{course_id}/assignments`: Create assignment with rubric and concept mappings.
   - `GET /api/v1/faculty/assignments/{assignment_id}`: Get assignment details with mapped concepts and rubric.
   - `PUT /api/v1/faculty/assignments/{assignment_id}`: Update assignment details, status (draft/published), due date, max marks, and mappings.
   - `DELETE /api/v1/faculty/assignments/{assignment_id}`: Delete assignment.
2. **`backend/app/routers/students.py`**:
   - `GET /api/v1/students/assignments`: List published assignments across all enrolled courses with concept tags and submission status.
   - `GET /api/v1/students/assignments/{assignment_id}`: Get full assignment details, rubric criteria, and mapped concepts for an enrolled student.
3. **`backend/app/routers/uploads.py`**:
   - In `create_submission`:
     - Lookup assignment by `assignment_id`. If not found, raise 404.
     - Verify assignment `status == 'published'`. If draft, raise 400/403 ("Submissions to draft assignments are not accepted").
     - Verify student enrollment via `is_student_enrolled(assignment.course_id, user.id)`. If not enrolled, raise 403 ("Student is not enrolled in this course").
     - Derive `course_code` and `rubric_id` authoritatively from the verified assignment record.

---

## 5. Frontend Implementation Plan

### 5.1 Storage & Types (`frontend/lib/types.ts` & `frontend/lib/storage.ts`)
- Add `Assignment`, `AssignmentCreate`, `AssignmentUpdate`, `CriterionConceptMapping` interfaces to `types.ts`.
- Add helper methods in `storage.ts`:
  - `fetchCourseAssignments(courseId: string)`
  - `fetchAssignmentDetails(assignmentId: string)`
  - `createAssignment(courseId: string, data: ...)`
  - `updateAssignment(assignmentId: string, data: ...)`
  - `deleteAssignment(assignmentId: string)`
  - `fetchStudentAssignments()`

### 5.2 Faculty Assignment Management UI
- Create `frontend/app/faculty/courses/[courseId]/assignments/page.tsx`:
  - Header with course breadcrumb, Back button, and "+ Create Assignment" action.
  - Table or card list of course assignments showing: Title, Status badge (Draft vs Published), Due date, Max marks, Associated rubric, Mapped concepts badges, Submission count.
  - Quick actions: Edit, Toggle Publish/Draft, Delete.
- Create `frontend/components/AssignmentEditorModal.tsx`:
  - Form fields: Title, Description, Due Date, Maximum Marks, Status (Draft / Published).
  - Rubric selector (dropdown populated with course rubrics).
  - Targeted Curriculum Concepts: Checkbox/tag list populated from course canonical concepts (`fetchCurriculumGraph`).
  - Rubric Criteria to Concept Mapping: When a rubric is selected, displays each criterion with an optional dropdown to assign it to one of the course's concepts.

### 5.3 Faculty Course Card Link
- Update `frontend/app/faculty/page.tsx` course cards with an explicit "Assignments" button linking to `/faculty/courses/${c.id}/assignments`.

### 5.4 Student Portal UI (`frontend/app/student/page.tsx` & `frontend/components/StudentUpload.tsx`)
- In `StudentUpload.tsx`:
  - Fetch authoritative student assignments via `fetchStudentAssignments()` rather than synthesizing from rubrics.
  - Only show enrolled courses and published assignments.
  - Display targeted curriculum concepts for the selected assignment.
  - Show due date and max marks.

---

## 6. Security & Invariant Checklist

| Invariant | Implementation Mechanism |
|---|---|
| Zero Client-Supplied Identity Trust | Authenticated `user.id` from verified Supabase JWT only. Never trust request body `faculty_id` or `student_id`. |
| Course Ownership on Assignment CRUD | Verify `public.owns_course(course_id)` on all faculty assignment endpoints. Cross-faculty operations return HTTP 403. |
| Strict Course-Concept Isolation | Database triggers and backend repository verify that `concept.course_id == assignment.course_id`. Rejects cross-course concepts with HTTP 400/Postgres EXCEPTION. |
| Draft Assignments Hidden from Students | RLS policy and student query filter `status = 'published'`. Student endpoint returns 404/403 for draft assignments. |
| Submission Guardrails | `POST /api/v1/submissions` validates file size/type, verifies student enrollment, and rejects submissions to draft assignments with HTTP 403. |
| Idempotent & Safe Migrations | `06_assignment_concept_mapping.up.sql` and rollback `06_assignment_concept_mapping.down.sql` tested on real PostgreSQL. |

---

## 7. Verification Plan & Test Matrix

1. **Automated Unit & Integration Tests (`backend/tests/test_assignments.py`)**:
   - Faculty create assignment with rubric and concepts.
   - Faculty update assignment (publish/unpublish, edit details).
   - Course isolation: Faculty A cannot read, edit, or delete Faculty B's assignments.
   - Cross-course concept rejection: attempting to map Course B's concepts to Course A's assignment is rejected.
   - Student visibility: enrolled student sees published assignments; draft assignments are excluded.
   - Student submission guards:
     - Submitting to published assignment succeeds.
     - Submitting to draft assignment returns 403/400.
     - Submitting to course student is not enrolled in returns 403.
2. **Empirical PostgreSQL Test Suite (`scratch/test_postgres_assignments.py`)**:
   - Apply Migration 06 to test database (`eduagents_test_fresh`).
   - Test `trg_check_assignment_concept_course_match` rejection on cross-course concept.
   - Test `assignment_criterion_concepts` trigger and uniqueness.
   - Test RLS policies for faculty and student roles.
   - Test migration rollback (`down.sql`) and re-application (`up.sql`).
3. **Frontend Compilation**:
   - Run `npx tsc --noEmit` and `npm run build` to ensure zero TypeScript errors.
4. **Execution Report**:
   - Document all steps, schema changes, API specs, and empirical test results in `docs/DAY3_EXECUTION_REPORT.md`.
