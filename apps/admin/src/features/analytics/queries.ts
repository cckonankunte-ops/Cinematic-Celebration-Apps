/**
 * TanStack Query hooks for the admin-only analytics reports. Each report is
 * keyed by name + location + filters, runs only for the active tab, and is
 * disabled until a location is selected. The endpoints themselves require the
 * `admin` role server-side.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { api } from '@/api/client';
import type {
  AnalyticsFilters,
  CreatedBookingsResult,
  SlotAmountsResult,
  TodayIncomeResult,
} from './types';

/** Query string for a report: location, inclusive date range, repeated status. */
export function buildAnalyticsQuery(
  locationId: number,
  filters: AnalyticsFilters,
): URLSearchParams {
  const params = new URLSearchParams({
    location_id: String(locationId),
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
  });
  for (const status of filters.statuses) {
    params.append('status', status);
  }
  return params;
}

function useReport<T>(
  name: string,
  locationId: number | null,
  filters: AnalyticsFilters,
  enabled: boolean,
  requireStatus: boolean,
): UseQueryResult<T> {
  // An empty status list on a booking report would silently fall back to the
  // server default (accepted), so don't query until one is chosen.
  const valid =
    filters.dateFrom !== '' &&
    filters.dateTo !== '' &&
    filters.dateTo >= filters.dateFrom &&
    (!requireStatus || filters.statuses.length > 0);
  return useQuery<T>({
    queryKey: ['analytics', name, locationId, filters],
    queryFn: () =>
      api.get<T>(
        `/api/v1/admin/analytics/${name}?${buildAnalyticsQuery(
          locationId as number,
          filters,
        ).toString()}`,
      ),
    enabled: enabled && locationId !== null && valid,
  });
}

export function useSlotAmounts(
  locationId: number | null,
  filters: AnalyticsFilters,
  enabled = true,
): UseQueryResult<SlotAmountsResult> {
  return useReport<SlotAmountsResult>('slot-amounts', locationId, filters, enabled, true);
}

export function useCreatedBookings(
  locationId: number | null,
  filters: AnalyticsFilters,
  enabled = true,
): UseQueryResult<CreatedBookingsResult> {
  return useReport<CreatedBookingsResult>(
    'created-bookings',
    locationId,
    filters,
    enabled,
    true,
  );
}

export function useTodayIncome(
  locationId: number | null,
  filters: AnalyticsFilters,
  enabled = true,
): UseQueryResult<TodayIncomeResult> {
  return useReport<TodayIncomeResult>('today-income', locationId, filters, enabled, false);
}
