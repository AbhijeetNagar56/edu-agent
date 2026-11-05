from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseOverviewAnalytics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    courseId: str
    course_id: Optional[str] = None
    courseCode: str
    course_code: Optional[str] = None
    courseName: str
    course_name: Optional[str] = None
    totalEnrolled: int = 0
    total_enrolled: Optional[int] = None
    totalAssignments: int = 0
    total_assignments: Optional[int] = None
    publishedAssignments: int = 0
    published_assignments: Optional[int] = None
    draftAssignments: int = 0
    draft_assignments: Optional[int] = None
    totalSubmissions: int = 0
    total_submissions: Optional[int] = None
    completedEvaluations: int = 0
    completed_evaluations: Optional[int] = None
    pendingEvaluations: int = 0
    pending_evaluations: Optional[int] = None
    manualReviewSubmissions: int = 0
    manual_review_submissions: Optional[int] = None
    averageAssignmentScore: float = 0.0
    average_assignment_score: Optional[float] = None
    conceptCoveragePercentage: float = 0.0
    concept_coverage_percentage: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            cid = data.get("courseId") or data.get("course_id") or ""
            data["courseId"] = cid
            data["course_id"] = cid
            code = data.get("courseCode") or data.get("course_code") or ""
            data["courseCode"] = code
            data["course_code"] = code
            name = data.get("courseName") or data.get("course_name") or ""
            data["courseName"] = name
            data["course_name"] = name
            te = data.get("totalEnrolled", data.get("total_enrolled", 0))
            data["totalEnrolled"] = te
            data["total_enrolled"] = te
            ta = data.get("totalAssignments", data.get("total_assignments", 0))
            data["totalAssignments"] = ta
            data["total_assignments"] = ta
            pa = data.get("publishedAssignments", data.get("published_assignments", 0))
            data["publishedAssignments"] = pa
            data["published_assignments"] = pa
            da = data.get("draftAssignments", data.get("draft_assignments", 0))
            data["draftAssignments"] = da
            data["draft_assignments"] = da
            ts = data.get("totalSubmissions", data.get("total_submissions", 0))
            data["totalSubmissions"] = ts
            data["total_submissions"] = ts
            ce = data.get("completedEvaluations", data.get("completed_evaluations", 0))
            data["completedEvaluations"] = ce
            data["completed_evaluations"] = ce
            pe = data.get("pendingEvaluations", data.get("pending_evaluations", 0))
            data["pendingEvaluations"] = pe
            data["pending_evaluations"] = pe
            mr = data.get("manualReviewSubmissions", data.get("manual_review_submissions", 0))
            data["manualReviewSubmissions"] = mr
            data["manual_review_submissions"] = mr
            avg = data.get("averageAssignmentScore", data.get("average_assignment_score", 0.0))
            data["averageAssignmentScore"] = avg
            data["average_assignment_score"] = avg
            cov = data.get("conceptCoveragePercentage", data.get("concept_coverage_percentage", 0.0))
            data["conceptCoveragePercentage"] = cov
            data["concept_coverage_percentage"] = cov
        return data


class StudentProgressSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    studentId: str
    student_id: Optional[str] = None
    studentName: str
    student_name: Optional[str] = None
    studentEmail: str
    student_email: Optional[str] = None
    totalConcepts: int = 0
    total_concepts: Optional[int] = None
    assessedConcepts: int = 0
    assessed_concepts: Optional[int] = None
    coveragePercentage: float = 0.0
    coverage_percentage: Optional[float] = None
    averageMastery: float = 0.0
    average_mastery: Optional[float] = None
    lowMasteryCount: int = 0
    low_mastery_count: Optional[int] = None
    developingCount: int = 0
    developing_count: Optional[int] = None
    strongCount: int = 0
    strong_count: Optional[int] = None
    unassessedCount: int = 0
    unassessed_count: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sid = data.get("studentId") or data.get("student_id") or ""
            data["studentId"] = sid
            data["student_id"] = sid
            sname = data.get("studentName") or data.get("student_name") or "Student"
            data["studentName"] = sname
            data["student_name"] = sname
            semail = data.get("studentEmail") or data.get("student_email") or ""
            data["studentEmail"] = semail
            data["student_email"] = semail
            tc = data.get("totalConcepts", data.get("total_concepts", 0))
            data["totalConcepts"] = tc
            data["total_concepts"] = tc
            ac = data.get("assessedConcepts", data.get("assessed_concepts", 0))
            data["assessedConcepts"] = ac
            data["assessed_concepts"] = ac
            cov = data.get("coveragePercentage", data.get("coverage_percentage", 0.0))
            data["coveragePercentage"] = cov
            data["coverage_percentage"] = cov
            avg = data.get("averageMastery", data.get("average_mastery", 0.0))
            data["averageMastery"] = avg
            data["average_mastery"] = avg
            low = data.get("lowMasteryCount", data.get("low_mastery_count", 0))
            data["lowMasteryCount"] = low
            data["low_mastery_count"] = low
            dev = data.get("developingCount", data.get("developing_count", 0))
            data["developingCount"] = dev
            data["developing_count"] = dev
            strg = data.get("strongCount", data.get("strong_count", 0))
            data["strongCount"] = strg
            data["strong_count"] = strg
            un = data.get("unassessedCount", data.get("unassessed_count", 0))
            data["unassessedCount"] = un
            data["unassessed_count"] = un
        return data


class ConceptAnalyticsSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conceptId: str
    concept_id: Optional[str] = None
    name: str
    category: str = "Core"
    difficulty: str = "intermediate"
    assessedStudentsCount: int = 0
    assessed_students_count: Optional[int] = None
    unassessedStudentsCount: int = 0
    unassessed_students_count: Optional[int] = None
    averageMastery: float = 0.0
    average_mastery: Optional[float] = None
    lowMasteryCount: int = 0
    low_mastery_count: Optional[int] = None
    developingCount: int = 0
    developing_count: Optional[int] = None
    strongHighCount: int = 0
    strong_high_count: Optional[int] = None
    needsAttention: bool = False
    needs_attention: Optional[bool] = None
    attentionReason: Optional[str] = None
    attention_reason: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            cid = data.get("conceptId") or data.get("concept_id") or ""
            data["conceptId"] = cid
            data["concept_id"] = cid
            asc = data.get("assessedStudentsCount", data.get("assessed_students_count", 0))
            data["assessedStudentsCount"] = asc
            data["assessed_students_count"] = asc
            usc = data.get("unassessedStudentsCount", data.get("unassessed_students_count", 0))
            data["unassessedStudentsCount"] = usc
            data["unassessed_students_count"] = usc
            avg = data.get("averageMastery", data.get("average_mastery", 0.0))
            data["averageMastery"] = avg
            data["average_mastery"] = avg
            low = data.get("lowMasteryCount", data.get("low_mastery_count", 0))
            data["lowMasteryCount"] = low
            data["low_mastery_count"] = low
            dev = data.get("developingCount", data.get("developing_count", 0))
            data["developingCount"] = dev
            data["developing_count"] = dev
            sh = data.get("strongHighCount", data.get("strong_high_count", 0))
            data["strongHighCount"] = sh
            data["strong_high_count"] = sh
            na = data.get("needsAttention", data.get("needs_attention", False))
            data["needsAttention"] = na
            data["needs_attention"] = na
            ar = data.get("attentionReason", data.get("attention_reason"))
            data["attentionReason"] = ar
            data["attention_reason"] = ar
        return data


class AssignmentAnalyticsSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    assignmentId: str
    assignment_id: Optional[str] = None
    title: str
    dueDate: Optional[str] = None
    due_date: Optional[str] = None
    maxMarks: float = 100.0
    max_marks: Optional[float] = None
    status: str = "draft"
    submissionCount: int = 0
    submission_count: Optional[int] = None
    completionRate: float = 0.0
    completion_rate: Optional[float] = None
    averageScore: float = 0.0
    average_score: Optional[float] = None
    scoreDistribution: Dict[str, int] = Field(default_factory=dict)
    score_distribution: Optional[Dict[str, int]] = None
    manualReviewCount: int = 0
    manual_review_count: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            aid = data.get("assignmentId") or data.get("assignment_id") or ""
            data["assignmentId"] = aid
            data["assignment_id"] = aid
            dd = data.get("dueDate") or data.get("due_date")
            data["dueDate"] = dd
            data["due_date"] = dd
            mm = data.get("maxMarks", data.get("max_marks", 100.0))
            data["maxMarks"] = mm
            data["max_marks"] = mm
            sc = data.get("submissionCount", data.get("submission_count", 0))
            data["submissionCount"] = sc
            data["submission_count"] = sc
            cr = data.get("completionRate", data.get("completion_rate", 0.0))
            data["completionRate"] = cr
            data["completion_rate"] = cr
            ascore = data.get("averageScore", data.get("average_score", 0.0))
            data["averageScore"] = ascore
            data["average_score"] = ascore
            sd = data.get("scoreDistribution", data.get("score_distribution", {}))
            data["scoreDistribution"] = sd
            data["score_distribution"] = sd
            mrc = data.get("manualReviewCount", data.get("manual_review_count", 0))
            data["manualReviewCount"] = mrc
            data["manual_review_count"] = mrc
        return data


class CourseLearningAnalytics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    overview: CourseOverviewAnalytics
    studentProgress: List[StudentProgressSummary] = Field(default_factory=list)
    student_progress: Optional[List[StudentProgressSummary]] = None
    conceptAnalytics: List[ConceptAnalyticsSummary] = Field(default_factory=list)
    concept_analytics: Optional[List[ConceptAnalyticsSummary]] = None
    assignmentAnalytics: List[AssignmentAnalyticsSummary] = Field(default_factory=list)
    assignment_analytics: Optional[List[AssignmentAnalyticsSummary]] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sp = data.get("studentProgress", data.get("student_progress", []))
            data["studentProgress"] = sp
            data["student_progress"] = sp
            ca = data.get("conceptAnalytics", data.get("concept_analytics", []))
            data["conceptAnalytics"] = ca
            data["concept_analytics"] = ca
            aa = data.get("assignmentAnalytics", data.get("assignment_analytics", []))
            data["assignmentAnalytics"] = aa
            data["assignment_analytics"] = aa
        return data


# =============================================================================
# DIRECT CONCEPT MASTERY OVERRIDE MODELS
# =============================================================================

class ConceptMasteryOverrideRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    masteryScore: float = Field(..., ge=0.0, le=1.0, alias="mastery_score")
    overrideReason: str = Field(..., min_length=3, alias="override_reason")
    confidenceScore: Optional[float] = Field(default=0.9, ge=0.0, le=1.0, alias="confidence_score")


class ConceptMasteryOverrideResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    studentId: str
    student_id: Optional[str] = None
    conceptId: str
    concept_id: Optional[str] = None
    masteryScore: float
    mastery_score: Optional[float] = None
    masteryPercentage: float
    mastery_percentage: Optional[float] = None
    confidenceScore: float
    confidence_score: Optional[float] = None
    source: str = "faculty_override"
    overriddenBy: str
    overridden_by: Optional[str] = None
    overrideReason: str
    override_reason: Optional[str] = None
    overriddenAt: str
    overridden_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_casings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sid = data.get("studentId") or data.get("student_id")
            data["studentId"] = sid
            data["student_id"] = sid
            cid = data.get("conceptId") or data.get("concept_id")
            data["conceptId"] = cid
            data["concept_id"] = cid
            ms = data.get("masteryScore", data.get("mastery_score", 0.0))
            data["masteryScore"] = ms
            data["mastery_score"] = ms
            mp = data.get("masteryPercentage", data.get("mastery_percentage", round(ms * 100.0, 2)))
            data["masteryPercentage"] = mp
            data["mastery_percentage"] = mp
            cs = data.get("confidenceScore", data.get("confidence_score", 0.9))
            data["confidenceScore"] = cs
            data["confidence_score"] = cs
            by = data.get("overriddenBy") or data.get("overridden_by")
            data["overriddenBy"] = by
            data["overridden_by"] = by
            reason = data.get("overrideReason") or data.get("override_reason")
            data["overrideReason"] = reason
            data["override_reason"] = reason
            at = data.get("overriddenAt") or data.get("overridden_at")
            data["overriddenAt"] = at
            data["overridden_at"] = at
        return data
