from datetime import datetime, timezone
import time
from typing import Tuple
from app.core.logging import logger
from app.models.evaluation import CriterionEvaluation, EvaluationResult
from app.models.rubric import Rubric
from app.models.submission import Submission
from app.ai.extract import extract_document_structure, RateLimitException, ExtractionError
from app.ai.grade import evaluate_submission_against_rubric, GradingError


async def run_evaluation_pipeline(
    submission: Submission,
    rubric: Rubric,
    raw_content: str,
) -> Tuple[EvaluationResult, int]:
    """
    Orchestrates the two-stage sequential Gemini AI Pipeline:
    Step 1: Document extraction into structured JSON via Gemini Flash-Lite.
    Step 2: Rubric evaluation & score computation via Gemini Flash.
    Returns (EvaluationResult, durationMs).
    """
    start_time = time.time()
    logger.info(f"Starting 2-Step AI Pipeline for submission {submission.id} (Rubric: {rubric.id})")

    # Stage 1: Extraction & Layout Normalization
    structured_doc = await extract_document_structure(raw_content, submission.fileName)

    # Stage 2: Deep Pedagogical Grading
    grading_output = await evaluate_submission_against_rubric(structured_doc, rubric)

    duration_ms = int((time.time() - start_time) * 1000)

    # Map to CriterionEvaluation with evidence, reasoning, and scoreRatio
    criteria_scores = [
        CriterionEvaluation(
            criterionId=c.criterionId,
            title=c.title,
            scoreAwarded=c.scoreAwarded,
            maxPoints=c.maxPoints,
            scoreRatio=c.scoreRatio,
            evidence=c.evidenceFromSubmission,
            reasoning=c.reasoning,
            feedback=c.feedback,
            strengths=c.strengths,
            improvements=c.improvements,
        )
        for c in grading_output.criteriaEvaluations
    ]

    max_score = grading_output.maxScore or rubric.totalPoints or 100.0
    percentage = round((grading_output.totalScore / max_score) * 100.0) if max_score > 0 else 0.0

    eval_result = EvaluationResult(
        score=grading_output.totalScore,
        maxScore=max_score,
        percentage=percentage,
        criteriaScores=criteria_scores,
        summaryFeedback=grading_output.summaryFeedback,
        strengths=grading_output.strengths,
        improvements=grading_output.improvements,
        conceptFeedback=[],
        aiModelExtraction="Gemini Flash-Lite",
        aiModelGrading="Gemini Flash",
        evaluatedAt=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(
        f"Pipeline completed for submission {submission.id}: score={eval_result.score}/{eval_result.maxScore} in {duration_ms}ms"
    )

    return eval_result, duration_ms
