'use client';

import React from 'react';
import { Clock, Loader2, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import { JobStatus } from '../lib/types';

interface BadgeProps {
  status: JobStatus;
  isOverridden?: boolean;
  size?: 'sm' | 'md';
}

export function StatusBadge({ status, isOverridden, size = 'md' }: BadgeProps) {
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-xs px-2.5 py-1 font-medium';

  if (isOverridden) {
    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800 ${sizeClasses}`}>
        <ShieldCheck className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
        Faculty Overridden
      </span>
    );
  }

  switch (status) {
    case 'pending':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800 ${sizeClasses}`}>
          <Clock className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
          Pending in Queue
        </span>
      );
    case 'processing':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800 ${sizeClasses}`}>
          <Loader2 className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 animate-spin" />
          AI Grading...
        </span>
      );
    case 'done':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800 ${sizeClasses}`}>
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
          Evaluated
        </span>
      );
    case 'flagged':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800 ${sizeClasses}`}>
          <AlertTriangle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
          Review Flagged
        </span>
      );
    case 'manual_review':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-full bg-orange-50 text-orange-700 border border-orange-200 dark:bg-orange-950/40 dark:text-orange-300 dark:border-orange-800 ${sizeClasses}`}>
          <AlertTriangle className="w-3.5 h-3.5 text-orange-600 dark:text-orange-400" />
          Manual Review Required
        </span>
      );

    case 'failed':
      return (
        <span className={`inline-flex items-center gap-1.5 rounded-full bg-gray-50 text-gray-700 border border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700 ${sizeClasses}`}>
          <AlertTriangle className="w-3.5 h-3.5 text-gray-500" />
          Failed (Retrying)
        </span>
      );
    default:
      return null;
  }
}
