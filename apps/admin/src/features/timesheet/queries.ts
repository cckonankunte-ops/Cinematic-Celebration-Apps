/**
 * TanStack Query hook for the admin timesheet. The timesheet lists accepted
 * bookings for a location + date, flat rows the UI groups by slot. Keyed by
 * `['timesheet', locationId, date]`; disabled until a location is selected.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { TimesheetRow } from './types';

function buildQuery(locationId: number, date: string): string {
  const params = new URLSearchParams({
    location_id: String(locationId),
    date,
  });
  return `/api/v1/admin/timesheet?${params.toString()}`;
}

export function useTimesheet(
  locationId: number | null,
  date: string,
): UseQueryResult<TimesheetRow[]> {
  return useQuery<TimesheetRow[]>({
    queryKey: ['timesheet', locationId, date],
    queryFn: () => api.get<TimesheetRow[]>(buildQuery(locationId as number, date)),
    enabled: locationId !== null,
  });
}
