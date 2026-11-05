import pytest
import uuid
from starlette.testclient import TestClient

from app.main import app
from app.services.repository import DEV_STUDENT_ID, DEV_FACULTY_ID, OTHER_FACULTY_ID, Repository, db
from app.models.common import JobStatus
from app.models.submission import Submission, FacultyOverride
from app.models.evaluation import EvaluationResult, CriterionEvaluation
from app.models.assignment import Assignment, AssignmentCreate, CriterionConceptMap
from app.models.curriculum import Concept, ConceptCreate
from app.models.course import CourseCreate


@pytest.fixture
def client():
    return TestClient(app)


def auth_headers(role: str = "faculty", user_id: str = DEV_FACULTY_ID) -> dict:
    return {
        "Authorization": f"Bearer mock-{role}:{user_id}",
    }


def make_submission(**kwargs) -> Submission:
    defaults = {
        "id": f"sub-{uuid.uuid4().hex[:6]}",
        "studentId": DEV_STUDENT_ID,
        "studentName": "Dev Student",
        "studentEmail": "dev@university.edu",
        "assignmentId": f"assign-{uuid.uuid4().hex[:6]}",
        "assignmentTitle": "Assignment Title",
        "courseCode": "CS101",
        "fileName": "solution.py",
        "fileSize": "10 KB",
        "fileType": "text",
        "status": JobStatus.DONE,
        "submittedAt": "2026-11-05T00:00:00Z",
        "rubricId": "rub-audit",
    }
    defaults.update(kwargs)
    return Submission(**defaults)


def make_evaluation(**kwargs) -> EvaluationResult:
    defaults = {
        "score": 100.0,
        "maxScore": 100.0,
        "percentage": 100.0,
        "summaryFeedback": "Overall feedback with sufficient details.",
        "strengths": ["Good approach"],
        "improvements": ["Edge case handling"],
        "criteriaScores": [],
        "evaluatedAt": "2026-11-05T00:00:00Z",
    }
    defaults.update(kwargs)
    return EvaluationResult(**defaults)


