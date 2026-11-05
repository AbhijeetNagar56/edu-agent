import pytest
import uuid
import time
from unittest.mock import patch, AsyncMock
from app.models.common import JobStatus, ProcessingStep
from app.models.job import GradingJob
from app.models.submission import Submission
from app.models.rubric import Rubric, RubricCriterion
from app.models.evaluation import EvaluationResult, CriterionEvaluation
from app.services.repository import Repository, db
from app.services.queue import QueueService
from app.ai.extract import RateLimitException


def make_submission(**kwargs) -> Submission:
    defaults = {
        "id": f"sub-{uuid.uuid4().hex[:6]}",
        "studentId": "student-1",
        "studentName": "Alex Student",
        "studentEmail": "alex@university.edu",
        "assignmentId": "assign-1",
        "assignmentTitle": "Assignment 1",
        "courseCode": "CS101",
        "fileName": "solution.py",
        "fileSize": "12 KB",
        "fileType": "text",
        "status": JobStatus.PENDING,
        "submittedAt": "2026-11-05T00:00:00Z",
        "rubricId": "rub-1",
    }
    defaults.update(kwargs)
    return Submission(**defaults)


@pytest.fixture(autouse=True)
def clean_queue_state():
    orig_jobs = dict(db.grading_jobs)
    orig_subs = dict(db.submissions)
    orig_rubrics = dict(db.rubrics)
    db.grading_jobs.clear()
    yield
    db.grading_jobs = orig_jobs
    db.submissions = orig_subs
    db.rubrics = orig_rubrics


def test_atomic_claim_and_concurrency_lock():
    """
    Test 1: Worker claiming and concurrency protection
    When Worker A claims a job, it is locked.
    Worker B cannot claim the same job concurrently.
    """
    sub_id = f"sub-{uuid.uuid4().hex[:6]}"
    job_id = f"job-{uuid.uuid4().hex[:6]}"

    job = GradingJob(
        id=job_id,
        submissionId=sub_id,
        status=JobStatus.PENDING,
        retryCount=0,
        maxRetries=3,
    )
    Repository.save_job(job)

    # Worker 1 claims the job
    claimed_1 = Repository.claim_grading_job(worker_id="worker-1", stale_interval_seconds=300)
    assert claimed_1 is not None
    assert claimed_1.id == job_id
    assert claimed_1.status == JobStatus.PROCESSING
    assert claimed_1.lockedBy == "worker-1"

    # Worker 2 attempts to claim while locked
    claimed_2 = Repository.claim_grading_job(worker_id="worker-2", stale_interval_seconds=300)
    # Must be None since the only job is locked
    assert claimed_2 is None


def test_stale_job_recovery():
    """
    Test 2: Abandoned job past stale interval is re-claimed
    """
    sub_id = f"sub-{uuid.uuid4().hex[:6]}"
    job_id = f"job-{uuid.uuid4().hex[:6]}"

    stale_iso = "2020-01-01T00:00:00+00:00"
    job = GradingJob(
        id=job_id,
        submissionId=sub_id,
        status=JobStatus.PROCESSING,
        retryCount=0,
        maxRetries=3,
        lockedBy="crashed-worker",
        lockedAt=stale_iso,
    )
    Repository.save_job(job)

    # Healthy worker claims it
    reclaimed = Repository.claim_grading_job(worker_id="healthy-worker", stale_interval_seconds=300)
    assert reclaimed is not None
    assert reclaimed.id == job_id
    assert reclaimed.lockedBy == "healthy-worker"


