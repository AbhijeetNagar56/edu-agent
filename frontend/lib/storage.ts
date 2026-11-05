'use client';

import { api } from './api';
import { supabase } from './supabase';
import {
  Course,
  FacultyOverride,
  Rubric,
  Submission,
  Concept,
  ConceptEdge,
  CurriculumGraph,
  Assignment,
  AssignmentCreate,
  AssignmentUpdate,
  StudentAssignment,
  StudentCurriculumGraph,
  EnrolledStudentSummary,
  CourseLearningAnalytics,
  ConceptMasteryOverridePayload,
} from './types';

type Envelope<T> = { success: boolean; data: T; meta?: Record<string, number> };
type Listener = (submissions: Submission[]) => void;
const listeners = new Set<Listener>();
let submissionsCache: Submission[] = [];
let rubricsCache: Rubric[] = [];
let coursesCache: Course[] = [];
let currentQuery: { faculty?: boolean } = {};
let realtimeStarted = false;

function publish(submissions: Submission[]) {
  submissionsCache = submissions;
  listeners.forEach((listener) => listener(submissions));
}

export function subscribeToSubmissions(listener: Listener) {
  listeners.add(listener);
  if (!realtimeStarted && supabase) {
    realtimeStarted = true;
    supabase.channel('eduagents-submissions')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'submissions' }, () => {
        void refreshSubmissions(currentQuery).catch((error) => console.error('Realtime refresh failed:', error));
      }).subscribe();
  }
  return () => listeners.delete(listener);
}

export function getCourses() { return coursesCache; }
export function getRubrics() { return rubricsCache; }
export function getSubmissions() { return submissionsCache; }

export async function refreshRubrics(courseCode?: string) {
  const query = courseCode ? `?course_code=${encodeURIComponent(courseCode)}` : '';
  const result = await api<Envelope<Rubric[]>>(`/api/v1/faculty/rubrics${query}`);
  rubricsCache = result.data || [];
  const groups = new Map<string, Rubric[]>();
  for (const rubric of rubricsCache) groups.set(rubric.courseCode, [...(groups.get(rubric.courseCode) || []), rubric]);
  coursesCache = [...groups].map(([code, items]) => ({
    id: code,
    code,
    name: code,
    instructor: '',
    assignments: items.map((r) => ({ id: r.id, title: r.assignmentTitle, dueDate: '', rubricId: r.id })),
  }));
  return rubricsCache;
}

export async function refreshSubmissions(options: { faculty?: boolean; courseCode?: string; status?: string; search?: string; assignmentId?: string } = {}) {
  currentQuery = options;
  const params = new URLSearchParams({ limit: '100' });
  if (options.courseCode && options.courseCode !== 'ALL') params.set('course_code', options.courseCode);
  if (options.status && options.status !== 'ALL') params.set('status', options.status);
  if (options.assignmentId && options.assignmentId !== 'ALL') params.set('assignment_id', options.assignmentId);
  if (options.search) params.set('search', options.search);
  const path = options.faculty ? '/api/v1/faculty/submissions' : '/api/v1/submissions';
  const result = await api<Envelope<Submission[]>>(`${path}?${params}`);
  publish(result.data || []);
  return submissionsCache;
}

export async function createSubmission(input: { file?: File; textContent?: string; studentId: string; studentName: string; studentEmail: string; assignmentId: string; assignmentTitle: string; courseCode: string; rubricId: string }) {
  const body = new FormData();
  if (input.file) body.set('file', input.file);
  if (input.textContent) body.set('text_content', input.textContent);
  body.set('student_id', input.studentId);
  body.set('student_name', input.studentName);
  body.set('student_email', input.studentEmail);
  body.set('assignment_id', input.assignmentId);
  body.set('assignment_title', input.assignmentTitle);
  body.set('course_code', input.courseCode);
  body.set('rubric_id', input.rubricId);
  const result = await api<Envelope<Submission>>('/api/v1/submissions', { method: 'POST', body });
  publish([result.data, ...submissionsCache.filter((s) => s.id !== result.data.id)]);
  return result.data;
}

