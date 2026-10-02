/**
 * TanStack Query hooks for the admin-only analytics reports. Each report is
 * keyed by its name + location + date and disabled until a location is
 * selected. The endpoints themselves require the `admin` role server-side.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { api } from '@/api/client';
import type { AdvanceAmountsResult, SlotAmountsResult } from './types';

function buildQuery(path: string, locationId: number, date: string): string {
  const params = new URLSearchParams({
    location_id: String(locationId),
    date,
  });
  return `${path}?${params.toString()}`;
}

export function useSlotAmounts(
  locationId: number | null,
  date: string,
): UseQueryResult<SlotAmountsResult> {
  return useQuery<SlotAmountsResult>({
    queryKey: ['analytics', 'slot-amounts', locationId, date],
    queryFn: () =>
      api.get<SlotAmountsResult>(
        buildQuery('/api/v1/admin/analytics/slot-amounts', locationId as number, date),
      ),
    enabled: locationId !== null,
  });
}

export function useAdvanceAmounts(
  locationId: number | null,
  date: string,
): UseQueryResult<AdvanceAmountsResult> {
  return useQuery<AdvanceAmountsResult>({
    queryKey: ['analytics', 'advance-amounts', locationId, date],
    queryFn: () =>
      api.get<AdvanceAmountsResult>(
        buildQuery('/api/v1/admin/analytics/advance-amounts', locationId as number, date),
      ),
    enabled: locationId !== null,
  });
}
