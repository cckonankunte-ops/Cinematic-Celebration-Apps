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
  CakeAdminRead,
  NamedAddonAdminRead,
  PlanAdminRead,
  PlanCreateBody,
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
