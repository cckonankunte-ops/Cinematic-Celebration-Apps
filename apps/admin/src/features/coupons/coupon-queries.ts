/**
 * TanStack Query hooks for admin coupon management (admin-only endpoints).
 * Coupons are location-scoped; the list is keyed by location and every mutation
 * invalidates it. Coupons stay server-authoritative — the admin only authors
 * the rule; the server validates and computes the discount at booking time.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { api } from '@/api/client';

/** Percentage base for a percentage coupon. */
export type CouponType = 'flat' | 'percentage';
export type PercentageBase = 'total' | 'selected_components';

/** Which price components a `selected_components` percentage applies to. */
export interface CouponComponents {
  plan: boolean;
  extra_guest: boolean;
  decor: boolean;
  combos: boolean;
  cake: boolean;
  food: boolean;
}

/** Mirrors the API `CouponRead`. Money is integer paise. */
export interface CouponRead {
  id: number;
  location_id: number;
  code: string;
  type: CouponType;
  /** Flat → paise; percentage → whole-number percent (0..100). */
  value: number;
  cap_paise: number | null;
  percentage_base: PercentageBase;
  components: CouponComponents | null;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  one_time: boolean;
  total_usage_limit: number | null;
  per_customer_limit: number | null;
  min_order_paise: number | null;
}

/** Mirrors the API `CouponCreate`. */
export interface CouponCreateBody {
  location_id: number;
  code: string;
  type: CouponType;
  value: number;
  cap_paise?: number | null;
  percentage_base: PercentageBase;
  components?: CouponComponents | null;
  effective_from?: string | null;
  effective_to?: string | null;
  is_active: boolean;
  one_time: boolean;
  total_usage_limit?: number | null;
  per_customer_limit?: number | null;
  min_order_paise?: number | null;
}

/** PATCH body: every field optional (partial update). */
export type CouponUpdateBody = Partial<Omit<CouponCreateBody, 'location_id'>>;

export function useCoupons(locationId: number | null): UseQueryResult<CouponRead[]> {
  return useQuery<CouponRead[]>({
    queryKey: ['coupons', locationId],
    queryFn: () =>
      api.get<CouponRead[]>(`/api/v1/admin/coupons?location_id=${locationId as number}`),
    enabled: locationId !== null,
  });
}

export function useCreateCoupon(): UseMutationResult<CouponRead, unknown, CouponCreateBody> {
  const qc = useQueryClient();
  return useMutation<CouponRead, unknown, CouponCreateBody>({
    mutationFn: (body) => api.post<CouponRead>('/api/v1/admin/coupons', body),
    onSuccess: (coupon) => {
      void qc.invalidateQueries({ queryKey: ['coupons', coupon.location_id] });
    },
  });
}

export function useUpdateCoupon(
  id: number,
): UseMutationResult<CouponRead, unknown, CouponUpdateBody> {
  const qc = useQueryClient();
  return useMutation<CouponRead, unknown, CouponUpdateBody>({
    mutationFn: (body) => api.patch<CouponRead>(`/api/v1/admin/coupons/${id}`, body),
    onSuccess: (coupon) => {
      void qc.invalidateQueries({ queryKey: ['coupons', coupon.location_id] });
    },
  });
}
