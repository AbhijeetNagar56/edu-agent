export type JobStatus = 'pending' | 'processing' | 'done' | 'failed' | 'flagged' | 'manual_review';

export interface RubricCriterion {
  id: string;
  title: string;
  description: string;
  maxPoints: number;
  weightPercent?: number;
}

export interface Rubric {
  id: string;
  courseCode: string;
  assignmentTitle: string;
  description: string;
  criteria: RubricCriterion[];
  totalPoints: number;
  createdAt: string;
}

export interface CriterionEvaluation {
  criterionId: string;
  title: string;
  scoreAwarded: number;
  maxPoints: number;
  scoreRatio?: number;
  evidence?: string;
  reasoning?: string;
  feedback: string;
  strengths?: string;
  improvements?: string;
}

export interface ConceptFeedback {
  conceptId: string;
  conceptName?: string;
  scoreRatio: number;
  evidenceCount: number;
  masteryContribution: number;
  confidenceScore: number;
  feedback: string;
  strengths?: string[];
  improvements?: string[];
}

export interface EvaluationResult {
  score: number;
  maxScore: number;
  percentage: number;
  criteriaScores: CriterionEvaluation[];
  conceptFeedback?: ConceptFeedback[];
  summaryFeedback: string;
  strengths: string[];
  improvements: string[];
  aiModelExtraction: string;
  aiModelGrading: string;
  evaluatedAt: string;
}

export interface FacultyOverride {
  isOverridden: boolean;
  originalScore: number;
  overriddenScore: number;
  overriddenBy: string;
  overriddenById?: string;
  overriddenByName?: string;
  overrideReason: string;
  overriddenAt: string;
  criterionAdjustments?: Record<string, number>;
}

export interface Submission {
  id: string;
  studentId: string;
  studentName: string;
  studentEmail: string;
  assignmentId: string;
  assignmentTitle: string;
  courseCode: string;
  fileName: string;
  fileSize: string;
  fileType: 'pdf' | 'markdown' | 'text';
  contentPreview?: string;
  status: JobStatus;
  submittedAt: string;
  rubricId: string;
  evaluation?: EvaluationResult;
  override?: FacultyOverride;
  processingStep?: 'queued' | 'extracting' | 'grading' | 'synced';
}

export type ConceptDifficulty = 'beginner' | 'intermediate' | 'advanced';

export interface Concept {
  id: string;
  courseId: string;
  name: string;
  description: string;
  category: string;
  difficulty: ConceptDifficulty;
  posX: number;
  posY: number;
  createdAt: string;
  // Student mastery overlay fields
  masteryScore?: number;
  masteryPercentage?: number;
  confidence?: number;
  masterySource?: string;
}

export interface ConceptEdge {
  id: string;
  courseId: string;
  fromConcept: string;
  toConcept: string;
  createdAt: string;
}

export interface CurriculumGraph {
  courseId: string;
  courseCode: string;
  courseName: string;
  courseDescription: string;
  concepts: Concept[];
  edges: ConceptEdge[];
}

export interface Course {
  id: string;
  code: string;
  name: string;
  description?: string;
  facultyId?: string;
  createdAt?: string;
  updatedAt?: string;
  conceptsCount?: number;
  assignmentsCount?: number;
  instructor?: string;
  assignments: {
    id: string;
    title: string;
    dueDate: string;
    rubricId: string;
  }[];
}


export type AssignmentStatus = 'draft' | 'published' | 'archived';

export interface CriterionConceptMap {
  criterionId: string;
  conceptId: string;
  conceptName?: string;
}

export interface Assignment {
  id: string;
  courseId: string;
  title: string;
  description: string;
  dueDate: string;
  maxPoints: number;
  status: AssignmentStatus;
  rubricId?: string;
  createdBy?: string;
  createdAt: string;
  updatedAt?: string;
  conceptIds: string[];
  concepts: Concept[];
  criterionConcepts: CriterionConceptMap[];
  submissionsCount?: number;
}

export interface AssignmentCreate {
  title: string;
  description?: string;
  dueDate: string;
  maxPoints?: number;
  status?: AssignmentStatus;
  rubricId?: string;
  conceptIds?: string[];
  criterionConcepts?: CriterionConceptMap[];
}

export interface AssignmentUpdate {
  title?: string;
  description?: string;
  dueDate?: string;
  maxPoints?: number;
  status?: AssignmentStatus;
  rubricId?: string;
  conceptIds?: string[];
  criterionConcepts?: CriterionConceptMap[];
}

