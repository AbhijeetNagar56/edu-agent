# Day 6 Implementation Plan: Faculty Review, Overrides & Learning Analytics

**Project**: Human-AI Co-Learning Agent (EduAgents)  
**Author**: Senior Full-Stack Architect, Supabase/PostgreSQL Database Engineer, and Security Reviewer  
**Status**: In Progress (Day 6)

---

## 1. Architectural Baseline & Audit Findings

### 1.1 Existing Functionality Reused
1. **Authoritative Submissions**:
   - `public.submissions` stores primary submission documents, statuses, and links to evaluations and overrides.
   - Statuses: `pending`, `processing`, `done`, `failed`, `flagged`, `manual_review`.
2. **Authoritative Criterion-to-Concept Mappings**:
   - `public.assignment_criterion_concepts` connects rubric criteria to canonical course concepts.
3. **Mastery Recomputation Engine**:
   - `Repository.recompute_student_concept_mastery` and `Repository.record_concept_evidence_and_update_mastery` (from Day 4) provide order-independent, idempotent mastery recomputation from `submission_concept_feedback`.
   - `Repository.has_active_faculty_override` ensures that active overrides are preserved against worker retries.
4. **Canonical Curriculum DAG**:
   - Exactly one canonical DAG per course (`concepts` and `concept_edges`).
5. **Student Knowledge Graph**:
   - Read-only student mastery visualization over the canonical DAG with genuine evidence citations.
6. **Existing Submission Overrides**:
   - `faculty_overrides` table logs submission score overrides, `criterion_adjustments JSONB`, `overridden_by` UUID, `overridden_by_name`, and `override_reason`.
   - `POST /api/v1/faculty/submissions/{id}/override` derives faculty identity securely from authenticated JWT session.

### 1.2 Identified Architectural Gaps
1. **Review Queue Enhancements**:
   - Needs assignment-specific filtering in the faculty submissions list.
   - Needs explicit filter for `manual_review` and `failed` submissions.
   - Needs clear pagination and total count metadata for large rosters.
2. **Override Workflow Gaps**:
   - No explicit endpoint to remove an override (`DELETE /api/v1/faculty/submissions/{id}/override`) and restore AI-derived mastery.
   - When criterion-level adjustments (`criterionAdjustments`) are submitted, criterion score ratios in `submission_concept_feedback` should be updated transactionally, followed by mastery recalculation.
   - The database schema for `faculty_overrides` currently mandates `submission_id NOT NULL`, preventing direct concept-level mastery overrides outside a submission context.
3. **Missing Learning Analytics**:
   - No dedicated course-level learning analytics API endpoint.
   - No structured analytics models aggregating course metrics, concept mastery distributions, student progress rosters, and assignment performance.
   - No dedicated faculty analytics dashboard page in the Next.js frontend.

---

## 2. Implementation Architecture

### Phase A: Database Schema Evolution (`supabase/migrations/08_faculty_overrides_and_analytics.up.sql`)
1. Evolve `public.faculty_overrides`:
   - Make `submission_id` nullable (`DROP NOT NULL`) to support concept-level overrides.
   - Add `target_type VARCHAR(32) NOT NULL DEFAULT 'submission' CHECK (target_type IN ('submission', 'concept_mastery'))`.
   - Add `concept_id UUID REFERENCES public.concepts(id) ON DELETE CASCADE`.
   - Add `student_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE`.
   - Add indices: `idx_faculty_overrides_concept` and `idx_faculty_overrides_student`.
2. Post-migration verification assertions in SQL to verify zero schema regressions.

### Phase B: Faculty Submission Review Queue
1. **API Enhancements**:
   - Update `GET /api/v1/faculty/submissions` to support `assignment_id` query parameter alongside `course_code`, `status`, and `search`.
   - Support `status = 'manual_review'` filter.
2. **Frontend Review Queue**:
   - In `frontend/app/faculty/page.tsx`:
     - Add assignment selector dropdown filtered by the selected course.
     - Add status filter pills: All, Manual Review, Pending/Processing, Completed/Done, Faculty Overridden.
     - Add badge distinguishing AI Grade vs Faculty Overridden Grade.

### Phase C: Detailed AI Evaluation Inspection
1. Update `frontend/components/GradeDetailModal.tsx`:
   - **Overall AI Evaluation**: AI-generated score, maximum score, evaluation summary, Gemini model identifier (`Gemini Flash-Lite` extraction, `Gemini Flash` grading), evaluation timestamp.
   - **Criterion-level Evaluation**: Title, max points, awarded points, verbatim evidence extracted from student work, AI reasoning, feedback, and mapped concepts.
   - **Concept-level Learning Evidence**: Associated concepts, evidence score ratio, confidence score, student mastery status, and faculty override state.
   - Clearly distinguish AI-generated scores and feedback from faculty decisions with distinct colored badges and icons.

