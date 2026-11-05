import pytest
import psycopg2
from psycopg2.errors import CheckViolation, UniqueViolation, ForeignKeyViolation
import uuid

DB_PARAMS = {
    "dbname": "eduagents_test_fresh",
    "user": "postgres",
    "host": "localhost",
    "port": 5433,
}

@pytest.fixture(scope="module")
def pg_conn():
    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = False
    yield conn
    conn.close()


def test_student_concept_mastery_bounds_constraints(pg_conn):
    cur = pg_conn.cursor()
    # Find existing student and concept in DB
    cur.execute("SELECT id FROM public.profiles LIMIT 1;")
    student_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM public.concepts LIMIT 1;")
    concept_id = cur.fetchone()[0]

    # Test 1: mastery_score > 1.0 rejected
    pg_conn.rollback()
    with pytest.raises(CheckViolation):
        cur.execute("""
            INSERT INTO public.student_concept_mastery (
                id, student_id, concept_id, mastery_score, mastery_percentage, confidence_score, source, evidence_count
            ) VALUES (
                gen_random_uuid(), %s, %s, 1.5, 150.0, 0.8, 'ai', 1
            );
        """, (student_id, concept_id))
    pg_conn.rollback()

    # Test 2: confidence_score > 1.0 rejected
    with pytest.raises(CheckViolation):
        cur.execute("""
            INSERT INTO public.student_concept_mastery (
                id, student_id, concept_id, mastery_score, mastery_percentage, confidence_score, source, evidence_count
            ) VALUES (
                gen_random_uuid(), %s, %s, 0.8, 80.0, 1.2, 'ai', 1
            );
        """, (student_id, concept_id))
    pg_conn.rollback()

    # Test 3: evidence_count < 0 rejected
    with pytest.raises(CheckViolation):
        cur.execute("""
            INSERT INTO public.student_concept_mastery (
                id, student_id, concept_id, mastery_score, mastery_percentage, confidence_score, source, evidence_count
            ) VALUES (
                gen_random_uuid(), %s, %s, 0.8, 80.0, 0.8, 'ai', -1
            );
        """, (student_id, concept_id))
    pg_conn.rollback()

    # Test 4: source not in ('ai', 'faculty_override') rejected
    with pytest.raises(CheckViolation):
        cur.execute("""
            INSERT INTO public.student_concept_mastery (
                id, student_id, concept_id, mastery_score, mastery_percentage, confidence_score, source, evidence_count
            ) VALUES (
                gen_random_uuid(), %s, %s, 0.8, 80.0, 0.8, 'invalid_source', 1
            );
        """, (student_id, concept_id))
    pg_conn.rollback()


def test_submission_concept_feedback_constraints(pg_conn):
    cur = pg_conn.cursor()
    cur.execute("SELECT id, student_id FROM public.submissions LIMIT 1;")
    sub_row = cur.fetchone()
    sub_id = sub_row[0]
    student_id = sub_row[1]
    cur.execute("SELECT id FROM public.concepts LIMIT 1;")
    concept_id = cur.fetchone()[0]

    # Test 1: score_ratio > 1.0 rejected
    pg_conn.rollback()
    with pytest.raises(CheckViolation):
        cur.execute("""
            INSERT INTO public.submission_concept_feedback (
                id, submission_id, student_id, concept_id, criterion_id, score_ratio, confidence
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'crit-1', 1.5, 0.8
            );
        """, (sub_id, student_id, concept_id))
    pg_conn.rollback()

    # Test 2: confidence < 0.0 rejected
    with pytest.raises(CheckViolation):
        cur.execute("""
            INSERT INTO public.submission_concept_feedback (
                id, submission_id, student_id, concept_id, criterion_id, score_ratio, confidence
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'crit-1', 0.5, -0.1
            );
        """, (sub_id, student_id, concept_id))
    pg_conn.rollback()

    # Test 3: non-existent evaluation_id foreign key rejected
    fake_eval_id = f"eval-fake-{uuid.uuid4().hex[:6]}"
    with pytest.raises(ForeignKeyViolation):
        cur.execute("""
            INSERT INTO public.submission_concept_feedback (
                id, submission_id, student_id, concept_id, criterion_id, score_ratio, confidence, evaluation_id
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'crit-1', 0.5, 0.8, %s
            );
        """, (sub_id, student_id, concept_id, fake_eval_id))
    pg_conn.rollback()

    # Test 4: unique constraint on (submission_id, concept_id, criterion_id) enforced
    test_crit_id = f"crit-uniq-{uuid.uuid4().hex[:6]}"
    cur.execute("""
        INSERT INTO public.submission_concept_feedback (
            id, submission_id, student_id, concept_id, criterion_id, score_ratio, confidence
        ) VALUES (
            gen_random_uuid(), %s, %s, %s, %s, 0.8, 0.85
        );
    """, (sub_id, student_id, concept_id, test_crit_id))
    
    with pytest.raises(UniqueViolation):
        cur.execute("""
            INSERT INTO public.submission_concept_feedback (
                id, submission_id, student_id, concept_id, criterion_id, score_ratio, confidence
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, 0.8, 0.85
            );
        """, (sub_id, student_id, concept_id, test_crit_id))
    pg_conn.rollback()
