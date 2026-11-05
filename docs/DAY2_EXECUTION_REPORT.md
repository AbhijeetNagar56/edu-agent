# Day 2 Execution Report: Faculty Curriculum Builder

## 1. Features Implemented

### 1.1 Faculty Course Management
- **Course Listing**: Faculty members can view courses they own via `GET /api/v1/faculty/courses`. Ownership is bound strictly to `user.id` extracted from the cryptographically verified session.
- **Course Creation**: Faculty can establish a new course with a code (e.g. `CS101`), title, and description via `POST /api/v1/faculty/courses`. Course codes are unique; duplicate registration is rejected with HTTP 409 Conflict.
- **Course Metadata**: `GET /api/v1/faculty/courses/{course_id}` allows inspecting course details with strict ownership verification.

### 1.2 Canonical Curriculum DAG Editor
- **One Canonical Graph Per Course**: Exact implementation of the architectural invariant: each course maintains exactly one canonical set of concepts in `public.concepts` and prerequisite edges in `public.concept_edges`. No separate student copies are created.
- **Interactive React Flow Canvas**: Full-page curriculum editor at `/faculty/courses/[courseId]/curriculum` powered by `@xyflow/react` (v12.12.1) with zoom, pan, minimap, background grid, and fit-view controls.
- **Custom Concept Nodes**: Displays concept name, category tag, difficulty tier badge (`beginner` = emerald, `intermediate` = amber, `advanced` = purple), and left/right connection handles.
- **Prerequisite Connection Convention**:
  - `Prerequisite Concept (Source Handle / Right) -> Dependent Concept (Target Handle / Left)`.
  - Visual arrows (`MarkerType.ArrowClosed`) clearly communicate prerequisite flow.
- **DAG Cycle Validation (Dual-Layered)**:
  - **Frontend**: Immediate cycle detection (depth-first traversal over edges) prevents connecting self-loops or circular paths ($A \to B \to A$ or multi-node $A \to B \to C \to A$), displaying an instant warning banner without losing unsaved changes.
  - **Backend & Database**: Authoritative cycle prevention enforced by `Repository._has_cycle_or_path` and the PostgreSQL trigger `trg_prevent_concept_edge_cycles`.
- **Persistent Layout Management**: "Save Layout" persists node coordinates (`posX`, `posY`) to the database. Reload restores the exact canvas state.
- **Cascade Deletion**: Removing a concept node automatically deletes incident prerequisite edges via foreign key `ON DELETE CASCADE`.

### 1.3 Student Learning Graph Compatibility (Phase 3 Foundation)
- Implemented `GET /api/v1/students/courses/{course_id}/curriculum`, which joins the canonical course curriculum graph with the authenticated student's mastery evidence records and concept feedback.

---

## 2. Files Created and Modified

### Created Files
| File Path | Description |
| :--- | :--- |
| `docs/DAY2_IMPLEMENTATION_PLAN.md` | Architecture plan, audit inventory, and reusability matrix. |
| `docs/DAY2_EXECUTION_REPORT.md` | Authoritative Day 2 verification and operations report. |
| `supabase/migrations/05_curriculum_enhancements.up.sql` | Versioned migration adding course description, concept category/difficulty, and faculty indexes. |
| `supabase/migrations/05_curriculum_enhancements.down.sql` | Rollback migration for migration 05. |
| `backend/app/models/course.py` | Pydantic models for Course, CourseCreate, and CourseUpdate. |
| `backend/app/models/curriculum.py` | Pydantic models for Concept, ConceptEdge, CurriculumGraph, and CurriculumSaveRequest. |
| `backend/app/routers/faculty_courses.py` | REST API router for faculty courses, curriculum graph, concepts, and edges. |
| `backend/tests/test_curriculum.py` | 12 automated unit and integration tests covering course and curriculum lifecycle. |
| `scratch/test_postgres_curriculum.py` | Empirical PostgreSQL 17 test suite validating triggers, check constraints, and RLS. |
| `frontend/components/CreateCourseModal.tsx` | Accessible modal dialog for creating a course. |
| `frontend/components/ConceptModal.tsx` | Accessible modal dialog for creating/editing curriculum concepts. |
| `frontend/components/CurriculumNode.tsx` | Custom React Flow node rendering concept metadata, badges, and handles. |
| `frontend/components/CurriculumCanvas.tsx` | Interactive React Flow canvas with cycle prevention and controls. |
| `frontend/app/faculty/courses/[courseId]/curriculum/page.tsx` | Full-page faculty curriculum editor page. |

