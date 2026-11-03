/**
 * Admin location settings: per-branch working hours, the online-booking cutoff,
 * and the late-booking switch (R5, R6). Times are IST "HH:MM". `closes_at` may
 * be earlier than `opens_at`, meaning close is the next day (e.g. 10:00 → 01:00).
 * The late switch lets customers self-book past the cutoff; staff/admin are
 * never blocked by the cutoff.
 */

import { useEffect, useState } from 'react';

import { useLocationsAdmin, useUpdateLocationHours } from './queries';
import type { LocationAdminRead } from './types';

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

  const field = 'rounded border border-gray-300 px-2 py-1 text-sm';

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
      <div className="space-y-2">
        {locations.data?.map((loc) => (
          <LocationRow key={loc.id} loc={loc} />
        ))}
      </div>
    </div>
  );
}