### Phase D: Human-in-the-Loop Override Workflow
1. **Distinct Override Operations**:
   - **Operation 1 (Overall Score Override)**: Modifies submission total score with audit justification.
   - **Operation 2 (Criterion Score Adjustments)**: Adjusts individual rubric criteria. Updates `submission_concept_feedback` score ratios for mapped concepts and recomputes student mastery.
   - **Operation 3 (Override Removal)**: Reverts `is_overridden` to `false`, updates `faculty_overrides` audit trail, and recomputes mastery from authoritative AI evidence.
   - **Operation 4 (Direct Concept Mastery Override)**: Directly overrides a concept's mastery score in `student_concept_mastery` with `source = 'faculty_override'`, logging an audit record in `faculty_overrides`.
2. **Mastery Engine Integration**:
   - Active overrides take precedence over worker evaluations.
   - Removal of an override executes `Repository.recompute_student_concept_mastery` to restore pure AI mastery from `submission_concept_feedback`.
   - Mandatory non-empty reason required on all override operations.

### Phase E: Course-Level Learning Analytics Engine
1. **Pydantic Response Models** (`backend/app/models/analytics.py`):
   - `CourseOverviewAnalytics`: Enrolled students, total assignments, published/draft breakdown, total submissions, completed evaluations, pending evaluations, manual review count, class average score, concept assessment coverage.
   - `StudentProgressSummary`: Student ID, name, email, assessed concepts count, total concepts, coverage percentage, average mastery (assessed concepts only; unassessed strictly excluded), low mastery count, developing count, strong/high count, unassessed count.
   - `ConceptAnalyticsSummary`: Concept ID, name, category, difficulty, assessed students count, unassessed students count, average mastery, low mastery count, developing count, strong/high count, needs attention flag.
   - `AssignmentAnalyticsSummary`: Assignment ID, title, due date, max marks, status, submission count, completion rate, average score, score distribution buckets (`<60`, `60-69`, `70-79`, `80-89`, `90-100`), manual review count.
   - `CourseLearningAnalytics`: Complete typed payload combining all four sections.
2. **Repository Calculation Method**:
   - `Repository.get_course_learning_analytics(course_id, faculty_user)`:
     - Verifies course authorization.
     - Gathers real persisted data from `courses`, `enrollments`, `concepts`, `assignments`, `submissions`, `student_concept_mastery`, and `submission_concept_feedback`.
     - Strictly excludes unassessed concepts from average mastery calculations.
3. **Endpoint**:
   - `GET /api/v1/faculty/courses/{course_id}/analytics` in `backend/app/routers/faculty_courses.py`.

### Phase F: Visual Analytics Dashboard
1. Dedicated route: `frontend/app/faculty/courses/[courseId]/analytics/page.tsx`.
2. Features:
   - Header with course breadcrumb navigation (Curriculum, Assignments, Students, Analytics).
   - Overview StatCards (Enrolled Students, Submissions, Evaluation Completion %, Class Avg Score, Concept Coverage %).
   - Attention Alert Banner for concepts with low mastery or low coverage.
   - Concept Mastery Distribution Chart (stacked bar / visual breakdown of Low, Developing, Strong/High).
   - Student Learning Progress Roster Table with search, sorting, and coverage progress bars.
   - Assignment Performance Cards with score distribution histogram bars.

### Phase G: Testing & Verification
1. Automated test suite in `backend/tests/test_faculty_review_analytics.py`:
   - Review queue course isolation and status filtering.
   - Override lifecycle: score correction, criterion adjustments, mandatory reason, audit trail preservation, override removal, and mastery restoration.
   - Analytics metrics accuracy: student counts, submission counts, average score calculation, unassessed concept exclusion from average mastery.
   - Course authorization & student access rejection (`403 FORBIDDEN`).
2. Run full test suite (`pytest backend/tests -v`).
3. Frontend TypeScript check (`npx tsc --noEmit`) and Turbopack production build (`npm run build`).
4. Visual UI screenshots for review queue and analytics dashboards.
5. Create `docs/DAY6_EXECUTION_REPORT.md`.

---

## 3. Work Breakdown & Execution Steps

1. **Step 1**: Create and apply Migration 08 (`supabase/migrations/08_faculty_overrides_and_analytics.up.sql`).
2. **Step 2**: Implement Analytics models in `backend/app/models/analytics.py`.
3. **Step 3**: Update Repository with override removal, criterion-adjustment evidence updates, direct concept mastery override, and course analytics computation.
4. **Step 4**: Implement backend routes in `backend/app/routers/faculty_courses.py` and `backend/app/routers/grades.py`.
5. **Step 5**: Write comprehensive automated tests in `backend/tests/test_faculty_review_analytics.py` and run full test suite.
6. **Step 6**: Update frontend types (`types.ts`) and API client (`storage.ts`).
7. **Step 7**: Update `GradeDetailModal.tsx` and `OverrideModal.tsx` to support criterion adjustments and override removal.
8. **Step 8**: Build `frontend/app/faculty/courses/[courseId]/analytics/page.tsx` and link in Faculty navigation.
9. **Step 9**: Verify frontend compilation (`npx tsc --noEmit`) and build (`npm run build`).
10. **Step 10**: Capture visual UI screenshots and write `docs/DAY6_EXECUTION_REPORT.md`.