### Modified Files
| File Path | Changes Made |
| :--- | :--- |
| `supabase/console_setup.sql` | Synchronized with migration 05 table enhancements and indexes. |
| `backend/app/main.py` | Registered `faculty_courses.router` with prefix `/api/v1/faculty/courses`. |
| `backend/app/models/__init__.py` | Exported Course and Curriculum models. |
| `backend/app/routers/students.py` | Added student read-only learning graph endpoint `GET /api/v1/students/courses/{course_id}/curriculum`. |
| `backend/app/core/auth.py` | Enabled custom user ID parsing for development mock tokens (`mock-faculty-token:<uuid>`). |
| `backend/app/services/repository.py` | Implemented course CRUD, concept CRUD, edge CRUD, DAG cycle detection, and layout persistence. |
| `frontend/package.json` | Installed `@xyflow/react` (v12.12.1). |
| `frontend/lib/types.ts` | Added `Concept`, `ConceptDifficulty`, `ConceptEdge`, `CurriculumGraph`, and updated `Course`. |
| `frontend/lib/storage.ts` | Added API methods for faculty courses, curriculum graph, concepts, and prerequisite edges. |
| `frontend/app/faculty/page.tsx` | Integrated Course Management cards, "+ New Course" modal, and links to Curriculum Builder. |

---

## 3. API Endpoints & Request/Response Contracts

### 3.1 Course Management
#### `GET /api/v1/faculty/courses`
- **Auth**: `Bearer <token>` (Role: `faculty` or `admin`)
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": [
    {
      "code": "CS101",
      "name": "Introduction to Computer Science and Algorithms",
      "description": "Core algorithms, asymptotic complexity, sorting, and graph structures.",
      "id": "c1010000-0000-0000-0000-000000000001",
      "facultyId": "00000000-0000-0000-0000-000000000101",
      "createdAt": "2026-09-01T08:00:00Z",
      "conceptsCount": 6,
      "assignmentsCount": 2
    }
  ],
  "message": "Faculty courses retrieved successfully."
}
```

#### `POST /api/v1/faculty/courses`
- **Auth**: `Bearer <token>` (Role: `faculty` or `admin`)
- **Request Body**:
```json
{
  "code": "CS202",
  "name": "Advanced Operating Systems",
  "description": "Virtual memory, threads, synchronization, and scheduling."
}
```
- **Response `201 Created`**:
```json
{
  "success": true,
  "data": {
    "code": "CS202",
    "name": "Advanced Operating Systems",
    "description": "Virtual memory, threads, synchronization, and scheduling.",
    "id": "7a942bc1-6f4a-4d2c-9a28-3e5fa09802c1",
    "facultyId": "00000000-0000-0000-0000-000000000101",
    "createdAt": "2026-11-05T03:39:47.123456Z",
    "conceptsCount": 0,
    "assignmentsCount": 0
  },
  "message": "Course 'CS202' created successfully."
}
```

### 3.2 Curriculum Graph Operations
#### `GET /api/v1/faculty/courses/{course_id}/curriculum`
- **Auth**: `Bearer <token>` (Role: `faculty` or `admin`, verifies course ownership)
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "courseId": "c1010000-0000-0000-0000-000000000001",
    "courseCode": "CS101",
    "courseName": "Introduction to Computer Science and Algorithms",
    "courseDescription": "Core algorithms, asymptotic complexity, sorting, and graph structures.",
    "concepts": [
      {
        "name": "Basic Programming Constructs",
        "description": "Variables, control flow, functions, and memory references.",
        "category": "Foundations",
        "difficulty": "beginner",
        "posX": 100.0,
        "posY": 220.0,
        "id": "c1010000-c001-0000-0000-000000000001",
        "courseId": "c1010000-0000-0000-0000-000000000001",
        "createdAt": "2026-09-02T09:00:00Z"
      }
    ],
    "edges": [
      {
        "fromConcept": "c1010000-c001-0000-0000-000000000001",
        "toConcept": "c1010000-c002-0000-0000-000000000002",
        "id": "e1010000-0001-0000-0000-000000000001",
        "courseId": "c1010000-0000-0000-0000-000000000001",
        "createdAt": "2026-09-02T10:00:00Z"
      }
    ]
  },
  "message": "Curriculum graph retrieved successfully."
}
```

