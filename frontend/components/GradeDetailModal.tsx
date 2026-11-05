'use client';

import React from 'react';
import {
  FileText,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Download,
  Calendar,
  Layers,
  ArrowRight,
  Quote,
  BrainCircuit,
  CheckCheck
} from 'lucide-react';
import { Submission } from '../lib/types';
import { Modal } from './Modal';
import { getScoreColor } from '../lib/utils';
import { StatusBadge } from './Badge';

interface GradeDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  submission: Submission | null;
  onOpenOverride?: (sub: Submission) => void;
  isFacultyView?: boolean;
}

export function GradeDetailModal({
  isOpen,
  onClose,
  submission,
  onOpenOverride,
  isFacultyView = false
}: GradeDetailModalProps) {
  if (!submission) return null;

  const evalData = submission.evaluation;
  const override = submission.override;
  const isOverridden = Boolean(override?.isOverridden);

  const displayScore = isOverridden
    ? override!.overriddenScore
    : (evalData?.score ?? 0);
  const maxScore = evalData?.maxScore ?? 100;
  const percentage = Math.round((displayScore / maxScore) * 100);
  const scoreColors = getScoreColor(percentage);

  const handleDownloadJSON = () => {
    const jsonStr = JSON.stringify(submission, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `grade_report_${submission.studentName.replace(/\s+/g, '_')}_${submission.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Assignment Evaluation & Feedback"
      subtitle={`${submission.courseCode} • ${submission.assignmentTitle}`}
      maxWidth="3xl"
    >
      <div className="space-y-6">
        {/* Student and Submission Info Header */}
        <div className="bg-slate-50 dark:bg-slate-800/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="font-semibold text-slate-900 dark:text-white text-sm">
              {submission.studentName}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {submission.studentId} • {submission.studentEmail}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1 justify-end">
                <FileText className="w-3.5 h-3.5" />
                <span className="font-mono">{submission.fileName}</span>
              </div>
              <div className="text-[11px] text-slate-400">
                Submitted {submission.submittedAt}
              </div>
            </div>
            <StatusBadge status={submission.status} isOverridden={isOverridden} />
          </div>
        </div>

        {/* Manual Review Required Alert */}
        {submission.status === 'manual_review' && (
          <div className="bg-orange-50 dark:bg-orange-950/40 border border-orange-200 dark:border-orange-800 p-4 rounded-xl flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-orange-600 dark:text-orange-400 shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <div className="font-bold text-orange-900 dark:text-orange-200">
                Manual Review Required (Unextractable or Blank Document)
              </div>
              <div className="text-orange-700 dark:text-orange-300">
                The uploaded document contains no machine-readable text (likely a scanned image, diagram-only PDF, or blank document). Automated AI grading was safely suspended to prevent fabricated or hallucinated feedback. Please grade this submission manually or request a resubmission.
              </div>
            </div>
          </div>
        )}

        {/* Score Summary Banner */}
        <div className={`p-5 rounded-2xl border ${scoreColors.bg} ${scoreColors.border} flex flex-wrap items-center justify-between gap-4`}>
          <div>
            <span className="text-xs uppercase font-bold tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
              {isOverridden ? 'Final Faculty Score' : 'AI Calculated Score'}
            </span>
            <div className="flex items-baseline gap-2">
              <span className={`text-4xl font-extrabold ${scoreColors.text}`}>
                {displayScore}
              </span>
              <span className="text-slate-500 dark:text-slate-400 font-medium text-lg">
                / {maxScore}
              </span>
              <span className={`text-sm font-semibold px-2.5 py-0.5 rounded-full ${scoreColors.bg} ${scoreColors.text} border ${scoreColors.border} ml-2`}>
                {percentage}%
              </span>
            </div>
          </div>

          {/* AI Pipeline Signature */}
          <div className="bg-white/90 dark:bg-slate-900/90 backdrop-blur-xs p-3 rounded-xl border border-slate-200 dark:border-slate-700 text-right">
            <div className="flex items-center justify-end gap-1.5 text-xs font-semibold text-purple-700 dark:text-purple-300">
              <Sparkles className="w-3.5 h-3.5 text-purple-600" />
              <span>Two-Stage Gemini AI</span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 font-mono">
              Schema: {evalData?.aiModelExtraction || 'Flash-Lite'} → Grade: {evalData?.aiModelGrading || 'Flash'}
            </p>
          </div>
        </div>

        {/* Faculty Override Banner (if active) */}
        {isOverridden && override && (
          <div className="bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 p-4 rounded-xl flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <div className="font-bold text-purple-900 dark:text-purple-200">
                Score Overridden by {override.overriddenBy}
              </div>
              <div className="text-purple-700 dark:text-purple-300">
                <span className="font-semibold">Reason:</span> {override.overrideReason}
              </div>
              <div className="text-slate-400 text-[10px] font-mono">
                Original AI Score: {override.originalScore} / {maxScore} • Overridden at {override.overriddenAt}
              </div>
            </div>
          </div>
        )}

        {/* AI Summary Feedback */}
        {evalData?.summaryFeedback && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Executive Evaluation Summary
            </h4>
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs leading-relaxed border border-slate-200 dark:border-slate-700">
              {evalData.summaryFeedback}
            </div>
          </div>
        )}

        {/* Rubric Breakdown List */}
        {evalData?.criteriaScores && evalData.criteriaScores.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Rubric Criteria Breakdown
              </h4>
              <span className="text-xs text-slate-400 font-mono">
                {evalData.criteriaScores.length} Criteria Evaluated
              </span>
            </div>

            <div className="space-y-3">
              {evalData.criteriaScores.map((criterion, idx) => {
                const critRatio = criterion.scoreRatio !== undefined
                  ? criterion.scoreRatio
                  : (criterion.maxPoints > 0 ? (criterion.scoreAwarded / criterion.maxPoints) : 1);
                const critColor = critRatio >= 0.8 ? 'text-emerald-600' : critRatio >= 0.6 ? 'text-amber-600' : 'text-rose-600';
                const critAdjusted = override?.criterionAdjustments?.[criterion.criterionId];

                return (
                  <div
                    key={criterion.criterionId || idx}
                    className="p-3.5 rounded-xl bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 dark:text-white text-xs">
                        {criterion.title}
                      </span>
                      <div className="flex items-center gap-2">
                        {critAdjusted !== undefined && (
                          <span className="text-[10px] bg-purple-100 dark:bg-purple-900/60 text-purple-700 dark:text-purple-300 px-1.5 py-0.5 rounded font-mono">
                            Adjusted
                          </span>
                        )}
                        <span className={`font-bold font-mono text-xs ${critColor}`}>
                          {critAdjusted !== undefined ? critAdjusted : criterion.scoreAwarded} / {criterion.maxPoints} pts
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          ({Math.round(critRatio * 100)}%)
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-600 dark:text-slate-300">
                      {criterion.feedback}
                    </p>

                    {/* Factual Evidence Excerpt */}
                    {criterion.evidence && (
                      <div className="p-2.5 rounded-lg bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/50 text-[11px] space-y-1">
                        <div className="flex items-center gap-1.5 font-semibold text-indigo-800 dark:text-indigo-300">
                          <Quote className="w-3 h-3 text-indigo-600" />
                          <span>Direct Submission Evidence:</span>
                        </div>
                        <p className="font-mono text-slate-700 dark:text-slate-300 italic whitespace-pre-wrap">
                          &ldquo;{criterion.evidence}&rdquo;
                        </p>
                      </div>
                    )}

                    {/* Pedagogical Reasoning */}
                    {criterion.reasoning && (
                      <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-150 dark:border-slate-700 text-[11px] space-y-0.5">
                        <span className="font-semibold text-slate-700 dark:text-slate-300">Pedagogical Rationale:</span>
                        <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                          {criterion.reasoning}
                        </p>
                      </div>
                    )}

                    {(criterion.strengths || criterion.improvements) && (
                      <div className="pt-2 border-t border-slate-100 dark:border-slate-700/60 grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                        {criterion.strengths && (
                          <div className="text-emerald-700 dark:text-emerald-400">
                            <span className="font-semibold">Strength:</span> {criterion.strengths}
                          </div>
                        )}
                        {criterion.improvements && (
                          <div className="text-amber-700 dark:text-amber-400">
                            <span className="font-semibold">Opportunity:</span> {criterion.improvements}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Curriculum Concept Evidence & Mastery Contribution */}
        {evalData?.conceptFeedback && evalData.conceptFeedback.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <BrainCircuit className="w-4 h-4 text-purple-600" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Concept Mastery & Evidence
                </h4>
              </div>
              <span className="text-[11px] text-slate-400">
                Authoritative mapping via <code className="font-mono">assignment_criterion_concepts</code>
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {evalData.conceptFeedback.map((cf) => {
                const masteryPct = Math.round(cf.masteryContribution * 100);
                const confPct = Math.round(cf.confidenceScore * 100);
                const ratioPct = Math.round(cf.scoreRatio * 100);

                return (
                  <div
                    key={cf.conceptId}
                    className="p-3.5 rounded-xl bg-purple-50/40 dark:bg-purple-950/20 border border-purple-200/70 dark:border-purple-800/60 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-bold text-xs text-purple-950 dark:text-purple-200">
                        {cf.conceptName || 'Curriculum Concept'}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold font-mono bg-purple-100 text-purple-800 dark:bg-purple-900/60 dark:text-purple-200 border border-purple-200 dark:border-purple-700">
                          {masteryPct}% Mastery
                        </span>
                        <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                          {confPct}% Conf.
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                      <span>Evidence Ratio: {ratioPct}%</span>
                      <span>Evidence Samples: N={cf.evidenceCount}</span>
                    </div>

                    <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                      {cf.feedback}
                    </p>

                    {cf.strengths && cf.strengths.length > 0 && (
                      <div className="text-[11px] text-emerald-700 dark:text-emerald-400">
                        <span className="font-semibold">Strengths:</span> {cf.strengths.join(' • ')}
                      </div>
                    )}
                    {cf.improvements && cf.improvements.length > 0 && (
                      <div className="text-[11px] text-amber-700 dark:text-amber-400">
                        <span className="font-semibold">Growth Areas:</span> {cf.improvements.join(' • ')}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Overall Strengths & Areas for Improvement */}
        {evalData && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Strengths */}
            <div className="p-4 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/60 space-y-2">
              <div className="flex items-center gap-1.5 font-bold text-xs text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Identified Strengths</span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-700 dark:text-slate-300 list-disc list-inside">
                {evalData.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>

            {/* Improvements */}
            <div className="p-4 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/60 space-y-2">
              <div className="flex items-center gap-1.5 font-bold text-xs text-amber-800 dark:text-amber-300">
                <AlertCircle className="w-4 h-4 text-amber-600" />
                <span>Areas for Pedagogical Growth</span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-700 dark:text-slate-300 list-disc list-inside">
                {evalData.improvements.map((imp, i) => (
                  <li key={i}>{imp}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Actions Footer */}
        <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <button
            onClick={handleDownloadJSON}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Evaluation JSON</span>
          </button>

          <div className="flex items-center gap-2">
            {isFacultyView && onOpenOverride && (
              <button
                onClick={() => {
                  onClose();
                  onOpenOverride(submission);
                }}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-700 shadow-sm transition"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>{isOverridden ? 'Edit Faculty Override' : 'Override Score / Feedback'}</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
