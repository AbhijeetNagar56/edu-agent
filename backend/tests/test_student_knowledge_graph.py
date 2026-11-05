import pytest
import uuid
from starlette.testclient import TestClient
from app.main import app
from app.services.repository import DEV_STUDENT_ID, DEV_FACULTY_ID, OTHER_FACULTY_ID
from app.models.common import JobStatus
from app.models.submission import Submission, FacultyOverride
from app.models.evaluation import EvaluationResult, CriterionEvaluation
from app.models.assignment import Assignment, CriterionConceptMap
from app.models.curriculum import Concept, ConceptEdge
from app.services.repository import Repository, db


@pytest.fixture
def client():
    return TestClient(app)


def auth_headers(role: str = "student", user_id: str = DEV_STUDENT_ID) -> dict:
    return {
        "Authorization": f"Bearer mock-{role}:{user_id}",
    }


def make_submission(**kwargs) -> Submission:
    defaults = {
        "id": f"sub-{uuid.uuid4().hex[:6]}",
        "studentId": DEV_STUDENT_ID,
        "studentName": "Alex Student",
        "studentEmail": "alex@university.edu",
        "assignmentId": f"assign-{uuid.uuid4().hex[:6]}",
        "assignmentTitle": "DP Problem Set",
        "courseCode": "CS101",
        "fileName": "solution.py",
        "fileSize": "12 KB",
        "fileType": "text",
        "status": JobStatus.DONE,
        "submittedAt": "2026-11-05T00:00:00Z",
        "rubricId": "rub-test",
    }
    defaults.update(kwargs)
    return Submission(**defaults)


def make_criterion(**kwargs) -> CriterionEvaluation:
    defaults = {
        "criterionId": f"crit-{uuid.uuid4().hex[:6]}",
        "title": "DP Formulation",
        "scoreAwarded": 10.0,
        "maxPoints": 10.0,
        "scoreRatio": 1.0,
        "confidence": 0.85,
        "evidence": "dp = [[0] * (w + 1) for _ in range(n + 1)]",
        "reasoning": "Correct recurrence relation implemented",
        "feedback": "Flawless recurrence relation and DP formulation.",
    }
    defaults.update(kwargs)
    return CriterionEvaluation(**defaults)


def make_evaluation(**kwargs) -> EvaluationResult:
    defaults = {
        "score": 100.0,
        "maxScore": 100.0,
        "percentage": 100.0,
        "summaryFeedback": "Overall solid performance",
        "strengths": ["Clear DP states"],
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
    orig_edges = dict(db.concept_edges)
    orig_feedback = list(getattr(db, "submission_concept_feedback", []))
    orig_overrides = list(getattr(db, "faculty_overrides", []))
    orig_enrollments = list(getattr(db, "enrollments", []))

    # Clear prior test pollution for test students
    db.mastery_records = [m for m in db.mastery_records if m.get("student_id") not in [DEV_STUDENT_ID, "00000000-0000-0000-0000-000000000099"]]
    db.submission_concept_feedback = [fb for fb in getattr(db, "submission_concept_feedback", []) if fb.get("student_id") not in [DEV_STUDENT_ID, "00000000-0000-0000-0000-000000000099"]]

    yield

    db.submissions = orig_submissions
    db.mastery_records = orig_mastery
    db.assignments = orig_assignments
    db.assignment_criterion_concepts = orig_crit_concepts
    db.concepts = orig_concepts
    db.concept_edges = orig_edges
    db.submission_concept_feedback = orig_feedback
    db.faculty_overrides = orig_overrides
    db.enrollments = orig_enrollments


# =============================================================================
# 1. CANONICAL GRAPH COMPLETENESS & UNASSESSED CONCEPTS
# =============================================================================

def test_student_retrieves_all_canonical_concepts_with_unassessed_status(client):
    """
    Test 1: Student retrieves all canonical concepts.
    Concepts without evidence must appear as unassessed (masteryScore = None, status = 'unassessed'),
    NOT zero mastery.
    """
    course_id = "c1010000-0000-0000-0000-000000000001"
    headers = auth_headers(role="student", user_id=DEV_STUDENT_ID)

    # Concept 1 (Assessed): Setup evaluated submission for student
    c1_id = "c1010000-c001-0000-0000-000000000001"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    crit1 = f"crit-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"

    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit1, conceptId=c1_id)]
    sub = make_submission(id=sid, studentId=DEV_STUDENT_ID, assignmentId=aid)
    db.submissions[sid] = sub

    eval_res = make_evaluation(
        score=85.0,
        maxScore=100.0,
        criteriaScores=[
            make_criterion(criterionId=crit1, scoreAwarded=85.0, maxPoints=100.0, scoreRatio=0.85, confidence=0.8)
        ]
    )
    Repository.record_concept_evidence_and_update_mastery(sub, eval_res)

    # Call endpoint
    res = client.get(f"/api/v1/students/courses/{course_id}/curriculum", headers=headers)
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    graph = payload["data"]

    # Must contain all canonical course concepts
    canonical_concepts = Repository.get_concepts_for_course(course_id)
    assert len(graph["concepts"]) == len(canonical_concepts)
    assert len(graph["edges"]) == len(Repository.get_edges_for_course(course_id))

    # Verify evaluated concept has mastery and status
    assessed_node = next(c for c in graph["concepts"] if c["id"] == c1_id)
    assert assessed_node["masteryScore"] is not None
    assert assessed_node["masteryScore"] > 0.0
    assert assessed_node["status"] in ["developing", "strong", "high"]
    assert assessed_node["feedback"]["recentFeedback"] is not None
    assert len(assessed_node["feedback"]["history"]) >= 1

    # Verify unassessed concepts have masteryScore = None, status = 'unassessed'
    unassessed_nodes = [c for c in graph["concepts"] if c["id"] != c1_id]
    assert len(unassessed_nodes) > 0
    for u in unassessed_nodes:
        assert u["masteryScore"] is None, f"Concept {u['name']} should have null masteryScore, got {u['masteryScore']}"
        assert u["masteryPercentage"] is None
        assert u["confidenceScore"] is None
        assert u["status"] == "unassessed"
        assert u["evidenceCount"] == 0
        assert u["masterySource"] == "unassessed"


