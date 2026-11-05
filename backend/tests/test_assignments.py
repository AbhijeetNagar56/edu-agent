import pytest
from app.core.config import settings

DEV_FACULTY_ID = "00000000-0000-0000-0000-000000000101"
DEV_STUDENT_ID = "00000000-0000-0000-0000-000000000302"
OTHER_FACULTY_ID = "00000000-0000-0000-0000-000000000999"

CS101_COURSE_ID = "c1010000-0000-0000-0000-000000000001"
AI301_COURSE_ID = "a3010000-0000-0000-0000-000000000002"
MATH201_COURSE_ID = "m2010000-0000-0000-0000-000000000003"


def test_faculty_list_course_assignments(faculty_client):
    """
    Faculty owner can list all assignments (both published and draft) for their course.
    """
    res = faculty_client.get(f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments")
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["success"] is True
    assigns = res_json["data"]
    assert len(assigns) >= 2

    # Check assign-1 fields
    assign_1 = next((a for a in assigns if a["id"] == "assign-1"), None)
    assert assign_1 is not None
    assert assign_1["status"] == "published"
    assert assign_1["maxPoints"] == 100.0
    assert assign_1["rubricId"] == "rubric-1"
    assert len(assign_1["conceptIds"]) >= 2
    assert len(assign_1["concepts"]) >= 2
    assert len(assign_1["criterionConcepts"]) >= 1

    # Check draft assignment is visible to faculty
    draft_assign = next((a for a in assigns if a["status"] == "draft"), None)
    assert draft_assign is not None


def test_faculty_create_assignment_with_concepts_and_criteria(faculty_client):
    """
    Faculty can create a new assignment mapping course concepts and rubric criteria.
    """
    payload = {
        "title": "Assignment 4: Advanced Graphs",
        "description": "Network flow and min-cut algorithms.",
        "dueDate": "2026-12-20T23:59:59Z",
        "maxPoints": 120.0,
        "status": "published",
        "rubricId": "rubric-2",
        "conceptIds": [
            "c1010000-c005-0000-0000-000000000005",
            "c1010000-c006-0000-0000-000000000006",
        ],
        "criterionConcepts": [
            {
                "criterionId": "crit-2-1",
                "conceptId": "c1010000-c005-0000-0000-000000000005",
            },
            {
                "criterionId": "crit-2-2",
                "conceptId": "c1010000-c006-0000-0000-000000000006",
            },
        ],
    }
    res = faculty_client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        json=payload,
    )
    assert res.status_code == 201
    res_json = res.json()
    assert res_json["success"] is True
    data = res_json["data"]
    assert data["title"] == "Assignment 4: Advanced Graphs"
    assert data["maxPoints"] == 120.0
    assert len(data["conceptIds"]) == 2
    assert len(data["criterionConcepts"]) == 2
    assert data["createdBy"] == DEV_FACULTY_ID


def test_faculty_cannot_map_cross_course_concepts(faculty_client):
    """
    Attempting to associate a concept from another course (AI301) to a CS101 assignment must be rejected.
    """
    payload = {
        "title": "Invalid Cross-Course Assignment",
        "description": "Cross course concept mapping test",
        "dueDate": "2026-12-25T23:59:59Z",
        "maxPoints": 100.0,
        "status": "published",
        "conceptIds": [
            "a3010000-c001-0000-0000-000000000001",  # belongs to AI301, not CS101!
        ],
    }
    res = faculty_client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        json=payload,
    )
    assert res.status_code == 400
    res_json = res.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "INVALID_CONCEPT_MAPPING"
    assert "Cross-course concept mapping is strictly forbidden" in res_json["error"]["message"]


def test_faculty_cannot_map_invalid_rubric_criterion(faculty_client):
    """
    Attempting to map a criterion ID that is not part of the selected rubric must be rejected.
    """
    payload = {
        "title": "Invalid Criterion Assignment",
        "description": "Criterion test",
        "dueDate": "2026-12-25T23:59:59Z",
        "maxPoints": 100.0,
        "status": "published",
        "rubricId": "rubric-1",
        "criterionConcepts": [
            {
                "criterionId": "non-existent-criterion-xyz",
                "conceptId": "c1010000-c001-0000-0000-000000000001",
            }
        ],
    }
    res = faculty_client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        json=payload,
    )
    assert res.status_code == 400
    res_json = res.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "INVALID_RUBRIC_CRITERION"


