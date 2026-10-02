/**
 * Bootstraps the `LocationProvider` for the authenticated shell. Admins get
 * every active location (and may switch); staff are pinned to their single
 * assigned `location_id`. Locations come from the public locations endpoint.
 */

import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { useAuth } from '@/features/auth/useAuth';
import { LocationProvider, type LocationOption } from './useLocation';

interface LocationApiRow {
  id: number;
  name: string;
  slug: string;
}

export function LocationGate({ children }: { children: ReactNode }): JSX.Element {
  const { user } = useAuth();

  const { data, isLoading, isError } = useQuery<LocationApiRow[]>({
    queryKey: ['locations'],
    queryFn: () => api.get<LocationApiRow[]>('/api/v1/public/locations'),
  });

  if (isLoading) {
    return <div className="p-4 text-sm text-gray-500">Loading locations…</div>;
  }
  if (isError || data === undefined) {
    return <div className="p-4 text-sm text-red-600">Failed to load locations.</div>;
  }

  const all: LocationOption[] = data.map((l) => ({ id: l.id, name: l.name, slug: l.slug }));
  const isAdmin = user?.role === 'admin';
  const locations = isAdmin
    ? all
    : all.filter((l) => l.id === user?.location_id);

  return (
    <LocationProvider
      locations={locations}
      canSwitch={isAdmin}
      initialLocationId={isAdmin ? (locations[0]?.id ?? null) : (user?.location_id ?? null)}
    >
      {children}
    </LocationProvider>
  );
}
