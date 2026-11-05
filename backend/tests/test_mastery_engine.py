import pytest
import uuid
from app.models.common import JobStatus
from app.models.submission import Submission
from app.models.evaluation import EvaluationResult, CriterionEvaluation
from app.models.assignment import Assignment, CriterionConceptMap
from app.models.curriculum import Concept
from app.services.repository import Repository, db


def make_submission(**kwargs) -> Submission:
    defaults = {
        "id": f"sub-{uuid.uuid4().hex[:6]}",
        "studentId": f"student-{uuid.uuid4().hex[:6]}",
        "studentName": "Alex Student",
        "studentEmail": "alex@university.edu",
        "assignmentId": f"assign-{uuid.uuid4().hex[:6]}",
        "assignmentTitle": "Assignment 1",
        "courseCode": "CS101",
        "fileName": "solution.py",
        "fileSize": "12 KB",
        "fileType": "text",
        "status": JobStatus.DONE,
        "submittedAt": "2026-11-05T00:00:00Z",
        "rubricId": "rub-1",
    }
    defaults.update(kwargs)
    return Submission(**defaults)


def make_assignment(**kwargs) -> Assignment:
    defaults = {
        "id": f"assign-{uuid.uuid4().hex[:6]}",
        "course_id": "CS101",
        "title": "DP Assignment 1",
        "dueDate": "2026-12-01T23:59:59Z",
        "maxPoints": 100.0,
        "status": "published",
        "rubric_id": "rub-1",
        "concept_ids": [],
        "criterion_concepts": [],
    }
    defaults.update(kwargs)
    return Assignment(**defaults)


def make_evaluation(**kwargs) -> EvaluationResult:
    defaults = {
        "score": 100.0,
        "maxScore": 100.0,
        "percentage": 100.0,
        "summaryFeedback": "Feedback",
        "strengths": [],
        "improvements": [],
        "criteriaScores": [],
        "evaluatedAt": "2026-11-05T00:00:00Z",
    }
    defaults.update(kwargs)
    return EvaluationResult(**defaults)


@pytest.fixture(autouse=True)
def clean_test_db():
    orig_submissions = dict(db.submissions)
    orig_mastery = list(db.mastery_records)
    orig_assignments = dict(db.assignments)
    orig_crit_concepts = dict(db.assignment_criterion_concepts)
    orig_concepts = dict(db.concepts)

    yield

    db.submissions = orig_submissions
    db.mastery_records = orig_mastery
    db.assignments = orig_assignments
    db.assignment_criterion_concepts = orig_crit_concepts
    db.concepts = orig_concepts


