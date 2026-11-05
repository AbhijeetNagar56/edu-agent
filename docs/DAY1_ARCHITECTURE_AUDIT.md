# Day 1 Architecture & Schema Audit: Human-AI Co-Learning Agent

**Date:** November 2026  
**Auditor:** Senior Full-Stack Architect, Supabase/PostgreSQL Database Engineer, Application Security Engineer  
**Project:** EduAgents – Human-AI Co-Learning Platform  
**Target Milestone:** Day 1 Consolidation, Authorization Hardening, and Schema Unification  

---

## 1. Executive Summary & Current Architecture

EduAgents is an agentic Human-AI co-learning platform designed for higher-education computer science courses. Its central educational mission is to maintain a dynamic student knowledge graph visualizing concept-level mastery through automated, rubric-aligned AI evaluation and faculty human-in-the-loop oversight.

### 1.1 High-Level Architecture Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend (Vercel)                       │
│  - /student: Document submission (PDF/MD), live status, grade modal    │
│  - /faculty: Class roster, grade review, score override modal, export  │
│  - /faculty/rubrics: Rubric creation, criteria weight management       │
└──────────────┬──────────────────────────────────────────▲──────────────┘
               │ 1. POST /api/v1/submissions              │ 6. Supabase Realtime
               │    (PDF / Markdown + metadata)          │    WebSocket events
               ▼                                          │
┌─────────────────────────────────────────────────────────┴──────────────┐
│                        FastAPI Backend (Port 8000)                     │
│  - app/routers/uploads.py: Validates upload, stores raw file           │
│  - app/services/storage.py: Ingests to Supabase Storage ('submissions')│
│  - app/services/queue.py: Enqueues job with status 'pending'           │
│  - app/routers/internal_jobs.py: POST /internal/process-jobs (cron)    │
│  - app/ai/pipeline.py: Two-stage sequential Gemini AI evaluation       │
│  - app/routers/grades.py: Rubrics CRUD & faculty grade overrides       │
└──────────────┬──────────────────────────────────────────▲──────────────┘
               │ 2. Store file & queue job                │ 5. Read file & write
               ▼                                          │    evaluations
┌─────────────────────────────────────────────────────────┴──────────────┐
│                  Supabase / PostgreSQL Cloud Database                  │
│  - PostgreSQL: Relational state, RLS policies, audit history           │
│  - Supabase Storage: Private bucket 'submissions' for student files    │
│  - Supabase Realtime: Publication on submission update events          │
│  - Supabase Auth: JWT-based user identities and profiles trigger       │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Tech Stack Inventory

| Tier | Existing Technology | Configured Version | Key Modules / Role |
| :--- | :--- | :--- | :--- |
| **Frontend** | Next.js (App Router, Turbopack) | `16.3.6` (React 19) | `app/student/page.tsx`, `app/faculty/page.tsx`, `lib/storage.ts`, `lib/api.ts` |
| **Backend** | FastAPI / Uvicorn / Starlette | `0.115.0+` (Python 3.13) | `app/main.py`, `app/routers/`, `app/services/`, `app/core/auth.py` |
| **Database & Auth** | Supabase / PostgreSQL | `PostgreSQL 15+` | `auth.users`, `public.profiles`, RLS, storage buckets, Supabase Realtime |
| **AI Evaluation** | Google Gemini (`google-genai`) | `gemini-2.5-flash-lite`, `gemini-2.5-flash` | Two-stage extraction (`app/ai/extract.py`) and rubric grading (`app/ai/grade.py`) |
| **Testing** | Pytest / Pytest-Asyncio | `pytest 8.4.2` | `backend/tests/` (20 test cases covering AI pipeline, submissions, faculty) |

---

## 2. Existing Database Schema Inventory

The repository currently exhibits **two competing, fragmented database schemas**:
1. **Schema 1 (`supabase/migrations/01_user_migrations.up.sql`):** The initial relational curriculum and knowledge graph schema utilizing UUID primary keys and Foreign Keys tied to `auth.users`.
2. **Schema 2 (`supabase/migrations/02_api_schema.up.sql`):** An ad-hoc API schema utilizing `text` primary keys (`sub-101`, `rubric-1`), client-supplied strings, and decoupled tables created to support rapid API implementation.
3. **Consolidation Script (`supabase/console_setup.sql`):** Attempts to declare both schemas side-by-side, explicitly noting: *"The original migration's public.submissions table models a different workflow. The FastAPI API uses submissions_v2 to avoid colliding with that schema."*

