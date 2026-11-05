'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  FileText,
  Calendar,
  Award,
  Layers,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Sparkles,
} from 'lucide-react';
import {
  Assignment,
  AssignmentCreate,
  AssignmentStatus,
  AssignmentUpdate,
  Concept,
  CriterionConceptMap,
  Rubric,
} from '@/lib/types';
import { createCourseAssignment, updateCourseAssignment } from '@/lib/storage';

interface AssignmentEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (saved: Assignment) => void;
  courseId: string;
  courseCode: string;
  concepts: Concept[];
  rubrics: Rubric[];
  assignment?: Assignment | null;
}

export function AssignmentEditorModal({
  isOpen,
  onClose,
  onSave,
  courseId,
  courseCode,
  concepts,
  rubrics,
  assignment,
}: AssignmentEditorModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [maxPoints, setMaxPoints] = useState(100);
  const [status, setStatus] = useState<AssignmentStatus>('draft');
  const [rubricId, setRubricId] = useState('');
  const [selectedConceptIds, setSelectedConceptIds] = useState<Set<string>>(new Set());
  const [criterionMap, setCriterionMap] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Course rubrics
  const courseRubrics = rubrics.filter(
    (r) => r.courseCode.toLowerCase() === courseCode.toLowerCase()
  );

  useEffect(() => {
    if (assignment) {
      setTitle(assignment.title);
      setDescription(assignment.description || '');
      // Format ISO string to datetime-local format: YYYY-MM-DDTHH:mm
      try {
        const d = new Date(assignment.dueDate);
        const isoLocal = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
          .toISOString()
          .slice(0, 16);
        setDueDate(isoLocal);
      } catch {
        setDueDate('');
      }
      setMaxPoints(assignment.maxPoints || 100);
      setStatus(assignment.status || 'published');
      setRubricId(assignment.rubricId || '');
      setSelectedConceptIds(new Set(assignment.conceptIds || []));

      const cm: Record<string, string> = {};
      (assignment.criterionConcepts || []).forEach((c) => {
        cm[c.criterionId] = c.conceptId;
      });
      setCriterionMap(cm);
    } else {
      setTitle('');
      setDescription('');
      // Default due date: 14 days from now
      const defaultDate = new Date();
      defaultDate.setDate(defaultDate.getDate() + 14);
      const isoLocal = new Date(defaultDate.getTime() - defaultDate.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16);
      setDueDate(isoLocal);
      setMaxPoints(100);
      setStatus('draft');
      setRubricId(courseRubrics[0]?.id || '');
      setSelectedConceptIds(new Set());
      setCriterionMap({});
    }
    setError('');
  }, [assignment, isOpen, courseCode]);

  if (!isOpen) return null;

  const activeRubric = rubrics.find((r) => r.id === rubricId);

  const toggleConcept = (conceptId: string) => {
    setSelectedConceptIds((prev) => {
      const next = new Set(prev);
      if (next.has(conceptId)) {
        next.delete(conceptId);
        // Also remove any criterion mappings using this concept
        setCriterionMap((prevCm) => {
          const nextCm = { ...prevCm };
          Object.entries(nextCm).forEach(([critId, cId]) => {
            if (cId === conceptId) delete nextCm[critId];
          });
          return nextCm;
        });
      } else {
        next.add(conceptId);
      }
      return next;
    });
  };

  const handleCriterionConceptChange = (criterionId: string, targetConceptId: string) => {
    setCriterionMap((prev) => {
      const next = { ...prev };
      if (!targetConceptId) {
        delete next[criterionId];
      } else {
        next[criterionId] = targetConceptId;
        // Auto-select concept in assignment concepts
        setSelectedConceptIds((prevConcepts) => new Set([...prevConcepts, targetConceptId]));
      }
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!title.trim()) {
      setError('Please provide an assignment title.');
      return;
    }
    if (!dueDate) {
      setError('Please specify a due date and time.');
      return;
    }
    if (maxPoints <= 0) {
      setError('Maximum points must be greater than zero.');
      return;
    }

    setIsSubmitting(true);

    try {
      const criterionConceptsList: CriterionConceptMap[] = Object.entries(criterionMap).map(
        ([critId, cId]) => ({
          criterionId: critId,
          conceptId: cId,
          conceptName: concepts.find((c) => c.id === cId)?.name,
        })
      );

      const allConceptIds = Array.from(selectedConceptIds);

      const dueIso = new Date(dueDate).toISOString();

      if (assignment) {
        const payload: AssignmentUpdate = {
          title: title.trim(),
          description: description.trim(),
          dueDate: dueIso,
          maxPoints: Number(maxPoints),
          status,
          rubricId: rubricId || undefined,
          conceptIds: allConceptIds,
          criterionConcepts: criterionConceptsList,
        };
        const updated = await updateCourseAssignment(assignment.id, payload);
        onSave(updated);
      } else {
        const payload: AssignmentCreate = {
          title: title.trim(),
          description: description.trim(),
          dueDate: dueIso,
          maxPoints: Number(maxPoints),
          status,
          rubricId: rubricId || undefined,
          conceptIds: allConceptIds,
          criterionConcepts: criterionConceptsList,
        };
        const created = await createCourseAssignment(courseId, payload);
        onSave(created);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save assignment.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-3xl my-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-950/40">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300">
                {courseCode}
              </span>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {assignment ? 'Edit Assignment' : 'Create New Assignment'}
              </h2>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Configure assignment parameters, bind grading rubrics, and map curriculum concepts.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Form Content */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Section 1: Core Details */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
              1. Assignment Overview
            </h3>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Assignment Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Assignment 1: Sorting Algorithms & Asymptotic Bounds"
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Instructions / Description
              </label>
              <textarea
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Provide prompt details, expected deliverables, formatting requirements, and code language guidelines..."
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Due Date & Time <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type="datetime-local"
                    required
                    value={dueDate}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Maximum Marks <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  required
                  min={1}
                  step={0.5}
                  value={maxPoints}
                  onChange={(e) => setMaxPoints(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Visibility Status
                </label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as AssignmentStatus)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                >
                  <option value="published">Published (Visible to Students)</option>
                  <option value="draft">Draft (Hidden from Students)</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Associated Rubric */}
          <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Award className="w-3.5 h-3.5 text-blue-600" />
                <span>2. AI Evaluation Rubric</span>
              </h3>
              <span className="text-[11px] text-slate-400">
                {courseRubrics.length} rubrics available for {courseCode}
              </span>
            </div>

            <div>
              <select
                value={rubricId}
                onChange={(e) => {
                  setRubricId(e.target.value);
                  setCriterionMap({});
                }}
                className="w-full px-3.5 py-2.5 text-xs rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500 font-medium"
              >
                <option value="">-- No Rubric Associated --</option>
                {courseRubrics.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.assignmentTitle} ({r.totalPoints} pts, {r.criteria.length} criteria)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Section 3: Targeted Curriculum Concepts */}
          <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
                  <span>3. Targeted Curriculum Concepts</span>
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Select concepts from this course's canonical curriculum graph targeted by this assignment.
                </p>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                {selectedConceptIds.size} Selected
              </span>
            </div>

            {concepts.length === 0 ? (
              <div className="p-4 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-center text-xs text-slate-400">
                No canonical concepts found for this course. Please open the Curriculum Builder first to add concepts.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-h-48 overflow-y-auto p-1">
                {concepts.map((concept) => {
                  const isChecked = selectedConceptIds.has(concept.id);
                  return (
                    <button
                      type="button"
                      key={concept.id}
                      onClick={() => toggleConcept(concept.id)}
                      className={`flex items-start gap-2.5 p-3 rounded-xl border text-left transition ${
                        isChecked
                          ? 'border-indigo-500 bg-indigo-50/60 dark:bg-indigo-950/40 text-slate-900 dark:text-white'
                          : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 text-slate-600 dark:text-slate-400'
                      }`}
                    >
                      <div
                        className={`size-4 mt-0.5 rounded-md border flex items-center justify-center transition ${
                          isChecked
                            ? 'bg-indigo-600 border-indigo-600 text-white'
                            : 'border-slate-300 dark:border-slate-600'
                        }`}
                      >
                        {isChecked && <CheckCircle2 className="w-3.5 h-3.5" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold truncate">{concept.name}</div>
                        {concept.category && (
                          <div className="text-[10px] text-slate-400 truncate">
                            {concept.category} • {concept.difficulty}
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Section 4: Rubric Criteria to Concept Mapping */}
          {activeRubric && activeRubric.criteria.length > 0 ? (
            <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-slate-800">
              <div>
                <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                  <span>4. Criterion-Level Concept Mapping</span>
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Map individual rubric criteria to specific curriculum concepts. This enables downstream AI evaluation to update concept mastery with high precision.
                </p>
              </div>

              <div className="space-y-2.5">
                {activeRubric.criteria.map((crit) => {
                  const mappedConceptId = criterionMap[crit.id] || '';
                  return (
                    <div
                      key={crit.id}
                      className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-center justify-between gap-3"
                    >
                      <div className="flex-1 min-w-[200px]">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                            {crit.title}
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-slate-200/80 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                            {crit.maxPoints} pts
                          </span>
                        </div>
                        {crit.description && (
                          <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-1 mt-0.5">
                            {crit.description}
                          </p>
                        )}
                      </div>

                      <div className="w-full sm:w-64">
                        <select
                          value={mappedConceptId}
                          onChange={(e) => handleCriterionConceptChange(crit.id, e.target.value)}
                          className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
                        >
                          <option value="">-- Whole Assignment --</option>
                          {concepts.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-2 pt-4 border-t border-slate-200 dark:border-slate-800">
              <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-slate-400" />
                <span>4. Criterion-Level Concept Mapping</span>
              </h3>
              <p className="text-[11px] text-slate-400">
                To configure criterion-level concept mappings, select an AI Evaluation Rubric in Section 2 above.
              </p>
            </div>
          )}

          {/* Modal Footer */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 text-xs font-semibold rounded-xl bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition disabled:opacity-50"
            >
              {isSubmitting ? 'Saving Assignment...' : assignment ? 'Save Changes' : 'Create Assignment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
