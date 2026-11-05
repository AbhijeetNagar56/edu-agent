from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any


class CriterionEvaluation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    criterionId: str = Field(..., alias="criterionId")
    title: str = Field(..., alias="title")
    scoreAwarded: float = Field(..., alias="scoreAwarded")
    maxPoints: float = Field(..., alias="maxPoints")
    scoreRatio: Optional[float] = Field(None, alias="scoreRatio", ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, alias="confidence", ge=0.0, le=1.0)
    evidence: Optional[str] = Field(None, alias="evidence")
    reasoning: Optional[str] = Field(None, alias="reasoning")
    feedback: str = Field(..., alias="feedback")
    strengths: Optional[str] = Field(None, alias="strengths")
    improvements: Optional[str] = Field(None, alias="improvements")


class ConceptFeedback(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    submissionId: Optional[str] = Field(default=None, alias="submissionId")
    studentId: Optional[str] = Field(default=None, alias="studentId")
    conceptId: str = Field(..., alias="conceptId")
    conceptName: Optional[str] = Field(default=None, alias="conceptName")
    criterionId: Optional[str] = Field(default=None, alias="criterionId")
    evaluationId: Optional[str] = Field(default=None, alias="evaluationId")
    scoreRatio: float = Field(default=0.0, alias="scoreRatio", ge=0.0, le=1.0)
    masteryPercentage: Optional[float] = Field(default=None, alias="masteryPercentage", ge=0.0, le=100.0)
    masteryContribution: Optional[float] = Field(default=None, alias="masteryContribution", ge=0.0, le=1.0)
    confidenceScore: float = Field(default=0.8, alias="confidenceScore", ge=0.0, le=1.0)
    confidence: Optional[float] = Field(default=0.8, alias="confidence", ge=0.0, le=1.0)
    evidenceCount: int = Field(default=1, alias="evidenceCount")
    feedback: Optional[str] = Field(default=None, alias="feedback")
    feedbackText: Optional[str] = Field(default=None, alias="feedbackText")
    evidence: str = Field(default="", alias="evidence")
    strengths: Optional[List[str]] = Field(default_factory=list, alias="strengths")
    improvements: Optional[List[str]] = Field(default_factory=list, alias="improvements")
    createdAt: Optional[str] = Field(default=None, alias="createdAt")


class EvaluationResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    score: float = Field(..., alias="score")
    maxScore: float = Field(..., alias="maxScore")
    percentage: float = Field(..., alias="percentage")
    criteriaScores: List[CriterionEvaluation] = Field(..., alias="criteriaScores")
    conceptFeedback: Optional[List[ConceptFeedback]] = Field(default_factory=list, alias="conceptFeedback")
    summaryFeedback: str = Field(..., alias="summaryFeedback")
    strengths: List[str] = Field(default_factory=list, alias="strengths")
    improvements: List[str] = Field(default_factory=list, alias="improvements")
    aiModelExtraction: str = Field(default="Gemini Flash-Lite", alias="aiModelExtraction")
    aiModelGrading: str = Field(default="Gemini Flash", alias="aiModelGrading")
    evaluatedAt: str = Field(..., alias="evaluatedAt")


class FacultyOverride(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    isOverridden: bool = Field(..., alias="isOverridden")
    originalScore: float = Field(..., alias="originalScore")
    overriddenScore: float = Field(..., alias="overriddenScore")
    overriddenBy: str = Field(..., alias="overriddenBy")
    overriddenById: Optional[str] = Field(None, alias="overriddenById")
    overriddenByName: Optional[str] = Field(None, alias="overriddenByName")
    overrideReason: str = Field(..., min_length=3, alias="overrideReason")
    overriddenAt: str = Field(..., alias="overriddenAt")
    criterionAdjustments: Optional[Dict[str, float]] = Field(None, alias="criterionAdjustments")


class FacultyOverrideRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    overriddenScore: float = Field(..., alias="overriddenScore")
    overrideReason: str = Field(..., min_length=3, alias="overrideReason")
    criterionAdjustments: Optional[Dict[str, float]] = Field(None, alias="criterionAdjustments")
