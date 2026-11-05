# EduAgents: Concept Mastery Engine Design

## 1. Overview and Core Principles

The central differentiator of EduAgents is the student knowledge graph, which visualizes concept-level mastery rather than merely reporting assignment grades.

### Core Axioms
1. **Assignment Grades $\neq$ Concept Mastery**: A student achieving 90% on an assignment does not automatically have 0.90 mastery on all associated concepts. An assignment represents a single sample of evidence within a specific context.
2. **Normalized Value Range**: Mastery score ($M$) and confidence score ($c$) are strictly normalized real numbers within $[0.0, 1.0]$.
3. **Canonical Shared DAG**: The curriculum graph (concepts and prerequisite edges) belongs to the course and is shared across all students. Mastery is individual to each student and must **never** duplicate the graph topology.
4. **No Prerequisite Cascade in Day 4**: In Day 4, mastery is updated strictly for concepts directly evaluated in the assignment. Prerequisite propagation and decay belong to Day 5.
5. **Faculty Override Precedence**: An authoritative faculty evaluation always takes precedence over AI-generated mastery. AI updates must never overwrite an active faculty override.
6. **Deterministic Idempotency**: Reprocessing an existing submission evaluation must not duplicate evidence or artificially inflate mastery or confidence.

---

## 2. Mathematical Formulation

### 2.1 Evidence Extraction from Assignment Rubric Criteria
Let assignment $A$ contain rubric criteria $\{k_1, k_2, \dots, k_n\}$.
Let authoritative mapping table `assignment_criterion_concepts` associate criteria with concept $C$:
$$K_C = \{ k \in \text{criteria} \mid (A, k, C) \in \text{assignment\_criterion\_concepts} \}$$

For each criterion $k \in K_C$, Gemini produces an awarded score $s_k \in [0, \text{max}_k]$.
The criterion score ratio is:
$$r_k = \frac{s_k}{\text{max}_k} \quad (\text{if } \text{max}_k > 0, \text{ else } 0.0)$$

The composite assignment evidence score $E \in [0.0, 1.0]$ for concept $C$ from this submission is the point-weighted average across all criteria mapped to $C$:
$$E = \frac{\sum_{k \in K_C} s_k}{\sum_{k \in K_C} \text{max}_k} \quad (\text{if } \sum \text{max}_k > 0, \text{ else } 0.0)$$

### 2.2 Evidence Confidence
The confidence $c_{\text{new}} \in [0.5, 0.95]$ of the new evidence is determined by the scope and evidence quality of the evaluation:
- Base confidence: $c_{\text{base}} = 0.70$
- Evidence bonus: $+0.10$ if direct verbatim textual/code evidence is cited in `evidence_from_submission`.
- Point weight scaling: scaled by points up to $+0.05$.
- Default AI evaluation confidence: $c_{\text{new}} = 0.80$.
- Faculty override confidence: $c_{\text{override}} = 1.00$.

### 2.3 Mastery Aggregation Model
Let a student have prior mastery state $(M_{\text{prior}}, c_{\text{prior}}, N)$, where:
- $M_{\text{prior}} \in [0.0, 1.0]$ is the current mastery score.
- $c_{\text{prior}} \in [0.0, 1.0]$ is the current confidence.
- $N \ge 0$ is the count of distinct historical submissions providing evidence for concept $C$.

#### Case 1: Initial Evidence ($N = 0$)
When no prior evidence exists for concept $C$, we avoid instantly leaping to the raw assignment score by anchoring against a neutral prior $M_0 = 0.50$ with prior weight $w_0 = 1.0$:
$$M_{\text{new}} = \frac{M_0 \cdot w_0 + E \cdot c_{\text{new}}}{w_0 + c_{\text{new}}}$$
$$c_{\text{updated}} = \min(0.95, c_{\text{new}} \times 0.85)$$
$$N_{\text{updated}} = 1$$

*Example*: If a student gets $100\%$ ($E = 1.0$) on their first assignment for a concept:
$$M_{\text{new}} = \frac{0.50 \cdot 1.0 + 1.0 \cdot 0.80}{1.0 + 0.80} = \frac{1.30}{1.80} \approx 0.7222$$
The student demonstrates good initial capability, but does not claim complete 1.0 mastery on a single submission.

