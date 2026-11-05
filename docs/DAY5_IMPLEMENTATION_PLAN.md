# DAY 5 IMPLEMENTATION PLAN: STUDENT INDIVIDUALIZED KNOWLEDGE GRAPH

**Project**: Human-AI Co-Learning Agent (EduAgents)  
**Author**: Senior Full-Stack Architect, Supabase/PostgreSQL Database Security Engineer  
**Status**: APPROVED FOR EXECUTION  
**Target Completion**: Day 5 Deliverables  

---

## 1. Product Objective & Core Principles

The central objective of Day 5 is to display the faculty-defined canonical curriculum DAG as an **individualized student learning graph**.

### The Cardinal Architectural Rule
$$\mathbf{\text{ONE CANONICAL CURRICULUM GRAPH}} + \mathbf{\text{STUDENT-SPECIFIC LEARNING DATA}}$$
- Concepts and prerequisite relationships (DAG edges) exist **once** per course.
- **Never** create separate copies of concepts or prerequisite relationships for individual students.
- The student learning graph is an overlay: canonical course DAG structure joined with student-specific mastery, confidence, and genuine evaluation evidence.
- Two students in the same course see the exact same curriculum structure, but distinctly different mastery states and evidence.

### The Three Critical Product Tenets
1. **All Concepts Displayed**: The graph renders every canonical curriculum concept, including concepts the student has never attempted. Missing mastery strictly means **UNASSESSED** (`None` / neutral slate), never zero mastery.
2. **Genuine Evaluation Evidence**: Clicking any concept reveals real evaluation evidence (from `submission_concept_feedback`, `evaluations`, and `faculty_overrides`), never fabricated mock text.
3. **Provable Individualization**: Multiple students enrolled in the same course inspect the same curriculum DAG layout with individualized mastery and evidence.

---

## 2. Audit of Existing System & Reusable Components

### Backend Components
- `backend/app/models/curriculum.py`: `Concept`, `ConceptEdge`, `CurriculumGraph` (canonical course structure).
- `backend/app/models/mastery.py`: `StudentConceptMastery` ($0.0 \le M \le 1.0, 0.0 \le c \le 1.0$).
- `backend/app/models/evaluation.py`: `ConceptFeedback`, `CriterionEvaluation`, `FacultyOverride`.
- `backend/app/routers/students.py`: `GET /api/v1/students/courses/{course_id}/curriculum`.
  - *Audit Finding*: Currently sets unassessed concepts to $M=0.0, c=0.0$ instead of `null`! Needs fix to distinguish unassessed from low mastery ($0.00 - 0.39$). Needs enrollment check for students and ownership check for faculty.
- `backend/app/services/repository.py`:
  - `get_curriculum_graph(course_id)`: Fetches canonical concepts and edges.
  - `get_student_mastery(student_id)`: Fetches mastery records.
  - `is_student_enrolled(course_id, student_id)`: Checks course enrollment.
  - `is_course_owner_by_id(course_id, faculty_user)`: Checks course ownership.
  - `submission_concept_feedback`: Authoritative evidence ledger storing criterion-level score ratios, confidences, feedback, and verbatim evidence excerpts.

### Frontend Components
- `@xyflow/react` (React Flow 12): Installed and verified in `CurriculumCanvas.tsx`.
- `frontend/components/CurriculumNode.tsx`: Reusable node with category, difficulty, and handles.
- `frontend/app/faculty/courses/[courseId]/curriculum/page.tsx`: Existing faculty curriculum DAG builder.
- `frontend/app/student/page.tsx`: Existing student workspace.
- `frontend/lib/storage.ts` & `frontend/lib/api.ts`: Centralized client with JWT auth headers.

---

## 3. Backend Implementation Specification

### 3.1 Endpoint 1: Student Individualized Curriculum Graph
`GET /api/v1/students/courses/{course_id}/curriculum`

#### Authentication & Authorization
- Identity is derived strictly from the authenticated session (`get_current_user`).
- If caller is a `student`:
  - `student_id` query param is ignored or rejected if different from `user.id`.
  - Must be enrolled in `course_id`; non-enrolled students receive `403 FORBIDDEN`.
- If caller is `faculty` or `admin`:
  - Caller may pass `?student_id=<enrolled_student_id>`.
  - Faculty member must own `course_id`; unauthorized faculty receive `403 FORBIDDEN`.
  - Target student must be enrolled in `course_id`; unenrolled student returns `404 NOT_FOUND`.

