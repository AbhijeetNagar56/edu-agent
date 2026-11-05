from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.auth import AuthUser, get_current_user
from app.core.errors import APIException
from app.core.logging import logger
from app.models.assignment import (
    Assignment,
    AssignmentCreate,
    AssignmentUpdate,
)
from app.models.common import StandardResponse
from app.services.repository import Repository

router = APIRouter(prefix="/api/v1/faculty", tags=["Faculty Assignments"])


@router.get(
    "/courses/{course_id}/assignments",
    response_model=StandardResponse[List[Assignment]],
    status_code=status.HTTP_200_OK,
)
async def list_course_assignments_endpoint(
    course_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    user: AuthUser = Depends(get_current_user),
):
    """
    Lists assignments for a course owned by the authenticated faculty member.
    Includes draft, published, and archived assignments.
    Cross-faculty access is strictly forbidden with HTTP 403.
    """
    if user.role not in ["faculty", "admin"]:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ROLE",
            message="Only faculty members can access course assignments.",
        )

    if not Repository.is_course_owner_by_id(course_id, user):
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_COURSE_ACCESS",
            message="You do not own this course and cannot inspect its assignments.",
        )

    assignments = Repository.get_assignments_for_course(
        course_id=course_id,
        status_filter=status_filter,
    )
    return StandardResponse[List[Assignment]](
        success=True,
        data=assignments,
        message="Course assignments retrieved successfully.",
    )


@router.post(
    "/courses/{course_id}/assignments",
    response_model=StandardResponse[Assignment],
    status_code=status.HTTP_201_CREATED,
)
async def create_course_assignment_endpoint(
    course_id: str,
    assignment_in: AssignmentCreate,
    user: AuthUser = Depends(get_current_user),
):
    """
    Creates an assignment with targeted course concepts and rubric criterion mappings.
    Faculty identity is derived authoritatively from user.id.
    Strictly verifies course ownership, course concept isolation, and criterion validity.
    """
    if user.role not in ["faculty", "admin"]:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ROLE",
            message="Only faculty members can create assignments.",
        )

    if not Repository.is_course_owner_by_id(course_id, user):
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_COURSE_ACCESS",
            message="You do not own this course and cannot create assignments for it.",
        )

    created = Repository.create_assignment(
        course_id=course_id,
        assignment_in=assignment_in,
        faculty_id=user.id,
    )
    logger.info(
        f"Faculty {user.id} created assignment '{created.id}' ({created.title}) for course {course_id}"
    )
    return StandardResponse[Assignment](
        success=True,
        data=created,
        message="Assignment created successfully.",
    )


@router.get(
    "/assignments/{assignment_id}",
    response_model=StandardResponse[Assignment],
    status_code=status.HTTP_200_OK,
)
async def get_assignment_detail_endpoint(
    assignment_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Retrieves complete assignment details including rubric and mapped concepts.
    Verifies that the authenticated faculty owns the assignment's course.
    """
    if user.role not in ["faculty", "admin"]:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ROLE",
            message="Only faculty members can view assignment management details.",
        )

    assignment = Repository.get_assignment_by_id(assignment_id)
    if not assignment:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ASSIGNMENT_NOT_FOUND",
            message=f"Assignment '{assignment_id}' was not found.",
        )

    if not Repository.is_course_owner_by_id(assignment.course_id, user):
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_COURSE_ACCESS",
            message="You do not own the course this assignment belongs to.",
        )

    return StandardResponse[Assignment](
        success=True,
        data=assignment,
        message="Assignment retrieved successfully.",
    )


@router.put(
    "/assignments/{assignment_id}",
    response_model=StandardResponse[Assignment],
    status_code=status.HTTP_200_OK,
)
async def update_assignment_endpoint(
    assignment_id: str,
    update_in: AssignmentUpdate,
    user: AuthUser = Depends(get_current_user),
):
    """
    Updates assignment title, description, due date, max marks, status (publish/unpublish),
    or associated concepts and criterion mappings.
    """
    if user.role not in ["faculty", "admin"]:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ROLE",
            message="Only faculty members can update assignments.",
        )

    existing = Repository.get_assignment_by_id(assignment_id)
    if not existing:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ASSIGNMENT_NOT_FOUND",
            message=f"Assignment '{assignment_id}' was not found.",
        )

    if not Repository.is_course_owner_by_id(existing.course_id, user):
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_COURSE_ACCESS",
            message="You do not own the course this assignment belongs to.",
        )

    updated = Repository.update_assignment(assignment_id, update_in)
    logger.info(f"Faculty {user.id} updated assignment '{assignment_id}'")
    return StandardResponse[Assignment](
        success=True,
        data=updated,
        message="Assignment updated successfully.",
    )


@router.delete(
    "/assignments/{assignment_id}",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_200_OK,
)
async def delete_assignment_endpoint(
    assignment_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Deletes an assignment and associated concept mappings.
    """
    if user.role not in ["faculty", "admin"]:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ROLE",
            message="Only faculty members can delete assignments.",
        )

    existing = Repository.get_assignment_by_id(assignment_id)
    if not existing:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ASSIGNMENT_NOT_FOUND",
            message=f"Assignment '{assignment_id}' was not found.",
        )

    if not Repository.is_course_owner_by_id(existing.course_id, user):
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_COURSE_ACCESS",
            message="You do not own the course this assignment belongs to.",
        )

    Repository.delete_assignment(assignment_id)
    logger.info(f"Faculty {user.id} deleted assignment '{assignment_id}'")
    return StandardResponse[dict](
        success=True,
        data={"id": assignment_id, "deleted": True},
        message="Assignment deleted successfully.",
    )
