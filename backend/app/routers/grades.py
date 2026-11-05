from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status as http_status

from app.core.auth import AuthUser, get_current_user, require_role
from app.core.errors import APIException
from app.core.logging import logger
from app.models.common import PaginatedResponse, StandardResponse
from app.models.evaluation import FacultyOverride, FacultyOverrideRequest
from app.models.rubric import Rubric, RubricCreate, RubricCriterion, RubricUpdate
from app.models.submission import Submission
from app.services.repository import Repository
from app.services.queue import QueueService

router = APIRouter(prefix="/api/v1/faculty", tags=["Faculty Operations"])


@router.post("/process-jobs", response_model=StandardResponse[Dict[str, Any]])
async def process_jobs_as_faculty(
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """Allow faculty to trigger a grading batch from the dashboard."""
    result = await QueueService.process_batch()
    return StandardResponse[Dict[str, Any]](
        success=True,
        data=result.model_dump(by_alias=True),
        message="Batch completed successfully",
    )


@router.get("/submissions", response_model=PaginatedResponse[Submission])
async def list_faculty_submissions(
    course_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    assignment_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Retrieves submissions across the roster with filtering by course, status, and search query.
    Faculty can access only submissions for courses they are authorized to manage.
    """
    if course_code and course_code != "ALL":
        if not Repository.is_course_authorized(course_code, user):
            logger.warning(f"Faculty {user.id} unauthorized for course {course_code}")
            raise APIException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message=f"You are not authorized to view submissions for course '{course_code}'.",
            )

    subs, meta = Repository.get_submissions(
        course_code=course_code,
        status=status,
        search=search,
        assignment_id=assignment_id,
        limit=limit,
        offset=offset,
        faculty_user=user,
    )

    return PaginatedResponse[Submission](
        success=True,
        data=subs,
        meta=meta,
    )


@router.post("/submissions/{id}/override", response_model=StandardResponse[Dict[str, Any]])
async def override_submission_grade(
    id: str,
    override_req: FacultyOverrideRequest,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Allows an instructor to override an AI evaluation score with an audit rationale.
    Faculty identity is derived strictly from the authenticated session.
    Verifies course authorization before modifying the record.
    """
    sub = Repository.get_submission_by_id(id)
    if not sub:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Submission with ID '{id}' was not found.",
        )

    # Verify faculty owns/is authorized for the course
    if not Repository.is_course_authorized(sub.courseCode, user):
        logger.warning(f"Faculty {user.id} forbidden from overriding submission in course {sub.courseCode}")
        raise APIException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=f"You are not authorized to override grades for course '{sub.courseCode}'.",
        )

    original_score = sub.evaluation.score if sub.evaluation else 0.0

    # Derive faculty identity strictly from authenticated user; never trust client-provided overriddenBy
    authoritative_overridden_by = user.full_name or user.email

    override = FacultyOverride(
        isOverridden=True,
        originalScore=original_score,
        overriddenScore=override_req.overriddenScore,
        overriddenById=user.id,
        overriddenByName=authoritative_overridden_by,
        overriddenBy=authoritative_overridden_by,
        overrideReason=override_req.overrideReason,
        overriddenAt=datetime.now(timezone.utc).isoformat(),
        criterionAdjustments=override_req.criterionAdjustments,
    )

    updated_sub = Repository.override_submission_grade(
        submission_id=id,
        override=override,
        faculty_user_id=user.id,
    )

    return StandardResponse[Dict[str, Any]](
        success=True,
        data={
            "submissionId": id,
            "finalScore": override.overriddenScore,
            "isOverridden": True,
            "override": override.model_dump(by_alias=True),
        },
        message="Grade successfully overridden with faculty audit justification.",
    )


