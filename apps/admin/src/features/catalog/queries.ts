/**
 * TanStack Query hooks for admin catalog management (admin-only endpoints).
 * Lists are keyed by resource + scope; every mutation invalidates the matching
 * list. "Delete" calls the soft-delete (deactivate) endpoints — rows are never
 * hard-deleted server-side.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { api } from '@/api/client';
import type {
  AdvanceRuleCreateBody,
  AdvanceRuleRead,
  CakeAdminRead,
  CakeCreateBody,
  CakeUpdateBody,
  ComboCreateBody,
  ComboUpdateBody,
  DecorCreateBody,
  DecorUpdateBody,
  DisallowedTimeCreateBody,
  DisallowedTimeRead,
  LocationAdminRead,
  LocationHoursUpdateBody,
  NamedAddonAdminRead,
  PlanAdminRead,
  PlanCreateBody,
  PlanPricingAdminRead,
  PlanPricingCreateBody,
  PlanUpdateBody,
  SlotAdminRead,
  SlotCreateBody,
} from './types';

// --- Plans ---
export function usePlans(locationId: number | null): UseQueryResult<PlanAdminRead[]> {
  return useQuery<PlanAdminRead[]>({
    queryKey: ['catalog', 'plans', locationId],
    queryFn: () =>
      api.get<PlanAdminRead[]>(`/api/v1/admin/plans?location_id=${locationId as number}`),
    enabled: locationId !== null,
  });
}

export function useCreatePlan(
  locationId: number | null,
): UseMutationResult<PlanAdminRead, unknown, PlanCreateBody> {
  const qc = useQueryClient();
  return useMutation<PlanAdminRead, unknown, PlanCreateBody>({
    mutationFn: (body) => api.post<PlanAdminRead>('/api/v1/admin/plans', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'plans', locationId] });
    },
  });
}

export function useUpdatePlan(
  locationId: number | null,
  planId: number,
): UseMutationResult<PlanAdminRead, unknown, PlanUpdateBody> {
  const qc = useQueryClient();
  return useMutation<PlanAdminRead, unknown, PlanUpdateBody>({
    mutationFn: (body) => api.patch<PlanAdminRead>(`/api/v1/admin/plans/${planId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'plans', locationId] });
    },
  });
}

export function useDeactivatePlan(
  locationId: number | null,
): UseMutationResult<PlanAdminRead, unknown, number> {
  const qc = useQueryClient();
  return useMutation<PlanAdminRead, unknown, number>({
    mutationFn: (planId) => api.del<PlanAdminRead>(`/api/v1/admin/plans/${planId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'plans', locationId] });
    },
  });
}

// --- Slots (scoped to a plan) ---
export function useSlots(planId: number | null): UseQueryResult<SlotAdminRead[]> {
  return useQuery<SlotAdminRead[]>({
    queryKey: ['catalog', 'slots', planId],
    queryFn: () =>
      api.get<SlotAdminRead[]>(`/api/v1/admin/slots?plan_id=${planId as number}`),
    enabled: planId !== null,
  });
}

export function useCreateSlot(
  planId: number | null,
): UseMutationResult<SlotAdminRead, unknown, SlotCreateBody> {
  const qc = useQueryClient();
  return useMutation<SlotAdminRead, unknown, SlotCreateBody>({
    mutationFn: (body) => api.post<SlotAdminRead>('/api/v1/admin/slots', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'slots', planId] });
    },
  });
}

export function useDeactivateSlot(
  planId: number | null,
): UseMutationResult<SlotAdminRead, unknown, number> {
  const qc = useQueryClient();
  return useMutation<SlotAdminRead, unknown, number>({
    mutationFn: (slotId) => api.del<SlotAdminRead>(`/api/v1/admin/slots/${slotId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'slots', planId] });
    },
  });
}

// --- Cakes ---
export function useCakes(locationId: number | null): UseQueryResult<CakeAdminRead[]> {
  return useQuery<CakeAdminRead[]>({
    queryKey: ['catalog', 'cakes', locationId],
    queryFn: () =>
      api.get<CakeAdminRead[]>(`/api/v1/admin/cakes?location_id=${locationId as number}`),
    enabled: locationId !== null,
  });
}

export function useCreateCake(
  locationId: number | null,
): UseMutationResult<CakeAdminRead, unknown, CakeCreateBody> {
  const qc = useQueryClient();
  return useMutation<CakeAdminRead, unknown, CakeCreateBody>({
    mutationFn: (body) => api.post<CakeAdminRead>('/api/v1/admin/cakes', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'cakes', locationId] });
    },
  });
}

export function useUpdateCake(
  locationId: number | null,
  cakeId: number,
): UseMutationResult<CakeAdminRead, unknown, CakeUpdateBody> {
  const qc = useQueryClient();
  return useMutation<CakeAdminRead, unknown, CakeUpdateBody>({
    mutationFn: (body) => api.patch<CakeAdminRead>(`/api/v1/admin/cakes/${cakeId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'cakes', locationId] });
    },
  });
}

export function useDeactivateCake(
  locationId: number | null,
): UseMutationResult<CakeAdminRead, unknown, number> {
  const qc = useQueryClient();
  return useMutation<CakeAdminRead, unknown, number>({
    mutationFn: (cakeId) => api.del<CakeAdminRead>(`/api/v1/admin/cakes/${cakeId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'cakes', locationId] });
    },
  });
}

// --- Special decor + combos (same read shape) ---
export function useSpecialDecor(
  locationId: number | null,
): UseQueryResult<NamedAddonAdminRead[]> {
  return useQuery<NamedAddonAdminRead[]>({
    queryKey: ['catalog', 'special-decor', locationId],
    queryFn: () =>
      api.get<NamedAddonAdminRead[]>(
        `/api/v1/admin/special-decor?location_id=${locationId as number}`,
      ),
    enabled: locationId !== null,
  });
}

export function useCreateDecor(
  locationId: number | null,
): UseMutationResult<NamedAddonAdminRead, unknown, DecorCreateBody> {
  const qc = useQueryClient();
  return useMutation<NamedAddonAdminRead, unknown, DecorCreateBody>({
    mutationFn: (body) => api.post<NamedAddonAdminRead>('/api/v1/admin/special-decor', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'special-decor', locationId] });
    },
  });
}

export function useUpdateDecor(
  locationId: number | null,
  decorId: number,
): UseMutationResult<NamedAddonAdminRead, unknown, DecorUpdateBody> {
  const qc = useQueryClient();
  return useMutation<NamedAddonAdminRead, unknown, DecorUpdateBody>({
    mutationFn: (body) =>
      api.patch<NamedAddonAdminRead>(`/api/v1/admin/special-decor/${decorId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'special-decor', locationId] });
    },
  });
}

export function useDeactivateDecor(
  locationId: number | null,
): UseMutationResult<NamedAddonAdminRead, unknown, number> {
  const qc = useQueryClient();
  return useMutation<NamedAddonAdminRead, unknown, number>({
    mutationFn: (decorId) =>
      api.del<NamedAddonAdminRead>(`/api/v1/admin/special-decor/${decorId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'special-decor', locationId] });
    },
  });
}

export function useCombos(
  locationId: number | null,
): UseQueryResult<NamedAddonAdminRead[]> {
  return useQuery<NamedAddonAdminRead[]>({
    queryKey: ['catalog', 'combos', locationId],
    queryFn: () =>
      api.get<NamedAddonAdminRead[]>(
        `/api/v1/admin/combos?location_id=${locationId as number}`,
      ),
    enabled: locationId !== null,
  });
}

/**
 * Create a combo. Combos may carry optional cake/LED baselines (paise) that the
 * pricing engine floors combo deltas against; a null baseline means the combo
 * does not absorb that component.
 */
