/**
 * Bookings list with location (from `useLocation`), date, and status filters.
 * Mobile-first: a stack of `BookingCard`s on small screens, a table on `md+`.
 * The table rows embed the same card for actions to avoid duplicate action UI.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { formatDate, todayIsoInIST } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { buildWhatsappUrl } from '@/lib/whatsapp';
import { useLocation } from '@/features/location/useLocation';
import { BookingCard } from './BookingCard';
import { StatusBadge } from './StatusBadge';
import { useBookings } from './booking-queries';
import type { BookingStatus } from './types';

const STATUS_OPTIONS: Array<{ value: '' | BookingStatus; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'expired', label: 'Expired' },
];

export function BookingListPage(): JSX.Element {
  const { selectedLocationId } = useLocation();
  const [date, setDate] = useState<string>(todayIsoInIST());
  const [status, setStatus] = useState<'' | BookingStatus>('');

  const { data, isLoading, isError } = useBookings(
    selectedLocationId,
    date === '' ? null : date,
    status === '' ? null : status,
  );

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Bookings</h1>
        <Link
          to="/bookings/new"
          className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          New booking
        </Link>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="text-sm">
          <span className="mr-2 text-gray-600">Date</span>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as '' | BookingStatus)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading && <p className="text-sm text-gray-500">Loading bookings…</p>}
      {isError && <p className="text-sm text-red-600">Failed to load bookings.</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-gray-500">No bookings for these filters.</p>
      )}

      {data && data.length > 0 && (
        <>
          {/* Mobile: card stack */}
          <div className="space-y-3 md:hidden">
            {data.map((b) => (
              <BookingCard key={b.id} booking={b} />
            ))}
          </div>

          {/* md+: full column table matching the legacy bookings grid */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse whitespace-nowrap text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Reference</th>
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Plan</th>
                  <th className="py-2 pr-4">Date</th>
                  <th className="py-2 pr-4">Slot</th>
                  <th className="py-2 pr-4">Guests</th>
                  <th className="py-2 pr-4 text-right">Amount paid</th>
                  <th className="py-2 pr-4 text-right">Amount due</th>
                  <th className="py-2 pr-4 text-right">Discount</th>
                  <th className="py-2 pr-4 text-right">Total</th>
                  <th className="py-2 pr-4">Special decor</th>
                  <th className="py-2 pr-4">Cakes</th>
                  <th className="py-2 pr-4">Combos</th>
                  <th className="py-2 pr-4">Occasion</th>
                  <th className="py-2 pr-4">Special person</th>
                  <th className="py-2 pr-4">Created</th>
                  <th className="py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.map((b) => (
                  <tr key={b.id} className="border-b border-gray-100 align-top">
                    <td className="py-2 pr-4">
                      <StatusBadge status={b.status} />
                    </td>
                    <td className="py-2 pr-4 font-mono text-xs">{b.booking_reference}</td>
                    <td className="py-2 pr-4">{b.booking_name}</td>
                    <td className="py-2 pr-4">{b.plan_title}</td>
                    <td className="py-2 pr-4">{formatDate(b.booking_date)}</td>
                    <td className="py-2 pr-4">{b.slot_description}</td>
                    <td className="py-2 pr-4">{b.people}</td>
                    <td className="py-2 pr-4 text-right">
                      {formatRupees(b.amount_paid_paise ?? 0)}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {formatRupees(b.amount_due_paise ?? 0)}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {formatRupees(b.discount_paise)}
                    </td>
                    <td className="py-2 pr-4 text-right">{formatRupees(b.total_paise)}</td>
                    <td className="py-2 pr-4 whitespace-normal">
                      {b.special_decor.length > 0 ? b.special_decor.join(', ') : '—'}
                    </td>
                    <td className="py-2 pr-4 whitespace-normal">
                      {b.cakes.length > 0 ? b.cakes.join(', ') : '—'}
                    </td>
                    <td className="py-2 pr-4 whitespace-normal">
                      {b.combos.length > 0 ? b.combos.join(', ') : '—'}
                    </td>
                    <td className="py-2 pr-4">{b.occasion_name ?? '—'}</td>
                    <td className="py-2 pr-4">{b.special_person_name ?? '—'}</td>
                    <td className="py-2 pr-4">{formatDate(b.created_at)}</td>
                    <td className="py-2 pr-4">
                      <div className="flex items-center gap-3">
                        {(b.status === 'pending' || b.status === 'accepted') && (
                          <Link
                            to={`/bookings/${b.id}/edit`}
                            className="font-medium text-gray-700 underline hover:text-gray-900"
                          >
                            Edit
                          </Link>
                        )}
                        <a
                          href={buildWhatsappUrl(b)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-green-700 underline hover:text-green-900"
                          title="Send WhatsApp confirmation to the customer"
                        >
                          WhatsApp
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
