'use client';

import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import {
  Sparkles,
  HelpCircle,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Award,
  Layers,
  ShieldCheck,
} from 'lucide-react';
import { StudentConceptStatus, ConceptDifficulty } from '@/lib/types';

export interface StudentLearningNodeData {
  id: string;
  name: string;
  description?: string;
  category?: string;
  difficulty?: ConceptDifficulty;
  masteryScore?: number | null;
  masteryPercentage?: number | null;
  confidenceScore?: number | null;
  confidence?: number | null;
  evidenceCount?: number;
  masterySource?: string;
  status: StudentConceptStatus;
  showConfidence?: boolean;
  onSelect?: (id: string) => void;
}

const statusConfig: Record<
  StudentConceptStatus,
  {
    label: string;
    bg: string;
    border: string;
    badgeBg: string;
    badgeText: string;
    badgeBorder: string;
    barColor: string;
    icon: React.ElementType;
  }
> = {
  unassessed: {
    label: 'Unassessed',
    bg: 'bg-slate-50/90 dark:bg-slate-900/60',
    border: 'border-dashed border-slate-300 dark:border-slate-700',
    badgeBg: 'bg-slate-100 dark:bg-slate-800',
    badgeText: 'text-slate-600 dark:text-slate-400',
    badgeBorder: 'border-slate-200 dark:border-slate-700',
    barColor: 'bg-slate-300 dark:bg-slate-700',
    icon: HelpCircle,
  },
  low_mastery: {
    label: 'Low Mastery',
    bg: 'bg-rose-50/70 dark:bg-rose-950/30',
    border: 'border-rose-300 dark:border-rose-800/80',
    badgeBg: 'bg-rose-100 dark:bg-rose-900/50',
    badgeText: 'text-rose-700 dark:text-rose-300',
    badgeBorder: 'border-rose-200 dark:border-rose-800',
    barColor: 'bg-rose-500',
    icon: AlertCircle,
  },
  developing: {
    label: 'Developing',
    bg: 'bg-amber-50/70 dark:bg-amber-950/30',
    border: 'border-amber-300 dark:border-amber-800/80',
    badgeBg: 'bg-amber-100 dark:bg-amber-900/50',
    badgeText: 'text-amber-700 dark:text-amber-300',
    badgeBorder: 'border-amber-200 dark:border-amber-800',
    barColor: 'bg-amber-500',
    icon: TrendingUp,
  },
  strong: {
    label: 'Strong',
    bg: 'bg-emerald-50/70 dark:bg-emerald-950/30',
    border: 'border-emerald-300 dark:border-emerald-800/80',
    badgeBg: 'bg-emerald-100 dark:bg-emerald-900/50',
    badgeText: 'text-emerald-700 dark:text-emerald-300',
    badgeBorder: 'border-emerald-200 dark:border-emerald-800',
    barColor: 'bg-emerald-500',
    icon: CheckCircle,
  },
  high: {
    label: 'High Mastery',
    bg: 'bg-indigo-50/80 dark:bg-indigo-950/40',
    border: 'border-indigo-300 dark:border-indigo-800',
    badgeBg: 'bg-indigo-100 dark:bg-indigo-900/50',
    badgeText: 'text-indigo-700 dark:text-indigo-300',
    badgeBorder: 'border-indigo-200 dark:border-indigo-800',
    barColor: 'bg-indigo-600 dark:bg-indigo-500',
    icon: Award,
  },
};

const difficultyColors: Record<ConceptDifficulty, { bg: string; text: string; border: string }> = {
  beginner: {
    bg: 'bg-slate-100 dark:bg-slate-800',
    text: 'text-slate-700 dark:text-slate-300',
    border: 'border-slate-200 dark:border-slate-700',
  },
  intermediate: {
    bg: 'bg-sky-50 dark:bg-sky-950/60',
    text: 'text-sky-700 dark:text-sky-300',
    border: 'border-sky-200 dark:border-sky-800',
  },
  advanced: {
    bg: 'bg-purple-50 dark:bg-purple-950/60',
    text: 'text-purple-700 dark:text-purple-300',
    border: 'border-purple-200 dark:border-purple-800',
  },
};

