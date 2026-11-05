import io
import pytest
from unittest.mock import patch
from app.ai.extract import RateLimitException
from app.core.config import settings
from app.models.common import JobStatus
from app.services.queue import QueueService
from app.services.repository import Repository, db


def test_file_size_exceeds_limit(student_client):
    large_bytes = b"0" * (settings.MAX_FILE_SIZE_BYTES + 1024)
    files = {"file": ("large_submission.pdf", io.BytesIO(large_bytes), "application/pdf")}
    data = {
        "student_id": "00000000-0000-0000-0000-000000000302",
        "student_name": "Large File Student",
        "student_email": "large@university.edu",
        "assignment_id": "assign-1",
        "assignment_title": "Assignment 1",
        "course_code": "CS101",
        "rubric_id": "rubric-1",
    }
    response = student_client.post("/api/v1/submissions", data=data, files=files)
    assert response.status_code == 413
    res_json = response.json()
    assert res_json["success"] is False
    assert res_json["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_faculty_submissions_filtering(faculty_client):
    # Filter by course CS101
    res_cs101 = faculty_client.get("/api/v1/faculty/submissions?course_code=CS101")
    assert res_cs101.status_code == 200
    for sub in res_cs101.json()["data"]:
        assert sub["courseCode"] == "CS101"

    # Filter by status done
    res_done = faculty_client.get("/api/v1/faculty/submissions?status=done")
    assert res_done.status_code == 200
    for sub in res_done.json()["data"]:
        assert sub["status"] == "done"

    # Filter by status overridden
    res_overridden = faculty_client.get("/api/v1/faculty/submissions?status=overridden")
    assert res_overridden.status_code == 200
    for sub in res_overridden.json()["data"]:
        assert sub["override"] is not None
        assert sub["override"]["isOverridden"] is True

    # Search filter
    res_search = faculty_client.get("/api/v1/faculty/submissions?search=Rivera")
    assert res_search.status_code == 200
    assert len(res_search.json()["data"]) >= 1
    assert "Rivera" in res_search.json()["data"][0]["studentName"]


def test_rubrics_filter_by_course(faculty_client):
    res = faculty_client.get("/api/v1/faculty/rubrics?course_code=AI301")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) >= 1
    for r in data:
        assert r["courseCode"] == "AI301"


@pytest.mark.anyio
async def test_queue_rate_limit_retry_handling():
    # Enqueue a mock job
    job = QueueService.enqueue_submission("sub-104")
    assert job.status == JobStatus.PENDING

    # Mock pipeline to throw RateLimitException
    with patch("app.services.queue.run_evaluation_pipeline", side_effect=RateLimitException("Quota exceeded")):
        result = await QueueService.process_batch(batch_size=5)
        assert result.retriedCount >= 1

        # Check job status remained/reset to pending and retry count increased
        updated_job = Repository.get_job_by_submission_id("sub-104")
        assert updated_job is not None
        assert updated_job.status == JobStatus.PENDING
        assert updated_job.retryCount >= 1
