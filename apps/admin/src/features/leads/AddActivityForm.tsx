import { useState } from 'react';

import { ApiError } from '@/api/client';
import { useAddActivity } from './lead-queries';
import type { ManualActivityType } from './types';

/** Add a note, call or WhatsApp entry with optional text (lead-crm R7.2). */
export function AddActivityForm({ leadId }: { leadId: number }): JSX.Element {
  const addActivity = useAddActivity();
  const [type, setType] = useState<ManualActivityType>('note');
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const onSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    const trimmed = text.trim();
    if (type === 'note' && !trimmed) {
      setError('Write a note first.');
      return;
    }
    setError(null);
    addActivity.mutate(
      { leadId, body: { type, text: trimmed || undefined } },
      {
        onSuccess: () => setText(''),
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : 'Could not save the activity.'),
      },
    );
  };

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Activity type">
        {(['note', 'call', 'whatsapp'] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={type === t}
            onClick={() => setType(t)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              type === t ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-700'
            }`}
          >
            {t === 'note' ? 'Note' : t === 'call' ? 'Call' : 'WhatsApp'}
          </button>
        ))}
      </div>
      <label className="block text-sm">
        <span className="sr-only">Activity text</span>
        <textarea
          rows={2}
          maxLength={2000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={type === 'note' ? 'Add a note' : 'What happened? (optional)'}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
        />
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={addActivity.isPending}
        className="rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {addActivity.isPending ? 'Saving…' : 'Add'}
      </button>
    </form>
  );
}