### Table-by-Table Inventory

| Table Name | Schema Origin | Primary Key | Key Foreign Keys | Unique Constraints | Purpose | Status in Codebase |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `public.profiles` | Schema 1 | `id` (uuid) | `id` references `auth.users(id)` ON DELETE CASCADE | `id` | Mirrors Supabase Auth users; stores `role` ('student'/'faculty') | Active in RLS & console setup; bypassed by dev mocks |
| `public.courses` | Schema 1 | `id` (uuid) | `faculty_id` references `profiles(id)` | None | Course catalog and faculty ownership | Unused by FastAPI backend (backend queries free-text `course_code`) |
| `public.enrollments` | Schema 1 | `(course_id, student_id)` | `courses(id)`, `profiles(id)` | Composite PK | Student course registrations | Unused by FastAPI backend |
| `public.concepts` | Schema 1 | `id` (uuid) | `course_id` references `courses(id)` | None | Knowledge graph nodes with (x, y) coordinates | Unused by current FastAPI backend |
| `public.concept_edges` | Schema 1 | `id` (uuid) | `from_concept`, `to_concept` references `concepts(id)` | `(from_concept, to_concept)` | Prerequisite DAG relationships | Unused by current FastAPI backend |
| `public.assignments` | Schema 1 | `id` (uuid) | `course_id` references `courses(id)` | None | Course assignments with due dates and rubric text | Unused by current FastAPI backend |
| `public.assignment_concepts` | Schema 1 | `(assignment_id, concept_id)` | `assignments(id)`, `concepts(id)` | Composite PK | Links assignments to covered knowledge concepts | Unused by current FastAPI backend |
| `public.submissions` (v1) | Schema 1 | `id` (uuid) | `assignment_id` references `assignments`, `student_id` references `profiles` | `(assignment_id, student_id)` | Original student submission model with concept feedback | **Orphaned / Competitor** to `submissions_v2` |
| `public.submission_concept_feedback` | Schema 1 | `id` (uuid) | `submission_id` references `submissions(v1)`, `concept_id` references `concepts` | None | Concept-level score and qualitative feedback | **Orphaned** due to `submissions` vs `submissions_v2` split |
| `public.student_concept_mastery` | Schema 1 | `id` (uuid) | `student_id` references `profiles`, `concept_id` references `concepts`, `submission_id` references `submissions(v1)` | None | Accumulated student concept mastery percentage | **Orphaned** from AI evaluation pipeline |
| `public.rubrics` | Schema 2 | `id` (text) | None (`course_code` is unverified text) | None | Faculty grading rubrics for assignments | **Actively used** by FastAPI & frontend |
| `public.rubric_criteria` | Schema 2 | `id` (text) | `rubric_id` references `rubrics(id)` ON DELETE CASCADE | None | Weighted rubric criteria and descriptions | **Actively used** by FastAPI & frontend |
| `public.submissions_v2` | Schema 2 | `id` (text) | `rubric_id` references `rubrics(id)`, `owner_id` references `auth.users(id)` | None | Flat submission metadata table with client strings | **Actively used** by FastAPI & frontend |
| `public.grading_jobs` | Schema 2 | `id` (text) | `submission_id` references `submissions_v2(id)` ON DELETE CASCADE | None | Async cron queue state (`pending`, `processing`, `done`) | **Actively used** by FastAPI job runner |
| `public.evaluations` | Schema 2 | `id` (text) | `submission_id` references `submissions_v2(id)` ON DELETE CASCADE | `submission_id` (1:1) | Overall Gemini AI grading output | **Actively used** by FastAPI & frontend |
| `public.criterion_evaluations` | Schema 2 | `id` (text) | `evaluation_id` references `evaluations(id)` ON DELETE CASCADE | None | Criterion-level points awarded and commentary | **Actively used** by FastAPI & frontend |
| `public.faculty_overrides` | Schema 2 | `id` (text) | `submission_id` references `submissions_v2(id)` ON DELETE CASCADE | None | Faculty grade override audit log | **Actively used** by FastAPI & frontend |