#### `PUT /api/v1/faculty/courses/{course_id}/curriculum`
- **Auth**: `Bearer <token>` (Role: `faculty` or `admin`, verifies course ownership)
- **Request Body**:
```json
{
  "positions": [
    { "id": "c1010000-c001-0000-0000-000000000001", "posX": 150.0, "posY": 250.0 }
  ]
}
```
- **Response `200 OK`**: Returns updated `CurriculumGraph`.

### 3.3 Granular Concept & Edge Operations
#### `POST /api/v1/faculty/courses/{course_id}/edges`
- **Request Body**:
```json
{
  "fromConcept": "c1010000-c005-0000-0000-000000000005",
  "toConcept": "c1010000-c006-0000-0000-000000000006"
}
```
- **Cycle Detected Response `400 Bad Request`**:
```json
{
  "error": {
    "code": "CYCLE_DETECTED",
    "message": "Cycle detected: Adding prerequisite edge from 'Graph Traversal' to 'Basic Programming' forms a circular dependency."
  }
}
```
- **Cross-Course Link Response `400 Bad Request`**:
```json
{
  "error": {
    "code": "CROSS_COURSE_EDGE",
    "message": "Prerequisite edges can only connect concepts within the same course."
  }
}
```

---

## 4. Database Schema Changes (Migration 05)

Migration `supabase/migrations/05_curriculum_enhancements.up.sql` applies:
```sql
ALTER TABLE public.courses ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_courses_faculty ON public.courses(faculty_id);

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

ALTER TABLE public.concept_edges ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
```

---

## 5. Security Checks & Invariant Verification

| Security Invariant | Verification Method | Result |
| :--- | :--- | :--- |
| **Authentication Requirement** | Requests to `/api/v1/faculty/courses/*` without Bearer token | **HTTP 401 Unauthorized** |
| **Student Modification Defense** | Students sending `POST/PUT/DELETE` to curriculum endpoints | **HTTP 403 Forbidden** |
| **Faculty Cross-Tenant Isolation** | Faculty member A attempting to access course owned by Faculty B | **HTTP 403 Forbidden** |
| **Identity Derivation** | Client-supplied `facultyId` or `userId` in payloads | **Discarded; strictly derived from `user.id`** |
| **Self-Loop Prevention** | Attempting to link concept $A \to A$ | **HTTP 400 Bad Request + DB Check** |
| **2-Node Cycle Prevention** | Existing $A \to B$, attempting to add $B \to A$ | **HTTP 400 Bad Request + Trigger Exception** |
| **Multi-Node Cycle Prevention** | Existing $A \to B \to C$, attempting to add $C \to A$ | **HTTP 400 Bad Request + Trigger Exception** |
| **Cross-Course Link Prevention** | Attempting to connect concept in Course 1 with concept in Course 2 | **HTTP 400 Bad Request + Trigger Exception** |
| **Cascade Cleanup** | Deleting concept $B$ removes all incident edges ($A \to B$, $B \to C$) | **Verified via ON DELETE CASCADE (0 orphan edges)** |
| **Database Row Level Security** | Verified on live PostgreSQL using `SET ROLE authenticated` | **RLS error code 42501 blocks unauthorized operations** |

---

## 6. Test Commands & Empirical Results

