'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Plus,
  Edit2,
  Trash2,
  Eye,
  Calendar,
  Award,
  BookOpen,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
  AlertCircle,
  FileText,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import {
  Assignment,
  Concept,
  Course,
  Rubric,
} from '@/lib/types';
import {
  fetchCourseDetails,
  fetchCourseAssignments,
  fetchCurriculumGraph,
  getRubrics,
  refreshRubrics,
  deleteCourseAssignment,
  updateCourseAssignment,
} from '@/lib/storage';
import { AssignmentEditorModal } from '@/components/AssignmentEditorModal';

export default function FacultyCourseAssignmentsPage() {
  const params = useParams();
  const router = useRouter();
  const courseId = params?.courseId as string;

  const [course, setCourse] = useState<Course | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [editingAssignment, setEditingAssignment] = useState<Assignment | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = async () => {
    if (!courseId) return;
    try {
      setIsLoading(true);
      const [courseData, assignsData, graphData] = await Promise.all([
        fetchCourseDetails(courseId),
        fetchCourseAssignments(courseId),
        fetchCurriculumGraph(courseId),
        refreshRubrics(),
      ]);
      setCourse(courseData);
      setAssignments(assignsData);
      setConcepts(graphData.concepts || []);
      setRubrics(getRubrics());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load course assignments.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [courseId]);

  const handleOpenCreate = () => {
    setEditingAssignment(null);
    setIsEditorOpen(true);
  };

  const handleOpenEdit = (assign: Assignment) => {
    setEditingAssignment(assign);
    setIsEditorOpen(true);
  };

  const handleToggleStatus = async (assign: Assignment) => {
    const nextStatus = assign.status === 'published' ? 'draft' : 'published';
    try {
      const updated = await updateCourseAssignment(assign.id, { status: nextStatus });
      setAssignments((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Could not toggle assignment status.');
    }
  };

  const handleDelete = async (assignId: string, title: string) => {
    if (
      confirm(
        `Are you sure you want to delete assignment "${title}"? All concept mappings and submissions linked to it will be affected.`
      )
    ) {
      try {
        await deleteCourseAssignment(assignId);
        setAssignments((prev) => prev.filter((a) => a.id !== assignId));
      } catch (err) {
        alert(err instanceof Error ? err.message : 'Could not delete assignment.');
      }
    }
  };

  const handleSaved = (saved: Assignment) => {
    setAssignments((prev) => {
      const exists = prev.some((a) => a.id === saved.id);
      if (exists) {
        return prev.map((a) => (a.id === saved.id ? saved : a));
      }
      return [saved, ...prev];
    });
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Clock className="w-4 h-4 animate-spin text-blue-600" />
          <span>Loading course assignments...</span>
        </div>
      </div>
    );
  }

  if (error || !course) {
    return (
      <div className="max-w-4xl mx-auto p-8 space-y-4">
        <Link
          href="/faculty"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Faculty Dashboard</span>
        </Link>
        <div className="p-6 rounded-2xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300">
          <h2 className="font-bold text-base mb-1">Could not load assignments</h2>
          <p className="text-xs">{error || 'Course not found.'}</p>
        </div>
      </div>
    );
  }

  const publishedCount = assignments.filter((a) => a.status === 'published').length;
  const draftCount = assignments.filter((a) => a.status === 'draft').length;
  const totalMaxMarks = assignments.reduce((sum, a) => sum + (a.maxPoints || 0), 0);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header & Breadcrumb */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Link
              href="/faculty"
              className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Dashboard</span>
            </Link>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <Link
              href={`/faculty/courses/${course.id}/curriculum`}
              className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 transition"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Curriculum Graph</span>
            </Link>
          </div>

          <div className="flex items-center gap-2.5">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
              {course.code}
            </span>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
              Course Assignments
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-xl">
            {course.name} — Manage assignment prompts, bind rubrics, and map individual rubric criteria to canonical curriculum concepts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href={`/faculty/courses/${course.id}/curriculum`}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition"
          >
            <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
            <span>Open Curriculum Builder ({concepts.length})</span>
          </Link>

          <button
            onClick={handleOpenCreate}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create Assignment</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Total Assignments
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {assignments.length}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Configured for {course.code}</div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
          <div className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
            Published
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {publishedCount}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Visible in Student Portal</div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
          <div className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider">
            Drafts
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {draftCount}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Hidden from students</div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
          <div className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
            Curriculum Concepts
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {concepts.length}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">In course DAG</div>
        </div>
      </div>

      {/* Assignment List */}
      <div className="space-y-4">
        {assignments.length === 0 ? (
          <div className="p-12 text-center rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900/40 space-y-3">
            <div className="size-12 mx-auto rounded-full bg-blue-50 dark:bg-blue-950 flex items-center justify-center text-blue-600">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              No assignments created yet
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Create assignments and map them to canonical concepts so students can submit work and receive AI evaluations.
            </p>
            <button
              onClick={handleOpenCreate}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create First Assignment</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {assignments.map((assign) => {
              const matchedRubric = rubrics.find((r) => r.id === assign.rubricId);
              const isPublished = assign.status === 'published';

              return (
                <div
                  key={assign.id}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs hover:shadow-md transition space-y-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            isPublished
                              ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                              : 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                          }`}
                        >
                          {assign.status}
                        </span>
                        <h2 className="text-base font-bold text-slate-900 dark:text-white">
                          {assign.title}
                        </h2>
                      </div>
                      {assign.description && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                          {assign.description}
                        </p>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleToggleStatus(assign)}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition ${
                          isPublished
                            ? 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
                            : 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                        }`}
                        title={isPublished ? 'Unpublish to draft' : 'Publish to students'}
                      >
                        {isPublished ? (
                          <>
                            <ToggleRight className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Unpublish</span>
                          </>
                        ) : (
                          <>
                            <ToggleLeft className="w-3.5 h-3.5 text-amber-600" />
                            <span>Publish</span>
                          </>
                        )}
                      </button>

                      <button
                        onClick={() => handleOpenEdit(assign)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/50 transition"
                        title="Edit Assignment"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => handleDelete(assign.id, assign.title)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/50 transition"
                        title="Delete Assignment"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Metadata Chips */}
                  <div className="flex flex-wrap items-center gap-3 pt-2 text-xs text-slate-500 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800">
                    <div className="flex items-center gap-1.5 font-medium">
                      <Calendar className="w-3.5 h-3.5 text-blue-600" />
                      <span>Due: {new Date(assign.dueDate).toLocaleDateString()}</span>
                    </div>

                    <div className="flex items-center gap-1.5 font-medium">
                      <Award className="w-3.5 h-3.5 text-amber-600" />
                      <span>{assign.maxPoints} Maximum Marks</span>
                    </div>

                    <div className="flex items-center gap-1.5 font-medium">
                      <Layers className="w-3.5 h-3.5 text-purple-600" />
                      <span>
                        Rubric: {matchedRubric ? matchedRubric.assignmentTitle : 'None'}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>{assign.submissionsCount ?? 0} Submissions</span>
                    </div>
                  </div>

                  {/* Targeted Concepts & Criterion Mapping */}
                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-2">
                    <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                      <BookOpen className="w-3 h-3 text-indigo-600" />
                      <span>Targeted Curriculum Concepts ({assign.conceptIds?.length || 0}):</span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5">
                      {assign.concepts && assign.concepts.length > 0 ? (
                        assign.concepts.map((concept) => (
                          <span
                            key={concept.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800"
                          >
                            <span>{concept.name}</span>
                            {concept.difficulty && (
                              <span className="text-[9px] opacity-70">({concept.difficulty})</span>
                            )}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-slate-400 italic">
                          No concepts explicitly mapped yet. Click Edit to map concepts.
                        </span>
                      )}
                    </div>

                    {/* Criteria Concepts Mapping */}
                    {assign.criterionConcepts && assign.criterionConcepts.length > 0 && (
                      <div className="pt-2">
                        <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5 mb-1.5">
                          <Sparkles className="w-3 h-3 text-emerald-600" />
                          <span>Criterion-Level Mappings:</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {assign.criterionConcepts.map((cc) => (
                            <div
                              key={cc.criterionId}
                              className="px-2.5 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs flex items-center justify-between"
                            >
                              <span className="font-mono text-[10px] text-slate-500">
                                {cc.criterionId}
                              </span>
                              <span className="font-medium text-emerald-700 dark:text-emerald-300">
                                → {cc.conceptName || cc.conceptId}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Assignment Editor Modal */}
      <AssignmentEditorModal
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        onSave={handleSaved}
        courseId={course.id}
        courseCode={course.code}
        concepts={concepts}
        rubrics={rubrics}
        assignment={editingAssignment}
      />
    </div>
  );
}