---

## 3. Frontend/Backend Table Dependency Mapping

### Frontend Dependencies (`frontend/`)

1. **Supabase Realtime Subscription (`frontend/lib/storage.ts` line 26):**
   - Subscribes specifically to table `public.submissions_v2` on channel `eduagents-submissions`.
   - On change events, triggers `refreshSubmissions()`.
2. **Synthetic Course Hierarchy (`frontend/lib/storage.ts` lines 41–49):**
   - The frontend **does not query `courses` or `assignments` tables**.
   - Instead, it calls `GET /api/v1/faculty/rubrics` and synthesizes fake `Course` and `Assignment` objects in client memory by grouping distinct `rubric.courseCode` strings.
3. **Submission Creation (`frontend/components/StudentUpload.tsx` lines 93–99):**
   - Sends client-entered form fields: `student_id`, `student_name`, `student_email`, `assignment_id` (set to `rubric.id`), `assignment_title`, `course_code`, and `rubric_id`.
4. **Faculty Override (`frontend/components/OverrideModal.tsx` lines 77–86):**
   - Sends `overriddenScore`, `overriddenBy` (arbitrary text input, default "Dr. Sarah Lin"), `overrideReason`, and `criterionAdjustments`.

### Backend Dependencies (`backend/app/`)

1. **`app/services/repository.py`:**
   - Supabase PostgREST queries strictly target:
     - `rubrics` (`.select("*, rubric_criteria(*)")`)
     - `rubric_criteria`
     - `submissions_v2` (`.select("*")`, `.upsert(row)`)
     - `grading_jobs` (`.select("*").eq("status", "pending")`)
     - `evaluations`
     - `criterion_evaluations`
     - `faculty_overrides`
   - When Supabase credentials are not present or queries fail, `repository.py` falls back to an in-memory dictionary `InMemoryDatabase` initialized with `SEED_SUBMISSIONS` and `SEED_RUBRICS`.
2. **`app/services/storage.py`:**
   - Interacts with Supabase Storage bucket `submissions`.
   - Stores raw files at storage key: `{submission_id}/{filename}`.
3. **`app/services/realtime.py`:**
   - Broadcasts ephemeral WebSocket messages on channel `eduagents-realtime`.

---

## 4. Existing Submission & Evaluation Lifecycle Trace

```
1. Student Upload
   ├── Next.js: Student selects course/assignment, drops PDF or Markdown.
   ├── Next.js: POST /api/v1/submissions (multipart/form-data)
   └── FastAPI (app/routers/uploads.py):
       ├── Computes ID: sub-<timestamp>
       ├── Stores file in Supabase Storage bucket 'submissions' (or in-memory)
       ├── Inserts row into public.submissions_v2 with status = 'pending'
       └── Creates public.grading_jobs row with status = 'pending'
                                │
                                ▼
2. Cron Job Scheduling
   ├── GitHub Actions cron or manual POST /internal/process-jobs
   └── FastAPI (app/routers/internal_jobs.py -> app/services/queue.py):
       ├── Authenticates via 'X-Internal-Secret'
       ├── Fetches batch of pending grading_jobs (limit 10)
       └── Locks each job: grading_jobs.status = 'processing'
                                │
                                ▼
3. AI Evaluation Pipeline
   ├── Retrieves raw text from storage (extracts PDF text via pypdf)
   ├── Stage 1: Document Ingestion (Gemini Flash-Lite)
   │   └── Generates structured JSON: documentTitle, author, sections, codeBlocks, proofs
   ├── Stage 2: Deep Pedagogical Grading (Gemini Flash)
   │   └── Evaluates structured JSON against rubric criteria
   │   └── Computes numerical scores, strengths, improvements, criterion feedback
   └── Writes to Postgres:
       ├── public.evaluations (overall score, percentage, feedback, models)
       ├── public.criterion_evaluations (score and feedback per criterion)
       ├── public.submissions_v2: status = 'done', processing_step = 'synced'
       └── public.grading_jobs: status = 'done', completed_at = NOW()
                                │
                                ▼
4. Realtime Broadcast & Student/Faculty Notification
   ├── Broadcasts event on Supabase channel 'eduagents-realtime'
   ├── Next.js Student Portal receives update via Realtime / fetch
   └── Submissions card flips from 'Pending' to 'Done' with score and feedback
                                │
                                ▼
5. Faculty Review & Override
   ├── Faculty inspects submission on /faculty dashboard
   ├── Faculty adjusts points on /override modal and adds justification
   └── FastAPI (POST /api/v1/faculty/submissions/{id}/override):
       ├── Inserts audit record into public.faculty_overrides
       └── Updates public.submissions_v2 (marks overridden)
```

