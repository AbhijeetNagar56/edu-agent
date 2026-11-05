from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    FLAGGED = "flagged"
    MANUAL_REVIEW = "manual_review"


class ProcessingStep(str, Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    GRADING = "grading"
    SYNCED = "synced"


class FileType(str, Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"


T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    data: List[T]
    meta: Dict[str, Any]


class ErrorDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class StandardError(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    success: bool = False
    error: ErrorDetails
    timestamp: str = datetime.now(timezone.utc).isoformat()