export async function saveRubric(rubric: Rubric) {
  const payload = {
    courseCode: rubric.courseCode,
    assignmentTitle: rubric.assignmentTitle,
    description: rubric.description,
    totalPoints: rubric.totalPoints,
    criteria: rubric.criteria.map(({ id, title, description, maxPoints, weightPercent }) => ({ id, title, description, maxPoints, weightPercent })),
  };
  const result = rubricCacheHas(rubric.id)
    ? await api<Envelope<Rubric>>(`/api/v1/faculty/rubrics/${encodeURIComponent(rubric.id)}`, { method: 'PUT', body: JSON.stringify(payload) })
    : await api<Envelope<Rubric>>('/api/v1/faculty/rubrics', { method: 'POST', body: JSON.stringify(payload) });
  await refreshRubrics();
  return result.data;
}

function rubricCacheHas(id: string) { return rubricsCache.some((item) => item.id === id); }

export async function deleteRubric(id: string) {
  await api(`/api/v1/faculty/rubrics/${encodeURIComponent(id)}`, { method: 'DELETE' });
  await refreshRubrics();
}

export async function overrideGrade(submissionId: string, override: FacultyOverride) {
  await api(`/api/v1/faculty/submissions/${encodeURIComponent(submissionId)}/override`, {
    method: 'POST',
    body: JSON.stringify({ overriddenScore: override.overriddenScore, overriddenBy: override.overriddenBy, overrideReason: override.overrideReason, criterionAdjustments: override.criterionAdjustments }),
  });
  const updated = (await api<Envelope<Submission>>(`/api/v1/submissions/${encodeURIComponent(submissionId)}`)).data;
  publish(submissionsCache.map((s) => s.id === updated.id ? updated : s));
  return updated;
}

export async function fetchFacultyCourses(): Promise<Course[]> {
  const result = await api<Envelope<Course[]>>('/api/v1/faculty/courses');
  return (result.data || []).map((c) => ({
    ...c,
    assignments: c.assignments || [],
  }));
}

export async function createFacultyCourse(data: { code: string; name: string; description?: string }): Promise<Course> {
  const result = await api<Envelope<Course>>('/api/v1/faculty/courses', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return result.data;
}

export async function fetchCourseDetails(courseId: string): Promise<Course> {
  const result = await api<Envelope<Course>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}`);
  return result.data;
}

export async function fetchCurriculumGraph(courseId: string): Promise<CurriculumGraph> {
  const result = await api<Envelope<CurriculumGraph>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/curriculum`);
  return result.data;
}

export async function saveCurriculumLayout(
  courseId: string,
  payload: {
    positions?: { id: string; posX: number; posY: number }[];
    edges?: { fromConcept: string; toConcept: string }[];
  }
): Promise<CurriculumGraph> {
  const result = await api<Envelope<CurriculumGraph>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/curriculum`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
  return result.data;
}

export async function createConcept(
  courseId: string,
  concept: {
    name: string;
    description?: string;
    category?: string;
    difficulty?: string;
    posX?: number;
    posY?: number;
  }
): Promise<Concept> {
  const result = await api<Envelope<Concept>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/concepts`, {
    method: 'POST',
    body: JSON.stringify(concept),
  });
  return result.data;
}

export async function updateConcept(
  courseId: string,
  conceptId: string,
  update: Partial<Concept>
): Promise<Concept> {
  const result = await api<Envelope<Concept>>(
    `/api/v1/faculty/courses/${encodeURIComponent(courseId)}/concepts/${encodeURIComponent(conceptId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(update),
    }
  );
  return result.data;
}

export async function deleteConcept(courseId: string, conceptId: string): Promise<void> {
  await api(
    `/api/v1/faculty/courses/${encodeURIComponent(courseId)}/concepts/${encodeURIComponent(conceptId)}`,
    { method: 'DELETE' }
  );
}

export async function createConceptEdge(
  courseId: string,
  fromConcept: string,
  toConcept: string
): Promise<ConceptEdge> {
  const result = await api<Envelope<ConceptEdge>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/edges`, {
    method: 'POST',
    body: JSON.stringify({ fromConcept, toConcept }),
  });
  return result.data;
}

export async function deleteConceptEdge(courseId: string, edgeId: string): Promise<void> {
  await api(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/edges/${encodeURIComponent(edgeId)}`, {
    method: 'DELETE',
  });
}


export async function fetchCourseAssignments(courseId: string, status?: string): Promise<Assignment[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  const result = await api<Envelope<Assignment[]>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/assignments${query}`);
  return result.data || [];
}