def test_initial_concept_evidence_calculation():
    """
    Test 1: Initial Evidence (N = 0)
    Student gets 100% (E = 1.0) on an assignment mapped to Concept A.
    Formula: M_1 = (0.50 * 1.0 + 1.0 * 0.80) / (1.0 + 0.80) = 1.30 / 1.80 = 0.7222.
    Confidence: c_1 <= 0.95.
    Evidence count: N = 1.
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    crit1 = f"crit-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Dynamic Programming")
    db.assignment_criterion_concepts[aid] = [
        CriterionConceptMap(criterionId=crit1, conceptId=cid, conceptName="Dynamic Programming")
    ]
    db.assignments[aid] = make_assignment(
        id=aid,
        concept_ids=[cid],
        criterion_concepts=db.assignment_criterion_concepts[aid]
    )

    submission = make_submission(
        id=sid,
        studentId=student_id,
        assignmentId=aid,
    )
    db.submissions[sid] = submission

    evaluation = make_evaluation(
        score=25.0,
        maxScore=25.0,
        percentage=100.0,
        summaryFeedback="Excellent DP solution.",
        strengths=["Optimal substructure identified"],
        improvements=[],
        criteriaScores=[
            CriterionEvaluation(
                criterionId=crit1,
                title="DP Table Formulation",
                scoreAwarded=25.0,
                maxPoints=25.0,
                scoreRatio=1.0,
                evidence="dp = [[0] * (w + 1) for _ in range(n + 1)]",
                reasoning="Correct 2D DP matrix initialization",
                feedback="Flawless DP formulation.",
            )
        ]
    )

    feedback_list = Repository.record_concept_evidence_and_update_mastery(submission, evaluation)
    assert len(feedback_list) == 1
    cf = feedback_list[0]
    assert cf.conceptId == cid
    assert cf.scoreRatio == 1.0
    assert cf.evidenceCount == 1

    # Check calculated mastery and confidence bounds
    assert 0.70 <= cf.masteryContribution <= 0.75
    assert 0.60 <= cf.confidenceScore <= 0.85
    assert cf.masteryContribution <= 1.0
    assert cf.confidenceScore <= 1.0

    # Verify persisted in db.mastery_records
    rec = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec["mastery_score"] == cf.masteryContribution
    assert rec["evidence_count"] == 1
    assert rec["source"] == "ai"


def test_subsequent_assignment_evidence_update():
    """
    Test 2: Subsequent Evidence (N >= 1)
    Student already has M_prior = 0.7222, c_prior = 0.68, N = 1.
    Submits second assignment scoring E = 0.90 (90%).
    W_prior = N * c_prior = 1 * 0.68 = 0.68.
    W_new = 0.80.
    M_new = (0.7222 * 0.68 + 0.90 * 0.80) / (0.68 + 0.80) approx 0.8183.
    N_updated = 2.
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    aid1 = f"assign-{uuid.uuid4().hex[:6]}"
    aid2 = f"assign-{uuid.uuid4().hex[:6]}"
    crit1 = f"crit-{uuid.uuid4().hex[:6]}"
    crit2 = f"crit-{uuid.uuid4().hex[:6]}"
    sid1 = f"sub-{uuid.uuid4().hex[:6]}"
    sid2 = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Graph Algorithms")
    db.assignment_criterion_concepts[aid1] = [CriterionConceptMap(criterionId=crit1, conceptId=cid)]
    db.assignment_criterion_concepts[aid2] = [CriterionConceptMap(criterionId=crit2, conceptId=cid)]

    # Prior state in database
    db.mastery_records.append({
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "concept_id": cid,
        "mastery_score": 0.7222,
        "mastery_percentage": 72.22,
        "confidence_score": 0.68,
        "evidence_count": 1,
        "submission_id": sid1,
        "source": "ai",
    })

    # Second submission
    submission2 = make_submission(
        id=sid2,
        studentId=student_id,
        assignmentId=aid2,
    )
    db.submissions[sid2] = submission2

    evaluation2 = make_evaluation(
        score=18.0,
        maxScore=20.0,
        percentage=90.0,
        summaryFeedback="Good Dijkstra implementation",
        strengths=["Priority queue used correctly"],
        improvements=["Could optimize edge relaxation"],
        criteriaScores=[
            CriterionEvaluation(
                criterionId=crit2,
                title="Dijkstra Shortest Path",
                scoreAwarded=18.0,
                maxPoints=20.0,
                scoreRatio=0.90,
                evidence="heapq.heappush(pq, (d, neighbor))",
                reasoning="Standard min-heap priority queue implementation",
                feedback="Solid graph search logic.",
            )
        ]
    )

    feedback_list = Repository.record_concept_evidence_and_update_mastery(submission2, evaluation2)
    assert len(feedback_list) == 1
    cf = feedback_list[0]
    assert cf.evidenceCount == 2
    assert cf.scoreRatio == 0.90
    assert 0.80 <= cf.masteryContribution <= 0.85
    assert cf.confidenceScore > 0.68
    assert cf.confidenceScore <= 0.99