# =============================================================================
# 2. INDIVIDUALIZED KNOWLEDGE GRAPH (TWO STUDENTS IN SAME COURSE)
# =============================================================================

def test_two_students_see_same_structure_but_different_mastery(client):
    """
    Test 2: Two students enrolled in the same course see the exact same
    canonical DAG structure, but individualized student mastery states and evidence.
    """
    course_id = "c1010000-0000-0000-0000-000000000001"
    student_1_id = DEV_STUDENT_ID
    student_2_id = "00000000-0000-0000-0000-000000000099"

    # Enroll student 2 in the course
    Repository.enroll_student(course_id, student_2_id)

    c1_id = "c1010000-c001-0000-0000-000000000001"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    crit1 = f"crit-{uuid.uuid4().hex[:6]}"
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit1, conceptId=c1_id)]

    # Student 1 gets High mastery (95%)
    sub1 = make_submission(studentId=student_1_id, assignmentId=aid)
    db.submissions[sub1.id] = sub1
    eval1 = make_evaluation(
        criteriaScores=[make_criterion(criterionId=crit1, scoreAwarded=95.0, maxPoints=100.0, scoreRatio=0.95, confidence=0.9)]
    )
    Repository.record_concept_evidence_and_update_mastery(sub1, eval1)

    # Student 2 gets Low mastery (25%)
    sub2 = make_submission(studentId=student_2_id, assignmentId=aid)
    db.submissions[sub2.id] = sub2
    eval2 = make_evaluation(
        criteriaScores=[make_criterion(criterionId=crit1, scoreAwarded=25.0, maxPoints=100.0, scoreRatio=0.25, confidence=0.7)]
    )
    Repository.record_concept_evidence_and_update_mastery(sub2, eval2)

    # Request Graph for Student 1
    res1 = client.get(f"/api/v1/students/courses/{course_id}/curriculum", headers=auth_headers("student", student_1_id))
    graph1 = res1.json()["data"]

    # Request Graph for Student 2
    res2 = client.get(f"/api/v1/students/courses/{course_id}/curriculum", headers=auth_headers("student", student_2_id))
    graph2 = res2.json()["data"]

    # Structural Equality: Exact same concepts, coordinates, and edges
    assert len(graph1["concepts"]) == len(graph2["concepts"])
    assert len(graph1["edges"]) == len(graph2["edges"])
    for i in range(len(graph1["concepts"])):
        assert graph1["concepts"][i]["id"] == graph2["concepts"][i]["id"]
        assert graph1["concepts"][i]["posX"] == graph2["concepts"][i]["posX"]
        assert graph1["concepts"][i]["posY"] == graph2["concepts"][i]["posY"]

    # Learning Individualization: Different mastery scores and statuses
    node1 = next(c for c in graph1["concepts"] if c["id"] == c1_id)
    node2 = next(c for c in graph2["concepts"] if c["id"] == c1_id)

    assert node1["masteryScore"] > 0.65
    assert node2["masteryScore"] < 0.45
    assert node1["status"] in ["strong", "high"]
    assert node2["status"] in ["low_mastery", "developing"]
    assert node1["masteryScore"] != node2["masteryScore"]


