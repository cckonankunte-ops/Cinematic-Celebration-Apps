import { useEffect, useState } from 'react';

import { publicApi, type Location } from '../../lib/api';
import { todayIsoInIST } from '../../lib/formatters';
import { telHref } from '../../lib/phone';

/**
 * Home-page hero widget: pick a branch and a date, then "Book Now" jumps into
 * the booking flow (`/book?location=<slug>&date=<iso>`), or "Call now" dials
 * the selected branch. Branches are fetched at runtime (static output can't
 * know them at build). The date defaults to today (IST) and cannot be in the
 * past. The server remains authoritative on availability; this is only a
 * convenient entry point.
 */
export default function HomeBookingWidget() {
  const today = todayIsoInIST();
  const [locations, setLocations] = useState<Location[]>([]);
  const [slug, setSlug] = useState('');
  const [date, setDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [callHint, setCallHint] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    publicApi
      .listLocations()
      .then((result) => {
        if (!active) return;
        setLocations(result);
      })
      .catch(() => {
        if (active) setError('Could not load branches right now.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selected = locations.find((l) => l.slug === slug) ?? null;

  const onBook = () => {
    setCallHint(null);
    if (!slug) {
      setCallHint('Please choose a location.');
      return;
    }
    if (!date) {
      setCallHint('Please choose a date.');
      return;
    }
    const params = new URLSearchParams({ location: slug, date });
    window.location.href = `/book?${params.toString()}`;
  };

  const onCall = () => {
    setCallHint(null);
    if (!selected) {
      setCallHint('Please choose a location first.');
      return;
    }
    const href = telHref(selected.phone);
    if (!href) {
      setCallHint(`${selected.name} has no phone number listed.`);
      return;
    }
    window.location.href = href;
  };

  if (loading) {
    return (
      <div className="rounded-2xl bg-white/95 p-4 text-sm text-gray-600 shadow-lg">
        Loading branches…
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-2xl bg-white/95 p-4 text-sm text-gray-700 shadow-lg">
        {error}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl rounded-2xl bg-white/95 p-4 text-left shadow-lg sm:p-5">
      <div className="grid gap-3 sm:grid-cols-[1fr,1fr,auto] sm:items-end">
        <label className="block text-sm font-semibold text-gray-700">
          Branch
          <select
            aria-label="Branch"
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand focus:outline-none"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          >
            <option value="">Choose a location</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.slug}>
                {loc.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm font-semibold text-gray-700">
          Date
          <input
            type="date"
            aria-label="Booking date"
            min={today}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-brand focus:outline-none"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onBook}
            className="flex-1 rounded-full bg-festive-hero px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-90 disabled:opacity-50 sm:flex-none"
          >
            Book Now
          </button>
          <button
            type="button"
            onClick={onCall}
            className="flex-1 rounded-full border border-brand px-5 py-2.5 text-sm font-semibold text-brand transition hover:bg-brand/5 sm:flex-none"
          >
            Call now
          </button>
        </div>
      </div>
      {callHint && <p className="mt-2 text-sm text-gray-600">{callHint}</p>}
    </div>
  );
}
