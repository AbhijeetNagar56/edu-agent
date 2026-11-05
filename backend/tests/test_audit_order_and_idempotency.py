import pytest
import uuid
from pydantic import ValidationError
from app.models.common import JobStatus
from app.models.submission import Submission, FacultyOverride
from app.models.evaluation import EvaluationResult, CriterionEvaluation
from app.models.assignment import Assignment, CriterionConceptMap
from app.models.curriculum import Concept
from app.services.repository import Repository, db


def make_submission(**kwargs) -> Submission:
    defaults = {
        "id": f"sub-{uuid.uuid4().hex[:6]}",
        "studentId": f"student-{uuid.uuid4().hex[:6]}",
        "studentName": "Audit Student",
        "studentEmail": "audit@university.edu",
        "assignmentId": f"assign-{uuid.uuid4().hex[:6]}",
        "assignmentTitle": "Algorithmic Audit Assignment",
        "courseCode": "CS101",
        "fileName": "solution.py",
        "fileSize": "10 KB",
        "fileType": "text",
        "status": JobStatus.DONE,
        "submittedAt": "2026-11-05T00:00:00Z",
        "rubricId": "rub-audit",
    }
    defaults.update(kwargs)
    return Submission(**defaults)


def make_assignment(**kwargs) -> Assignment:
    defaults = {
        "id": f"assign-{uuid.uuid4().hex[:6]}",
        "course_id": "CS101",
        "title": "Audit Assignment",
        "dueDate": "2026-12-01T23:59:59Z",
        "maxPoints": 100.0,
        "status": "published",
        "rubric_id": "rub-audit",
        "concept_ids": [],
        "criterion_concepts": [],
    }
    defaults.update(kwargs)
    return Assignment(**defaults)


def make_criterion(**kwargs) -> CriterionEvaluation:
    defaults = {
        "criterionId": f"crit-{uuid.uuid4().hex[:6]}",
        "title": "Criterion Title",
        "scoreAwarded": 10.0,
        "maxPoints": 10.0,
        "scoreRatio": 1.0,
        "confidence": 0.8,
        "evidence": "Evidence string with >= 15 characters of text",
        "reasoning": "Reasoning string for assessment",
        "feedback": "Constructive feedback string",
    }
    defaults.update(kwargs)
    return CriterionEvaluation(**defaults)


def make_evaluation(**kwargs) -> EvaluationResult:
    defaults = {
        "score": 100.0,
        "maxScore": 100.0,
        "percentage": 100.0,
        "summaryFeedback": "Overall feedback",
        "strengths": [],
        "improvements": [],
        "criteriaScores": [],
        "evaluatedAt": "2026-11-05T00:00:00Z",
    }
    defaults.update(kwargs)
    return EvaluationResult(**defaults)


def make_override(**kwargs) -> FacultyOverride:
    defaults = {
        "isOverridden": True,
        "originalScore": 50.0,
        "overriddenScore": 95.0,
        "overriddenBy": "prof_oak",
        "overrideReason": "Demonstrated mastery during review",
        "overriddenAt": "2026-11-05T00:00:00Z",
    }
    defaults.update(kwargs)
    return FacultyOverride(**defaults)


@pytest.fixture(autouse=True)
def clean_test_db():
    orig_submissions = dict(db.submissions)
    orig_mastery = list(db.mastery_records)
    orig_assignments = dict(db.assignments)
    orig_crit_concepts = dict(db.assignment_criterion_concepts)
    orig_concepts = dict(db.concepts)
    orig_feedback = list(getattr(db, "submission_concept_feedback", []))
    orig_overrides = list(getattr(db, "faculty_overrides", []))

    yield

    db.submissions = orig_submissions
    db.mastery_records = orig_mastery
    db.assignments = orig_assignments
    db.assignment_criterion_concepts = orig_crit_concepts
    db.concepts = orig_concepts
    db.submission_concept_feedback = orig_feedback
    db.faculty_overrides = orig_overrides


# =============================================================================
# 1. ORDER INDEPENDENCE TESTS
# =============================================================================