# =============================================================================
# 3. EVIDENCE ISOLATION & ATTRIBUTION
# =============================================================================

def test_feedback_and_evidence_belongs_strictly_to_authenticated_student(client):
    """
    Test 3: Verify that student feedback and evidence excerpts belong strictly
    to the authenticated student. Another student's evidence is never exposed.
    """
    course_id = "c1010000-0000-0000-0000-000000000001"
    student_1_id = DEV_STUDENT_ID
    student_2_id = "00000000-0000-0000-0000-000000000099"
    Repository.enroll_student(course_id, student_2_id)

    c1_id = "c1010000-c001-0000-0000-000000000001"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    crit1 = f"crit-{uuid.uuid4().hex[:6]}"
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit1, conceptId=c1_id)]

    secret_evidence_student2 = "SECRET_CODE_WRITTEN_BY_STUDENT_2_DO_NOT_LEAK"
    sub2 = make_submission(studentId=student_2_id, assignmentId=aid)
    db.submissions[sub2.id] = sub2
    eval2 = make_evaluation(
        criteriaScores=[make_criterion(criterionId=crit1, evidence=secret_evidence_student2, feedback="Student 2 private feedback")]
    )
    Repository.record_concept_evidence_and_update_mastery(sub2, eval2)

    # Student 1 fetches curriculum
    res = client.get(f"/api/v1/students/courses/{course_id}/curriculum", headers=auth_headers("student", student_1_id))
    graph = res.json()["data"]

    # Student 1 must NOT see Student 2's secret code or feedback
    node = next(c for c in graph["concepts"] if c["id"] == c1_id)
    assert secret_evidence_student2 not in node["feedback"]["evidenceExcerpts"]
    for h in node["feedback"]["history"]:
        assert h["evidence"] != secret_evidence_student2
        assert h["submissionId"] != sub2.id


# =============================================================================
# 4. AUTHORIZATION, ENROLLMENT & CROSS-COURSE SECURITY
# =============================================================================

def test_unenrolled_student_is_rejected_with_403(client):
    """
    Test 4: Unenrolled student cannot access course curriculum graph.
    """
    unenrolled_course_id = "m2010000-0000-0000-0000-000000000003"
    res = client.get(
        f"/api/v1/students/courses/{unenrolled_course_id}/curriculum",
        headers=auth_headers("student", DEV_STUDENT_ID),
    )
    assert res.status_code == 403
    assert res.json().get("error", {}).get("code") == "NOT_ENROLLED"


def test_student_cannot_inspect_another_student_via_query_param(client):
    """
    Test 5: Never accept client-supplied student ID from student callers.
    """
    course_id = "c1010000-0000-0000-0000-000000000001"
    victim_id = "00000000-0000-0000-0000-000000000099"
    Repository.enroll_student(course_id, victim_id)

    # Student passes ?student_id=victim_id
    res = client.get(
        f"/api/v1/students/courses/{course_id}/curriculum?student_id={victim_id}",
        headers=auth_headers("student", DEV_STUDENT_ID),
    )
    assert res.status_code == 200
    # Must strictly return caller's data (DEV_STUDENT_ID), ignoring spoof attempt
    assert res.json()["data"]["studentId"] == DEV_STUDENT_ID


def test_faculty_can_view_enrolled_students_in_owned_course(client):
    """
    Test 6: Faculty can list enrolled students and inspect an enrolled student's graph
    for a course they own.
    """
    course_id = "c1010000-0000-0000-0000-000000000001"
    headers = auth_headers("faculty", DEV_FACULTY_ID)

    # 1. List enrolled students
    res_students = client.get(f"/api/v1/faculty/courses/{course_id}/students", headers=headers)
    assert res_students.status_code == 200
    students_list = res_students.json()["data"]
    assert len(students_list) >= 1
    assert any(s["studentId"] == DEV_STUDENT_ID for s in students_list)

    # 2. Inspect enrolled student's graph
    res_graph = client.get(
        f"/api/v1/students/courses/{course_id}/curriculum?student_id={DEV_STUDENT_ID}",
        headers=headers,
    )
    assert res_graph.status_code == 200
    assert res_graph.json()["data"]["studentId"] == DEV_STUDENT_ID


