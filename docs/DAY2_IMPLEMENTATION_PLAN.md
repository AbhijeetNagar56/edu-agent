# Day 2 Implementation Plan: Faculty Curriculum Builder

## 1. Executive Summary
The primary objective of Day 2 is to deliver an interactive, production-grade **Faculty Curriculum Builder** allowing instructors to create and maintain a course's canonical curriculum as a Directed Acyclic Graph (DAG). 

In accordance with core architectural tenets:
- **One Canonical Graph Per Course**: There is exactly one canonical curriculum graph per course in `public.concepts` and `public.concept_edges`. Student-specific graphs are derived dynamically by joining canonical course concepts with student mastery records and concept feedback; no student-specific concept or edge copies are created.
- **Security & Authorization**: Course ownership is derived strictly from the authenticated backend session (`user.id`). Client-provided faculty or student identifiers are discarded. RLS policies and backend checks enforce isolation between faculty members.
- **Cycle Prevention**: Prerequisite connections follow `Prerequisite (from) -> Dependent (to)`. Cycles are rejected on the frontend for immediate UI feedback and strictly rejected by the PostgreSQL trigger `trg_prevent_concept_edge_cycles` at the database level.

---

## 2. Repository Audit & Reusability Matrix

### 2.1 Reused Frontend Components & Modules
| Component / Module | Path | Reusability Plan |
| :--- | :--- | :--- |
| `Navbar` | `frontend/components/Navbar.tsx` | Global top navigation, route highlight, authentication session state, live sync pill. Enhanced with direct link to Curriculum Builder. |
| `Modal` | `frontend/components/Modal.tsx` | Reusable modal dialog with backdrop, escape key handlers, accessible title for Course Creation and Concept Editing modals. |
| `StatCard` | `frontend/components/StatCard.tsx` | Used on course curriculum header to display Total Concepts, Prerequisite Edges, and Curriculum Structure metrics. |
| `Badge` / `StatusBadge` | `frontend/components/Badge.tsx` | Badging for difficulty tiers (`beginner`, `intermediate`, `advanced`) and course status indicators. |
| `api` Client | `frontend/lib/api.ts` | Central fetch wrapper passing Supabase Bearer token, unified error parsing via `ApiError`. |
| `supabase` Client | `frontend/lib/supabase.ts` | Client initialization for Supabase auth and realtime channel management. |
| `@xyflow/react` | `frontend/package.json` | Modern React Flow package (v12.12.1) installed for node-based graph rendering, panning, zooming, and edge interactions. |

### 2.2 Existing Backend APIs
- `GET /api/v1/faculty/submissions`: Filtered submissions for authorized faculty courses.
- `POST /api/v1/faculty/submissions/{id}/override`: Grade overrides with authenticated faculty audit trail.
- `GET/POST/PUT/DELETE /api/v1/faculty/rubrics`: Rubrics CRUD for authorized courses.
- `GET /api/v1/students/{student_id}/mastery`: Student mastery records with authorization checks.

### 2.3 Missing Functionality to Implement in Day 2
1. **Course Management Endpoints**:
   - `GET /api/v1/faculty/courses`: List courses owned by the authenticated faculty member.
   - `POST /api/v1/faculty/courses`: Create a new course with `name`, `code`, and `description`.
   - `GET /api/v1/faculty/courses/{course_id}`: Retrieve single course details and verify ownership.
2. **Curriculum Graph Consolidated Endpoints**:
   - `GET /api/v1/faculty/courses/{course_id}/curriculum`: Fetch canonical course metadata, concepts with coordinates and metadata, and prerequisite edges.
   - `PUT /api/v1/faculty/courses/{course_id}/curriculum`: Batch save or update concept positions and graph layout without creating duplicates.
3. **Granular Concept & Prerequisite Edge Endpoints**:
   - `POST /api/v1/faculty/courses/{course_id}/concepts`: Create concept node.
   - `PUT /api/v1/faculty/courses/{course_id}/concepts/{concept_id}`: Update concept node (name, description, category, difficulty, pos_x, pos_y).
   - `DELETE /api/v1/faculty/courses/{course_id}/concepts/{concept_id}`: Delete concept node (cascades prerequisite edges).
   - `POST /api/v1/faculty/courses/{course_id}/edges`: Create prerequisite edge (`from_concept` -> `to_concept`).
   - `DELETE /api/v1/faculty/courses/{course_id}/edges/{edge_id}`: Delete prerequisite edge.
4. **Student Read-Only Canonical Curriculum Endpoint (Phase 3 Prep)**:
   - `GET /api/v1/students/courses/{course_id}/curriculum`: Returns canonical course curriculum graph joined with authenticated student's mastery records.
