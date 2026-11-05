from app.models.analytics import (
    CourseOverviewAnalytics,
    StudentProgressSummary,
    ConceptAnalyticsSummary,
    AssignmentAnalyticsSummary,
    CourseLearningAnalytics,
)
from fastapi import status
from app.core.errors import APIException
import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.logging import logger
from app.models.common import JobStatus, ProcessingStep
from app.models.evaluation import EvaluationResult, FacultyOverride, ConceptFeedback, CriterionEvaluation
from app.models.health import QueueStats
from app.models.job import GradingJob
from app.models.rubric import Rubric, RubricCriterion, RubricUpdate
from app.models.submission import Submission
from app.models.assignment import (
    Assignment,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentStatus,
    CriterionConceptMap,
    StudentAssignment,
)
from app.models.course import Course, CourseCreate, CourseUpdate
from app.models.curriculum import (
    Concept,
    ConceptCreate,
    ConceptUpdate,
    ConceptEdge,
    ConceptEdgeCreate,
    CurriculumGraph,
    CurriculumSaveRequest,
    CurriculumPositionUpdate,
    StudentCurriculumConcept,
    StudentPrerequisiteEdge,
    StudentCurriculumGraph,
    ConceptFeedbackSummary,
    EvidenceHistoryItem,
    EnrolledStudentSummary,
)
from app.services.supabase_client import get_supabase_client, is_supabase_configured

# Default test faculty UUID
DEV_FACULTY_ID = "00000000-0000-0000-0000-000000000101"
DEV_STUDENT_ID = "00000000-0000-0000-0000-000000000302"
OTHER_FACULTY_ID = "00000000-0000-0000-0000-000000000999"

SEED_COURSES: List[Course] = [
    Course(
        id="c1010000-0000-0000-0000-000000000001",
        code="CS101",
        name="Introduction to Computer Science and Algorithms",
        description="Core algorithms, asymptotic complexity, sorting, and graph structures.",
        facultyId=DEV_FACULTY_ID,
        createdAt="2026-09-01T08:00:00Z",
        conceptsCount=6,
        assignmentsCount=2,
    ),
    Course(
        id="a3010000-0000-0000-0000-000000000002",
        code="AI301",
        name="Machine Learning and Neural Optimization",
        description="Mathematical foundations of machine learning, gradient methods, and deep neural architectures.",
        facultyId=DEV_FACULTY_ID,
        createdAt="2026-09-05T08:00:00Z",
        conceptsCount=3,
        assignmentsCount=1,
    ),
    Course(
        id="m2010000-0000-0000-0000-000000000003",
        code="MATH201",
        name="Discrete Mathematics and Logic",
        description="Formal proofs, propositional calculus, and discrete relations.",
        facultyId=OTHER_FACULTY_ID,
        createdAt="2026-09-10T08:00:00Z",
        conceptsCount=0,
        assignmentsCount=0,
    ),
]

SEED_CONCEPTS: List[Concept] = [
    Concept(
        id="c1010000-c001-0000-0000-000000000001",
        courseId="c1010000-0000-0000-0000-000000000001",
        name="Basic Programming Constructs",
        description="Variables, control flow, functions, and memory references.",
        category="Foundations",
        difficulty="beginner",
        posX=100.0,
        posY=220.0,
        createdAt="2026-09-02T09:00:00Z",
    ),
    Concept(
        id="c1010000-c002-0000-0000-000000000002",
        courseId="c1010000-0000-0000-0000-000000000001",
        name="Linear Data Structures",
        description="Dynamic arrays, linked lists, stacks, and queues.",
        category="Data Structures",
        difficulty="beginner",
        posX=360.0,
        posY=120.0,
        createdAt="2026-09-02T09:10:00Z",
    ),
    Concept(
        id="c1010000-c003-0000-0000-000000000003",
        courseId="c1010000-0000-0000-0000-000000000001",
        name="Asymptotic Analysis and Big-O",
        description="Time and space complexity bounds, best/average/worst case models.",
        category="Complexity Theory",
        difficulty="intermediate",
        posX=360.0,
        posY=320.0,
        createdAt="2026-09-02T09:20:00Z",
    ),
    Concept(
        id="c1010000-c004-0000-0000-000000000004",
        courseId="c1010000-0000-0000-0000-000000000001",
        name="Comparison Sorting Algorithms",
        description="MergeSort, QuickSort, and HeapSort implementation and empirical behavior.",
        category="Algorithms",
        difficulty="intermediate",
        posX=640.0,
        posY=120.0,
        createdAt="2026-09-02T09:30:00Z",
    ),
    Concept(
        id="c1010000-c005-0000-0000-000000000005",
        courseId="c1010000-0000-0000-0000-000000000001",
        name="Divide and Conquer Paradigms",
        description="Recursive recurrences, Master Theorem, and partitioning.",
        category="Algorithms",
        difficulty="intermediate",
        posX=640.0,
        posY=320.0,
        createdAt="2026-09-02T09:40:00Z",
    ),
    Concept(
        id="c1010000-c006-0000-0000-000000000006",
        courseId="c1010000-0000-0000-0000-000000000001",
        name="Graph Traversal and Shortest Paths",
        description="Adjacency graphs, BFS, DFS, Dijkstra, and priority queue min-heaps.",
        category="Advanced Algorithms",
        difficulty="advanced",
        posX=920.0,
        posY=220.0,
        createdAt="2026-09-02T09:50:00Z",
    ),
    Concept(
        id="a3010000-c001-0000-0000-000000000001",
        courseId="a3010000-0000-0000-0000-000000000002",
        name="Multivariate Calculus and Gradients",
        description="Partial derivatives, Jacobian matrices, and loss surfaces.",
        category="Mathematics",
        difficulty="beginner",
        posX=120.0,
        posY=200.0,
        createdAt="2026-09-06T10:00:00Z",
    ),
    Concept(
        id="a3010000-c002-0000-0000-000000000002",
        courseId="a3010000-0000-0000-0000-000000000002",
        name="Gradient Descent and Optimizers",
        description="Batch, Mini-batch, Momentum, and Adam convergence dynamics.",
        category="Optimization",
        difficulty="intermediate",
        posX=420.0,
        posY=200.0,
        createdAt="2026-09-06T10:10:00Z",
    ),
    Concept(
        id="a3010000-c003-0000-0000-000000000003",
        courseId="a3010000-0000-0000-0000-000000000002",
        name="Deep Neural Architectures",
        description="Layer composition, activation nonlinearities, and backpropagation.",
        category="Deep Learning",
        difficulty="advanced",
        posX=720.0,
        posY=200.0,
        createdAt="2026-09-06T10:20:00Z",
    ),
]

SEED_CONCEPT_EDGES: List[ConceptEdge] = [
    ConceptEdge(
        id="e1010000-0001-0000-0000-000000000001",
        courseId="c1010000-0000-0000-0000-000000000001",
        fromConcept="c1010000-c001-0000-0000-000000000001",
        toConcept="c1010000-c002-0000-0000-000000000002",
        createdAt="2026-09-02T10:00:00Z",
    ),
    ConceptEdge(
        id="e1010000-0002-0000-0000-000000000002",
        courseId="c1010000-0000-0000-0000-000000000001",
        fromConcept="c1010000-c001-0000-0000-000000000001",
        toConcept="c1010000-c003-0000-0000-000000000003",
        createdAt="2026-09-02T10:05:00Z",
    ),
    ConceptEdge(
        id="e1010000-0003-0000-0000-000000000003",
        courseId="c1010000-0000-0000-0000-000000000001",
        fromConcept="c1010000-c002-0000-0000-000000000002",
        toConcept="c1010000-c004-0000-0000-000000000004",
        createdAt="2026-09-02T10:10:00Z",
    ),
    ConceptEdge(
        id="e1010000-0004-0000-0000-000000000004",
        courseId="c1010000-0000-0000-0000-000000000001",
        fromConcept="c1010000-c003-0000-0000-000000000003",
        toConcept="c1010000-c005-0000-0000-000000000005",
        createdAt="2026-09-02T10:15:00Z",
    ),
    ConceptEdge(
        id="e1010000-0005-0000-0000-000000000005",
        courseId="c1010000-0000-0000-0000-000000000001",
        fromConcept="c1010000-c004-0000-0000-000000000004",
        toConcept="c1010000-c006-0000-0000-000000000006",
        createdAt="2026-09-02T10:20:00Z",
    ),
    ConceptEdge(
        id="e1010000-0006-0000-0000-000000000006",
        courseId="c1010000-0000-0000-0000-000000000001",
        fromConcept="c1010000-c005-0000-0000-000000000005",
        toConcept="c1010000-c006-0000-0000-000000000006",
        createdAt="2026-09-02T10:25:00Z",
    ),
    ConceptEdge(
        id="e3010000-0001-0000-0000-000000000001",
        courseId="a3010000-0000-0000-0000-000000000002",
        fromConcept="a3010000-c001-0000-0000-000000000001",
        toConcept="a3010000-c002-0000-0000-000000000002",
        createdAt="2026-09-06T11:00:00Z",
    ),
    ConceptEdge(
        id="e3010000-0002-0000-0000-000000000002",
        courseId="a3010000-0000-0000-0000-000000000002",
        fromConcept="a3010000-c002-0000-0000-000000000002",
        toConcept="a3010000-c003-0000-0000-000000000003",
        createdAt="2026-09-06T11:05:00Z",
    ),
]


SEED_ASSIGNMENTS: List[Assignment] = [
    Assignment(
        id="assign-1",
        courseId="c1010000-0000-0000-0000-000000000001",
        title="Assignment 1: Sorting Algorithms & Complexity",
        description="Implement and empirically benchmark QuickSort, MergeSort, and HeapSort. Formally analyze asymptotic time and space bounds.",
        dueDate="2026-11-20T23:59:59Z",
        maxPoints=100.0,
        status="published",
        rubricId="rubric-1",
        createdBy=DEV_FACULTY_ID,
        createdAt="2026-09-15T08:00:00Z",
        conceptIds=[
            "c1010000-c001-0000-0000-000000000001",
            "c1010000-c002-0000-0000-000000000002",
            "c1010000-c003-0000-0000-000000000003",
            "c1010000-c004-0000-0000-000000000004",
        ],
        criterionConcepts=[
            CriterionConceptMap(criterionId="crit-1", conceptId="c1010000-c004-0000-0000-000000000004", conceptName="Divide-and-Conquer Sorting"),
            CriterionConceptMap(criterionId="crit-2", conceptId="c1010000-c003-0000-0000-000000000003", conceptName="Asymptotic Analysis and Big-O"),
        ],
        submissionsCount=3,
    ),
    Assignment(
        id="assign-2",
        courseId="c1010000-0000-0000-0000-000000000001",
        title="Assignment 2: Graph Traversal & Dijkstra",
        description="Implement graph adjacency list, binary min-heap, and Dijkstra shortest path algorithm with edge case handling.",
        dueDate="2026-12-01T23:59:59Z",
        maxPoints=100.0,
        status="published",
        rubricId="rubric-2",
        createdBy=DEV_FACULTY_ID,
        createdAt="2026-09-20T08:00:00Z",
        conceptIds=[
            "c1010000-c005-0000-0000-000000000005",
            "c1010000-c006-0000-0000-000000000006",
        ],
        criterionConcepts=[
            CriterionConceptMap(criterionId="crit-2-1", conceptId="c1010000-c005-0000-0000-000000000005", conceptName="Graph Traversal & BFS/DFS"),
            CriterionConceptMap(criterionId="crit-2-2", conceptId="c1010000-c006-0000-0000-000000000006", conceptName="Shortest Paths & Greedy Algorithms"),
        ],
        submissionsCount=0,
    ),
    Assignment(
        id="assign-3",
        courseId="a3010000-0000-0000-0000-000000000002",
        title="Lab 3: Gradient Descent Optimization Report",
        description="Explore convergence properties of SGD, Momentum, and Adam on convex and non-convex surfaces.",
        dueDate="2026-11-25T23:59:59Z",
        maxPoints=100.0,
        status="published",
        rubricId="rubric-3",
        createdBy=DEV_FACULTY_ID,
        createdAt="2026-09-25T08:00:00Z",
        conceptIds=[
            "a3010000-c001-0000-0000-000000000001",
            "a3010000-c002-0000-0000-000000000002",
        ],
        criterionConcepts=[
            CriterionConceptMap(criterionId="crit-3-1", conceptId="a3010000-c001-0000-0000-000000000001", conceptName="Loss Functions & Convexity"),
            CriterionConceptMap(criterionId="crit-3-2", conceptId="a3010000-c002-0000-0000-000000000002", conceptName="Gradient Descent Variants"),
        ],
        submissionsCount=1,
    ),
    Assignment(
        id="assign-draft-1",
        courseId="c1010000-0000-0000-0000-000000000001",
        title="Assignment 3: Dynamic Programming (Draft)",
        description="Upcoming assignment on memoization and tabular dynamic programming.",
        dueDate="2026-12-15T23:59:59Z",
        maxPoints=100.0,
        status="draft",
        rubricId=None,
        createdBy=DEV_FACULTY_ID,
        createdAt="2026-10-01T08:00:00Z",
        conceptIds=[],
        criterionConcepts=[],
        submissionsCount=0,
    ),
]

SEED_ENROLLMENTS: List[Dict[str, str]] = [
    {"course_id": "c1010000-0000-0000-0000-000000000001", "student_id": DEV_STUDENT_ID},
    {"course_id": "a3010000-0000-0000-0000-000000000002", "student_id": DEV_STUDENT_ID},
]

SEED_RUBRICS: List[Rubric] = [
    Rubric(
        id="rubric-1",
        courseCode="CS101",
        assignmentTitle="Assignment 1: Sorting Algorithms & Complexity",
        description="Evaluation criteria for empirical sorting analysis and time complexity justifications.",
        totalPoints=100.0,
        createdAt="2026-10-01",
        criteria=[
            RubricCriterion(
                id="crit-1",
                title="Algorithm Correctness & Implementation",
                description="Implements QuickSort, MergeSort, and HeapSort correctly with optimal boundary handling.",
                maxPoints=35.0,
            ),
            RubricCriterion(
                id="crit-2",
                title="Theoretical Time & Space Complexity",
                description="Rigorous Big-O derivation for best, average, and worst-case scenarios.",
                maxPoints=25.0,
            ),
            RubricCriterion(
                id="crit-3",
                title="Empirical Benchmark Analysis",
                description="Plots runtime against input array sizes (N=10^3 to 10^6) with standard deviations.",
                maxPoints=25.0,
            ),
            RubricCriterion(
                id="crit-4",
                title="Code Clarity & Documentation",
                description="Clean coding style, meaningful identifiers, and markdown formatting.",
                maxPoints=15.0,
            ),
        ],
    ),
    Rubric(
        id="rubric-2",
        courseCode="CS101",
        assignmentTitle="Assignment 2: Graph Traversal & Dijkstra",
        description="Assessment of shortest-path algorithm correctness and priority queue usage.",
        totalPoints=100.0,
        createdAt="2026-10-02",
        criteria=[
            RubricCriterion(
                id="crit-2-1",
                title="Graph Representation & Min-Heap Heapify",
                description="Adjacency list representation and binary heap priority queue usage.",
                maxPoints=40.0,
            ),
            RubricCriterion(
                id="crit-2-2",
                title="Dijkstra Implementation & Edge-case Handling",
                description="Properly ignores negative cycles and disconnect components.",
                maxPoints=35.0,
            ),
            RubricCriterion(
                id="crit-2-3",
                title="Complexity Discussion & Code Style",
                description="O((V+E)log V) proof and modular code organization.",
                maxPoints=25.0,
            ),
        ],
    ),
    Rubric(
        id="rubric-3",
        courseCode="AI301",
        assignmentTitle="Lab 3: Gradient Descent Optimization Report",
        description="Analysis of SGD, Momentum, and Adam optimizers on non-convex surfaces.",
        totalPoints=100.0,
        createdAt="2026-10-03",
        criteria=[
            RubricCriterion(
                id="crit-3-1",
                title="Mathematical Derivation of Gradients",
                description="Accurate analytical gradients and partial derivative chains.",
                maxPoints=30.0,
            ),
            RubricCriterion(
                id="crit-3-2",
                title="Comparative Convergence Experiments",
                description="Loss curve comparisons and hyperparameter sensitivity grids.",
                maxPoints=40.0,
            ),
            RubricCriterion(
                id="crit-3-3",
                title="Pedagogical Synthesis & Conclusions",
                description="Insightful discussion of saddle points and local minima traps.",
                maxPoints=30.0,
            ),
        ],
    ),
]

