from datetime import datetime, timezone
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ConceptDifficulty = Literal["beginner", "intermediate", "advanced"]


class ConceptBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=256, description="Concept display name")
    description: str = Field(default="", max_length=2000, description="Pedagogical description")
    category: str = Field(default="", max_length=128, description="Topic or category classification")
    difficulty: ConceptDifficulty = Field(default="intermediate", description="Target mastery difficulty")
    pos_x: float = Field(default=0.0, alias="posX", description="X coordinate on curriculum canvas")
    pos_y: float = Field(default=0.0, alias="posY", description="Y coordinate on curriculum canvas")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Concept name cannot be blank.")
        return s


class ConceptCreate(ConceptBase):
    pass


class ConceptUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    description: Optional[str] = Field(default=None, max_length=2000)
    category: Optional[str] = Field(default=None, max_length=128)
    difficulty: Optional[ConceptDifficulty] = None
    pos_x: Optional[float] = Field(default=None, alias="posX")
    pos_y: Optional[float] = Field(default=None, alias="posY")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Concept name cannot be blank.")
            return s
        return v


class Concept(ConceptBase):
    id: str = Field(..., description="UUID primary key")
    course_id: str = Field(..., alias="courseId", description="UUID foreign key to courses.id")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        alias="createdAt"
    )


class ConceptEdgeBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_concept: str = Field(..., alias="fromConcept", description="Prerequisite concept UUID")
    to_concept: str = Field(..., alias="toConcept", description="Dependent concept UUID")

    @field_validator("to_concept")
    @classmethod
    def check_self_loop(cls, v: str, info) -> str:
        from_val = info.data.get("from_concept")
        if from_val and from_val == v:
            raise ValueError("Prerequisite edge cannot connect a concept to itself.")
        return v


class ConceptEdgeCreate(ConceptEdgeBase):
    pass


class ConceptEdge(ConceptEdgeBase):
    id: str = Field(..., description="UUID primary key")
    course_id: str = Field(..., alias="courseId", description="UUID foreign key to courses.id")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        alias="createdAt"
    )


class CurriculumPositionUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Concept UUID")
    pos_x: float = Field(..., alias="posX")
    pos_y: float = Field(..., alias="posY")


class CurriculumSaveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    positions: Optional[List[CurriculumPositionUpdate]] = Field(
        default=None,
        description="Updated concept coordinates"
    )
    edges: Optional[List[ConceptEdgeBase]] = Field(
        default=None,
        description="Authoritative list of prerequisite edges for the course"
    )


