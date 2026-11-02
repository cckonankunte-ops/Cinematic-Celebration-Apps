/**
 * Per-plan slot management: lists a plan's slots and offers a compact create
 * form. A slot is a start time (on the hour/half-hour) plus a duration in
 * minutes; the server derives the display label and validates the start minute
 * and working-hours containment. Deactivate is a soft-delete.
 */

import { useState } from 'react';

import {
  useCreateSlot,
  useDeactivateSlot,
  useSlots,
} from './queries';
import type { SlotCreateBody } from './types';

/** :00/:30 start-time options across a 24h day ("HH:MM"). */
const START_OPTIONS: string[] = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, '0');
  const m = i % 2 === 0 ? '00' : '30';
  return `${h}:${m}`;
});

/** Common durations in minutes. */
const DURATION_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 60, label: '1 hour' },
  { value: 90, label: '1.5 hours' },
  { value: 120, label: '2 hours' },
  { value: 180, label: '3 hours' },
];

function fmt12h(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number);
  const hour = h % 12 || 12;
  const ampm = h < 12 ? 'AM' : 'PM';
  return `${hour}:${String(m).padStart(2, '0')} ${ampm}`;
}

export function SlotManager({ planId }: { planId: number }): JSX.Element {
  const slots = useSlots(planId);
  const createSlot = useCreateSlot(planId);
  const deactivateSlot = useDeactivateSlot(planId);

  const [start, setStart] = useState('11:00');
  const [duration, setDuration] = useState(120);

  const onCreate = (e: React.FormEvent): void => {
    e.preventDefault();
    const body: SlotCreateBody = {
      plan_id: planId,
      start_time: start,
      duration_minutes: duration,
      show_combos: true,
      sort_order: slots.data?.length ?? 0,
      // Start validity in the past to avoid the IST/UTC "today" boundary race.
      effective_from: '2020-01-01',
    };
    createSlot.mutate(body);
  };

  const field = 'rounded border border-gray-300 px-2 py-1 text-sm';

  return (
    <div className="mt-2 space-y-2 border-t border-gray-100 pt-2">
      <h4 className="text-xs font-semibold text-gray-600">Slots</h4>
      {slots.data && slots.data.length === 0 && (
        <p className="text-xs text-gray-500">No slots yet.</p>
      )}
      <ul className="space-y-1">
        {slots.data?.map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between rounded border border-gray-200 px-2 py-1 text-xs"
          >
            <span>
              {s.start_time
                ? `${fmt12h(s.start_time.slice(0, 5))} · ${s.duration_minutes} min`
                : s.description}
              {!s.is_active && <span className="ml-2 text-gray-400">(inactive)</span>}
            </span>
            <button
              type="button"
              disabled={!s.is_active || deactivateSlot.isPending}
              onClick={() => deactivateSlot.mutate(s.id)}
              className="rounded border border-red-300 px-1.5 py-0.5 text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              Deactivate
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={onCreate} className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-gray-600">
          Start
          <select
            aria-label="Slot start time"
            className={`${field} ml-1`}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          >
            {START_OPTIONS.map((t) => (
              <option key={t} value={t}>
                {fmt12h(t)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-gray-600">
          Duration
          <select
            aria-label="Slot duration"
            className={`${field} ml-1`}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
          >
            {DURATION_OPTIONS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={createSlot.isPending}
          className="rounded bg-gray-900 px-2 py-1 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          Add slot
        </button>
      </form>
      {createSlot.isError && (
        <p className="text-xs text-red-600">
          Could not add slot (check it's on the hour/half-hour and within working
          hours).
        </p>
      )}
    </div>
  );
}