def test_faculty_course_isolation_on_assignments(client):
    """
    Faculty B cannot view, create, edit, or delete assignments for Faculty A's course.
    """
    headers_b = {"Authorization": f"Bearer mock-faculty-token:{OTHER_FACULTY_ID}"}

    # 1. Listing Faculty A's course assignments returns 403
    res_list = client.get(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        headers=headers_b,
    )
    assert res_list.status_code == 403
    assert res_list.json()["error"]["code"] == "FORBIDDEN_COURSE_ACCESS"

    # 2. Creating an assignment in Faculty A's course returns 403
    res_create = client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        headers=headers_b,
        json={"title": "Hacked", "dueDate": "2026-12-30T00:00:00Z"},
    )
    assert res_create.status_code == 403

    # 3. Reading assignment details for Faculty A's assignment returns 403
    res_detail = client.get(
        "/api/v1/faculty/assignments/assign-1",
        headers=headers_b,
    )
    assert res_detail.status_code == 403

    # 4. Updating Faculty A's assignment returns 403
    res_update = client.put(
        "/api/v1/faculty/assignments/assign-1",
        headers=headers_b,
        json={"title": "Unauthorized Title Change"},
    )
    assert res_update.status_code == 403


def test_faculty_update_assignment_publish_toggle(faculty_client):
    """
    Faculty can update assignment details and toggle status between draft and published.
    """
    # Create draft
    create_res = faculty_client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        json={
            "title": "Draft Topic",
            "description": "Work in progress",
            "dueDate": "2027-01-01T00:00:00Z",
            "status": "draft",
            "maxPoints": 50.0,
        },
    )
    assign_id = create_res.json()["data"]["id"]

    # Publish it
    update_res = faculty_client.put(
        f"/api/v1/faculty/assignments/{assign_id}",
        json={"status": "published", "title": "Published Topic", "maxPoints": 75.0},
    )
    assert update_res.status_code == 200
    updated = update_res.json()["data"]
    assert updated["status"] == "published"
    assert updated["title"] == "Published Topic"
    assert updated["maxPoints"] == 75.0


def test_faculty_delete_assignment(faculty_client):
    """
    Faculty can delete an assignment from their course.
    """
    create_res = faculty_client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        json={
            "title": "To be deleted",
            "dueDate": "2027-01-01T00:00:00Z",
            "status": "draft",
        },
    )
    assign_id = create_res.json()["data"]["id"]

    del_res = faculty_client.delete(f"/api/v1/faculty/assignments/{assign_id}")
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True

    # Detail check 404
    get_res = faculty_client.get(f"/api/v1/faculty/assignments/{assign_id}")
    assert get_res.status_code == 404


def test_student_list_published_assignments(student_client):
    """
    Student receives published assignments for enrolled courses with concept tags and rubric.
    Draft assignments are strictly hidden.
    """
    res = student_client.get("/api/v1/students/assignments")
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["success"] is True
    assigns = res_json["data"]

    # All returned assignments must be published
    for a in assigns:
        assert a["status"] == "published"
        assert a["id"] != "assign-draft-1"

    # Enrolled course assignments are present
    assign_ids = [a["id"] for a in assigns]
    assert "assign-1" in assign_ids
    assert "assign-2" in assign_ids


def test_student_cannot_view_draft_assignment_details(student_client):
    """
    Draft assignments must return 404 when requested by a student.
    """
    res = student_client.get("/api/v1/students/assignments/assign-draft-1")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ASSIGNMENT_NOT_FOUND"


def test_student_cannot_view_assignment_for_non_enrolled_course(client):
    """
    Student requesting an assignment for a course they are not enrolled in receives 403 Forbidden.
    """
    # Create an assignment in MATH201 (student is not enrolled in MATH201)
    # Using faculty B token to create assignment in MATH201
    headers_faculty_b = {"Authorization": f"Bearer mock-faculty-token:{OTHER_FACULTY_ID}"}
    create_res = client.post(
        f"/api/v1/faculty/courses/{MATH201_COURSE_ID}/assignments",
        headers=headers_faculty_b,
        json={
            "title": "MATH201 Midterm",
            "dueDate": "2026-12-01T00:00:00Z",
            "status": "published",
        },
    )
    math_assign_id = create_res.json()["data"]["id"]

    # Student tries to fetch assignment detail
    headers_student = {"Authorization": f"Bearer mock-student-token:{DEV_STUDENT_ID}"}
    student_res = client.get(
        f"/api/v1/students/assignments/{math_assign_id}",
        headers=headers_student,
    )
    assert student_res.status_code == 403
    assert student_res.json()["error"]["code"] == "NOT_ENROLLED"


