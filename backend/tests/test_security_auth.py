import uuid
import pytest
from app.core.config import settings
from app.models.common import JobStatus
from app.models.evaluation import FacultyOverride
from app.models.submission import Submission
from app.services.repository import DEV_FACULTY_ID, DEV_STUDENT_ID, Repository, db


# -------------------------------------------------------------------------
# 1. Authenticated student can submit an assignment
# -------------------------------------------------------------------------
def test_authenticated_student_can_submit_assignment(student_client):
    payload = {
        "assignment_id": "assign-1",
        "assignment_title": "Assignment 1: Sorting Algorithms",
        "course_code": "CS101",
        "rubric_id": "rubric-1",
        "text_content": "# Quicksort Implementation\nAuthoritative submission by student.",
    }
    response = student_client.post("/api/v1/submissions", data=payload)
    assert response.status_code == 201
    res_json = response.json()
    assert res_json["success"] is True
    data = res_json["data"]
    # Verified: studentId derived strictly from authenticated user session
    assert data["studentId"] == DEV_STUDENT_ID
    assert data["courseCode"] == "CS101"
    assert data["status"] == "pending"

    # In repository storage, ownerId is strictly set to DEV_STUDENT_ID
    sub_in_db = Repository.get_submission_by_id(data["id"])
    assert sub_in_db is not None
    assert sub_in_db.ownerId == DEV_STUDENT_ID


# -------------------------------------------------------------------------
# 2. Student cannot submit on behalf of another student
# -------------------------------------------------------------------------
def test_student_cannot_submit_on_behalf_of_another_student(student_client):
    payload = {
        "student_id": "00000000-0000-0000-0000-000000000999",  # Attempt to spoof another student UUID
        "assignment_id": "assign-1",
        "assignment_title": "Assignment 1",
        "course_code": "CS101",
        "rubric_id": "rubric-1",
        "text_content": "Impersonation attempt submission",
    }
    response = student_client.post("/api/v1/submissions", data=payload)
    assert response.status_code == 403
    res_json = response.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "FORBIDDEN"
    assert "Cannot submit assignment on behalf of another student" in res_json["error"]["message"]


# -------------------------------------------------------------------------
# 3. Student cannot read another student's submission
# -------------------------------------------------------------------------
def test_student_cannot_read_another_students_submission(student_client):
    # Seed a submission belonging strictly to a different student
    other_student_id = "00000000-0000-0000-0000-000000000888"
    other_sub_id = "sub-other-student-test"
    db.submissions[other_sub_id] = Submission(
        id=other_sub_id,
        studentId=other_student_id,
        studentName="Other Student",
        studentEmail="other@university.edu",
        ownerId=other_student_id,
        assignmentId="assign-1",
        assignmentTitle="Assignment 1",
        courseCode="CS101",
        fileName="other.pdf",
        fileSize="100 KB",
        fileType="pdf",
        status=JobStatus.DONE,
        submittedAt="2026-11-01 10:00",
        rubricId="rubric-1",
    )

    response = student_client.get(f"/api/v1/submissions/{other_sub_id}")
    assert response.status_code == 403
    res_json = response.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "FORBIDDEN"
    assert "You can only view your own submissions" in res_json["error"]["message"]


# -------------------------------------------------------------------------
# 4. Student cannot read another student's mastery records
# -------------------------------------------------------------------------
def test_student_cannot_read_another_students_mastery_records(student_client):
    other_student_id = "00000000-0000-0000-0000-000000000888"
    response = student_client.get(f"/api/v1/students/{other_student_id}/mastery")
    assert response.status_code == 403
    res_json = response.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "FORBIDDEN"
    assert "You can only view your own mastery records" in res_json["error"]["message"]