def test_faculty_override_precedence():
    """
    Test 3: Faculty Override Precedence
    If a faculty member sets an override on mastery (source == 'faculty_override'),
    subsequent AI evaluations MUST NOT overwrite the faculty's score!
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    crit = f"crit-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Recursion")
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit, conceptId=cid)]

    # Faculty had explicitly set mastery to 0.95 with source = faculty_override
    db.mastery_records.append({
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "concept_id": cid,
        "mastery_score": 0.95,
        "mastery_percentage": 95.0,
        "confidence_score": 1.0,
        "evidence_count": 2,
        "submission_id": "prev-sub",
        "source": "faculty_override",
    })

    # Student submits new assignment where AI gives a poor score 40% (0.40)
    submission = make_submission(
        id=sid,
        studentId=student_id,
        assignmentId=aid,
    )
    db.submissions[sid] = submission

    evaluation = make_evaluation(
        score=4.0,
        maxScore=10.0,
        percentage=40.0,
        summaryFeedback="Stack overflow issues",
        strengths=[],
        improvements=["Add base case"],
        criteriaScores=[
            CriterionEvaluation(
                criterionId=crit,
                title="Recursive Base Case",
                scoreAwarded=4.0,
                maxPoints=10.0,
                scoreRatio=0.40,
                evidence="def recurse(n): return recurse(n-1)",
                reasoning="Missing base case",
                feedback="Infinite recursion.",
            )
        ]
    )

    feedback_list = Repository.record_concept_evidence_and_update_mastery(submission, evaluation)
    assert len(feedback_list) == 1
    cf = feedback_list[0]

    # Faculty override score of 0.95 MUST be preserved
    assert cf.masteryContribution == 0.95
    assert cf.confidenceScore == 1.0

    rec = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec["mastery_score"] == 0.95
    assert rec["source"] == "faculty_override"
    assert rec["confidence_score"] == 1.0


def test_idempotent_reprocessing():
    """
    Test 4: Idempotency
    Running the mastery engine multiple times on the same submission must NOT
    duplicate evidence counts or alter the mastery calculation.
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    crit = f"crit-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Sorting")
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit, conceptId=cid)]

    submission = make_submission(
        id=sid,
        studentId=student_id,
        assignmentId=aid,
    )
    db.submissions[sid] = submission

    evaluation = make_evaluation(
        score=20.0,
        maxScore=20.0,
        percentage=100.0,
        summaryFeedback="Excellent Quicksort",
        strengths=["Good partition scheme"],
        improvements=[],
        criteriaScores=[
            CriterionEvaluation(
                criterionId=crit,
                title="Lomuto Partition",
                scoreAwarded=20.0,
                maxPoints=20.0,
                scoreRatio=1.0,
                evidence="def partition(arr, low, high):",
                reasoning="Clean Lomuto partition implementation",
                feedback="Great job.",
            )
        ]
    )

    # First run
    fb1 = Repository.record_concept_evidence_and_update_mastery(submission, evaluation)
    rec1 = dict(next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid))

    assert fb1[0].evidenceCount == 1

    # Second run (exact same submission ID)
    fb2 = Repository.record_concept_evidence_and_update_mastery(submission, evaluation)
    rec2 = dict(next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid))

    # Evidence count must NOT increment
    assert fb2[0].evidenceCount == 1
    assert rec2["evidence_count"] == 1
    assert rec1["mastery_score"] == rec2["mastery_score"]
    assert rec1["confidence_score"] == rec2["confidence_score"]


