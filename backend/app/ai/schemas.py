from typing import List, Optional
from pydantic import BaseModel, Field


# --- Stage 1: Extraction & Layout Normalization Schemas ---

class CodeBlock(BaseModel):
    language: str
    code: str


class ExtractedSection(BaseModel):
    sectionTitle: str
    content: str
    codeBlocks: Optional[List[CodeBlock]] = Field(default_factory=list)


class FormatValidation(BaseModel):
    hasExecutableCode: bool
    hasTheoreticalAnalysis: bool
    pageCountEstimate: Optional[int] = 1


class StructuredDocument(BaseModel):
    documentTitle: Optional[str] = "Student Assignment Submission"
    authorDeclared: Optional[str] = None
    sections: List[ExtractedSection]
    formatValidation: FormatValidation


# --- Stage 2: Rubric Evaluation & Pedagogical Reasoning Schemas ---

class CriterionGradingOutput(BaseModel):
    criterionId: str
    title: str
    scoreAwarded: float
    maxPoints: float
    scoreRatio: float = Field(default=0.0)
    evidenceFromSubmission: str = Field(default="")
    reasoning: str = Field(default="")
    feedback: str
    strengths: Optional[str] = None
    improvements: Optional[str] = None


class GradingOutput(BaseModel):
    totalScore: float
    maxScore: float
    summaryFeedback: str
    strengths: List[str]
    improvements: List[str]
    criteriaEvaluations: List[CriterionGradingOutput]
