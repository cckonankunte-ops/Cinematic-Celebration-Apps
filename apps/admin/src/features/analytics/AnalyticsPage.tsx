/**
 * Admin-only analytics. Two tabs — "Slot amount" and "Advance amount" — each
 * showing a daily report table with a Day Summary footer and an Export button
 * that streams the server-generated `.xlsx`. The route is already gated to
 * admins; this page also defensively checks the role and renders nothing
 * sensitive otherwise.
 */

import { useState } from 'react';

import { todayIsoInIST } from '@/lib/dates';
import { exportUrl, triggerDownload } from '@/lib/download';
import { useAuth } from '@/features/auth/useAuth';
import { useLocation } from '@/features/location/useLocation';
import { SlotAmountTable } from './SlotAmountTable';
import { AdvanceAmountTable } from './AdvanceAmountTable';
import { useAdvanceAmounts, useSlotAmounts } from './queries';

type Tab = 'slot' | 'advance';

const TABS: Array<{ value: Tab; label: string; exportPath: string }> = [
  {
    value: 'slot',
    label: 'Slot amount',
    exportPath: '/api/v1/admin/analytics/slot-amounts/export',
  },
  {
    value: 'advance',
    label: 'Advance amount',
    exportPath: '/api/v1/admin/analytics/advance-amounts/export',
  },
];

function tabClass(isActive: boolean): string {
  const base = 'rounded px-3 py-1.5 text-sm font-medium';
  return isActive
    ? `${base} bg-gray-900 text-white`
    : `${base} text-gray-700 hover:bg-gray-100`;
}

export function AnalyticsPage(): JSX.Element {
  const { user } = useAuth();
  const { selectedLocationId } = useLocation();
  const [tab, setTab] = useState<Tab>('slot');
  const [date, setDate] = useState<string>(todayIsoInIST());

  const slot = useSlotAmounts(selectedLocationId, date);
  const advance = useAdvanceAmounts(selectedLocationId, date);

  // Defensive: the route is admin-gated, but never render financials to a
  // non-admin even if the component is somehow mounted.
  if (user?.role !== 'admin') {
    return <p className="text-sm text-red-600">Analytics is available to admins only.</p>;
  }

  const active = tab === 'slot' ? slot : advance;
  const activeTab = TABS.find((t) => t.value === tab) as (typeof TABS)[number];

  const onExport = (): void => {
    if (selectedLocationId === null) {
      return;
    }
    triggerDownload(
      exportUrl(activeTab.exportPath, { location_id: selectedLocationId, date }),
    );
  };

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Analytics</h1>
        <button
          type="button"
          onClick={onExport}
          disabled={selectedLocationId === null}
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
        <label className="ml-auto text-sm">
          <span className="mr-2 text-gray-600">Date</span>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
        </label>
      </div>

      {active.isLoading && <p className="text-sm text-gray-500">Loading analytics…</p>}
      {active.isError && <p className="text-sm text-red-600">Failed to load analytics.</p>}

      {tab === 'slot' && slot.data && <SlotAmountTable result={slot.data} />}
      {tab === 'advance' && advance.data && <AdvanceAmountTable result={advance.data} />}
    </section>
  );
}