def test_order_independence_multiple_criteria_same_concept():
    """
    AUDIT REQUIREMENT 1:
    Test criteria mapped to the same concept in both orders:
      Criterion A: score ratio 0.9, confidence 0.9
      Criterion B: score ratio 0.3, confidence 0.5
    Assert that the final mastery and confidence are strictly identical regardless of order:
      [A then B] vs [B then A].
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    crit_a_id = f"crit-A-{uuid.uuid4().hex[:4]}"
    crit_b_id = f"crit-B-{uuid.uuid4().hex[:4]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Dynamic Programming")

    # Define Criterion A (r = 0.9, c = 0.9, max = 10, awarded = 9)
    crit_A = make_criterion(
        criterionId=crit_a_id,
        title="Criterion A",
        scoreAwarded=9.0,
        maxPoints=10.0,
        scoreRatio=0.9,
        confidence=0.9,
    )

    # Define Criterion B (r = 0.3, c = 0.5, max = 10, awarded = 3)
    crit_B = make_criterion(
        criterionId=crit_b_id,
        title="Criterion B",
        scoreAwarded=3.0,
        maxPoints=10.0,
        scoreRatio=0.3,
        confidence=0.5,
    )

    # --- TRIAL 1: Process in order [A then B] ---
    student_1 = f"student-1-{uuid.uuid4().hex[:4]}"
    assign_1 = f"assign-1-{uuid.uuid4().hex[:4]}"
    sub_1 = f"sub-1-{uuid.uuid4().hex[:4]}"

    db.assignment_criterion_concepts[assign_1] = [
        CriterionConceptMap(criterionId=crit_a_id, conceptId=cid),
        CriterionConceptMap(criterionId=crit_b_id, conceptId=cid),
    ]
    submission_1 = make_submission(id=sub_1, studentId=student_1, assignmentId=assign_1)
    db.submissions[sub_1] = submission_1

    eval_AB = make_evaluation(
        score=12.0,
        maxScore=20.0,
        percentage=60.0,
        summaryFeedback="Evaluated AB",
        criteriaScores=[crit_A, crit_B],  # Order A then B
    )

    result_AB = Repository.record_concept_evidence_and_update_mastery(submission_1, eval_AB)
    assert len(result_AB) == 1
    mastery_AB = result_AB[0].masteryContribution
    confidence_AB = result_AB[0].confidenceScore
    evidence_AB = result_AB[0].scoreRatio

    # --- TRIAL 2: Process in order [B then A] ---
    student_2 = f"student-2-{uuid.uuid4().hex[:4]}"
    assign_2 = f"assign-2-{uuid.uuid4().hex[:4]}"
    sub_2 = f"sub-2-{uuid.uuid4().hex[:4]}"

    db.assignment_criterion_concepts[assign_2] = [
        CriterionConceptMap(criterionId=crit_b_id, conceptId=cid),
        CriterionConceptMap(criterionId=crit_a_id, conceptId=cid),
    ]
    submission_2 = make_submission(id=sub_2, studentId=student_2, assignmentId=assign_2)
    db.submissions[sub_2] = submission_2

    eval_BA = make_evaluation(
        score=12.0,
        maxScore=20.0,
        percentage=60.0,
        summaryFeedback="Evaluated BA",
        criteriaScores=[crit_B, crit_A],  # Order B then A
    )

    result_BA = Repository.record_concept_evidence_and_update_mastery(submission_2, eval_BA)
    assert len(result_BA) == 1
    mastery_BA = result_BA[0].masteryContribution
    confidence_BA = result_BA[0].confidenceScore
    evidence_BA = result_BA[0].scoreRatio

    # Strict Mathematical Equality Assertions
    assert evidence_AB == evidence_BA == 0.60
    assert mastery_AB == mastery_BA
    assert confidence_AB == confidence_BA

    # Expected analytical values:
    # E = (9 + 3) / 20 = 0.60
    # c_new = (10*0.9 + 10*0.5) / 20 = 0.70
    # M_1 = (0.50 * 1.0 + 0.60 * 0.70) / (1.0 + 0.70) = 0.92 / 1.70 = 0.5412
    # c_1 = min(0.95, 0.70 * 0.85) = 0.5950
    assert mastery_AB == 0.5412
    assert confidence_AB == 0.5950


# =============================================================================
# 2. CORRECTED EVALUATION AND IDEMPOTENCY TESTS
# =============================================================================

def test_corrected_evaluation_and_idempotency_without_drift():
    """
    AUDIT REQUIREMENT 2:
    1. Process an evaluation (e.g. score awarded 9/10, r=0.9).
    2. Verify evidence count N=1 and mastery calculated.
    3. Update its criterion score (e.g. corrected to 4/10, r=0.4).
    4. Reprocess the same submission.
    5. Verify old evidence is replaced rather than counted again.
    6. Verify mastery is recomputed from authoritative evidence without drift.
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    crit_id = f"crit-{uuid.uuid4().hex[:6]}"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Recursion")
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit_id, conceptId=cid)]
    submission = make_submission(id=sid, studentId=student_id, assignmentId=aid)
    db.submissions[sid] = submission

    # Step 1: Initial evaluation (Score = 9/10 -> r = 0.9, c = 0.8)
    eval_1 = make_evaluation(
        score=9.0,
        maxScore=10.0,
        percentage=90.0,
        criteriaScores=[
            make_criterion(
                criterionId=crit_id,
                scoreAwarded=9.0,
                maxPoints=10.0,
                scoreRatio=0.9,
                confidence=0.8,
            )
        ]
    )
    Repository.record_concept_evidence_and_update_mastery(submission, eval_1)

    rec_1 = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec_1["evidence_count"] == 1
    # M_1 = (0.50 * 1.0 + 0.9 * 0.8) / (1.0 + 0.8) = 1.22 / 1.8 = 0.6778
    assert rec_1["mastery_score"] == 0.6778

    # Step 2: Reprocess identical submission (Idempotency test)
    Repository.record_concept_evidence_and_update_mastery(submission, eval_1)
    rec_rep = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec_rep["evidence_count"] == 1
    assert rec_rep["mastery_score"] == 0.6778

    # Check evidence record in db.submission_concept_feedback
    fb_recs = [fb for fb in db.submission_concept_feedback if fb["submission_id"] == sid and fb["concept_id"] == cid]
    assert len(fb_recs) == 1
    assert fb_recs[0]["score_ratio"] == 0.9

    # Step 3 & 4: Regrade / Correct evaluation to score 4/10 (r = 0.4, c = 0.8)
    eval_corrected = make_evaluation(
        score=4.0,
        maxScore=10.0,
        percentage=40.0,
        criteriaScores=[
            make_criterion(
                criterionId=crit_id,
                scoreAwarded=4.0,
                maxPoints=10.0,
                scoreRatio=0.4,
                confidence=0.8,
            )
        ]
    )
    Repository.record_concept_evidence_and_update_mastery(submission, eval_corrected)

    # Step 5: Verify evidence was REPLACED in-place, NOT duplicated
    fb_recs_after = [fb for fb in db.submission_concept_feedback if fb["submission_id"] == sid and fb["concept_id"] == cid]
    assert len(fb_recs_after) == 1
    assert fb_recs_after[0]["score_ratio"] == 0.4

    # Step 6: Verify mastery was recomputed cleanly from authoritative records:
    # Clean M_1 = (0.50 * 1.0 + 0.4 * 0.8) / (1.0 + 0.8) = 0.82 / 1.8 = 0.4556
    rec_after = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec_after["evidence_count"] == 1
    assert rec_after["mastery_score"] == 0.4556, (
        f"Expected clean recomputation 0.4556 without drift, got {rec_after['mastery_score']}"
    )