def test_submission_to_draft_assignment_rejected(student_client):
    """
    Submissions to draft assignments must be rejected with 400 Bad Request.
    """
    payload = {
        "assignment_id": "assign-draft-1",
        "assignment_title": "Draft Homework",
        "course_code": "CS101",
        "rubric_id": "rubric-1",
        "text_content": "# Report on draft assignment",
    }
    res = student_client.post("/api/v1/submissions", data=payload)
    assert res.status_code == 400
    res_json = res.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "ASSIGNMENT_NOT_PUBLISHED"


def test_submission_to_non_enrolled_course_assignment_rejected(client):
    """
    Student submitting to a course they are not enrolled in is rejected with 403 Forbidden.
    """
    # Create assignment in MATH201
    headers_faculty_b = {"Authorization": f"Bearer mock-faculty-token:{OTHER_FACULTY_ID}"}
    create_res = client.post(
        f"/api/v1/faculty/courses/{MATH201_COURSE_ID}/assignments",
        headers=headers_faculty_b,
        json={
            "title": "MATH201 Quiz",
            "dueDate": "2026-12-01T00:00:00Z",
            "status": "published",
        },
    )
    math_assign_id = create_res.json()["data"]["id"]

    headers_student = {"Authorization": f"Bearer mock-student-token:{DEV_STUDENT_ID}"}
    payload = {
        "assignment_id": math_assign_id,
        "assignment_title": "MATH201 Quiz",
        "course_code": "MATH201",
        "rubric_id": "rubric-1",
        "text_content": "# Math Quiz submission",
    }
    res = client.post("/api/v1/submissions", headers=headers_student, data=payload)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "NOT_ENROLLED"


def test_submission_to_published_assignment_succeeds(student_client):
    """
    Student submitting to a published enrolled assignment succeeds and generates pending submission.
    """
    payload = {
        "assignment_id": "assign-2",
        "assignment_title": "Assignment 2: Graph Traversal",
        "course_code": "CS101",
        "rubric_id": "rubric-2",
        "text_content": "# Graph Analysis\nDijkstra algorithm implementation in Python.",
    }
    res = student_client.post("/api/v1/submissions", data=payload)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["studentId"] == DEV_STUDENT_ID
    assert data["assignmentId"] == "assign-2"
    assert data["status"] == "pending"


def test_faculty_cannot_map_criterion_without_rubric(faculty_client):
    """
    Attempting to provide criterion-to-concept mappings without associating a rubric must be rejected.
    """
    payload = {
        "title": "Assignment Without Rubric",
        "description": "Attempting criterion mapping with no rubric",
        "dueDate": "2026-12-25T23:59:59Z",
        "maxPoints": 100.0,
        "rubricId": None,
        "criterionConcepts": [
            {
                "criterionId": "crit-1-1",
                "conceptId": "c1010000-c001-0000-0000-000000000001",
            }
        ],
    }
    res = faculty_client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        json=payload,
    )
    assert res.status_code == 400
    res_json = res.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "RUBRIC_REQUIRED_FOR_CRITERIA"


def test_create_assignment_defaults_to_draft_when_status_omitted(faculty_client):
    """
    Omitting the status field during assignment creation defaults authoritatively to 'draft'.
    """
    payload = {
        "title": "Unspecified Status Assignment",
        "description": "Status omitted by caller",
        "dueDate": "2026-12-30T00:00:00Z",
        "maxPoints": 50.0,
    }
    res = faculty_client.post(
        f"/api/v1/faculty/courses/{CS101_COURSE_ID}/assignments",
        json=payload,
    )
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["status"] == "draft"


def test_faculty_cannot_remove_rubric_while_criterion_mappings_exist(faculty_client):
    """
    Updating an assignment to clear its rubric while criterion mappings exist must be rejected.
    """
    # assign-1 has rubric-1 and criterionConcepts
    res = faculty_client.put(
        "/api/v1/faculty/assignments/assign-1",
        json={"rubricId": ""},
    )
    assert res.status_code == 400
    res_json = res.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "RUBRIC_REQUIRED_FOR_CRITERIA"


def test_faculty_cannot_change_to_incompatible_rubric(faculty_client):
    """
    Changing an assignment's rubric to one that does not define the mapped criteria must be rejected.
    """
    # assign-1 has mapped criteria from rubric-1 ('crit-1-1').
    # rubric-2 has criteria 'crit-2-1', 'crit-2-2' (so 'crit-1-1' is not present).
    res = faculty_client.put(
        "/api/v1/faculty/assignments/assign-1",
        json={"rubricId": "rubric-2"},
    )
    assert res.status_code == 400
    res_json = res.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "INCOMPATIBLE_RUBRIC_CHANGE"
