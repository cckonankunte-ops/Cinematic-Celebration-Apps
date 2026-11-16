import { useEffect, useRef, useState } from 'react';

import { publicApi, type Location } from '../../lib/api';
import { telHref } from '../../lib/phone';

/**
 * Floating call button, styled to match the WhatsApp FAB in Base.astro. Tap to
 * open a branch picker, then each branch is a `tel:` link to its number.
 * Branches without a phone are not shown. Branches load lazily on first open.
 *
 * Positioning: the WhatsApp FAB sits at bottom-left (mobile) / bottom-right
 * (sm+). This button stacks just ABOVE it in the same corner so the two don't
 * overlap the booking page's sticky action bar.
 */
export default function FloatingCall() {
  const [open, setOpen] = useState(false);
  const [locations, setLocations] = useState<Location[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Lazy-load branches the first time the panel opens.
  useEffect(() => {
    if (!open || locations !== null || error) return;
    let active = true;
    publicApi
      .listLocations()
      .then((result) => {
        if (active) setLocations(result.filter((l) => telHref(l.phone) !== null));
      })
      .catch(() => {
        if (active) setError('Could not load branches.');
      });
    return () => {
      active = false;
    };
  }, [open, locations, error]);

  // Close when clicking outside.
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, [open]);

  return (
    <div
      ref={rootRef}
      className="fixed bottom-36 left-4 z-50 sm:bottom-20 sm:left-auto sm:right-4"
    >
      {open && (
        <div className="mb-2 w-60 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg">
          <p className="border-b border-gray-100 px-4 py-2 text-sm font-semibold text-gray-700">
            Call a branch
          </p>
          <ul className="max-h-64 overflow-y-auto">
            {locations === null && !error && (
              <li className="px-4 py-3 text-sm text-gray-500">Loading…</li>
            )}
            {error && <li className="px-4 py-3 text-sm text-red-600">{error}</li>}
            {locations !== null && locations.length === 0 && !error && (
              <li className="px-4 py-3 text-sm text-gray-500">
                No branches available.
              </li>
            )}
            {locations?.map((loc) => (
              <li key={loc.id}>
                <a
                  className="flex items-center justify-between px-4 py-3 text-sm text-gray-800 hover:bg-gray-50"
                  href={telHref(loc.phone) as string}
                >
                  <span>{loc.name}</span>
                  <span aria-hidden="true" className="text-brand">
                    ›
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        aria-label="Call a branch"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex h-14 w-14 items-center justify-center rounded-full bg-festive-hero text-white shadow-lg transition hover:opacity-90"
      >
        <svg viewBox="0 0 24 24" className="h-7 w-7 fill-current" aria-hidden="true">
          <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z" />
        </svg>
      </button>
    </div>
  );
}