---

## 5. Duplicate Schema Identification & Disconnects

The audit reveals **six major structural disconnects** between the intended Human-AI Co-Learning platform and the existing implementation:

```
┌────────────────────────────────────────┐       ┌────────────────────────────────────────┐
│     Schema 1: Learning Graph Model     │       │       Schema 2: FastAPI API Model      │
│  (courses, concepts, concept_mastery)  │       │   (rubrics, submissions_v2, jobs)      │
├────────────────────────────────────────┤       ├────────────────────────────────────────┤
│ • UUID primary keys throughout         │       │ • Text primary keys ('sub-101')        │
│ • Strong FKs to auth.users (profiles)  │  VS   │ • Weak/absent FKs; free-text strings   │
│ • Concept DAG with prerequisite edges  │       │ • No knowledge graph awareness         │
│ • Concept mastery calculated & tracked │       │ • No mastery records written by AI     │
│ • Table: 'submissions' (orphaned)      │       │ • Table: 'submissions_v2' (active)     │
└────────────────────────────────────────┘       └────────────────────────────────────────┘
```

1. **`submissions` vs `submissions_v2`:**
   - `submissions` has UUID PK, references `assignments(id)` and `profiles(id)`, tracks `attempts`, `is_late`, `processing_started_at`, and links to `submission_concept_feedback`.
   - `submissions_v2` has Text PK, stores unstructured student names/emails, links to `grading_jobs` and `evaluations`.
   - **Result:** Two competing submission models. The AI pipeline writes exclusively to `submissions_v2`, leaving `submission_concept_feedback` and `student_concept_mastery` completely dry.
2. **Assignments vs Rubrics:**
   - In Schema 1, `assignments` belongs to `courses`, has `due_date`, and links to `concepts` via `assignment_concepts`.
   - In Schema 2, `rubrics` acts as a surrogate assignment table, containing `assignment_title` and `course_code` text fields without relational integrity.
3. **Student Identity Disconnect:**
   - Schema 1 models students via `profiles(id uuid)` tied to `auth.users(id)`.
   - Schema 2 and the FastAPI routes accept client-provided `student_id` ("STU-2024-302"), `student_name`, and `student_email` without checking the authenticated JWT.
4. **Faculty Override vs Mastery Override:**
   - Schema 1 provided a table `student_concept_mastery` with `source in ('ai', 'faculty_override')`.
   - Schema 2 provided `faculty_overrides` logging score adjustments and textual justification for rubric criteria.
   - Neither system currently updates concept mastery when a faculty override occurs.
5. **Realtime Channel Disconnect:**
   - Frontend listens to PostgreSQL changes on `submissions_v2`.
   - Backend `RealtimeService` broadcasts broadcast events on `eduagents-realtime`.

---

## 6. Critical Security & Authorization Vulnerabilities

A comprehensive review of the authentication headers, route handlers, and RLS policies identified **eight high-severity vulnerabilities**:

### Vulnerability 1: Student Impersonation in Submission Upload (High)
- **Location:** `backend/app/routers/uploads.py` line 20–31 (`create_submission`).
- **Issue:** The endpoint accepts `student_id: str = Form(...)`, `student_name: str = Form(...)`, and `student_email: str = Form(...)` directly from the client.
- **Impact:** An authenticated student can pass another student's ID or email in the form body and submit assignments on their behalf. Identity is not derived from `user.id`.

### Vulnerability 2: Student Unauthorized Record Access via Insecure Email Matching (High)
- **Location:** `backend/app/routers/uploads.py` lines 93, 130.
- **Issue:** Ownership verification checks `sub.studentEmail.lower() != user.email.lower()`.
- **Impact:** Email strings are mutable, susceptible to unicode spoofing, and detached from the immutable Supabase UUID (`auth.uid()`). If an attacker submits a file with a victim's email, the victim can read the attacker's files or vice-versa.

