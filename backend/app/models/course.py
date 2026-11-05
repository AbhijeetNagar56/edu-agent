from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(..., min_length=2, max_length=32, description="Unique course code (e.g. CS101)")
    name: str = Field(..., min_length=2, max_length=256, description="Full human-readable course name")
    description: str = Field(default="", max_length=2000, description="Course synopsis or curriculum overview")

    @field_validator("code", "name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be blank or whitespace-only.")
        return s


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(default=None, min_length=2, max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Name cannot be blank.")
            return s
        return v


class Course(CourseBase):
    id: str = Field(..., description="UUID primary key")
    faculty_id: str = Field(..., alias="facultyId", description="UUID foreign key to profiles.id")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        alias="createdAt"
    )
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")
    concepts_count: int = Field(default=0, alias="conceptsCount")
    assignments_count: int = Field(default=0, alias="assignmentsCount")
