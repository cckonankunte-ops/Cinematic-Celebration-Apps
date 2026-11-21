import { useEffect, useId, useRef, useState } from 'react';

import { CLOSE_REASON_LABELS, type CloseReason } from './types';

/**
 * Close a lead as Lost or Not interested (lead-crm R1.8, R7.5). A reason is
 * required; "Other" also needs a short explanation.
 */
export interface CloseLeadDialogProps {
  status: 'lost' | 'not_interested';
  isSaving: boolean;
  error: string | null;
  onConfirm: (reason: CloseReason, text: string | null) => void;
  onCancel: () => void;
}

export function CloseLeadDialog({
  status,
  isSaving,
  error,
  onConfirm,
  onCancel,
}: CloseLeadDialogProps): JSX.Element {
  const id = useId();
  const [reason, setReason] = useState<CloseReason | ''>('');
  const [text, setText] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const firstField = useRef<HTMLSelectElement>(null);

  useEffect(() => {
    firstField.current?.focus();
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel]);

  const submit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!reason) {
      setLocalError('Choose a reason.');
      return;
    }
    if (reason === 'other' && !text.trim()) {
      setLocalError('Add a short explanation for "Other".');
      return;
    }
    setLocalError(null);
    onConfirm(reason, text.trim() || null);
  };

  const title = status === 'lost' ? 'Mark as lost' : 'Mark as not interested';

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        onSubmit={submit}
        className="w-full max-w-sm space-y-3 rounded bg-white p-4 shadow-lg"
      >
        <h2 id={`${id}-title`} className="text-base font-semibold text-gray-900">
          {title}
        </h2>
        <label className="block space-y-1 text-sm">
          <span className="font-medium text-gray-700">Reason *</span>
          <select
            ref={firstField}
            value={reason}
            onChange={(e) => setReason(e.target.value as CloseReason | '')}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">Choose a reason</option>
            {(Object.keys(CLOSE_REASON_LABELS) as CloseReason[]).map((r) => (
              <option key={r} value={r}>
                {CLOSE_REASON_LABELS[r]}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1 text-sm">
          <span className="font-medium text-gray-700">Details{reason === 'other' ? ' *' : ''}</span>
          <textarea
            rows={2}
            maxLength={500}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
        {(localError || error) && <p className="text-xs text-red-600">{localError ?? error}</p>}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {isSaving ? 'Saving…' : 'Close lead'}
          </button>
        </div>
      </form>
    </div>
  );
}
