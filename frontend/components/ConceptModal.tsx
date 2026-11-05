'use client';

import React, { useState, useEffect } from 'react';
import { Layers, AlertCircle, Loader2, Trash2 } from 'lucide-react';
import { Modal } from './Modal';
import { Concept, ConceptDifficulty } from '@/lib/types';
import { createConcept, updateConcept, deleteConcept } from '@/lib/storage';

interface ConceptModalProps {
  isOpen: boolean;
  onClose: () => void;
  courseId: string;
  concept?: Concept | null;
  defaultPosition?: { posX: number; posY: number };
  onConceptSaved: (concept: Concept) => void;
  onConceptDeleted?: (conceptId: string) => void;
}

export function ConceptModal({
  isOpen,
  onClose,
  courseId,
  concept,
  defaultPosition,
  onConceptSaved,
  onConceptDeleted,
}: ConceptModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [difficulty, setDifficulty] = useState<ConceptDifficulty>('intermediate');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isEditing = Boolean(concept);

  useEffect(() => {
    if (concept) {
      setName(concept.name || '');
      setDescription(concept.description || '');
      setCategory(concept.category || '');
      setDifficulty(concept.difficulty || 'intermediate');
    } else {
      setName('');
      setDescription('');
      setCategory('');
      setDifficulty('intermediate');
    }
    setErrorMessage(null);
  }, [concept, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMessage('Concept name is required.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMessage(null);

      if (isEditing && concept) {
        const updated = await updateConcept(courseId, concept.id, {
          name: name.trim(),
          description: description.trim(),
          category: category.trim(),
          difficulty,
        });
        onConceptSaved(updated);
      } else {
        const created = await createConcept(courseId, {
          name: name.trim(),
          description: description.trim(),
          category: category.trim(),
          difficulty,
          posX: defaultPosition?.posX ?? 250,
          posY: defaultPosition?.posY ?? 200,
        });
        onConceptSaved(created);
      }
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save concept node.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!concept || !confirm(`Delete concept "${concept.name}" and all its prerequisite edges?`)) {
      return;
    }

    try {
      setIsDeleting(true);
      setErrorMessage(null);
      await deleteConcept(courseId, concept.id);
      if (onConceptDeleted) {
        onConceptDeleted(concept.id);
      }
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete concept.');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? 'Edit Concept Node' : 'Add New Curriculum Concept'}
      subtitle={isEditing ? `Modify attributes for "${concept?.name}"` : 'Define a pedagogical concept node for this course'}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {errorMessage && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Concept Title <span className="text-rose-500">*</span>
          </label>
          <input
            type="text"
            required
            placeholder="e.g. Asymptotic Complexity (Big-O)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Category / Topic
            </label>
            <input
              type="text"
              placeholder="e.g. Complexity Theory, Algorithms"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Difficulty Tier
            </label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as ConceptDifficulty)}
              className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Pedagogical Description
          </label>
          <textarea
            rows={3}
            placeholder="Explain what the student is expected to learn or master..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
          <div>
            {isEditing && (
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting || isSubmitting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-xl transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{isDeleting ? 'Deleting...' : 'Delete Concept'}</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting || isDeleting}
              className="px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || isDeleting}
              className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-xs transition disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Layers className="w-3.5 h-3.5" />
                  <span>{isEditing ? 'Save Changes' : 'Add Concept'}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
