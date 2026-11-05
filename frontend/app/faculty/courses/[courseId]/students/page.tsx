'use client';

import React, { useState, useEffect, useCallback, use } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Users,
  BookOpen,
  FileText,
  Clock,
  AlertCircle,
  Search,
  ChevronRight,
  TrendingUp,
  Award,
  Layers,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  HelpCircle,
} from 'lucide-react';
import {
  Course,
  EnrolledStudentSummary,
  StudentCurriculumGraph as StudentCurriculumGraphType,
} from '@/lib/types';
import {
  fetchCourseDetails,
  fetchCourseEnrolledStudents,
  fetchStudentCurriculumGraph,
} from '@/lib/storage';
import { StudentKnowledgeGraph } from '@/components/StudentKnowledgeGraph';
import { StatCard } from '@/components/StatCard';

interface PageProps {
  params: Promise<{ courseId: string }>;
}

export default function FacultyCourseStudentsPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const courseId = resolvedParams.courseId;

  const [course, setCourse] = useState<Course | null>(null);
  const [students, setStudents] = useState<EnrolledStudentSummary[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<EnrolledStudentSummary | null>(null);
  const [studentGraph, setStudentGraph] = useState<StudentCurriculumGraphType | null>(null);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Initial load
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const [courseData, studentsData] = await Promise.all([
        fetchCourseDetails(courseId),
        fetchCourseEnrolledStudents(courseId),
      ]);
      setCourse(courseData);
      setStudents(studentsData);
      if (studentsData.length > 0 && !selectedStudent) {
        // Auto-select first student
        setSelectedStudent(studentsData[0]);
      }
    } catch (err: any) {
      console.error('Failed to load course students:', err);
      setErrorMessage(err.message || 'Failed to load course enrolled students.');
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Load selected student's graph
  const loadStudentGraph = useCallback(
    async (studentId: string) => {
      try {
        setGraphLoading(true);
        const graph = await fetchStudentCurriculumGraph(courseId, studentId);
        setStudentGraph(graph);
      } catch (err: any) {
        console.error('Failed to fetch student graph:', err);
      } finally {
        setGraphLoading(false);
      }
    },
    [courseId]
  );

  useEffect(() => {
    if (selectedStudent) {
      void loadStudentGraph(selectedStudent.studentId);
    }
  }, [selectedStudent, loadStudentGraph]);

  const filteredStudents = students.filter(
    (s) =>
      s.studentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.studentEmail.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-16">
        <div className="flex items-center gap-2.5 text-slate-500 text-sm">
          <Clock className="w-5 h-5 animate-spin text-blue-600" />
          <span>Loading Enrolled Students & Curriculum Data...</span>
        </div>
      </div>
    );
  }

  if (errorMessage || !course) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12">
        <div className="p-6 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-bold">Failed to Load Course Students</h3>
              <p className="text-xs mt-1 text-rose-700 dark:text-rose-400">
                {errorMessage || 'Course not found or access denied.'}
              </p>
              <Link
                href="/faculty"
                className="inline-flex items-center gap-1.5 mt-4 text-xs font-semibold px-3 py-1.5 rounded-xl bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 hover:bg-rose-100 transition"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Return to Faculty Dashboard</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const totalAssessedAcrossClass = students.reduce((sum, s) => sum + s.totalAssessedConcepts, 0);
  const avgClassMastery =
    students.length > 0
      ? Math.round(
          (students.reduce((sum, s) => sum + s.averageMastery, 0) / students.length) * 100
        )
      : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header & Breadcrumbs */}
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
            <span>Curriculum DAG</span>
          </Link>
          <span className="text-slate-300 dark:text-slate-700">•</span>
          <Link
            href={`/faculty/courses/${course.id}/assignments`}
            className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-800 dark:hover:text-slate-300 transition"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Assignments</span>
          </Link>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                {course.code}
              </span>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                Student Learning Graphs & Mastery Inspector
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-3xl leading-relaxed">
              Inspect how individual students navigate the canonical curriculum DAG. View personalized mastery overlays, confidence scores, and genuine evaluation evidence.
            </p>
          </div>
        </div>
      </div>

      {/* Class Aggregate Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Enrolled Students"
          value={students.length}
          subtext="Active learners in course"
          icon={Users}
          iconColor="text-indigo-600 dark:text-indigo-400"
          iconBg="bg-indigo-50 dark:bg-indigo-950/50"
        />
        <StatCard
          title="Concept Assessments"
          value={totalAssessedAcrossClass}
          subtext="Evaluated submission evidence"
          icon={Layers}
          iconColor="text-emerald-600 dark:text-emerald-400"
          iconBg="bg-emerald-50 dark:bg-emerald-950/50"
        />
        <StatCard
          title="Class Average Mastery"
          value={students.length > 0 ? `${avgClassMastery}%` : '—'}
          subtext="Aggregated concept scores"
          icon={TrendingUp}
          iconColor="text-blue-600 dark:text-blue-400"
          iconBg="bg-blue-50 dark:bg-blue-950/50"
        />
      </div>

      {/* Two Column Layout: Student Roster Sidebar & Interactive Knowledge Graph */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Student Selector Sidebar */}
        <div className="lg:col-span-4 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5" />
              <span>Enrolled Students ({students.length})</span>
            </h3>
          </div>

          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by student name or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:text-white"
            />
          </div>

          {/* Student List */}
          <div className="space-y-2 max-h-[550px] overflow-y-auto pr-1">
            {filteredStudents.length === 0 ? (
              <div className="p-6 text-center text-xs text-slate-400">
                No matching enrolled students found.
              </div>
            ) : (
              filteredStudents.map((st) => {
                const isSelected = selectedStudent?.studentId === st.studentId;
                const masteryPct = Math.round(st.averageMastery * 100);

                return (
                  <button
                    key={st.studentId}
                    onClick={() => setSelectedStudent(st)}
                    className={`w-full text-left p-3 rounded-xl border transition-all flex flex-col gap-2 ${
                      isSelected
                        ? 'bg-indigo-50/80 dark:bg-indigo-950/40 border-indigo-400 dark:border-indigo-600 ring-2 ring-indigo-500/20 shadow-xs'
                        : 'bg-white dark:bg-slate-800/40 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-bold text-xs text-slate-900 dark:text-white truncate">
                        {st.studentName}
                      </div>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          masteryPct >= 70
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                            : masteryPct >= 40
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                            : st.totalAssessedConcepts > 0
                            ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
                            : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                        }`}
                      >
                        {st.totalAssessedConcepts > 0 ? `${masteryPct}% avg` : 'Unassessed'}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                      {st.studentEmail}
                    </div>

                    {/* Progress Bar */}
                    <div className="space-y-1 pt-1">
                      <div className="flex items-center justify-between text-[10px] text-slate-400">
                        <span>Coverage</span>
                        <span>
                          {st.totalAssessedConcepts} / {st.totalConcepts} concepts
                        </span>
                      </div>
                      <div className="w-full h-1 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full transition-all duration-300"
                          style={{
                            width: `${
                              st.totalConcepts > 0
                                ? (st.totalAssessedConcepts / st.totalConcepts) * 100
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right: Individualized Knowledge Graph Canvas */}
        <div className="lg:col-span-8 flex flex-col h-[700px]">
          {graphLoading ? (
            <div className="h-full flex items-center justify-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2 text-slate-500 text-xs">
                <Clock className="w-4 h-4 animate-spin text-indigo-600" />
                <span>Loading student individualized learning graph...</span>
              </div>
            </div>
          ) : studentGraph ? (
            <StudentKnowledgeGraph
              graph={studentGraph}
              onRefresh={() => selectedStudent && loadStudentGraph(selectedStudent.studentId)}
              isLoading={graphLoading}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 text-slate-400">
              <Users className="w-10 h-10 mb-2 text-slate-300" />
              <p className="text-sm font-semibold">Select an enrolled student to inspect their graph</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