export function useCreateCombo(
  locationId: number | null,
): UseMutationResult<NamedAddonAdminRead, unknown, ComboCreateBody> {
  const qc = useQueryClient();
  return useMutation<NamedAddonAdminRead, unknown, ComboCreateBody>({
    mutationFn: (body) => api.post<NamedAddonAdminRead>('/api/v1/admin/combos', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'combos', locationId] });
    },
  });
}

export function useUpdateCombo(
  locationId: number | null,
  comboId: number,
): UseMutationResult<NamedAddonAdminRead, unknown, ComboUpdateBody> {
  const qc = useQueryClient();
  return useMutation<NamedAddonAdminRead, unknown, ComboUpdateBody>({
    mutationFn: (body) =>
      api.patch<NamedAddonAdminRead>(`/api/v1/admin/combos/${comboId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'combos', locationId] });
    },
  });
}

export function useDeactivateCombo(
  locationId: number | null,
): UseMutationResult<NamedAddonAdminRead, unknown, number> {
  const qc = useQueryClient();
  return useMutation<NamedAddonAdminRead, unknown, number>({
    mutationFn: (comboId) => api.del<NamedAddonAdminRead>(`/api/v1/admin/combos/${comboId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'combos', locationId] });
    },
  });
}

// --- Plan pricing (per-duration base price + advance, R11) ---
export function usePlanPricing(
  planId: number | null,
): UseQueryResult<PlanPricingAdminRead[]> {
  return useQuery<PlanPricingAdminRead[]>({
    queryKey: ['catalog', 'plan-pricing', planId],
    queryFn: () =>
      api.get<PlanPricingAdminRead[]>(
        `/api/v1/admin/plan-pricing?plan_id=${planId as number}`,
      ),
    enabled: planId !== null,
  });
}

