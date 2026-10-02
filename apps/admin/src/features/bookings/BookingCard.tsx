/**
 * One booking row. Renders as a card (used in the mobile stack and reused as a
 * table row's expandable detail on larger screens). Shows reference, name,
 * date, status, and derived money, plus the payment dialog + accept/reject/
 * WhatsApp actions. Payment-derived fields on the list item are optional, so we
 * fall back to 0 when absent.
 */

import { useState } from 'react';

import { formatDate } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import type { BookingLike } from '@/lib/whatsapp';
import { BookingActions } from './BookingActions';
import { PaymentDialog } from './PaymentDialog';
import { StatusBadge } from './StatusBadge';
import type { BookingListItem } from './types';

function toWhatsapp(booking: BookingListItem): BookingLike {
  // The list item lacks plan/slot descriptions; use what we have so the
  // message is still useful. Full detail is available on the booking page.
  return {
    booking_name: booking.booking_name,
    booking_reference: booking.booking_reference,
    plan_title: '',
    booking_date: booking.booking_date,
    slot_description: '',
  };
}

export function BookingCard({ booking }: { booking: BookingListItem }): JSX.Element {
  const [payOpen, setPayOpen] = useState(false);
  const paid = booking.amount_paid_paise ?? 0;
  const advance = booking.advance_paise ?? 0;
  const due = booking.amount_due_paise ?? booking.total_paise - paid;

  return (
    <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-medium text-gray-900">{booking.booking_name}</p>
          <p className="text-xs text-gray-500">{booking.booking_reference}</p>
        </div>
        <StatusBadge status={booking.status} />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <dt className="text-gray-500">Date</dt>
        <dd className="text-right text-gray-900">{formatDate(booking.booking_date)}</dd>
        <dt className="text-gray-500">People</dt>
        <dd className="text-right text-gray-900">{booking.people}</dd>
        <dt className="text-gray-500">Total</dt>
        <dd className="text-right text-gray-900">{formatRupees(booking.total_paise)}</dd>
        <dt className="text-gray-500">Paid</dt>
        <dd className="text-right text-gray-900">{formatRupees(paid)}</dd>
        <dt className="text-gray-500">Due</dt>
        <dd className="text-right text-gray-900">{formatRupees(due)}</dd>
      </dl>

      <button
        type="button"
        onClick={() => setPayOpen(true)}
        className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
      >
        Record payment
      </button>

      <BookingActions
        bookingId={booking.id}
        status={booking.status}
        advancePaise={advance}
        amountPaidPaise={paid}
        whatsapp={toWhatsapp(booking)}
      />

      <PaymentDialog
        bookingId={booking.id}
        open={payOpen}
        onClose={() => setPayOpen(false)}
      />
    </div>
  );
}