# =============================================================================
# 3. FACULTY OVERRIDE LIFECYCLE TESTS
# =============================================================================

def test_faculty_override_lifecycle_full():
    """
    AUDIT REQUIREMENT 3:
    - Active override followed by new AI evidence.
    - Multiple sequential faculty overrides.
    - Worker retry while override is active.
    - Override removal and recalculation after override removal.
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    crit_id = f"crit-{uuid.uuid4().hex[:6]}"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Trees")
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit_id, conceptId=cid)]
    submission = make_submission(id=sid, studentId=student_id, assignmentId=aid)
    db.submissions[sid] = submission

    # 1. Initial AI evaluation (score = 50.0 -> r = 0.5)
    ai_eval = make_evaluation(
        score=50.0,
        maxScore=100.0,
        percentage=50.0,
        criteriaScores=[
            make_criterion(
                criterionId=crit_id,
                scoreAwarded=50.0,
                maxPoints=100.0,
                scoreRatio=0.5,
                confidence=0.8,
            )
        ]
    )
    Repository.record_concept_evidence_and_update_mastery(submission, ai_eval)
    rec = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec["source"] == "ai"
    assert rec["mastery_score"] == 0.50

    # 2. Faculty applies Override 1 (Score = 95.0)
    override_1 = make_override(
        isOverridden=True,
        originalScore=50.0,
        overriddenScore=95.0,
        overriddenBy="prof_oak",
        overrideReason="Exceptional creative tree traversal",
    )
    Repository.override_submission_grade(sid, override_1)

    rec_ov1 = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec_ov1["source"] == "faculty_override"
    assert rec_ov1["confidence_score"] == 1.0
    assert rec_ov1["mastery_score"] == 0.95

    # 3. New AI evaluation / worker retry runs while override is active
    # Precedence Rule: Must preserve active override!
    ai_eval_new = make_evaluation(
        score=60.0,
        maxScore=100.0,
        percentage=60.0,
        criteriaScores=[
            make_criterion(
                criterionId=crit_id,
                scoreAwarded=60.0,
                maxPoints=100.0,
                scoreRatio=0.6,
                confidence=0.8,
            )
        ]
    )
    Repository.record_concept_evidence_and_update_mastery(submission, ai_eval_new)
    rec_after_ai = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec_after_ai["source"] == "faculty_override"
    assert rec_after_ai["confidence_score"] == 1.0
    assert rec_after_ai["mastery_score"] == 0.95, "Active override must not be overwritten by AI retry"

    # 4. Multiple Faculty Overrides: Faculty amends override to 85.0
    override_2 = make_override(
        isOverridden=True,
        originalScore=50.0,
        overriddenScore=85.0,
        overriddenBy="prof_oak",
        overrideReason="Corrected minor calculation in override",
    )
    Repository.override_submission_grade(sid, override_2)
    rec_ov2 = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec_ov2["source"] == "faculty_override"
    assert rec_ov2["confidence_score"] == 1.0
    assert rec_ov2["mastery_score"] == 0.85

    # 5. Override Removal: Faculty removes the override (isOverridden = False)
    # Precedence Rule: Recalculates clean mastery from authoritative AI evidence!
    override_removed = make_override(
        isOverridden=False,
        originalScore=50.0,
        overriddenScore=50.0,
        overriddenBy="prof_oak",
        overrideReason="Override rescinded; restored AI assessment",
    )
    Repository.override_submission_grade(sid, override_removed)

    rec_restored = next(m for m in db.mastery_records if m["student_id"] == student_id and m["concept_id"] == cid)
    assert rec_restored["source"] == "ai"
    # The AI evidence was 60.0 (r=0.6, c=0.8) -> M_1 = (0.50*1.0 + 0.6*0.8)/(1.0+0.8) = 0.98/1.8 = 0.5444
    assert rec_restored["mastery_score"] == 0.5444
    assert rec_restored["confidence_score"] < 1.0


# =============================================================================
# 4. DATABASE BOUNDS AND CLAMPING TESTS
# =============================================================================

def test_database_bounds_and_clamping():
    """
    AUDIT REQUIREMENT 4:
    Verify bounds [0.0, 1.0] for score_ratio, confidence, mastery; non-negative evidence count.
    """
    cid = f"concept-{uuid.uuid4().hex[:6]}"
    crit_id = f"crit-{uuid.uuid4().hex[:6]}"
    aid = f"assign-{uuid.uuid4().hex[:6]}"
    sid = f"sub-{uuid.uuid4().hex[:6]}"
    student_id = f"student-{uuid.uuid4().hex[:6]}"

    db.concepts[cid] = Concept(id=cid, courseId="CS101", name="Complexity")
    db.assignment_criterion_concepts[aid] = [CriterionConceptMap(criterionId=crit_id, conceptId=cid)]
    submission = make_submission(id=sid, studentId=student_id, assignmentId=aid)
    db.submissions[sid] = submission

    # Case 1: Pydantic rejects invalid scoreRatio > 1.0
    with pytest.raises(ValidationError):
        make_criterion(scoreRatio=1.5)

    # Case 2: Pydantic rejects invalid scoreRatio < 0.0
    with pytest.raises(ValidationError):
        make_criterion(scoreRatio=-0.2)

    # Case 3: Pydantic rejects invalid confidence > 1.0
    with pytest.raises(ValidationError):
        make_criterion(confidence=1.2)

    # Case 4: Pydantic rejects invalid confidence < 0.0
    with pytest.raises(ValidationError):
        make_criterion(confidence=-0.1)

    # Case 5: Valid boundary inputs (0.0 and 1.0) produce valid clamped mastery
    eval_bound_high = make_evaluation(
        score=100.0,
        maxScore=100.0,
        criteriaScores=[make_criterion(criterionId=crit_id, scoreAwarded=100.0, maxPoints=100.0, scoreRatio=1.0, confidence=1.0)]
    )
    res_high = Repository.record_concept_evidence_and_update_mastery(submission, eval_bound_high)
    assert 0.0 <= res_high[0].masteryContribution <= 1.0
    assert 0.0 <= res_high[0].confidenceScore <= 1.0
    assert res_high[0].evidenceCount >= 0

    eval_bound_low = make_evaluation(
        score=0.0,
        maxScore=100.0,
        criteriaScores=[make_criterion(criterionId=crit_id, scoreAwarded=0.0, maxPoints=100.0, scoreRatio=0.0, confidence=0.0)]
    )
    res_low = Repository.record_concept_evidence_and_update_mastery(submission, eval_bound_low)
    assert 0.0 <= res_low[0].masteryContribution <= 1.0
    assert 0.0 <= res_low[0].confidenceScore <= 1.0
    assert res_low[0].evidenceCount >= 0