export function useCreatePlanPricing(
  planId: number | null,
): UseMutationResult<PlanPricingAdminRead, unknown, PlanPricingCreateBody> {
  const qc = useQueryClient();
  return useMutation<PlanPricingAdminRead, unknown, PlanPricingCreateBody>({
    mutationFn: (body) =>
      api.post<PlanPricingAdminRead>('/api/v1/admin/plan-pricing', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'plan-pricing', planId] });
    },
  });
}

export function useDeactivatePlanPricing(
  planId: number | null,
): UseMutationResult<PlanPricingAdminRead, unknown, number> {
  const qc = useQueryClient();
  return useMutation<PlanPricingAdminRead, unknown, number>({
    mutationFn: (pricingId) =>
      api.del<PlanPricingAdminRead>(`/api/v1/admin/plan-pricing/${pricingId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'plan-pricing', planId] });
    },
  });
}

// --- Locations (working hours + online-booking policy) ---
export function useLocationsAdmin(): UseQueryResult<LocationAdminRead[]> {
  return useQuery<LocationAdminRead[]>({
    queryKey: ['catalog', 'locations'],
    queryFn: () => api.get<LocationAdminRead[]>('/api/v1/admin/locations'),
  });
}

export function useUpdateLocationHours(): UseMutationResult<
  LocationAdminRead,
  unknown,
  { locationId: number; body: LocationHoursUpdateBody }
> {
  const qc = useQueryClient();
  return useMutation<
    LocationAdminRead,
    unknown,
    { locationId: number; body: LocationHoursUpdateBody }
  >({
    mutationFn: ({ locationId, body }) =>
      api.patch<LocationAdminRead>(`/api/v1/admin/locations/${locationId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'locations'] });
    },
  });
}

// --- Disallowed booking-time ranges (per branch) ---
export function useDisallowedTimes(
  locationId: number | null,
): UseQueryResult<DisallowedTimeRead[]> {
  return useQuery<DisallowedTimeRead[]>({
    queryKey: ['catalog', 'disallowed-times', locationId],
    queryFn: () =>
      api.get<DisallowedTimeRead[]>(
        `/api/v1/admin/locations/${locationId as number}/disallowed-times`,
      ),
    enabled: locationId !== null,
  });
}

export function useCreateDisallowedTime(
  locationId: number | null,
): UseMutationResult<DisallowedTimeRead, unknown, DisallowedTimeCreateBody> {
  const qc = useQueryClient();
  return useMutation<DisallowedTimeRead, unknown, DisallowedTimeCreateBody>({
    mutationFn: (body) =>
      api.post<DisallowedTimeRead>(
        `/api/v1/admin/locations/${locationId as number}/disallowed-times`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['catalog', 'disallowed-times', locationId],
      });
    },
  });
}

export function useDeleteDisallowedTime(
  locationId: number | null,
): UseMutationResult<void, unknown, number> {
  const qc = useQueryClient();
  return useMutation<void, unknown, number>({
    mutationFn: (rowId) =>
      api.del<void>(
        `/api/v1/admin/locations/${locationId as number}/disallowed-times/${rowId}`,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['catalog', 'disallowed-times', locationId],
      });
    },
  });
}

// --- Advance rules (per branch) ---
export function useAdvanceRules(
  locationId: number | null,
): UseQueryResult<AdvanceRuleRead[]> {
  return useQuery<AdvanceRuleRead[]>({
    queryKey: ['catalog', 'advance-rules', locationId],
    queryFn: () =>
      api.get<AdvanceRuleRead[]>(
        `/api/v1/admin/locations/${locationId as number}/advance-rules`,
      ),
    enabled: locationId !== null,
  });
}

export function useCreateAdvanceRule(
  locationId: number | null,
): UseMutationResult<AdvanceRuleRead, unknown, AdvanceRuleCreateBody> {
  const qc = useQueryClient();
  return useMutation<AdvanceRuleRead, unknown, AdvanceRuleCreateBody>({
    mutationFn: (body) =>
      api.post<AdvanceRuleRead>(
        `/api/v1/admin/locations/${locationId as number}/advance-rules`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['catalog', 'advance-rules', locationId],
      });
    },
  });
}

export function useDeleteAdvanceRule(
  locationId: number | null,
): UseMutationResult<void, unknown, number> {
  const qc = useQueryClient();
  return useMutation<void, unknown, number>({
    mutationFn: (ruleId) =>
      api.del<void>(
        `/api/v1/admin/locations/${locationId as number}/advance-rules/${ruleId}`,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['catalog', 'advance-rules', locationId],
      });
    },
  });
}
