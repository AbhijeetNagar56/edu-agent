'use client';

import React, { useState, useEffect } from 'react';
import { ShieldCheck, AlertCircle } from 'lucide-react';
import { Submission, FacultyOverride } from '../lib/types';
import { Modal } from './Modal';
import { overrideGrade, removeSubmissionOverride } from '../lib/storage';

interface OverrideModalProps {
  isOpen: boolean;
  onClose: () => void;
  submission: Submission | null;
  onOverrideSaved: (updated: Submission) => void;
}

export function OverrideModal({
  isOpen,
  onClose,
  submission,
  onOverrideSaved
}: OverrideModalProps) {
  const [newScore, setNewScore] = useState<number>(0);
  const [instructorName, setInstructorName] = useState<string>('Dr. Sarah Lin');
  const [overrideReason, setOverrideReason] = useState<string>('');
  const [criterionAdjustments, setCriterionAdjustments] = useState<Record<string, number>>({});
  const [error, setError] = useState<string>('');
  const [isReverting, setIsReverting] = useState<boolean>(false);

  const handleRevert = async () => {
    if (!submission) return;
    if (!window.confirm('Are you sure you want to revoke this faculty override and restore pure AI evaluation?')) {
      return;
    }
    setIsReverting(true);
    try {
      await removeSubmissionOverride(submission.id, 'Faculty revoked override and reverted to AI score');
      const revertedSub: Submission = {
        ...submission,
        override: submission.override ? {
          ...submission.override,
          isOverridden: false,
          overriddenScore: submission.evaluation?.score ?? 0,
        } : undefined,
      };
      onOverrideSaved(revertedSub);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove override.');
    } finally {
      setIsReverting(false);
    }
  };

  useEffect(() => {
    if (submission) {
      const current = submission.override?.isOverridden
        ? submission.override.overriddenScore
        : (submission.evaluation?.score ?? 0);
      setNewScore(current);
      setOverrideReason(submission.override?.overrideReason || '');
      setInstructorName(submission.override?.overriddenBy || 'Dr. Sarah Lin');
      setCriterionAdjustments(submission.override?.criterionAdjustments || {});
      setError('');
    }
  }, [submission]);

  if (!submission) return null;

  const maxScore = submission.evaluation?.maxScore ?? 100;
  const originalScore = submission.evaluation?.score ?? 0;

  const handleCriterionScoreChange = (critId: string, val: number, maxCrit: number) => {
    const clamped = Math.max(0, Math.min(val, maxCrit));
    const nextAdjustments = {
      ...criterionAdjustments,
      [critId]: clamped
    };
    setCriterionAdjustments(nextAdjustments);

    // Sum up the total
    if (submission.evaluation?.criteriaScores) {
      const sum = submission.evaluation.criteriaScores.reduce((acc, c) => {
        const valForC = nextAdjustments[c.criterionId] !== undefined
          ? nextAdjustments[c.criterionId]
          : c.scoreAwarded;
        return acc + valForC;
      }, 0);
      setNewScore(sum);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideReason.trim()) {
      setError('Please provide a brief justification or note for the override.');
      return;
    }
    if (newScore < 0 || newScore > maxScore) {
      setError(`Score must be between 0 and ${maxScore}.`);
      return;
    }

    const overrideData: FacultyOverride = {
      isOverridden: true,
      originalScore,
      overriddenScore: newScore,
      overriddenBy: instructorName.trim() || 'Faculty Instructor',
      overrideReason: overrideReason.trim(),
      overriddenAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
      criterionAdjustments
    };

    try {
      const updated = await overrideGrade(submission.id, overrideData);
      onOverrideSaved(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save grade override.');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Faculty Grade Override"
      subtitle={`Student: ${submission.studentName} (${submission.studentId})`}
      maxWidth="2xl"
    >
      <form onSubmit={handleSave} className="space-y-5">
        {/* Comparison Header */}
        <div className="grid grid-cols-2 gap-4 bg-slate-50 dark:bg-slate-800/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
              Original AI Grade
            </span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-2xl font-bold text-slate-700 dark:text-slate-300">
                {originalScore}
              </span>
              <span className="text-xs text-slate-400">/ {maxScore}</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">Calculated by Gemini AI</p>
          </div>

          <div>
            <span className="text-xs font-semibold text-purple-700 dark:text-purple-300 uppercase tracking-wider block">
              New Faculty Grade
            </span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {newScore}
              </span>
              <span className="text-xs text-slate-400">/ {maxScore}</span>
              <span className="text-xs font-mono font-semibold text-purple-700 dark:text-purple-300 ml-1">
                ({Math.round((newScore / maxScore) * 100)}%)
              </span>
            </div>
            <p className="text-[11px] text-purple-600 dark:text-purple-400 mt-0.5">Overrides public grade</p>
          </div>
        </div>

        {/* Criteria-level adjustments if available */}
        {submission.evaluation?.criteriaScores && submission.evaluation.criteriaScores.length > 0 && (
          <div className="space-y-2.5">
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
              Adjust Individual Criteria (Optional)
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {submission.evaluation.criteriaScores.map((c) => {
                const currentVal = criterionAdjustments[c.criterionId] !== undefined
                  ? criterionAdjustments[c.criterionId]
                  : c.scoreAwarded;

                return (
                  <div
                    key={c.criterionId}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs"
                  >
                    <span className="text-slate-800 dark:text-slate-200 font-medium truncate max-w-xs">
                      {c.title}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400 text-[11px]">Original: {c.scoreAwarded}</span>
                      <input
                        type="number"
                        min={0}
                        max={c.maxPoints}
                        value={currentVal}
                        onChange={(e) => handleCriterionScoreChange(c.criterionId, Number(e.target.value), c.maxPoints)}
                        className="w-16 px-2 py-1 text-center font-bold text-purple-600 border border-purple-200 dark:border-purple-800 dark:bg-slate-900 rounded-md focus:outline-hidden focus:ring-1 focus:ring-purple-500"
                      />
                      <span className="text-slate-400 font-mono">/ {c.maxPoints}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Total Score Input */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Total Overridden Score (0 - {maxScore})
          </label>
          <input
            type="number"
            min={0}
            max={maxScore}
            value={newScore}
            onChange={(e) => setNewScore(Number(e.target.value))}
            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm font-semibold focus:outline-hidden focus:ring-2 focus:ring-purple-500"
            required
          />
        </div>

        {/* Instructor Name */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Instructor Name / Title
          </label>
          <input
            type="text"
            value={instructorName}
            onChange={(e) => setInstructorName(e.target.value)}
            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs focus:outline-hidden focus:ring-2 focus:ring-purple-500"
            placeholder="e.g. Dr. Sarah Lin"
            required
          />
        </div>

        {/* Reason / Notes */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Faculty Override Justification & Feedback
          </label>
          <textarea
            rows={3}
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            placeholder="Explain why the score was adjusted (e.g. manual verification of edge case analysis, partial credit for alternate proof, etc.)..."
            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs focus:outline-hidden focus:ring-2 focus:ring-purple-500"
            required
          />
          <p className="text-[11px] text-slate-400 mt-1">
            This justification will be permanently visible to the student and recorded in the audit trail.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-1.5 p-3 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
          <div>
            {submission.override?.isOverridden && (
              <button
                type="button"
                onClick={handleRevert}
                disabled={isReverting}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300 dark:hover:bg-rose-900/60 border border-rose-200 dark:border-rose-800 transition disabled:opacity-50"
              >
                {isReverting ? 'Reverting...' : 'Revert to Original AI Grade'}
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-700 shadow-sm transition"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Apply Faculty Override</span>
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