class CurriculumGraph(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    course_id: str = Field(..., alias="courseId")
    course_code: str = Field(..., alias="courseCode")
    course_name: str = Field(..., alias="courseName")
    course_description: str = Field(default="", alias="courseDescription")
    concepts: List[Concept] = Field(default_factory=list)
    edges: List[ConceptEdge] = Field(default_factory=list)


# =============================================================================
# DAY 5: INDIVIDUALIZED STUDENT KNOWLEDGE GRAPH MODELS
# =============================================================================

class EvidenceHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    submissionId: Optional[str] = None
    submission_id: Optional[str] = None
    assignmentId: Optional[str] = None
    assignment_id: Optional[str] = None
    assignmentTitle: Optional[str] = None
    assignment_title: Optional[str] = None
    criterionId: Optional[str] = None
    criterion_id: Optional[str] = None
    scoreRatio: float = 0.0
    score_ratio: float = 0.0
    confidence: float = 0.8
    feedbackText: str = ""
    feedback_text: str = ""
    evidence: str = ""
    evaluatedAt: Optional[str] = None
    evaluated_at: Optional[str] = None
    source: str = "ai"
    facultyOverride: Optional[Dict[str, Any]] = None
    faculty_override: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            s_id = data.get("submissionId") or data.get("submission_id")
            data["submissionId"] = s_id
            data["submission_id"] = s_id
            a_id = data.get("assignmentId") or data.get("assignment_id")
            data["assignmentId"] = a_id
            data["assignment_id"] = a_id
            a_title = data.get("assignmentTitle") or data.get("assignment_title")
            data["assignmentTitle"] = a_title
            data["assignment_title"] = a_title
            c_id = data.get("criterionId") or data.get("criterion_id")
            data["criterionId"] = c_id
            data["criterion_id"] = c_id
            sr = data.get("scoreRatio", data.get("score_ratio", 0.0))
            data["scoreRatio"] = sr
            data["score_ratio"] = sr
            ft = data.get("feedbackText", data.get("feedback_text", ""))
            data["feedbackText"] = ft
            data["feedback_text"] = ft
            ev = data.get("evaluatedAt", data.get("evaluated_at"))
            data["evaluatedAt"] = ev
            data["evaluated_at"] = ev
            fo = data.get("facultyOverride", data.get("faculty_override"))
            data["facultyOverride"] = fo
            data["faculty_override"] = fo
        return data


class ConceptFeedbackSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recentFeedback: Optional[str] = None
    recent_feedback: Optional[str] = None
    evidenceExcerpts: List[str] = Field(default_factory=list)
    evidence_excerpts: List[str] = Field(default_factory=list)
    relatedCriterionIds: List[str] = Field(default_factory=list)
    related_criterion_ids: List[str] = Field(default_factory=list)
    associatedAssignmentIds: List[str] = Field(default_factory=list)
    associated_assignment_ids: List[str] = Field(default_factory=list)
    associatedAssignments: List[Dict[str, Any]] = Field(default_factory=list)
    associated_assignments: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[EvidenceHistoryItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            rf = data.get("recentFeedback") or data.get("recent_feedback")
            data["recentFeedback"] = rf
            data["recent_feedback"] = rf
            ee = data.get("evidenceExcerpts") or data.get("evidence_excerpts") or []
            data["evidenceExcerpts"] = ee
            data["evidence_excerpts"] = ee
            rc = data.get("relatedCriterionIds") or data.get("related_criterion_ids") or []
            data["relatedCriterionIds"] = rc
            data["related_criterion_ids"] = rc
            aa_ids = data.get("associatedAssignmentIds") or data.get("associated_assignment_ids") or []
            data["associatedAssignmentIds"] = aa_ids
            data["associated_assignment_ids"] = aa_ids
            aa = data.get("associatedAssignments") or data.get("associated_assignments") or []
            data["associatedAssignments"] = aa
            data["associated_assignments"] = aa
        return data


class StudentCurriculumConcept(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    conceptId: Optional[str] = None
    concept_id: Optional[str] = None
    name: str
    description: str = ""
    category: str = ""
    difficulty: ConceptDifficulty = "intermediate"
    posX: float = 0.0
    posY: float = 0.0
    pos_x: float = 0.0
    pos_y: float = 0.0
    positionX: float = 0.0
    positionY: float = 0.0
    position_x: float = 0.0
    position_y: float = 0.0

    # Student-specific mastery & confidence (None indicates UNASSESSED)
    masteryScore: Optional[float] = None
    mastery_score: Optional[float] = None
    masteryPercentage: Optional[float] = None
    mastery_percentage: Optional[float] = None
    confidenceScore: Optional[float] = None
    confidence_score: Optional[float] = None
    confidence: Optional[float] = None
    evidenceCount: int = 0
    evidence_count: int = 0
    masterySource: str = "unassessed"
    mastery_source: str = "unassessed"
    lastEvaluatedAt: Optional[str] = None
    last_evaluated_at: Optional[str] = None
    status: Literal["unassessed", "low_mastery", "developing", "strong", "high"] = "unassessed"

    # Evidence details
    feedback: ConceptFeedbackSummary = Field(default_factory=ConceptFeedbackSummary)

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            cid = data.get("id") or data.get("conceptId") or data.get("concept_id")
            data["id"] = cid
            data["conceptId"] = cid
            data["concept_id"] = cid
            px = data.get("posX", data.get("pos_x", data.get("positionX", data.get("position_x", 0.0))))
            py = data.get("posY", data.get("pos_y", data.get("positionY", data.get("position_y", 0.0))))
            data["posX"] = px
            data["pos_x"] = px
            data["positionX"] = px
            data["position_x"] = px
            data["posY"] = py
            data["pos_y"] = py
            data["positionY"] = py
            data["position_y"] = py
            ms = data.get("masteryScore", data.get("mastery_score"))
            data["masteryScore"] = ms
            data["mastery_score"] = ms
            mp = data.get("masteryPercentage", data.get("mastery_percentage"))
            data["masteryPercentage"] = mp
            data["mastery_percentage"] = mp
            cs = data.get("confidenceScore", data.get("confidence_score", data.get("confidence")))
            data["confidenceScore"] = cs
            data["confidence_score"] = cs
            data["confidence"] = cs
            ec = data.get("evidenceCount", data.get("evidence_count", 0))
            data["evidenceCount"] = ec
            data["evidence_count"] = ec
            src = data.get("masterySource", data.get("mastery_source", "unassessed"))
            data["masterySource"] = src
            data["mastery_source"] = src
            le = data.get("lastEvaluatedAt", data.get("last_evaluated_at"))
            data["lastEvaluatedAt"] = le
            data["last_evaluated_at"] = le
        return data


class StudentPrerequisiteEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    fromConcept: Optional[str] = None
    from_concept: Optional[str] = None
    toConcept: Optional[str] = None
    to_concept: Optional[str] = None
    sourceConceptId: Optional[str] = None
    source_concept_id: Optional[str] = None
    targetConceptId: Optional[str] = None
    target_concept_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            src = data.get("fromConcept") or data.get("from_concept") or data.get("sourceConceptId") or data.get("source_concept_id")
            tgt = data.get("toConcept") or data.get("to_concept") or data.get("targetConceptId") or data.get("target_concept_id")
            data["fromConcept"] = src
            data["from_concept"] = src
            data["sourceConceptId"] = src
            data["source_concept_id"] = src
            data["toConcept"] = tgt
            data["to_concept"] = tgt
            data["targetConceptId"] = tgt
            data["target_concept_id"] = tgt
        return data


class StudentCurriculumGraph(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    courseId: Optional[str] = None
    course_id: Optional[str] = None
    courseCode: Optional[str] = None
    course_code: Optional[str] = None
    courseName: Optional[str] = None
    course_name: Optional[str] = None
    courseDescription: str = ""
    course_description: str = ""
    studentId: Optional[str] = None
    student_id: Optional[str] = None
    studentName: str = "Student"
    student_name: str = "Student"
    studentEmail: str = ""
    student_email: str = ""
    concepts: List[StudentCurriculumConcept] = Field(default_factory=list)
    edges: List[StudentPrerequisiteEdge] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            cid = data.get("courseId") or data.get("course_id")
            data["courseId"] = cid
            data["course_id"] = cid
            cc = data.get("courseCode") or data.get("course_code")
            data["courseCode"] = cc
            data["course_code"] = cc
            cn = data.get("courseName") or data.get("course_name")
            data["courseName"] = cn
            data["course_name"] = cn
            cd = data.get("courseDescription", data.get("course_description", ""))
            data["courseDescription"] = cd
            data["course_description"] = cd
            sid = data.get("studentId") or data.get("student_id")
            data["studentId"] = sid
            data["student_id"] = sid
            sname = data.get("studentName", data.get("student_name", "Student"))
            data["studentName"] = sname
            data["student_name"] = sname
            se = data.get("studentEmail", data.get("student_email", ""))
            data["studentEmail"] = se
            data["student_email"] = se
        return data


class EnrolledStudentSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    studentId: Optional[str] = None
    student_id: Optional[str] = None
    studentName: Optional[str] = None
    student_name: Optional[str] = None
    studentEmail: Optional[str] = None
    student_email: Optional[str] = None
    enrolledAt: Optional[str] = None
    enrolled_at: Optional[str] = None
    totalAssessedConcepts: int = 0
    total_assessed_concepts: int = 0
    totalConcepts: int = 0
    total_concepts: int = 0
    averageMastery: float = 0.0
    average_mastery: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sid = data.get("studentId") or data.get("student_id")
            data["studentId"] = sid
            data["student_id"] = sid
            sn = data.get("studentName") or data.get("student_name")
            data["studentName"] = sn
            data["student_name"] = sn
            se = data.get("studentEmail") or data.get("student_email")
            data["studentEmail"] = se
            data["student_email"] = se
            ea = data.get("enrolledAt") or data.get("enrolled_at")
            data["enrolledAt"] = ea
            data["enrolled_at"] = ea
            tac = data.get("totalAssessedConcepts", data.get("total_assessed_concepts", 0))
            data["totalAssessedConcepts"] = tac
            data["total_assessed_concepts"] = tac
            tc = data.get("totalConcepts", data.get("total_concepts", 0))
            data["totalConcepts"] = tc
            data["total_concepts"] = tc
            am = data.get("averageMastery", data.get("average_mastery", 0.0))
            data["averageMastery"] = am
            data["average_mastery"] = am
        return data
