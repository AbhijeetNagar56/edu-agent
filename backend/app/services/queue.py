from datetime import datetime, timezone
import time
from typing import Optional
import uuid

from app.core.config import settings
from app.core.logging import logger
from app.models.common import JobStatus, ProcessingStep
from app.models.job import GradingJob, JobProcessItemResult, BatchProcessResult
from app.services.repository import Repository
from app.services.realtime import RealtimeService
from app.services.storage import StorageService
from app.ai.pipeline import run_evaluation_pipeline
from app.ai.extract import RateLimitException


class QueueService:
    @staticmethod
    def enqueue_submission(submission_id: str) -> GradingJob:
        job_id = f"job-{int(time.time() * 1000) % 100000}"
        job = GradingJob(
            id=job_id,
            submissionId=submission_id,
            status=JobStatus.PENDING,
            retryCount=0,
            maxRetries=3,
            startedAt=None,
            completedAt=None,
        )
        Repository.save_job(job)
        logger.info(f"Enqueued grading job {job.id} for submission {submission_id}")
        return job

    @staticmethod
    async def process_batch(batch_size: int = 10, worker_id: Optional[str] = None) -> BatchProcessResult:
        """
        Drains up to batch_size pending or abandoned jobs from the queue using atomic claims,
        evaluates submissions with the Gemini AI pipeline, persists evaluations,
        updates concept mastery, and emits Realtime events.
        """
        batch_size = max(1, min(batch_size, 25))
        worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"

        succeeded = 0
        failed = 0
        retried = 0
        manual_reviews = 0
        job_results = []
        claimed_jobs = []

        # Claim jobs atomically one by one up to batch_size (FOR UPDATE SKIP LOCKED)
        for _ in range(batch_size):
            job = Repository.claim_grading_job(worker_id=worker_id, stale_interval_seconds=300)
            if not job:
                break
            claimed_jobs.append(job)

        # Fallback if no jobs were claimed via atomic claim (e.g. mock DB in test mode)
        if not claimed_jobs:
            pending_jobs = Repository.get_pending_grading_jobs(limit=batch_size)
            for j in pending_jobs:
                j.status = JobStatus.PROCESSING
                j.lockedBy = worker_id
                j.lockedAt = datetime.now(timezone.utc).isoformat()
                j.startedAt = j.startedAt or datetime.now(timezone.utc).isoformat()
                Repository.save_job(j)
                claimed_jobs.append(j)

        for job in claimed_jobs:
            start_job_time = time.time()
            sub = Repository.get_submission_by_id(job.submissionId)
            if not sub:
                job.status = JobStatus.FAILED
                job.errorLog = f"Submission {job.submissionId} not found."
                job.completedAt = datetime.now(timezone.utc).isoformat()
                Repository.save_job(job)
                failed += 1
                job_results.append(
                    JobProcessItemResult(
                        jobId=job.id,
                        submissionId=job.submissionId,
                        status="failed",
                        error="Submission not found",
                    )
                )
                continue

            # Update submission step to extracting
            sub.status = JobStatus.PROCESSING
            sub.processingStep = ProcessingStep.EXTRACTING
            Repository.save_submission(sub)

            try:
                # Retrieve raw content
                raw_content = StorageService.get_submission_text(sub.id, sub.fileName, sub.contentPreview)

                # Check for unextractable, blank, or scanned PDF
                if StorageService.is_unextractable_or_empty(raw_content):
                    logger.warning(f"Submission {sub.id} is unextractable or blank; transitioning to manual_review.")
                    sub.status = JobStatus.MANUAL_REVIEW
                    sub.processingStep = None
                    Repository.save_submission(sub)

                    job.status = JobStatus.MANUAL_REVIEW
                    job.errorLog = "Submission file contains no machine-readable text or is a scanned/empty document. Flagged for manual review."
                    job.completedAt = datetime.now(timezone.utc).isoformat()
                    Repository.save_job(job)

                    manual_reviews += 1
                    job_results.append(
                        JobProcessItemResult(
                            jobId=job.id,
                            submissionId=sub.id,
                            status="manual_review",
                            error="File unextractable or empty",
                        )
                    )

                    await RealtimeService.broadcast_submission_update(
                        submission_id=sub.id,
                        status="manual_review",
                        processing_step=None,
                        course_code=sub.courseCode,
                    )
                    continue

                # Retrieve rubric
                rubric = Repository.get_rubric_by_id(sub.rubricId)
                if not rubric:
                    rubrics = Repository.get_rubrics()
                    rubric = rubrics[0] if rubrics else None

                if not rubric:
                    raise Exception(f"Rubric {sub.rubricId} not found and no default available.")

                # Update step to grading
                sub.processingStep = ProcessingStep.GRADING
                Repository.save_submission(sub)

                # Run two-step AI pipeline
                eval_result, duration_ms = await run_evaluation_pipeline(sub, rubric, raw_content)

                # Calculate concept evidence and update student concept mastery
                concept_feedback = Repository.record_concept_evidence_and_update_mastery(sub, eval_result)
                eval_result.conceptFeedback = concept_feedback

                # Save evaluation on submission
                sub.status = JobStatus.DONE
                sub.processingStep = ProcessingStep.SYNCED
                sub.evaluation = eval_result
                Repository.save_submission(sub)

                # Mark job completed
                job.status = JobStatus.DONE
                job.completedAt = datetime.now(timezone.utc).isoformat()
                job.errorLog = None
                Repository.save_job(job)

                succeeded += 1
                job_results.append(
                    JobProcessItemResult(
                        jobId=job.id,
                        submissionId=sub.id,
                        status="done",
                        score=eval_result.score,
                        durationMs=duration_ms,
                    )
                )

                # Broadcast Realtime update
                await RealtimeService.broadcast_submission_update(
                    submission_id=sub.id,
                    status="done",
                    processing_step="synced",
                    score=eval_result.score,
                    max_score=eval_result.maxScore,
                    course_code=sub.courseCode,
                )

            except RateLimitException as rle:
                # Rate limit handling: bounded retries
                logger.warning(f"Rate limited while processing job {job.id}: {rle}")
                job.retryCount += 1
                if job.retryCount >= job.maxRetries:
                    job.status = JobStatus.FAILED
                    job.errorLog = f"Max retries ({job.maxRetries}) exceeded: {str(rle)}"
                    job.completedAt = datetime.now(timezone.utc).isoformat()
                    Repository.save_job(job)

                    sub.status = JobStatus.FLAGGED
                    sub.processingStep = None
                    Repository.save_submission(sub)

                    failed += 1
                    job_results.append(
                        JobProcessItemResult(
                            jobId=job.id,
                            submissionId=sub.id,
                            status="failed",
                            error=f"Max retries exceeded: {str(rle)}",
                        )
                    )
                else:
                    job.status = JobStatus.PENDING
                    job.errorLog = f"Rate limited: {str(rle)}"
                    job.lockedBy = None
                    job.lockedAt = None
                    Repository.save_job(job)

                    sub.status = JobStatus.PENDING
                    sub.processingStep = ProcessingStep.QUEUED
                    Repository.save_submission(sub)

                    retried += 1
                    job_results.append(
                        JobProcessItemResult(
                            jobId=job.id,
                            submissionId=sub.id,
                            status="pending",
                            error="Rate limited. Retrying on next iteration.",
                        )
                    )

            except Exception as e:
                logger.error(f"Error processing job {job.id} for submission {sub.id}: {e}")
                job.status = JobStatus.FAILED
                job.errorLog = str(e)
                job.completedAt = datetime.now(timezone.utc).isoformat()
                Repository.save_job(job)

                sub.status = JobStatus.FLAGGED
                sub.processingStep = None
                Repository.save_submission(sub)

                failed += 1
                job_results.append(
                    JobProcessItemResult(
                        jobId=job.id,
                        submissionId=sub.id,
                        status="flagged",
                        error=str(e),
                    )
                )

        return BatchProcessResult(
            processedCount=len(claimed_jobs),
            succeededCount=succeeded,
            failedCount=failed,
            retriedCount=retried,
            jobs=job_results,
        )