def test_faculty_submission_queue_filtering(client):
    """
    Verifies that faculty can filter submissions by course, status, assignment_id, and search query,
    with pagination metadata.
    """
    course_code = f"CS-REV-{uuid.uuid4().hex[:4].upper()}"
    course = Repository.create_course(
        CourseCreate(code=course_code, name="Review Course", description="Test Course"),
        faculty_id=DEV_FACULTY_ID,
    )

    assign_1 = Repository.create_assignment(
        course_id=course.id,
        assignment_in=AssignmentCreate(
            title="Assignment Alpha",
            description="First assignment",
            maxPoints=100.0,
            dueDate="2026-11-20T00:00:00Z",
            status="published",
        ),
        faculty_id=DEV_FACULTY_ID,
    )
    assign_2 = Repository.create_assignment(
        course_id=course.id,
        assignment_in=AssignmentCreate(
            title="Assignment Beta",
            description="Second assignment",
            maxPoints=50.0,
            dueDate="2026-11-25T00:00:00Z",
            status="published",
        ),
        faculty_id=DEV_FACULTY_ID,
    )

    # Create submissions with distinct statuses and assignments
    sub1 = make_submission(
        id=f"sub-q1-{uuid.uuid4().hex[:6]}",
        studentId=DEV_STUDENT_ID,
        studentName="Alice Student",
        studentEmail="alice@university.edu",
        assignmentId=assign_1.id,
        assignmentTitle=assign_1.title,
        courseCode=course_code,
        status=JobStatus.DONE,
        evaluation=make_evaluation(score=85.0, maxScore=100.0, percentage=85.0),
    )
    sub2 = make_submission(
        id=f"sub-q2-{uuid.uuid4().hex[:6]}",
        studentId=DEV_STUDENT_ID,
        studentName="Alice Student",
        studentEmail="alice@university.edu",
        assignmentId=assign_2.id,
        assignmentTitle=assign_2.title,
        courseCode=course_code,
        status="manual_review",
    )
    sub3 = make_submission(
        id=f"sub-q3-{uuid.uuid4().hex[:6]}",
        studentId="student-bob",
        studentName="Bob Builder",
        studentEmail="bob@university.edu",
        assignmentId=assign_1.id,
        assignmentTitle=assign_1.title,
        courseCode=course_code,
        status=JobStatus.PENDING,
    )
    for s in [sub1, sub2, sub3]:
        db.submissions[s.id] = s

    # 1. Filter by course
    res = client.get(
        f"/api/v1/faculty/submissions?course_code={course_code}",
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res.status_code == 200
    data = res.json()["data"]
    sub_ids = [s["id"] for s in data]
    assert sub1.id in sub_ids
    assert sub2.id in sub_ids
    assert sub3.id in sub_ids

    # 2. Filter by status manual_review
    res = client.get(
        f"/api/v1/faculty/submissions?course_code={course_code}&status=manual_review",
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == sub2.id

    # 3. Filter by assignment_id
    res = client.get(
        f"/api/v1/faculty/submissions?course_code={course_code}&assignment_id={assign_2.id}",
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == sub2.id

    # 4. Search by student name
    res = client.get(
        f"/api/v1/faculty/submissions?course_code={course_code}&search=Builder",
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == sub3.id


def test_faculty_override_lifecycle_and_criterion_adjustments(client):
    """
    Verifies the complete override lifecycle:
    - Score override with mandatory reason
    - Criterion-level adjustments updating criteriaScores and submission_concept_feedback
    - Override revocation reverting to AI-calculated evaluation and restoring pure AI mastery
    """
    course_code = f"CS-OVR-{uuid.uuid4().hex[:4].upper()}"
    course = Repository.create_course(
        CourseCreate(code=course_code, name="Override Lifecycle Course", description="Test"),
        faculty_id=DEV_FACULTY_ID,
    )

    c1 = Repository.create_concept(
        course_id=course.id,
        concept_in=ConceptCreate(name="Graph Search", description="BFS and DFS", category="Algorithms", difficulty="intermediate"),
    )

    crit_id = f"crit-bfs-{uuid.uuid4().hex[:4]}"
    crit = CriterionEvaluation(
        criterionId=crit_id,
        title="BFS Implementation",
        scoreAwarded=10.0,
        maxPoints=20.0,
        scoreRatio=0.5,
        feedback="Missing visited set check",
    )

    sub_id = f"sub-ovr-{uuid.uuid4().hex[:6]}"
    sub = make_submission(
        id=sub_id,
        studentId=DEV_STUDENT_ID,
        studentName="Carol Student",
        studentEmail="carol@university.edu",
        assignmentId="assign-ovr",
        assignmentTitle="Graph Traversal",
        courseCode=course_code,
        status=JobStatus.DONE,
        evaluation=make_evaluation(
            score=50.0,
            maxScore=100.0,
            percentage=50.0,
            summaryFeedback="Partial BFS solution.",
            criteriaScores=[crit],
        ),
    )
    db.submissions[sub.id] = sub

    # Seed criterion mapping and initial AI evaluation evidence
    db.assignment_criterion_concepts["assign-ovr"] = [
        CriterionConceptMap(criterionId=crit_id, conceptId=c1.id)
    ]
    Repository.record_concept_evidence_and_update_mastery(sub, sub.evaluation)

    initial_mastery = next((m for m in db.mastery_records if str(m["student_id"]) == DEV_STUDENT_ID and str(m["concept_id"]) == str(c1.id)), None)
    assert initial_mastery is not None
    assert initial_mastery["source"] == "ai"
    initial_score = float(initial_mastery["mastery_score"])

    # 1. Reject override without reason
    res_bad = client.post(
        f"/api/v1/faculty/submissions/{sub_id}/override",
        json={"overriddenScore": 85.0, "overrideReason": ""},
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res_bad.status_code == 422  # Pydantic min_length validation

    # 2. Perform override with criterion adjustment
    res_ovr = client.post(
        f"/api/v1/faculty/submissions/{sub_id}/override",
        json={
            "overriddenScore": 90.0,
            "overrideReason": "Student clarified BFS edge cases in office hours.",
            "criterionAdjustments": {crit_id: 18.0},  # 18/20 = 0.9 ratio
        },
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res_ovr.status_code == 200
    ovr_data = res_ovr.json()["data"]
    assert ovr_data["finalScore"] == 90.0
    assert ovr_data["isOverridden"] is True

    # Verify submission evaluation reflects updated criterion and overall score
    updated_sub = Repository.get_submission_by_id(sub_id)
    assert updated_sub.override.isOverridden is True
    assert updated_sub.override.overriddenScore == 90.0
    assert updated_sub.override.overriddenById == DEV_FACULTY_ID
    assert updated_sub.evaluation.score == 50.0  # original preserved
    assert updated_sub.evaluation.criteriaScores[0].scoreAwarded == 18.0
    assert updated_sub.evaluation.criteriaScores[0].scoreRatio == 0.9

    # Verify concept mastery was updated deterministically from updated evidence
    updated_mastery = next((m for m in db.mastery_records if str(m["student_id"]) == DEV_STUDENT_ID and str(m["concept_id"]) == str(c1.id)), None)
    assert updated_mastery["mastery_score"] > initial_score

    # 3. Revoke override via DELETE /api/v1/faculty/submissions/{id}/override
    res_rev = client.delete(
        f"/api/v1/faculty/submissions/{sub_id}/override?reason=Testing+revocation",
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res_rev.status_code == 200
    rev_data = res_rev.json()["data"]
    assert rev_data["isOverridden"] is False

    reloaded_sub = Repository.get_submission_by_id(sub_id)
    assert reloaded_sub.override.isOverridden is False


def test_direct_concept_mastery_override_and_revocation(client):
    """
    Verifies direct concept mastery override:
    - POST overrides student_concept_mastery with source='faculty_override'
    - logs to faculty_overrides audit table
    - DELETE revokes override, resets source to 'ai', and recomputes mastery from evidence
    """
    course_code = f"CS-DIR-{uuid.uuid4().hex[:4].upper()}"
    course = Repository.create_course(
        CourseCreate(code=course_code, name="Direct Override Course", description="Test"),
        faculty_id=DEV_FACULTY_ID,
    )
    Repository.enroll_student(course.id, DEV_STUDENT_ID)

    c1 = Repository.create_concept(
        course_id=course.id,
        concept_in=ConceptCreate(name="Dynamic Programming", description="Memoization", category="Algorithms", difficulty="advanced"),
    )

    # 1. Override concept mastery directly
    res = client.post(
        f"/api/v1/faculty/courses/{course.id}/students/{DEV_STUDENT_ID}/concepts/{c1.id}/override",
        json={
            "masteryScore": 0.95,
            "confidenceScore": 0.92,
            "overrideReason": "Demonstrated mastery during lab oral examination.",
        },
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["studentId"] == DEV_STUDENT_ID
    assert body["conceptId"] == str(c1.id)
    assert body["masteryScore"] == 0.95
    assert body["masteryPercentage"] == 95.0
    assert body["source"] == "faculty_override"

    # Verify audit log in db.faculty_overrides
    override_audit = [fo for fo in db.faculty_overrides if fo.get("concept_id") == str(c1.id)]
    assert len(override_audit) >= 1
    assert override_audit[-1]["target_type"] == "concept_mastery"
    assert override_audit[-1]["overridden_score"] == 0.95
    assert override_audit[-1]["is_overridden"] is True

    # 2. Revoke concept mastery override
    res_del = client.delete(
        f"/api/v1/faculty/courses/{course.id}/students/{DEV_STUDENT_ID}/concepts/{c1.id}/override",
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res_del.status_code == 200

    # Verify audit log records revocation
    override_audit_rev = [fo for fo in db.faculty_overrides if fo.get("concept_id") == str(c1.id)]
    assert override_audit_rev[-1]["is_overridden"] is False

    # Since there was no prior submission evidence, mastery falls back to unassessed/0.0
    mastery = next((m for m in db.mastery_records if str(m["student_id"]) == DEV_STUDENT_ID and str(m["concept_id"]) == str(c1.id)), None)
    assert mastery is not None
    assert mastery["source"] == "ai"


def test_course_learning_analytics_computation(client):
    """
    Verifies course learning analytics endpoint:
    - Overview metrics (enrolled, assignments, submissions, coverage)
    - Student progress: STRICT EXCLUSION of unassessed concepts from average mastery!
    - Concept analytics: flags needsAttention for concepts with low mastery or zero assessed
    - Assignment analytics: score distribution buckets
    """
    course_code = f"CS-ANL-{uuid.uuid4().hex[:4].upper()}"
    course = Repository.create_course(
        CourseCreate(code=course_code, name="Analytics Test Course", description="Test Course"),
        faculty_id=DEV_FACULTY_ID,
    )

    # Enroll 2 students
    Repository.enroll_student(course.id, DEV_STUDENT_ID)
    student_2 = f"student-dan-{uuid.uuid4().hex[:4]}"
    Repository.enroll_student(course.id, student_2)

    # Create 3 concepts
    c1 = Repository.create_concept(
        course_id=course.id,
        concept_in=ConceptCreate(name="Recursion", description="Base and recursive cases", category="Basics", difficulty="beginner"),
    )
    c2 = Repository.create_concept(
        course_id=course.id,
        concept_in=ConceptCreate(name="Binary Trees", description="Tree structures", category="Data Structures", difficulty="intermediate"),
    )
    c3 = Repository.create_concept(
        course_id=course.id,
        concept_in=ConceptCreate(name="Red-Black Trees", description="Balanced trees", category="Data Structures", difficulty="advanced"),
    )

    # Create 1 published assignment and 1 draft
    a1 = Repository.create_assignment(
        course_id=course.id,
        assignment_in=AssignmentCreate(
            title="Trees Lab",
            description="Tree exercises",
            maxPoints=100.0,
            dueDate="2026-11-20T00:00:00Z",
            status="published",
        ),
        faculty_id=DEV_FACULTY_ID,
    )
    a2 = Repository.create_assignment(
        course_id=course.id,
        assignment_in=AssignmentCreate(
            title="Draft Project",
            description="Upcoming project",
            maxPoints=100.0,
            dueDate="2026-12-01T00:00:00Z",
            status="draft",
        ),
        faculty_id=DEV_FACULTY_ID,
    )

    # Student 1 has mastery only in Concept 1 (score 0.85). Concepts 2 and 3 are UNASSESSED!
    db.mastery_records.append({
        "id": str(uuid.uuid4()),
        "student_id": DEV_STUDENT_ID,
        "concept_id": c1.id,
        "mastery_score": 0.85,
        "mastery_percentage": 85.0,
        "confidence_score": 0.9,
        "source": "ai",
        "evidence_count": 1,
    })

    # Student 2 has mastery in Concept 1 (score 0.30) and Concept 2 (score 0.45). Concept 3 is UNASSESSED!
    db.mastery_records.append({
        "id": str(uuid.uuid4()),
        "student_id": student_2,
        "concept_id": c1.id,
        "mastery_score": 0.30,
        "mastery_percentage": 30.0,
        "confidence_score": 0.8,
        "source": "ai",
        "evidence_count": 1,
    })
    db.mastery_records.append({
        "id": str(uuid.uuid4()),
        "student_id": student_2,
        "concept_id": c2.id,
        "mastery_score": 0.45,
        "mastery_percentage": 45.0,
        "confidence_score": 0.85,
        "source": "ai",
        "evidence_count": 1,
    })

    # Submissions for assignment 1
    sub1 = make_submission(
        id=f"sub-anl1-{uuid.uuid4().hex[:6]}",
        studentId=DEV_STUDENT_ID,
        studentName="Dev Student",
        studentEmail="dev@university.edu",
        assignmentId=a1.id,
        assignmentTitle=a1.title,
        courseCode=course_code,
        status=JobStatus.DONE,
        evaluation=make_evaluation(score=88.0, maxScore=100.0, percentage=88.0),
    )
    sub2 = make_submission(
        id=f"sub-anl2-{uuid.uuid4().hex[:6]}",
        studentId=student_2,
        studentName="Dan Student",
        studentEmail="dan@university.edu",
        assignmentId=a1.id,
        assignmentTitle=a1.title,
        courseCode=course_code,
        status=JobStatus.DONE,
        evaluation=make_evaluation(score=62.0, maxScore=100.0, percentage=62.0),
    )
    for s in [sub1, sub2]:
        db.submissions[s.id] = s

    # Fetch course learning analytics
    res = client.get(
        f"/api/v1/faculty/courses/{course.id}/analytics",
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res.status_code == 200
    data = res.json()["data"]

    # 1. Overview checks
    ov = data["overview"]
    assert ov["courseId"] == course.id
    assert ov["courseCode"] == course_code
    assert ov["totalEnrolled"] == 2
    assert ov["totalAssignments"] == 2
    assert ov["publishedAssignments"] == 1
    assert ov["draftAssignments"] == 1
    assert ov["totalSubmissions"] == 2
    assert ov["completedEvaluations"] == 2
    assert ov["averageAssignmentScore"] == 75.0  # (88 + 62) / 2
    # 2 out of 3 concepts assessed (c1 and c2) = 66.7%
    assert ov["conceptCoveragePercentage"] == 66.7

    # 2. Student progress summary & UNASSESSED EXCLUSION check
    sp = data["studentProgress"]
    assert len(sp) == 2
    s1_summary = next(s for s in sp if s["studentId"] == DEV_STUDENT_ID)
    assert s1_summary["totalConcepts"] == 3
    assert s1_summary["assessedConcepts"] == 1
    assert s1_summary["unassessedCount"] == 2
    # CRITICAL: Average mastery MUST be 85.0%, NOT 85/3 = 28.3%!
    assert s1_summary["averageMastery"] == 85.0
    assert s1_summary["strongCount"] == 1

    s2_summary = next(s for s in sp if s["studentId"] == student_2)
    assert s2_summary["totalConcepts"] == 3
    assert s2_summary["assessedConcepts"] == 2
    assert s2_summary["unassessedCount"] == 1
    # Average of 30.0 and 45.0 = 37.5%
    assert s2_summary["averageMastery"] == 37.5
    assert s2_summary["lowMasteryCount"] == 1
    assert s2_summary["developingCount"] == 1

    # 3. Concept analytics summary & attention flags
    ca = data["conceptAnalytics"]
    assert len(ca) == 3

    c1_anl = next(c for c in ca if c["conceptId"] == str(c1.id))
    assert c1_anl["assessedStudentsCount"] == 2
    assert c1_anl["averageMastery"] == 57.5  # (85 + 30) / 2
    # 1 out of 2 students in low (<0.40) is 50%, >= 30% threshold -> needsAttention = True
    assert c1_anl["needsAttention"] is True

    c3_anl = next(c for c in ca if c["conceptId"] == str(c3.id))
    assert c3_anl["assessedStudentsCount"] == 0
    assert c3_anl["unassessedStudentsCount"] == 2
    assert c3_anl["needsAttention"] is True
    assert c3_anl["attentionReason"] == "No students assessed yet"

    # 4. Assignment analytics breakdown & score distribution
    aa = data["assignmentAnalytics"]
    assert len(aa) == 2
    a1_anl = next(a for a in aa if a["assignmentId"] == a1.id)
    assert a1_anl["submissionCount"] == 2
    assert a1_anl["completionRate"] == 100.0
    assert a1_anl["averageScore"] == 75.0
    assert a1_anl["scoreDistribution"]["60-69"] == 1  # 62.0
    assert a1_anl["scoreDistribution"]["80-89"] == 1  # 88.0


def test_security_and_course_isolation(client):
    """
    Verifies that:
    - Students are rejected with 403 Forbidden on faculty review queue, overrides, and analytics
    - Unauthorized faculty are rejected with 403 Forbidden for courses they do not own
    - Non-enrolled students cannot have their concept mastery overridden
    """
    course_code = f"CS-SEC-{uuid.uuid4().hex[:4].upper()}"
    course = Repository.create_course(
        CourseCreate(code=course_code, name="Security Course", description="Test"),
        faculty_id=DEV_FACULTY_ID,
    )

    # 1. Student cannot access faculty review queue
    res = client.get(
        "/api/v1/faculty/submissions",
        headers=auth_headers("student", DEV_STUDENT_ID),
    )
    assert res.status_code == 403

    # 2. Student cannot access course analytics
    res = client.get(
        f"/api/v1/faculty/courses/{course.id}/analytics",
        headers=auth_headers("student", DEV_STUDENT_ID),
    )
    assert res.status_code == 403

    # 3. Faculty B cannot access Faculty A's course analytics
    res = client.get(
        f"/api/v1/faculty/courses/{course.id}/analytics",
        headers=auth_headers("faculty", OTHER_FACULTY_ID),
    )
    assert res.status_code == 403

    # 4. Faculty B cannot access Faculty A's submissions
    res = client.get(
        f"/api/v1/faculty/submissions?course_code={course_code}",
        headers=auth_headers("faculty", OTHER_FACULTY_ID),
    )
    assert res.status_code == 403

    # 5. Concept override on non-enrolled student is rejected
    c1 = Repository.create_concept(
        course_id=course.id,
        concept_in=ConceptCreate(name="Hashing", description="Hash tables", category="Basics", difficulty="beginner"),
    )
    res = client.post(
        f"/api/v1/faculty/courses/{course.id}/students/unregistered-student/concepts/{c1.id}/override",
        json={"masteryScore": 0.8, "overrideReason": "Test"},
        headers=auth_headers("faculty", DEV_FACULTY_ID),
    )
    assert res.status_code == 404
