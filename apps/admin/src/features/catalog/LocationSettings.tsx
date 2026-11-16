/**
 * Admin location settings: per-branch working hours, the online-booking cutoff,
 * and the late-booking switch (R5, R6). Times are IST "HH:MM". `closes_at` may
 * be earlier than `opens_at`, meaning close is the next day (e.g. 10:00 → 01:00).
 * The late switch lets customers self-book past the cutoff; staff/admin are
 * never blocked by the cutoff.
 */

import { useEffect, useState } from 'react';

import { ApiError } from '@/api/client';
import { formatRupees, rupeesToPaise } from '@/lib/money';
import {
  useAdvanceRules,
  useCreateAdvanceRule,
  useCreateDisallowedTime,
  useDeleteAdvanceRule,
  useDeleteDisallowedTime,
  useDisallowedTimes,
  useLocationsAdmin,
  useUpdateLocationHours,
} from './queries';
import type { LocationAdminRead } from './types';

const field = 'rounded border border-gray-300 px-2 py-1 text-sm';

function LocationRow({ loc }: { loc: LocationAdminRead }): JSX.Element {
  const update = useUpdateLocationHours();
  const [opensAt, setOpensAt] = useState(loc.opens_at.slice(0, 5));
  const [closesAt, setClosesAt] = useState(loc.closes_at.slice(0, 5));
  const [cutoff, setCutoff] = useState(loc.last_online_booking_start.slice(0, 5));
  const [allowLate, setAllowLate] = useState(loc.allow_late_booking);
  const [bookingMode, setBookingMode] = useState<'slot' | 'open'>(loc.booking_mode);

  // Re-sync local fields if the server value changes after a refetch.
  useEffect(() => {
    setOpensAt(loc.opens_at.slice(0, 5));
    setClosesAt(loc.closes_at.slice(0, 5));
    setCutoff(loc.last_online_booking_start.slice(0, 5));
    setAllowLate(loc.allow_late_booking);
    setBookingMode(loc.booking_mode);
  }, [loc]);

  const onSave = (e: React.FormEvent): void => {
    e.preventDefault();
    update.mutate({
      locationId: loc.id,
      body: {
        opens_at: opensAt,
        closes_at: closesAt,
        last_online_booking_start: cutoff,
        allow_late_booking: allowLate,
        booking_mode: bookingMode,
      },
    });
  };

  return (
    <form
      onSubmit={onSave}
      className="flex flex-wrap items-end gap-3 rounded border border-gray-200 bg-white p-3 text-sm"
    >
      <span className="min-w-[8rem] font-medium text-gray-900">{loc.name}</span>
      <label className="text-xs text-gray-600">
        Opens
        <input
          type="time"
          step={1800}
          className={`${field} ml-1`}
          value={opensAt}
          onChange={(e) => setOpensAt(e.target.value)}
        />
      </label>
      <label className="text-xs text-gray-600">
        Closes
        <input
          type="time"
          step={1800}
          className={`${field} ml-1`}
          value={closesAt}
          onChange={(e) => setClosesAt(e.target.value)}
        />
      </label>
      <label className="text-xs text-gray-600">
        Online cutoff
        <input
          type="time"
          step={1800}
          className={`${field} ml-1`}
          value={cutoff}
          onChange={(e) => setCutoff(e.target.value)}
        />
      </label>
      <label className="flex items-center gap-1 text-xs text-gray-700">
        <input
          type="checkbox"
          checked={allowLate}
          onChange={(e) => setAllowLate(e.target.checked)}
        />
        Allow late online booking
      </label>
      <label className="text-xs text-gray-600">
        Booking mode
        <select
          aria-label={`Booking mode for ${loc.name}`}
          className={`${field} ml-1`}
          value={bookingMode}
          onChange={(e) => setBookingMode(e.target.value as 'slot' | 'open')}
        >
          <option value="slot">Slot picker</option>
          <option value="open">Open (start + duration)</option>
        </select>
      </label>
      <button
        type="submit"
        disabled={update.isPending}
        className="rounded bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {update.isPending ? 'Saving…' : 'Save'}
      </button>
      {update.isError && <span className="text-xs text-red-600">Save failed.</span>}
    </form>
  );
}

