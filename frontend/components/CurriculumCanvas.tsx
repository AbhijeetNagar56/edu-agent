'use client';

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Connection,
  Edge,
  Node,
  MarkerType,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Save,
  Plus,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Trash2,
  Layers,
  Info,
} from 'lucide-react';
import { Concept, ConceptEdge } from '@/lib/types';
import { CurriculumNode } from './CurriculumNode';
import {
  createConceptEdge,
  deleteConceptEdge,
  saveCurriculumLayout,
  fetchCurriculumGraph,
} from '@/lib/storage';

interface CurriculumCanvasProps {
  courseId: string;
  initialConcepts: Concept[];
  initialEdges: ConceptEdge[];
  onEditConcept: (conceptId: string) => void;
  onAddConcept: (pos?: { posX: number; posY: number }) => void;
}

export function CurriculumCanvas({
  courseId,
  initialConcepts,
  initialEdges,
  onEditConcept,
  onAddConcept,
}: CurriculumCanvasProps) {
  const nodeTypes: any = useMemo(() => ({ curriculumConcept: CurriculumNode }), []);

  const convertConceptsToNodes = useCallback(
    (concepts: Concept[]): Node[] =>
      concepts.map((c) => ({
        id: c.id,
        type: 'curriculumConcept',
        position: { x: c.posX || 100, y: c.posY || 100 },
        data: {
          id: c.id,
          name: c.name,
          description: c.description,
          category: c.category,
          difficulty: c.difficulty,
          masteryPercentage: c.masteryPercentage,
          onEdit: onEditConcept,
        },
      })),
    [onEditConcept]
  );

  const convertEdgesToFlowEdges = useCallback(
    (edges: ConceptEdge[]): Edge[] =>
      edges.map((e) => ({
        id: e.id,
        source: e.fromConcept,
        target: e.toConcept,
        animated: true,
        style: { stroke: '#6366f1', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#6366f1',
          width: 16,
          height: 16,
        },
      })),
    []
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(convertConceptsToNodes(initialConcepts));
  const [edges, setEdges, onEdgesChange] = useEdgesState(convertEdgesToFlowEdges(initialEdges));

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [alertError, setAlertError] = useState<string | null>(null);

  // Sync when initialConcepts or initialEdges change (e.g. after modal operations)
  useEffect(() => {
    setNodes(convertConceptsToNodes(initialConcepts));
  }, [initialConcepts, convertConceptsToNodes, setNodes]);

  useEffect(() => {
    setEdges(convertEdgesToFlowEdges(initialEdges));
  }, [initialEdges, convertEdgesToFlowEdges, setEdges]);

  // Frontend Cycle Detection via DFS
  const checkHasCycle = useCallback(
    (sourceId: string, targetId: string, currentEdges: Edge[]): boolean => {
      if (sourceId === targetId) return true;

      // Check if a path from targetId to sourceId already exists
      const adj = new Map<string, string[]>();
      for (const e of currentEdges) {
        if (!adj.has(e.source)) adj.set(e.source, []);
        adj.get(e.source)!.push(e.target);
      }

      const visited = new Set<string>();
      const queue = [targetId];

      while (queue.length > 0) {
        const curr = queue.shift()!;
        if (curr === sourceId) return true;
        if (visited.has(curr)) continue;
        visited.add(curr);

        const neighbors = adj.get(curr) || [];
        for (const next of neighbors) {
          if (!visited.has(next)) {
            queue.push(next);
          }
        }
      }

      return false;
    },
    []
  );

  const onConnect = useCallback(
    async (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      setAlertError(null);

      // 1. Self Loop
      if (connection.source === connection.target) {
        setAlertError('A concept cannot have a prerequisite connection to itself.');
        return;
      }

      // 2. Duplicate Edge
      const isDuplicate = edges.some(
        (e) => e.source === connection.source && e.target === connection.target
      );
      if (isDuplicate) {
        setAlertError('This prerequisite relationship already exists.');
        return;
      }

      // 3. Cycle Detection
      if (checkHasCycle(connection.source, connection.target, edges)) {
        setAlertError(
          'Cycle detected: Connecting this prerequisite forms a circular dependency in the curriculum DAG.'
        );
        return;
      }

      // 4. Persist to Backend/Database
      try {
        const createdEdge = await createConceptEdge(courseId, connection.source, connection.target);
        const flowEdge: Edge = {
          id: createdEdge.id,
          source: createdEdge.fromConcept,
          target: createdEdge.toConcept,
          animated: true,
          style: { stroke: '#6366f1', strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#6366f1',
            width: 16,
            height: 16,
          },
        };
        setEdges((eds) => addEdge(flowEdge, eds));
      } catch (err: any) {
        setAlertError(err.message || 'Failed to establish prerequisite edge.');
      }
    },
    [courseId, edges, checkHasCycle, setEdges]
  );

  const onEdgesDelete = useCallback(
    async (deletedEdges: Edge[]) => {
      for (const e of deletedEdges) {
        try {
          await deleteConceptEdge(courseId, e.id);
        } catch (err: any) {
          console.error(`Failed to delete edge ${e.id}:`, err);
        }
      }
    },
    [courseId]
  );

  const handleSaveLayout = async () => {
    try {
      setIsSaving(true);
      setAlertError(null);
      setSaveSuccess(false);

      const positions = nodes.map((n) => ({
        id: n.id,
        posX: Math.round(n.position.x),
        posY: Math.round(n.position.y),
      }));

      await saveCurriculumLayout(courseId, { positions });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setAlertError(err.message || 'Failed to save graph layout.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReload = async () => {
    try {
      setAlertError(null);
      const graph = await fetchCurriculumGraph(courseId);
      setNodes(convertConceptsToNodes(graph.concepts));
      setEdges(convertEdgesToFlowEdges(graph.edges));
    } catch (err: any) {
      setAlertError(err.message || 'Failed to reload curriculum graph.');
    }
  };

  return (
    <div className="relative w-full h-[650px] rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 overflow-hidden shadow-xs flex flex-col">
      {/* Top Action Toolbar */}
      <div className="absolute top-4 left-4 right-4 z-10 flex flex-wrap items-center justify-between gap-3 pointer-events-none">
        {/* Left: Direction legend & Helper */}
        <div className="pointer-events-auto flex items-center gap-2 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md px-3.5 py-1.5 rounded-xl border border-slate-200/80 dark:border-slate-800/80 shadow-xs text-xs text-slate-600 dark:text-slate-300">
          <Info className="w-3.5 h-3.5 text-blue-500" />
          <span>
            Prerequisite Direction:{' '}
            <strong className="font-semibold text-slate-900 dark:text-white">
              [Left Node] → [Right Node]
            </strong>
          </span>
        </div>

        {/* Right: Actions */}
        <div className="pointer-events-auto flex items-center gap-2">
          <button
            onClick={() => onAddConcept({ posX: 300, posY: 200 })}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-xs transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Concept</span>
          </button>

          <button
            onClick={handleSaveLayout}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-xs transition disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5 text-indigo-600" />
            <span>{isSaving ? 'Saving...' : 'Save Layout'}</span>
          </button>

          <button
            onClick={handleReload}
            title="Reload canonical graph from database"
            className="p-1.5 text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-xs transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Notification Pill (Top Center) */}
      <div className="absolute top-16 left-1/2 -translate-x-1/2 z-20 pointer-events-none w-full max-w-md px-4">
        {saveSuccess && (
          <div className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 text-white text-xs font-medium shadow-lg animate-in fade-in slide-in-from-top-2 duration-200 pointer-events-auto">
            <CheckCircle2 className="w-4 h-4" />
            <span>Curriculum graph layout persisted to database.</span>
          </div>
        )}

        {alertError && (
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-rose-600 text-white text-xs font-medium shadow-lg animate-in fade-in slide-in-from-top-2 duration-200 pointer-events-auto">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{alertError}</span>
            </div>
            <button
              onClick={() => setAlertError(null)}
              className="text-xs uppercase font-mono tracking-wider opacity-80 hover:opacity-100 underline"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Empty State */}
      {nodes.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
          <div className="w-14 h-14 rounded-2xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 flex items-center justify-center text-blue-600 mb-3 shadow-xs">
            <Layers className="w-7 h-7" />
          </div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-1">
            No Curriculum Concepts Defined
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mb-4 leading-relaxed">
            This course does not have any canonical concepts yet. Add foundational concepts and connect them via prerequisite edges to construct the learning graph.
          </p>
          <button
            onClick={() => onAddConcept({ posX: 250, posY: 200 })}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-xs transition"
          >
            <Plus className="w-4 h-4" />
            <span>Add First Concept</span>
          </button>
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onEdgesDelete={onEdgesDelete}
          fitView
          attributionPosition="bottom-right"
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
          <Controls className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-xs" />
          <MiniMap
            zoomable
            pannable
            className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xs"
          />
        </ReactFlow>
      )}
    </div>
  );
}
