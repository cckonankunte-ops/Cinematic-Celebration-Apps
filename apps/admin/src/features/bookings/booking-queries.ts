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
import type { BookingListItem, BookingRead, PaymentRead } from './types';

/** Body for recording a payment (amount already converted to paise). */
export interface RecordPaymentBody {
  method: 'cash' | 'upi' | 'card' | 'other';
  amount_paise: number;
  received_at?: string;
  note?: string;
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

export function useCreateBooking(): UseMutationResult<
  BookingRead,
  unknown,
  BookingCreateValues
> {
  const qc = useQueryClient();
  return useMutation<BookingRead, unknown, BookingCreateValues>({
    mutationFn: (body) => api.post<BookingRead>('/api/v1/admin/bookings', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['bookings'] });
    },
  });
}

export function useUpdateBooking(
  id: number,
): UseMutationResult<BookingRead, unknown, Partial<BookingCreateValues>> {
  const qc = useQueryClient();
  return useMutation<BookingRead, unknown, Partial<BookingCreateValues>>({
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