SEED_SUBMISSIONS: List[Submission] = [
    Submission(
        id="sub-101",
        studentId=DEV_STUDENT_ID,
        studentName="Alex Rivera",
        studentEmail="alex.rivera@university.edu",
        ownerId=DEV_STUDENT_ID,
        assignmentId="assign-1",
        assignmentTitle="Assignment 1: Sorting Algorithms & Complexity",
        courseCode="CS101",
        fileName="alex_rivera_sorting_analysis.pdf",
        fileSize="1.4 MB",
        fileType="pdf",
        status=JobStatus.DONE,
        submittedAt="2026-10-07 14:22",
        rubricId="rubric-1",
        contentPreview="Comparative Analysis of Quicksort (Dual-Pivot) and Mergesort on Random vs Nearly Sorted Datasets. Includes Big-O proofs, empirical runtime tables, and memory profiling.",
        evaluation=EvaluationResult(
            score=92.0,
            maxScore=100.0,
            percentage=92.0,
            summaryFeedback="Exceptional submission demonstrating deep comprehension of algorithmic trade-offs. The empirical benchmarking confirms theoretical predictions with high experimental precision.",
            strengths=[
                "Robust dual-pivot quicksort implementation with recursion depth guard",
                "High-quality statistical plots with confidence intervals across multiple trials",
                "Master theorem and recurrence relations clearly articulated",
            ],
            improvements=[
                "Optimize memory reuse for auxiliary mergesort buffer",
                "Add memory profiling graphs alongside CPU execution times",
            ],
            aiModelExtraction="Gemini Flash-Lite",
            aiModelGrading="Gemini Flash",
            evaluatedAt="2026-10-07 14:24",
            criteriaScores=[
                {
                    "criterionId": "crit-1",
                    "title": "Algorithm Correctness & Implementation",
                    "scoreAwarded": 33.0,
                    "maxPoints": 35.0,
                    "feedback": "Dual-pivot partition algorithm implemented with high fidelity. QuickSort recursion depth limit guard correctly implemented.",
                    "strengths": "Excellent edge-case defense against adversarial quadratic inputs.",
                    "improvements": "MergeSort buffer allocation could be reused between recursive calls to reduce GC churn.",
                },
                {
                    "criterionId": "crit-2",
                    "title": "Theoretical Time & Space Complexity",
                    "scoreAwarded": 24.0,
                    "maxPoints": 25.0,
                    "feedback": "Rigorous master theorem application for mergesort. Clear explanation of random pivot expectation.",
                    "strengths": "Clear recurrences with step-by-step substitution method.",
                    "improvements": "Minor omission in space complexity analysis of auxiliary stack frames for worst-case quicksort.",
                },
                {
                    "criterionId": "crit-3",
                    "title": "Empirical Benchmark Analysis",
                    "scoreAwarded": 22.0,
                    "maxPoints": 25.0,
                    "feedback": "Runtime plots clearly distinguish O(N log N) from O(N^2) behavior on sorted arrays.",
                    "strengths": "Clean matplotlib visualizations with error bars across 10 trials.",
                    "improvements": "Include cache miss telemetry or perf counters for deeper hardware-level analysis.",
                },
                {
                    "criterionId": "crit-4",
                    "title": "Code Clarity & Documentation",
                    "scoreAwarded": 13.0,
                    "maxPoints": 15.0,
                    "feedback": "Extremely clean code formatting, well-commented helper functions.",
                    "strengths": "Follows PEP 8 / Google Style guide conventions.",
                    "improvements": "Docstrings could clarify type constraints on generic sorting comparator.",
                },
            ],
        ),
    ),
    Submission(
        id="sub-102",
        studentId="STU-2024-114",
        studentName="Samantha Chen",
        studentEmail="s.chen@university.edu",
        assignmentId="assign-1",
        assignmentTitle="Assignment 1: Sorting Algorithms & Complexity",
        courseCode="CS101",
        fileName="chen_samantha_report.md",
        fileSize="420 KB",
        fileType="markdown",
        status=JobStatus.DONE,
        submittedAt="2026-10-07 16:05",
        rubricId="rubric-1",
        contentPreview="Sorting Benchmarking Report in Markdown format. Explores QuickSort, MergeSort, and TimSort behavior on sorted, reverse sorted, and uniformly distributed integer arrays.",
        evaluation=EvaluationResult(
            score=84.0,
            maxScore=100.0,
            percentage=84.0,
            summaryFeedback="Good solid work covering all essential requirements. To achieve full marks, provide mathematical proofs rather than only stating asymptotic bounds.",
            strengths=[
                "Clean markdown layout with formatted tables",
                "Well-tested sorting routines with verified outputs",
            ],
            improvements=[
                "Add visual benchmark plots",
                "Strengthen average-case proof using indicator random variables",
            ],
            aiModelExtraction="Gemini Flash-Lite",
            aiModelGrading="Gemini Flash",
            evaluatedAt="2026-10-07 16:07",
            criteriaScores=[
                {
                    "criterionId": "crit-1",
                    "title": "Algorithm Correctness & Implementation",
                    "scoreAwarded": 30.0,
                    "maxPoints": 35.0,
                    "feedback": "Standard Lomuto partitioning used. Works as expected for average case.",
                    "strengths": "Accurate base cases and clean recursion.",
                    "improvements": "Lomuto partition degenerates to O(N^2) on identical element arrays; Hoare partition would be more resilient.",
                },
                {
                    "criterionId": "crit-2",
                    "title": "Theoretical Time & Space Complexity",
                    "scoreAwarded": 20.0,
                    "maxPoints": 25.0,
                    "feedback": "Good overview of Big-O notations, but lacks formal mathematical proof for average case.",
                    "strengths": "Accurate asymptotic notation descriptions.",
                    "improvements": "Provide formal expectation derivation using indicator random variables.",
                },
                {
                    "criterionId": "crit-3",
                    "title": "Empirical Benchmark Analysis",
                    "scoreAwarded": 22.0,
                    "maxPoints": 25.0,
                    "feedback": "Tabular data provided for N up to 500,000.",
                    "strengths": "Accurate timing measurements in milliseconds.",
                    "improvements": "Visual graphs would make the crossover points between QuickSort and MergeSort much clearer.",
                },
                {
                    "criterionId": "crit-4",
                    "title": "Code Clarity & Documentation",
                    "scoreAwarded": 12.0,
                    "maxPoints": 15.0,
                    "feedback": "Clean Markdown formatting with syntax-highlighted code fences.",
                    "strengths": "Easy to read and navigate.",
                    "improvements": "Add inline commentary for the merge loop indices.",
                },
            ],
        ),
        override=FacultyOverride(
            isOverridden=True,
            originalScore=84.0,
            overriddenScore=89.0,
            overriddenBy="Dr. Sarah Lin",
            overrideReason="Student included an insightful handwritten proof in the appendix that the extraction stage partially omitted. Adjusted Theoretical Complexity from 20 to 25.",
            overriddenAt="2026-10-07 18:30",
            criterionAdjustments={"crit-2": 25.0},
        ),
    ),
    Submission(
        id="sub-103",
        studentId="STU-2024-042",
        studentName="Marcus Brody",
        studentEmail="m.brody@university.edu",
        assignmentId="assign-3",
        assignmentTitle="Lab 3: Gradient Descent Optimization Report",
        courseCode="AI301",
        fileName="brody_sgd_optimization.pdf",
        fileSize="3.1 MB",
        fileType="pdf",
        status=JobStatus.PROCESSING,
        processingStep=ProcessingStep.GRADING,
        submittedAt="2026-10-08 21:10",
        rubricId="rubric-3",
        contentPreview="Experimental study comparing Mini-batch SGD with Adam and RMSprop on Rosenbrock and Rastrigin test functions.",
    ),
    Submission(
        id="sub-104",
        studentId="STU-2024-198",
        studentName="Elena Rostova",
        studentEmail="elena.r@university.edu",
        assignmentId="assign-1",
        assignmentTitle="Assignment 1: Sorting Algorithms & Complexity",
        courseCode="CS101",
        fileName="elena_sorting_report.pdf",
        fileSize="2.0 MB",
        fileType="pdf",
        status=JobStatus.PENDING,
        processingStep=ProcessingStep.QUEUED,
        submittedAt="2026-10-08 22:25",
        rubricId="rubric-1",
        contentPreview="Sorting analysis submission with C++ benchmark driver and python plotting scripts.",
    ),
    Submission(
        id="sub-105",
        studentId="STU-2024-077",
        studentName="Devon Patel",
        studentEmail="d.patel@university.edu",
        assignmentId="assign-1",
        assignmentTitle="Assignment 1: Sorting Algorithms & Complexity",
        courseCode="CS101",
        fileName="patel_sorting_hw.md",
        fileSize="150 KB",
        fileType="markdown",
        status=JobStatus.FLAGGED,
        submittedAt="2026-10-08 19:40",
        rubricId="rubric-1",
        contentPreview="Sorting algorithm implementation report. AI pipeline detected incomplete complexity section or missing benchmark file.",
        evaluation=EvaluationResult(
            score=58.0,
            maxScore=100.0,
            percentage=58.0,
            summaryFeedback="Flagged for Faculty Review: The submission appears to be missing benchmark graphs and has truncated mathematical derivations.",
            strengths=["Basic sorting code passes elementary test cases"],
            improvements=["Complete missing complexity proofs", "Attach benchmark charts"],
            aiModelExtraction="Gemini Flash-Lite",
            aiModelGrading="Gemini Flash",
            evaluatedAt="2026-10-08 19:42",
            criteriaScores=[],
        ),
    ),
]


class InMemoryDatabase:
    def __init__(self):
        self.rubrics: Dict[str, Rubric] = {r.id: copy.deepcopy(r) for r in SEED_RUBRICS}
        self.submissions: Dict[str, Submission] = {s.id: copy.deepcopy(s) for s in SEED_SUBMISSIONS}
        self.grading_jobs: Dict[str, GradingJob] = {
            "job-103": GradingJob(
                id="job-103",
                submissionId="sub-103",
                status=JobStatus.PROCESSING,
                startedAt="2026-10-08T21:10:00Z",
            ),
            "job-104": GradingJob(
                id="job-104",
                submissionId="sub-104",
                status=JobStatus.PENDING,
                startedAt=None,
            ),
        }
        self.file_storage: Dict[str, bytes] = {}
        # Course ownership: maps course_code -> faculty_id (UUID)
        self.courses: Dict[str, Course] = {c.id: copy.deepcopy(c) for c in SEED_COURSES}
        self.concepts: Dict[str, Concept] = {c.id: copy.deepcopy(c) for c in SEED_CONCEPTS}
        self.concept_edges: Dict[str, ConceptEdge] = {e.id: copy.deepcopy(e) for e in SEED_CONCEPT_EDGES}
        self.course_owners: Dict[str, str] = {
            "CS101": DEV_FACULTY_ID,
            "AI301": DEV_FACULTY_ID,
            "CS201": DEV_FACULTY_ID,
            "MATH201": OTHER_FACULTY_ID,
            "c1010000-0000-0000-0000-000000000001": DEV_FACULTY_ID,
            "a3010000-0000-0000-0000-000000000002": DEV_FACULTY_ID,
            "m2010000-0000-0000-0000-000000000003": OTHER_FACULTY_ID,
        }
        # Student concept mastery records
        self.mastery_records: List[Dict[str, Any]] = []
        self.submission_concept_feedback: List[Dict[str, Any]] = []
        self.faculty_overrides: List[Dict[str, Any]] = []
        self.assignments: Dict[str, Assignment] = {a.id: copy.deepcopy(a) for a in SEED_ASSIGNMENTS}
        self.assignment_concepts: Dict[str, List[str]] = {a.id: list(a.concept_ids) for a in SEED_ASSIGNMENTS}
        self.assignment_criterion_concepts: Dict[str, List[CriterionConceptMap]] = {
            a.id: copy.deepcopy(a.criterion_concepts) for a in SEED_ASSIGNMENTS
        }
        self.enrollments: List[Dict[str, str]] = [dict(e) for e in SEED_ENROLLMENTS]



db = InMemoryDatabase()


