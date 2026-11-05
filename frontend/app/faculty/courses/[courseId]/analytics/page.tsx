'use client';

import React, { useState, useEffect, useCallback, use } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  BookOpen,
  Users,
  FileText,
  TrendingUp,
  Sparkles,
  Clock,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  Layers,
  Search,
  Award,
  HelpCircle,
  RefreshCw,
  Sliders,
  X,
  Check,
  BarChart2,
} from 'lucide-react';
import {
  CourseLearningAnalytics,
  StudentProgressSummary,
  ConceptAnalyticsSummary,
  AssignmentAnalyticsSummary,
  ConceptMasteryOverridePayload,
} from '@/lib/types';
import {
  fetchCourseAnalytics,
  overrideConceptMastery,
  removeConceptMasteryOverride,
} from '@/lib/storage';
import { StatCard } from '@/components/StatCard';
import { Modal } from '@/components/Modal';

interface PageProps {
  params: Promise<{ courseId: string }>;
}

export default function FacultyCourseAnalyticsPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const courseId = resolvedParams.courseId;

  const [analytics, setAnalytics] = useState<CourseLearningAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'progress' | 'concepts' | 'assignments'>('progress');

  // Filters
  const [studentSearch, setStudentSearch] = useState('');
  const [conceptSearch, setConceptSearch] = useState('');

  // Concept Override Modal State
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<StudentProgressSummary | null>(null);
  const [selectedConceptId, setSelectedConceptId] = useState<string>('');
  const [overrideMastery, setOverrideMastery] = useState<number>(85);
  const [overrideConfidence, setOverrideConfidence] = useState<number>(90);
  const [overrideReason, setOverrideReason] = useState<string>('');
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);
  const [overrideError, setOverrideError] = useState<string | null>(null);

  const loadAnalytics = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const data = await fetchCourseAnalytics(courseId);
      setAnalytics(data);
    } catch (err: any) {
      console.error('Failed to load course analytics:', err);
      setErrorMessage(err.message || 'Failed to load course learning analytics.');
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  const handleOpenOverride = (student: StudentProgressSummary) => {
    setSelectedStudent(student);
    if (analytics && analytics.conceptAnalytics.length > 0) {
      setSelectedConceptId(analytics.conceptAnalytics[0].conceptId);
    }
    setOverrideMastery(85);
    setOverrideConfidence(90);
    setOverrideReason('');
    setOverrideError(null);
    setOverrideModalOpen(true);
  };

  const handleSaveConceptOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStudent || !selectedConceptId) return;
    if (!overrideReason.trim()) {
      setOverrideError('Please provide a mandatory faculty justification rationale.');
      return;
    }

    try {
      setOverrideSubmitting(true);
      setOverrideError(null);
      const payload: ConceptMasteryOverridePayload = {
        masteryScore: Math.max(0, Math.min(1.0, overrideMastery / 100.0)),
        confidenceScore: Math.max(0, Math.min(1.0, overrideConfidence / 100.0)),
        overrideReason: overrideReason.trim(),
      };
      await overrideConceptMastery(courseId, selectedStudent.studentId, selectedConceptId, payload);
      setOverrideModalOpen(false);
      await loadAnalytics();
    } catch (err: any) {
      setOverrideError(err.message || 'Failed to apply concept mastery override.');
    } finally {
      setOverrideSubmitting(false);
    }
  };

  const handleRevokeConceptOverride = async () => {
    if (!selectedStudent || !selectedConceptId) return;
    if (!window.confirm('Are you sure you want to revoke this concept override and restore pure AI mastery?')) {
      return;
    }

    try {
      setOverrideSubmitting(true);
      setOverrideError(null);
      await removeConceptMasteryOverride(courseId, selectedStudent.studentId, selectedConceptId, 'Faculty revoked concept override.');
      setOverrideModalOpen(false);
      await loadAnalytics();
    } catch (err: any) {
      setOverrideError(err.message || 'Failed to revoke concept mastery override.');
    } finally {
      setOverrideSubmitting(false);
    }
  };

  if (loading && !analytics) {
    return (
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Clock className="w-4 h-4 animate-spin text-purple-600" />
          <span>Computing Course Learning Analytics...</span>
        </div>
      </div>
    );
  }

  if (errorMessage && !analytics) {
    return (
      <div className="max-w-4xl mx-auto p-6 sm:p-8 space-y-4">
        <Link
          href="/faculty"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-900 dark:hover:text-white transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Faculty Dashboard</span>
        </Link>
        <div className="p-4 rounded-xl bg-rose-50 text-rose-700 border border-rose-200 text-sm flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      </div>
    );
  }

  const ov = analytics!.overview;

  const filteredStudents = analytics!.studentProgress.filter((s) => {
    if (!studentSearch.trim()) return true;
    const q = studentSearch.toLowerCase();
    return s.studentName.toLowerCase().includes(q) || s.studentEmail.toLowerCase().includes(q);
  });

  const filteredConcepts = analytics!.conceptAnalytics.filter((c) => {
    if (!conceptSearch.trim()) return true;
    const q = conceptSearch.toLowerCase();
    return c.name.toLowerCase().includes(q) || c.category.toLowerCase().includes(q);
  });

  const attentionConceptsCount = analytics!.conceptAnalytics.filter((c) => c.needsAttention).length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Navigation Sub-Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div className="flex items-center gap-4">
          <Link
            href="/faculty"
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 dark:hover:text-white transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Faculty Hub</span>
          </Link>
          <span className="text-slate-300 dark:text-slate-700">|</span>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
              {ov.courseCode}
            </span>
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{ov.courseName}</span>
          </div>
        </div>

        {/* Tab & Action Navigation */}
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href={`/faculty/courses/${courseId}/assignments`}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 transition"
          >
            Assignments
          </Link>
          <Link
            href={`/faculty/courses/${courseId}/curriculum`}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 transition"
          >
            Curriculum DAG
          </Link>
          <Link
            href={`/faculty/courses/${courseId}/students`}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 transition"
          >
            Knowledge Graphs
          </Link>
          <button
            onClick={() => void loadAnalytics()}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-purple-600 bg-purple-50 hover:bg-purple-100 dark:bg-purple-950/50 dark:text-purple-300 transition"
            title="Refresh learning metrics"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main Page Title Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xs flex flex-wrap items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-200 dark:border-purple-800 flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Pedagogical Learning Analytics</span>
            </span>
            <span className="text-xs font-mono text-slate-400">Course: {ov.courseCode}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
            {ov.courseName} • Analytics
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Real-time mastery aggregation across class rosters, concept vulnerability flags, assignment distribution histograms, and direct human-in-the-loop overrides.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-right">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-bold block">
              Attention Required
            </span>
            <span className="text-xl font-black text-rose-600 dark:text-rose-400">
              {attentionConceptsCount} Concept{attentionConceptsCount !== 1 ? 's' : ''}
            </span>
          </div>
          {ov.manualReviewSubmissions > 0 && (
            <div className="p-3 rounded-2xl bg-orange-50 dark:bg-orange-950/40 border border-orange-200 dark:border-orange-800 text-right">
              <span className="text-[11px] uppercase tracking-wider text-orange-600 font-bold block">
                Manual Review Queue
              </span>
              <span className="text-xl font-black text-orange-600 dark:text-orange-400">
                {ov.manualReviewSubmissions} Sub{ov.manualReviewSubmissions !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Top 5 Key Performance Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Enrolled Students"
          value={ov.totalEnrolled}
          subtext="Active class roster"
          icon={Users}
          iconColor="text-blue-600 dark:text-blue-400"
          iconBg="bg-blue-50 dark:bg-blue-950/40"
        />
        <StatCard
          title="Assignments"
          value={`${ov.publishedAssignments} / ${ov.totalAssignments}`}
          subtext="Published / Total"
          icon={FileText}
          iconColor="text-indigo-600 dark:text-indigo-400"
          iconBg="bg-indigo-50 dark:bg-indigo-950/40"
        />
        <StatCard
          title="Avg. Assignment Score"
          value={`${ov.averageAssignmentScore}%`}
          subtext={`Across ${ov.completedEvaluations} evaluated`}
          icon={Award}
          iconColor="text-emerald-600 dark:text-emerald-400"
          iconBg="bg-emerald-50 dark:bg-emerald-950/40"
        />
        <StatCard
          title="Concept Coverage"
          value={`${ov.conceptCoveragePercentage}%`}
          subtext="Curriculum assessed"
          icon={BookOpen}
          iconColor="text-purple-600 dark:text-purple-400"
          iconBg="bg-purple-50 dark:bg-purple-950/40"
        />
        <StatCard
          title="Total Submissions"
          value={ov.totalSubmissions}
          subtext={`${ov.pendingEvaluations} pending batch`}
          icon={Clock}
          iconColor="text-amber-600 dark:text-amber-400"
          iconBg="bg-amber-50 dark:bg-amber-950/40"
        />
      </div>

      {/* Segmented Tab Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('progress')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === 'progress'
              ? 'bg-purple-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>Student Learning Roster ({analytics!.studentProgress.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('concepts')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === 'concepts'
              ? 'bg-purple-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Concept Mastery & Attention ({analytics!.conceptAnalytics.length})</span>
          {attentionConceptsCount > 0 && (
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('assignments')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeTab === 'assignments'
              ? 'bg-purple-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <BarChart2 className="w-3.5 h-3.5" />
          <span>Assignment Distributions ({analytics!.assignmentAnalytics.length})</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: STUDENT PROGRESS SUMMARY ROSTER */}
      {/* ========================================================================= */}
      {activeTab === 'progress' && (
        <div className="space-y-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={studentSearch}
                onChange={(e) => setStudentSearch(e.target.value)}
                placeholder="Search students by name or email..."
                className="w-full pl-9 pr-4 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl text-xs focus:outline-hidden focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
              <span>Strong (≥70%)</span>
              <span className="inline-block w-2 h-2 rounded-full bg-amber-500 ml-2" />
              <span>Developing (40-69%)</span>
              <span className="inline-block w-2 h-2 rounded-full bg-rose-500 ml-2" />
              <span>Low (&lt;40%)</span>
              <span className="inline-block w-2 h-2 rounded-full bg-slate-300 ml-2" />
              <span>Unassessed</span>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 text-slate-500 uppercase tracking-wider font-semibold">
                    <th className="py-3 px-4">Student</th>
                    <th className="py-3 px-4">Coverage</th>
                    <th className="py-3 px-4">Avg. Mastery (Assessed Only)</th>
                    <th className="py-3 px-4">Mastery Breakdown</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredStudents.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-400">
                        No enrolled students matching filter.
                      </td>
                    </tr>
                  ) : (
                    filteredStudents.map((st) => (
                      <tr key={st.studentId} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition">
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-slate-900 dark:text-white">{st.studentName}</div>
                          <div className="text-[11px] text-slate-400 font-mono">{st.studentEmail}</div>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                              {st.assessedConcepts}/{st.totalConcepts}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">({st.coveragePercentage}%)</span>
                          </div>
                          <div className="w-24 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden mt-1">
                            <div
                              className="h-full bg-purple-500 rounded-full transition-all"
                              style={{ width: `${st.coveragePercentage}%` }}
                            />
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          {st.assessedConcepts > 0 ? (
                            <div className="flex items-baseline gap-1.5">
                              <span
                                className={`text-base font-extrabold font-mono ${
                                  st.averageMastery >= 70
                                    ? 'text-emerald-600 dark:text-emerald-400'
                                    : st.averageMastery >= 40
                                    ? 'text-amber-600 dark:text-amber-400'
                                    : 'text-rose-600 dark:text-rose-400'
                                }`}
                              >
                                {st.averageMastery}%
                              </span>
                              <span className="text-[10px] text-slate-400 font-mono">
                                ({st.assessedConcepts} concept{st.assessedConcepts !== 1 ? 's' : ''})
                              </span>
                            </div>
                          ) : (
                            <span className="text-slate-400 italic text-[11px]">Unassessed</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-1.5 font-mono text-[11px]">
                            <span
                              className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-bold border border-emerald-200 dark:border-emerald-800"
                              title="Strong concepts (≥70%)"
                            >
                              {st.strongCount} S
                            </span>
                            <span
                              className="px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 font-bold border border-amber-200 dark:border-amber-800"
                              title="Developing concepts (40-69%)"
                            >
                              {st.developingCount} D
                            </span>
                            <span
                              className="px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 font-bold border border-rose-200 dark:border-rose-800"
                              title="Low mastery concepts (<40%)"
                            >
                              {st.lowMasteryCount} L
                            </span>
                            <span
                              className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                              title="Unassessed concepts"
                            >
                              {st.unassessedCount} U
                            </span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => handleOpenOverride(st)}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-950/50 hover:bg-purple-100 transition"
                            >
                              <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
                              <span>Override Mastery</span>
                            </button>
                            <Link
                              href={`/faculty/courses/${courseId}/students`}
                              className="px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
                            >
                              View Graph
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: CONCEPT-LEVEL PEDAGOGICAL ANALYTICS & ATTENTION ALERTS */}
      {/* ========================================================================= */}
      {activeTab === 'concepts' && (
        <div className="space-y-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={conceptSearch}
                onChange={(e) => setConceptSearch(e.target.value)}
                placeholder="Search concepts by name or category..."
                className="w-full pl-9 pr-4 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl text-xs focus:outline-hidden focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div className="text-xs text-slate-500 font-medium">
              Flagged if avg. mastery &lt; 50% or ≥ 30% of assessed cohort is struggling
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredConcepts.map((c) => (
              <div
                key={c.conceptId}
                className={`bg-white dark:bg-slate-900 border rounded-2xl p-5 shadow-xs transition flex flex-col justify-between ${
                  c.needsAttention
                    ? 'border-rose-200 dark:border-rose-900/60 bg-rose-50/20'
                    : 'border-slate-200 dark:border-slate-800'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {c.category}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${
                        c.difficulty === 'beginner'
                          ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300'
                          : c.difficulty === 'intermediate'
                          ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                          : 'bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300'
                      }`}
                    >
                      {c.difficulty}
                    </span>
                  </div>

                  <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-2">{c.name}</h3>

                  {c.needsAttention ? (
                    <div className="mb-3 p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900/50 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                      <div>
                        <div className="text-[11px] font-bold text-rose-800 dark:text-rose-200">
                          Pedagogical Attention Flag
                        </div>
                        <div className="text-[11px] text-rose-700 dark:text-rose-300">
                          {c.attentionReason || 'Requires curriculum re-anchoring'}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mb-3 p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 flex items-center gap-1.5 text-[11px] text-emerald-800 dark:text-emerald-300 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Cohort Progress On Track</span>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-150 dark:border-slate-700 text-xs mb-3">
                    <div>
                      <span className="text-[10px] text-slate-400 block font-semibold">Class Avg. Mastery</span>
                      <span
                        className={`text-lg font-bold font-mono ${
                          c.averageMastery >= 70
                            ? 'text-emerald-600'
                            : c.averageMastery >= 40
                            ? 'text-amber-600'
                            : 'text-rose-600'
                        }`}
                      >
                        {c.averageMastery}%
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block font-semibold">Assessed Cohort</span>
                      <span className="text-lg font-bold font-mono text-slate-700 dark:text-slate-300">
                        {c.assessedStudentsCount} / {c.assessedStudentsCount + c.unassessedStudentsCount}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-emerald-600 font-bold">{c.strongHighCount} Strong</span>
                  <span className="text-amber-600 font-bold">{c.developingCount} Dev</span>
                  <span className="text-rose-600 font-bold">{c.lowMasteryCount} Low</span>
                  <span className="text-slate-400">{c.unassessedStudentsCount} Unassessed</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: ASSIGNMENT PERFORMANCE BREAKDOWN & HISTOGRAM */}
      {/* ========================================================================= */}
      {activeTab === 'assignments' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {analytics!.assignmentAnalytics.map((a) => {
              const totalDist = Object.values(a.scoreDistribution).reduce((acc, v) => acc + v, 0);

              return (
                <div
                  key={a.assignmentId}
                  className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-wider ${
                          a.status === 'published'
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200'
                            : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        {a.status}
                      </span>
                      <h3 className="font-bold text-slate-900 dark:text-white text-base mt-1.5">{a.title}</h3>
                      {a.dueDate && (
                        <p className="text-xs text-slate-400 mt-0.5">Due: {new Date(a.dueDate).toLocaleDateString()}</p>
                      )}
                    </div>

                    <div className="text-right">
                      <span className="text-xs font-semibold text-slate-400 block">Class Average</span>
                      <span className="text-2xl font-black text-purple-600 dark:text-purple-400 font-mono">
                        {a.averageScore}%
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-150 dark:border-slate-700 text-center text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 block font-semibold">Submissions</span>
                      <span className="text-sm font-bold font-mono text-slate-800 dark:text-slate-200">
                        {a.submissionCount}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block font-semibold">Completion</span>
                      <span className="text-sm font-bold font-mono text-slate-800 dark:text-slate-200">
                        {a.completionRate}%
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block font-semibold">Max Points</span>
                      <span className="text-sm font-bold font-mono text-slate-800 dark:text-slate-200">
                        {a.maxMarks}
                      </span>
                    </div>
                  </div>

                  {/* Score Distribution Buckets Histogram */}
                  <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300 block uppercase tracking-wider">
                      Cohort Score Distribution
                    </span>

                    <div className="space-y-1.5">
                      {Object.entries(a.scoreDistribution).map(([bucket, count]) => {
                        const pct = totalDist > 0 ? Math.round((count / totalDist) * 100) : 0;
                        return (
                          <div key={bucket} className="flex items-center gap-3 text-xs">
                            <span className="w-14 font-mono font-semibold text-slate-500 text-[11px]">{bucket}%</span>
                            <div className="flex-1 h-3 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  bucket === '90-100' || bucket === '80-89'
                                    ? 'bg-emerald-500'
                                    : bucket === '70-79'
                                    ? 'bg-blue-500'
                                    : bucket === '60-69'
                                    ? 'bg-amber-500'
                                    : 'bg-rose-500'
                                }`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                            <span className="w-12 text-right font-mono text-[11px] text-slate-400">
                              {count} ({pct}%)
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {a.manualReviewCount > 0 && (
                    <div className="p-2.5 rounded-xl bg-orange-50 dark:bg-orange-950/40 border border-orange-200 dark:border-orange-800 text-xs text-orange-800 dark:text-orange-300 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-orange-600" />
                      <span>{a.manualReviewCount} submission(s) pending manual document review</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* DIRECT CONCEPT MASTERY OVERRIDE MODAL */}
      {/* ========================================================================= */}
      <Modal
        isOpen={overrideModalOpen}
        onClose={() => setOverrideModalOpen(false)}
        title="Direct Concept Mastery Override"
        subtitle={selectedStudent ? `Student: ${selectedStudent.studentName} (${selectedStudent.studentEmail})` : ''}
        maxWidth="lg"
      >
        <form onSubmit={handleSaveConceptOverride} className="space-y-5">
          {/* Concept Picker */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Select Canonical Concept
            </label>
            <select
              value={selectedConceptId}
              onChange={(e) => setSelectedConceptId(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs font-semibold focus:outline-hidden focus:ring-2 focus:ring-purple-500"
              required
            >
              {analytics?.conceptAnalytics.map((c) => (
                <option key={c.conceptId} value={c.conceptId}>
                  {c.name} ({c.category} • Avg: {c.averageMastery}%)
                </option>
              ))}
            </select>
          </div>

          {/* Mastery Score Slider & Number */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                Overridden Mastery Score
              </label>
              <span className="text-base font-extrabold text-purple-600 font-mono">{overrideMastery}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={overrideMastery}
              onChange={(e) => setOverrideMastery(Number(e.target.value))}
              className="w-full accent-purple-600"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Mastery score will be persisted with source = 'faculty_override'.
            </p>
          </div>

          {/* Confidence Score Slider */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                Confidence Level
              </label>
              <span className="text-sm font-bold text-slate-700 dark:text-slate-300 font-mono">
                {overrideConfidence}%
              </span>
            </div>
            <input
              type="range"
              min={50}
              max={100}
              step={1}
              value={overrideConfidence}
              onChange={(e) => setOverrideConfidence(Number(e.target.value))}
              className="w-full accent-purple-600"
            />
          </div>

          {/* Mandatory Reason */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Mandatory Pedagogical Audit Rationale
            </label>
            <textarea
              rows={3}
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="e.g. Student demonstrated full understanding during 1-on-1 office hours code review..."
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs focus:outline-hidden focus:ring-2 focus:ring-purple-500"
              required
            />
          </div>

          {overrideError && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-50 text-rose-700 border border-rose-200 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{overrideError}</span>
            </div>
          )}

          {/* Modal Actions */}
          <div className="flex items-center justify-between gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={handleRevokeConceptOverride}
              disabled={overrideSubmitting}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300 transition disabled:opacity-50"
            >
              Revoke & Revert to AI
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setOverrideModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={overrideSubmitting}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-700 shadow-sm transition disabled:opacity-50"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>{overrideSubmitting ? 'Saving...' : 'Apply Concept Override'}</span>
              </button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  );
}
