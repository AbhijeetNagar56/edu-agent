import json
from typing import Any, Dict, List
from app.models.rubric import Rubric


STAGE_2_SYSTEM_INSTRUCTION = """
You are an expert university computer science grader and pedagogy evaluator.
Evaluate the student submission objectively, rigorously, and independently against each rubric criterion.

Rules:
1. Every rubric criterion MUST be evaluated individually. Never omit any criterion.
2. Award numerical scores strictly within [0, maxPoints] for each criterion.
3. For each criterion, locate and extract factual evidenceFromSubmission (verbatim quotes or code snippets). Do NOT invent, assume, or hallucinate evidence not present in the student document. If evidence is missing, state: "No direct evidence identified in submission".
4. Provide clear pedagogical reasoning explaining the score deduction or award based strictly on the extracted evidence.
5. Provide actionable, constructive feedback tailored to the student's submission.
6. Calculate scoreRatio as scoreAwarded / maxPoints (between 0.0 and 1.0).
7. List 2-3 overall strengths and 1-2 concrete areas for pedagogical growth.
8. TotalScore must equal the exact sum of all criteria scoreAwarded.

Output strictly valid JSON matching the requested schema.
"""


def build_stage_2_prompt(rubric: Rubric, extracted_doc: Dict[str, Any]) -> str:
    criteria_summary = [
        {
            "criterionId": c.id,
            "title": c.title,
            "description": c.description,
            "maxPoints": c.maxPoints,
        }
        for c in rubric.criteria
    ]

    return f"""
Assignment: {rubric.assignmentTitle}
Course: {rubric.courseCode}
Total Points: {rubric.totalPoints}

Rubric Criteria to Evaluate:
{json.dumps(criteria_summary, indent=2)}

Structured Student Document:
{json.dumps(extracted_doc, indent=2)}

Evaluate the student's submission thoroughly and objectively against each rubric criterion.
Output strictly valid JSON in the format:
{{
  "totalScore": 90.0,
  "maxScore": {rubric.totalPoints},
  "summaryFeedback": "Comprehensive evaluation summary...",
  "strengths": ["Strength 1", "Strength 2"],
  "improvements": ["Area for growth 1"],
  "criteriaEvaluations": [
    {{
      "criterionId": "criterion id strictly matching rubric",
      "title": "criterion title",
      "scoreAwarded": 25.0,
      "maxPoints": 30.0,
      "scoreRatio": 0.8333,
      "evidenceFromSubmission": "Exact quote or code excerpt from student document...",
      "reasoning": "Pedagogical justification for points awarded...",
      "feedback": "Actionable guidance...",
      "strengths": "Specific strength for this criterion",
      "improvements": "Specific improvement for this criterion"
    }}
  ]
}}
"""