### 6.1 Backend Automated Pytest Suite
Command:
```powershell
python -m pytest backend/tests/ -v
```
Output:
```
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-8.4.2
collected 46 items

backend/tests/test_ai_pipeline.py::test_stage_1_document_extraction PASSED   [  2%]
backend/tests/test_ai_pipeline.py::test_stage_2_rubric_evaluation PASSED     [  4%]
backend/tests/test_curriculum.py::test_faculty_can_list_owned_courses PASSED [  6%]
backend/tests/test_curriculum.py::test_faculty_can_create_course PASSED      [  8%]
backend/tests/test_curriculum.py::test_duplicate_course_code_is_rejected PASSED [ 10%]
backend/tests/test_curriculum.py::test_faculty_cannot_access_another_facultys_curriculum PASSED [ 13%]
backend/tests/test_curriculum.py::test_student_cannot_modify_curriculum PASSED [ 15%]
backend/tests/test_curriculum.py::test_unauthenticated_requests_rejected PASSED [ 17%]
backend/tests/test_curriculum.py::test_concept_crud_lifecycle_and_cascade_edge_deletion PASSED [ 19%]
backend/tests/test_curriculum.py::test_prerequisite_edge_dag_cycle_rejection PASSED [ 21%]
backend/tests/test_curriculum.py::test_cross_course_prerequisite_edge_rejection PASSED [ 23%]
backend/tests/test_curriculum.py::test_duplicate_prerequisite_edge_rejection PASSED [ 26%]
backend/tests/test_curriculum.py::test_save_curriculum_layout_batch_update PASSED [ 28%]
backend/tests/test_curriculum.py::test_student_read_only_curriculum_learning_graph PASSED [ 30%]
backend/tests/test_security_auth.py::test_jwt_security_rejection_forged_expired_invalid PASSED [ 82%]
backend/tests/test_submissions.py::test_get_submission_detail PASSED         [ 97%]
backend/tests/test_submissions.py::test_get_nonexistent_submission_404 PASSED [100%]

======================== 46 passed, 1 warning in 2.62s ========================
```

### 6.2 Empirical PostgreSQL 17 Cluster Verification
Command:
```powershell
python scratch/test_postgres_curriculum.py
```
Output:
```
======================================================================
EMPIRICAL POSTGRESQL 17 CURRICULUM VERIFICATION SUITE
======================================================================
[TEST 1] Setup Faculty and Student Profiles...
  -> Passed: Profiles initialized.
[TEST 2] Course Creation with Description & Uniqueness...
  -> Passed: Course 1 created: CS101 (ad23a395-5c2c-4106-95dd-4f556d9f545b)
  -> Passed: Course 2 created: AI301 (f5e54078-b987-4e66-82c5-5b41e4fc5079)
[TEST 3] Concept Insertion with Category & Difficulty...
  -> Passed: Created concepts: c1=0e38f2d1-..., c2=9f49bca5-..., c3=859e4849-..., c_ai=4ab4be27-...
[TEST 4] Difficulty Check Constraint Rejection...
  -> Passed: Check constraint rejected invalid difficulty: 23514
[TEST 5] Prerequisite Edge Insertion...
  -> Passed: Prerequisite chain created: c1 -> c2 -> c3
[TEST 6] Trigger Rejection of Self-Loop Edge (c1 -> c1)...
  -> Passed: Trigger rejected self loop: ERROR: Concept cannot have a prerequisite edge to itself.
[TEST 7] Trigger Rejection of 2-Node Cycle (c2 -> c1)...
  -> Passed: Trigger rejected 2-node cycle: ERROR: Cycle detected: Adding prerequisite edge forms a circular dependency.
[TEST 8] Trigger Rejection of Multi-Node Cycle (c3 -> c1)...
  -> Passed: Trigger rejected multi-node cycle: ERROR: Cycle detected: Adding prerequisite edge forms a circular dependency.
[TEST 9] Trigger Rejection of Cross-Course Edge (c1 in CS101 -> c_ai in AI301)...
  -> Passed: Trigger rejected cross-course edge: ERROR: Prerequisite edges can only connect concepts within the same course.
[TEST 10] Concept Deletion Cascade on Edges...
  -> Passed: Dependent prerequisite edges successfully removed via ON DELETE CASCADE.
[TEST 11] RLS Isolation Verification...
  -> Passed: RLS blocked unauthorized faculty insert: 42501
  -> Passed: RLS blocked student concept insert: 42501
======================================================================
ALL 11 POSTGRESQL CURRICULUM VERIFICATION TESTS PASSED SUCCESSFULLY!
======================================================================
```