#### Response Payload Structure (`StudentCurriculumGraph`)
```json
{
  "courseId": "c1010000-0000-0000-0000-000000000001",
  "courseCode": "CS101",
  "courseName": "Data Structures & Algorithms",
  "courseDescription": "Core CS curriculum",
  "studentId": "student-uuid",
  "studentName": "Alex Student",
  "concepts": [
    {
      "id": "c0000000-0000-0000-0000-000000000001",
      "conceptId": "c0000000-0000-0000-0000-000000000001",
      "name": "Dynamic Programming",
      "description": "Optimal substructure and memoization",
      "category": "Algorithms",
      "difficulty": "intermediate",
      "posX": 250.0,
      "posY": 180.0,
      
      "masteryScore": 0.85,
      "masteryPercentage": 85.0,
      "confidenceScore": 0.80,
      "evidenceCount": 2,
      "masterySource": "ai",
      "lastEvaluatedAt": "2026-11-05T00:00:00Z",
      "status": "strong",
      
      "feedback": {
        "recentFeedback": "Flawless recurrence relation and DP table formulation.",
        "evidenceExcerpts": ["dp = [[0] * (w + 1) for _ in range(n + 1)]"],
        "relatedCriterionIds": ["crit-dp-1"],
        "associatedAssignmentIds": ["assign-1"],
        "associatedAssignments": [
          {
            "id": "assign-1",
            "title": "DP Assignment 1",
            "submittedAt": "2026-11-05T00:00:00Z"
          }
        ],
        "history": [
          {
            "submissionId": "sub-101",
            "assignmentId": "assign-1",
            "assignmentTitle": "DP Assignment 1",
            "criterionId": "crit-dp-1",
            "scoreRatio": 0.85,
            "confidence": 0.80,
            "feedbackText": "Flawless recurrence relation.",
            "evidence": "dp = [[0] * (w + 1) for _ in range(n + 1)]",
            "evaluatedAt": "2026-11-05T00:00:00Z",
            "source": "ai"
          }
        ]
      }
    }
  ],
  "edges": [
    {
      "id": "edge-1",
      "fromConcept": "c0000000-0000-0000-0000-000000000000",
      "toConcept": "c0000000-0000-0000-0000-000000000001",
      "sourceConceptId": "c0000000-0000-0000-0000-000000000000",
      "targetConceptId": "c0000000-0000-0000-0000-000000000001"
    }
  ]
}
```

#### Mastery State Mapping
| State | Score Range | Status Code | UI Treatment |
|---|---|---|---|
| **UNASSESSED** | `null` (no evidence) | `"unassessed"` | Neutral slate, dashed outline, badge "Unassessed" |
| **LOW MASTERY** | $0.00 \le M \le 0.39$ | `"low_mastery"` | Rose/Red indicator, badge "Needs Attention" |
| **DEVELOPING** | $0.40 \le M \le 0.69$ | `"developing"` | Amber/Orange indicator, badge "Developing" |
| **STRONG** | $0.70 \le M \le 0.89$ | `"strong"` | Emerald/Green indicator, badge "Strong" |
| **HIGH** | $0.90 \le M \le 1.00$ | `"high"` | Blue/Indigo indicator, badge "Mastered" |

Confidence is strictly reported separately as $c \in [0.0, 1.0]$ with sample count $N \ge 0$.

---

### 3.2 Endpoint 2: Faculty Enrolled Students List
`GET /api/v1/faculty/courses/{course_id}/students`
- Verifies faculty ownership of `course_id`.
- Returns all students enrolled in the course with enrollment timestamp, profile details, and mastery progress summary.

---

## 4. Frontend Graph Visualization Architecture

### 4.1 Student Knowledge Graph Component (`StudentKnowledgeGraph.tsx`)
- Read-only React Flow canvas:
  - Disables node dragging (or enables pan without modifying backend positions).
  - Background grid (`BackgroundVariant.Dots`).
  - Navigation controls (`Controls`, `MiniMap`).
  - Fit-view button (`fitView({ padding: 0.2 })`).
- Visual Custom Node (`StudentLearningNode.tsx`):
  - Category and difficulty headers.
  - Concept title and description.
  - Prominent mastery badge with explicit color coding for the 5 states.
  - Explicit confidence meter ($0 - 100\%$) displayed separately from mastery score.
  - Evidence count indicator ($N$ evaluations).
  - Clickable node surface opening the Concept Detail Panel.