export interface StudentAssignment {
  id: string;
  courseId: string;
  courseCode: string;
  courseName: string;
  title: string;
  description: string;
  dueDate: string;
  maxPoints: number;
  status: AssignmentStatus;
  rubricId?: string;
  rubric?: Rubric;
  concepts: Concept[];
  criterionConcepts: CriterionConceptMap[];
  submissionStatus: 'unsubmitted' | 'pending' | 'processing' | 'graded' | 'flagged';
  submissionId?: string;
  submittedAt?: string;
  score?: number;
}

// =============================================================================
// DAY 5: INDIVIDUALIZED STUDENT KNOWLEDGE GRAPH TYPES
// =============================================================================

export type StudentConceptStatus = 'unassessed' | 'low_mastery' | 'developing' | 'strong' | 'high';

export interface EvidenceHistoryItem {
  submissionId: string;
  assignmentId?: string;
  assignmentTitle?: string;
  criterionId: string;
  scoreRatio: number;
  confidence: number;
  feedbackText: string;
  evidence: string;
  evaluatedAt?: string;
  source: string;
  facultyOverride?: Record<string, any>;
}

export interface ConceptFeedbackSummary {
  recentFeedback?: string;
  evidenceExcerpts: string[];
  relatedCriterionIds: string[];
  associatedAssignmentIds: string[];
  associatedAssignments: {
    id: string;
    title: string;
    dueDate?: string;
  }[];
  history: EvidenceHistoryItem[];
}

export interface StudentCurriculumConcept {
  id: string;
  conceptId?: string;
  name: string;
  description: string;
  category: string;
  difficulty: ConceptDifficulty;
  posX: number;
  posY: number;
  masteryScore?: number | null;
  masteryPercentage?: number | null;
  confidenceScore?: number | null;
  confidence?: number | null;
  evidenceCount: number;
  masterySource: string;
  lastEvaluatedAt?: string | null;
  status: StudentConceptStatus;
  feedback: ConceptFeedbackSummary;
}

export interface StudentPrerequisiteEdge {
  id: string;
  fromConcept: string;
  toConcept: string;
  sourceConceptId?: string;
  targetConceptId?: string;
}

export interface StudentCurriculumGraph {
  courseId: string;
  courseCode: string;
  courseName: string;
  courseDescription: string;
  studentId: string;
  studentName: string;
  studentEmail: string;
  concepts: StudentCurriculumConcept[];
  edges: StudentPrerequisiteEdge[];
}

export interface EnrolledStudentSummary {
  studentId: string;
  studentName: string;
  studentEmail: string;
  enrolledAt?: string;
  totalAssessedConcepts: number;
  totalConcepts: number;
  averageMastery: number;
}


export interface CourseOverviewAnalytics {
  courseId: string;
  courseCode: string;
  courseName: string;
  totalEnrolled: number;
  totalAssignments: number;
  publishedAssignments: number;
  draftAssignments: number;
  totalSubmissions: number;
  completedEvaluations: number;
  pendingEvaluations: number;
  manualReviewSubmissions: number;
  averageAssignmentScore: number;
  conceptCoveragePercentage: number;
}

export interface StudentProgressSummary {
  studentId: string;
  studentName: string;
  studentEmail: string;
  totalConcepts: number;
  assessedConcepts: number;
  coveragePercentage: number;
  averageMastery: number;
  lowMasteryCount: number;
  developingCount: number;
  strongCount: number;
  unassessedCount: number;
}

export interface ConceptAnalyticsSummary {
  conceptId: string;
  name: string;
  category: string;
  difficulty: ConceptDifficulty;
  assessedStudentsCount: number;
  unassessedStudentsCount: number;
  averageMastery: number;
  lowMasteryCount: number;
  developingCount: number;
  strongHighCount: number;
  needsAttention: boolean;
  attentionReason?: string | null;
}

export interface AssignmentAnalyticsSummary {
  assignmentId: string;
  title: string;
  dueDate?: string | null;
  maxMarks: number;
  status: string;
  submissionCount: number;
  completionRate: number;
  averageScore: number;
  scoreDistribution: Record<string, number>;
  manualReviewCount: number;
}

export interface CourseLearningAnalytics {
  overview: CourseOverviewAnalytics;
  studentProgress: StudentProgressSummary[];
  conceptAnalytics: ConceptAnalyticsSummary[];
  assignmentAnalytics: AssignmentAnalyticsSummary[];
}

export interface ConceptMasteryOverridePayload {
  masteryScore: number;
  confidenceScore?: number;
  overrideReason: string;
}
