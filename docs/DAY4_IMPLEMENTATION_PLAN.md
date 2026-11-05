# Day 4 Implementation Plan: AI Evaluation and Concept Mastery Engine

## Executive Summary

The objective of Day 4 is to implement a production-grade, explainable, and reliable AI-powered assignment evaluation pipeline that ingests student submissions (PDF or text), produces structured rubric-level evaluations via Google Gemini, maps criterion evaluations to curriculum concepts using the authoritative `assignment_criterion_concepts` table, persists granular evidence and feedback, and updates normalized student concept mastery records (`[0.0, 1.0]`) while strictly respecting faculty overrides.

---

## 1. Audit of Existing Implementation

### 1.1 What Already Works
- **Gemini SDK Setup**: `backend/app/ai/extract.py` and `backend/app/ai/grade.py` integrate with `google.genai` Client using `GEMINI_MODEL_LITE` and `GEMINI_MODEL_FLASH`.
- **PDF Extraction**: `StorageService.extract_text_from_pdf` uses `pypdf` to extract text from multi-page PDFs.
- **Authoritative Database Tables**: `public.submissions`, `public.assignments`, `public.concepts`, `public.assignment_criterion_concepts`, `public.evaluations`, `public.criterion_evaluations`, `public.submission_concept_feedback`, `public.student_concept_mastery`, and `public.faculty_overrides` exist in the database.
- **Day 3 Concept Mapping**: `assignment_criterion_concepts` is the single authoritative join table linking assignment rubric criteria to course concepts with foreign keys and database triggers.
- **Batch Endpoint**: `/internal/process-jobs` endpoint exists with cron secret authorization.

### 1.2 Gaps and Deficiencies to Address
1. **Disconnected Mastery Pipeline**: The batch job runner (`QueueService.process_batch`) evaluates assignments and saves `sub.evaluation`, but **never** links criteria to `assignment_criterion_concepts`, **never** persists rows into `submission_concept_feedback`, and **never** updates `student_concept_mastery`.
2. **Missing Criterion Schema Fields**: `criterion_evaluations` currently lacks `evidence`, `reasoning`, and `score_ratio` columns required by Day 4 Phase B/C.
3. **Missing Concept Feedback Schema Fields**: `submission_concept_feedback` currently only has `(id, submission_id, concept_id, mastery_percentage, feedback_text)`. It lacks `student_id`, `criterion_id`, `evaluation_id`, `evidence`, `score_ratio`, and `confidence`.
4. **Faculty Override Precedence**: If a faculty member overrides a student's grade, subsequent AI grading or re-evaluations could overwrite the faculty's score and mastery. There is no protection preventing AI from clobbering active faculty overrides.
5. **Lack of Idempotency**: Reprocessing an existing submission increments `evidence_count` and modifies mastery on repeated runs.
6. **No Atomic Job Claiming**: `QueueService.process_batch` selects pending jobs without row locking (`FOR UPDATE SKIP LOCKED`). Two concurrent workers can claim and process the same job, creating duplicate evaluations and race conditions.
7. **Unsafe Fallback on Empty PDFs**: If a PDF contains no extractable text (e.g. scanned image or corrupted PDF), the current code falls back to heuristic grading and invents an 88% grade instead of flagging the submission for `manual_review`.
8. **Missing `manual_review` Status**: The check constraints on `submissions.status` and `grading_jobs.status` do not include `'manual_review'`.

---

## 2. Architecture & Design

### 2.1 Complete End-to-End Workflow
```
Student Upload (PDF/MD)
  ↓
Storage & Ingestion (pypdf text extraction)
  ↓
Empty Text Detection?
  ├─ YES → Mark Submission & Job 'manual_review', record note, halt automated grading
  └─ NO  → Create GradingJob (pending)
  ↓
Worker Atomic Claim (`claim_grading_job` via FOR UPDATE SKIP LOCKED)
  ↓
Gemini 2-Stage Evaluation:
  Stage 1: Document extraction into StructuredDocument (Gemini Flash-Lite)
  Stage 2: Independent Rubric Criteria Evaluation (Gemini Flash)
  ↓
Pydantic Validation & Bounds Checking (awarded_points, max_points, score_ratio, total_score)
  ↓
Authoritative Concept Mapping:
  Query `assignment_criterion_concepts` for mapped concepts
  ↓
Persist Evaluations:
  - Upsert `evaluations` (submission_id unique)
  - Insert `criterion_evaluations` (with evidence, reasoning, score_ratio)
  - Insert/Upsert `submission_concept_feedback` (with student_id, criterion_id, evidence, score_ratio)
  ↓
Concept Mastery Engine:
  - Check for active faculty override (preserve if present)
  - Calculate deterministic evidence aggregation
  - Update `student_concept_mastery` [0.0 - 1.0] (idempotent)
  ↓
Mark Job 'done' & Emit Realtime Status
```

