'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  GraduationCap,
  FileText,
  Clock,
  CheckCircle2,
  RefreshCw,
  BookOpen,
  Calendar,
  Award,
  ChevronRight,
  Eye,
  UploadCloud,
  Network,
  Layers,
  Sparkles,
} from 'lucide-react';
import {
  Course,
  Rubric,
  StudentAssignment,
  Submission,
  StudentCurriculumGraph as StudentCurriculumGraphType,
} from '@/lib/types';
import {
  getCourses,
  getRubrics,
  getSubmissions,
  refreshRubrics,
  refreshSubmissions,
  subscribeToSubmissions,
  fetchStudentAssignments,
  fetchStudentCurriculumGraph,
} from '@/lib/storage';
import { StudentUpload } from '@/components/StudentUpload';
import { SubmissionCard } from '@/components/SubmissionCard';
import { GradeDetailModal } from '@/components/GradeDetailModal';
import { RubricViewerModal } from '@/components/RubricViewerModal';
import { StatCard } from '@/components/StatCard';
import { StudentKnowledgeGraph } from '@/components/StudentKnowledgeGraph';

export default function StudentPortalPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [studentAssignments, setStudentAssignments] = useState<StudentAssignment[]>([]);
  const [selectedAssignId, setSelectedAssignId] = useState<string>('');
  const [selectedSub, setSelectedSub] = useState<Submission | null>(null);
  const [selectedRubric, setSelectedRubric] = useState<Rubric | null>(null);
  const [mounted, setMounted] = useState(false);

  // Tab mode: 'assignments' | 'knowledge_graph'
  const [activeTab, setActiveTab] = useState<'assignments' | 'knowledge_graph'>('assignments');
  const [studentGraph, setStudentGraph] = useState<StudentCurriculumGraphType | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<string>('c1010000-0000-0000-0000-000000000001');
  const [graphLoading, setGraphLoading] = useState(false);

  const uploadSectionRef = useRef<HTMLDivElement>(null);

  const loadAll = async () => {
    try {
      const [rubricList, , assignsList] = await Promise.all([
        refreshRubrics(),
        refreshSubmissions(),
        fetchStudentAssignments(),
      ]);
      setCourses(getCourses());
      setRubrics(rubricList);
      setSubmissions(getSubmissions());
      setStudentAssignments(assignsList);
      if (assignsList.length > 0 && !selectedAssignId) {
        setSelectedAssignId(assignsList[0].id);
      }
    } catch (error) {
      console.error('Failed to load student data:', error);
    }
  };

  const loadGraph = useCallback(async (courseId: string) => {
    try {
      setGraphLoading(true);
      const g = await fetchStudentCurriculumGraph(courseId);
      setStudentGraph(g);
    } catch (err) {
      console.error('Failed to load student curriculum graph:', err);
    } finally {
      setGraphLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      await loadAll();
      if (active) setMounted(true);
    })();

    const unsubscribe = subscribeToSubmissions((updatedSubs) => {
      setSubmissions(updatedSubs);
      setSelectedSub((prev) => (prev ? updatedSubs.find((s) => s.id === prev.id) || prev : null));
    });

    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (activeTab === 'knowledge_graph' && selectedCourseId) {
      void loadGraph(selectedCourseId);
    }
  }, [activeTab, selectedCourseId, loadGraph]);

  // Derived list of enrolled courses from assignments
  const enrolledCourses = useMemo(() => {
    const map = new Map<string, { id: string; code: string; name: string }>();
    map.set('c1010000-0000-0000-0000-000000000001', {
      id: 'c1010000-0000-0000-0000-000000000001',
      code: 'CS101',
      name: 'Data Structures and Algorithms',
    });
    studentAssignments.forEach((a) => {
      if (a.courseId && !map.has(a.courseId)) {
        map.set(a.courseId, { id: a.courseId, code: a.courseCode, name: a.courseName });
      }
    });
    return Array.from(map.values());
  }, [studentAssignments]);

  if (!mounted) {
    return (
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Clock className="w-4 h-4 animate-spin text-blue-600" />
          <span>Loading Student Portal...</span>
        </div>
      </div>
    );
  }

  const activeSubs = submissions;
  const evaluatedCount = activeSubs.filter((s) => s.status === 'done').length;
  const inProgressCount = activeSubs.filter((s) => s.status === 'pending' || s.status === 'processing').length;
  const averageScore =
    evaluatedCount > 0
      ? Math.round(
          activeSubs
            .filter((s) => s.evaluation)
            .reduce(
              (sum, s) =>
                sum +
                (s.override?.isOverridden
                  ? s.override.overriddenScore
                  : s.evaluation!.score),
              0
            ) / evaluatedCount
        )
      : 0;

  const handleSelectAssignmentForUpload = (assignmentId: string) => {
    setSelectedAssignId(assignmentId);
    uploadSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-xs sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-md bg-teal-50 dark:bg-teal-950/60 px-3 py-1 text-xs font-semibold text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
              <GraduationCap className="w-3.5 h-3.5" />
              <span>Smart Classroom & Assessment</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-3xl">
              Student Workspace
            </h1>
            <p className="max-w-xl text-xs text-slate-500 dark:text-slate-400 sm:text-sm">
              Submit your assignment files, track rubric scores, and explore your individualized concept mastery graph in real time.
            </p>
          </div>

          <div className="space-y-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 p-4 text-xs">
            <div className="font-semibold text-slate-800 dark:text-slate-200">Enrolled Student Account</div>
            <div className="text-slate-500 dark:text-slate-400">
              Access granted to published assignments and curriculum graphs.
            </div>
            <div className="flex items-center gap-1.5 pt-2 text-[10px] text-slate-500">
              <span className="size-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Realtime evaluation stream connected</span>
            </div>
          </div>
        </div>
      </div>

      {/* Primary Tab Navigation */}
      <div className="flex items-center gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
        <button
          onClick={() => setActiveTab('assignments')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition ${
            activeTab === 'assignments'
              ? 'bg-blue-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Assignments & Submissions</span>
        </button>
        <button
          onClick={() => setActiveTab('knowledge_graph')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition ${
            activeTab === 'knowledge_graph'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Network className="w-4 h-4" />
          <span>My Knowledge Graph</span>
          <span className="text-[10px] bg-indigo-500 text-white px-2 py-0.5 rounded-full font-bold">
            Interactive DAG
          </span>
        </button>
      </div>

      {/* TAB CONTENT 1: KNOWLEDGE GRAPH VIEW */}
      {activeTab === 'knowledge_graph' && (
        <div className="space-y-4">
          {/* Course Selector Bar */}
          <div className="p-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-indigo-600" />
              <label htmlFor="course-select" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Select Course Curriculum:
              </label>
              <select
                id="course-select"
                value={selectedCourseId}
                onChange={(e) => setSelectedCourseId(e.target.value)}
                className="text-xs font-semibold bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 dark:text-white"
              >
                {enrolledCourses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              <span>Click any concept node to inspect genuine evidence and evaluation feedback</span>
            </div>
          </div>

          {/* Interactive Knowledge Graph Canvas Container */}
          <div className="h-[720px] w-full">
            {graphLoading ? (
              <div className="h-full flex items-center justify-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2 text-slate-500 text-xs">
                  <Clock className="w-4 h-4 animate-spin text-indigo-600" />
                  <span>Loading your personalized knowledge graph...</span>
                </div>
              </div>
            ) : studentGraph ? (
              <StudentKnowledgeGraph
                graph={studentGraph}
                onRefresh={() => loadGraph(selectedCourseId)}
                isLoading={graphLoading}
                onViewAssignment={(id) => {
                  setActiveTab('assignments');
                  handleSelectAssignmentForUpload(id);
                }}
              />
            ) : (
              <div className="h-full flex flex-col items-center justify-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-8 text-center text-slate-400">
                <Network className="w-10 h-10 mb-2 text-slate-300" />
                <p className="text-sm font-semibold">No knowledge graph available for this course</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB CONTENT 2: ASSIGNMENTS & SUBMISSIONS VIEW */}
      {activeTab === 'assignments' && (
        <div className="space-y-8">
          {/* Metrics Row */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <StatCard
              title="Published Assignments"
              value={studentAssignments.length}
              subtext="Available course tasks"
              icon={FileText}
              iconColor="text-blue-600 dark:text-blue-400"
              iconBg="bg-blue-50 dark:bg-blue-950/40"
            />
            <StatCard
              title="Active Submissions"
              value={activeSubs.length}
              subtext="Total submissions recorded"
              icon={UploadCloud}
              iconColor="text-indigo-600 dark:text-indigo-400"
              iconBg="bg-indigo-50 dark:bg-indigo-950/40"
            />
            <StatCard
              title="Evaluated by AI"
              value={evaluatedCount}
              subtext="Graded against rubric"
              icon={CheckCircle2}
              iconColor="text-emerald-600 dark:text-emerald-400"
              iconBg="bg-emerald-50 dark:bg-emerald-950/40"
            />
            <StatCard
              title="In Queue / Grading"
              value={inProgressCount}
              subtext="Processing in background"
              icon={Clock}
              iconColor="text-amber-600 dark:text-amber-400"
              iconBg="bg-amber-50 dark:bg-amber-950/40"
            />
          </div>

          {/* Assigned Course Work Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-indigo-600" />
                  <span>Assigned Course Work & Concepts</span>
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Published assignments for your enrolled courses, showing targeted curriculum concepts and current status.
                </p>
              </div>
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                {studentAssignments.length} Tasks
              </span>
            </div>

            {studentAssignments.length === 0 ? (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center text-xs text-slate-400">
                No published assignments found for your enrolled courses yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {studentAssignments.map((assign) => {
                  const isSelected = selectedAssignId === assign.id;
                  const hasSubmitted = assign.submissionStatus !== 'unsubmitted';

                  return (
                    <div
                      key={assign.id}
                      className={`bg-white dark:bg-slate-900 border rounded-2xl p-5 shadow-xs transition flex flex-col justify-between ${
                        isSelected
                          ? 'border-blue-500 ring-2 ring-blue-500/20 shadow-md'
                          : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                      }`}
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                            {assign.courseCode}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider ${
                              assign.submissionStatus === 'graded'
                                ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200'
                                : assign.submissionStatus === 'pending' || assign.submissionStatus === 'processing'
                                ? 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                            }`}
                          >
                            {assign.submissionStatus === 'graded'
                              ? `Graded: ${assign.score ?? 0} pts`
                              : assign.submissionStatus === 'pending'
                              ? 'Awaiting AI Grading'
                              : 'Not Submitted'}
                          </span>
                        </div>

                        <div>
                          <h3 className="font-bold text-slate-900 dark:text-white text-sm line-clamp-1">
                            {assign.title}
                          </h3>
                          {assign.description && (
                            <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mt-1 leading-relaxed">
                              {assign.description}
                            </p>
                          )}
                        </div>

                        <div className="flex items-center gap-3 text-[11px] text-slate-500 font-medium">
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5 text-blue-600" />
                            <span>Due {new Date(assign.dueDate).toLocaleDateString()}</span>
                          </span>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <Award className="w-3.5 h-3.5 text-amber-600" />
                            <span>{assign.maxPoints} pts</span>
                          </span>
                        </div>

                        {/* Mapped Concepts Pills */}
                        {assign.concepts && assign.concepts.length > 0 && (
                          <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                            <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                              Targeted Concepts ({assign.concepts.length}):
                            </div>
                            <div className="flex flex-wrap items-center gap-1">
                              {assign.concepts.map((concept) => (
                                <span
                                  key={concept.id}
                                  className="px-2 py-0.5 rounded text-[10px] font-medium bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-900"
                                >
                                  {concept.name}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Card Action Controls */}
                      <div className="pt-4 mt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2">
                        {assign.rubric ? (
                          <button
                            onClick={() => setSelectedRubric(assign.rubric || null)}
                            className="flex items-center gap-1 text-[11px] font-semibold text-slate-600 dark:text-slate-300 hover:text-blue-600 transition"
                          >
                            <Eye className="w-3 h-3 text-blue-600" />
                            <span>View Rubric</span>
                          </button>
                        ) : (
                          <span className="text-[11px] text-slate-400">No Rubric</span>
                        )}

                        <button
                          onClick={() => handleSelectAssignmentForUpload(assign.id)}
                          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                            isSelected
                              ? 'bg-blue-600 text-white'
                              : 'bg-slate-100 dark:bg-slate-800 hover:bg-blue-50 hover:text-blue-600 text-slate-700 dark:text-slate-300'
                          }`}
                        >
                          <span>{hasSubmitted ? 'Resubmit Work' : 'Submit Work'}</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Main Two-Column Layout */}
          <div ref={uploadSectionRef} className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Column: Upload Component (5 cols) */}
            <div className="lg:col-span-5 space-y-6">
              <StudentUpload
                courses={courses}
                rubrics={rubrics}
                studentAssignments={studentAssignments}
                selectedAssignmentId={selectedAssignId}
                onSelectAssignment={(id) => setSelectedAssignId(id)}
                onSubmissionCreated={(newSub) => {
                  setSubmissions((prev) => {
                    const idx = prev.findIndex((s) => s.id === newSub.id);
                    if (idx >= 0) {
                      const updated = [...prev];
                      updated[idx] = newSub;
                      return updated;
                    }
                    return [newSub, ...prev];
                  });
                  // Refresh assignment cards
                  void fetchStudentAssignments().then(setStudentAssignments);
                }}
                onViewRubric={(rubric) => setSelectedRubric(rubric)}
              />
            </div>

            {/* Right Column: Submissions Feed (7 cols) */}
            <div className="lg:col-span-7 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-white">
                    My Submissions & Status
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Live updates automatically stream in when evaluations complete.
                  </p>
                </div>
                <button
                  onClick={() => void refreshSubmissions().catch((error) => console.error(error))}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition"
                  title="Refresh submissions list"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>

              {activeSubs.length === 0 ? (
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-12 text-center space-y-3">
                  <FileText className="w-10 h-10 text-slate-300 mx-auto" />
                  <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    No submissions yet
                  </h3>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    Use the form on the left or click &quot;Submit Work&quot; on any assigned course work card.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {activeSubs.map((sub) => (
                    <SubmissionCard
                      key={sub.id}
                      submission={sub}
                      onViewDetails={(s) => setSelectedSub(s)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      <GradeDetailModal
        isOpen={Boolean(selectedSub)}
        onClose={() => setSelectedSub(null)}
        submission={selectedSub}
        isFacultyView={false}
      />

      <RubricViewerModal
        isOpen={Boolean(selectedRubric)}
        onClose={() => setSelectedRubric(null)}
        rubric={selectedRubric}
      />
    </div>
  );
}
