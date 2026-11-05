from app.models.analytics import (
    CourseLearningAnalytics,
    ConceptMasteryOverrideRequest,
    ConceptMasteryOverrideResponse,
)
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status as http_status

from app.core.auth import AuthUser, require_role
from app.core.errors import APIException
from app.core.logging import logger
from app.models.common import StandardResponse
from app.models.course import Course, CourseCreate
from app.models.curriculum import (
    Concept,
    ConceptCreate,
    ConceptUpdate,
    ConceptEdge,
    ConceptEdgeCreate,
    CurriculumGraph,
    CurriculumSaveRequest,
    EnrolledStudentSummary,
)
from app.services.repository import Repository

router = APIRouter(prefix="/api/v1/faculty/courses", tags=["Faculty Course & Curriculum"])


def verify_course_owner(course_id: str, user: AuthUser) -> None:
    """Helper to verify faculty ownership of a course or raise 403 Forbidden."""
    if not Repository.is_course_owner_by_id(course_id, user):
        logger.warning(f"Faculty {user.id} unauthorized for course {course_id}")
        raise APIException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=f"You are not authorized to view or modify curriculum for course '{course_id}'.",
        )


# ============================================================================
# COURSE MANAGEMENT
# ============================================================================
@router.get("", response_model=StandardResponse[List[Course]])
async def list_faculty_courses(
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Lists courses owned by the authenticated faculty member.
    Admins see all registered courses.
    """
    is_admin = user.role == "admin"
    courses = Repository.get_courses_for_faculty(faculty_id=user.id, is_admin=is_admin)
    return StandardResponse[List[Course]](
        success=True,
        data=courses,
        message="Faculty courses retrieved successfully.",
    )


@router.post("", status_code=http_status.HTTP_201_CREATED, response_model=StandardResponse[Course])
async def create_course(
    course_in: CourseCreate,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Creates a new course with a code, title, and description.
    Faculty ownership is strictly bound to the authenticated user's ID.
    """
    created = Repository.create_course(course_in=course_in, faculty_id=user.id)
    return StandardResponse[Course](
        success=True,
        data=created,
        message=f"Course '{created.code}' created successfully.",
    )


@router.get("/{course_id}", response_model=StandardResponse[Course])
async def get_course_details(
    course_id: str,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Retrieves metadata for a specific course. Verifies faculty ownership.
    """
    verify_course_owner(course_id, user)
    course = Repository.get_course_by_id(course_id)
    if not course:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="COURSE_NOT_FOUND",
            message=f"Course '{course_id}' was not found.",
        )
    return StandardResponse[Course](
        success=True,
        data=course,
        message="Course details retrieved successfully.",
    )


# ============================================================================
# CONSOLIDATED CURRICULUM GRAPH
# ============================================================================
@router.get("/{course_id}/curriculum", response_model=StandardResponse[CurriculumGraph])
async def get_curriculum(
    course_id: str,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Returns the complete canonical curriculum graph for the course:
    course metadata, concept nodes with canvas coordinates, and prerequisite edges.
    """
    verify_course_owner(course_id, user)
    graph = Repository.get_curriculum_graph(course_id)
    if not graph:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="COURSE_NOT_FOUND",
            message=f"Course '{course_id}' was not found.",
        )
    return StandardResponse[CurriculumGraph](
        success=True,
        data=graph,
        message="Curriculum graph retrieved successfully.",
    )


@router.put("/{course_id}/curriculum", response_model=StandardResponse[CurriculumGraph])
async def save_curriculum_layout(
    course_id: str,
    save_req: CurriculumSaveRequest,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Persists updated node coordinates and authoritative prerequisite edges for the course.
    Validates DAG integrity, rejects circular dependencies, and avoids duplicates.
    """
    verify_course_owner(course_id, user)
    updated_graph = Repository.save_curriculum_layout(course_id, save_req)
    return StandardResponse[CurriculumGraph](
        success=True,
        data=updated_graph,
        message="Curriculum layout saved successfully.",
    )


# ============================================================================
# GRANULAR CONCEPT CRUD
# ============================================================================
@router.post("/{course_id}/concepts", status_code=http_status.HTTP_201_CREATED, response_model=StandardResponse[Concept])
async def create_concept(
    course_id: str,
    concept_in: ConceptCreate,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Adds a new concept node to the course's canonical curriculum.
    """
    verify_course_owner(course_id, user)
    concept = Repository.create_concept(course_id, concept_in)
    return StandardResponse[Concept](
        success=True,
        data=concept,
        message=f"Concept '{concept.name}' added to course.",
    )


@router.put("/{course_id}/concepts/{concept_id}", response_model=StandardResponse[Concept])
async def update_concept(
    course_id: str,
    concept_id: str,
    update_in: ConceptUpdate,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Updates concept attributes (name, description, category, difficulty, or canvas position).
    """
    verify_course_owner(course_id, user)
    updated = Repository.update_concept(course_id, concept_id, update_in)
    if not updated:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="CONCEPT_NOT_FOUND",
            message=f"Concept '{concept_id}' was not found in course '{course_id}'.",
        )
    return StandardResponse[Concept](
        success=True,
        data=updated,
        message="Concept updated successfully.",
    )


@router.delete("/{course_id}/concepts/{concept_id}", response_model=StandardResponse[Dict[str, str]])
async def delete_concept(
    course_id: str,
    concept_id: str,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Deletes a concept from the canonical curriculum.
    Cascades and cleans up any incident prerequisite edges.
    """
    verify_course_owner(course_id, user)
    deleted = Repository.delete_concept(course_id, concept_id)
    if not deleted:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="CONCEPT_NOT_FOUND",
            message=f"Concept '{concept_id}' was not found in course '{course_id}'.",
        )
    return StandardResponse[Dict[str, str]](
        success=True,
        data={"deletedConceptId": concept_id},
        message=f"Concept '{concept_id}' and all dependent edges successfully removed.",
    )


# ============================================================================
# GRANULAR PREREQUISITE EDGE CRUD
# ============================================================================
@router.post("/{course_id}/edges", status_code=http_status.HTTP_201_CREATED, response_model=StandardResponse[ConceptEdge])
async def create_concept_edge(
    course_id: str,
    edge_in: ConceptEdgeCreate,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Creates a directed prerequisite edge: Prerequisite Concept -> Dependent Concept.
    Validates DAG integrity, rejects self-loops, cross-course links, and circular dependencies.
    """
    verify_course_owner(course_id, user)
    edge = Repository.create_concept_edge(course_id, edge_in)
    return StandardResponse[ConceptEdge](
        success=True,
        data=edge,
        message="Prerequisite edge created successfully.",
    )


@router.delete("/{course_id}/edges/{edge_id}", response_model=StandardResponse[Dict[str, str]])
async def delete_concept_edge(
    course_id: str,
    edge_id: str,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Deletes a prerequisite edge from the course curriculum.
    """
    verify_course_owner(course_id, user)
    deleted = Repository.delete_concept_edge(course_id, edge_id)
    if not deleted:
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="EDGE_NOT_FOUND",
            message=f"Prerequisite edge '{edge_id}' was not found in course '{course_id}'.",
        )
    return StandardResponse[Dict[str, str]](
        success=True,
        data={"deletedEdgeId": edge_id},
        message=f"Prerequisite edge '{edge_id}' successfully removed.",
    )


@router.get("/{course_id}/students", response_model=StandardResponse[List[EnrolledStudentSummary]])
async def list_course_enrolled_students(
    course_id: str,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Lists enrolled students for a course owned by the authenticated faculty member.
    """
    if user.role != "admin":
        verify_course_owner(course_id, user)

    students = Repository.get_course_enrolled_students(course_id)
    return StandardResponse[List[EnrolledStudentSummary]](
        success=True,
        data=students,
        message="Enrolled students retrieved successfully.",
    )


# ============================================================================
# COURSE LEARNING ANALYTICS
# ============================================================================
@router.get("/{course_id}/analytics", response_model=StandardResponse[CourseLearningAnalytics])
async def get_course_analytics(
    course_id: str,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Retrieves course-level, student-level, concept-level, and assignment-level
    learning analytics. Excludes unassessed concepts from student mastery averages.
    Enforces course ownership.
    """
    verify_course_owner(course_id, user)
    analytics = Repository.get_course_learning_analytics(course_id=course_id, faculty_user=user)
    return StandardResponse[CourseLearningAnalytics](
        success=True,
        data=analytics,
        message="Course learning analytics retrieved successfully.",
    )


# ============================================================================
# DIRECT CONCEPT MASTERY OVERRIDE
# ============================================================================
@router.post(
    "/{course_id}/students/{student_id}/concepts/{concept_id}/override",
    response_model=StandardResponse[ConceptMasteryOverrideResponse],
)
async def override_student_concept_mastery(
    course_id: str,
    student_id: str,
    concept_id: str,
    override_req: ConceptMasteryOverrideRequest,
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Directly overrides a student's concept mastery score with mandatory audit justification.
    """
    verify_course_owner(course_id, user)

    # Verify student is enrolled in the course
    enrolled = Repository.get_course_enrolled_students(course_id)
    if not any(str(st["student_id"]) == str(student_id) for st in enrolled):
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="STUDENT_NOT_ENROLLED",
            message=f"Student '{student_id}' is not enrolled in course '{course_id}'.",
        )

    # Verify concept belongs to the course
    course_concepts = Repository.get_concepts_for_course(course_id)
    if not any(str(c.id) == str(concept_id) for c in course_concepts):
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="CONCEPT_NOT_FOUND",
            message=f"Concept '{concept_id}' does not belong to course '{course_id}'.",
        )

    authoritative_name = user.full_name or user.email
    result = Repository.override_concept_mastery(
        course_id=course_id,
        student_id=student_id,
        concept_id=concept_id,
        mastery_score=override_req.masteryScore,
        confidence_score=override_req.confidenceScore or 0.9,
        override_reason=override_req.overrideReason,
        faculty_user_id=user.id,
        faculty_user_name=authoritative_name,
    )

    return StandardResponse[ConceptMasteryOverrideResponse](
        success=True,
        data=ConceptMasteryOverrideResponse(**result),
        message="Concept mastery overridden successfully with faculty audit justification.",
    )


@router.delete(
    "/{course_id}/students/{student_id}/concepts/{concept_id}/override",
    response_model=StandardResponse[Dict[str, Any]],
)
async def remove_student_concept_mastery_override(
    course_id: str,
    student_id: str,
    concept_id: str,
    reason: Optional[str] = Query("Faculty concept mastery override revoked."),
    user: AuthUser = Depends(require_role(["faculty", "admin"])),
):
    """
    Removes a direct concept mastery override, restoring pure AI evidence calculation.
    """
    verify_course_owner(course_id, user)

    enrolled = Repository.get_course_enrolled_students(course_id)
    if not any(str(st["student_id"]) == str(student_id) for st in enrolled):
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="STUDENT_NOT_ENROLLED",
            message=f"Student '{student_id}' is not enrolled in course '{course_id}'.",
        )

    course_concepts = Repository.get_concepts_for_course(course_id)
    if not any(str(c.id) == str(concept_id) for c in course_concepts):
        raise APIException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            code="CONCEPT_NOT_FOUND",
            message=f"Concept '{concept_id}' does not belong to course '{course_id}'.",
        )

    authoritative_name = user.full_name or user.email
    recomputed = Repository.remove_concept_mastery_override(
        course_id=course_id,
        student_id=student_id,
        concept_id=concept_id,
        override_reason=reason or "Faculty concept mastery override revoked.",
        faculty_user_id=user.id,
        faculty_user_name=authoritative_name,
    )

    return StandardResponse[Dict[str, Any]](
        success=True,
        data=recomputed or {},
        message="Concept mastery override revoked and recalculated from pure AI evidence.",
    )