### Vulnerability 3: Faculty Spoofing in Grade Override Audit Trail (Critical)
- **Location:** `backend/app/routers/grades.py` lines 81–83 (`override_submission_grade`).
- **Issue:** The override endpoint accepts `override_req.overriddenBy` from the JSON payload:
  ```python
  overriddenBy = override_req.overriddenBy or user.email
  ```
- **Impact:** Any user with a faculty role can forge the `overriddenBy` string (e.g. impersonating "Dean of Faculty") in the permanent audit trail.

### Vulnerability 4: Missing Course Authorization on Faculty Operations (High)
- **Location:** `backend/app/routers/grades.py` lines 31, 59, 118, 160, 184.
- **Issue:** The dependency `require_role(["faculty", "admin"])` only verifies that the caller has a global faculty role. It never verifies that the authenticated instructor actually owns or teaches the course corresponding to the submission or rubric (`public.owns_course(course_id)`).
- **Impact:** Any faculty member can read, delete, or override grades and rubrics for any course across the university.

### Vulnerability 5: Insecure Mock Authentication Fallback in Development (Critical)
- **Location:** `backend/app/core/auth.py` lines 41–46, 56–60, 95–100.
- **Issue:**
  ```python
  if not credentials:
      if settings.ENVIRONMENT == "development":
          return AuthUser(id="STU-2024-302", email="jordan.taylor@university.edu", role="student")
  if token.startswith("mock-") or token.startswith("dev-"):
      role = "admin" if "admin" in token else ("faculty" if "faculty" in token else "student")
      ...
  ```
- **Impact:** If `ENVIRONMENT` is omitted or misconfigured in production or staging, unauthenticated requests automatically gain student access, and sending `Bearer dev-admin` grants complete administrative privileges. Furthermore, dummy IDs like `"STU-2024-302"` break PostgreSQL foreign keys referencing UUID `profiles.id`.

### Vulnerability 6: Insecure Role Trust via Client-Controlled `user_metadata` (High)
- **Location:** `backend/app/core/auth.py` line 70:
  ```python
  role = metadata.get("role") or (auth_user.user_metadata or {}).get("role") or "student"
  ```
- **Impact:** In Supabase Auth, `user_metadata` is writable by clients upon sign-up or profile update (`supabase.auth.updateUser({ data: { role: 'faculty' } })`). Only `app_metadata` or the server-controlled `public.profiles.role` table column is protected. Trusting `user_metadata` allows self-escalation to `faculty` or `admin`.

### Vulnerability 7: Insecure Unverified JWT Fallback (High)
- **Location:** `backend/app/core/auth.py` lines 81–85:
  ```python
  claims = jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])
  ```
- **Impact:** When Supabase client initialization fails or is absent in dev mode, the backend decodes any JWT without validating its cryptographic signature, accepting forged tokens.

### Vulnerability 8: Overly Permissive Row Level Security (RLS) in `console_setup.sql` (Medium)
- **Location:** `supabase/console_setup.sql` lines 289, 291, 300:
  ```sql
  create policy "faculty read api submissions" on public.submissions_v2 for select to authenticated using (public.api_is_faculty());
  create policy "faculty manage rubrics" on public.rubrics for all to authenticated using (public.api_is_faculty());
  ```
- **Impact:** Bypasses course-level boundary isolation. Any faculty account can select all rows in `submissions_v2` and mutate all rows in `rubrics`.

---

## 7. Proposed Authoritative Database Schema

To satisfy the Day 1 requirements without breaking the application, we design **one unified authoritative schema** that merges the strengths of Schema 1 (relational integrity, UUIDs, curriculum DAG, mastery) and Schema 2 (rubric criteria, evaluations, queue status, faculty overrides).

### 7.1 Unified Entity Architecture

1. **`profiles` (Identity):**
   - Retained as the authoritative user record, populated via Supabase `on_auth_user_created` trigger.
   - Primary key: `id UUID` referencing `auth.users(id)`.
   - Columns: `id`, `email`, `full_name`, `role` (`student` or `faculty`), `created_at`.
