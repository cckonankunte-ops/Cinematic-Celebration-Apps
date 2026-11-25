/**
 * Daily time sheet: accepted bookings for the selected location + date, listed
 * in start-time order (ascending). Mobile-first — each row is a detail card
 * showing "Name - time range". An Export button streams the server-generated `.xlsx` from
 * `/admin/timesheet/export`.
 */

import { useState } from 'react';

import { formatRupees } from '@/lib/money';
import { todayIsoInIST } from '@/lib/dates';
import { exportUrl, triggerDownload } from '@/lib/download';
import { useLocation } from '@/features/location/useLocation';
import { useTimesheet } from './queries';
import type { TimesheetRow } from './types';

/** Render a labelled detail only when the value is present. */
function Detail({
  label,
  value,
  bold = false,
}: {
  label: string;
  value: string | null | undefined;
  bold?: boolean;
}): JSX.Element | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  return (
    <span className="inline-flex gap-1">
      <span className="text-gray-500">{label}:</span>
      <span className={bold ? 'font-bold text-gray-900' : 'text-gray-900'}>{value}</span>
    </span>
  );
}

function RowCard({ row }: { row: TimesheetRow }): JSX.Element {
  return (
    <div className="rounded border border-gray-200 bg-white p-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium text-gray-900">
          {row.booking_name}
          {row.slot_description ? ` - ${row.slot_description}` : ''}
        </span>
        <span className="font-medium">{formatRupees(row.amount_due_paise)} due</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <Detail label="Plan" value={row.plan_title} bold />
        <Detail label="People" value={String(row.people)} />
        <Detail label="Phone" value={row.phone} />
        <Detail label="Occasion" value={row.occasion} />
        <Detail label="Cake" value={row.cake} />
        <Detail label="On cake" value={row.name_on_cake} />
        <Detail label="LED" value={row.led_name} />
        <Detail label="Decor" value={row.special_decor} />
        <Detail label="Combos" value={row.combos} />
      </div>
    </div>
  );
}

export function TimesheetPage(): JSX.Element {
  const { selectedLocationId } = useLocation();
  const [date, setDate] = useState<string>(todayIsoInIST());

  const { data, isLoading, isError } = useTimesheet(selectedLocationId, date);

  const onExport = (): void => {
    if (selectedLocationId === null) {
      return;
    }
    triggerDownload(
      exportUrl('/api/v1/admin/timesheet/export', {
        location_id: selectedLocationId,
        date,
      }),
    );
  };

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Time Sheet</h1>
        <button
          type="button"
          onClick={onExport}
          disabled={selectedLocationId === null}
          className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          Export
        </button>
      </div>

      <label className="block text-sm">
        <span className="mr-2 text-gray-600">Date</span>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        />
      </label>

      {isLoading && <p className="text-sm text-gray-500">Loading time sheet…</p>}
      {isError && <p className="text-sm text-red-600">Failed to load time sheet.</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-gray-500">No accepted bookings for this date.</p>
      )}

      {/* Flat list: the API returns bookings ordered by start time, and each
          card shows its own time range next to the name. */}
      {data && (
        <div className="space-y-2">
          {data.map((row, i) => (
            <RowCard key={`${row.slot_id}-${row.booking_name}-${i}`} row={row} />
          ))}
        </div>
      )}
    </section>
  );
}
