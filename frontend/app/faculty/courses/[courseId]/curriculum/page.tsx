'use client';

import React, { useState, useEffect, useCallback, use } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  BookOpen,
  Layers,
  GitBranch,
  ShieldCheck,
  Clock,
  Plus,
  AlertCircle,
  Sparkles,
  Users,
} from 'lucide-react';
import { Course, Concept, ConceptEdge, CurriculumGraph } from '@/lib/types';
import { fetchCourseDetails, fetchCurriculumGraph } from '@/lib/storage';
import { CurriculumCanvas } from '@/components/CurriculumCanvas';
import { ConceptModal } from '@/components/ConceptModal';
import { StatCard } from '@/components/StatCard';

interface PageProps {
  params: Promise<{ courseId: string }>;
}

export default function CourseCurriculumPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const courseId = resolvedParams.courseId;

  const [course, setCourse] = useState<Course | null>(null);
  const [graph, setGraph] = useState<CurriculumGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Concept Modal State
  const [isConceptModalOpen, setIsConceptModalOpen] = useState(false);
  const [editingConcept, setEditingConcept] = useState<Concept | null>(null);
  const [newConceptPosition, setNewConceptPosition] = useState<{ posX: number; posY: number }>({
    posX: 250,
    posY: 200,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const [courseData, graphData] = await Promise.all([
        fetchCourseDetails(courseId),
        fetchCurriculumGraph(courseId),
      ]);
      setCourse(courseData);
      setGraph(graphData);
    } catch (err: any) {
      console.error(err);
      setErrorMessage(err.message || 'Failed to load course curriculum.');
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleOpenAddConcept = (pos?: { posX: number; posY: number }) => {
    setEditingConcept(null);
    if (pos) {
      setNewConceptPosition(pos);
    }
    setIsConceptModalOpen(true);
  };

  const handleOpenEditConcept = (conceptId: string) => {
    if (!graph) return;
    const found = graph.concepts.find((c) => c.id === conceptId);
    if (found) {
      setEditingConcept(found);
      setIsConceptModalOpen(true);
    }
  };

  const handleConceptSaved = (savedConcept: Concept) => {
    if (!graph) return;
    const exists = graph.concepts.some((c) => c.id === savedConcept.id);
    if (exists) {
      setGraph({
        ...graph,
        concepts: graph.concepts.map((c) => (c.id === savedConcept.id ? savedConcept : c)),
      });
    } else {
      setGraph({
        ...graph,
        concepts: [...graph.concepts, savedConcept],
      });
    }
  };

  const handleConceptDeleted = (deletedId: string) => {
    if (!graph) return;
    setGraph({
      ...graph,
      concepts: graph.concepts.filter((c) => c.id !== deletedId),
      edges: graph.edges.filter((e) => e.fromConcept !== deletedId && e.toConcept !== deletedId),
    });
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-2.5 text-slate-500 text-sm">
          <Clock className="w-5 h-5 animate-spin text-blue-600" />
          <span>Loading Canonical Curriculum Graph...</span>
        </div>
      </div>
    );
  }

  if (errorMessage || !course || !graph) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12">
        <div className="p-6 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-bold">Failed to Load Curriculum</h3>
              <p className="text-xs mt-1 text-rose-700 dark:text-rose-400">
                {errorMessage || 'Course or curriculum graph not found. Please verify ownership and course ID.'}
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

  const conceptsCount = graph.concepts.length;
  const edgesCount = graph.edges.length;
  const beginnerCount = graph.concepts.filter((c) => c.difficulty === 'beginner').length;
  const intermediateCount = graph.concepts.filter((c) => c.difficulty === 'intermediate').length;
  const advancedCount = graph.concepts.filter((c) => c.difficulty === 'advanced').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header & Breadcrumb */}
      <div>
        <Link
          href="/faculty"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition mb-3"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Faculty Dashboard</span>
        </Link>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                {course.code}
              </span>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                {course.name}
              </h1>
            </div>
            {course.description && (
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1.5 max-w-3xl leading-relaxed">
                {course.description}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Link
              href={`/faculty/courses/${course.id}/students`}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 border border-indigo-200 dark:border-indigo-800 rounded-xl transition"
            >
              <Users className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span>Student Learning Graphs</span>
            </Link>
            <button
              onClick={() => handleOpenAddConcept({ posX: 200, posY: 200 })}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-xs transition"
            >
              <Plus className="w-4 h-4" />
              <span>Add Concept</span>
            </button>
          </div>
        </div>
      </div>

      {/* Curriculum Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Total Concepts"
          value={conceptsCount}
          icon={Layers}
          iconColor="text-blue-600 dark:text-blue-400"
          iconBg="bg-blue-50 dark:bg-blue-950/50"
        />
        <StatCard
          title="Prerequisite Edges"
          value={edgesCount}
          icon={GitBranch}
          iconColor="text-indigo-600 dark:text-indigo-400"
          iconBg="bg-indigo-50 dark:bg-indigo-950/50"
        />
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
              Difficulty Distribution
            </span>
            <Sparkles className="w-4 h-4 text-amber-500" />
          </div>
          <div className="flex items-center gap-3 text-xs font-mono font-semibold pt-1">
            <span className="text-emerald-600 dark:text-emerald-400">
              {beginnerCount} Beginner
            </span>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span className="text-amber-600 dark:text-amber-400">
              {intermediateCount} Intermediate
            </span>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span className="text-purple-600 dark:text-purple-400">
              {advancedCount} Advanced
            </span>
          </div>
        </div>
      </div>

      {/* Interactive Curriculum Canvas */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              Curriculum Prerequisite Graph (DAG)
            </h2>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              Drag from right port to left port to define prerequisites
            </span>
          </div>
        </div>

        <CurriculumCanvas
          courseId={course.id}
          initialConcepts={graph.concepts}
          initialEdges={graph.edges}
          onEditConcept={handleOpenEditConcept}
          onAddConcept={handleOpenAddConcept}
        />
      </div>

      {/* Concept Add/Edit Modal */}
      <ConceptModal
        isOpen={isConceptModalOpen}
        onClose={() => setIsConceptModalOpen(false)}
        courseId={course.id}
        concept={editingConcept}
        defaultPosition={newConceptPosition}
        onConceptSaved={handleConceptSaved}
        onConceptDeleted={handleConceptDeleted}
      />
    </div>
  );
}
