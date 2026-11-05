from datetime import datetime, timezone
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.curriculum import Concept
from app.models.rubric import Rubric

AssignmentStatus = Literal["draft", "published", "archived"]


class CriterionConceptMap(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    criterion_id: str = Field(..., alias="criterionId", description="Rubric criterion identifier")
    concept_id: str = Field(..., alias="conceptId", description="Target curriculum concept UUID")
    concept_name: Optional[str] = Field(default=None, alias="conceptName")


class AssignmentBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=256, description="Assignment title")
    description: str = Field(default="", max_length=10000, description="Pedagogical instructions and guidance")
    due_date: str = Field(..., alias="dueDate", description="ISO 8601 deadline timestamp")
    max_points: float = Field(default=100.0, ge=1.0, alias="maxPoints", description="Maximum achievable marks")
    status: AssignmentStatus = Field(default="draft", description="Visibility status")
    rubric_id: Optional[str] = Field(default=None, alias="rubricId", description="Referenced rubric identifier")

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Assignment title cannot be blank or whitespace-only.")
        return s


class AssignmentCreate(AssignmentBase):
    concept_ids: List[str] = Field(
        default_factory=list,
        alias="conceptIds",
        description="List of course concept UUIDs mapped to this assignment",
    )
    criterion_concepts: List[CriterionConceptMap] = Field(
        default_factory=list,
        alias="criterionConcepts",
        description="Explicit mappings from rubric criterion to course concept UUIDs",
    )


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=10000)
    due_date: Optional[str] = Field(default=None, alias="dueDate")
    max_points: Optional[float] = Field(default=None, ge=1.0, alias="maxPoints")
    status: Optional[AssignmentStatus] = None
    rubric_id: Optional[str] = Field(default=None, alias="rubricId")
    concept_ids: Optional[List[str]] = Field(default=None, alias="conceptIds")
    criterion_concepts: Optional[List[CriterionConceptMap]] = Field(default=None, alias="criterionConcepts")

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Assignment title cannot be blank.")
            return s
        return v


class Assignment(AssignmentBase):
    id: str = Field(..., description="UUID primary key")
    course_id: str = Field(..., alias="courseId", description="UUID foreign key to courses.id")
    created_by: Optional[str] = Field(default=None, alias="createdBy", description="UUID of author profile")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        alias="createdAt",
    )
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")
    concept_ids: List[str] = Field(default_factory=list, alias="conceptIds")
    concepts: List[Concept] = Field(default_factory=list, description="Populated concept details")
    criterion_concepts: List[CriterionConceptMap] = Field(default_factory=list, alias="criterionConcepts")
    submissions_count: int = Field(default=0, alias="submissionsCount")


class StudentAssignment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    course_id: str = Field(..., alias="courseId")
    course_code: str = Field(..., alias="courseCode")
    course_name: str = Field(..., alias="courseName")
    title: str
    description: str
    due_date: str = Field(..., alias="dueDate")
    max_points: float = Field(..., alias="maxPoints")
    status: AssignmentStatus
    rubric_id: Optional[str] = Field(None, alias="rubricId")
    rubric: Optional[Rubric] = None
    concepts: List[Concept] = Field(default_factory=list)
    criterion_concepts: List[CriterionConceptMap] = Field(default_factory=list, alias="criterionConcepts")
    submission_status: str = Field(default="unsubmitted", alias="submissionStatus")
    submission_id: Optional[str] = Field(None, alias="submissionId")
    submitted_at: Optional[str] = Field(None, alias="submittedAt")
    score: Optional[float] = None
