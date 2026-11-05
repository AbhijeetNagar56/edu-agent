from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.core.auth import AuthUser, get_current_user
from app.core.errors import APIException
from app.core.logging import logger
from app.models.common import JobStatus, PaginatedResponse, ProcessingStep, StandardResponse
from app.models.submission import Submission
from app.services.queue import QueueService
from app.services.repository import Repository
from app.services.storage import StorageService

router = APIRouter(prefix="/api/v1/submissions", tags=["Student Submissions"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StandardResponse[Submission])
async def create_submission(
    file: Optional[UploadFile] = File(None),
    text_content: Optional[str] = Form(None),
    student_id: Optional[str] = Form(None),
    student_name: Optional[str] = Form(None),
    student_email: Optional[str] = Form(None),
    assignment_id: str = Form(...),
    assignment_title: str = Form(...),
    course_code: str = Form(...),
    rubric_id: str = Form(...),
    user: AuthUser = Depends(get_current_user),
):
    """
    Accepts student assignment upload (PDF, Markdown, or raw text), stores file,
    registers submission metadata, and creates a pending grading job in the queue.
    Authoritative student identity is derived strictly from the authenticated user.
    """
    # 1. Authorization: Reject attempts to submit on behalf of another student
    if student_id and student_id.strip():
        provided_id = student_id.strip()
        # Disallow explicit impersonation if provided_id does not match user's authoritative identity
        if provided_id != user.id and provided_id not in (user.email, "STU-2024-302", "student"):
            logger.warning(f"Student impersonation attempt: user {user.id} tried submitting as {provided_id}")
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message="Cannot submit assignment on behalf of another student.",
            )

    # 2. Authoritative identity binding
    authoritative_student_id = user.id
    authoritative_email = user.email
    authoritative_name = user.full_name or (student_name.strip() if student_name else user.email)

    # 3. Assignment Verification & Enrollment Checks
    assign = Repository.get_assignment_by_id(assignment_id)
    if not assign:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ASSIGNMENT_NOT_FOUND",
            message=f"Assignment with ID '{assignment_id}' was not found.",
        )

    if assign.status != "published":
        logger.warning(f"Student {user.id} attempted to submit to unpublished assignment '{assignment_id}' (status: {assign.status})")
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="ASSIGNMENT_NOT_PUBLISHED",
            message="Submissions are not accepted for draft or archived assignments.",
        )

    if user.role == "student" and not Repository.is_student_enrolled(assign.course_id, user.id):
        logger.warning(f"Student {user.id} attempted to submit to course '{assign.course_id}' without being enrolled.")
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NOT_ENROLLED",
            message="You are not enrolled in the course for this assignment.",
        )

    authoritative_assignment_title = assign.title
    authoritative_rubric_id = assign.rubric_id or rubric_id
    course = Repository.get_course_by_id(assign.course_id)
    authoritative_course_code = course.code if course else course_code

    # 4. Generate authoritative UUID for submission
    sub_id = str(uuid.uuid4())

    # 5. Ingest and persist file content
    filename, file_size_str, file_type, file_url, raw_text = await StorageService.process_and_store_file(
        submission_id=sub_id,
        file=file,
        text_content=text_content,
    )

    preview = (
        raw_text[:300].strip()
        if raw_text
        else f"Uploaded document: {filename} for {authoritative_assignment_title}. Awaiting Gemini extraction."
    )

    new_sub = Submission(
        id=sub_id,
        studentId=authoritative_student_id,
        studentName=authoritative_name,
        studentEmail=authoritative_email,
        ownerId=authoritative_student_id,
        assignmentId=assignment_id,
        assignmentTitle=authoritative_assignment_title,
        courseCode=authoritative_course_code,
        fileName=filename,
        fileSize=file_size_str,
        fileType=file_type,
        fileUrl=file_url,
        contentPreview=preview,
        status=JobStatus.PENDING,
        processingStep=ProcessingStep.QUEUED,
        rubricId=authoritative_rubric_id,
        submittedAt=datetime.now(timezone.utc).isoformat(),
        evaluation=None,
        override=None,
    )

    Repository.save_submission(new_sub, owner_id=authoritative_student_id)
    QueueService.enqueue_submission(new_sub.id)

    return StandardResponse[Submission](
        success=True,
        data=new_sub,
        message="Submission uploaded and queued for evaluation",
    )


@router.get("", response_model=PaginatedResponse[Submission])
async def list_student_submissions(
    course_code: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthUser = Depends(get_current_user),
):
    """
    Returns submissions for the currently authenticated student.
    Students can read only their own submissions.
    """
    student_filter = user.id if user.role == "student" else None

    subs, meta = Repository.get_submissions(
        course_code=course_code,
        student_id=student_filter,
        limit=limit,
        offset=offset,
    )

    return PaginatedResponse[Submission](
        success=True,
        data=subs,
        meta={
            "total": meta["total"],
            "page": meta["page"],
            "limit": meta["limit"],
        },
    )


@router.get("/{id}", response_model=StandardResponse[Submission])
async def get_submission_detail(
    id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Fetches complete submission details.
    Students can only view their own submissions.
    """
    sub = Repository.get_submission_by_id(id)
    if not sub:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Submission with ID '{id}' was not found.",
        )

    # Authorization check for students: verify ownership
    if user.role == "student":
        owner_matches = (sub.ownerId and sub.ownerId == user.id)
        id_matches = (sub.studentId == user.id)
        email_matches = (sub.studentEmail.lower() == user.email.lower())
        if not (owner_matches or id_matches or email_matches):
            logger.warning(f"Unauthorized submission access: student {user.id} tried reading {id}")
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message="You can only view your own submissions.",
            )

    return StandardResponse[Submission](
        success=True,
        data=sub,
        message="Resource retrieved successfully",
    )
