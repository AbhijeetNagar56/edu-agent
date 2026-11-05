from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import APIException, format_error_response
from app.core.logging import logger
from app.routers import health, uploads, grades, internal_jobs, students, faculty_courses, faculty_assignments


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("EduAgents FastAPI Backend initialized.")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Port: {settings.PORT}")
    logger.info(f"Gemini Flash-Lite: {settings.GEMINI_MODEL_LITE}")
    logger.info(f"Gemini Flash: {settings.GEMINI_MODEL_FLASH}")
    logger.info("=" * 60)
    yield


app = FastAPI(
    title="EduAgents API",
    description="Backend API for EduAgents Human-AI Co-Learning Platform with Two-Step Gemini AI Pipeline.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return format_error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    details = {
        "validationErrors": [
            {
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
            for err in errors
        ]
    }
    return format_error_response(
        code="VALIDATION_ERROR",
        message="Request payload failed schema validation.",
        details=details,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error on {request.url.path}: {exc}")
    return format_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred.",
        details={"error": str(exc)},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# Include Routers
app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(grades.router)
app.include_router(internal_jobs.router)
app.include_router(students.router)
app.include_router(faculty_courses.router)
app.include_router(faculty_assignments.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