def test_boundary_values_and_clamping():
    """
    Test 5: Boundary Values (0.0 and 1.0)
    Verify mastery score and confidence never fall below 0.0 or exceed 1.0.
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    crit = f"crit-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Bit Manipulation")
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit, conceptId=cid)]

    submission = make_submission(
        id=sid,
        studentId=student_id,
        assignmentId=aid,
    )
    db.submissions[sid] = submission

    eval_zero = make_evaluation(
        score=0.0,
        maxScore=20.0,
        percentage=0.0,
        summaryFeedback="Did not compile",
        strengths=[],
        improvements=["Fix syntax"],
        criteriaScores=[
            CriterionEvaluation(
                criterionId=crit,
                title="Bitmask",
                scoreAwarded=0.0,
                maxPoints=20.0,
                scoreRatio=0.0,
                evidence="",
                reasoning="Syntax error",
                feedback="Failed.",
            )
        ]
    )

    fb_zero = Repository.record_concept_evidence_and_update_mastery(submission, eval_zero)
    m_val = fb_zero[0].masteryContribution
    c_val = fb_zero[0].confidenceScore
    assert 0.0 <= m_val <= 1.0
    assert 0.0 <= c_val <= 1.0


def test_criterion_mapping_scenarios():
    """
    Test 6: Criterion-to-Concept Mapping Scenarios
    - 1:1 mapping
    - 1:many mapping (one criterion to multiple concepts)
    - many:1 mapping (multiple criteria to one concept)
    - unmapped criteria (graded for score, ignored for mastery)
    - unmapped concepts (remain untouched)
    """
    c_algo = f"concept-algo-{uuid.uuid4().hex[:4]}"
    c_ds = f"concept-ds-{uuid.uuid4().hex[:4]}"
    c_untouched = f"concept-untouched-{uuid.uuid4().hex[:4]}"
    aid = f"assign-map-{uuid.uuid4().hex[:4]}"

    db.concepts[c_algo] = Concept(id=c_algo, courseId="CS101", name="Algorithms")
    db.concepts[c_ds] = Concept(id=c_ds, courseId="CS101", name="Data Structures")
    db.concepts[c_untouched] = Concept(id=c_untouched, courseId="CS101", name="Untouched Concept")

    crit_algo_1 = f"crit-a1-{uuid.uuid4().hex[:4]}"
    crit_algo_2 = f"crit-a2-{uuid.uuid4().hex[:4]}"
    crit_cross = f"crit-cross-{uuid.uuid4().hex[:4]}"
    crit_unmapped = f"crit-unmap-{uuid.uuid4().hex[:4]}"

    db.assignment_criterion_concepts[aid] = [
        CriterionConceptMap(criterionId=crit_algo_1, conceptId=c_algo),
        CriterionConceptMap(criterionId=crit_algo_2, conceptId=c_algo),
        CriterionConceptMap(criterionId=crit_cross, conceptId=c_algo),
        CriterionConceptMap(criterionId=crit_cross, conceptId=c_ds),
    ]

    student_id = f"student-{uuid.uuid4().hex[:6]}"
    sub_id = f"sub-{uuid.uuid4().hex[:6]}"
    sub = make_submission(
        id=sub_id,
        studentId=student_id,
        assignmentId=aid,
    )
    db.submissions[sub_id] = sub

    evaluation = make_evaluation(
        score=45.0,
        maxScore=50.0,
        percentage=90.0,
        summaryFeedback="Great overall work.",
        strengths=[],
        improvements=[],
        criteriaScores=[
            CriterionEvaluation(
                criterionId=crit_algo_1,
                title="Time Complexity",
                scoreAwarded=10.0,
                maxPoints=10.0,
                scoreRatio=1.0,
                evidence="Runs in O(N log N)",
                reasoning="Optimal complexity",
                feedback="Excellent time complexity.",
            ),
            CriterionEvaluation(
                criterionId=crit_algo_2,
                title="Space Complexity",
                scoreAwarded=10.0,
                maxPoints=10.0,
                scoreRatio=1.0,
                evidence="In-place auxiliary memory O(1)",
                reasoning="Optimal space",
                feedback="Minimal auxiliary memory.",
            ),
            CriterionEvaluation(
                criterionId=crit_cross,
                title="Balanced BST Integration",
                scoreAwarded=15.0,
                maxPoints=20.0,
                scoreRatio=0.75,
                evidence="class Node: left, right",
                reasoning="AVL rotations implemented",
                feedback="Solid tree structures.",
            ),
            CriterionEvaluation(
                criterionId=crit_unmapped,
                title="Code Style & PEP8",
                scoreAwarded=10.0,
                maxPoints=10.0,
                scoreRatio=1.0,
                evidence="Clean formatting",
                reasoning="PEP8 compliant",
                feedback="Clean formatting.",
            ),
        ]
    )

    feedback_list = Repository.record_concept_evidence_and_update_mastery(sub, evaluation)

    # Exactly 2 concepts should be in the feedback list (c_algo and c_ds)
    evaluated_concept_ids = {cf.conceptId for cf in feedback_list}
    assert evaluated_concept_ids == {c_algo, c_ds}
    assert c_untouched not in evaluated_concept_ids

    # For c_algo: criteria are crit_algo_1 (10/10), crit_algo_2 (10/10), crit_cross (15/20)
    # Total awarded = 35, Total max = 40 -> composite ratio E = 35 / 40 = 0.875
    cf_algo = next(cf for cf in feedback_list if cf.conceptId == c_algo)
    assert cf_algo.scoreRatio == 0.875

    # For c_ds: criteria is crit_cross (15/20) -> composite ratio E = 15 / 20 = 0.75
    cf_ds = next(cf for cf in feedback_list if cf.conceptId == c_ds)
    assert cf_ds.scoreRatio == 0.75

    # Untouched concept has no mastery records created
    untouched_records = [m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == c_untouched]
    assert len(untouched_records) == 0