### 2.2 Versioned SQL Migration (07)
We will introduce Migration 07 (`07_evaluation_mastery_pipeline.up.sql` and `down.sql`):
- Add `reasoning`, `evidence`, `score_ratio` to `criterion_evaluations`.
- Add `student_id`, `criterion_id`, `evaluation_id`, `evidence`, `score_ratio`, `confidence` to `submission_concept_feedback`.
- Add `locked_at`, `locked_by`, `max_retries` to `grading_jobs`.
- Expand check constraints for `submissions.status` and `grading_jobs.status` to include `'manual_review'`.
- Create atomic `claim_grading_job(p_worker_id, p_stale_interval)` RPC.
- All DDL without broad silent exception handling, with post-migration verification assertions.

### 2.3 Structured Gemini Evaluation
- Strict Pydantic models:
  - `CriterionGradingOutput`: `criterionId`, `title`, `scoreAwarded`, `maxPoints`, `scoreRatio`, `evidenceFromSubmission`, `reasoning`, `feedback`, `strengths`, `improvements`.
  - `GradingOutput`: `totalScore`, `maxScore`, `summaryFeedback`, `strengths`, `improvements`, `criteriaEvaluations`.
- Strict validation:
  - Awarded points strictly between `0` and `maxPoints`.
  - Criterion IDs strictly verified against assignment rubric criteria.
  - Overall score validated against sum of criterion awarded points.
  - Reject malformed responses or missing criteria.

### 2.4 Concept Mastery Aggregation Engine
Documented comprehensively in `docs/MASTERY_UPDATE_DESIGN.md`:
- Normalized score range: `[0.0, 1.0]`.
- Asymptotic, confidence-weighted aggregation preventing single-assignment wild swings.
- Absolute faculty override precedence (`source = 'faculty_override'` cannot be overwritten by AI).
- Deterministic idempotency: reprocessing the same submission evaluation yields identical mastery without duplicating evidence counts.

---

## 3. Files to Modify and Create

| File | Nature of Change |
| :--- | :--- |
| `supabase/migrations/07_evaluation_mastery_pipeline.up.sql` | Schema updates for criterion evidence, concept feedback, atomic queue claiming, and `manual_review` status. |
| `supabase/migrations/07_evaluation_mastery_pipeline.down.sql` | Clean rollback for Migration 07. |
| `supabase/console_setup.sql` | Synchronize Section 14 with Migration 07. |
| `backend/app/models/common.py` | Add `MANUAL_REVIEW = "manual_review"` to `JobStatus`. |
| `backend/app/ai/schemas.py` | Enrich `CriterionGradingOutput` with `scoreRatio`, `evidenceFromSubmission`, and `reasoning`. |
| `backend/app/ai/prompts/grading.py` | Update prompt to instruct Gemini to extract explicit textual evidence and pedagogical reasoning per criterion. |
| `backend/app/ai/grade.py` | Enforce strict Pydantic validation, criterion ID matching against rubric, and score bounds. |
| `backend/app/services/storage.py` | Detect empty/scanned PDFs with no extractable text and flag for manual review. |
| `backend/app/services/repository.py` | Implement `get_assignment_criterion_concepts`, atomic job claiming, evaluation persistence, concept feedback persistence, and mastery engine. |
| `backend/app/services/queue.py` | Overhaul batch processor to use atomic claiming, empty-text detection, concept mapping, and mastery updates. |
| `frontend/components/GradeDetailModal.tsx` | Display criterion evidence, reasoning, and mapped concept feedback. |
| `backend/tests/test_ai_pipeline.py` | Add unit tests for Gemini evaluation validation, bounds checking, empty PDF handling, and rate limits. |
| `backend/tests/test_mastery_engine.py` | Add unit tests for concept mapping, mastery aggregation, idempotency, and faculty override precedence. |
| `backend/tests/test_queue_lifecycle.py` | Add unit tests for atomic claiming, concurrent workers, retry limits, and crash recovery. |
| `scratch/test_postgres_day4.py` | PostgreSQL database verification script for Migration 07, atomic claim RPC, triggers, and RLS. |
| `docs/MASTERY_UPDATE_DESIGN.md` | Formal specification of the mastery update algorithm and equations. |
| `docs/DAY4_EXECUTION_REPORT.md` | Complete Day 4 execution report with test logs and deliverables. |