# -------------------------------------------------------------------------
# 5. Faculty cannot access courses they do not own
# -------------------------------------------------------------------------
def test_faculty_cannot_access_courses_they_do_not_own(faculty_client):
    # Dr. Sarah Lin does not own "BIO999"
    unauthorized_course = "BIO999"

    # Test 5a: Submissions listing for unauthorized course
    res_list = faculty_client.get(f"/api/v1/faculty/submissions?course_code={unauthorized_course}")
    assert res_list.status_code == 403
    assert res_list.json()["error"]["code"] == "FORBIDDEN"

    # Test 5b: Rubric creation for unauthorized course
    rubric_payload = {
        "courseCode": unauthorized_course,
        "assignmentTitle": "Bio Lab 1",
        "description": "Unauthorized rubric creation",
        "totalPoints": 100.0,
        "criteria": [{"title": "Lab Technique", "description": "Protocol", "maxPoints": 100.0}],
    }
    res_rubric = faculty_client.post("/api/v1/faculty/rubrics", json=rubric_payload)
    assert res_rubric.status_code == 403
    assert res_rubric.json()["error"]["code"] == "FORBIDDEN"


# -------------------------------------------------------------------------
# 6. Faculty can access their authorized course submissions
# -------------------------------------------------------------------------
def test_faculty_can_access_their_authorized_course_submissions(faculty_client):
    # Dr. Sarah Lin owns CS101
    response = faculty_client.get("/api/v1/faculty/submissions?course_code=CS101")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert "data" in res_json
    assert "meta" in res_json
    for sub in res_json["data"]:
        assert sub["courseCode"] == "CS101"


# -------------------------------------------------------------------------
# 7. Faculty override identity is derived from authentication
# -------------------------------------------------------------------------
def test_faculty_override_identity_is_derived_from_authentication(faculty_client):
    override_payload = {
        "overriddenScore": 95.0,
        "overriddenBy": "Malicious Spoofed Dean Identity",  # Client-supplied spoof
        "overrideReason": "Valid reassessment of asymptotic analysis.",
        "criterionAdjustments": {"crit-1": 35.0},
    }
    response = faculty_client.post("/api/v1/faculty/submissions/sub-101/override", json=override_payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    override_data = res_json["data"]["override"]

    # Must NOT use "Malicious Spoofed Dean Identity"
    assert override_data["overriddenBy"] != "Malicious Spoofed Dean Identity"
    # Must use authoritative identity of authenticated user
    assert override_data["overriddenBy"] == "Dr. Sarah Lin"


# -------------------------------------------------------------------------
# 8. Unauthenticated requests are rejected with 401
# -------------------------------------------------------------------------
def test_unauthenticated_requests_rejected_with_401(client):
    # All protected endpoints must reject requests lacking Authorization header
    endpoints = [
        ("GET", "/api/v1/submissions"),
        ("POST", "/api/v1/submissions"),
        ("GET", "/api/v1/submissions/sub-101"),
        ("GET", "/api/v1/faculty/submissions"),
        ("POST", "/api/v1/faculty/submissions/sub-101/override"),
        ("GET", "/api/v1/faculty/rubrics"),
        ("POST", "/api/v1/faculty/rubrics"),
        ("GET", f"/api/v1/students/{DEV_STUDENT_ID}/mastery"),
    ]
    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, data={} if "submissions" in path and method == "POST" and "override" not in path else None, json={} if "override" in path or "rubrics" in path else None)
        assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {res.status_code}"
        assert res.json()["error"]["code"] == "UNAUTHORIZED"


# -------------------------------------------------------------------------
# 9. Production configuration cannot activate mock authentication
# -------------------------------------------------------------------------
def test_production_configuration_cannot_activate_mock_auth(client):
    original_env = settings.ENVIRONMENT
    try:
        # Simulate production environment
        settings.ENVIRONMENT = "production"

        headers = {"Authorization": "Bearer dev-student"}
        res = client.get("/api/v1/submissions", headers=headers)
        assert res.status_code == 401
        res_json = res.json()
        assert res_json["error"]["code"] == "UNAUTHORIZED"
        assert "Mock authentication tokens are strictly prohibited in production" in res_json["error"]["message"]

        # Also test dev-faculty
        headers_fac = {"Authorization": "Bearer dev-faculty"}
        res_fac = client.get("/api/v1/faculty/submissions", headers=headers_fac)
        assert res_fac.status_code == 401
        assert res_fac.json()["error"]["code"] == "UNAUTHORIZED"
    finally:
        settings.ENVIRONMENT = original_env


