'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Users,
  TrendingUp,
  Search,
  Filter,
  Download,
  ShieldCheck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Play,
  FileSpreadsheet,
  Layers,
  ArrowUpDown,
  FileText,
  Sparkles
} from 'lucide-react';
import { Course, Rubric, Submission } from '@/lib/types';
import { getCourses, getRubrics, getSubmissions, refreshRubrics, refreshSubmissions, subscribeToSubmissions } from '@/lib/storage';
import { api } from '@/lib/api';
import { exportSubmissionsToCSV, downloadJSON, getScoreColor } from '@/lib/utils';
import { StatCard } from '@/components/StatCard';
import { CreateCourseModal } from '@/components/CreateCourseModal';
import { fetchFacultyCourses } from '@/lib/storage';
import { BookOpen, ArrowRight, Plus } from 'lucide-react';
import { StatusBadge } from '@/components/Badge';
import { GradeDetailModal } from '@/components/GradeDetailModal';
import { OverrideModal } from '@/components/OverrideModal';
import { RubricViewerModal } from '@/components/RubricViewerModal';

export default function FacultyDashboardPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [facultyCourses, setFacultyCourses] = useState<Course[]>([]);
  const [isCreateCourseOpen, setIsCreateCourseOpen] = useState(false);
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [selectedCourse, setSelectedCourse] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedAssignment, setSelectedAssignment] = useState<string>('ALL');

  const availableAssignments = React.useMemo(() => {
    const map = new Map<string, { id: string; title: string }>();
    submissions.forEach((s) => {
      if (selectedCourse === 'ALL' || s.courseCode === selectedCourse) {
        if (s.assignmentId && !map.has(s.assignmentId)) {
          map.set(s.assignmentId, { id: s.assignmentId, title: s.assignmentTitle || s.assignmentId });
        }
      }
    });
    return Array.from(map.values());
  }, [submissions, selectedCourse]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSubForDetail, setSelectedSubForDetail] = useState<Submission | null>(null);
  const [selectedSubForOverride, setSelectedSubForOverride] = useState<Submission | null>(null);
  const [selectedRubric, setSelectedRubric] = useState<Rubric | null>(null);
  const [isProcessingBatch, setIsProcessingBatch] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const [fCourses] = await Promise.all([
          fetchFacultyCourses().catch(() => []),
          refreshRubrics(),
          refreshSubmissions({ faculty: true }),
        ]);
        if (active) {
          setFacultyCourses(fCourses);
          setCourses(getCourses());
          setRubrics(getRubrics());
          setSubmissions(getSubmissions());
        }
      } catch (error) { console.error(error); }
      finally { if (active) setMounted(true); }
    })();

    const unsubscribe = subscribeToSubmissions((updatedSubs) => {
      setSubmissions(updatedSubs);
      setSelectedSubForDetail((prev) => (prev ? updatedSubs.find((s) => s.id === prev.id) || prev : null));
      setSelectedSubForOverride((prev) => (prev ? updatedSubs.find((s) => s.id === prev.id) || prev : null));
    });

    return () => { active = false; unsubscribe(); };
  }, []);

  if (!mounted) {
    return (
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Clock className="w-4 h-4 animate-spin text-blue-600" />
          <span>Loading Faculty Dashboard...</span>
        </div>
      </div>
    );
  }

  // Filter submissions
  const filteredSubmissions = submissions.filter((sub) => {
    if (selectedCourse !== 'ALL' && sub.courseCode !== selectedCourse) return false;
    if (selectedAssignment !== 'ALL' && sub.assignmentId !== selectedAssignment) return false;
    if (statusFilter !== 'ALL') {
      if (statusFilter === 'overridden') {
        if (!sub.override?.isOverridden) return false;
      } else if (sub.status !== statusFilter) {
        return false;
      }
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = sub.studentName.toLowerCase().includes(q);
      const matchId = sub.studentId.toLowerCase().includes(q);
      const matchTitle = sub.assignmentTitle.toLowerCase().includes(q);
      if (!matchName && !matchId && !matchTitle) return false;
    }
    return true;
  });

  // Calculate statistics
  const totalSubmissions = submissions.length;
  const evaluatedCount = submissions.filter((s) => s.status === 'done').length;
  const pendingCount = submissions.filter((s) => s.status === 'pending' || s.status === 'processing').length;
  const overriddenCount = submissions.filter((s) => s.override?.isOverridden).length;
  const flaggedCount = submissions.filter((s) => s.status === 'flagged').length;

  const validScores = submissions
    .filter((s) => s.status === 'done' && s.evaluation)
    .map((s) => (s.override?.isOverridden ? s.override.overriddenScore : s.evaluation!.score));
  const classAvg = validScores.length > 0
    ? Math.round(validScores.reduce((a, b) => a + b, 0) / validScores.length)
    : 0;

  // Process all pending jobs simulate cron POST /internal/process-jobs
  const handleProcessPendingJobs = async () => {
    setIsProcessingBatch(true);
    try { await api('/api/v1/faculty/process-jobs', { method: 'POST' }); await refreshSubmissions({ faculty: true }); }
    catch (error) { alert(error instanceof Error ? error.message : 'Queue processing failed.'); }
    finally { setIsProcessingBatch(false); }
  };

  const handleExportCSV = () => {
    exportSubmissionsToCSV(filteredSubmissions, selectedCourse !== 'ALL' ? selectedCourse : undefined);
  };

  const handleExportJSON = () => {
    downloadJSON(filteredSubmissions, `eduagents_submissions_${selectedCourse}_${Date.now()}.json`);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xs flex flex-wrap items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
              Instructor Command Center
            </span>
            <span className="text-xs font-mono text-slate-400">Dr. Sarah Lin</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
            Faculty Evaluation Dashboard
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
            Review automated Gemini grading across class rosters, inspect rubric alignments, override scores with pedagogical justifications, and export reports.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => setIsCreateCourseOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Course</span>
          </button>

          <button
            onClick={handleProcessPendingJobs}
            disabled={isProcessingBatch || pendingCount === 0}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-orange-600 hover:bg-orange-700 text-white shadow-xs transition disabled:opacity-50 disabled:cursor-not-allowed"
            title="Trigger scheduled job runner to process pending jobs"
          >
            <Play className={`w-3.5 h-3.5 ${isProcessingBatch ? 'animate-spin' : ''}`} />
            <span>{isProcessingBatch ? 'Processing Queue...' : `Drain Queue (${pendingCount})`}</span>
          </button>

          <Link
            href="/faculty/rubrics"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Manage Rubrics ({rubrics.length})</span>
          </Link>

          <div className="relative inline-flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1">
            <button
              onClick={handleExportCSV}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-700 transition"
              title="Download CSV export"
            >
              <Download className="w-3.5 h-3.5 text-blue-600" />
              <span>CSV</span>
            </button>
            <button
              onClick={handleExportJSON}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-700 transition"
              title="Download JSON export"
            >
              <span>JSON</span>
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Submissions"
          value={totalSubmissions}
          subtext="Class submissions"
          icon={Users}
          iconColor="text-blue-600 dark:text-blue-400"
          iconBg="bg-blue-50 dark:bg-blue-950/40"
        />
        <StatCard
          title="Pending Queue"
          value={pendingCount}
          subtext="Awaiting cron execution"
          icon={Clock}
          iconColor="text-amber-600 dark:text-amber-400"
          iconBg="bg-amber-50 dark:bg-amber-950/40"
        />
        <StatCard
          title="Evaluated by AI"
          value={evaluatedCount}
          subtext="Graded via Gemini"
          icon={CheckCircle2}
          iconColor="text-emerald-600 dark:text-emerald-400"
          iconBg="bg-emerald-50 dark:bg-emerald-950/40"
        />
        <StatCard
          title="Faculty Overrides"
          value={overriddenCount}
          subtext="Audit trail logged"
          icon={ShieldCheck}
          iconColor="text-purple-600 dark:text-purple-400"
          iconBg="bg-purple-50 dark:bg-purple-950/40"
        />
        <StatCard
          title="Class Average"
          value={`${classAvg}%`}
          subtext="Across graded tasks"
          icon={Sparkles}
          iconColor="text-indigo-600 dark:text-indigo-400"
          iconBg="bg-indigo-50 dark:bg-indigo-950/40"
        />
      </div>

      {/* Courses & Curriculum Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between px-1">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-blue-600" />
              <span>Courses & Canonical Curriculum Graphs</span>
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Manage your courses, define pedagogical concepts, and construct prerequisite DAGs
            </p>
          </div>
          <button
            onClick={() => setIsCreateCourseOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 hover:bg-blue-100 transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create Course</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {facultyCourses.map((c) => (
            <div
              key={c.id}
              className="group bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700 transition flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                    {c.code}
                  </span>
                  <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                    <span>{c.conceptsCount ?? 0} Concepts</span>
                    <span>•</span>
                    <span>{c.assignmentsCount ?? 0} Assigns</span>
                  </div>
                </div>
                <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-1 line-clamp-1">
                  {c.name}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed mb-4">
                  {c.description || 'No description provided for this course.'}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2 flex-wrap">
                <Link
                  href={`/faculty/courses/${c.id}/assignments`}
                  className="flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-blue-600 transition"
                >
                  <FileText className="w-3.5 h-3.5 text-blue-600" />
                  <span>Assigns ({c.assignmentsCount ?? 0})</span>
                </Link>
                <Link
                  href={`/faculty/courses/${c.id}/curriculum`}
                  className="flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-blue-600 transition"
                >
                  <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Curriculum</span>
                </Link>
                <Link
                  href={`/faculty/courses/${c.id}/students`}
                  className="flex items-center gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-700 transition"
                >
                  <Users className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Students</span>
                </Link>
                <Link
                  href={`/faculty/courses/${c.id}/analytics`}
                  className="flex items-center gap-1 text-xs font-semibold text-purple-600 dark:text-purple-400 hover:text-purple-700 transition"
                >
                  <TrendingUp className="w-3.5 h-3.5 text-purple-600" />
                  <span>Analytics</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by student name, ID, or assignment..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Course Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500 font-medium">Course:</span>
            <select
              value={selectedCourse}
              onChange={(e) => {
                setSelectedCourse(e.target.value);
                setSelectedAssignment('ALL');
              }}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Courses</option>
              {courses.map((c) => (
                <option key={c.id} value={c.code}>
                  {c.code} - {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Assignment Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500 font-medium">Assignment:</span>
            <select
              value={selectedAssignment}
              onChange={(e) => setSelectedAssignment(e.target.value)}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 max-w-[200px] truncate"
            >
              <option value="ALL">All Assignments</option>
              {availableAssignments.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500 font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="done">Done / Evaluated</option>
              <option value="manual_review">Manual Review Required</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="flagged">Flagged</option>
              <option value="overridden">Faculty Overridden</option>
            </select>
          </div>
        </div>
      </div>

      {/* Submissions Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="font-bold text-slate-900 dark:text-white text-base">
              Roster Submissions
            </h2>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              Showing {filteredSubmissions.length} of {totalSubmissions}
            </span>
          </div>
          <span className="text-xs text-slate-400 hidden sm:inline">
            Click &quot;Review&quot; to inspect full Gemini analysis or &quot;Override&quot; to adjust score
          </span>
        </div>

        {filteredSubmissions.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto" />
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              No matching submissions found
            </h3>
            <p className="text-xs text-slate-500">
              Try adjusting your filter or search query.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50/80 dark:bg-slate-800/40 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-800">
                  <th className="px-6 py-3.5">Student</th>
                  <th className="px-4 py-3.5">Course & Assignment</th>
                  <th className="px-4 py-3.5">Document</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5">Score</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredSubmissions.map((sub) => {
                  const isOverridden = Boolean(sub.override?.isOverridden);
                  const evalScore = sub.evaluation?.score;
                  const maxScore = sub.evaluation?.maxScore ?? 100;
                  const finalScore = isOverridden ? sub.override!.overriddenScore : evalScore;
                  const percentage = finalScore !== undefined ? Math.round((finalScore / maxScore) * 100) : null;
                  const scoreColors = percentage !== null ? getScoreColor(percentage) : null;

                  return (
                    <tr
                      key={sub.id}
                      className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition group"
                    >
                      {/* Student Info */}
                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-900 dark:text-white">
                          {sub.studentName}
                        </div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                          {sub.studentId}
                        </div>
                      </td>

                      {/* Course & Assignment */}
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                            {sub.courseCode}
                          </span>
                          <span className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-xs block">
                            {sub.assignmentTitle}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          Submitted {sub.submittedAt}
                        </div>
                      </td>

                      {/* Document */}
                      <td className="px-4 py-4 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                        <div className="flex items-center gap-1">
                          <FileText className="w-3.5 h-3.5 text-slate-400" />
                          <span className="truncate max-w-[150px]">{sub.fileName}</span>
                        </div>
                        <span className="text-[10px] text-slate-400">({sub.fileSize})</span>
                      </td>

                      {/* Status */}
                      <td className="px-4 py-4">
                        <StatusBadge status={sub.status} isOverridden={isOverridden} size="sm" />
                      </td>

                      {/* Score */}
                      <td className="px-4 py-4">
                        {finalScore !== undefined && scoreColors ? (
                          <div className="flex items-baseline gap-1.5">
                            <span className={`font-bold font-mono text-sm ${scoreColors.text}`}>
                              {finalScore}
                            </span>
                            <span className="text-slate-400 text-[11px]">/ {maxScore}</span>
                            <span className={`text-[10px] font-semibold px-1.5 py-0.2 rounded ${scoreColors.bg} ${scoreColors.text}`}>
                              {percentage}%
                            </span>
                            {isOverridden && (
                              <span title="Overridden by Faculty" className="text-purple-600 dark:text-purple-400">
                                <ShieldCheck className="w-3.5 h-3.5" />
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400 font-mono text-xs">Pending</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setSelectedSubForDetail(sub)}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition"
                          >
                            Review
                          </button>
                          <button
                            onClick={() => setSelectedSubForOverride(sub)}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-50 hover:bg-purple-100 dark:bg-purple-950/60 dark:hover:bg-purple-900/60 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 transition flex items-center gap-1"
                          >
                            <ShieldCheck className="w-3 h-3" />
                            <span>Override</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <GradeDetailModal
        isOpen={Boolean(selectedSubForDetail)}
        onClose={() => setSelectedSubForDetail(null)}
        submission={selectedSubForDetail}
        onOpenOverride={(s) => {
          setSelectedSubForDetail(null);
          setSelectedSubForOverride(s);
        }}
        isFacultyView={true}
      />

      <OverrideModal
        isOpen={Boolean(selectedSubForOverride)}
        onClose={() => setSelectedSubForOverride(null)}
        submission={selectedSubForOverride}
        onOverrideSaved={(updated) => {
          setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
          setSelectedSubForOverride(null);
        }}
      />
    </div>
  );
}
