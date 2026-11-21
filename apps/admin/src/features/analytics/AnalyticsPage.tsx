/**
 * Admin-only analytics. Three tabs:
 *  - Slot amount: bookings by CELEBRATION date, with all their payments.
 *  - Bookings created: bookings by creation date (what they ordered, owe).
 *  - Today income: payments RECEIVED in the date(s), per method.
 * A shared From/To date range (default today) and a status filter (default
 * accepted) apply to every tab; Export streams the server-built `.xlsx`.
 * The route is admin-gated; this page also defensively checks the role.
 */

import { useState } from 'react';

import { todayIsoInIST } from '@/lib/dates';
import { exportUrl, triggerDownload } from '@/lib/download';
import { useAuth } from '@/features/auth/useAuth';
import { useLocation } from '@/features/location/useLocation';
import { CreatedBookingsTable } from './CreatedBookingsTable';
import { SlotAmountTable } from './SlotAmountTable';
import { TodayIncomeTable } from './TodayIncomeTable';
import { buildAnalyticsQuery, useCreatedBookings, useSlotAmounts, useTodayIncome } from './queries';
import type { AnalyticsFilters, BookingStatusName } from './types';

type Tab = 'slot' | 'created' | 'income';

const TABS: Array<{ value: Tab; label: string; exportPath: string }> = [
  { value: 'slot', label: 'Slot amount', exportPath: '/api/v1/admin/analytics/slot-amounts/export' },
  {
    value: 'created',
    label: 'Bookings created',
    exportPath: '/api/v1/admin/analytics/created-bookings/export',
  },
  {
    value: 'income',
    label: 'Today income',
    exportPath: '/api/v1/admin/analytics/today-income/export',
  },
];

const STATUSES: Array<{ value: BookingStatusName; label: string }> = [
  { value: 'accepted', label: 'Accepted' },
  { value: 'pending', label: 'Pending' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'expired', label: 'Expired' },
  { value: 'rejected', label: 'Rejected' },
];

function tabClass(isActive: boolean): string {
  const base = 'rounded px-3 py-1.5 text-sm font-medium';
  return isActive
    ? `${base} bg-gray-900 text-white`
    : `${base} text-gray-700 hover:bg-gray-100`;
}

function chipClass(isOn: boolean): string {
  const base = 'rounded-full border px-3 py-1 text-xs font-medium';
  return isOn
    ? `${base} border-gray-900 bg-gray-900 text-white`
    : `${base} border-gray-300 text-gray-700 hover:bg-gray-100`;
}

export function AnalyticsPage(): JSX.Element {
  const { user } = useAuth();
  const { selectedLocationId } = useLocation();
  const [tab, setTab] = useState<Tab>('slot');
  const [dateFrom, setDateFrom] = useState<string>(todayIsoInIST());
  const [dateTo, setDateTo] = useState<string>(todayIsoInIST());
  // Booking reports default to accepted. Income defaults to every status
  // (money received counts even if the booking was later cancelled).
  const [bookingStatuses, setBookingStatuses] = useState<BookingStatusName[]>(['accepted']);
  const [incomeStatuses, setIncomeStatuses] = useState<BookingStatusName[]>([]);

  const bookingFilters: AnalyticsFilters = { dateFrom, dateTo, statuses: bookingStatuses };
  const incomeFilters: AnalyticsFilters = { dateFrom, dateTo, statuses: incomeStatuses };

  const slot = useSlotAmounts(selectedLocationId, bookingFilters, tab === 'slot');
  const created = useCreatedBookings(selectedLocationId, bookingFilters, tab === 'created');
  const income = useTodayIncome(selectedLocationId, incomeFilters, tab === 'income');

  // Defensive: the route is admin-gated, but never render financials to a
  // non-admin even if the component is somehow mounted.
  if (user?.role !== 'admin') {
    return <p className="text-sm text-red-600">Analytics is available to admins only.</p>;
  }

  const isIncome = tab === 'income';
  const statuses = isIncome ? incomeStatuses : bookingStatuses;
  const setStatuses = isIncome ? setIncomeStatuses : setBookingStatuses;
  const active = tab === 'slot' ? slot : tab === 'created' ? created : income;
  const activeTab = TABS.find((t) => t.value === tab) as (typeof TABS)[number];
  const rangeInvalid = dateFrom !== '' && dateTo !== '' && dateTo < dateFrom;

  const toggleStatus = (value: BookingStatusName): void => {
    setStatuses((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value],
    );
  };

  const onExport = (): void => {
    if (selectedLocationId === null || rangeInvalid) {
      return;
    }
    const params = buildAnalyticsQuery(
      selectedLocationId,
      isIncome ? incomeFilters : bookingFilters,
    ).toString();
    triggerDownload(exportUrl(activeTab.exportPath, {}) + `?${params}`);
  };

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Analytics</h1>
        <button
          type="button"
          onClick={onExport}
          disabled={selectedLocationId === null || rangeInvalid}
          className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          Export
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            className={tabClass(tab === t.value)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mr-2 text-gray-600">From</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">To</span>
          <input
            type="date"
            value={dateTo}
            min={dateFrom}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
      </div>
      {rangeInvalid && (
        <p className="text-sm text-red-600">&lsquo;To&rsquo; date cannot be before &lsquo;From&rsquo; date.</p>
      )}

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Booking status">
        <span className="text-sm text-gray-600">Status</span>
        {STATUSES.map((s) => (
          <button
            key={s.value}
            type="button"
            aria-pressed={statuses.includes(s.value)}
            onClick={() => toggleStatus(s.value)}
            className={chipClass(statuses.includes(s.value))}
          >
            {s.label}
          </button>
        ))}
        {isIncome && statuses.length === 0 && (
          <span className="text-xs text-gray-500">All statuses</span>
        )}
      </div>

      {active.isLoading && <p className="text-sm text-gray-500">Loading analytics…</p>}
      {active.isError && <p className="text-sm text-red-600">Failed to load analytics.</p>}
      {!isIncome && statuses.length === 0 && (
        <p className="text-sm text-amber-700">Select at least one status to see bookings.</p>
      )}

      {tab === 'slot' && slot.data && <SlotAmountTable result={slot.data} />}
      {tab === 'created' && created.data && <CreatedBookingsTable result={created.data} />}
      {tab === 'income' && income.data && <TodayIncomeTable result={income.data} />}
    </section>
  );
}
