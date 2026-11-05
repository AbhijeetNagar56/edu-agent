from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.core.auth import AuthUser, get_current_user
from app.core.errors import APIException
from app.models.assignment import StudentAssignment
from app.models.curriculum import StudentCurriculumGraph
from app.models.common import StandardResponse
from app.services.repository import Repository

router = APIRouter(prefix="/api/v1/students", tags=["Student Operations"])


@router.get("/{student_id}/mastery", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_student_mastery_endpoint(
    student_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Retrieves student concept mastery records.
    Strictly forbids students from viewing another student's mastery records.
    """
    mastery = Repository.get_student_mastery(student_id=student_id, calling_user=user)
    return StandardResponse[List[Dict[str, Any]]](
        success=True,
        data=mastery,
        message="Mastery records retrieved successfully",
    )


@router.get("/courses/{course_id}/curriculum", response_model=StandardResponse[StudentCurriculumGraph])
async def get_student_course_curriculum_endpoint(
    course_id: str,
    student_id: Optional[str] = Query(None),
    user: AuthUser = Depends(get_current_user),
):
    """
    Read-only student learning graph API.
    Joins canonical course concepts and prerequisite edges with the student's mastery records.
    Missing mastery indicates UNASSESSED (masteryScore = None), NOT zero mastery.
    Students can only view their own graph for enrolled courses.
    Faculty can view enrolled students for courses they own.
    """
    # Verify course exists
    course = Repository.get_course_by_id(course_id)
    if not course:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="COURSE_NOT_FOUND",
            message=f"Course '{course_id}' was not found.",
        )

    if user.role == "student":
        # Check course enrollment for student
        if not Repository.is_student_enrolled(course.id, user.id):
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="NOT_ENROLLED",
                message=f"You are not enrolled in course '{course.code}'.",
            )
        target_student_id = user.id
    elif user.role in ["faculty", "admin"]:
        # Verify faculty course ownership
        if user.role != "admin" and not Repository.is_course_owner_by_id(course.id, user):
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message=f"You are not authorized to view student curriculum for course '{course.code}'.",
            )
        if student_id:
            if not Repository.is_student_enrolled(course.id, student_id):
                raise APIException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="STUDENT_NOT_ENROLLED",
                    message=f"Student '{student_id}' is not enrolled in course '{course.code}'.",
                )
            target_student_id = student_id
        else:
            enrolled = Repository.get_course_enrolled_students(course.id)
            target_student_id = enrolled[0]["student_id"] if enrolled else user.id
    else:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Unauthorized role.",
        )

    learning_graph = Repository.get_student_course_curriculum(course_id=course.id, student_id=target_student_id)
    return StandardResponse[StudentCurriculumGraph](
        success=True,
        data=learning_graph,
        message="Student course curriculum retrieved successfully.",
    )


@router.get("/assignments", response_model=StandardResponse[List[StudentAssignment]])
async def list_student_assignments_endpoint(
    course_id: Optional[str] = Query(None, alias="course_id"),
    user: AuthUser = Depends(get_current_user),
):
    """
    Lists all published assignments for courses the authenticated student is enrolled in.
    Draft assignments are strictly hidden.
    """
    assignments = Repository.get_student_assignments(
        student_id=user.id,
        course_id=course_id,
    )
    return StandardResponse[List[StudentAssignment]](
        success=True,
        data=assignments,
        message="Student assignments retrieved successfully.",
    )


@router.get("/assignments/{assignment_id}", response_model=StandardResponse[StudentAssignment])
async def get_student_assignment_detail_endpoint(
    assignment_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """
    Retrieves full details of a published assignment for an enrolled student.
    Draft assignments return 404 (hidden from students).
    Non-enrolled courses return 403 Forbidden.
    """
    assign = Repository.get_assignment_by_id(assignment_id)
    if not assign or assign.status != "published":
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="ASSIGNMENT_NOT_FOUND",
            message=f"Assignment '{assignment_id}' was not found.",
        )

    # Verify enrollment
    if user.role == "student" and not Repository.is_student_enrolled(assign.course_id, user.id):
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NOT_ENROLLED",
            message="You are not enrolled in the course for this assignment.",
        )

    # Get course and rubric
    course = Repository.get_course_by_id(assign.course_id)
    rubric = Repository.get_rubric_by_id(assign.rubric_id) if assign.rubric_id else None

    # Get student's submission status if any
    subs, _ = Repository.get_submissions(student_id=user.id, limit=100)
    student_sub = next((s for s in subs if s.assignmentId == assign.id), None)

    sub_status = "unsubmitted"
    sub_id = None
    submitted_at = None
    score = None
    if student_sub:
        sub_id = student_sub.id
        submitted_at = student_sub.submittedAt
        sub_status = student_sub.status.value if hasattr(student_sub.status, "value") else str(student_sub.status)
        if student_sub.evaluation:
            score = student_sub.evaluation.score

    student_assign = StudentAssignment(
        id=assign.id,
        courseId=assign.course_id,
        courseCode=course.code if course else "",
        courseName=course.name if course else "",
        title=assign.title,
        description=assign.description,
        dueDate=assign.due_date,
        maxPoints=assign.max_points,
        status=assign.status,
        rubricId=assign.rubric_id,
        rubric=rubric,
        concepts=assign.concepts,
        criterionConcepts=assign.criterion_concepts,
        submissionStatus=sub_status,
        submissionId=sub_id,
        submittedAt=submitted_at,
        score=score,
    )

    return StandardResponse[StudentAssignment](
        success=True,
        data=student_assign,
        message="Assignment retrieved successfully.",
    )
