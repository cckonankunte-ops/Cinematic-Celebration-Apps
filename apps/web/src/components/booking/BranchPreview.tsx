import { useEffect, useState } from 'react';
import { publicApi, type Location } from '../../lib/api';

/**
 * Compact branch cards for the home page. Fetches active branches at runtime
 * (static output can't know them at build) and links each into the booking
 * flow. Kept lightweight; when the branch count grows this can switch to a
 * "see all" layout.
 */
export default function BranchPreview() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    publicApi
      .listLocations()
      .then((result) => {
        if (active) setLocations(result);
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

  if (loading) {
    return <p className="text-gray-500">Loading branches…</p>;
  }
  if (error) {
    return <p className="text-gray-600">{error}</p>;
  }

  return (
    <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {locations.map((loc) => (
        <li
          key={loc.id}
          className="card-lift flex flex-col rounded-2xl border border-white/60 bg-white p-6 shadow-sm"
        >
          <div className="flex items-center gap-2">
            <span className="text-2xl" aria-hidden="true">
              🎪
            </span>
            <h3 className="text-lg font-bold text-gray-900">{loc.name}</h3>
          </div>
          {loc.address && (
            <p className="mt-2 line-clamp-2 text-sm text-gray-600">{loc.address}</p>
          )}
          <a
            href={`/book?location=${encodeURIComponent(loc.slug)}`}
            className="mt-5 inline-block rounded-full bg-festive-hero px-5 py-2.5 text-center text-sm font-semibold text-white shadow-sm transition hover:opacity-90"
          >
            Book this branch
          </a>
        </li>
      ))}
    </ul>
  );
}