@pytest.mark.asyncio
async def test_unextractable_document_transitions_to_manual_review():
    """
    Test 3: Empty or scanned document transitions to manual_review
    Automated AI grading is bypassed to avoid hallucinated scores.
    """
    sub_id = f"sub-empty-{uuid.uuid4().hex[:6]}"
    job_id = f"job-empty-{uuid.uuid4().hex[:6]}"

    sub = make_submission(
        id=sub_id,
        fileName="scanned_handwriting.pdf",
        status=JobStatus.PENDING,
    )
    Repository.save_submission(sub)

    job = GradingJob(
        id=job_id,
        submissionId=sub_id,
        status=JobStatus.PENDING,
        retryCount=0,
        maxRetries=3,
    )
    Repository.save_job(job)

    # Storage returns unextractable marker
    with patch("app.services.storage.StorageService.get_submission_text", return_value="[UNEXTRACTABLE_PDF] Scanned image without OCR text"):
        with patch("app.services.queue.run_evaluation_pipeline") as mock_pipeline:
            result = await QueueService.process_batch(batch_size=5, worker_id="test-worker")

            # AI pipeline MUST NOT be called
            mock_pipeline.assert_not_called()

    # Submission status must be manual_review
    saved_sub = Repository.get_submission_by_id(sub_id)
    assert saved_sub.status == JobStatus.MANUAL_REVIEW

    # Job status must be manual_review
    saved_job = Repository.get_job_by_submission_id(sub_id)
    assert saved_job.status == JobStatus.MANUAL_REVIEW
    assert "manual review" in saved_job.errorLog.lower()


@pytest.mark.asyncio
async def test_rate_limit_retry_and_exhaustion():
    """
    Test 4: Rate limit retries and exhaustion
    - When RateLimitException is caught, retryCount increments and resets to PENDING.
    - When retryCount reaches maxRetries, job fails and submission is FLAGGED.
    """
    sub_id = f"sub-rl-{uuid.uuid4().hex[:6]}"
    job_id = f"job-rl-{uuid.uuid4().hex[:6]}"

    sub = make_submission(
        id=sub_id,
        fileName="code.py",
        status=JobStatus.PENDING,
        rubricId="rub-1",
    )
    Repository.save_submission(sub)

    # Setup valid rubric so we reach pipeline
    db.rubrics["rub-1"] = Rubric(
        id="rub-1",
        courseCode="CS101",
        assignmentTitle="Test",
        description="",
        criteria=[RubricCriterion(id="c1", title="Code Quality", description="", maxPoints=10.0)],
        totalPoints=10.0,
        createdAt="2026-01-01T00:00:00Z"
    )

    job = GradingJob(
        id=job_id,
        submissionId=sub_id,
        status=JobStatus.PENDING,
        retryCount=0,
        maxRetries=2,
    )
    Repository.save_job(job)

    valid_code_text = "def calculate_statistics(numbers):\n    total = sum(numbers)\n    return total / len(numbers)"

    # Attempt 1: Rate limited
    with patch("app.services.storage.StorageService.get_submission_text", return_value=valid_code_text):
        with patch("app.services.queue.run_evaluation_pipeline", side_effect=RateLimitException("429 Too Many Requests")):
            res1 = await QueueService.process_batch(batch_size=5, worker_id="worker-rl")
            assert res1.retriedCount == 1

    saved_job = Repository.get_job_by_submission_id(sub_id)
    assert saved_job.retryCount == 1
    assert saved_job.status == JobStatus.PENDING

    # Attempt 2: Rate limited again -> hits maxRetries (2) -> FAILS
    with patch("app.services.storage.StorageService.get_submission_text", return_value=valid_code_text):
        with patch("app.services.queue.run_evaluation_pipeline", side_effect=RateLimitException("429 Too Many Requests")):
            res2 = await QueueService.process_batch(batch_size=5, worker_id="worker-rl")
            assert res2.failedCount == 1

    saved_job2 = Repository.get_job_by_submission_id(sub_id)
    assert saved_job2.retryCount == 2
    assert saved_job2.status == JobStatus.FAILED
    assert "max retries" in saved_job2.errorLog.lower()

    saved_sub2 = Repository.get_submission_by_id(sub_id)
    assert saved_sub2.status == JobStatus.FLAGGED
