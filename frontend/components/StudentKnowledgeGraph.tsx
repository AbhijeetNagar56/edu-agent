'use client';

import React, { useState, useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  MarkerType,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Search,
  Filter,
  Sparkles,
  Layers,
  HelpCircle,
  AlertCircle,
  TrendingUp,
  CheckCircle2,
  Award,
  BarChart3,
  RefreshCw,
  Eye,
  EyeOff,
} from 'lucide-react';
import {
  StudentCurriculumGraph,
  StudentCurriculumConcept,
  StudentConceptStatus,
} from '@/lib/types';
import { StudentLearningNode } from './StudentLearningNode';
import { ConceptDetailPanel } from './ConceptDetailPanel';

interface StudentKnowledgeGraphProps {
  graph: StudentCurriculumGraph;
  onRefresh?: () => void;
  isLoading?: boolean;
  onViewAssignment?: (assignmentId: string) => void;
}

const nodeTypes: any = {
  studentLearningConcept: StudentLearningNode,
};

type FilterStatus = 'all' | StudentConceptStatus;

export function StudentKnowledgeGraph({
  graph,
  onRefresh,
  isLoading,
  onViewAssignment,
}: StudentKnowledgeGraphProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');
  const [showConfidence, setShowConfidence] = useState(true);
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(null);

  // Statistics calculation
  const totalConcepts = graph.concepts.length;
  const assessedConcepts = graph.concepts.filter(
    (c) => c.status !== 'unassessed' && typeof c.masteryScore === 'number'
  );
  const unassessedCount = totalConcepts - assessedConcepts.length;
  const avgMastery =
    assessedConcepts.length > 0
      ? Math.round(
          (assessedConcepts.reduce((acc, c) => acc + (c.masteryScore || 0), 0) /
            assessedConcepts.length) *
            100
        )
      : 0;

  // Status counts for filter pills
  const statusCounts = useMemo(() => {
    const counts: Record<FilterStatus, number> = {
      all: totalConcepts,
      unassessed: 0,
      low_mastery: 0,
      developing: 0,
      strong: 0,
      high: 0,
    };
    graph.concepts.forEach((c) => {
      const st = c.status || 'unassessed';
      if (counts[st] !== undefined) counts[st]++;
    });
    return counts;
  }, [graph.concepts, totalConcepts]);

  // Selected concept for detail panel
  const selectedConcept = useMemo(
    () => graph.concepts.find((c) => c.id === selectedConceptId) || null,
    [graph.concepts, selectedConceptId]
  );

  const handleSelectConcept = useCallback((conceptId: string) => {
    setSelectedConceptId(conceptId);
  }, []);

  // Filter and build React Flow Nodes
  const nodes: Node[] = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return graph.concepts.map((concept) => {
      const matchesSearch =
        !query ||
        concept.name.toLowerCase().includes(query) ||
        (concept.category && concept.category.toLowerCase().includes(query));

      const matchesStatus =
        statusFilter === 'all' || concept.status === statusFilter;

      const isDimmed = !matchesSearch || !matchesStatus;

      return {
        id: concept.id,
        type: 'studentLearningConcept',
        position: { x: concept.posX || 100, y: concept.posY || 100 },
        data: {
          id: concept.id,
          name: concept.name,
          description: concept.description,
          category: concept.category,
          difficulty: concept.difficulty,
          masteryScore: concept.masteryScore,
          masteryPercentage: concept.masteryPercentage,
          confidenceScore: concept.confidenceScore,
          confidence: concept.confidence,
          evidenceCount: concept.evidenceCount,
          masterySource: concept.masterySource,
          status: concept.status || 'unassessed',
          showConfidence,
          onSelect: handleSelectConcept,
        },
        selected: selectedConceptId === concept.id,
        style: {
          opacity: isDimmed ? 0.25 : 1.0,
          transition: 'opacity 0.2s ease-in-out',
        },
      };
    });
  }, [
    graph.concepts,
    searchQuery,
    statusFilter,
    showConfidence,
    selectedConceptId,
    handleSelectConcept,
  ]);

  // Convert Prerequisite Edges
  const edges: Edge[] = useMemo(() => {
    return graph.edges.map((e) => ({
      id: e.id,
      source: e.fromConcept || e.sourceConceptId || '',
      target: e.toConcept || e.targetConceptId || '',
      animated: true,
      style: { stroke: '#6366f1', strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#6366f1',
        width: 16,
        height: 16,
      },
    }));
  }, [graph.edges]);

  // MiniMap node color logic
  const minimapNodeColor = (node: Node) => {
    const data = node.data as any;
    switch (data?.status) {
      case 'high':
        return '#4f46e5';
      case 'strong':
        return '#10b981';
      case 'developing':
        return '#f59e0b';
      case 'low_mastery':
        return '#f43f5e';
      default:
        return '#94a3b8';
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-slate-50 dark:bg-slate-950 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
      {/* Top Banner & Analytics Summary */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2.5 py-0.5 rounded-md border border-indigo-200 dark:border-indigo-800">
              {graph.courseCode}
            </span>
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              {graph.courseName}
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Student: <span className="font-semibold text-slate-700 dark:text-slate-300">{graph.studentName}</span>{' '}
            ({graph.studentEmail})
          </p>
        </div>

        {/* Aggregate Stats Ribbon */}
        <div className="flex items-center gap-3 sm:gap-6 flex-wrap bg-slate-50 dark:bg-slate-800/60 px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700/80">
          <div>
            <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Concepts</div>
            <div className="text-sm font-bold text-slate-900 dark:text-white">
              {assessedConcepts.length} / {totalConcepts}
            </div>
          </div>
          <div className="w-px h-6 bg-slate-200 dark:bg-slate-700" />
          <div>
            <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider">Unassessed</div>
            <div className="text-sm font-bold text-slate-500">
              {unassessedCount}
            </div>
          </div>
          <div className="w-px h-6 bg-slate-200 dark:bg-slate-700" />
          <div>
            <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider flex items-center gap-1">
              <BarChart3 className="w-3 h-3 text-indigo-500" />
              Avg Mastery
            </div>
            <div className="text-sm font-bold text-indigo-600 dark:text-indigo-400">
              {assessedConcepts.length > 0 ? `${avgMastery}%` : '—'}
            </div>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              title="Refresh graph data"
              className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 flex-wrap">
        {/* Search */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search concepts or category..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:text-white"
          />
        </div>

        {/* Status Filter Buttons */}
        <div className="flex items-center gap-1.5 flex-wrap w-full sm:w-auto">
          {(
            [
              { key: 'all', label: 'All' },
              { key: 'unassessed', label: 'Unassessed' },
              { key: 'low_mastery', label: 'Low (<40%)' },
              { key: 'developing', label: 'Developing' },
              { key: 'strong', label: 'Strong' },
              { key: 'high', label: 'High (≥90%)' },
            ] as const
          ).map(({ key, label }) => {
            const active = statusFilter === key;
            const count = statusCounts[key];
            return (
              <button
                key={key}
                onClick={() => setStatusFilter(key)}
                className={`text-[11px] font-medium px-2.5 py-1 rounded-lg border transition flex items-center gap-1.5 ${
                  active
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                    : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                <span>{label}</span>
                <span
                  className={`text-[9px] px-1 py-0.2 rounded-full ${
                    active ? 'bg-indigo-700 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-300'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}

          {/* Toggle Confidence */}
          <button
            onClick={() => setShowConfidence(!showConfidence)}
            title={showConfidence ? 'Hide confidence bars' : 'Show confidence bars'}
            className={`p-1.5 rounded-lg border text-xs flex items-center gap-1 transition ${
              showConfidence
                ? 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800'
                : 'bg-slate-50 dark:bg-slate-800 text-slate-500 border-slate-200 dark:border-slate-700'
            }`}
          >
            {showConfidence ? <Eye className="w-3.5 h-3.5 text-sky-500" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span className="hidden md:inline text-[10px] font-medium">Confidence</span>
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 w-full relative min-h-[500px]">
        {graph.concepts.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center text-slate-500">
            <Layers className="w-10 h-10 text-slate-400 mb-2" />
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">
              No Concepts in Curriculum
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mt-1">
              The faculty has not added concepts to this course curriculum graph yet.
            </p>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.25 }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={true}
            minZoom={0.2}
            maxZoom={2.0}
            className="bg-slate-50/50 dark:bg-slate-950/50"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#94a3b8" />
            <Controls showInteractive={false} className="!bg-white dark:!bg-slate-900 !border-slate-200 dark:!border-slate-800" />
            <MiniMap
              nodeColor={minimapNodeColor}
              className="!bg-white/80 dark:!bg-slate-900/80 !border-slate-200 dark:!border-slate-800 rounded-xl overflow-hidden shadow-sm"
              maskColor="rgba(0, 0, 0, 0.1)"
            />
          </ReactFlow>
        )}
      </div>

      {/* Concept Detail Slide-over / Modal */}
      <ConceptDetailPanel
        concept={selectedConcept}
        onClose={() => setSelectedConceptId(null)}
        onViewAssignment={onViewAssignment}
      />
    </div>
  );
}