### 6.3 Frontend TypeScript Verification
Command:
```powershell
cd frontend; npx tsc --noEmit
```
Output:
```
Command exited with code 0. (0 errors)
```

### 6.4 Next.js Production Build
Command:
```powershell
cd frontend; npm run build
```
Output:
```
✓ Compiled successfully in 6.6s
✓ Generating static pages using 11 workers (9/9) in 7.2s
  Finalizing page optimization ...

Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /admin
├ ○ /architecture
├ ○ /faculty
├ ƒ /faculty/courses/[courseId]/curriculum
├ ○ /faculty/rubrics
└ ○ /student
```

---

## 7. Known Limitations
1. **Multi-Selection Box Selection**: React Flow canvas currently supports single-node selection for modal editing. Bulk concept movement is supported by drag-panning, but bulk attribute editing is intentionally disabled to avoid accidental batch overwrites.
2. **Auto-Layout / Sugiyama Layout**: Concepts are manually positioned by faculty on the canvas and their $(x, y)$ coordinates are saved. An automated hierarchical DAG layout algorithm (e.g. Dagre) can be added as an optional "Auto-Align" helper in future phases.

---

## 8. Manual Testing Procedure

1. **Start Backend**:
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. **Start Frontend**:
   ```powershell
   cd frontend; npm run dev
   ```
3. **Faculty Workflow**:
   - Navigate to `http://localhost:3000/faculty`.
   - Observe the "Courses & Canonical Curriculum Graphs" grid showing CS101 and AI301.
   - Click **"+ New Course"**, enter Code: `CS202`, Title: `Advanced Algorithms`, Description: `Dynamic programming and network flow`, click **Create Course**. The new course card appears dynamically.
   - Click **"Open Curriculum Builder"** on `CS101` (`/faculty/courses/c1010000-0000-0000-0000-000000000001/curriculum`).
   - Observe the 6 concept nodes and directional prerequisite edges.
   - Click **"Add Concept"**, enter Name: `Network Flow & Bipartite Matching`, Difficulty: `Advanced`, Category: `Graph Theory`. The new node appears on the canvas.
   - Drag a connection from the right port of `Graph Traversal & Shortest Paths` to the left port of `Network Flow`. Notice the animated purple arrow appears.
   - Try dragging a connection backward from `Network Flow` to `Basic Programming Constructs`. Notice the red banner: *"Cycle detected: Connecting this prerequisite forms a circular dependency in the curriculum DAG."* The invalid edge is rejected.
   - Move nodes around to optimize the layout, click **"Save Layout"**. The green success toast appears.
   - Refresh the browser (`F5`). Observe the saved positions and prerequisite connections reload identically from the database.

---

## 9. Screenshots of the Working Faculty Curriculum Editor

The application was run and high-resolution screenshots were captured using headless Chromium:

1. **Faculty Curriculum Builder (DAG Editor)**:
   - File: `docs/screenshots/curriculum_builder.png`
   - Shows the 6 CS101 concept nodes, difficulty tier badges, category tags, directional arrows, and graph controls.
2. **Faculty Evaluation Dashboard**:
   - File: `docs/screenshots/faculty_dashboard.png`
   - Shows the new "Owned Courses & Canonical Curriculum Graphs" grid, course cards, "+ New Course" button, and direct navigation links.
3. **Assignment Grading Rubrics**:
   - File: `docs/screenshots/faculty_rubrics.png`
   - Shows the rubric management interface for course evaluations.

Full visual artifact: [DAY2_SCREENSHOTS.md](file:///C:/Users/mitta/.gemini/antigravity/brain/6c3f1dca-9a88-43da-9c78-1f4aa10c9695/DAY2_SCREENSHOTS.md)