# -------------------------------------------------------------------------
# 10. Evaluation persistence uses authoritative schema and mastery separation
# -------------------------------------------------------------------------
def test_evaluation_persistence_authoritative_schema_and_mastery():
    test_student_id = "00000000-0000-0000-0000-000000000302"
    test_concept_id = "c0000000-0000-0000-0000-000000000099"

    # Step 1: Record evidence from AI evaluation
    record_ai = Repository.record_concept_mastery_evidence(
        student_id=test_student_id,
        concept_id=test_concept_id,
        raw_score=85.0,
        max_score=100.0,
        submission_id="sub-101",
        source="ai_evaluation",
    )
    assert record_ai["student_id"] == test_student_id
    assert record_ai["concept_id"] == test_concept_id
    assert 0.0 <= record_ai["mastery_score"] <= 1.0
    assert record_ai["mastery_score"] == 0.85
    assert record_ai["source"] == "ai_evaluation"
    assert record_ai["confidence_score"] == 0.6
    assert record_ai["evidence_count"] == 1

    # Step 2: Record evidence from faculty override (source attribution & full confidence)
    record_override = Repository.record_concept_mastery_evidence(
        student_id=test_student_id,
        concept_id=test_concept_id,
        raw_score=95.0,
        max_score=100.0,
        submission_id="sub-101",
        source="faculty_override",
    )
    assert record_override["mastery_score"] == 0.95
    assert record_override["source"] == "faculty_override"
    assert record_override["confidence_score"] == 1.0
    assert record_override["evidence_count"] == 2


# -------------------------------------------------------------------------
# 11. Mastery boundary values, multiple evidence, and confidence ceiling
# -------------------------------------------------------------------------
def test_mastery_boundary_values_and_multiple_evidence():
    student_id = "00000000-0000-0000-0000-000000000302"
    concept_min = "c0000000-0000-0000-0000-000000000010"
    concept_max = "c0000000-0000-0000-0000-000000000011"
    concept_multi = "c0000000-0000-0000-0000-000000000012"

    # Boundary 1: Minimum (0.0) and negative clamp
    rec_min = Repository.record_concept_mastery_evidence(
        student_id=student_id,
        concept_id=concept_min,
        raw_score=0.0,
        max_score=100.0,
    )
    assert rec_min["mastery_score"] == 0.0
    assert rec_min["mastery_percentage"] == 0.0

    rec_neg = Repository.record_concept_mastery_evidence(
        student_id=student_id,
        concept_id=concept_min,
        raw_score=-20.0,
        max_score=100.0,
    )
    assert rec_neg["mastery_score"] >= 0.0, "Mastery score dropped below 0.0"

    # Boundary 2: Maximum (1.0) and overflow clamp
    rec_max = Repository.record_concept_mastery_evidence(
        student_id=student_id,
        concept_id=concept_max,
        raw_score=100.0,
        max_score=100.0,
    )
    assert rec_max["mastery_score"] == 1.0
    assert rec_max["mastery_percentage"] == 100.0

    rec_over = Repository.record_concept_mastery_evidence(
        student_id=student_id,
        concept_id=concept_max,
        raw_score=150.0,
        max_score=100.0,
    )
    assert rec_over["mastery_score"] <= 1.0, "Mastery score exceeded 1.0"

    # Multiple evidence records: Confidence ceiling verification (never exceeds 1.0)
    for i in range(12):
        rec_ev = Repository.record_concept_mastery_evidence(
            student_id=student_id,
            concept_id=concept_multi,
            raw_score=80.0,
            max_score=100.0,
            source="ai_evaluation",
        )
        assert rec_ev["confidence_score"] <= 1.0, f"Confidence exceeded 1.0 at iteration {i}: {rec_ev['confidence_score']}"
        assert rec_ev["evidence_count"] == i + 1

    assert rec_ev["confidence_score"] == 1.0, "Expected confidence to plateau at 1.0"
    assert rec_ev["source"] in ("ai_evaluation", "faculty_override", "diagnostic_quiz", "manual_adjustment")


