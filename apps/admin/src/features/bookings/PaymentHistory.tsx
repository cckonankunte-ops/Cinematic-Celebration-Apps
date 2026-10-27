/**
 * Payment ledger for a booking, shown on the Edit page. Lists payments
 * oldest-first (passed in from the loaded `BookingRead.payments`), marks voided
 * entries, labels reversing entries, and derives Amount paid / Amount due from
 * the rows. Staff may record a payment; only admins may void a non-voided,
 * non-reversal payment (which appends a reversing entry — the void is
 * server-authoritative).
 */

import { useState } from 'react';

import { ApiError } from '@/api/client';
import { formatDate } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { useAuth } from '@/features/auth/useAuth';
import { PaymentDialog } from './PaymentDialog';
import { useVoidPayment } from './booking-queries';
import { paymentVoidSchema } from './booking-schema';
import type { PaymentRead } from './types';

interface PaymentHistoryProps {
  bookingId: number;
  /** Payments oldest-first (from `BookingRead.payments`). */
  payments: PaymentRead[];
  /** The booking's authoritative total; due = total − sum(payments). */
  totalPaise: number;
}

export function PaymentHistory({
  bookingId,
  payments,
  totalPaise,
}: PaymentHistoryProps): JSX.Element {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);

  // Paid is the ledger sum; a voided payment and its reversal net to zero.
  const amountPaid = payments.reduce((sum, p) => sum + p.amount_paise, 0);
  const amountDue = totalPaise - amountPaid;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">Payments</h2>
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          Record payment
        </button>
      </div>

      {payments.length === 0 && (
        <p className="text-sm text-gray-500">No payments recorded yet.</p>
      )}

      {payments.length > 0 && (
        <ul className="divide-y divide-gray-200 rounded border border-gray-200">
          {payments.map((payment) => (
            <PaymentRow
              key={payment.id}
              bookingId={bookingId}
              payment={payment}
              canVoid={isAdmin}
            />
          ))}
        </ul>
      )}

      <div className="flex justify-between text-sm text-gray-700">
        <span className="font-medium">Amount paid</span>
        <span>{formatRupees(amountPaid)}</span>
      </div>
      <div className="flex justify-between text-sm text-gray-700">
        <span className="font-medium">Amount due</span>
        <span>{formatRupees(amountDue)}</span>
      </div>

      <PaymentDialog
        bookingId={bookingId}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
      />
    </section>
  );
}

interface PaymentRowProps {
  bookingId: number;
  payment: PaymentRead;
  canVoid: boolean;
}

function PaymentRow({ bookingId, payment, canVoid }: PaymentRowProps): JSX.Element {
  const isReversal = payment.reverses_payment_id !== null;
  const voidable = canVoid && !payment.is_voided && !isReversal;

  return (
    <li className="space-y-2 p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className={payment.is_voided ? 'text-gray-400 line-through' : 'text-gray-800'}>
          <p className="font-medium">
            {payment.method}
            {isReversal && (
              <span className="ml-2 font-normal text-gray-500">
                Reversal of #{payment.reverses_payment_id}
              </span>
            )}
            {payment.is_voided && (
              <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700 no-underline">
                Voided
              </span>
            )}
          </p>
          {payment.note && <p className="text-gray-600">{payment.note}</p>}
          <p className="text-xs text-gray-500">{formatDate(payment.received_at)}</p>
        </div>
        <span
          className={
            payment.amount_paise < 0
              ? 'font-medium text-red-600'
              : 'font-medium text-gray-900'
          }
        >
          {formatRupees(payment.amount_paise)}
        </span>
      </div>

      {voidable && <VoidControl bookingId={bookingId} paymentId={payment.id} />}
    </li>
  );
}

function VoidControl({
  bookingId,
  paymentId,
}: {
  bookingId: number;
  paymentId: number;
}): JSX.Element {
  const voidPayment = useVoidPayment(bookingId);
  const [open, setOpen] = useState<boolean>(false);
  const [reason, setReason] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs font-medium text-red-600 underline"
      >
        Void
      </button>
    );
  }

  const onConfirm = async (): Promise<void> => {
    setError(null);
    const parsed = paymentVoidSchema.safeParse({ reason });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'A reason is required.');
      return;
    }
    try {
      await voidPayment.mutateAsync({ paymentId, reason: parsed.data.reason });
      setOpen(false);
      setReason('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to void payment.');
    }
  };

  return (
    <div className="space-y-2 rounded border border-red-200 bg-red-50 p-2">
      <label className="block text-xs font-medium text-gray-700">
        Reason for voiding
        <input
          type="text"
          aria-label="Reason for voiding"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            setReason('');
            setError(null);
          }}
          className="rounded px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={voidPayment.isPending}
          className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-60"
        >
          {voidPayment.isPending ? 'Voiding…' : 'Confirm void'}
        </button>
      </div>
    </div>
  );
}