5. **Interactive Graph UI & Editor**:
   - Course overview list and course creation modal.
   - Full React Flow canvas editor (`/faculty/courses/[courseId]/curriculum`) featuring:
     - Custom concept node with badges and port handles.
     - Prerequisite edge rendering with directional arrows.
     - Interactive creation, editing, deletion of nodes and edges.
     - Client-side cycle detection warning users before edge creation.
     - Persistent position saving and reloading from database.
     - Empty state with guided creation for fresh courses.

---

## 3. Database Schema Enhancements (Migration 05)

The existing tables `public.courses`, `public.concepts`, and `public.concept_edges` already support core relations and cycle triggers from Day 1. Migration `05_curriculum_enhancements.up.sql` adds:
1. `public.courses`:
   - `description TEXT NOT NULL DEFAULT ''`
   - Index `idx_courses_faculty` on `faculty_id`
2. `public.concepts`:
   - `category TEXT NOT NULL DEFAULT ''` (topic / category classification)
   - `difficulty TEXT NOT NULL DEFAULT 'intermediate' CHECK (difficulty IN ('beginner', 'intermediate', 'advanced'))`
3. `public.concept_edges`:
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` (if omitted)
4. RLS Compatibility:
   - Policies established in `04_rls_security_hardening.up.sql` (`public.owns_course(course_id)`) automatically govern these new columns without requiring broad policy rewrites.

---

## 4. Implementation Steps & File Modifications

| Step | Action | Files Affected |
| :--- | :--- | :--- |
| **1. Database** | Create migration 05 (`.up.sql`, `.down.sql`) and update `console_setup.sql`. Apply to local PostgreSQL test cluster. | `supabase/migrations/05_curriculum_enhancements.up.sql`<br>`supabase/migrations/05_curriculum_enhancements.down.sql`<br>`supabase/console_setup.sql` |
| **2. Backend Models** | Define Pydantic models for Course, Concept, ConceptEdge, and Curriculum Graph payloads with validation. | `backend/app/models/course.py`<br>`backend/app/models/curriculum.py` |
| **3. Backend Services** | Implement repository methods for Course CRUD, Concept CRUD, Edge CRUD, Graph Layout persistence, and ownership authorization. Support dual mode (Supabase + In-memory fallback). | `backend/app/services/repository.py` |
| **4. Backend Routers** | Create faculty course and curriculum router, register with `main.py`, enforce role and ownership checks. Add student read-only curriculum endpoint. | `backend/app/routers/faculty_courses.py`<br>`backend/app/routers/students.py`<br>`backend/app/main.py` |
| **5. Frontend Storage & API** | Add frontend types and API functions for courses and curriculum graph. | `frontend/lib/types.ts`<br>`frontend/lib/storage.ts` |
| **6. Frontend UI** | Implement React Flow Custom Node, Curriculum Canvas, Concept Modal, Course Creation Modal, and Curriculum Editor page. | `frontend/components/CurriculumNode.tsx`<br>`frontend/components/CurriculumCanvas.tsx`<br>`frontend/components/ConceptModal.tsx`<br>`frontend/components/CreateCourseModal.tsx`<br>`frontend/app/faculty/courses/[courseId]/curriculum/page.tsx`<br>`frontend/app/faculty/page.tsx` |
| **7. Testing & Verification** | Create backend unit/integration tests and empirical PostgreSQL verification script. Run frontend build and typecheck. | `backend/tests/test_curriculum.py`<br>`scratch/test_postgres_curriculum.py` |
| **8. Documentation** | Compile authoritative Day 2 execution report. | `docs/DAY2_EXECUTION_REPORT.md` |

---

## 5. Security Architecture & Invariants

1. **Role Enforcement**:
   - Only users with role `faculty` or `admin` can access `/api/v1/faculty/courses/*`.
   - Students receive HTTP 403 Forbidden if attempting any curriculum modification.
2. **Ownership Verification**:
   - For every course operation, `public.courses.faculty_id` must match `auth_user.id`.
   - Attempting to access or alter another faculty member's course returns HTTP 403 Forbidden.
3. **Cross-Course Integrity**:
   - Concepts cannot be transferred or linked to a course other than their parent course.
   - Edges connecting concepts from two different courses are strictly rejected (HTTP 400 Bad Request + DB Trigger Exception).
4. **Cycle Prevention**:
   - Self-loops (`from_concept == to_concept`) are rejected immediately.
   - Directed cycles (e.g. $A \to B \to C \to A$) are rejected by BFS/DFS cycle detection in backend and guaranteed by the recursive CTE trigger `trg_prevent_concept_edge_cycles` in PostgreSQL.
5. **No Data Fabrication**:
   - No mock student mastery or sample data is mixed into the canonical curriculum graph.
