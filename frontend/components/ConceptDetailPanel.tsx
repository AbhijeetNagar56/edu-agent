'use client';

import React, { useEffect } from 'react';
import {
  X,
  Sparkles,
  BookOpen,
  Award,
  Layers,
  Clock,
  ShieldCheck,
  FileText,
  Quote,
  HelpCircle,
  AlertCircle,
  TrendingUp,
  CheckCircle2,
  Calendar,
  ExternalLink,
} from 'lucide-react';
import { StudentCurriculumConcept, StudentConceptStatus } from '@/lib/types';

interface ConceptDetailPanelProps {
  concept: StudentCurriculumConcept | null;
  onClose: () => void;
  onViewAssignment?: (assignmentId: string) => void;
}

const statusBadgeConfig: Record<
  StudentConceptStatus,
  { label: string; bg: string; text: string; border: string; icon: React.ElementType }
> = {
  unassessed: {
    label: 'Unassessed',
    bg: 'bg-slate-100 dark:bg-slate-800',
    text: 'text-slate-600 dark:text-slate-300',
    border: 'border-slate-300 dark:border-slate-700',
    icon: HelpCircle,
  },
  low_mastery: {
    label: 'Low Mastery (0% - 39%)',
    bg: 'bg-rose-100 dark:bg-rose-950/60',
    text: 'text-rose-700 dark:text-rose-300',
    border: 'border-rose-300 dark:border-rose-800',
    icon: AlertCircle,
  },
  developing: {
    label: 'Developing (40% - 69%)',
    bg: 'bg-amber-100 dark:bg-amber-950/60',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-300 dark:border-amber-800',
    icon: TrendingUp,
  },
  strong: {
    label: 'Strong (70% - 89%)',
    bg: 'bg-emerald-100 dark:bg-emerald-950/60',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-300 dark:border-emerald-800',
    icon: CheckCircle2,
  },
  high: {
    label: 'High Mastery (90% - 100%)',
    bg: 'bg-indigo-100 dark:bg-indigo-950/60',
    text: 'text-indigo-700 dark:text-indigo-300',
    border: 'border-indigo-300 dark:border-indigo-800',
    icon: Award,
  },
};