2. **`courses` & `enrollments` (Academic Structure):**
   - `courses`: `id UUID PK`, `code TEXT UNIQUE` (e.g. `'CS101'`), `name TEXT`, `faculty_id UUID references profiles(id)`.
   - `enrollments`: `course_id UUID`, `student_id UUID`, composite PK `(course_id, student_id)`.
3. **`concepts` & `concept_edges` (Knowledge Graph):**
   - `concepts`: `id UUID PK`, `course_id UUID references courses(id)`, `name TEXT`, `description TEXT`, `pos_x`, `pos_y`.
   - `concept_edges`: `id UUID PK`, `course_id UUID`, `from_concept UUID`, `to_concept UUID`.
   - **Cycle Prevention:** Enforced via a trigger `check_concept_edge_cycles()` that disallows any edge creating a cycle in the prerequisite DAG.
4. **`rubrics` & `rubric_criteria` (Assignment Rubrics):**
   - `rubrics`: `id TEXT PK`, `course_id UUID references courses(id)`, `course_code TEXT`, `assignment_title TEXT`, `description TEXT`, `total_points NUMERIC`, `created_at TIMESTAMPTZ`.
   - `rubric_criteria`: `id TEXT PK`, `rubric_id TEXT references rubrics(id)`, `title TEXT`, `description TEXT`, `max_points NUMERIC`, `weight_percent NUMERIC`, `order_index INT`.
5. **`assignments` & `assignment_concepts` (Curriculum Assignments):**
   - `assignments`: `id UUID PK`, `course_id UUID references courses(id)`, `rubric_id TEXT references rubrics(id)`, `title TEXT`, `description TEXT`, `due_date TIMESTAMPTZ`.
   - `assignment_concepts`: `assignment_id UUID`, `concept_id UUID`, composite PK `(assignment_id, concept_id)`.
   - **Course Match Constraint:** Enforced via trigger `check_assignment_concept_course_match()` ensuring concept and assignment belong to the identical course.
6. **`submissions` (Authoritative Submissions Model):**
   - Unifies `public.submissions` and `public.submissions_v2`.
   - `id UUID PK default gen_random_uuid()` (with backward compatibility view `submissions_v2`).
   - `assignment_id UUID references assignments(id) on delete cascade`.
   - `student_id UUID not null references profiles(id) on delete cascade` (authoritative identity).
   - `course_id UUID references courses(id) on delete cascade`.
   - `rubric_id TEXT references rubrics(id) on delete set null`.
   - File fields: `file_path TEXT`, `file_name TEXT`, `file_size TEXT`, `file_type TEXT`, `file_url TEXT`, `content_preview TEXT`.
   - Lifecycle status: `status TEXT check (status in ('pending', 'processing', 'graded', 'done', 'failed', 'flagged'))`.
   - `processing_step TEXT check (processing_step in ('queued', 'extracting', 'grading', 'synced'))`.
   - Execution & Grading metadata: `attempts INT default 1`, `processing_started_at TIMESTAMPTZ`, `overall_score NUMERIC`, `feedback_summary TEXT`, `error_message TEXT`, `is_late BOOLEAN default false`.
   - Timestamps: `submitted_at TIMESTAMPTZ default now()`, `created_at TIMESTAMPTZ default now()`, `updated_at TIMESTAMPTZ default now()`.
   - **Resubmission Policy:** For the MVP, `UNIQUE (assignment_id, student_id)` enforces one active submission per student per assignment.
7. **`grading_jobs` (Queue Processing):**
   - `id UUID PK default gen_random_uuid()`.
   - `submission_id UUID not null references submissions(id) on delete cascade`.
   - `status TEXT check (status in ('pending', 'processing', 'done', 'failed', 'flagged'))`.
   - `retry_count INT default 0`, `error_log TEXT`, `started_at`, `completed_at`.
8. **`evaluations` & `criterion_evaluations` (AI Evaluation):**
   - `evaluations`: `id UUID PK`, `submission_id UUID not null unique references submissions(id) on delete cascade`. Stores `score`, `max_score`, `percentage`, `summary_feedback`, `strengths (JSONB)`, `improvements (JSONB)`, `ai_model_extraction`, `ai_model_grading`, `evaluated_at`.
   - `criterion_evaluations`: `id UUID PK`, `evaluation_id UUID not null references evaluations(id) on delete cascade`. Stores `criterion_id`, `title`, `score_awarded`, `max_points`, `feedback`, `strengths`, `improvements`.
