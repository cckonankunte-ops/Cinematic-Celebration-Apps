/**
 * Bookings list with location (from `useLocation`), date, and status filters.
 * Mobile-first: a stack of `BookingCard`s on small screens, a table on `md+`.
 * The table rows embed the same card for actions to avoid duplicate action UI.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { formatDate, todayIsoInIST } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import type { BookingLike } from '@/lib/whatsapp';
import { useLocation } from '@/features/location/useLocation';
import { BookingActions } from './BookingActions';
import { BookingCard } from './BookingCard';
import { PaymentDialog } from './PaymentDialog';
import { StatusBadge } from './StatusBadge';
import { useDebounce } from '@/hooks/useDebounce';
import { useBookings, type BookingFilters, type BookingSearchField } from './booking-queries';
import type { BookingListItem, BookingStatus } from './types';

/** Full action set for a desktop table row: payment + accept/reject + WhatsApp. */
function BookingRowActions({ booking }: { booking: BookingListItem }): JSX.Element {
  const [payOpen, setPayOpen] = useState(false);
  const paid = booking.amount_paid_paise ?? 0;
  const advance = booking.advance_paise ?? 0;
  const canEdit = booking.status === 'pending' || booking.status === 'accepted';
  const whatsapp: BookingLike = {
    booking_name: booking.booking_name,
    booking_reference: booking.booking_reference,
    plan_title: booking.plan_title,
    combos: booking.combos,
    occasion_name: booking.occasion_name,
    booking_date: booking.booking_date,
    special_person_name: booking.special_person_name,
    cakes: booking.cakes,
    name_on_cake: booking.name_on_cake,
    cake_weight_half_kg: booking.cake_weight_half_kg,
    slot_description: booking.slot_description,
    phone: booking.phone,
    map_url: booking.map_url,
  };
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => setPayOpen(true)}
          className="font-medium text-gray-700 underline hover:text-gray-900"
        >
          Record payment
        </button>
        {canEdit && (
          <Link
            to={`/bookings/${booking.id}/edit`}
            className="font-medium text-gray-700 underline hover:text-gray-900"
          >
            Edit
          </Link>
        )}
      </div>
      <BookingActions
        bookingId={booking.id}
        status={booking.status}
        advancePaise={advance}
        amountPaidPaise={paid}
        whatsapp={whatsapp}
      />
      <PaymentDialog
        bookingId={booking.id}
        open={payOpen}
        onClose={() => setPayOpen(false)}
      />
    </div>
  );
}

const STATUS_OPTIONS: Array<{ value: '' | BookingStatus; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'expired', label: 'Expired' },
];

const SEARCH_FIELDS: Array<{ value: BookingSearchField; label: string }> = [
  { value: 'any', label: 'Any' },
  { value: 'customer_name', label: 'Customer name' },
  { value: 'phone', label: 'Phone' },
  { value: 'booking_ref', label: 'Booking ref' },
  { value: 'occasion_person', label: 'Occasion / person' },
  { value: 'name_on_cake', label: 'Name on cake' },
];

const PAGE_SIZES = [50, 100, 200];

export function BookingListPage(): JSX.Element {
  const { selectedLocationId } = useLocation();
  // Default view: today's bookings (From = today, others empty).
  const today = todayIsoInIST();
  const [q, setQ] = useState('');
  const [searchIn, setSearchIn] = useState<BookingSearchField>('any');
  const [status, setStatus] = useState<'' | BookingStatus>('');
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState('');
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  // Reset all filters back to the default (today's bookings).
  const resetFilters = (): void => {
    setQ('');
    setSearchIn('any');
    setStatus('');
    setDateFrom(today);
    setDateTo('');
    setLimit(50);
    setOffset(0);
  };

  // Debounce the text query (min-3-char gate lives in the query builder).
  const debouncedQ = useDebounce(q, 350);

  const filters: BookingFilters = {
    q: debouncedQ,
    searchIn,
    status: status === '' ? null : status,
    dateFrom: dateFrom || null,
    dateTo: dateTo || null,
    limit,
    offset,
  };

  const { data, isLoading, isError } = useBookings(selectedLocationId, filters);

  // Any filter change resets to the first page.
  const resetOffset = (): void => setOffset(0);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = Math.min(offset + limit, total);

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

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mr-2 text-gray-600">Search</span>
          <input
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              resetOffset();
            }}
            placeholder="min 3 characters"
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">In</span>
          <select
            value={searchIn}
            onChange={(e) => {
              setSearchIn(e.target.value as BookingSearchField);
              resetOffset();
            }}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {SEARCH_FIELDS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">From</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              resetOffset();
            }}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">To</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              resetOffset();
            }}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">Status</span>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as '' | BookingStatus);
              resetOffset();
            }}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">Per page</span>
          <select
            value={limit}
            onChange={(e) => {
              setLimit(Number(e.target.value));
              resetOffset();
            }}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={resetFilters}
          title="Reset filters to today"
          aria-label="Reset filters"
          className="flex items-center gap-1 rounded border border-gray-300 px-2 py-1 text-sm text-gray-600 hover:bg-gray-50"
        >
          <span aria-hidden="true">↺</span>
          <span>Reset</span>
        </button>
      </div>

      {isLoading && <p className="text-sm text-gray-500">Loading bookings…</p>}
      {isError && <p className="text-sm text-red-600">Failed to load bookings.</p>}
      {data && items.length === 0 && (
        <p className="text-sm text-gray-500">No bookings for these filters.</p>
      )}

      {data && items.length > 0 && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
            <span>
              Showing {showingFrom}–{showingTo} of {total}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="rounded border border-gray-300 px-2 py-1 disabled:opacity-40"
              >
                Prev
              </button>
              <button
                type="button"
                disabled={offset + limit >= total}
                onClick={() => setOffset(offset + limit)}
                className="rounded border border-gray-300 px-2 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
          {/* Mobile: card stack */}
          <div className="space-y-3 md:hidden">
            {items.map((b) => (
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
                {items.map((b) => (
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
                      <BookingRowActions booking={b} />
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
