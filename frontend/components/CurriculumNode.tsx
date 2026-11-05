'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Edit2, Sparkles } from 'lucide-react';
import { ConceptDifficulty } from '@/lib/types';

export interface CurriculumNodeData {
  id: string;
  name: string;
  description?: string;
  category?: string;
  difficulty?: ConceptDifficulty;
  masteryPercentage?: number;
  onEdit?: (id: string) => void;
}

const difficultyColors: Record<ConceptDifficulty, { bg: string; text: string; border: string }> = {
  beginner: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/60',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-200 dark:border-emerald-800',
  },
  intermediate: {
    bg: 'bg-amber-50 dark:bg-amber-950/60',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800',
  },
  advanced: {
    bg: 'bg-purple-50 dark:bg-purple-950/60',
    text: 'text-purple-700 dark:text-purple-300',
    border: 'border-purple-200 dark:border-purple-800',
  },
};

export const CurriculumNode = memo((props: any) => {
  const { data, selected } = props;
  const nodeData = data as CurriculumNodeData;
  const diffTier = (nodeData.difficulty || 'intermediate') as ConceptDifficulty;
  const colors = difficultyColors[diffTier] || difficultyColors.intermediate;

  return (
    <div
      className={`group relative min-w-[220px] max-w-[280px] rounded-2xl bg-white dark:bg-slate-900 border transition-all duration-150 p-4 shadow-sm hover:shadow-md ${
        selected
          ? 'border-blue-500 ring-2 ring-blue-500/20 shadow-blue-500/10'
          : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
      }`}
    >
      {/* Target Handle (Incoming Prerequisite: Left) */}
      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-blue-500 border-2 border-white dark:border-slate-900 transition-transform group-hover:scale-125"
      />

      {/* Header: Category & Difficulty */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 font-mono truncate max-w-[120px]">
          {nodeData.category || 'Core'}
        </span>
        <span
          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border capitalize ${colors.bg} ${colors.text} ${colors.border}`}
        >
          {diffTier}
        </span>
      </div>

      {/* Title */}
      <div className="flex items-start justify-between gap-1">
        <h4 className="text-xs font-bold text-slate-900 dark:text-white leading-tight">
          {nodeData.name}
        </h4>
        {nodeData.onEdit && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              nodeData.onEdit?.(nodeData.id);
            }}
            title="Edit concept details"
            className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition"
          >
            <Edit2 className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* Description Snippet */}
      {nodeData.description && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
          {nodeData.description}
        </p>
      )}

      {/* Optional Mastery pill (if viewing with student overlay) */}
      {typeof nodeData.masteryPercentage === 'number' && (
        <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-medium">
            <Sparkles className="w-3 h-3 text-amber-500" />
            <span>Mastery:</span>
          </div>
          <span className="text-xs font-bold font-mono text-blue-600 dark:text-blue-400">
            {nodeData.masteryPercentage}%
          </span>
        </div>
      )}

      {/* Source Handle (Outgoing Dependent: Right) */}
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-indigo-600 border-2 border-white dark:border-slate-900 transition-transform group-hover:scale-125"
      />
    </div>
  );
});

CurriculumNode.displayName = 'CurriculumNode';