# -------------------------------------------------------------------------
# 12. JWT Security: Reject forged, expired, and invalid-signature tokens
# -------------------------------------------------------------------------
def test_jwt_security_rejection_forged_expired_invalid(client):
    import time
    import jwt

    test_secret = "test-supa-secret-key-32-chars-long-12345"
    original_secret = settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = test_secret

    try:
        # 1. Forged token signed with untrusted malicious secret
        forged_payload = {
            "sub": DEV_STUDENT_ID,
            "aud": "authenticated",
            "app_metadata": {"role": "student"},
            "exp": int(time.time()) + 3600,
        }
        forged_token = jwt.encode(forged_payload, "malicious-hacker-secret-key", algorithm="HS256")
        res_forged = client.get("/api/v1/submissions", headers={"Authorization": f"Bearer {forged_token}"})
        assert res_forged.status_code == 401
        assert res_forged.json()["error"]["code"] == "UNAUTHORIZED"

        # 2. Expired token signed with genuine secret
        expired_payload = {
            "sub": DEV_STUDENT_ID,
            "aud": "authenticated",
            "app_metadata": {"role": "student"},
            "exp": int(time.time()) - 3600,  # 1 hour in the past
        }
        expired_token = jwt.encode(expired_payload, test_secret, algorithm="HS256")
        res_expired = client.get("/api/v1/submissions", headers={"Authorization": f"Bearer {expired_token}"})
        assert res_expired.status_code == 401
        assert "expired" in res_expired.json()["error"]["message"].lower()

        # 3. Corrupted / invalid signature token
        tampered_token = forged_token[:-8] + "abcdefgh"
        res_tampered = client.get("/api/v1/submissions", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res_tampered.status_code == 401

        # 4. Valid token signed with correct secret and claims succeeds
        valid_payload = {
            "sub": DEV_STUDENT_ID,
            "aud": "authenticated",
            "email": "student@eduagents.app",
            "app_metadata": {"role": "student"},
            "user_metadata": {"full_name": "Jordan Taylor"},
            "exp": int(time.time()) + 3600,
        }
        valid_token = jwt.encode(valid_payload, test_secret, algorithm="HS256")
        res_valid = client.get("/api/v1/submissions", headers={"Authorization": f"Bearer {valid_token}"})
        assert res_valid.status_code == 200
        assert res_valid.json()["success"] is True

    finally:
        settings.SUPABASE_JWT_SECRET = original_secret


# -------------------------------------------------------------------------
# 13. Faculty override UUID foreign-key and display name separation
# -------------------------------------------------------------------------
def test_faculty_override_uuid_and_display_name_separation(faculty_client):
    override_payload = {
        "overriddenScore": 98.0,
        "overriddenBy": "Malicious Spoofed Dean Identity",
        "overrideReason": "Reassessment of asymptotic proofs.",
        "criterionAdjustments": {"crit-1": 40.0},
    }
    response = faculty_client.post("/api/v1/faculty/submissions/sub-101/override", json=override_payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True

    override_data = res_json["data"]["override"]
    # Check that overriddenById contains authenticated faculty UUID
    assert override_data["overriddenById"] == DEV_FACULTY_ID
    # Check that overriddenByName contains authenticated faculty display name
    assert override_data["overriddenByName"] == "Dr. Sarah Lin"
    # Client-supplied spoof was completely disregarded
    assert override_data["overriddenByName"] != "Malicious Spoofed Dean Identity"
    assert override_data["overriddenBy"] != "Malicious Spoofed Dean Identity"


# -------------------------------------------------------------------------
# 14. Realtime subscription targets authoritative submissions table
# -------------------------------------------------------------------------
def test_realtime_subscription_targets_authoritative_submissions():
    with open("frontend/lib/storage.ts", "r", encoding="utf-8") as f:
        code = f.read()

    # Must subscribe directly to physical table 'submissions'
    assert "table: 'submissions'" in code, "Frontend Realtime must subscribe to physical table 'submissions'"
    # Must NOT subscribe to SQL view 'submissions_v2'
    assert "table: 'submissions_v2'" not in code, "Frontend Realtime must not subscribe to SQL view 'submissions_v2'"