9. **`submission_concept_feedback` & `student_concept_mastery` (Learning Progress):**
   - `submission_concept_feedback`: `id UUID PK`, `submission_id UUID references submissions(id)`, `concept_id UUID references concepts(id)`, `mastery_percentage NUMERIC`, `feedback_text TEXT`.
   - `student_concept_mastery`: `id UUID PK`, `student_id UUID references profiles(id)`, `concept_id UUID references concepts(id)`, `submission_id UUID references submissions(id)`, `mastery_percentage NUMERIC`, `source TEXT check (source in ('ai', 'faculty_override'))`.
   - **Mastery Assumption:** Assignment marks are evidence inputs, not raw mastery percentages. Mastery is calculated independently from rubric criteria and weighted by assignment concept coverage.
10. **`faculty_overrides` (Human Oversight & Audit):**
    - `id UUID PK default gen_random_uuid()`.
    - `submission_id UUID not null references submissions(id) on delete cascade`.
    - `is_overridden BOOLEAN default true`.
    - `original_score NUMERIC not null`, `overridden_score NUMERIC not null`.
    - `overridden_by UUID not null references profiles(id)` (authenticated faculty UUID).
    - `overridden_by_name TEXT not null` (display name for convenience).
    - `override_reason TEXT not null`.
    - `criterion_adjustments JSONB`.
    - `overridden_at TIMESTAMPTZ default now()`.

---

## 8. Migration and Compatibility Plan

### 8.1 Migration Steps

1. **Migration `03_authoritative_schema.up.sql`:**
   - Ensure `courses`, `enrollments`, `concepts`, `concept_edges`, `rubrics`, `rubric_criteria` exist with unified columns and foreign keys.
   - Consolidate `submissions` table to contain all required columns from both `submissions` and `submissions_v2`.
   - Point `grading_jobs.submission_id`, `evaluations.submission_id`, and `faculty_overrides.submission_id` to `submissions(id)`.
   - Create updatable compatibility view `public.submissions_v2` over `public.submissions` so existing Next.js frontend and legacy callers do not break.
   - Implement trigger functions:
     - `check_concept_edge_cycles()`: Prevents cycles in concept DAG.
     - `check_assignment_concept_course_match()`: Enforces course boundary on assignment concepts.
     - `set_updated_at()`: Automatically refreshes `updated_at` timestamps.
2. **Migration `04_rls_security_hardening.up.sql`:**
   - Drop insecure broad RLS policies.
   - Re-implement hardened RLS policies:
     - Students can read ONLY their own submissions, evaluations, feedback, and mastery records.
     - Students can view courses only when enrolled or course is public.
     - Faculty can view and mutate ONLY courses, rubrics, submissions, and overrides where `public.owns_course(course_id)` is TRUE.
     - Pin `search_path = public, auth` on all `SECURITY DEFINER` functions.
3. **Backend Compatibility Layer (`backend/app/`):**
   - Update `app/core/auth.py`:
     - Secure `get_current_user` to derive student/faculty identity strictly from authenticated Supabase JWT.
     - Read role strictly from `app_metadata.role` or `profiles.role` table, NEVER from mutable `user_metadata`.
     - Disable insecure mock tokens in production (`if settings.ENVIRONMENT != "development"`).
   - Update `app/routers/uploads.py`:
     - Bind `student_id` strictly to `user.id`.
     - Reject student attempts to submit on behalf of other users.
   - Update `app/routers/grades.py`:
     - Bind `overriddenBy` strictly to authenticated faculty identity (`user.id` / `user.email`).
     - Check course authorization (`owns_course`) before allowing grade overrides or rubric mutations.
   - Update `app/services/repository.py`:
     - Direct all submission queries to the authoritative `submissions` table (with fallback handling for `submissions_v2`).

---

*This document serves as the architectural foundation for Day 1 execution. Schema diagrams and migration definitions follow in `docs/DAY1_SCHEMA.md` and `supabase/migrations/`.*