export async function fetchAssignmentDetails(assignmentId: string): Promise<Assignment> {
  const result = await api<Envelope<Assignment>>(`/api/v1/faculty/assignments/${encodeURIComponent(assignmentId)}`);
  return result.data;
}

export async function createCourseAssignment(courseId: string, payload: AssignmentCreate): Promise<Assignment> {
  const result = await api<Envelope<Assignment>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/assignments`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return result.data;
}

export async function updateCourseAssignment(assignmentId: string, payload: AssignmentUpdate): Promise<Assignment> {
  const result = await api<Envelope<Assignment>>(`/api/v1/faculty/assignments/${encodeURIComponent(assignmentId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
  return result.data;
}

export async function deleteCourseAssignment(assignmentId: string): Promise<void> {
  await api(`/api/v1/faculty/assignments/${encodeURIComponent(assignmentId)}`, {
    method: 'DELETE',
  });
}

export async function fetchStudentAssignments(courseId?: string): Promise<StudentAssignment[]> {
  const query = courseId ? `?course_id=${encodeURIComponent(courseId)}` : '';
  const result = await api<Envelope<StudentAssignment[]>>(`/api/v1/students/assignments${query}`);
  return result.data || [];
}

export async function fetchStudentAssignmentDetails(assignmentId: string): Promise<StudentAssignment> {
  const result = await api<Envelope<StudentAssignment>>(`/api/v1/students/assignments/${encodeURIComponent(assignmentId)}`);
  return result.data;
}

export async function fetchStudentCurriculumGraph(courseId: string, studentId?: string): Promise<StudentCurriculumGraph> {
  const query = studentId ? `?student_id=${encodeURIComponent(studentId)}` : '';
  const result = await api<Envelope<StudentCurriculumGraph>>(`/api/v1/students/courses/${encodeURIComponent(courseId)}/curriculum${query}`);
  return result.data;
}

export async function fetchCourseEnrolledStudents(courseId: string): Promise<EnrolledStudentSummary[]> {
  const result = await api<Envelope<EnrolledStudentSummary[]>>(`/api/v1/faculty/courses/${encodeURIComponent(courseId)}/students`);
  return result.data || [];
}


export async function removeSubmissionOverride(
  submissionId: string,
  reason?: string
): Promise<{ submissionId: string; finalScore: number; isOverridden: boolean }> {
  const query = reason ? `?reason=${encodeURIComponent(reason)}` : '';
  const result = await api<Envelope<{ submissionId: string; finalScore: number; isOverridden: boolean }>>(
    `/api/v1/faculty/submissions/${encodeURIComponent(submissionId)}/override${query}`,
    { method: 'DELETE' }
  );
  // Update local cache
  const current = submissionsCache.find((s) => s.id === submissionId);
  if (current) {
    if (current.override) {
      current.override.isOverridden = false;
      current.override.overriddenScore = current.evaluation?.score ?? 0;
    }
    publish([...submissionsCache]);
  }
  return result.data;
}

export async function fetchCourseAnalytics(courseId: string): Promise<CourseLearningAnalytics> {
  const result = await api<Envelope<CourseLearningAnalytics>>(
    `/api/v1/faculty/courses/${encodeURIComponent(courseId)}/analytics`
  );
  return result.data;
}

export async function overrideConceptMastery(
  courseId: string,
  studentId: string,
  conceptId: string,
  payload: ConceptMasteryOverridePayload
): Promise<any> {
  const result = await api<Envelope<any>>(
    `/api/v1/faculty/courses/${encodeURIComponent(courseId)}/students/${encodeURIComponent(studentId)}/concepts/${encodeURIComponent(conceptId)}/override`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
  return result.data;
}

export async function removeConceptMasteryOverride(
  courseId: string,
  studentId: string,
  conceptId: string,
  reason?: string
): Promise<any> {
  const query = reason ? `?reason=${encodeURIComponent(reason)}` : '';
  const result = await api<Envelope<any>>(
    `/api/v1/faculty/courses/${encodeURIComponent(courseId)}/students/${encodeURIComponent(studentId)}/concepts/${encodeURIComponent(conceptId)}/override${query}`,
    { method: 'DELETE' }
  );
  return result.data;
}