export function ConceptDetailPanel({ concept, onClose, onViewAssignment }: ConceptDetailPanelProps) {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!concept) return null;

  const status = concept.status || 'unassessed';
  const cfg = statusBadgeConfig[status] || statusBadgeConfig.unassessed;
  const StatusIcon = cfg.icon;

  const isAssessed = status !== 'unassessed' && typeof concept.masteryScore === 'number';
  const pct = isAssessed
    ? Math.round(concept.masteryPercentage ?? (concept.masteryScore || 0) * 100)
    : null;
  const conf = isAssessed
    ? Math.round((concept.confidenceScore ?? concept.confidence ?? 0.8) * 100)
    : null;

  const recentFeedback = concept.feedback?.recentFeedback;
  const excerpts = concept.feedback?.evidenceExcerpts || [];
  const assignments = concept.feedback?.associatedAssignments || [];
  const history = concept.feedback?.history || [];

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-sm flex justify-end transition-opacity animate-in fade-in duration-200">
      {/* Click outside backdrop */}
      <div className="flex-1" onClick={onClose} />

      {/* Slide-over Container */}
      <div className="w-full max-w-xl bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 h-full flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="p-6 border-b border-slate-200 dark:border-slate-800 flex items-start justify-between gap-4 bg-slate-50/50 dark:bg-slate-900/50">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-500 bg-slate-200/60 dark:bg-slate-800 px-2 py-0.5 rounded">
                {concept.category || 'Core'}
              </span>
              <span className="text-[10px] font-semibold text-slate-500 capitalize bg-slate-200/60 dark:bg-slate-800 px-2 py-0.5 rounded">
                {concept.difficulty || 'intermediate'}
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              {concept.name}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition"
            aria-label="Close details"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Pedagogical Description */}
          {concept.description && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                Concept Overview
              </h3>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-800/40 p-3.5 rounded-xl border border-slate-200/70 dark:border-slate-800">
                {concept.description}
              </p>
            </div>
          )}

          {/* Mastery State Card */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 bg-gradient-to-br from-slate-50/80 to-slate-100/30 dark:from-slate-800/40 dark:to-slate-900/40 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span
                className={`inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full border ${cfg.bg} ${cfg.text} ${cfg.border}`}
              >
                <StatusIcon className="w-3.5 h-3.5" />
                <span>{cfg.label}</span>
              </span>

              {concept.masterySource === 'faculty_override' && (
                <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Faculty Overridden
                </span>
              )}
            </div>

            {/* Score Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="bg-white dark:bg-slate-800 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
                <div className="text-[10px] text-slate-500 font-medium">Mastery Score</div>
                <div className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {isAssessed ? `${pct}%` : 'Unassessed'}
                </div>
                {isAssessed && (
                  <div className="text-[10px] text-slate-400 font-mono">
                    {concept.masteryScore?.toFixed(4)}
                  </div>
                )}
              </div>

              <div className="bg-white dark:bg-slate-800 p-3 rounded-xl border border-slate-200 dark:border-slate-700">
                <div className="text-[10px] text-slate-500 font-medium flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-sky-500" />
                  Confidence
                </div>
                <div className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {isAssessed ? `${conf}%` : 'N/A'}
                </div>
                {isAssessed && (
                  <div className="text-[10px] text-slate-400 font-mono">
                    {(concept.confidenceScore ?? concept.confidence ?? 0.8).toFixed(4)}
                  </div>
                )}
              </div>

              <div className="bg-white dark:bg-slate-800 p-3 rounded-xl border border-slate-200 dark:border-slate-700 col-span-2 sm:col-span-1">
                <div className="text-[10px] text-slate-500 font-medium flex items-center gap-1">
                  <Layers className="w-3 h-3 text-indigo-500" />
                  Evidence Count
                </div>
                <div className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {concept.evidenceCount || 0}
                </div>
                <div className="text-[10px] text-slate-400">
                  {concept.evidenceCount === 1 ? '1 assessment' : `${concept.evidenceCount || 0} assessments`}
                </div>
              </div>
            </div>

            {concept.lastEvaluatedAt && (
              <div className="text-[11px] text-slate-500 flex items-center gap-1.5 pt-1">
                <Clock className="w-3 h-3 text-slate-400" />
                <span>Last updated: {new Date(concept.lastEvaluatedAt).toLocaleString()}</span>
              </div>
            )}
          </div>

          {/* Genuine AI Feedback Section */}
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              Latest Concept-Level Feedback
            </h3>
            {recentFeedback ? (
              <div className="bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800/80 rounded-xl p-4 text-sm text-slate-800 dark:text-slate-200 leading-relaxed shadow-sm">
                <p className="whitespace-pre-wrap">{recentFeedback}</p>
              </div>
            ) : (
              <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 rounded-xl p-4 text-xs text-slate-500 leading-relaxed text-center">
                <HelpCircle className="w-6 h-6 mx-auto mb-1 text-slate-400" />
                <p className="font-medium text-slate-600 dark:text-slate-300">No evaluation feedback yet</p>
                <p className="mt-1 text-[11px]">
                  Submit work for an assignment covering this concept to receive AI-driven feedback and establish mastery.
                </p>
              </div>
            )}
          </div>

          {/* Direct Evidence Excerpts */}
          {excerpts.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Quote className="w-3.5 h-3.5 text-amber-500" />
                Direct Evidence from Submissions
              </h3>
              <div className="space-y-2.5">
                {excerpts.map((excerpt, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-amber-50/50 dark:bg-amber-950/20 border-l-4 border-amber-400 rounded-r-xl text-xs font-mono text-slate-700 dark:text-slate-300 leading-relaxed overflow-x-auto"
                  >
                    <span className="text-amber-500 font-bold mr-1">&ldquo;</span>
                    {excerpt}
                    <span className="text-amber-500 font-bold ml-1">&rdquo;</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Associated Assignments */}
          {assignments.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-blue-500" />
                Mapped Assignments
              </h3>
              <div className="space-y-2">
                {assignments.map((assign) => (
                  <div
                    key={assign.id}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/60 flex items-center justify-between gap-3 hover:border-slate-300 transition"
                  >
                    <div>
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                        {assign.title}
                      </h4>
                      {assign.dueDate && (
                        <p className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                          <Calendar className="w-2.5 h-2.5" />
                          Due: {new Date(assign.dueDate).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    {onViewAssignment && (
                      <button
                        onClick={() => onViewAssignment(assign.id)}
                        className="text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-0.5"
                      >
                        <span>View</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evaluation Progression History */}
          {history.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                Evaluation Progression History ({history.length})
              </h3>
              <div className="space-y-3">
                {history.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="font-bold text-slate-900 dark:text-white">
                        {item.assignmentTitle || 'Assignment'}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                          {Math.round((item.scoreRatio || 0) * 100)}% score
                        </span>
                        <span className="text-[10px] text-sky-600 dark:text-sky-400">
                          {Math.round((item.confidence || 0.8) * 100)}% conf
                        </span>
                      </div>
                    </div>

                    {item.feedbackText && (
                      <p className="text-slate-600 dark:text-slate-300 text-[11px] leading-relaxed italic bg-white dark:bg-slate-900/60 p-2 rounded-lg border border-slate-200/50 dark:border-slate-800/50">
                        {item.feedbackText}
                      </p>
                    )}

                    <div className="flex items-center justify-between text-[10px] text-slate-400">
                      <span>Sub: {item.submissionId.slice(0, 10)}...</span>
                      {item.evaluatedAt && (
                        <span>{new Date(item.evaluatedAt).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/60 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold rounded-xl bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition"
          >
            Close Details
          </button>
        </div>
      </div>
    </div>
  );
}
