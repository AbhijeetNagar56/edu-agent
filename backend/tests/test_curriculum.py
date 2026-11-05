import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.repository import DEV_FACULTY_ID, DEV_STUDENT_ID, OTHER_FACULTY_ID, db, SEED_COURSES

client = TestClient(app)


def test_faculty_can_list_owned_courses():
    """Faculty should only see courses they own unless they are admin."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    response = client.get("/api/v1/faculty/courses", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    courses = data["data"]
    assert len(courses) >= 2
    # Check that all returned courses have facultyId == DEV_FACULTY_ID
    for c in courses:
        assert c["facultyId"] == DEV_FACULTY_ID
    codes = [c["code"] for c in courses]
    assert "CS101" in codes
    assert "AI301" in codes
    assert "MATH201" not in codes  # MATH201 is owned by OTHER_FACULTY_ID


def test_faculty_can_create_course():
    """Faculty can create a new course. Faculty identity is derived strictly from authentication."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    payload = {
        "code": "CS202",
        "name": "Advanced Data Structures and Operating Systems",
        "description": "Virtual memory, multi-threading, and concurrent lock-free trees."
    }
    response = client.post("/api/v1/faculty/courses", json=payload, headers=headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["success"] is True
    created = res_data["data"]
    assert created["code"] == "CS202"
    assert created["facultyId"] == DEV_FACULTY_ID
    assert created["description"] == payload["description"]


def test_duplicate_course_code_is_rejected():
    """Cannot register two courses with the exact same course code."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    payload = {
        "code": "CS101",
        "name": "Duplicate Computer Science",
        "description": "Conflict attempt"
    }
    response = client.post("/api/v1/faculty/courses", json=payload, headers=headers)
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "DUPLICATE_COURSE_CODE"


def test_faculty_cannot_access_another_facultys_curriculum():
    """Faculty A cannot view or edit curriculum for a course owned by Faculty B."""
    faculty_a_headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    math_course_id = "m2010000-0000-0000-0000-000000000003"  # Owned by OTHER_FACULTY_ID

    # 1. Attempt GET curriculum
    res_get = client.get(f"/api/v1/faculty/courses/{math_course_id}/curriculum", headers=faculty_a_headers)
    assert res_get.status_code == 403
    assert res_get.json()["error"]["code"] == "FORBIDDEN"

    # 2. Attempt POST concept
    res_post = client.post(
        f"/api/v1/faculty/courses/{math_course_id}/concepts",
        json={"name": "Forbidden Logic", "difficulty": "intermediate"},
        headers=faculty_a_headers
    )
    assert res_post.status_code == 403

    # 3. Authorized faculty CAN access their own course
    faculty_b_headers = {"Authorization": f"Bearer mock-faculty-token:{OTHER_FACULTY_ID}"}
    res_auth = client.get(f"/api/v1/faculty/courses/{math_course_id}/curriculum", headers=faculty_b_headers)
    assert res_auth.status_code == 200


def test_student_cannot_modify_curriculum():
    """Students attempting to create, update, or delete concepts or edges are rejected with 403 Forbidden."""
    student_headers = {"Authorization": f"Bearer mock-student-token:{DEV_STUDENT_ID}"}
    cs101_id = "c1010000-0000-0000-0000-000000000001"

    # 1. Attempt to list faculty courses
    res_list = client.get("/api/v1/faculty/courses", headers=student_headers)
    assert res_list.status_code == 403

    # 2. Attempt to create concept
    res_create = client.post(
        f"/api/v1/faculty/courses/{cs101_id}/concepts",
        json={"name": "Hacked Node"},
        headers=student_headers
    )
    assert res_create.status_code == 403


def test_unauthenticated_requests_rejected():
    """Unauthenticated requests are rejected with 401 Unauthorized."""
    cs101_id = "c1010000-0000-0000-0000-000000000001"
    res = client.get(f"/api/v1/faculty/courses/{cs101_id}/curriculum")
    assert res.status_code == 401


def test_concept_crud_lifecycle_and_cascade_edge_deletion():
    """Faculty can create, update, and delete concepts, and deleting a concept cleans up dependent edges."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    course_id = "c1010000-0000-0000-0000-000000000001"

    # 1. Create concept
    concept_payload = {
        "name": "Dynamic Programming",
        "description": "Optimal substructure and memoization tables.",
        "category": "Algorithms",
        "difficulty": "advanced",
        "posX": 800.0,
        "posY": 400.0,
    }
    res_create = client.post(f"/api/v1/faculty/courses/{course_id}/concepts", json=concept_payload, headers=headers)
    assert res_create.status_code == 201
    concept_data = res_create.json()["data"]
    concept_id = concept_data["id"]
    assert concept_data["name"] == "Dynamic Programming"
    assert concept_data["category"] == "Algorithms"
    assert concept_data["difficulty"] == "advanced"

    # 2. Update concept
    update_payload = {
        "description": "Memoization tables and bottom-up DP algorithms.",
        "posX": 820.0,
        "posY": 420.0,
    }
    res_update = client.put(f"/api/v1/faculty/courses/{course_id}/concepts/{concept_id}", json=update_payload, headers=headers)
    assert res_update.status_code == 200
    updated_data = res_update.json()["data"]
    assert updated_data["description"] == update_payload["description"]
    assert updated_data["posX"] == 820.0

    # 3. Create prerequisite edge to this concept
    # Divide & Conquer (c1010000-c005-0000-0000-000000000005) -> Dynamic Programming
    from_concept = "c1010000-c005-0000-0000-000000000005"
    edge_payload = {
        "fromConcept": from_concept,
        "toConcept": concept_id,
    }
    res_edge = client.post(f"/api/v1/faculty/courses/{course_id}/edges", json=edge_payload, headers=headers)
    assert res_edge.status_code == 201
    edge_id = res_edge.json()["data"]["id"]

    # Verify edge exists in graph
    res_graph = client.get(f"/api/v1/faculty/courses/{course_id}/curriculum", headers=headers)
    assert res_graph.status_code == 200
    edge_ids = [e["id"] for e in res_graph.json()["data"]["edges"]]
    assert edge_id in edge_ids

    # 4. Delete concept
    res_del = client.delete(f"/api/v1/faculty/courses/{course_id}/concepts/{concept_id}", headers=headers)
    assert res_del.status_code == 200

    # 5. Verify concept is gone AND the dependent edge is cascaded / removed
    res_graph_after = client.get(f"/api/v1/faculty/courses/{course_id}/curriculum", headers=headers)
    assert res_graph_after.status_code == 200
    graph_after = res_graph_after.json()["data"]
    concept_ids_after = [c["id"] for c in graph_after["concepts"]]
    edge_ids_after = [e["id"] for e in graph_after["edges"]]
    assert concept_id not in concept_ids_after
    assert edge_id not in edge_ids_after


def test_prerequisite_edge_dag_cycle_rejection():
    """Graph must reject self-loops, 2-node cycles, and multi-node cycles."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    course_id = "c1010000-0000-0000-0000-000000000001"

    # In CS101, existing chain:
    # c1 -> c2 -> c4 -> c6
    c1 = "c1010000-c001-0000-0000-000000000001"
    c2 = "c1010000-c002-0000-0000-000000000002"
    c6 = "c1010000-c006-0000-0000-000000000006"

    # 1. Self loop rejection: c1 -> c1
    res_self = client.post(f"/api/v1/faculty/courses/{course_id}/edges", json={"fromConcept": c1, "toConcept": c1}, headers=headers)
    assert res_self.status_code in [400, 422]

    # 2. 2-node cycle rejection: c2 -> c1 (since c1 -> c2 already exists)
    res_2node = client.post(f"/api/v1/faculty/courses/{course_id}/edges", json={"fromConcept": c2, "toConcept": c1}, headers=headers)
    assert res_2node.status_code == 400
    assert res_2node.json()["error"]["code"] == "CYCLE_DETECTED"

    # 3. Multi-node cycle rejection: c6 -> c1 (since c1 -> c2 -> c4 -> c6 exists)
    res_multi = client.post(f"/api/v1/faculty/courses/{course_id}/edges", json={"fromConcept": c6, "toConcept": c1}, headers=headers)
    assert res_multi.status_code == 400
    assert res_multi.json()["error"]["code"] == "CYCLE_DETECTED"


def test_cross_course_prerequisite_edge_rejection():
    """Prerequisite edges cannot connect concepts across different courses."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    cs101_id = "c1010000-0000-0000-0000-000000000001"

    cs_concept = "c1010000-c001-0000-0000-000000000001"  # CS101
    ai_concept = "a3010000-c001-0000-0000-000000000001"  # AI301

    res = client.post(
        f"/api/v1/faculty/courses/{cs101_id}/edges",
        json={"fromConcept": cs_concept, "toConcept": ai_concept},
        headers=headers
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "CROSS_COURSE_EDGE"


def test_duplicate_prerequisite_edge_rejection():
    """Duplicate prerequisite edges between the same two concepts are rejected."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    cs101_id = "c1010000-0000-0000-0000-000000000001"

    # c1 -> c2 already exists in seed
    c1 = "c1010000-c001-0000-0000-000000000001"
    c2 = "c1010000-c002-0000-0000-000000000002"

    res = client.post(
        f"/api/v1/faculty/courses/{cs101_id}/edges",
        json={"fromConcept": c1, "toConcept": c2},
        headers=headers
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "DUPLICATE_EDGE"


def test_save_curriculum_layout_batch_update():
    """Faculty can save updated node coordinates and layout."""
    headers = {"Authorization": f"Bearer mock-faculty-token:{DEV_FACULTY_ID}"}
    cs101_id = "c1010000-0000-0000-0000-000000000001"

    payload = {
        "positions": [
            {"id": "c1010000-c001-0000-0000-000000000001", "posX": 150.0, "posY": 250.0},
            {"id": "c1010000-c002-0000-0000-000000000002", "posX": 400.0, "posY": 150.0},
        ]
    }
    res = client.put(f"/api/v1/faculty/courses/{cs101_id}/curriculum", json=payload, headers=headers)
    assert res.status_code == 200
    graph = res.json()["data"]
    concept_map = {c["id"]: c for c in graph["concepts"]}
    assert concept_map["c1010000-c001-0000-0000-000000000001"]["posX"] == 150.0
    assert concept_map["c1010000-c001-0000-0000-000000000001"]["posY"] == 250.0


def test_student_read_only_curriculum_learning_graph():
    """Students can fetch the canonical course curriculum graph overlaid with their mastery records."""
    student_headers = {"Authorization": f"Bearer mock-student-token:{DEV_STUDENT_ID}"}
    cs101_id = "c1010000-0000-0000-0000-000000000001"

    res = client.get(f"/api/v1/students/courses/{cs101_id}/curriculum", headers=student_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["courseId"] == cs101_id
    assert data["studentId"] == DEV_STUDENT_ID
    assert len(data["concepts"]) >= 6
    assert len(data["edges"]) >= 6
    # Each concept should include mastery fields
    for c in data["concepts"]:
        assert "masteryScore" in c
        assert "masteryPercentage" in c
        assert "confidence" in c
        assert "masterySource" in c
