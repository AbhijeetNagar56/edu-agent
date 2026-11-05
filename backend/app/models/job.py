from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.common import JobStatus


class GradingJob(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    submissionId: str = Field(..., alias="submissionId")
    status: JobStatus = JobStatus.PENDING
    retryCount: int = Field(0, alias="retryCount")
    maxRetries: int = Field(3, alias="maxRetries")
    lockedBy: Optional[str] = Field(None, alias="lockedBy")
    lockedAt: Optional[str] = Field(None, alias="lockedAt")
    errorLog: Optional[str] = Field(None, alias="errorLog")
    startedAt: Optional[str] = Field(None, alias="startedAt")
    completedAt: Optional[str] = Field(None, alias="completedAt")


class JobProcessItemResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jobId: str = Field(..., alias="jobId")
    submissionId: str = Field(..., alias="submissionId")
    status: str
    score: Optional[float] = None
    durationMs: Optional[int] = Field(None, alias="durationMs")
    error: Optional[str] = None


class BatchProcessResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    processedCount: int = Field(0, alias="processedCount")
    succeededCount: int = Field(0, alias="succeededCount")
    failedCount: int = Field(0, alias="failedCount")
    retriedCount: int = Field(0, alias="retriedCount")
    jobs: List[JobProcessItemResult] = Field(default_factory=list)