#### Case 2: Subsequent Evidence ($N \ge 1$)
When subsequent independent evidence arrives, the prior mastery is weighted by prior evidence and confidence, while the new evidence is weighted by $c_{\text{new}}$:
$$W_{\text{prior}} = \min(4.0, N \cdot c_{\text{prior}})$$
$$W_{\text{new}} = c_{\text{new}}$$
$$M_{\text{new}} = \frac{M_{\text{prior}} \cdot W_{\text{prior}} + E \cdot W_{\text{new}}}{W_{\text{prior}} + W_{\text{new}}}$$

Confidence increases asymptotically towards $1.0$:
$$c_{\text{updated}} = \min\left(0.99, c_{\text{prior}} + (1.0 - c_{\text{prior}}) \times 0.20\right)$$
$$N_{\text{updated}} = N + 1$$

*Example*: A student with $M_{\text{prior}} = 0.7222$, $c_{\text{prior}} = 0.68$, $N = 1$ submits a second assignment and scores $90\%$ ($E = 0.90$):
$$W_{\text{prior}} = 1 \cdot 0.68 = 0.68$$
$$W_{\text{new}} = 0.80$$
$$M_{\text{new}} = \frac{0.7222 \cdot 0.68 + 0.90 \cdot 0.80}{0.68 + 0.80} = \frac{0.4911 + 0.7200}{1.48} = \frac{1.2111}{1.48} \approx 0.8183$$
$$c_{\text{updated}} = 0.68 + (1.0 - 0.68) \times 0.20 = 0.744$$
$$N_{\text{updated}} = 2$$

---

## 3. Faculty Override Precedence

Faculty members have ultimate pedagogical authority. When a faculty member overrides an assignment score:
1. `public.faculty_overrides` stores the override details (`overridden_score`, `overridden_by`, `criterion_adjustments`).
2. If criterion adjustments are provided, concept evidence scores are re-computed using the faculty's adjusted criterion scores.
3. The mastery record is updated with:
   - `source = 'faculty_override'`
   - `confidence_score = 1.0`
   - `mastery_score = M_{\text{override}}`
4. **AI Protection Rule**: When an AI evaluation job runs (e.g. background batch or retry), the engine checks whether an active faculty override exists on the submission or whether `student_concept_mastery.source == 'faculty_override'`. If active, the AI engine **must not** overwrite the mastery record. It records the AI concept feedback but preserves the faculty-designated mastery score.

---

## 4. Deterministic Idempotency

To ensure that job retries or repeated cron executions never duplicate evidence counts or skew mastery:
1. `public.submission_concept_feedback` maintains a unique constraint on `(submission_id, concept_id, criterion_id)`.
2. Upserting feedback for an already-evaluated submission updates the existing evidence record in place without generating new rows.
3. Before incrementing $N$, the engine verifies whether `submission_id` has already contributed to concept $C$:
   - If `last_evidence_submission_id == submission_id`, the existing record is updated in place, keeping $N$ constant.
   - If `last_evidence_submission_id != submission_id`, $N$ is incremented ($N \leftarrow N + 1$).

---

## 5. Boundary Protection & Precision

- Every calculated score is clamped:
  $$M = \min(1.0, \max(0.0, M))$$
  $$c = \min(1.0, \max(0.0, c))$$
- Both are rounded to 4 decimal places matching the PostgreSQL schema `NUMERIC(5, 4)` and check constraints `CHECK (mastery_score >= 0.0 AND mastery_score <= 1.0)`.
- Percentage representations are strictly computed as $\text{round}(M \times 100.0, 2)$.

---

## 6. Known Limitations in Day 4 Scope

- Prerequisite propagation (Bayesian belief network propagation up/down DAG edges) is deferred to Day 5.
- Time-based memory decay (Ebbinghaus forgetting curve) is deferred to Day 5.
- Day 4 focuses on rock-solid, explainable, and deterministic criterion-to-concept aggregation.