export const StudentLearningNode = memo((props: any) => {
  const { data, selected } = props;
  const nodeData = data as StudentLearningNodeData;
  const status = nodeData.status || 'unassessed';
  const cfg = statusConfig[status] || statusConfig.unassessed;
  const StatusIcon = cfg.icon;

  const diffTier = (nodeData.difficulty || 'intermediate') as ConceptDifficulty;
  const diffStyle = difficultyColors[diffTier] || difficultyColors.intermediate;

  const isAssessed = status !== 'unassessed' && typeof nodeData.masteryScore === 'number';
  const pct = isAssessed
    ? Math.round((nodeData.masteryPercentage ?? (nodeData.masteryScore || 0) * 100))
    : null;
  const conf = isAssessed
    ? Math.round(((nodeData.confidenceScore ?? nodeData.confidence ?? 0.8) * 100))
    : null;

  const evidenceCount = nodeData.evidenceCount || 0;
  const isOverridden = nodeData.masterySource === 'faculty_override';

  return (
    <div
      onClick={() => nodeData.onSelect?.(nodeData.id)}
      className={`group relative min-w-[240px] max-w-[290px] rounded-2xl border transition-all duration-200 p-4 shadow-sm hover:shadow-lg cursor-pointer ${
        cfg.bg
      } ${cfg.border} ${
        selected
          ? 'ring-2 ring-indigo-500 shadow-indigo-500/20 scale-[1.02]'
          : 'hover:scale-[1.01]'
      }`}
    >
      {/* Target Handle (Left: incoming prerequisite) */}
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={false}
        className="w-2.5 h-2.5 !bg-indigo-500 !border-2 !border-white dark:!border-slate-900"
      />

      {/* Source Handle (Right: outgoing prerequisite) */}
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={false}
        className="w-2.5 h-2.5 !bg-indigo-500 !border-2 !border-white dark:!border-slate-900"
      />

      {/* Top Meta: Category & Difficulty */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 font-mono truncate max-w-[120px]">
          {nodeData.category || 'Core Concept'}
        </span>
        <span
          className={`text-[9px] font-semibold px-2 py-0.5 rounded-full border capitalize ${diffStyle.bg} ${diffStyle.text} ${diffStyle.border}`}
        >
          {diffTier}
        </span>
      </div>

      {/* Concept Name */}
      <h4 className="text-xs font-bold text-slate-900 dark:text-white leading-tight mb-2">
        {nodeData.name}
      </h4>

      {/* Status & Evidence Badge Row */}
      <div className="flex items-center justify-between gap-1.5 mb-3">
        <span
          className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cfg.badgeBg} ${cfg.badgeText} ${cfg.badgeBorder}`}
        >
          <StatusIcon className="w-3 h-3" />
          <span>{cfg.label}</span>
        </span>

        {isAssessed ? (
          <span className="inline-flex items-center gap-1 text-[9px] font-medium text-slate-500 dark:text-slate-400 bg-white/80 dark:bg-slate-800/80 px-1.5 py-0.5 rounded-md border border-slate-200 dark:border-slate-700">
            <Layers className="w-2.5 h-2.5 text-indigo-500" />
            <span>{evidenceCount} ev</span>
          </span>
        ) : (
          <span className="text-[9px] text-slate-400 italic">No evidence</span>
        )}
      </div>

      {/* Progress Bars & Metrics */}
      {isAssessed ? (
        <div className="space-y-2 pt-2 border-t border-slate-200/60 dark:border-slate-800/60">
          {/* Mastery Bar */}
          <div>
            <div className="flex items-center justify-between text-[10px] mb-1">
              <span className="font-semibold text-slate-700 dark:text-slate-300">Mastery</span>
              <span className="font-bold text-slate-900 dark:text-white">{pct}%</span>
            </div>
            <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full ${cfg.barColor} rounded-full transition-all duration-500`}
                style={{ width: `${Math.min(100, Math.max(0, pct || 0))}%` }}
              />
            </div>
          </div>

          {/* Confidence Meter (if enabled or visible) */}
          {nodeData.showConfidence !== false && conf !== null && (
            <div>
              <div className="flex items-center justify-between text-[9px] mb-0.5 text-slate-500 dark:text-slate-400">
                <span className="flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5 text-sky-500" />
                  Confidence
                </span>
                <span className="font-semibold">{conf}%</span>
              </div>
              <div className="w-full h-1 bg-slate-100 dark:bg-slate-800/80 rounded-full overflow-hidden">
                <div
                  className="h-full bg-sky-500 dark:bg-sky-400 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, conf))}%` }}
                />
              </div>
            </div>
          )}

          {/* Source indicator */}
          {isOverridden && (
            <div className="flex items-center gap-1 text-[9px] text-purple-600 dark:text-purple-400 pt-0.5">
              <ShieldCheck className="w-3 h-3" />
              <span className="font-medium">Faculty Overridden</span>
            </div>
          )}
        </div>
      ) : (
        <div className="pt-2 border-t border-slate-200/50 dark:border-slate-800/50">
          <div className="w-full h-1.5 bg-slate-200/60 dark:bg-slate-800/60 rounded-full overflow-hidden">
            <div className="h-full w-0 bg-transparent" />
          </div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1.5 text-center">
            Click to view prerequisite details
          </p>
        </div>
      )}
    </div>
  );
});

StudentLearningNode.displayName = 'StudentLearningNode';
