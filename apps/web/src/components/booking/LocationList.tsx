import { useEffect, useState } from 'react';
import { publicApi, type Location } from '../../lib/api';

/**
 * Fetches active branches at runtime and links each to the booking flow
 * (`/book?location=slug`). Static output means we cannot know slugs at build
 * time, so this is a client-side island rather than a prerendered list.
 */
export default function LocationList() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {locations.map((loc) => (
        <li
          key={loc.id}
          className="rounded border border-gray-200 p-5 hover:border-brand"
        >
          <h2 className="text-lg font-semibold">{loc.name}</h2>
          {loc.address && (
            <p className="mt-1 text-sm text-gray-600">{loc.address}</p>
          )}
          {loc.phone && (
            <p className="mt-1 text-sm text-gray-600">{loc.phone}</p>
          )}
          <div className="mt-4 flex gap-3">
            <a
              href={`/book?location=${encodeURIComponent(loc.slug)}`}
              className="rounded bg-brand px-4 py-2 text-sm text-white"
            >
              Book now
            </a>
          </div>
        </li>
      ))}
    </ul>
  );
}
