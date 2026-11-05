from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class StudentConceptMastery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    studentId: str = Field(..., alias="student_id")
    conceptId: str = Field(..., alias="concept_id")
    submissionId: Optional[str] = Field(None, alias="submission_id")
    masteryScore: float = Field(..., alias="mastery_score", ge=0.0, le=1.0)
    confidenceScore: float = Field(..., alias="confidence_score", ge=0.0, le=1.0)
    source: Literal["ai_evaluation", "faculty_override", "diagnostic_quiz", "manual_adjustment"] = Field(
        "ai_evaluation", alias="source"
    )
    evidenceCount: int = Field(1, alias="evidence_count", ge=1)
    lastEvaluatedAt: str = Field(..., alias="last_evaluated_at")
    createdAt: Optional[str] = Field(None, alias="created_at")

    @computed_field(alias="mastery_percentage")
    def mastery_percentage(self) -> float:
        """Computed percentage (0-100) kept in sync with authoritative 0.0-1.0 score."""
        return round(self.masteryScore * 100.0, 2)