def test_faculty_cannot_access_unowned_course(client):
    """
    Test 7: Faculty cannot access students or student graphs for a course they do not own.
    """
    unowned_course_id = "m2010000-0000-0000-0000-000000000003"  # Owned by OTHER_FACULTY_ID
    headers = auth_headers("faculty", DEV_FACULTY_ID)

    # 1. List students -> 403 Forbidden
    res_students = client.get(f"/api/v1/faculty/courses/{unowned_course_id}/students", headers=headers)
    assert res_students.status_code == 403

    # 2. View student curriculum -> 403 Forbidden
    res_graph = client.get(
        f"/api/v1/students/courses/{unowned_course_id}/curriculum?student_id={DEV_STUDENT_ID}",
        headers=headers,
    )
    assert res_graph.status_code == 403


# =============================================================================
# 5. MULTIPLE HISTORICAL EVALUATIONS AND FACULTY OVERRIDE ON CONCEPT
# =============================================================================

def test_multiple_feedback_records_and_override_history_preserved(client):
    """
    Test 8: Multiple feedback records and faculty overrides for one concept
    are cleanly returned in the concept detail history.
    """
    course_id = "c1010000-0000-0000-0000-000000000001"
    student_id = DEV_STUDENT_ID
    cid = "c1010000-c001-0000-0000-000000000001"
    aid1 = f"assign-1-{uuid.uuid4().hex[:4]}"
    aid2 = f"assign-2-{uuid.uuid4().hex[:4]}"
    crit1 = f"crit-1-{uuid.uuid4().hex[:4]}"
    crit2 = f"crit-2-{uuid.uuid4().hex[:4]}"

    db.assignment_criterion_concepts[aid1] = [CriterionConceptMap(criterionId=crit1, conceptId=cid)]
    db.assignment_criterion_concepts[aid2] = [CriterionConceptMap(criterionId=crit2, conceptId=cid)]

    # Submission 1
    sub1 = make_submission(id=f"sub-1-{uuid.uuid4().hex[:4]}", studentId=student_id, assignmentId=aid1, assignmentTitle="Assignment 1")
    db.submissions[sub1.id] = sub1
    eval1 = make_evaluation(
        criteriaScores=[make_criterion(criterionId=crit1, scoreAwarded=70.0, maxPoints=100.0, scoreRatio=0.70, feedback="Feedback 1", evidence="Evidence 1 here")]
    )
    Repository.record_concept_evidence_and_update_mastery(sub1, eval1)

    # Submission 2
    sub2 = make_submission(id=f"sub-2-{uuid.uuid4().hex[:4]}", studentId=student_id, assignmentId=aid2, assignmentTitle="Assignment 2")
    db.submissions[sub2.id] = sub2
    eval2 = make_evaluation(
        criteriaScores=[make_criterion(criterionId=crit2, scoreAwarded=90.0, maxPoints=100.0, scoreRatio=0.90, feedback="Feedback 2", evidence="Evidence 2 here")]
    )
    Repository.record_concept_evidence_and_update_mastery(sub2, eval2)

    # Faculty overrides Submission 2 to 95.0
    override = FacultyOverride(
        isOverridden=True,
        originalScore=90.0,
        overriddenScore=95.0,
        overriddenBy="prof_oak",
        overrideReason="Excellent edge relaxation proof",
        overriddenAt="2026-11-05T01:00:00Z",
    )
    Repository.override_submission_grade(sub2.id, override)

    # Student retrieves curriculum
    res = client.get(f"/api/v1/students/courses/{course_id}/curriculum", headers=auth_headers("student", student_id))
    assert res.status_code == 200
    graph = res.json()["data"]

    concept = next(c for c in graph["concepts"] if c["id"] == cid)
    assert concept["evidenceCount"] >= 2
    assert concept["masterySource"] == "faculty_override"
    assert concept["masteryScore"] == 0.95
    assert len(concept["feedback"]["history"]) >= 2
    assert len(concept["feedback"]["associatedAssignments"]) >= 2

    # Check faculty override presence in history
    hist_sub2 = next(h for h in concept["feedback"]["history"] if h["submissionId"] == sub2.id)
    assert hist_sub2["facultyOverride"] is not None
    assert hist_sub2["facultyOverride"]["overriddenScore"] == 95.0
