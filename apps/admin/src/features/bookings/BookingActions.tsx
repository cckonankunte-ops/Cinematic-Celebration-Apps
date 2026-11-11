/**
 * Accept / Reject / WhatsApp actions for a single booking.
 *
 * - Accept opens a small confirm. Admins see an "override advance" checkbox so
 *   they can accept below the required advance; staff do not. We surface the
 *   paid-vs-required advance so the operator can see the shortfall.
 * - Reject confirms before calling the reject mutation.
 * - WhatsApp opens a prefilled share URL in a new tab.
 */

import { useState } from 'react';

import { ApiError } from '@/api/client';
import { formatRupees } from '@/lib/money';
import { buildWhatsappUrl, type BookingLike } from '@/lib/whatsapp';
import { useAuth } from '@/features/auth/useAuth';
import {
  useAcceptBooking,
  useCancelBooking,
  useRejectBooking,
} from './booking-queries';
import type { BookingStatus } from './types';

interface BookingActionsProps {
  bookingId: number;
  status: BookingStatus;
  advancePaise: number;
  amountPaidPaise: number;
  whatsapp: BookingLike;
}

export function BookingActions({
  bookingId,
  status,
  advancePaise,
  amountPaidPaise,
  whatsapp,
}: BookingActionsProps): JSX.Element {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const accept = useAcceptBooking(bookingId);
  const reject = useRejectBooking(bookingId);
  const cancel = useCancelBooking(bookingId);

  const [confirming, setConfirming] = useState<'accept' | 'reject' | 'cancel' | null>(
    null,
  );
  const [override, setOverride] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const advanceMet = amountPaidPaise >= advancePaise;
  const isPending = status === 'pending';
  // Cancel is admin-only and available any time for a live (pending/accepted)
  // booking. It sets the booking to 'cancelled' and frees the slot.
  const canCancel = isAdmin && (status === 'pending' || status === 'accepted');

  const onCancel = async (): Promise<void> => {
    setError(null);
    try {
      const reason = cancelReason.trim();
      await cancel.mutateAsync(reason ? { reason } : {});
      setConfirming(null);
      setCancelReason('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to cancel booking.');
    }
  };

  const onAccept = async (): Promise<void> => {
    setError(null);
    try {
      await accept.mutateAsync({ override_advance: isAdmin && override });
      setConfirming(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to accept booking.');
    }
  };

  const onReject = async (): Promise<void> => {
    setError(null);
    try {
      await reject.mutateAsync();
      setConfirming(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to reject booking.');
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {isPending && (
          <>
            <button
              type="button"
              onClick={() => setConfirming('accept')}
              className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700"
            >
              Accept
            </button>
            <button
              type="button"
              onClick={() => setConfirming('reject')}
              className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
            >
              Reject
            </button>
          </>
        )}
        {canCancel && (
          <button
            type="button"
            onClick={() => setConfirming('cancel')}
            className="rounded bg-orange-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-orange-700"
          >
            Cancel booking
          </button>
        )}
        <a
          href={buildWhatsappUrl(whatsapp)}
          target="_blank"
          rel="noreferrer"
          className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
        >
          WhatsApp
        </a>
      </div>

      {confirming === 'accept' && (
        <div className="space-y-2 rounded border border-gray-200 p-3">
          <p className="text-sm text-gray-700">
            Paid {formatRupees(amountPaidPaise)} of required advance{' '}
            {formatRupees(advancePaise)}.
          </p>
          {!advanceMet && !isAdmin && (
            <p className="text-xs text-amber-700">
              Advance not met. An admin must override to accept.
            </p>
          )}
          {isAdmin && !advanceMet && (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={override}
                onChange={(e) => setOverride(e.target.checked)}
              />
              Override advance requirement
            </label>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onAccept}
              disabled={accept.isPending}
              className="rounded bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-60"
            >
              Confirm accept
            </button>
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="rounded px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {confirming === 'reject' && (
        <div className="space-y-2 rounded border border-gray-200 p-3">
          <p className="text-sm text-gray-700">Reject this booking?</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onReject}
              disabled={reject.isPending}
              className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
            >
              Confirm reject
            </button>
            <button
              type="button"
              onClick={() => setConfirming(null)}
              className="rounded px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {confirming === 'cancel' && (
        <div className="space-y-2 rounded border border-gray-200 p-3">
          <p className="text-sm text-gray-700">
            Cancel this booking? This frees the slot. Add an optional reason
            (saved to the booking message).
          </p>
          <textarea
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            placeholder="Reason (optional)"
            rows={2}
            className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-brand focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={cancel.isPending}
              className="rounded bg-orange-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-60"
            >
              Confirm cancel
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirming(null);
                setCancelReason('');
              }}
              className="rounded px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
            >
              Back
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