@router.delete("/submissions/{id}/override", response_model=StandardResponse[Dict[str, Any]])
async def remove_submission_override(
    id: str,
    reason: Optional[str] = Query("Faculty override revoked. Reverted to original AI evaluation."),
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Allows an instructor to revoke a grade override, reverting to pure AI-computed evaluation
    and recalculating concept mastery from authoritative evidence.
    """
    sub = Repository.get_submission_by_id(id)
    if not sub:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Submission with ID '{id}' was not found.",
        )

    if not Repository.is_course_authorized(sub.courseCode, user):
        logger.warning(f"Faculty {user.id} forbidden from removing override in course {sub.courseCode}")
        raise APIException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=f"You are not authorized to manage overrides for course '{sub.courseCode}'.",
        )

    authoritative_overridden_by = user.full_name or user.email

    updated_sub = Repository.remove_submission_override(
        submission_id=id,
        faculty_user_id=user.id,
        faculty_user_name=authoritative_overridden_by,
        reason=reason or "Faculty override revoked. Reverted to original AI evaluation.",
    )

    return StandardResponse[Dict[str, Any]](
        success=True,
        data={
            "submissionId": id,
            "finalScore": updated_sub.evaluation.score if updated_sub and updated_sub.evaluation else 0.0,
            "isOverridden": False,
        },
        message="Grade override removed successfully. Concept mastery recalculated from original AI evidence.",
    )



@router.get("/rubrics", response_model=StandardResponse[List[Rubric]])
async def list_rubrics(
    course_code: Optional[str] = Query(None),
    user: AuthUser = Depends(get_current_user),
):
    """
    Lists available assignment grading rubrics and criteria.
    """
    rubrics = Repository.get_rubrics(course_code=course_code)
    return StandardResponse[List[Rubric]](
        success=True,
        data=rubrics,
        message="Rubrics retrieved successfully",
    )


@router.post("/rubrics", status_code=http_status.HTTP_201_CREATED, response_model=StandardResponse[Rubric])
async def create_rubric(
    rubric_in: RubricCreate,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Creates a new grading rubric. Verifies course authorization.
    """
    if not Repository.is_course_authorized(rubric_in.courseCode, user):
        raise APIException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=f"You are not authorized to create rubrics for course '{rubric_in.courseCode}'.",
        )

    rubric_id = f"rubric-{uuid.uuid4().hex[:8]}"

    criteria = [
        RubricCriterion(
            id=f"{rubric_id}-crit-{i+1}",
            title=c.title,
            description=c.description,
            maxPoints=c.maxPoints,
            weightPercent=c.weightPercent,
        )
        for i, c in enumerate(rubric_in.criteria)
    ]

    total_pts = rubric_in.totalPoints or sum(c.maxPoints for c in criteria) or 100.0

    new_rubric = Rubric(
        id=rubric_id,
        courseCode=rubric_in.courseCode,
        assignmentTitle=rubric_in.assignmentTitle,
        description=rubric_in.description,
        totalPoints=total_pts,
        createdAt=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        criteria=criteria,
    )

    saved = Repository.create_rubric(new_rubric)

    return StandardResponse[Rubric](
        success=True,
        data=saved,
        message="Rubric created successfully.",
    )


@router.put("/rubrics/{id}", response_model=StandardResponse[Rubric])
async def update_rubric(
    id: str,
    rubric_update: RubricUpdate,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Updates rubric metadata or criteria distributions. Verifies course authorization.
    """
    rubric = Repository.get_rubric_by_id(id)
    if not rubric:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Rubric with ID '{id}' was not found.",
        )

    if not Repository.is_course_authorized(rubric.courseCode, user):
        raise APIException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=f"You are not authorized to update rubrics for course '{rubric.courseCode}'.",
        )

    updated = Repository.update_rubric(id, rubric_update)
    return StandardResponse[Rubric](
        success=True,
        data=updated,
        message="Rubric updated successfully.",
    )


@router.delete("/rubrics/{id}", response_model=StandardResponse[Dict[str, str]])
async def delete_rubric(
    id: str,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Deletes a rubric. Verifies course authorization.
    """
    rubric = Repository.get_rubric_by_id(id)
    if not rubric:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Rubric with ID '{id}' was not found.",
        )

    if not Repository.is_course_authorized(rubric.courseCode, user):
        raise APIException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=f"You are not authorized to delete rubrics for course '{rubric.courseCode}'.",
        )

    Repository.delete_rubric(id)
    return StandardResponse[Dict[str, str]](
        success=True,
        data={"deletedId": id},
        message=f"Rubric {id} successfully deleted.",
    )
