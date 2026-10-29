/**
 * TanStack Query hooks for admin bookings and the payments ledger. Reads are
 * keyed by `['bookings', ...]` / `['booking', id]`; every mutation invalidates
 * the relevant keys so the list and detail views stay in sync.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { api } from '@/api/client';
import type { BookingCreateValues } from './booking-schema';
import type {
  BookingListItem,
  BookingRead,
  PaymentRead,
  PriceBreakdownRead,
} from './types';

/** Body for recording a payment (amount already converted to paise). */
export interface RecordPaymentBody {
  method: 'cash' | 'upi' | 'card' | 'other';
  amount_paise: number;
  received_at?: string;
  note?: string;
}

/**
 * Request shape for the admin price preview. Mirrors the server's preview body:
 * ids + quantities only, money fields in paise. `booking_id` is sent in edit
 * mode so the coupon usage check excludes this booking's own redemption. The
 * server is authoritative on all money; this is only for the live summary.
 */
export interface AdminPreviewBody {
  location_id: number;
  plan_id: number;
  slot_id: number;
  booking_date: string;
  people: number;
  cake_id?: number;
  cake_weight_half_kg: number;
  special_decor: { id: number; quantity: number }[];
  combos: { id: number }[];
  led_name?: string;
  occasion_id?: number;
  coupon_code?: string;
  booking_id?: number;
  discount_paise: number;
  food_paise: number;
  other_paise: number;
  cleaning_paise: number;
}

function buildListQuery(
  locationId: number,
  date: string | null,
  status: string | null,
): string {
  const params = new URLSearchParams({ location_id: String(locationId) });
  if (date) {
    params.set('date', date);
  }
  if (status) {
    params.set('status', status);
  }
  return `/api/v1/admin/bookings?${params.toString()}`;
}

export function useBookings(
  locationId: number | null,
  date: string | null,
  status: string | null,
): UseQueryResult<BookingListItem[]> {
  return useQuery<BookingListItem[]>({
    queryKey: ['bookings', locationId, date, status],
    queryFn: () => api.get<BookingListItem[]>(buildListQuery(locationId as number, date, status)),
    enabled: locationId !== null,
  });
}

export function useBooking(id: number | null): UseQueryResult<BookingRead> {
  return useQuery<BookingRead>({
    queryKey: ['booking', id],
    queryFn: () => api.get<BookingRead>(`/api/v1/admin/bookings/${id}`),
    enabled: id !== null,
  });
}

/**
 * Create-booking request body. The posted shape drops the UI-only
 * `advance_rupees` field (see BookingFormPage) and sends the API's
 * `advance_amount_paise` (paise) + `advance_method` only when an advance was
 * entered. Everything else mirrors `BookingCreateValues`.
 */
/**
 * The booking body as the API expects it: the UI-only rupee money fields
 * (`*_rupees`) and the advance inputs are replaced by integer-paise fields.
 * `BookingFormPage.toApiMoney` performs the rupees -> paise mapping.
 */
type ApiBookingBody = Omit<
  BookingCreateValues,
  | 'advance_rupees'
  | 'advance_method'
  | 'discount_rupees'
  | 'food_rupees'
  | 'other_rupees'
  | 'cleaning_rupees'
> & {
  discount_paise: number;
  food_paise: number;
  other_paise: number;
  cleaning_paise: number;
};

export type CreateBookingBody = ApiBookingBody & {
  advance_amount_paise?: number;
  advance_method?: 'cash' | 'upi' | 'card' | 'other';
};

/** Edit body: a partial of the API booking body (money already in paise). */
export type UpdateBookingBody = Partial<ApiBookingBody>;

export function useCreateBooking(): UseMutationResult<
  BookingRead,
  unknown,
  CreateBookingBody
> {
  const qc = useQueryClient();
  return useMutation<BookingRead, unknown, CreateBookingBody>({
    mutationFn: (body) => api.post<BookingRead>('/api/v1/admin/bookings', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['bookings'] });
    },
  });
}

export function useUpdateBooking(
  id: number,
): UseMutationResult<BookingRead, unknown, UpdateBookingBody> {
  const qc = useQueryClient();
  return useMutation<BookingRead, unknown, UpdateBookingBody>({
    mutationFn: (body) => api.patch<BookingRead>(`/api/v1/admin/bookings/${id}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['bookings'] });
      void qc.invalidateQueries({ queryKey: ['booking', id] });
    },
  });
}

export function useAcceptBooking(
  id: number,
): UseMutationResult<BookingRead, unknown, { override_advance: boolean }> {
  const qc = useQueryClient();
  return useMutation<BookingRead, unknown, { override_advance: boolean }>({
    mutationFn: (body) =>
      api.post<BookingRead>(`/api/v1/admin/bookings/${id}/accept`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['bookings'] });
      void qc.invalidateQueries({ queryKey: ['booking', id] });
    },
  });
}

export function useRejectBooking(
  id: number,
): UseMutationResult<BookingRead, unknown, void> {
  const qc = useQueryClient();
  return useMutation<BookingRead, unknown, void>({
    mutationFn: () => api.post<BookingRead>(`/api/v1/admin/bookings/${id}/reject`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['bookings'] });
      void qc.invalidateQueries({ queryKey: ['booking', id] });
    },
  });
}

export function useBookingPayments(id: number | null): UseQueryResult<PaymentRead[]> {
  return useQuery<PaymentRead[]>({
    queryKey: ['booking', id, 'payments'],
    queryFn: () => api.get<PaymentRead[]>(`/api/v1/admin/bookings/${id}/payments`),
    enabled: id !== null,
  });
}

export function useRecordPayment(
  id: number,
): UseMutationResult<PaymentRead, unknown, RecordPaymentBody> {
  const qc = useQueryClient();
  return useMutation<PaymentRead, unknown, RecordPaymentBody>({
    mutationFn: (body) =>
      api.post<PaymentRead>(`/api/v1/admin/bookings/${id}/payments`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['booking', id] });
      void qc.invalidateQueries({ queryKey: ['booking', id, 'payments'] });
      void qc.invalidateQueries({ queryKey: ['bookings'] });
    },
  });
}

/**
 * Imperative price preview as a mutation (not a query) so the Edit/create form
 * can debounce-call it on field changes without creating a query key per
 * keystroke. Returns the server-authoritative `PriceBreakdownRead`.
 */
export function usePreviewBooking(): UseMutationResult<
  PriceBreakdownRead,
  unknown,
  AdminPreviewBody
> {
  return useMutation<PriceBreakdownRead, unknown, AdminPreviewBody>({
    mutationFn: (body) =>
      api.post<PriceBreakdownRead>('/api/v1/admin/bookings/preview', body),
  });
}

/**
 * Admin-only void of a payment. Posts a reason and gets back the booking's full
 * ledger (original + reversing entry). The void is server-authoritative; on
 * success we invalidate this booking's detail + payments and the bookings list
 * so every derived amount refetches.
 */
export function useVoidPayment(
  bookingId: number,
): UseMutationResult<PaymentRead[], unknown, { paymentId: number; reason: string }> {
  const qc = useQueryClient();
  return useMutation<PaymentRead[], unknown, { paymentId: number; reason: string }>({
    mutationFn: ({ paymentId, reason }) =>
      api.post<PaymentRead[]>(`/api/v1/admin/payments/${paymentId}/void`, { reason }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['booking', bookingId] });
      void qc.invalidateQueries({ queryKey: ['booking', bookingId, 'payments'] });
      void qc.invalidateQueries({ queryKey: ['bookings'] });
    },
  });
}
