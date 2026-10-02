/**
 * TanStack Query hooks for the public catalog data that populate the booking
 * form selects. These read the public endpoints (admins/staff may read them
 * too) scoped by location or plan. Queries are disabled until their required
 * id is available so cascading selects fetch only when relevant.
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { api } from '@/api/client';

export interface PlanOption {
  id: number;
  location_id: number;
  title: string;
  price_paise: number;
  people_allowed: number;
  max_people_allowed: number;
  extra_guest_paise: number;
  advance_paise: number;
}

export interface SlotOption {
  id: number;
  plan_id: number;
  description: string;
  show_combos: boolean;
  sort_order: number;
}

export interface CatalogItemOption {
  id: number;
  name: string;
  price_paise: number;
}

export interface OccasionOption {
  id: number;
  name: string;
}

function useCatalog<T>(
  key: readonly unknown[],
  path: string,
  enabled: boolean,
): UseQueryResult<T> {
  return useQuery<T>({
    queryKey: key,
    queryFn: () => api.get<T>(path),
    enabled,
  });
}

export function usePlans(locationId: number | null): UseQueryResult<PlanOption[]> {
  return useCatalog<PlanOption[]>(
    ['plans', locationId],
    `/api/v1/public/locations/${locationId}/plans`,
    locationId !== null,
  );
}

export function useSlots(planId: number | null): UseQueryResult<SlotOption[]> {
  return useCatalog<SlotOption[]>(
    ['slots', planId],
    `/api/v1/public/plans/${planId}/slots`,
    planId !== null,
  );
}

/** Shapes `CakeRead` ({description}) into the shared `{name}` option. */
export function useCakes(locationId: number | null): UseQueryResult<CatalogItemOption[]> {
  return useQuery<CatalogItemOption[]>({
    queryKey: ['cakes', locationId],
    queryFn: async () => {
      const rows = await api.get<{ id: number; description: string; price_paise: number }[]>(
        `/api/v1/public/locations/${locationId}/cakes`,
      );
      return rows.map((r) => ({ id: r.id, name: r.description, price_paise: r.price_paise }));
    },
    enabled: locationId !== null,
  });
}

export function useSpecialDecor(
  locationId: number | null,
): UseQueryResult<CatalogItemOption[]> {
  return useCatalog<CatalogItemOption[]>(
    ['special-decor', locationId],
    `/api/v1/public/locations/${locationId}/special-decor`,
    locationId !== null,
  );
}

export function useCombos(locationId: number | null): UseQueryResult<CatalogItemOption[]> {
  return useCatalog<CatalogItemOption[]>(
    ['combos', locationId],
    `/api/v1/public/locations/${locationId}/combos`,
    locationId !== null,
  );
}

export function useOccasions(locationId: number | null): UseQueryResult<OccasionOption[]> {
  return useCatalog<OccasionOption[]>(
    ['occasions', locationId],
    `/api/v1/public/locations/${locationId}/occasions`,
    locationId !== null,
  );
}