class Repository:
    @staticmethod
    def is_course_authorized(course_code: Optional[str], user: Any) -> bool:
        """
        Verifies that the authenticated faculty user owns the course.
        Admins are authorized for all courses.
        """
        if not user:
            return False
        if getattr(user, "role", "") == "admin":
            return True
        if getattr(user, "role", "") != "faculty":
            return False
        if not course_code or course_code == "ALL":
            return True

        client = get_supabase_client()
        if client:
            try:
                res = client.table("courses").select("id").eq("code", course_code).eq("faculty_id", user.id).limit(1).execute()
                if res.data and len(res.data) > 0:
                    return True
            except Exception as e:
                logger.warning(f"Supabase course ownership query failed: {e}")

        # In-memory check
        owner_id = db.course_owners.get(course_code)
        if owner_id:
            return owner_id == user.id

        # Default fallback for development/seed courses
        return user.id == DEV_FACULTY_ID and course_code in ["CS101", "AI301", "CS201"]

    @staticmethod
    def get_rubrics(course_code: Optional[str] = None) -> List[Rubric]:
        client = get_supabase_client()
        if client:
            try:
                query = client.table("rubrics").select("*, rubric_criteria(*)")
                if course_code:
                    query = query.eq("course_code", course_code)
                res = query.execute()
                if res.data is not None:
                    rubrics = []
                    for row in res.data:
                        criteria = [
                            RubricCriterion(
                                id=c["id"],
                                title=c["title"],
                                description=c.get("description", ""),
                                maxPoints=float(c.get("max_points", 0)),
                                weightPercent=c.get("weight_percent"),
                            )
                            for c in row.get("rubric_criteria", [])
                        ]
                        rubrics.append(
                            Rubric(
                                id=row["id"],
                                courseCode=row["course_code"],
                                assignmentTitle=row["assignment_title"],
                                description=row.get("description", ""),
                                totalPoints=float(row.get("total_points", 100)),
                                createdAt=row.get("created_at", ""),
                                criteria=criteria,
                            )
                        )
                    return rubrics
            except Exception as e:
                logger.warning(f"Supabase rubrics query failed, using in-memory store: {e}")

        # In-memory fallback
        results = list(db.rubrics.values())
        if course_code:
            results = [r for r in results if r.courseCode.lower() == course_code.lower()]
        return results

    @staticmethod
    def get_rubric_by_id(rubric_id: str) -> Optional[Rubric]:
        client = get_supabase_client()
        if client:
            try:
                res = client.table("rubrics").select("*, rubric_criteria(*)").eq("id", rubric_id).execute()
                if res.data is not None and res.data:
                    row = res.data[0]
                    criteria = [
                        RubricCriterion(
                            id=c["id"],
                            title=c["title"],
                            description=c.get("description", ""),
                            maxPoints=float(c.get("max_points", 0)),
                            weightPercent=c.get("weight_percent"),
                        )
                        for c in row.get("rubric_criteria", [])
                    ]
                    return Rubric(
                        id=row["id"],
                        courseCode=row["course_code"],
                        assignmentTitle=row["assignment_title"],
                        description=row.get("description", ""),
                        totalPoints=float(row.get("total_points", 100)),
                        createdAt=row.get("created_at", ""),
                        criteria=criteria,
                    )
            except Exception as e:
                logger.warning(f"Supabase fetch rubric failed: {e}")

        return db.rubrics.get(rubric_id)

    @staticmethod
    def create_rubric(rubric: Rubric) -> Rubric:
        client = get_supabase_client()
        if client:
            try:
                client.table("rubrics").insert({
                    "id": rubric.id,
                    "course_code": rubric.courseCode,
                    "assignment_title": rubric.assignmentTitle,
                    "description": rubric.description,
                    "total_points": rubric.totalPoints,
                    "created_at": rubric.createdAt,
                }).execute()
                for i, c in enumerate(rubric.criteria):
                    client.table("rubric_criteria").insert({
                        "id": c.id,
                        "rubric_id": rubric.id,
                        "title": c.title,
                        "description": c.description,
                        "max_points": c.maxPoints,
                        "weight_percent": c.weightPercent,
                        "order_index": i,
                    }).execute()
            except Exception as e:
                logger.warning(f"Supabase insert rubric failed: {e}")

        db.rubrics[rubric.id] = copy.deepcopy(rubric)
        return rubric

    @staticmethod
    def update_rubric(rubric_id: str, update_data: RubricUpdate) -> Optional[Rubric]:
        rubric = Repository.get_rubric_by_id(rubric_id)
        if not rubric:
            return None

        if update_data.courseCode is not None:
            rubric.courseCode = update_data.courseCode
        if update_data.assignmentTitle is not None:
            rubric.assignmentTitle = update_data.assignmentTitle
        if update_data.description is not None:
            rubric.description = update_data.description
        if update_data.totalPoints is not None:
            rubric.totalPoints = update_data.totalPoints
        if update_data.criteria is not None:
            rubric.criteria = update_data.criteria

        client = get_supabase_client()
        if client:
            try:
                client.table("rubrics").update({
                    "course_code": rubric.courseCode,
                    "assignment_title": rubric.assignmentTitle,
                    "description": rubric.description,
                    "total_points": rubric.totalPoints,
                }).eq("id", rubric_id).execute()
                client.table("rubric_criteria").delete().eq("rubric_id", rubric_id).execute()
                for i, criterion in enumerate(rubric.criteria):
                    client.table("rubric_criteria").insert({
                        "id": criterion.id,
                        "rubric_id": rubric_id,
                        "title": criterion.title,
                        "description": criterion.description,
                        "max_points": criterion.maxPoints,
                        "weight_percent": criterion.weightPercent,
                        "order_index": i,
                    }).execute()
            except Exception as e:
                logger.warning(f"Supabase update rubric failed: {e}")

        db.rubrics[rubric_id] = copy.deepcopy(rubric)
        return rubric

    @staticmethod
    def delete_rubric(rubric_id: str) -> bool:
        if rubric_id in db.rubrics:
            del db.rubrics[rubric_id]
        client = get_supabase_client()
        if client:
            try:
                client.table("rubrics").delete().eq("id", rubric_id).execute()
            except Exception as e:
                logger.warning(f"Supabase delete rubric failed: {e}")
        return True

    @staticmethod
    def get_submissions(
        course_code: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        student_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        faculty_user: Optional[Any] = None,
    ) -> Tuple[List[Submission], Dict[str, Any]]:
        client = get_supabase_client()
        subs = list(db.submissions.values())

        if client:
            try:
                # Query authoritative submissions table with fallback to submissions_v2
                target_table = "submissions"
                query = client.table(target_table).select("*", count="exact").order("submitted_at", desc=True)
                if course_code and course_code != "ALL":
                    query = query.eq("course_code", course_code)
                if status and status != "ALL" and status != "overridden":
                    query = query.eq("status", status)
                if student_id:
                    query = query.or_(f"student_id.eq.{student_id},owner_id.eq.{student_id}")
                if search and search.strip():
                    term = search.strip().replace(",", " ")
                    query = query.or_(f"student_name.ilike.%{term}%,student_id.ilike.%{term}%,assignment_title.ilike.%{term}%")
                result = query.range(offset, offset + limit - 1).execute()
                if result.data is not None:
                    subs = [s for row in result.data if (s := Repository._submission_from_row(row)) is not None]
                    for submission in subs:
                        db.submissions[submission.id] = copy.deepcopy(submission)
            except Exception as e:
                # Fallback to submissions_v2 if authoritative submissions query failed
                try:
                    query = client.table("submissions_v2").select("*", count="exact").order("submitted_at", desc=True)
                    if course_code and course_code != "ALL":
                        query = query.eq("course_code", course_code)
                    if status and status != "ALL" and status != "overridden":
                        query = query.eq("status", status)
                    if student_id:
                        query = query.or_(f"student_id.eq.{student_id},owner_id.eq.{student_id}")
                    result = query.range(offset, offset + limit - 1).execute()
                    if result.data is not None:
                        subs = [s for row in result.data if (s := Repository._submission_from_row(row)) is not None]
                except Exception as inner_e:
                    logger.warning(f"Supabase submissions query failed: {inner_e}")

        # In-memory filtering
        if student_id:
            subs = [s for s in subs if s.studentId == student_id or s.ownerId == student_id or s.studentEmail.lower() == student_id.lower()]

        if assignment_id and assignment_id != "ALL":
            subs = [s for s in subs if str(getattr(s, "assignmentId", "")) == str(assignment_id)]

        if course_code and course_code != "ALL":
            subs = [s for s in subs if s.courseCode.lower() == course_code.lower()]
        elif faculty_user and getattr(faculty_user, "role", "") == "faculty":
            # If faculty lists all, only show courses they own
            subs = [s for s in subs if Repository.is_course_authorized(s.courseCode, faculty_user)]

        if status and status != "ALL":
            if status == "overridden":
                subs = [s for s in subs if s.override and s.override.isOverridden]
            else:
                subs = [s for s in subs if s.status == status]

        if search and search.strip():
            q = search.strip().lower()
            subs = [
                s
                for s in subs
                if q in s.studentName.lower()
                or q in s.studentId.lower()
                or q in s.studentEmail.lower()
                or q in s.assignmentTitle.lower()
                or q in s.fileName.lower()
            ]

        total = len(subs)
        evaluated = sum(1 for s in subs if s.status == JobStatus.DONE or s.evaluation is not None)
        pending = sum(1 for s in subs if s.status in [JobStatus.PENDING, JobStatus.PROCESSING])
        overridden = sum(1 for s in subs if s.override and s.override.isOverridden)

        evaluated_scores = []
        for s in subs:
            if s.override and s.override.isOverridden:
                evaluated_scores.append(s.override.overriddenScore)
            elif s.evaluation:
                evaluated_scores.append(s.evaluation.score)

        class_average = round(sum(evaluated_scores) / len(evaluated_scores), 1) if evaluated_scores else 0.0
        paginated = subs[offset : offset + limit] if not client else subs

        meta = {
            "total": total,
            "evaluated": evaluated,
            "pending": pending,
            "overridden": overridden,
            "classAverage": class_average,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "limit": limit,
        }

        return paginated, meta

    @staticmethod
    def get_submission_by_id(submission_id: str) -> Optional[Submission]:
        client = get_supabase_client()
        if client:
            try:
                res = client.table("submissions").select("*").eq("id", submission_id).execute()
                if not res.data:
                    res = client.table("submissions_v2").select("*").eq("id", submission_id).execute()
                if res.data:
                    submission = Repository._submission_from_row(res.data[0])
                    if submission:
                        db.submissions[submission.id] = copy.deepcopy(submission)
                        return submission
            except Exception as e:
                logger.warning(f"Supabase get submission failed: {e}")

        return db.submissions.get(submission_id)

    @staticmethod
    def _submission_from_row(row: Dict[str, Any]) -> Optional[Submission]:
        try:
            submission = Submission(
                id=str(row["id"]),
                studentId=str(row.get("student_id", "")),
                studentName=row.get("student_name", "Student"),
                studentEmail=row.get("student_email", ""),
                assignmentId=str(row.get("assignment_id", "")),
                assignmentTitle=row.get("assignment_title", "Assignment"),
                courseCode=row.get("course_code", "CS101"),
                fileName=row.get("file_name", "submission.pdf"),
                fileSize=row.get("file_size", "0 B"),
                fileType=row.get("file_type", "pdf"),
                fileUrl=row.get("file_url"),
                contentPreview=row.get("content_preview"),
                status=row.get("status", "pending"),
                processingStep=row.get("processing_step"),
                rubricId=row.get("rubric_id") or "",
                submittedAt=str(row.get("submitted_at", "")),
                ownerId=str(row.get("owner_id") or row.get("student_id", "")),
            )
            client = get_supabase_client()
            if client:
                evaluation_rows = client.table("evaluations").select("*").eq("submission_id", submission.id).limit(1).execute().data or []
                if evaluation_rows:
                    ev = evaluation_rows[0]
                    criteria = client.table("criterion_evaluations").select("*").eq("evaluation_id", ev["id"]).execute().data or []
                    concept_feedback_list = []
                    try:
                        scf_rows = client.table("submission_concept_feedback").select("*, concepts(name)").eq("submission_id", submission.id).execute().data or []
                        if scf_rows:
                            seen_cids = {}
                            for r in scf_rows:
                                cid = str(r["concept_id"])
                                if cid not in seen_cids:
                                    c_name = r.get("concepts", {}).get("name") if isinstance(r.get("concepts"), dict) else (db.concepts[cid].name if cid in db.concepts else "Concept")
                                    seen_cids[cid] = ConceptFeedback(
                                        conceptId=cid,
                                        conceptName=c_name,
                                        scoreRatio=float(r.get("score_ratio") or 0.0),
                                        evidenceCount=1,
                                        masteryContribution=float(r.get("mastery_percentage") or 0.0) / 100.0,
                                        confidenceScore=float(r.get("confidence") or 0.8),
                                        feedback=r.get("feedback_text") or "",
                                        strengths=[],
                                        improvements=[],
                                    )
                            concept_feedback_list = list(seen_cids.values())
                    except Exception as scf_err:
                        logger.debug(f"Could not load submission_concept_feedback: {scf_err}")

                    submission.evaluation = EvaluationResult(
                        score=float(ev["score"]),
                        maxScore=float(ev["max_score"]),
                        percentage=float(ev["percentage"]),
                        summaryFeedback=ev.get("summary_feedback", ""),
                        strengths=ev.get("strengths") or [],
                        improvements=ev.get("improvements") or [],
                        aiModelExtraction=ev.get("ai_model_extraction") or "",
                        aiModelGrading=ev.get("ai_model_grading") or "",
                        evaluatedAt=str(ev.get("evaluated_at", "")),
                        criteriaScores=[{
                            "criterionId": c["criterion_id"],
                            "title": c.get("title") or "",
                            "scoreAwarded": float(c["score_awarded"]),
                            "maxPoints": float(c["max_points"]),
                            "scoreRatio": float(c["score_ratio"]) if c.get("score_ratio") is not None else (float(c["score_awarded"]) / float(c["max_points"]) if float(c.get("max_points") or 0) > 0 else 0.0),
                            "evidence": c.get("evidence"),
                            "reasoning": c.get("reasoning"),
                            "feedback": c.get("feedback") or "",
                            "strengths": c.get("strengths"),
                            "improvements": c.get("improvements"),
                        } for c in criteria],
                        conceptFeedback=concept_feedback_list,
                    )
                override_rows = client.table("faculty_overrides").select("*").eq("submission_id", submission.id).order("overridden_at", desc=True).limit(1).execute().data or []
                if override_rows:
                    ov = override_rows[0]
                    submission.override = FacultyOverride(
                        isOverridden=ov["is_overridden"],
                        originalScore=float(ov["original_score"]),
                        overriddenScore=float(ov["overridden_score"]),
                        overriddenBy=ov.get("overridden_by_name") or ov.get("overridden_by") or "Faculty",
                        overrideReason=ov["override_reason"],
                        overriddenAt=str(ov["overridden_at"]),
                        criterionAdjustments=ov.get("criterion_adjustments"),
                    )
            return submission
        except Exception as e:
            logger.warning(f"Could not map Supabase submission row: {e}")
            return None

    @staticmethod
    def save_submission(submission: Submission, owner_id: Optional[str] = None) -> Submission:
        db.submissions[submission.id] = copy.deepcopy(submission)
        client = get_supabase_client()
        if client:
            try:
                row = {
                    "id": submission.id,
                    "student_id": owner_id or submission.studentId,
                    "student_name": submission.studentName,
                    "student_email": submission.studentEmail,
                    "assignment_id": submission.assignmentId,
                    "assignment_title": submission.assignmentTitle,
                    "course_code": submission.courseCode,
                    "file_name": submission.fileName,
                    "file_size": submission.fileSize,
                    "file_type": submission.fileType,
                    "file_url": submission.fileUrl,
                    "rubric_id": submission.rubricId,
                    "status": submission.status.value,
                    "processing_step": submission.processingStep.value if submission.processingStep else None,
                    "content_preview": submission.contentPreview,
                    "submitted_at": submission.submittedAt,
                }
                if submission.assignmentId:
                    assign = Repository.get_assignment_by_id(submission.assignmentId)
                    if assign:
                        if not row.get("course_id"):
                            row["course_id"] = assign.course_id
                        if not row.get("rubric_id") and assign.rubric_id:
                            row["rubric_id"] = assign.rubric_id

                if owner_id:
                    row["owner_id"] = owner_id

                # Upsert into authoritative submissions table
                try:
                    client.table("submissions").upsert(row).execute()
                except Exception as sub_err:
                    logger.warning(f"Authoritative submissions upsert error (trying fallback): {sub_err}")
                    client.table("submissions_v2").upsert(row).execute()

                # Evaluations persistence
                if submission.evaluation:
                    evaluation = submission.evaluation
                    evaluation_id = str(uuid.uuid4())
                    client.table("evaluations").upsert({
                        "id": evaluation_id,
                        "submission_id": submission.id,
                        "score": evaluation.score,
                        "max_score": evaluation.maxScore,
                        "percentage": evaluation.percentage,
                        "summary_feedback": evaluation.summaryFeedback,
                        "strengths": evaluation.strengths,
                        "improvements": evaluation.improvements,
                        "ai_model_extraction": evaluation.aiModelExtraction,
                        "ai_model_grading": evaluation.aiModelGrading,
                        "evaluated_at": evaluation.evaluatedAt,
                    }, on_conflict="submission_id").execute()

                    client.table("criterion_evaluations").delete().eq("evaluation_id", evaluation_id).execute()
                    for criterion in evaluation.criteriaScores:
                        crit_ratio = criterion.scoreRatio if criterion.scoreRatio is not None else (round(criterion.scoreAwarded / criterion.maxPoints, 4) if criterion.maxPoints > 0 else 0.0)
                        client.table("criterion_evaluations").insert({
                            "id": str(uuid.uuid4()),
                            "evaluation_id": evaluation_id,
                            "criterion_id": criterion.criterionId,
                            "title": criterion.title,
                            "score_awarded": criterion.scoreAwarded,
                            "max_points": criterion.maxPoints,
                            "score_ratio": crit_ratio,
                            "reasoning": criterion.reasoning or "",
                            "evidence": criterion.evidence or "",
                            "feedback": criterion.feedback,
                            "strengths": criterion.strengths,
                            "improvements": criterion.improvements,
                        }).execute()
            except Exception as e:
                logger.warning(f"Supabase upsert submission failed: {e}")

        return submission

    @staticmethod
    def override_submission_grade(
        submission_id: str,
        override: FacultyOverride,
        faculty_user_id: Optional[str] = None,
    ) -> Optional[Submission]:
        sub = Repository.get_submission_by_id(submission_id)
        if not sub:
            return None

        sub.override = override
        if sub.status == JobStatus.FLAGGED:
            sub.status = JobStatus.DONE

        Repository.save_submission(sub)

        faculty_user_uuid = faculty_user_id or getattr(override, "overriddenById", None) or DEV_FACULTY_ID

        fo_row = {
            "id": str(uuid.uuid4()),
            "submission_id": submission_id,
            "is_overridden": override.isOverridden,
            "original_score": override.originalScore,
            "overridden_score": override.overriddenScore,
            "overridden_by": faculty_user_uuid,
            "overridden_by_name": getattr(override, "overriddenByName", None) or override.overriddenBy,
            "override_reason": override.overrideReason,
            "criterion_adjustments": override.criterionAdjustments,
            "overridden_at": override.overriddenAt or datetime.now(timezone.utc).isoformat(),
        }
        if hasattr(db, "faculty_overrides"):
            db.faculty_overrides.append(fo_row)

        client = get_supabase_client()
        if client:
            try:
                client.table("faculty_overrides").insert({
                    "id": str(uuid.uuid4()),
                    "submission_id": submission_id,
                    "is_overridden": override.isOverridden,
                    "original_score": override.originalScore,
                    "overridden_score": override.overriddenScore,
                    "overridden_by": faculty_user_uuid,
                    "overridden_by_name": getattr(override, "overriddenByName", None) or override.overriddenBy,
                    "override_reason": override.overrideReason,
                    "criterion_adjustments": override.criterionAdjustments,
                    "overridden_at": override.overriddenAt,
                }).execute()
            except Exception as e:
                logger.warning(f"Supabase insert override failed: {e}")

        # Identify concepts associated with this submission's assignment
        maps = Repository.get_assignment_criterion_concepts(sub.assignmentId)
        concept_ids = set()
        if maps:
            for m in maps:
                cid = getattr(m, "concept_id", None) or getattr(m, "conceptId", None)
                if cid:
                    concept_ids.add(cid)
        if not concept_ids:
            c_list = db.assignment_concepts.get(sub.assignmentId, [])
            concept_ids.update(c_list)
        if not concept_ids:
            concept_ids.add("c0000000-0000-0000-0000-000000000001")

        # Update criterion evaluations and concept feedback if criterionAdjustments provided
        if override.criterionAdjustments and sub.evaluation and sub.evaluation.criteriaScores:
            for crit in sub.evaluation.criteriaScores:
                if crit.criterionId in override.criterionAdjustments:
                    adj = float(override.criterionAdjustments[crit.criterionId])
                    crit.scoreAwarded = adj
                    if crit.maxPoints > 0:
                        crit.scoreRatio = min(1.0, max(0.0, round(adj / crit.maxPoints, 4)))

            # Update score_ratio in submission_concept_feedback for this submission
            for crit_id, adj_val in override.criterionAdjustments.items():
                crit_obj = next((c for c in sub.evaluation.criteriaScores if c.criterionId == crit_id), None)
                if crit_obj and crit_obj.maxPoints > 0:
                    new_ratio = min(1.0, max(0.0, round(adj_val / crit_obj.maxPoints, 4)))
                    for fb in getattr(db, "submission_concept_feedback", []):
                        if str(fb.get("submission_id")) == str(sub.id) and str(fb.get("criterion_id")) == str(crit_id):
                            fb["score_ratio"] = new_ratio
                    if client:
                        try:
                            client.table("submission_concept_feedback").update({
                                "score_ratio": new_ratio
                            }).eq("submission_id", sub.id).eq("criterion_id", crit_id).execute()
                        except Exception as e:
                            logger.warning(f"Failed to update submission_concept_feedback: {e}")

            Repository.save_submission(sub)

        if override.isOverridden:
            if not override.criterionAdjustments:
                for cid in concept_ids:
                    Repository.record_concept_mastery_evidence(
                        student_id=sub.studentId,
                        concept_id=cid,
                        raw_score=override.overriddenScore,
                        max_score=sub.evaluation.maxScore if sub.evaluation else 100.0,
                        submission_id=sub.id,
                        source="faculty_override",
                    )
            else:
                # Criterion-level adjustments: recompute mastery deterministically from updated evidence
                for cid in concept_ids:
                    Repository.recompute_student_concept_mastery(
                        student_id=sub.studentId,
                        concept_id=cid,
                    )
        else:
            # Override removed: recalculate clean AI mastery from authoritative evidence
            for cid in concept_ids:
                Repository.recompute_student_concept_mastery(
                    student_id=sub.studentId,
                    concept_id=cid,
                )

        return sub

    @staticmethod
    def record_concept_mastery_evidence(
        student_id: str,
        concept_id: str,
        raw_score: float,
        max_score: float,
        submission_id: Optional[str] = None,
        source: str = "ai_evaluation",
    ) -> Dict[str, Any]:
        """
        Calculates and records concept mastery evidence for a student.
        Mastery score is stored as a normalized fraction (0.0 to 1.0) calculated
        independently from raw assignment points, with confidence scaled by evidence count.
        """
        safe_max = max(max_score, 1.0)
        mastery_fraction = max(0.0, min(1.0, round(raw_score / safe_max, 4)))
        now_iso = datetime.now(timezone.utc).isoformat()

        existing = next(
            (m for m in db.mastery_records if m.get("student_id") == student_id and m.get("concept_id") == concept_id),
            None
        )

        # Source normalization
        allowed_sources = {"ai_evaluation", "faculty_override", "diagnostic_quiz", "manual_adjustment"}
        norm_source = source if source in allowed_sources else ("ai_evaluation" if "ai" in source else "faculty_override")

        if existing:
            evidence_count = existing.get("evidence_count", 1) + 1
            if norm_source == "faculty_override":
                new_mastery = mastery_fraction
                confidence = 1.0
            else:
                new_mastery = max(0.0, min(1.0, round(0.7 * existing.get("mastery_score", mastery_fraction) + 0.3 * mastery_fraction, 4)))
                confidence = min(1.0, max(0.0, round(0.5 + 0.1 * evidence_count, 4)))

            existing["mastery_score"] = new_mastery
            existing["mastery_percentage"] = round(new_mastery * 100.0, 2)
            existing["confidence_score"] = confidence
            existing["source"] = norm_source
            existing["evidence_count"] = evidence_count
            existing["last_evidence_submission_id"] = submission_id
            existing["last_evaluated_at"] = now_iso
            existing["updated_at"] = now_iso
            record = existing
        else:
            confidence = 1.0 if norm_source == "faculty_override" else 0.6
            record = {
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "concept_id": concept_id,
                "mastery_score": mastery_fraction,
                "mastery_percentage": round(mastery_fraction * 100.0, 2),
                "confidence_score": min(1.0, max(0.0, confidence)),
                "source": norm_source,
                "last_evidence_submission_id": submission_id,
                "evidence_count": 1,
                "last_evaluated_at": now_iso,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            db.mastery_records.append(record)

        client = get_supabase_client()
        if client:
            try:
                client.table("student_concept_mastery").upsert(record, on_conflict="student_id,concept_id").execute()
            except Exception as e:
                logger.warning(f"Supabase student_concept_mastery upsert failed: {e}")

        return record

    @staticmethod
    def get_student_mastery(student_id: str, calling_user: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Retrieves concept mastery records for a student.
        Enforces access control: Students can only read their own mastery records.
        Faculty and Admin can read student mastery.
        """
        if calling_user and calling_user.role == "student":
            if calling_user.id != student_id and calling_user.email != student_id:
                raise APIException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="FORBIDDEN",
                    message="You can only view your own mastery records.",
                )

        client = get_supabase_client()
        if client:
            try:
                res = client.table("student_concept_mastery").select("*, concepts(name, course_id)").eq("student_id", student_id).execute()
                if res.data is not None:
                    return res.data
            except Exception as e:
                logger.warning(f"Supabase student mastery query failed: {e}")

        # In-memory fallback
        return [
            m for m in db.mastery_records
            if m.get("student_id") == student_id
        ]

    @staticmethod
    def get_pending_grading_jobs(limit: int = 10) -> List[GradingJob]:
        client = get_supabase_client()
        if client:
            try:
                rows = client.table("grading_jobs").select("*").eq("status", "pending").order("id").limit(limit).execute().data or []
                jobs = [GradingJob(
                    id=str(row["id"]),
                    submissionId=str(row["submission_id"]),
                    status=row["status"],
                    retryCount=row.get("retry_count", 0),
                    errorLog=row.get("error_log"),
                    startedAt=str(row["started_at"]) if row.get("started_at") else None,
                    completedAt=str(row["completed_at"]) if row.get("completed_at") else None,
                ) for row in rows]
                for job in jobs:
                    db.grading_jobs[job.id] = copy.deepcopy(job)
                return jobs
            except Exception as e:
                logger.warning(f"Supabase pending-job query failed, using in-memory store: {e}")

        pending = [j for j in db.grading_jobs.values() if j.status == JobStatus.PENDING]
        return pending[:limit]

    @staticmethod
    def get_job_by_submission_id(submission_id: str) -> Optional[GradingJob]:
        for job in reversed(list(db.grading_jobs.values())):
            if job.submissionId == submission_id:
                return job
        return None

    @staticmethod
    def save_job(job: GradingJob) -> GradingJob:
        db.grading_jobs[job.id] = copy.deepcopy(job)
        client = get_supabase_client()
        if client:
            try:
                client.table("grading_jobs").upsert({
                    "id": job.id,
                    "submission_id": job.submissionId,
                    "status": job.status.value,
                    "retry_count": job.retryCount,
                    "max_retries": job.maxRetries,
                    "locked_by": job.lockedBy,
                    "locked_at": job.lockedAt,
                    "error_log": job.errorLog,
                    "started_at": job.startedAt,
                    "completed_at": job.completedAt,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            except Exception as e:
                logger.warning(f"Supabase grading-job upsert failed: {e}")
        return job


    @staticmethod
    def claim_grading_job(worker_id: str, stale_interval_seconds: int = 300) -> Optional[GradingJob]:
        """
        Atomically claims a pending or abandoned grading job using PostgreSQL's
        claim_grading_job stored procedure with FOR UPDATE SKIP LOCKED concurrency protection.
        In mock or disconnected mode, performs thread-safe in-memory locking.
        """
        client = get_supabase_client()
        if client:
            try:
                res = client.rpc(
                    "claim_grading_job",
                    {
                        "p_worker_id": worker_id,
                        "p_stale_interval": f"{stale_interval_seconds} seconds"
                    }
                ).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    job = GradingJob(
                        id=str(row["id"]),
                        submissionId=str(row["submission_id"]),
                        status=JobStatus(row["status"]),
                        retryCount=row.get("retry_count", 0),
                        maxRetries=row.get("max_retries", 3),
                        lockedBy=row.get("locked_by"),
                        lockedAt=str(row.get("started_at", "")),
                        startedAt=str(row["started_at"]) if row.get("started_at") else None,
                        completedAt=None,
                    )
                    db.grading_jobs[job.id] = copy.deepcopy(job)
                    return job
                return None
            except Exception as e:
                logger.warning(f"claim_grading_job RPC failed, using in-memory fallback: {e}")

        # In-memory mock fallback
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        for job in db.grading_jobs.values():
            is_pending = (job.status == JobStatus.PENDING and job.retryCount < job.maxRetries)
            is_stale = False
            if job.status == JobStatus.PROCESSING:
                if job.lockedAt:
                    try:
                        locked_dt = datetime.fromisoformat(job.lockedAt.replace("Z", "+00:00"))
                        is_stale = (now_dt - locked_dt).total_seconds() > stale_interval_seconds
                    except Exception:
                        is_stale = True
                else:
                    is_stale = True

            if is_pending or is_stale:
                job.status = JobStatus.PROCESSING
                job.lockedBy = worker_id
                job.lockedAt = now_iso
                job.startedAt = job.startedAt or now_iso
                return copy.deepcopy(job)
        return None

    @staticmethod
    def get_assignment_criterion_concepts(assignment_id: str) -> List[CriterionConceptMap]:
        """
        Retrieves the authoritative criterion-to-concept mappings for an assignment from
        the assignment_criterion_concepts table.
        """
        client = get_supabase_client()
        if client:
            try:
                res = (
                    client.table("assignment_criterion_concepts")
                    .select("criterion_id, concept_id, concepts(name)")
                    .eq("assignment_id", assignment_id)
                    .execute()
                )
                if res.data:
                    results = []
                    for row in res.data:
                        c_name = None
                        if isinstance(row.get("concepts"), dict):
                            c_name = row["concepts"].get("name")
                        elif row.get("concept_id") in db.concepts:
                            c_name = db.concepts[row["concept_id"]].name
                        results.append(
                            CriterionConceptMap(
                                criterionId=str(row["criterion_id"]),
                                conceptId=str(row["concept_id"]),
                                conceptName=c_name,
                            )
                        )
                    return results
            except Exception as e:
                logger.warning(f"Supabase get_assignment_criterion_concepts failed: {e}")

        # In-memory lookup
        if assignment_id in db.assignment_criterion_concepts:
            maps = copy.deepcopy(db.assignment_criterion_concepts[assignment_id])
            for m in maps:
                cid = getattr(m, "concept_id", None) or getattr(m, "conceptId", None)
                cname = getattr(m, "concept_name", None) or getattr(m, "conceptName", None)
                if not cname and cid in db.concepts:
                    if hasattr(m, "concept_name"):
                        m.concept_name = db.concepts[cid].name
                    elif hasattr(m, "conceptName"):
                        m.conceptName = db.concepts[cid].name
            return maps

        assign = db.assignments.get(assignment_id)
        if assign and getattr(assign, "criterion_concepts", None):
            maps = copy.deepcopy(assign.criterion_concepts)
            for m in maps:
                cid = getattr(m, "concept_id", None) or getattr(m, "conceptId", None)
                cname = getattr(m, "concept_name", None) or getattr(m, "conceptName", None)
                if not cname and cid in db.concepts:
                    if hasattr(m, "concept_name"):
                        m.concept_name = db.concepts[cid].name
                    elif hasattr(m, "conceptName"):
                        m.conceptName = db.concepts[cid].name
            return maps

        return []

    @staticmethod
    def has_active_faculty_override(submission_id: str) -> bool:
        """
        Determines whether an active faculty override exists for the given submission.
        """
        if hasattr(db, "faculty_overrides") and db.faculty_overrides:
            matching = [fo for fo in db.faculty_overrides if fo.get("submission_id") == submission_id]
            if matching:
                return bool(matching[-1].get("is_overridden", True))

        sub = db.submissions.get(submission_id)
        if sub and sub.override is not None:
            return bool(sub.override.isOverridden)

        client = get_supabase_client()
        if client:
            try:
                res = (
                    client.table("faculty_overrides")
                    .select("id, is_overridden")
                    .eq("submission_id", submission_id)
                    .order("overridden_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    return bool(res.data[0].get("is_overridden", True))
            except Exception as e:
                logger.warning(f"Supabase has_active_faculty_override query failed: {e}")

        return False

    @staticmethod
    def recompute_student_concept_mastery(student_id: str, concept_id: str) -> Optional[Dict[str, Any]]:
        """
        Recomputes a student's concept mastery score and confidence from authoritative
        historical evidence records in submission_concept_feedback.
        Guarantees:
        1. Fully reproducible, deterministic calculation.
        2. Corrected or replaced evidence updates mastery cleanly without ghost drift.
        3. Preserves active faculty overrides.
        4. Restores pure AI mastery upon faculty override removal.
        """
        existing_mastery = next(
            (m for m in db.mastery_records if str(m.get("student_id")) == str(student_id) and str(m.get("concept_id")) == str(concept_id)),
            None
        )
        client = get_supabase_client()
        if client:
            try:
                res = (
                    client.table("student_concept_mastery")
                    .select("*")
                    .eq("student_id", student_id)
                    .eq("concept_id", concept_id)
                    .limit(1)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    existing_mastery = res.data[0]
            except Exception as e:
                logger.warning(f"Error querying student_concept_mastery in recompute: {e}")

        # Check if faculty override is active
        if existing_mastery and existing_mastery.get("source") == "faculty_override":
            sub_id = existing_mastery.get("submission_id")
            if sub_id and Repository.has_active_faculty_override(sub_id):
                logger.info(f"Preserving active faculty override for student {student_id}, concept {concept_id}")
                return existing_mastery

        # Gather authoritative historical evidence records
        feedback_records = []
        if client:
            try:
                res = (
                    client.table("submission_concept_feedback")
                    .select("*")
                    .eq("student_id", student_id)
                    .eq("concept_id", concept_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                if res.data:
                    feedback_records = res.data
            except Exception as e:
                logger.warning(f"Error querying submission_concept_feedback in recompute: {e}")

        if not feedback_records:
            feedback_records = [
                fb for fb in getattr(db, "submission_concept_feedback", [])
                if str(fb.get("student_id")) == str(student_id) and str(fb.get("concept_id")) == str(concept_id)
            ]

        if not feedback_records:
            return existing_mastery

        # Group by submission_id to calculate submission-level composite evidence
        submissions_order = []
        sub_groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in feedback_records:
            sid = str(r["submission_id"])
            if sid not in sub_groups:
                submissions_order.append(sid)
                sub_groups[sid] = []
            sub_groups[sid].append(r)

        # Pre-compute submission-level aggregated evidence
        sub_evidence: Dict[str, Tuple[float, float]] = {}
        for sid, recs in sub_groups.items():
            e_vals = [float(r.get("score_ratio", 0.0)) for r in recs]
            c_vals = [float(r.get("confidence", 0.8)) for r in recs]
            E = sum(e_vals) / len(e_vals) if e_vals else 0.0
            c_new = sum(c_vals) / len(c_vals) if c_vals else 0.8
            sub_evidence[sid] = (E, c_new)

        # Baseline check: If older submissions exist in existing_mastery not recorded in feedback
        if existing_mastery and existing_mastery.get("submission_id") and existing_mastery.get("submission_id") not in sub_groups:
            M_current = float(existing_mastery.get("mastery_score", 0.50))
            c_current = float(existing_mastery.get("confidence_score", 0.60))
            start_N = int(existing_mastery.get("evidence_count", 1))
        else:
            M_current = 0.50
            c_current = 0.60
            start_N = 0

        N = start_N
        for idx, sid in enumerate(submissions_order):
            E, c_new = sub_evidence[sid]
            step_idx = start_N + idx
            if step_idx == 0:
                # Initial evidence
                M_current = (0.50 * 1.0 + E * c_new) / (1.0 + c_new)
                c_current = min(0.95, round(c_new * 0.85, 4))
                N = 1
            else:
                # Subsequent evidence
                W = min(4.0, step_idx * c_current)
                M_current = (M_current * W + E * c_new) / (W + c_new)
                c_current = min(0.99, round(c_current + (1.0 - c_current) * 0.20, 4))
                N = step_idx + 1

        M_final = min(1.0, max(0.0, round(M_current, 4)))
        c_final = min(1.0, max(0.0, round(c_current, 4)))
        now_iso = datetime.now(timezone.utc).isoformat()
        last_sub_id = submissions_order[-1] if submissions_order else None

        mastery_payload = {
            "student_id": student_id,
            "concept_id": concept_id,
            "submission_id": last_sub_id,
            "mastery_score": M_final,
            "mastery_percentage": round(M_final * 100.0, 2),
            "confidence_score": c_final,
            "source": "ai",
            "evidence_count": N,
            "last_evaluated_at": now_iso,
            "updated_at": now_iso,
        }

        # Update in-memory
        existing_in_mem = next(
            (m for m in db.mastery_records if str(m.get("student_id")) == str(student_id) and str(m.get("concept_id")) == str(concept_id)),
            None
        )
        if existing_in_mem:
            existing_in_mem.update(mastery_payload)
        else:
            db.mastery_records.append({**mastery_payload, "id": str(uuid.uuid4()), "created_at": now_iso})

        # Update Supabase
        if client:
            try:
                client.table("student_concept_mastery").upsert(
                    mastery_payload,
                    on_conflict="student_id,concept_id"
                ).execute()
            except Exception as e:
                logger.warning(f"Supabase student_concept_mastery upsert in recompute failed: {e}")

        return mastery_payload

    @staticmethod
    def record_concept_evidence_and_update_mastery(
        submission: Submission,
        evaluation: EvaluationResult
    ) -> List[ConceptFeedback]:
        """
        Converts rubric criterion evaluations into curriculum concept evidence and updates
        student concept mastery records strictly adhering to the specification in docs/MASTERY_UPDATE_DESIGN.md.

        1. Queries authoritative criterion-to-concept mappings from assignment_criterion_concepts.
        2. Unmapped criteria are graded for assignment score but ignored by the concept mastery engine.
        3. Aggregates multi-criterion composite evidence E in [0.0, 1.0].
        4. Detects direct verbatim textual evidence to assign confidence score c in [0.5, 0.95].
        5. Respects Faculty Override Precedence: does NOT overwrite active faculty overrides.
        6. Implements idempotent reprocessing: prevents evidence count inflation on repeated runs.
        7. Persists submission_concept_feedback and student_concept_mastery.
        """
        criterion_concept_maps = Repository.get_assignment_criterion_concepts(submission.assignmentId)
        if not criterion_concept_maps:
            logger.info(f"No criterion-concept mappings found for assignment {submission.assignmentId}. Skipping mastery update.")
            return []

        # Index criteria scores by criterionId
        criteria_by_id = {c.criterionId: c for c in evaluation.criteriaScores}

        # Group criteria by concept_id
        concept_criteria: Dict[str, List[CriterionEvaluation]] = {}
        concept_names: Dict[str, str] = {}
        for cc in criterion_concept_maps:
            cc_crit_id = getattr(cc, "criterion_id", None) or getattr(cc, "criterionId", None)
            cc_concept_id = getattr(cc, "concept_id", None) or getattr(cc, "conceptId", None)
            cc_concept_name = getattr(cc, "concept_name", None) or getattr(cc, "conceptName", None)
            if cc_crit_id and cc_crit_id in criteria_by_id:
                concept_criteria.setdefault(cc_concept_id, []).append(criteria_by_id[cc_crit_id])
                if cc_concept_name:
                    concept_names[cc_concept_id] = cc_concept_name
                elif cc_concept_id in db.concepts:
                    concept_names[cc_concept_id] = db.concepts[cc_concept_id].name

        if not concept_criteria:
            return []

        # Check for active faculty override on this submission
        has_override = Repository.has_active_faculty_override(submission.id)

        now_iso = datetime.now(timezone.utc).isoformat()
        concept_feedback_list: List[ConceptFeedback] = []
        client = get_supabase_client()

        for concept_id, crit_list in concept_criteria.items():
            # 1. Composite Evidence Score E in [0.0, 1.0]
            sum_awarded = sum(c.scoreAwarded for c in crit_list)
            sum_max = sum(c.maxPoints for c in crit_list)
            E = round(sum_awarded / sum_max, 4) if sum_max > 0 else 0.0
            E = max(0.0, min(1.0, E))

            # 2. Evidence Confidence c_new in [0.0, 1.0]
            # If criteria provide explicit confidence values, calculate points-weighted composite confidence:
            explicit_confidences = [c.confidence for c in crit_list if getattr(c, "confidence", None) is not None]
            if len(explicit_confidences) == len(crit_list):
                if sum_max > 0:
                    c_new = round(sum(c.maxPoints * c.confidence for c in crit_list) / sum_max, 4)
                else:
                    c_new = round(sum(explicit_confidences) / len(explicit_confidences), 4)
                c_new = max(0.0, min(1.0, c_new))
            else:
                c_base = 0.70
                has_verbatim = any(bool(c.evidence and len(c.evidence.strip()) >= 15) for c in crit_list)
                bonus_evidence = 0.10 if has_verbatim else 0.0
                bonus_pts = 0.05 if sum_max >= 20.0 else 0.0
                c_new = round(min(0.95, max(0.50, c_base + bonus_evidence + bonus_pts)), 4)

            # 3. Aggregate feedback, strengths, and improvements
            feedbacks = [c.feedback for c in crit_list if c.feedback]
            strengths = []
            for c in crit_list:
                if c.strengths:
                    if isinstance(c.strengths, list):
                        strengths.extend(c.strengths)
                    else:
                        strengths.append(c.strengths)
            improvements = []
            for c in crit_list:
                if c.improvements:
                    if isinstance(c.improvements, list):
                        improvements.extend(c.improvements)
                    else:
                        improvements.append(c.improvements)
            combined_feedback = " ".join(feedbacks) if feedbacks else f"Demonstrated {round(E * 100, 1)}% competence across {len(crit_list)} evaluated criteria."

            # 4. Persist submission_concept_feedback first (authoritative granular evidence)
            for c in crit_list:
                c_evidence = c.evidence or ""
                c_ratio = c.scoreRatio if c.scoreRatio is not None else (round(c.scoreAwarded / c.maxPoints, 4) if c.maxPoints > 0 else 0.0)
                crit_conf = c.confidence if getattr(c, "confidence", None) is not None else c_new
                feedback_row = {
                    "submission_id": submission.id,
                    "student_id": submission.studentId,
                    "concept_id": concept_id,
                    "criterion_id": c.criterionId,
                    "score_ratio": max(0.0, min(1.0, c_ratio)),
                    "confidence": max(0.0, min(1.0, crit_conf)),
                    "feedback_text": c.feedback or "",
                    "evidence": c_evidence,
                    "mastery_percentage": round(E * 100.0, 2),
                    "created_at": now_iso,
                }
                # Update in-memory db.submission_concept_feedback (replace if exists for idempotency)
                if hasattr(db, "submission_concept_feedback"):
                    existing_idx = next(
                        (i for i, fb in enumerate(db.submission_concept_feedback)
                         if fb.get("submission_id") == submission.id
                         and fb.get("concept_id") == concept_id
                         and fb.get("criterion_id") == c.criterionId),
                        None
                    )
                    if existing_idx is not None:
                        db.submission_concept_feedback[existing_idx] = feedback_row
                    else:
                        db.submission_concept_feedback.append(feedback_row)

                if client:
                    try:
                        client.table("submission_concept_feedback").upsert(
                            feedback_row,
                            on_conflict="submission_id,concept_id,criterion_id"
                        ).execute()
                    except Exception as e:
                        logger.warning(f"Supabase submission_concept_feedback upsert failed: {e}")

            # 5. Fetch existing student mastery record
            existing_record = None
            if client:
                try:
                    res = (
                        client.table("student_concept_mastery")
                        .select("*")
                        .eq("student_id", submission.studentId)
                        .eq("concept_id", concept_id)
                        .limit(1)
                        .execute()
                    )
                    if res.data and len(res.data) > 0:
                        existing_record = res.data[0]
                except Exception as e:
                    logger.warning(f"Error querying student_concept_mastery: {e}")

            if not existing_record:
                existing_record = next(
                    (m for m in db.mastery_records if str(m.get("student_id")) == str(submission.studentId) and str(m.get("concept_id")) == str(concept_id)),
                    None
                )

            # 6. Faculty Override Precedence Protection vs Authoritative Evidence Recomputation
            if has_override or (existing_record and existing_record.get("source") == "faculty_override"):
                # Do NOT overwrite faculty mastery!
                M_updated = float(existing_record.get("mastery_score", E)) if existing_record else E
                c_updated = float(existing_record.get("confidence_score", 1.0)) if existing_record else 1.0
                N_updated = existing_record.get("evidence_count", 1) if existing_record else 1
                record_source = "faculty_override"
                logger.info(f"Preserving faculty override mastery for student {submission.studentId}, concept {concept_id}")
            else:
                # Recompute clean asymptotic mastery from authoritative evidence
                mastery_res = Repository.recompute_student_concept_mastery(submission.studentId, concept_id)
                if mastery_res:
                    M_updated = float(mastery_res.get("mastery_score", E))
                    c_updated = float(mastery_res.get("confidence_score", c_new))
                    N_updated = int(mastery_res.get("evidence_count", 1))
                else:
                    M_updated = E
                    c_updated = c_new
                    N_updated = 1

            # 8. Add to output list
            c_name = concept_names.get(concept_id) or (db.concepts[concept_id].name if concept_id in db.concepts else "Curriculum Concept")
            concept_feedback_list.append(
                ConceptFeedback(
                    conceptId=concept_id,
                    conceptName=c_name,
                    scoreRatio=E,
                    evidenceCount=N_updated,
                    masteryContribution=M_updated,
                    confidenceScore=c_updated,
                    feedback=combined_feedback,
                    strengths=strengths,
                    improvements=improvements,
                )
            )

        return concept_feedback_list

    @staticmethod
    def get_queue_stats() -> QueueStats:
        pending_count = sum(1 for j in db.grading_jobs.values() if j.status == JobStatus.PENDING)
        processing_count = sum(1 for j in db.grading_jobs.values() if j.status == JobStatus.PROCESSING)
        return QueueStats(
            pendingJobs=pending_count,
            processingJobs=processing_count,
            oldestPendingJobAgeSeconds=45 if pending_count > 0 else 0,
        )


    @staticmethod
    def is_course_owner_by_id(course_id: str, user: Any) -> bool:
        """
        Verifies that the authenticated faculty user owns the course (by UUID or code).
        Admins are authorized for all courses.
        """
        if not user:
            return False
        if getattr(user, "role", "") == "admin":
            return True
        if getattr(user, "role", "") != "faculty":
            return False

        client = get_supabase_client()
        if client:
            try:
                res = client.table("courses").select("id, faculty_id, code").or_(f"id.eq.{course_id},code.eq.{course_id}").limit(1).execute()
                if res.data and len(res.data) > 0:
                    return str(res.data[0].get("faculty_id")) == str(user.id)
            except Exception as e:
                logger.warning(f"Supabase course ownership query by id failed: {e}")

        # In-memory check
        course = db.courses.get(course_id)
        if course:
            return str(course.faculty_id) == str(user.id)
        for c in db.courses.values():
            if c.code.lower() == course_id.lower():
                return str(c.faculty_id) == str(user.id)
        return False

    @staticmethod
    def get_courses_for_faculty(faculty_id: str, is_admin: bool = False) -> List[Course]:
        client = get_supabase_client()
        if client:
            try:
                q = client.table("courses").select("*")
                if not is_admin:
                    q = q.eq("faculty_id", faculty_id)
                res = q.order("created_at", desc=True).execute()
                if res.data is not None:
                    courses = []
                    for row in res.data:
                        cid = str(row["id"])
                        c_cnt = 0
                        try:
                            c_cnt_res = client.table("concepts").select("id", count="exact").eq("course_id", cid).execute()
                            c_cnt = c_cnt_res.count if c_cnt_res.count is not None else 0
                        except Exception:
                            pass
                        a_cnt = 0
                        try:
                            a_cnt_res = client.table("assignments").select("id", count="exact").eq("course_id", cid).execute()
                            a_cnt = a_cnt_res.count if a_cnt_res.count is not None else 0
                        except Exception:
                            pass
                        courses.append(
                            Course(
                                id=cid,
                                code=row["code"],
                                name=row["name"],
                                description=row.get("description", "") or "",
                                facultyId=str(row["faculty_id"]),
                                createdAt=str(row.get("created_at", "")),
                                updatedAt=str(row.get("updated_at")) if row.get("updated_at") else None,
                                conceptsCount=c_cnt,
                                assignmentsCount=a_cnt,
                            )
                        )
                    return courses
            except Exception as e:
                logger.warning(f"Supabase get_courses_for_faculty failed: {e}")

        # In-memory fallback
        results = []
        for c in db.courses.values():
            if is_admin or str(c.faculty_id) == str(faculty_id):
                c_copy = copy.deepcopy(c)
                c_copy.concepts_count = sum(1 for cp in db.concepts.values() if cp.course_id == c.id)
                c_copy.assignments_count = sum(1 for r in db.rubrics.values() if r.courseCode.lower() == c.code.lower())
                results.append(c_copy)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    @staticmethod
    def get_course_by_id(course_id: str) -> Optional[Course]:
        client = get_supabase_client()
        if client:
            try:
                res = client.table("courses").select("*").or_(f"id.eq.{course_id},code.eq.{course_id}").limit(1).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    cid = str(row["id"])
                    c_cnt = 0
                    try:
                        c_cnt = client.table("concepts").select("id", count="exact").eq("course_id", cid).execute().count or 0
                    except Exception:
                        pass
                    a_cnt = 0
                    try:
                        a_cnt = client.table("assignments").select("id", count="exact").eq("course_id", cid).execute().count or 0
                    except Exception:
                        pass
                    return Course(
                        id=cid,
                        code=row["code"],
                        name=row["name"],
                        description=row.get("description", "") or "",
                        facultyId=str(row["faculty_id"]),
                        createdAt=str(row.get("created_at", "")),
                        updatedAt=str(row.get("updated_at")) if row.get("updated_at") else None,
                        conceptsCount=c_cnt,
                        assignmentsCount=a_cnt,
                    )
            except Exception as e:
                logger.warning(f"Supabase get_course_by_id failed: {e}")

        # In-memory check
        course = db.courses.get(course_id)
        if course:
            c_copy = copy.deepcopy(course)
            c_copy.concepts_count = sum(1 for cp in db.concepts.values() if cp.course_id == course.id)
            c_copy.assignments_count = sum(1 for r in db.rubrics.values() if r.courseCode.lower() == course.code.lower())
            return c_copy
        for c in db.courses.values():
            if c.code.lower() == course_id.lower():
                c_copy = copy.deepcopy(c)
                c_copy.concepts_count = sum(1 for cp in db.concepts.values() if cp.course_id == c.id)
                c_copy.assignments_count = sum(1 for r in db.rubrics.values() if r.courseCode.lower() == c.code.lower())
                return c_copy
        return None

    @staticmethod
    def get_course_by_code(course_code: str) -> Optional[Course]:
        client = get_supabase_client()
        if client:
            try:
                res = client.table("courses").select("*").ilike("code", course_code).limit(1).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    return Course(
                        id=str(row["id"]),
                        code=row["code"],
                        name=row["name"],
                        description=row.get("description", "") or "",
                        facultyId=str(row["faculty_id"]),
                        createdAt=str(row.get("created_at", "")),
                    )
            except Exception as e:
                logger.warning(f"Supabase get_course_by_code failed: {e}")

        for c in db.courses.values():
            if c.code.lower() == course_code.lower():
                return copy.deepcopy(c)
        return None

    @staticmethod
    def create_course(course_in: CourseCreate, faculty_id: str) -> Course:
        # Check uniqueness of course code
        existing = Repository.get_course_by_code(course_in.code)
        if existing:
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="DUPLICATE_COURSE_CODE",
                message=f"A course with code '{course_in.code}' already exists.",
            )

        new_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        new_course = Course(
            id=new_id,
            code=course_in.code.upper(),
            name=course_in.name,
            description=course_in.description,
            facultyId=faculty_id,
            createdAt=now_iso,
            conceptsCount=0,
            assignmentsCount=0,
        )

        client = get_supabase_client()
        if client:
            try:
                res = client.table("courses").insert({
                    "id": new_id,
                    "code": course_in.code.upper(),
                    "name": course_in.name,
                    "description": course_in.description,
                    "faculty_id": faculty_id,
                }).select().single().execute()
                if res.data:
                    row = res.data
                    new_course = Course(
                        id=str(row["id"]),
                        code=row["code"],
                        name=row["name"],
                        description=row.get("description", "") or "",
                        facultyId=str(row["faculty_id"]),
                        createdAt=str(row.get("created_at", now_iso)),
                        conceptsCount=0,
                        assignmentsCount=0,
                    )
            except Exception as e:
                err_str = str(e)
                if "duplicate key" in err_str or "unique constraint" in err_str:
                    raise APIException(
                        status_code=status.HTTP_409_CONFLICT,
                        code="DUPLICATE_COURSE_CODE",
                        message=f"Course code '{course_in.code}' is already registered.",
                    )
                logger.warning(f"Supabase course insert failed: {e}")

        db.courses[new_course.id] = copy.deepcopy(new_course)
        db.course_owners[new_course.code] = faculty_id
        db.course_owners[new_course.id] = faculty_id
        return new_course

    @staticmethod
    def _has_cycle_or_path(course_id: str, start_concept_id: str, target_concept_id: str) -> bool:
        """
        Checks if there is a directed path from start_concept_id to target_concept_id
        within the given course. If start == target, returns True (self-loop / cycle).
        """
        if start_concept_id == target_concept_id:
            return True

        # Check in-memory edges for this course
        visited = set()
        queue = [start_concept_id]

        adj: Dict[str, List[str]] = {}
        for e in db.concept_edges.values():
            if e.course_id == course_id:
                adj.setdefault(e.from_concept, []).append(e.to_concept)

        while queue:
            curr = queue.pop(0)
            if curr == target_concept_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        return False

    @staticmethod
    def get_curriculum_graph(course_id: str) -> Optional[CurriculumGraph]:
        course = Repository.get_course_by_id(course_id)
        if not course:
            return None

        concepts: List[Concept] = []
        edges: List[ConceptEdge] = []

        client = get_supabase_client()
        if client:
            try:
                c_res = client.table("concepts").select("*").eq("course_id", course.id).order("created_at").execute()
                if c_res.data:
                    for r in c_res.data:
                        concepts.append(
                            Concept(
                                id=str(r["id"]),
                                courseId=str(r["course_id"]),
                                name=r["name"],
                                description=r.get("description", "") or "",
                                category=r.get("category", "") or "",
                                difficulty=r.get("difficulty", "intermediate") or "intermediate",
                                posX=float(r.get("pos_x", 0.0) or 0.0),
                                posY=float(r.get("pos_y", 0.0) or 0.0),
                                createdAt=str(r.get("created_at", "")),
                            )
                        )
                e_res = client.table("concept_edges").select("*").eq("course_id", course.id).order("created_at").execute()
                if e_res.data:
                    for r in e_res.data:
                        edges.append(
                            ConceptEdge(
                                id=str(r["id"]),
                                courseId=str(r["course_id"]),
                                fromConcept=str(r["from_concept"]),
                                toConcept=str(r["to_concept"]),
                                createdAt=str(r.get("created_at", "")),
                            )
                        )
                return CurriculumGraph(
                    courseId=course.id,
                    courseCode=course.code,
                    courseName=course.name,
                    courseDescription=course.description,
                    concepts=concepts,
                    edges=edges,
                )
            except Exception as e:
                logger.warning(f"Supabase get_curriculum_graph failed: {e}")

        # In-memory fallback
        concepts = [copy.deepcopy(c) for c in db.concepts.values() if c.course_id == course.id]
        edges = [copy.deepcopy(e) for e in db.concept_edges.values() if e.course_id == course.id]
        return CurriculumGraph(
            courseId=course.id,
            courseCode=course.code,
            courseName=course.name,
            courseDescription=course.description,
            concepts=concepts,
            edges=edges,
        )

    @staticmethod
    def get_concepts_for_course(course_id: str) -> List[Concept]:
        graph = Repository.get_curriculum_graph(course_id)
        return graph.concepts if graph else []

    @staticmethod
    def get_edges_for_course(course_id: str) -> List[ConceptEdge]:
        graph = Repository.get_curriculum_graph(course_id)
        return graph.edges if graph else []

    @staticmethod
    def create_concept(course_id: str, concept_in: ConceptCreate) -> Concept:
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        new_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        concept = Concept(
            id=new_id,
            courseId=course.id,
            name=concept_in.name,
            description=concept_in.description,
            category=concept_in.category,
            difficulty=concept_in.difficulty,
            posX=concept_in.pos_x,
            posY=concept_in.pos_y,
            createdAt=now_iso,
        )

        client = get_supabase_client()
        if client:
            try:
                res = client.table("concepts").insert({
                    "id": new_id,
                    "course_id": course.id,
                    "name": concept_in.name,
                    "description": concept_in.description,
                    "category": concept_in.category,
                    "difficulty": concept_in.difficulty,
                    "pos_x": concept_in.pos_x,
                    "pos_y": concept_in.pos_y,
                }).select().single().execute()
                if res.data:
                    r = res.data
                    concept = Concept(
                        id=str(r["id"]),
                        courseId=str(r["course_id"]),
                        name=r["name"],
                        description=r.get("description", "") or "",
                        category=r.get("category", "") or "",
                        difficulty=r.get("difficulty", "intermediate") or "intermediate",
                        posX=float(r.get("pos_x", 0.0) or 0.0),
                        posY=float(r.get("pos_y", 0.0) or 0.0),
                        createdAt=str(r.get("created_at", now_iso)),
                    )
            except Exception as e:
                logger.warning(f"Supabase concept insert failed: {e}")

        db.concepts[concept.id] = copy.deepcopy(concept)
        return concept

    @staticmethod
    def update_concept(course_id: str, concept_id: str, update_in: ConceptUpdate) -> Optional[Concept]:
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        client = get_supabase_client()
        if client:
            try:
                update_dict = {}
                if update_in.name is not None:
                    update_dict["name"] = update_in.name
                if update_in.description is not None:
                    update_dict["description"] = update_in.description
                if update_in.category is not None:
                    update_dict["category"] = update_in.category
                if update_in.difficulty is not None:
                    update_dict["difficulty"] = update_in.difficulty
                if update_in.pos_x is not None:
                    update_dict["pos_x"] = update_in.pos_x
                if update_in.pos_y is not None:
                    update_dict["pos_y"] = update_in.pos_y

                res = client.table("concepts").update(update_dict).eq("id", concept_id).eq("course_id", course.id).select().execute()
                if res.data and len(res.data) > 0:
                    r = res.data[0]
                    updated = Concept(
                        id=str(r["id"]),
                        courseId=str(r["course_id"]),
                        name=r["name"],
                        description=r.get("description", "") or "",
                        category=r.get("category", "") or "",
                        difficulty=r.get("difficulty", "intermediate") or "intermediate",
                        posX=float(r.get("pos_x", 0.0) or 0.0),
                        posY=float(r.get("pos_y", 0.0) or 0.0),
                        createdAt=str(r.get("created_at", "")),
                    )
                    db.concepts[updated.id] = copy.deepcopy(updated)
                    return updated
            except Exception as e:
                logger.warning(f"Supabase concept update failed: {e}")

        concept = db.concepts.get(concept_id)
        if not concept or concept.course_id != course.id:
            return None

        if update_in.name is not None:
            concept.name = update_in.name
        if update_in.description is not None:
            concept.description = update_in.description
        if update_in.category is not None:
            concept.category = update_in.category
        if update_in.difficulty is not None:
            concept.difficulty = update_in.difficulty
        if update_in.pos_x is not None:
            concept.pos_x = update_in.pos_x
        if update_in.pos_y is not None:
            concept.pos_y = update_in.pos_y

        db.concepts[concept.id] = copy.deepcopy(concept)
        return copy.deepcopy(concept)

    @staticmethod
    def delete_concept(course_id: str, concept_id: str) -> bool:
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        client = get_supabase_client()
        if client:
            try:
                res = client.table("concepts").delete().eq("id", concept_id).eq("course_id", course.id).execute()
            except Exception as e:
                logger.warning(f"Supabase concept delete failed: {e}")

        concept = db.concepts.get(concept_id)
        if not concept or concept.course_id != course.id:
            return False

        del db.concepts[concept_id]
        edges_to_remove = [
            e_id for e_id, e in db.concept_edges.items()
            if e.from_concept == concept_id or e.to_concept == concept_id
        ]
        for e_id in edges_to_remove:
            db.concept_edges.pop(e_id, None)

        return True

    @staticmethod
    def create_concept_edge(course_id: str, edge_in: ConceptEdgeCreate) -> ConceptEdge:
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        # 1. Reject self-loop
        if edge_in.from_concept == edge_in.to_concept:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="SELF_LOOP_DETECTED",
                message="Concept cannot have a prerequisite edge to itself.",
            )

        # 2. Check concepts existence and course association
        from_c = None
        to_c = None
        client = get_supabase_client()
        if client:
            try:
                res = client.table("concepts").select("id, course_id, name").in_("id", [edge_in.from_concept, edge_in.to_concept]).execute()
                if res.data:
                    for r in res.data:
                        if str(r["id"]) == str(edge_in.from_concept):
                            from_c = r
                        if str(r["id"]) == str(edge_in.to_concept):
                            to_c = r
            except Exception as e:
                logger.warning(f"Supabase concept lookup for edge failed: {e}")

        if not from_c or not to_c:
            from_c = db.concepts.get(edge_in.from_concept)
            to_c = db.concepts.get(edge_in.to_concept)

        if not from_c or not to_c:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CONCEPT_NOT_FOUND",
                message="One or both concepts specified for the prerequisite edge do not exist.",
            )

        from_cid = str(from_c.get("course_id") if isinstance(from_c, dict) else from_c.course_id)
        to_cid = str(to_c.get("course_id") if isinstance(to_c, dict) else to_c.course_id)
        if from_cid != str(course.id) or to_cid != str(course.id):
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CROSS_COURSE_EDGE",
                message="Prerequisite edges can only connect concepts within the same course.",
            )

        # 3. Check duplicate edge
        for e in db.concept_edges.values():
            if e.course_id == course.id and e.from_concept == edge_in.from_concept and e.to_concept == edge_in.to_concept:
                raise APIException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="DUPLICATE_EDGE",
                    message="A prerequisite edge already exists between these concepts.",
                )

        # 4. Check DAG cycles (path from to_concept to from_concept)
        if Repository._has_cycle_or_path(course.id, edge_in.to_concept, edge_in.from_concept):
            from_name = from_c.get("name") if isinstance(from_c, dict) else from_c.name
            to_name = to_c.get("name") if isinstance(to_c, dict) else to_c.name
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CYCLE_DETECTED",
                message=f"Cycle detected: Adding prerequisite edge from '{from_name}' to '{to_name}' forms a circular dependency.",
            )

        new_edge_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        edge = ConceptEdge(
            id=new_edge_id,
            courseId=course.id,
            fromConcept=edge_in.from_concept,
            toConcept=edge_in.to_concept,
            createdAt=now_iso,
        )

        if client:
            try:
                res = client.table("concept_edges").insert({
                    "id": new_edge_id,
                    "course_id": course.id,
                    "from_concept": edge_in.from_concept,
                    "to_concept": edge_in.to_concept,
                }).select().single().execute()
                if res.data:
                    r = res.data
                    edge = ConceptEdge(
                        id=str(r["id"]),
                        courseId=str(r["course_id"]),
                        fromConcept=str(r["from_concept"]),
                        toConcept=str(r["to_concept"]),
                        createdAt=str(r.get("created_at", now_iso)),
                    )
            except Exception as e:
                err_str = str(e)
                if "Cycle detected" in err_str or "circular" in err_str:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="CYCLE_DETECTED",
                        message=err_str,
                    )
                if "within the same course" in err_str:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="CROSS_COURSE_EDGE",
                        message=err_str,
                    )
                if "duplicate" in err_str or "unique constraint" in err_str:
                    raise APIException(
                        status_code=status.HTTP_409_CONFLICT,
                        code="DUPLICATE_EDGE",
                        message="A prerequisite edge already exists between these concepts.",
                    )
                logger.warning(f"Supabase concept edge insert failed: {e}")

        db.concept_edges[edge.id] = copy.deepcopy(edge)
        return edge

    @staticmethod
    def delete_concept_edge(course_id: str, edge_id: str) -> bool:
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        client = get_supabase_client()
        if client:
            try:
                res = client.table("concept_edges").delete().eq("id", edge_id).eq("course_id", course.id).execute()
            except Exception as e:
                logger.warning(f"Supabase concept edge delete failed: {e}")

        edge = db.concept_edges.get(edge_id)
        if not edge or edge.course_id != course.id:
            return False

        del db.concept_edges[edge_id]
        return True

    @staticmethod
    def save_curriculum_layout(course_id: str, save_req: CurriculumSaveRequest) -> CurriculumGraph:
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        # 1. Update positions
        if save_req.positions:
            for pos in save_req.positions:
                Repository.update_concept(
                    course_id=course.id,
                    concept_id=pos.id,
                    update_in=ConceptUpdate(posX=pos.pos_x, posY=pos.pos_y)
                )

        # 2. Update edges if specified
        if save_req.edges is not None:
            # Validate self-loops
            for e_in in save_req.edges:
                if e_in.from_concept == e_in.to_concept:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="SELF_LOOP_DETECTED",
                        message="Self-loops are not permitted in prerequisite graphs.",
                    )

            # Cycle detection on submitted edge set
            adj: Dict[str, List[str]] = {}
            for e_in in save_req.edges:
                adj.setdefault(e_in.from_concept, []).append(e_in.to_concept)

            visited_state: Dict[str, int] = {}
            def dfs(node: str) -> bool:
                visited_state[node] = 1
                for neighbor in adj.get(node, []):
                    if visited_state.get(neighbor) == 1:
                        return True
                    if visited_state.get(neighbor, 0) == 0:
                        if dfs(neighbor):
                            return True
                visited_state[node] = 2
                return False

            for node in list(adj.keys()):
                if visited_state.get(node, 0) == 0:
                    if dfs(node):
                        raise APIException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="CYCLE_DETECTED",
                            message="Circular prerequisite dependency detected in submitted graph.",
                        )

            # Clear existing edges for this course
            client = get_supabase_client()
            if client:
                try:
                    client.table("concept_edges").delete().eq("course_id", course.id).execute()
                except Exception as e:
                    logger.warning(f"Supabase delete existing edges failed: {e}")

            for eid in [k for k, v in db.concept_edges.items() if v.course_id == course.id]:
                del db.concept_edges[eid]

            # Insert new edges
            for e_in in save_req.edges:
                Repository.create_concept_edge(course.id, ConceptEdgeCreate(fromConcept=e_in.from_concept, toConcept=e_in.to_concept))

        result = Repository.get_curriculum_graph(course.id)
        if not result:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )
        return result

    @staticmethod
    def enroll_student(course_id: str, student_id: str) -> bool:
        """Enrolls a student in a course if not already enrolled."""
        if not Repository.is_student_enrolled(course_id, student_id):
            db.enrollments.append({"course_id": str(course_id), "student_id": str(student_id)})
            client = get_supabase_client()
            if client:
                try:
                    client.table("enrollments").upsert({
                        "course_id": course_id,
                        "student_id": student_id,
                    }, on_conflict="course_id,student_id").execute()
                except Exception as e:
                    logger.warning(f"Supabase enroll_student failed: {e}")
            return True
        return False

    @staticmethod
    def get_course_enrolled_students(course_id: str) -> List[Dict[str, Any]]:
        """Retrieves students enrolled in a course with their mastery summary."""
        enrolled_ids = set()
        client = get_supabase_client()
        if client:
            try:
                res = client.table("enrollments").select("student_id").eq("course_id", course_id).execute()
                if res.data:
                    for r in res.data:
                        enrolled_ids.add(str(r["student_id"]))
            except Exception as e:
                logger.warning(f"Supabase get_course_enrolled_students failed: {e}")

        for e in getattr(db, "enrollments", []):
            if str(e.get("course_id")) == str(course_id):
                enrolled_ids.add(str(e.get("student_id")))

        if not enrolled_ids and course_id in ["c1010000-0000-0000-0000-000000000001", "a3010000-0000-0000-0000-000000000002"]:
            enrolled_ids.add(DEV_STUDENT_ID)

        course_concepts = Repository.get_concepts_for_course(course_id)
        total_concepts = len(course_concepts)
        concept_ids = {c.id for c in course_concepts}

        students = []
        for sid in sorted(list(enrolled_ids)):
            s_name = "Alex Student" if sid == DEV_STUDENT_ID else f"Student ({sid[:8]})"
            s_email = "alex.student@university.edu" if sid == DEV_STUDENT_ID else f"{sid[:8]}@university.edu"
            if client:
                try:
                    p = client.table("profiles").select("name, full_name, email").eq("id", sid).limit(1).execute()
                    if p.data and len(p.data) > 0:
                        s_name = p.data[0].get("full_name") or p.data[0].get("name") or s_name
                        s_email = p.data[0].get("email") or s_email
                except Exception:
                    pass

            mastery_list = Repository.get_student_mastery(sid)
            course_mastery = [m for m in mastery_list if m.get("concept_id") in concept_ids]
            assessed_count = len(course_mastery)
            avg_m = (
                round(sum(float(m.get("mastery_score", 0.0)) for m in course_mastery) / assessed_count, 4)
                if assessed_count > 0 else 0.0
            )

            students.append({
                "student_id": sid,
                "student_name": s_name,
                "student_email": s_email,
                "enrolled_at": "2026-10-01T00:00:00Z",
                "total_assessed_concepts": assessed_count,
                "total_concepts": total_concepts,
                "average_mastery": avg_m,
            })
        return students

    @staticmethod
    def get_student_course_curriculum(course_id: str, student_id: str) -> StudentCurriculumGraph:
        """
        Retrieves the canonical curriculum DAG for course_id enriched with the student's
        individualized learning data. Missing mastery strictly signifies UNASSESSED (masteryScore = None),
        NOT zero mastery.
        """
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        graph = Repository.get_curriculum_graph(course_id)
        if not graph:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CURRICULUM_NOT_FOUND",
                message=f"Curriculum graph for course '{course_id}' was not found.",
            )

        # Student identity
        student_name = "Alex Student" if student_id == DEV_STUDENT_ID else f"Student ({student_id[:8]})"
        student_email = "alex.student@university.edu" if student_id == DEV_STUDENT_ID else f"{student_id[:8]}@university.edu"
        client = get_supabase_client()
        if client:
            try:
                p = client.table("profiles").select("name, full_name, email").eq("id", student_id).limit(1).execute()
                if p.data and len(p.data) > 0:
                    student_name = p.data[0].get("full_name") or p.data[0].get("name") or student_name
                    student_email = p.data[0].get("email") or student_email
            except Exception:
                pass

        # Fetch student mastery
        mastery_list = Repository.get_student_mastery(student_id)
        mastery_by_concept = {str(m.get("concept_id")): m for m in mastery_list}

        # Fetch historical feedback records
        feedback_records = []
        if client:
            try:
                res = (
                    client.table("submission_concept_feedback")
                    .select("*")
                    .eq("student_id", student_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                if res.data:
                    feedback_records = res.data
            except Exception as e:
                logger.warning(f"Error querying submission_concept_feedback in curriculum: {e}")

        if not feedback_records:
            feedback_records = [
                fb for fb in getattr(db, "submission_concept_feedback", [])
                if str(fb.get("student_id")) == str(student_id)
            ]

        feedback_by_concept: Dict[str, List[Dict[str, Any]]] = {}
        for fb in feedback_records:
            cid = str(fb.get("concept_id"))
            feedback_by_concept.setdefault(cid, []).append(fb)

        # Index student submissions
        submissions, _ = Repository.get_submissions(student_id=student_id, limit=200)
        sub_by_id = {str(s.id): s for s in submissions}

        # Build enriched concepts
        enriched_concepts: List[StudentCurriculumConcept] = []
        for c in graph.concepts:
            cid = str(c.id)
            m = mastery_by_concept.get(cid)
            c_feedbacks = feedback_by_concept.get(cid, [])

            if m:
                score = round(float(m.get("mastery_score", 0.0)), 4)
                score = max(0.0, min(1.0, score))
                pct = round(float(m.get("mastery_percentage", score * 100.0)), 2)
                conf = round(float(m.get("confidence_score") if m.get("confidence_score") is not None else m.get("confidence", 0.8)), 4)
                conf = max(0.0, min(1.0, conf))
                ev_count = int(m.get("evidence_count", 1))
                m_source = m.get("source", "ai")
                last_eval = m.get("last_evaluated_at")
                if score < 0.40:
                    c_status = "low_mastery"
                elif score < 0.70:
                    c_status = "developing"
                elif score < 0.90:
                    c_status = "strong"
                else:
                    c_status = "high"
            else:
                score = None
                pct = None
                conf = None
                ev_count = 0
                m_source = "unassessed"
                last_eval = None
                c_status = "unassessed"

            recent_fb = c_feedbacks[-1].get("feedback_text") if c_feedbacks else None
            excerpts = [
                str(fb.get("evidence")) for fb in c_feedbacks
                if fb.get("evidence") and len(str(fb.get("evidence")).strip()) >= 5
            ]
            crit_ids = list({str(fb.get("criterion_id")) for fb in c_feedbacks if fb.get("criterion_id")})

            assigned_ids = set()
            assigned_list = []
            history_items = []
            for fb in c_feedbacks:
                sub_id = str(fb.get("submission_id"))
                sub = sub_by_id.get(sub_id) or db.submissions.get(sub_id)
                a_id = sub.assignmentId if sub else None
                a_title = sub.assignmentTitle if sub else "Assignment"
                sub_date = sub.submittedAt if sub else fb.get("created_at")

                if a_id and a_id not in assigned_ids:
                    assigned_ids.add(a_id)
                    assigned_list.append({"id": a_id, "title": a_title, "submittedAt": sub_date})

                override_info = None
                if sub and sub.override and sub.override.isOverridden:
                    override_info = {
                        "overriddenScore": sub.override.overriddenScore,
                        "overriddenBy": sub.override.overriddenBy,
                        "overrideReason": sub.override.overrideReason,
                        "overriddenAt": sub.override.overriddenAt,
                    }

                history_items.append(
                    EvidenceHistoryItem(
                        submission_id=sub_id,
                        assignment_id=a_id,
                        assignment_title=a_title,
                        criterion_id=str(fb.get("criterion_id", "")),
                        score_ratio=round(float(fb.get("score_ratio", 0.0)), 4),
                        confidence=round(float(fb.get("confidence", 0.8)), 4),
                        feedback_text=fb.get("feedback_text") or "",
                        evidence=fb.get("evidence") or "",
                        evaluated_at=fb.get("created_at") or sub_date,
                        source=fb.get("source") or m_source,
                        faculty_override=override_info,
                    )
                )

            enriched_concepts.append(
                StudentCurriculumConcept(
                    id=c.id,
                    concept_id=c.id,
                    name=c.name,
                    description=c.description or "",
                    category=c.category or "Core",
                    difficulty=c.difficulty or "intermediate",
                    pos_x=c.pos_x,
                    pos_y=c.pos_y,
                    position_x=c.pos_x,
                    position_y=c.pos_y,
                    mastery_score=score,
                    mastery_percentage=pct,
                    confidence_score=conf,
                    confidence=conf,
                    evidence_count=ev_count,
                    mastery_source=m_source,
                    last_evaluated_at=last_eval,
                    status=c_status,
                    feedback=ConceptFeedbackSummary(
                        recent_feedback=recent_fb,
                        evidence_excerpts=excerpts,
                        related_criterion_ids=crit_ids,
                        associated_assignment_ids=list(assigned_ids),
                        associated_assignments=assigned_list,
                        history=history_items,
                    ),
                )
            )

        enriched_edges = [
            StudentPrerequisiteEdge(
                id=e.id,
                from_concept=e.from_concept,
                to_concept=e.to_concept,
                source_concept_id=e.from_concept,
                target_concept_id=e.to_concept,
            )
            for e in graph.edges
        ]

        return StudentCurriculumGraph(
            course_id=course.id,
            course_code=course.code,
            course_name=course.name,
            course_description=course.description or "",
            student_id=student_id,
            student_name=student_name,
            student_email=student_email,
            concepts=enriched_concepts,
            edges=enriched_edges,
        )


    @staticmethod
    def is_student_enrolled(course_id: str, student_id: str) -> bool:
        """
        Verifies whether student_id is enrolled in course_id.
        """
        if student_id == DEV_STUDENT_ID and course_id in [
            "c1010000-0000-0000-0000-000000000001",
            "a3010000-0000-0000-0000-000000000002",
        ]:
            return True

        client = get_supabase_client()
        if client:
            try:
                res = (
                    client.table("enrollments")
                    .select("course_id")
                    .eq("course_id", course_id)
                    .eq("student_id", student_id)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    return True
            except Exception as e:
                logger.warning(f"Supabase is_student_enrolled check failed: {e}")

        return any(
            e.get("course_id") == course_id and e.get("student_id") == student_id
            for e in db.enrollments
        )

    @staticmethod
    def get_assignments_for_course(
        course_id: str,
        status_filter: Optional[str] = None,
    ) -> List[Assignment]:
        """
        Returns assignments for a course, optionally filtered by status ('published', 'draft', etc.).
        Populates targeted curriculum concepts and criteria concept mappings.
        """
        results: List[Assignment] = []
        client = get_supabase_client()
        if client:
            try:
                q = client.table("assignments").select("*").eq("course_id", course_id)
                if status_filter:
                    q = q.eq("status", status_filter)
                res = q.order("created_at", desc=True).execute()
                rows = res.data or []
                for row in rows:
                    assign_id = str(row["id"])
                    c_res = (
                        client.table("assignment_concepts")
                        .select("concept_id, concepts(*)")
                        .eq("assignment_id", assign_id)
                        .execute()
                    )
                    concept_ids = [str(r["concept_id"]) for r in (c_res.data or [])]
                    concepts = []
                    for r in (c_res.data or []):
                        if r.get("concepts"):
                            c_data = r["concepts"]
                            concepts.append(
                                Concept(
                                    id=str(c_data["id"]),
                                    courseId=str(c_data["course_id"]),
                                    name=c_data["name"],
                                    description=c_data.get("description", "") or "",
                                    category=c_data.get("category", "") or "",
                                    difficulty=c_data.get("difficulty", "intermediate"),
                                    posX=float(c_data.get("pos_x", 0.0)),
                                    posY=float(c_data.get("pos_y", 0.0)),
                                    createdAt=str(c_data.get("created_at", "")),
                                )
                            )
                    crit_res = (
                        client.table("assignment_criterion_concepts")
                        .select("criterion_id, concept_id, concepts(name)")
                        .eq("assignment_id", assign_id)
                        .execute()
                    )
                    crit_maps = []
                    for cr in (crit_res.data or []):
                        c_name = None
                        if cr.get("concepts"):
                            c_name = cr["concepts"].get("name")
                        crit_maps.append(
                            CriterionConceptMap(
                                criterionId=cr["criterion_id"],
                                conceptId=str(cr["concept_id"]),
                                conceptName=c_name,
                            )
                        )
                    sub_count_res = (
                        client.table("submissions")
                        .select("id", count="exact")
                        .eq("assignment_id", assign_id)
                        .execute()
                    )
                    sub_count = sub_count_res.count or 0

                    results.append(
                        Assignment(
                            id=assign_id,
                            courseId=str(row["course_id"]),
                            title=row["title"],
                            description=row.get("description", "") or "",
                            dueDate=str(row.get("due_date", "")),
                            maxPoints=float(row.get("max_points", 100.0)),
                            status=row.get("status", "published"),
                            rubricId=row.get("rubric_id"),
                            createdBy=str(row["created_by"]) if row.get("created_by") else None,
                            createdAt=str(row.get("created_at", "")),
                            updatedAt=str(row["updated_at"]) if row.get("updated_at") else None,
                            conceptIds=concept_ids,
                            concepts=concepts,
                            criterionConcepts=crit_maps,
                            submissionsCount=sub_count,
                        )
                    )
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Supabase get_assignments_for_course failed: {e}")

        # Fallback to in-memory store
        course_assigns = [
            copy.deepcopy(a)
            for a in db.assignments.values()
            if a.course_id == course_id and (not status_filter or a.status == status_filter)
        ]
        course_assigns.sort(key=lambda a: a.created_at, reverse=True)
        for a in course_assigns:
            a.concepts = [
                copy.deepcopy(db.concepts[cid])
                for cid in a.concept_ids
                if cid in db.concepts
            ]
            a.submissions_count = sum(
                1 for s in db.submissions.values() if s.assignmentId == a.id
            )
            for cc in a.criterion_concepts:
                if cc.concept_id in db.concepts and not cc.concept_name:
                    cc.concept_name = db.concepts[cc.concept_id].name
        return course_assigns

    @staticmethod
    def get_assignment_by_id(assignment_id: str) -> Optional[Assignment]:
        """
        Retrieves a single assignment by its UUID or identifier.
        """
        client = get_supabase_client()
        if client:
            try:
                res = client.table("assignments").select("*").eq("id", assignment_id).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    c_res = (
                        client.table("assignment_concepts")
                        .select("concept_id, concepts(*)")
                        .eq("assignment_id", assignment_id)
                        .execute()
                    )
                    concept_ids = [str(r["concept_id"]) for r in (c_res.data or [])]
                    concepts = []
                    for r in (c_res.data or []):
                        if r.get("concepts"):
                            c_data = r["concepts"]
                            concepts.append(
                                Concept(
                                    id=str(c_data["id"]),
                                    courseId=str(c_data["course_id"]),
                                    name=c_data["name"],
                                    description=c_data.get("description", "") or "",
                                    category=c_data.get("category", "") or "",
                                    difficulty=c_data.get("difficulty", "intermediate"),
                                    posX=float(c_data.get("pos_x", 0.0)),
                                    posY=float(c_data.get("pos_y", 0.0)),
                                    createdAt=str(c_data.get("created_at", "")),
                                )
                            )
                    crit_res = (
                        client.table("assignment_criterion_concepts")
                        .select("criterion_id, concept_id, concepts(name)")
                        .eq("assignment_id", assignment_id)
                        .execute()
                    )
                    crit_maps = []
                    for cr in (crit_res.data or []):
                        c_name = None
                        if cr.get("concepts"):
                            c_name = cr["concepts"].get("name")
                        crit_maps.append(
                            CriterionConceptMap(
                                criterionId=cr["criterion_id"],
                                conceptId=str(cr["concept_id"]),
                                conceptName=c_name,
                            )
                        )
                    sub_count_res = (
                        client.table("submissions")
                        .select("id", count="exact")
                        .eq("assignment_id", assignment_id)
                        .execute()
                    )
                    sub_count = sub_count_res.count or 0

                    return Assignment(
                        id=str(row["id"]),
                        courseId=str(row["course_id"]),
                        title=row["title"],
                        description=row.get("description", "") or "",
                        dueDate=str(row.get("due_date", "")),
                        maxPoints=float(row.get("max_points", 100.0)),
                        status=row.get("status", "published"),
                        rubricId=row.get("rubric_id"),
                        createdBy=str(row["created_by"]) if row.get("created_by") else None,
                        createdAt=str(row.get("created_at", "")),
                        updatedAt=str(row["updated_at"]) if row.get("updated_at") else None,
                        conceptIds=concept_ids,
                        concepts=concepts,
                        criterionConcepts=crit_maps,
                        submissionsCount=sub_count,
                    )
            except Exception as e:
                logger.warning(f"Supabase get_assignment_by_id failed: {e}")

        # In-memory lookup
        if assignment_id in db.assignments:
            a = copy.deepcopy(db.assignments[assignment_id])
            a.concepts = [
                copy.deepcopy(db.concepts[cid])
                for cid in a.concept_ids
                if cid in db.concepts
            ]
            a.submissions_count = sum(
                1 for s in db.submissions.values() if s.assignmentId == a.id
            )
            for cc in a.criterion_concepts:
                if cc.concept_id in db.concepts and not cc.concept_name:
                    cc.concept_name = db.concepts[cc.concept_id].name
            return a
        return None

    @staticmethod
    def create_assignment(
        course_id: str,
        assignment_in: AssignmentCreate,
        faculty_id: str,
    ) -> Assignment:
        """
        Creates an assignment for a course, strictly verifying course ownership,
        concept course-isolation, and rubric criteria consistency.
        """
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        # 1. Verify concept course-isolation: ALL mapped concepts MUST belong to this course
        if assignment_in.concept_ids:
            for cid in assignment_in.concept_ids:
                concept = db.concepts.get(cid)
                if not concept:
                    client = get_supabase_client()
                    if client:
                        c_res = client.table("concepts").select("*").eq("id", cid).execute()
                        if c_res.data:
                            row = c_res.data[0]
                            concept = Concept(
                                id=str(row["id"]),
                                courseId=str(row["course_id"]),
                                name=row["name"],
                            )
                if not concept or concept.course_id != course_id:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="INVALID_CONCEPT_MAPPING",
                        message=f"Concept '{cid}' does not belong to course '{course_id}'. Cross-course concept mapping is strictly forbidden.",
                    )

        # 2. Verify criterion concepts: concept belongs to course, and criterion belongs to rubric
        rubric = None
        if assignment_in.rubric_id:
            rubric = Repository.get_rubric_by_id(assignment_in.rubric_id)
            if not rubric:
                raise APIException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="RUBRIC_NOT_FOUND",
                    message=f"Referenced rubric '{assignment_in.rubric_id}' was not found.",
                )

        if assignment_in.criterion_concepts:
            if not assignment_in.rubric_id:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="RUBRIC_REQUIRED_FOR_CRITERIA",
                    message="An assignment must have an associated rubric to map criterion concepts.",
                )
            for cc in assignment_in.criterion_concepts:
                concept = db.concepts.get(cc.concept_id)
                if not concept:
                    client = get_supabase_client()
                    if client:
                        c_res = client.table("concepts").select("*").eq("id", cc.concept_id).execute()
                        if c_res.data:
                            row = c_res.data[0]
                            concept = Concept(
                                id=str(row["id"]),
                                courseId=str(row["course_id"]),
                                name=row["name"],
                            )
                if not concept or concept.course_id != course_id:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="INVALID_CRITERION_CONCEPT",
                        message=f"Concept '{cc.concept_id}' mapped to criterion '{cc.criterion_id}' does not belong to course '{course_id}'.",
                    )
                if rubric:
                    valid_crit_ids = [c.id for c in rubric.criteria]
                    if cc.criterion_id not in valid_crit_ids:
                        raise APIException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="INVALID_RUBRIC_CRITERION",
                            message=f"Criterion '{cc.criterion_id}' does not belong to rubric '{assignment_in.rubric_id}'.",
                        )

        new_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        all_concept_ids = list(dict.fromkeys(
            assignment_in.concept_ids + [cc.concept_id for cc in assignment_in.criterion_concepts]
        ))

        enriched_crit_concepts = []
        for cc in assignment_in.criterion_concepts:
            c_name = cc.concept_name
            if not c_name and cc.concept_id in db.concepts:
                c_name = db.concepts[cc.concept_id].name
            enriched_crit_concepts.append(
                CriterionConceptMap(
                    criterionId=cc.criterion_id,
                    conceptId=cc.concept_id,
                    conceptName=c_name,
                )
            )

        client = get_supabase_client()
        if client:
            try:
                client.table("assignments").insert({
                    "id": new_id,
                    "course_id": course_id,
                    "title": assignment_in.title,
                    "description": assignment_in.description,
                    "due_date": assignment_in.due_date,
                    "max_points": assignment_in.max_points,
                    "status": assignment_in.status,
                    "rubric_id": assignment_in.rubric_id,
                    "created_by": faculty_id,
                }).execute()

                for cid in all_concept_ids:
                    client.table("assignment_concepts").insert({
                        "assignment_id": new_id,
                        "concept_id": cid,
                    }).execute()

                for cc in enriched_crit_concepts:
                    client.table("assignment_criterion_concepts").insert({
                        "assignment_id": new_id,
                        "criterion_id": cc.criterion_id,
                        "concept_id": cc.concept_id,
                    }).execute()
            except Exception as e:
                logger.warning(f"Supabase create_assignment failed: {e}")

        concepts = [
            copy.deepcopy(db.concepts[cid])
            for cid in all_concept_ids
            if cid in db.concepts
        ]
        created_assign = Assignment(
            id=new_id,
            courseId=course_id,
            title=assignment_in.title,
            description=assignment_in.description,
            dueDate=assignment_in.due_date,
            maxPoints=assignment_in.max_points,
            status=assignment_in.status,
            rubricId=assignment_in.rubric_id,
            createdBy=faculty_id,
            createdAt=now_iso,
            conceptIds=all_concept_ids,
            concepts=concepts,
            criterionConcepts=enriched_crit_concepts,
            submissionsCount=0,
        )
        db.assignments[new_id] = copy.deepcopy(created_assign)

        if course_id in db.courses:
            db.courses[course_id].assignments_count = len([
                a for a in db.assignments.values() if a.course_id == course_id
            ])

        return created_assign

    @staticmethod
    def update_assignment(
        assignment_id: str,
        update_in: AssignmentUpdate,
    ) -> Optional[Assignment]:
        """
        Updates assignment details, status (draft/published), rubric, or concept mappings.
        """
        existing = Repository.get_assignment_by_id(assignment_id)
        if not existing:
            return None

        course_id = existing.course_id
        target_rubric_id = update_in.rubric_id if update_in.rubric_id is not None else existing.rubric_id

        if update_in.concept_ids is not None:
            for cid in update_in.concept_ids:
                concept = db.concepts.get(cid)
                if not concept or concept.course_id != course_id:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="INVALID_CONCEPT_MAPPING",
                        message=f"Concept '{cid}' does not belong to course '{course_id}'.",
                    )

        rubric = None
        if target_rubric_id:
            rubric = Repository.get_rubric_by_id(target_rubric_id)

        remaining_criterion_concepts = (
            update_in.criterion_concepts
            if update_in.criterion_concepts is not None
            else existing.criterion_concepts
        )
        if not target_rubric_id and remaining_criterion_concepts:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="RUBRIC_REQUIRED_FOR_CRITERIA",
                message="Cannot remove rubric while criterion concept mappings exist. Remove criterion mappings first.",
            )

        if target_rubric_id and target_rubric_id != existing.rubric_id and remaining_criterion_concepts:
            valid_crit_ids = {c.id for c in rubric.criteria} if rubric else set()
            for cc in remaining_criterion_concepts:
                if cc.criterion_id not in valid_crit_ids:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="INCOMPATIBLE_RUBRIC_CHANGE",
                        message=f"Cannot change rubric: criterion '{cc.criterion_id}' is not present in new rubric '{target_rubric_id}'.",
                    )

        if update_in.criterion_concepts is not None:
            for cc in update_in.criterion_concepts:
                concept = db.concepts.get(cc.concept_id)
                if not concept or concept.course_id != course_id:
                    raise APIException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="INVALID_CRITERION_CONCEPT",
                        message=f"Concept '{cc.concept_id}' does not belong to course '{course_id}'.",
                    )
                if rubric:
                    valid_crit_ids = [c.id for c in rubric.criteria]
                    if cc.criterion_id not in valid_crit_ids:
                        raise APIException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="INVALID_RUBRIC_CRITERION",
                            message=f"Criterion '{cc.criterion_id}' is not in rubric '{target_rubric_id}'.",
                        )

        now_iso = datetime.now(timezone.utc).isoformat()
        client = get_supabase_client()
        if client:
            try:
                update_fields = {"updated_at": now_iso}
                if update_in.title is not None:
                    update_fields["title"] = update_in.title
                if update_in.description is not None:
                    update_fields["description"] = update_in.description
                if update_in.due_date is not None:
                    update_fields["due_date"] = update_in.due_date
                if update_in.max_points is not None:
                    update_fields["max_points"] = update_in.max_points
                if update_in.status is not None:
                    update_fields["status"] = update_in.status
                if update_in.rubric_id is not None:
                    update_fields["rubric_id"] = update_in.rubric_id

                client.table("assignments").update(update_fields).eq("id", assignment_id).execute()

                if update_in.concept_ids is not None:
                    client.table("assignment_concepts").delete().eq("assignment_id", assignment_id).execute()
                    for cid in update_in.concept_ids:
                        client.table("assignment_concepts").insert({
                            "assignment_id": assignment_id,
                            "concept_id": cid,
                        }).execute()

                if update_in.criterion_concepts is not None:
                    client.table("assignment_criterion_concepts").delete().eq("assignment_id", assignment_id).execute()
                    for cc in update_in.criterion_concepts:
                        client.table("assignment_criterion_concepts").insert({
                            "assignment_id": assignment_id,
                            "criterion_id": cc.criterion_id,
                            "concept_id": cc.concept_id,
                        }).execute()
            except Exception as e:
                logger.warning(f"Supabase update_assignment failed: {e}")

        if assignment_id in db.assignments:
            a = db.assignments[assignment_id]
            if update_in.title is not None:
                a.title = update_in.title
            if update_in.description is not None:
                a.description = update_in.description
            if update_in.due_date is not None:
                a.due_date = update_in.due_date
            if update_in.max_points is not None:
                a.max_points = update_in.max_points
            if update_in.status is not None:
                a.status = update_in.status
            if update_in.rubric_id is not None:
                a.rubric_id = update_in.rubric_id
            if update_in.concept_ids is not None:
                a.concept_ids = list(update_in.concept_ids)
            if update_in.criterion_concepts is not None:
                a.criterion_concepts = copy.deepcopy(update_in.criterion_concepts)
                for cc in a.criterion_concepts:
                    if cc.concept_id in db.concepts and not cc.concept_name:
                        cc.concept_name = db.concepts[cc.concept_id].name
            a.updated_at = now_iso

        return Repository.get_assignment_by_id(assignment_id)

    @staticmethod
    def delete_assignment(assignment_id: str) -> bool:
        """
        Deletes an assignment and updates course counts.
        """
        existing = Repository.get_assignment_by_id(assignment_id)
        if not existing:
            return False

        client = get_supabase_client()
        if client:
            try:
                client.table("assignments").delete().eq("id", assignment_id).execute()
            except Exception as e:
                logger.warning(f"Supabase delete_assignment failed: {e}")

        course_id = existing.course_id
        if assignment_id in db.assignments:
            del db.assignments[assignment_id]

        if course_id in db.courses:
            db.courses[course_id].assignments_count = len([
                a for a in db.assignments.values() if a.course_id == course_id
            ])

        return True

    @staticmethod
    def get_student_assignments(
        student_id: str,
        course_id: Optional[str] = None,
    ) -> List[StudentAssignment]:
        """
        Lists all published assignments for courses the student is enrolled in,
        populated with rubric details, mapped concepts, and current submission status.
        Draft assignments are strictly excluded.
        """
        enrolled_course_ids = set()
        client = get_supabase_client()
        if client:
            try:
                res = client.table("enrollments").select("course_id").eq("student_id", student_id).execute()
                for r in (res.data or []):
                    enrolled_course_ids.add(str(r["course_id"]))
            except Exception as e:
                logger.warning(f"Supabase fetch enrollments failed: {e}")

        for e in db.enrollments:
            if e.get("student_id") == student_id:
                enrolled_course_ids.add(e.get("course_id"))

        if student_id == DEV_STUDENT_ID:
            enrolled_course_ids.add("c1010000-0000-0000-0000-000000000001")
            enrolled_course_ids.add("a3010000-0000-0000-0000-000000000002")

        if course_id:
            if course_id not in enrolled_course_ids:
                return []
            target_course_ids = [course_id]
        else:
            target_course_ids = list(enrolled_course_ids)

        student_assignments: List[StudentAssignment] = []

        for cid in target_course_ids:
            course = Repository.get_course_by_id(cid)
            if not course:
                continue

            assigns = Repository.get_assignments_for_course(cid, status_filter="published")

            subs, _ = Repository.get_submissions(student_id=student_id, limit=200)
            subs_by_assign = {}
            for s in subs:
                subs_by_assign[s.assignmentId] = s

            for a in assigns:
                sub = subs_by_assign.get(a.id)
                sub_status = "unsubmitted"
                sub_id = None
                submitted_at = None
                score = None

                if sub:
                    sub_id = sub.id
                    submitted_at = sub.submittedAt
                    if sub.status == JobStatus.DONE:
                        sub_status = "graded"
                        score = sub.override.overriddenScore if sub.override and sub.override.isOverridden else (
                            sub.evaluation.score if sub.evaluation else None
                        )
                    elif sub.status == JobStatus.PROCESSING:
                        sub_status = "processing"
                    elif sub.status == JobStatus.FLAGGED:
                        sub_status = "flagged"
                    else:
                        sub_status = "pending"

                rubric = Repository.get_rubric_by_id(a.rubric_id) if a.rubric_id else None

                student_assignments.append(
                    StudentAssignment(
                        id=a.id,
                        courseId=course.id,
                        courseCode=course.code,
                        courseName=course.name,
                        title=a.title,
                        description=a.description,
                        dueDate=a.due_date,
                        maxPoints=a.max_points,
                        status=a.status,
                        rubricId=a.rubric_id,
                        rubric=rubric,
                        concepts=a.concepts,
                        criterionConcepts=a.criterion_concepts,
                        submissionStatus=sub_status,
                        submissionId=sub_id,
                        submittedAt=submitted_at,
                        score=score,
                    )
                )

        student_assignments.sort(key=lambda sa: sa.due_date)
        return student_assignments

    @staticmethod
    def remove_submission_override(
        submission_id: str,
        faculty_user_id: str,
        faculty_user_name: str,
        reason: str = "Faculty override revoked. Reverted to original AI evaluation.",
    ) -> Optional[Submission]:
        """
        Removes an active submission override, records revocation in faculty_overrides audit log,
        and recomputes student concept mastery from authoritative historical evidence.
        """
        sub = Repository.get_submission_by_id(submission_id)
        if not sub:
            return None

        orig_score = sub.evaluation.score if sub.evaluation else 0.0
        override = FacultyOverride(
            isOverridden=False,
            originalScore=orig_score,
            overriddenScore=orig_score,
            overriddenById=faculty_user_id,
            overriddenByName=faculty_user_name,
            overriddenBy=faculty_user_name,
            overrideReason=reason,
            overriddenAt=datetime.now(timezone.utc).isoformat(),
            criterionAdjustments=None,
        )
        return Repository.override_submission_grade(
            submission_id=submission_id,
            override=override,
            faculty_user_id=faculty_user_id,
        )

    @staticmethod
    def override_concept_mastery(
        course_id: str,
        student_id: str,
        concept_id: str,
        mastery_score: float,
        confidence_score: float,
        override_reason: str,
        faculty_user_id: str,
        faculty_user_name: str,
    ) -> Dict[str, Any]:
        """
        Directly overrides a student's concept mastery score with mandatory audit justification.
        Persists into student_concept_mastery with source='faculty_override' and logs to faculty_overrides.
        """
        clamped_mastery = max(0.0, min(1.0, round(float(mastery_score), 4)))
        clamped_conf = max(0.0, min(1.0, round(float(confidence_score), 4)))
        now_iso = datetime.now(timezone.utc).isoformat()

        # Update in-memory mastery_records
        existing = next(
            (m for m in db.mastery_records if str(m.get("student_id")) == str(student_id) and str(m.get("concept_id")) == str(concept_id)),
            None
        )
        mastery_payload = {
            "student_id": student_id,
            "concept_id": concept_id,
            "mastery_score": clamped_mastery,
            "mastery_percentage": round(clamped_mastery * 100.0, 2),
            "confidence_score": clamped_conf,
            "source": "faculty_override",
            "evidence_count": (existing.get("evidence_count", 0) + 1) if existing else 1,
            "last_evaluated_at": now_iso,
            "updated_at": now_iso,
        }
        if existing:
            existing.update(mastery_payload)
        else:
            db.mastery_records.append({**mastery_payload, "id": str(uuid.uuid4()), "created_at": now_iso})

        # Log audit in faculty_overrides
        fo_row = {
            "id": str(uuid.uuid4()),
            "target_type": "concept_mastery",
            "concept_id": concept_id,
            "student_id": student_id,
            "submission_id": None,
            "is_overridden": True,
            "original_score": existing.get("mastery_score", 0.0) if existing else 0.0,
            "overridden_score": clamped_mastery,
            "overridden_by": faculty_user_id,
            "overridden_by_name": faculty_user_name,
            "override_reason": override_reason,
            "criterion_adjustments": None,
            "overridden_at": now_iso,
        }
        if hasattr(db, "faculty_overrides"):
            db.faculty_overrides.append(fo_row)

        client = get_supabase_client()
        if client:
            try:
                client.table("student_concept_mastery").upsert(
                    mastery_payload,
                    on_conflict="student_id,concept_id"
                ).execute()
                client.table("faculty_overrides").insert(fo_row).execute()
            except Exception as e:
                logger.warning(f"Supabase concept mastery override failed: {e}")

        return {
            "studentId": student_id,
            "conceptId": concept_id,
            "masteryScore": clamped_mastery,
            "masteryPercentage": round(clamped_mastery * 100.0, 2),
            "confidenceScore": clamped_conf,
            "source": "faculty_override",
            "overriddenBy": faculty_user_name,
            "overrideReason": override_reason,
            "overriddenAt": now_iso,
        }

    @staticmethod
    def remove_concept_mastery_override(
        course_id: str,
        student_id: str,
        concept_id: str,
        override_reason: str,
        faculty_user_id: str,
        faculty_user_name: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Removes direct concept mastery override, logs revocation in faculty_overrides,
        and recomputes pure AI-derived mastery from authoritative evidence in submission_concept_feedback.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        fo_row = {
            "id": str(uuid.uuid4()),
            "target_type": "concept_mastery",
            "concept_id": concept_id,
            "student_id": student_id,
            "submission_id": None,
            "is_overridden": False,
            "original_score": 0.0,
            "overridden_score": 0.0,
            "overridden_by": faculty_user_id,
            "overridden_by_name": faculty_user_name,
            "override_reason": override_reason or "Faculty concept mastery override revoked.",
            "criterion_adjustments": None,
            "overridden_at": now_iso,
        }
        if hasattr(db, "faculty_overrides"):
            db.faculty_overrides.append(fo_row)

        # Force in-memory source from 'faculty_override' to 'ai' prior to recompute
        existing = next(
            (m for m in db.mastery_records if str(m.get("student_id")) == str(student_id) and str(m.get("concept_id")) == str(concept_id)),
            None
        )
        if existing and existing.get("source") == "faculty_override":
            existing["source"] = "ai"

        client = get_supabase_client()
        if client:
            try:
                client.table("faculty_overrides").insert(fo_row).execute()
                client.table("student_concept_mastery").update({"source": "ai"}).eq("student_id", student_id).eq("concept_id", concept_id).execute()
            except Exception as e:
                logger.warning(f"Supabase concept override revocation failed: {e}")

        return Repository.recompute_student_concept_mastery(student_id=student_id, concept_id=concept_id)

    @staticmethod
    def get_course_learning_analytics(course_id: str, faculty_user: Optional[Any] = None) -> CourseLearningAnalytics:
        """
        Computes course-level, student-level, concept-level, and assignment-level learning analytics
        from real persisted database records. Strictly excludes unassessed concepts from average mastery.
        """
        course = Repository.get_course_by_id(course_id)
        if not course:
            raise APIException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                code="COURSE_NOT_FOUND",
                message=f"Course '{course_id}' was not found.",
            )

        if faculty_user and getattr(faculty_user, "role", "") == "faculty":
            if not Repository.is_course_owner_by_id(course.id, faculty_user):
                raise APIException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    code="FORBIDDEN",
                    message=f"You are not authorized to view analytics for course '{course.code}'.",
                )

        enrolled_students = Repository.get_course_enrolled_students(course.id)
        total_enrolled = len(enrolled_students)

        concepts = Repository.get_concepts_for_course(course.id)
        total_concepts = len(concepts)
        concept_ids = [c.id for c in concepts]

        assignments = Repository.get_assignments_for_course(course.id)
        total_assignments = len(assignments)
        published_assignments = sum(1 for a in assignments if a.status == "published")
        draft_assignments = total_assignments - published_assignments

        subs, _ = Repository.get_submissions(course_code=course.code, limit=1000)
        total_submissions = len(subs)
        completed_evaluations = sum(1 for s in subs if s.status == JobStatus.DONE or s.evaluation is not None)
        pending_evaluations = sum(1 for s in subs if s.status in [JobStatus.PENDING, JobStatus.PROCESSING])
        manual_review_submissions = sum(1 for s in subs if getattr(s, "status", "") == "manual_review" or getattr(s, "status", "") == JobStatus.FLAGGED)

        completed_scores = []
        for s in subs:
            if s.override and s.override.isOverridden:
                max_pts = s.evaluation.maxScore if s.evaluation else 100.0
                completed_scores.append((s.override.overriddenScore / max_pts) * 100.0 if max_pts > 0 else 0.0)
            elif s.evaluation and s.evaluation.maxScore > 0:
                completed_scores.append((s.evaluation.score / s.evaluation.maxScore) * 100.0)

        average_assignment_score = round(sum(completed_scores) / len(completed_scores), 1) if completed_scores else 0.0

        assessed_concept_ids = set()
        for st in enrolled_students:
            s_mastery = Repository.get_student_mastery(st["student_id"])
            for m in s_mastery:
                cid = str(m.get("concept_id"))
                if cid in concept_ids and m.get("mastery_score") is not None:
                    assessed_concept_ids.add(cid)

        concept_coverage_pct = round((len(assessed_concept_ids) / total_concepts) * 100.0, 1) if total_concepts > 0 else 0.0

        # Student Progress Summary
        student_progress: List[StudentProgressSummary] = []
        for st in enrolled_students:
            sid = st["student_id"]
            s_name = st["student_name"]
            s_email = st["student_email"]
            s_mastery_list = Repository.get_student_mastery(sid)
            s_mastery_map = {str(m.get("concept_id")): m for m in s_mastery_list if str(m.get("concept_id")) in concept_ids}

            assessed_count = 0
            low_count = 0
            dev_count = 0
            strong_count = 0
            mastery_sum = 0.0

            for c in concepts:
                m = s_mastery_map.get(str(c.id))
                if m and m.get("mastery_score") is not None:
                    score = float(m.get("mastery_score", 0.0))
                    assessed_count += 1
                    mastery_sum += score * 100.0
                    if score < 0.40:
                        low_count += 1
                    elif score < 0.70:
                        dev_count += 1
                    else:
                        strong_count += 1

            unassessed_count = total_concepts - assessed_count
            cov_pct = round((assessed_count / total_concepts) * 100.0, 1) if total_concepts > 0 else 0.0
            avg_m = round(mastery_sum / assessed_count, 1) if assessed_count > 0 else 0.0

            student_progress.append(
                StudentProgressSummary(
                    studentId=sid,
                    studentName=s_name,
                    studentEmail=s_email,
                    totalConcepts=total_concepts,
                    assessedConcepts=assessed_count,
                    coveragePercentage=cov_pct,
                    averageMastery=avg_m,
                    lowMasteryCount=low_count,
                    developingCount=dev_count,
                    strongCount=strong_count,
                    unassessedCount=unassessed_count,
                )
            )

        # Concept Analytics Summary
        concept_analytics: List[ConceptAnalyticsSummary] = []
        for c in concepts:
            cid = str(c.id)
            c_assessed_scores = []
            c_low = 0
            c_dev = 0
            c_strong = 0

            for st in enrolled_students:
                sid = st["student_id"]
                s_mastery_list = Repository.get_student_mastery(sid)
                m = next((m for m in s_mastery_list if str(m.get("concept_id")) == cid), None)
                if m and m.get("mastery_score") is not None:
                    score = float(m.get("mastery_score", 0.0))
                    c_assessed_scores.append(score * 100.0)
                    if score < 0.40:
                        c_low += 1
                    elif score < 0.70:
                        c_dev += 1
                    else:
                        c_strong += 1

            c_assessed_count = len(c_assessed_scores)
            c_unassessed_count = total_enrolled - c_assessed_count
            c_avg_m = round(sum(c_assessed_scores) / c_assessed_count, 1) if c_assessed_count > 0 else 0.0

            needs_attention = False
            attention_reason = None
            if c_assessed_count > 0:
                if c_avg_m < 50.0:
                    needs_attention = True
                    attention_reason = f"Low average mastery ({c_avg_m}%)"
                elif (c_low / c_assessed_count) >= 0.30:
                    needs_attention = True
                    attention_reason = f"{round((c_low / c_assessed_count) * 100)}% of assessed students in low mastery"
            elif total_enrolled > 0:
                needs_attention = True
                attention_reason = "No students assessed yet"

            concept_analytics.append(
                ConceptAnalyticsSummary(
                    conceptId=cid,
                    name=c.name,
                    category=c.category,
                    difficulty=c.difficulty,
                    assessedStudentsCount=c_assessed_count,
                    unassessedStudentsCount=c_unassessed_count,
                    averageMastery=c_avg_m,
                    lowMasteryCount=c_low,
                    developingCount=c_dev,
                    strongHighCount=c_strong,
                    needsAttention=needs_attention,
                    attentionReason=attention_reason,
                )
            )

        # Assignment Analytics Summary
        assignment_analytics: List[AssignmentAnalyticsSummary] = []
        for a in assignments:
            a_subs = [s for s in subs if str(s.assignmentId) == str(a.id)]
            a_sub_count = len(a_subs)
            a_done = [s for s in a_subs if s.status == JobStatus.DONE or s.evaluation is not None]
            a_comp_rate = round((len(a_done) / a_sub_count) * 100.0, 1) if a_sub_count > 0 else 0.0
            a_manual = sum(1 for s in a_subs if getattr(s, "status", "") == "manual_review" or getattr(s, "status", "") == JobStatus.FLAGGED)

            a_scores = []
            score_dist = {"<60": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
            for s in a_done:
                val = None
                if s.override and s.override.isOverridden:
                    max_p = s.evaluation.maxScore if s.evaluation else getattr(a, 'max_points', getattr(a, 'maxPoints', 100.0)) or 100.0
                    val = (s.override.overriddenScore / max_p) * 100.0 if max_p > 0 else 0.0
                elif s.evaluation and s.evaluation.maxScore > 0:
                    val = (s.evaluation.score / s.evaluation.maxScore) * 100.0

                if val is not None:
                    a_scores.append(val)
                    if val < 60.0:
                        score_dist["<60"] += 1
                    elif val < 70.0:
                        score_dist["60-69"] += 1
                    elif val < 80.0:
                        score_dist["70-79"] += 1
                    elif val < 90.0:
                        score_dist["80-89"] += 1
                    else:
                        score_dist["90-100"] += 1

            a_avg_score = round(sum(a_scores) / len(a_scores), 1) if a_scores else 0.0

            assignment_analytics.append(
                AssignmentAnalyticsSummary(
                    assignmentId=str(a.id),
                    title=getattr(a, "title", "Assignment"),
                    dueDate=getattr(a, "due_date", getattr(a, "dueDate", None)),
                    maxMarks=float(getattr(a, "max_points", getattr(a, "maxPoints", 100.0)) or 100.0),
                    status=getattr(a, "status", "published"),
                    submissionCount=a_sub_count,
                    completionRate=a_comp_rate,
                    averageScore=a_avg_score,
                    scoreDistribution=score_dist,
                    manualReviewCount=a_manual,
                )
            )

        overview = CourseOverviewAnalytics(
            courseId=course.id,
            courseCode=course.code,
            courseName=course.name,
            totalEnrolled=total_enrolled,
            totalAssignments=total_assignments,
            publishedAssignments=published_assignments,
            draftAssignments=draft_assignments,
            totalSubmissions=total_submissions,
            completedEvaluations=completed_evaluations,
            pendingEvaluations=pending_evaluations,
            manualReviewSubmissions=manual_review_submissions,
            averageAssignmentScore=average_assignment_score,
            conceptCoveragePercentage=concept_coverage_pct,
        )

        return CourseLearningAnalytics(
            overview=overview,
            studentProgress=student_progress,
            conceptAnalytics=concept_analytics,
            assignmentAnalytics=assignment_analytics,
        )
