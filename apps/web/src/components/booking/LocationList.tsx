import { useEffect, useState } from 'react';
import { publicApi, type Location } from '../../lib/api';
import BranchThemes from './BranchThemes';

/**
 * Fetches active branches at runtime and links each to the booking flow
 * (`/book?location=slug`). Static output means we cannot know slugs at build
 * time, so this is a client-side island rather than a prerendered list.
 */
export default function LocationList() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Which branch's themes are expanded (one at a time keeps it tidy).
  const [openThemes, setOpenThemes] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    publicApi
      .listLocations()
      .then((result) => {
        if (active) {
          setLocations(result);
        }
      })
      .catch(() => {
        if (active) {
          setError('Could not load branches. Please try again later.');
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <p className="text-gray-500">Loading branches…</p>;
  }
  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  return (
    <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {locations.map((loc) => {
        // WhatsApp link from the branch phone (digits only; 10-digit numbers
        // get the 91 country code).
        const digits = (loc.phone ?? '').replace(/\D/g, '');
        const waNumber = digits.length === 10 ? `91${digits}` : digits;
        return (
          <li
            key={loc.id}
            className="card-lift flex flex-col rounded-2xl border border-white/60 bg-white p-6 shadow-sm"
          >
            <div className="flex items-center gap-2">
              <span className="text-2xl" aria-hidden="true">
                🎪
              </span>
              <h2 className="text-lg font-bold text-gray-900">{loc.name}</h2>
            </div>
            {loc.address && (
              <p className="mt-2 text-sm text-gray-600">{loc.address}</p>
            )}
            <div className="mt-3 space-y-1 text-sm">
              {loc.phone && (
                <a href={`tel:${digits}`} className="block text-brand hover:underline">
                  📞 {loc.phone}
                </a>
              )}
              {waNumber && (
                <a
                  href={`https://wa.me/${waNumber}`}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-festive-mint hover:underline"
                >
                  💬 WhatsApp
                </a>
              )}
              {loc.map_url && (
                <a
                  href={loc.map_url}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-brand hover:underline"
                >
                  📍 View on map
                </a>
              )}
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <a
                href={`/book?location=${encodeURIComponent(loc.slug)}`}
                className="inline-block rounded-full bg-festive-hero px-5 py-2.5 text-center text-sm font-semibold text-white shadow-sm transition hover:opacity-90"
              >
                Book this branch
              </a>
              <button
                type="button"
                onClick={() =>
                  setOpenThemes((cur) => (cur === loc.id ? null : loc.id))
                }
                className="rounded-full border border-brand px-5 py-2.5 text-sm font-semibold text-brand transition hover:bg-brand/5"
              >
                {openThemes === loc.id ? 'Hide themes' : 'View themes'}
              </button>
            </div>

            {openThemes === loc.id && (
              <div className="mt-4 border-t border-gray-100 pt-4">
                <p className="mb-3 text-sm font-semibold text-gray-700">
                  Decoration themes at {loc.name}
                </p>
                <BranchThemes locationId={loc.id} slug={loc.slug} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