### 4.2 Interactive Graph Filtering
- **Status Filter**: `All` | `Assessed Only` | `Unassessed` | `Low Mastery` | `Developing` | `Strong` | `High`
- **Category Filter**: Dynamically extracted unique categories.
- **Search Query**: Real-time filtering by concept name.
- Non-matching nodes are styled with reduced opacity ($0.2$) while preserving DAG prerequisite continuity.

### 4.3 Concept Detail Slide-Over Panel (`ConceptDetailPanel.tsx`)
- Triggered by clicking any node in the graph.
- **Section 1: Overview**:
  - Concept Name, Category, Difficulty badge.
  - Current Mastery percentage with state badge.
  - Confidence percentage with explanation.
  - Evidence count and mastery source (AI Evaluation vs Faculty Override).
- **Section 2: Genuine Evaluation Evidence**:
  - Recent feedback text.
  - Verbatim code/text excerpts from student submissions.
  - Associated assignment name, due date, and submitted timestamp.
  - Criterion-level scores ($s_k / w_k$).
- **Section 3: Evaluation History**:
  - Chronological timeline of evaluations from `submission_concept_feedback`.
  - Distinguishes initial AI assessments from faculty overrides.
  - If unassessed: Displays pedagogical prerequisite advice and relevant upcoming assignments.

---

## 5. Real-Time Synchronization & Safety

### Realtime Subscription Setup
- Channel: `student-learning-graph-{studentId}-{courseId}`
- Subscribed Tables:
  - `student_concept_mastery` filtered by `student_id=eq.{studentId}`
  - `submission_concept_feedback` filtered by `student_id=eq.{studentId}`
  - `faculty_overrides`
- Upon event reception: Refresh student curriculum graph cleanly without page reload.
- Unsubscribe and clean up on component unmount to prevent memory leaks.
- Manual "Refresh Graph" fallback button with loading spinner.

---

## 6. Faculty Student Progress View

### Faculty Route: `/faculty/courses/[courseId]/students`
- Course selection dropdown.
- Student selection picker: Lists all enrolled students with quick summary chips.
- Renders the exact same `StudentKnowledgeGraph` canvas with the selected student's data.
- Allows faculty to inspect any student's concept-level mastery and evidence.
- Demonstrates provable individualization: switching between Student A and Student B renders the exact same DAG layout with different node colors and evidence.

---

## 7. Testing & Verification Plan

### Backend Unit & Integration Tests (`test_student_knowledge_graph.py`)
1. **Canonical Concept Completeness**: All course concepts are returned, including those with no mastery record.
2. **Unassessed vs Zero Mastery**: Unassessed concepts return `masteryScore: null, status: "unassessed"`.
3. **Mastery Individualization**: Enrolling Student 1 and Student 2 in the same course yields identical concept DAG structure, but different mastery scores.
4. **Evidence Attribution**: Feedback excerpts belong strictly to the authenticated student; no leakage across students.
5. **Security & Enrollment Enforcement**: Unenrolled student request returns `403 Forbidden`.
6. **Cross-Course Isolation**: Accessing concepts from another course is rejected.
7. **Faculty Course Ownership**: Faculty can view enrolled students for owned courses, rejected for other faculty courses.
8. **Live PostgreSQL Physical Verification**: Direct SQL queries validating student mastery joins and foreign keys.

### Frontend Verification
- TypeScript strict compiler check (`npx tsc --noEmit`).
- Production build verification (`npm run build`).

---

## 8. Execution Milestones

- [ ] **Milestone 1**: Implement backend models, repository join queries, and router endpoints for student curriculum graph and faculty students list.
- [ ] **Milestone 2**: Write comprehensive backend tests and verify 100% pass rate.
- [ ] **Milestone 3**: Build frontend components (`StudentKnowledgeGraph`, `StudentLearningNode`, `ConceptDetailPanel`, `GraphFilters`).
- [ ] **Milestone 4**: Integrate student knowledge graph into `/student` and create faculty progress view in `/faculty/courses/[courseId]/students`.
- [ ] **Milestone 5**: Verify real-time updates, TypeScript compilation, and produce `docs/DAY5_EXECUTION_REPORT.md`.