export function LocationSettings(): JSX.Element {
  const locations = useLocationsAdmin();

  return (
    <div className="space-y-2">
      <h2 className="text-base font-semibold text-gray-800">
        Location hours &amp; online booking
      </h2>
      <p className="text-xs text-gray-500">
        Close time may be earlier than open (next-day close, e.g. 10:00 → 01:00).
        The cutoff blocks customer online bookings that start at/after it unless
        “Allow late online booking” is on; staff and admins are never blocked.
      </p>
      {locations.isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {locations.isError && (
        <p className="text-sm text-red-600">Failed to load locations.</p>
      )}
      <div className="space-y-4">
        {locations.data?.map((loc) => (
          <div
            key={loc.id}
            className="space-y-2 rounded border border-gray-200 bg-gray-50 p-3"
          >
            <LocationRow loc={loc} />
            <div className="grid gap-3 md:grid-cols-2">
              <DisallowedTimesManager locationId={loc.id} />
              <AdvanceRulesManager locationId={loc.id} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Disallowed booking-time ranges (per branch)
// ---------------------------------------------------------------------------
function DisallowedTimesManager({ locationId }: { locationId: number }): JSX.Element {
  const rows = useDisallowedTimes(locationId);
  const create = useCreateDisallowedTime(locationId);
  const remove = useDeleteDisallowedTime(locationId);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [maxDuration, setMaxDuration] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);

  const onAdd = (e: React.FormEvent): void => {
    e.preventDefault();
    setError(null);
    create.mutate(
      {
        start_time: start,
        end_time: end,
        max_duration_minutes: maxDuration === '' ? null : Number(maxDuration),
        note: note.trim() === '' ? null : note.trim(),
      },
      {
        onSuccess: () => {
          setStart('');
          setEnd('');
          setMaxDuration('');
          setNote('');
        },
        onError: (err) =>
          setError(
            err instanceof ApiError ? err.message : 'Could not add the time range.',
          ),
      },
    );
  };

  return (
    <div className="space-y-2 rounded border border-gray-200 bg-white p-2">
      <h4 className="text-xs font-semibold text-gray-700">Disallowed times</h4>
      <p className="text-[11px] text-gray-500">
        Customers cannot start a booking inside these ranges. An optional max
        duration caps bookings that start before the range. Staff/admin can
        override when creating a booking.
      </p>
      {rows.isLoading && <p className="text-xs text-gray-500">Loading…</p>}
      {(rows.data ?? []).length === 0 && !rows.isLoading && (
        <p className="text-xs text-gray-500">None.</p>
      )}
      <ul className="space-y-1">
        {(rows.data ?? []).map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between rounded border border-gray-200 px-2 py-1 text-xs"
          >
            <span>
              {r.start_time.slice(0, 5)}–{r.end_time.slice(0, 5)}
              {r.max_duration_minutes !== null && (
                <span className="text-gray-500"> · max {r.max_duration_minutes}m</span>
              )}
              {r.note && <span className="text-gray-500"> · {r.note}</span>}
            </span>
            <button
              type="button"
              disabled={remove.isPending}
              onClick={() => remove.mutate(r.id)}
              className="rounded border border-gray-300 px-2 py-0.5 text-[11px] hover:bg-gray-50 disabled:opacity-50"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <form onSubmit={onAdd} className="flex flex-wrap items-end gap-2">
        <label className="text-[11px] text-gray-600">
          From
          <input
            type="time"
            step={1800}
            required
            className={`${field} ml-1`}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label className="text-[11px] text-gray-600">
          To
          <input
            type="time"
            step={1800}
            required
            className={`${field} ml-1`}
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label className="text-[11px] text-gray-600">
          Max min
          <input
            type="number"
            min={0}
            placeholder="—"
            className={`${field} ml-1 w-20`}
            value={maxDuration}
            onChange={(e) => setMaxDuration(e.target.value)}
          />
        </label>
        <input
          className={`${field} flex-1`}
          placeholder="Note (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded bg-gray-900 px-3 py-1 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          Add
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Advance rules (per branch)
// ---------------------------------------------------------------------------
function AdvanceRulesManager({ locationId }: { locationId: number }): JSX.Element {
  const rows = useAdvanceRules(locationId);
  const create = useCreateAdvanceRule(locationId);
  const remove = useDeleteAdvanceRule(locationId);
  const [minTotal, setMinTotal] = useState('');
  const [advance, setAdvance] = useState('');
  const [error, setError] = useState<string | null>(null);

  const onAdd = (e: React.FormEvent): void => {
    e.preventDefault();
    setError(null);
    create.mutate(
      {
        min_total_paise: rupeesToPaise(Number(minTotal)),
        advance_paise: rupeesToPaise(Number(advance)),
      },
      {
        onSuccess: () => {
          setMinTotal('');
          setAdvance('');
        },
        onError: (err) =>
          setError(
            err instanceof ApiError
              ? err.message
              : 'Could not add the advance rule.',
          ),
      },
    );
  };

  // Highest threshold the total meets wins; show sorted high→low for clarity.
  const sorted = [...(rows.data ?? [])].sort(
    (a, b) => b.min_total_paise - a.min_total_paise,
  );

  return (
    <div className="space-y-2 rounded border border-gray-200 bg-white p-2">
      <h4 className="text-xs font-semibold text-gray-700">Advance rules</h4>
      <p className="text-[11px] text-gray-500">
        The highest threshold the final total (after discount &amp; coupon)
        meets sets the required advance. If no rule matches, the plan’s own
        advance applies.
      </p>
      {rows.isLoading && <p className="text-xs text-gray-500">Loading…</p>}
      {sorted.length === 0 && !rows.isLoading && (
        <p className="text-xs text-gray-500">None.</p>
      )}
      <ul className="space-y-1">
        {sorted.map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between rounded border border-gray-200 px-2 py-1 text-xs"
          >
            <span>
              Total ≥ {formatRupees(r.min_total_paise)}
              <span className="text-gray-500">
                {' '}
                → advance {formatRupees(r.advance_paise)}
              </span>
            </span>
            <button
              type="button"
              disabled={remove.isPending}
              onClick={() => remove.mutate(r.id)}
              className="rounded border border-gray-300 px-2 py-0.5 text-[11px] hover:bg-gray-50 disabled:opacity-50"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <form onSubmit={onAdd} className="flex flex-wrap items-end gap-2">
        <label className="text-[11px] text-gray-600">
          Total ≥ ₹
          <input
            type="number"
            min={0}
            step="0.01"
            required
            className={`${field} ml-1 w-28`}
            value={minTotal}
            onChange={(e) => setMinTotal(e.target.value)}
          />
        </label>
        <label className="text-[11px] text-gray-600">
          Advance ₹
          <input
            type="number"
            min={0}
            step="0.01"
            required
            className={`${field} ml-1 w-28`}
            value={advance}
            onChange={(e) => setAdvance(e.target.value)}
          />
        </label>
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded bg-gray-900 px-3 py-1 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          Add
        </button>
      </form>
    </div>
  );
}
