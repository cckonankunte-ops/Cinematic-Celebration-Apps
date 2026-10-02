/**
 * TanStack Query hook for the admin cakesheet. Lists cake orders for a location
 * + date as flat rows the UI groups by slot. Keyed by
 * `['cakesheet', locationId, date]`; disabled until a location is selected.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { CakesheetRow } from './types';

function buildQuery(locationId: number, date: string): string {
  const params = new URLSearchParams({
    location_id: String(locationId),
    date,
  });
  return `/api/v1/admin/cakesheet?${params.toString()}`;
}

export function useCakesheet(
  locationId: number | null,
  date: string,
): UseQueryResult<CakesheetRow[]> {
  return useQuery<CakesheetRow[]>({
    queryKey: ['cakesheet', locationId, date],
    queryFn: () => api.get<CakesheetRow[]>(buildQuery(locationId as number, date)),
    enabled: locationId !== null,
  });
}
