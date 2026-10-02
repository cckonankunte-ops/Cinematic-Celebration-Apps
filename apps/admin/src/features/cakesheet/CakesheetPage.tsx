/**
 * Daily cake sheet: cake orders for the selected location + date, grouped under
 * per-slot headers (ordered by slot sort order). Mobile-first list. An Export
 * button streams the server-generated `.xlsx` from `/admin/cakesheet/export`.
 */

import { useState } from 'react';

import { todayIsoInIST } from '@/lib/dates';
import { exportUrl, triggerDownload } from '@/lib/download';
import { groupBySlot } from '@/lib/group-by-slot';
import { useLocation } from '@/features/location/useLocation';
import { useCakesheet } from './queries';

export function CakesheetPage(): JSX.Element {
  const { selectedLocationId } = useLocation();
  const [date, setDate] = useState<string>(todayIsoInIST());

  const { data, isLoading, isError } = useCakesheet(selectedLocationId, date);
  const groups = data ? groupBySlot(data) : [];

  const onExport = (): void => {
    if (selectedLocationId === null) {
      return;
    }
    triggerDownload(
      exportUrl('/api/v1/admin/cakesheet/export', {
        location_id: selectedLocationId,
        date,
      }),
    );
  };

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Cake Sheet</h1>
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

      {isLoading && <p className="text-sm text-gray-500">Loading cake sheet…</p>}
      {isError && <p className="text-sm text-red-600">Failed to load cake sheet.</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-gray-500">No cake orders for this date.</p>
      )}

      {groups.map((group) => (
        <div key={group.slotId} className="space-y-2">
          <h2 className="text-sm font-semibold text-gray-700">{group.slotDescription}</h2>
          <ul className="space-y-2">
            {group.rows.map((row, i) => (
              <li
                key={`${row.slot_id}-${i}`}
                className="rounded border border-gray-200 bg-white p-3 text-sm"
              >
                <span className="font-medium text-gray-900">{row.cake}</span>
                {row.name_on_cake !== null && row.name_on_cake !== '' && (
                  <span className="ml-2 text-xs text-gray-500">
                    on cake: <span className="text-gray-900">{row.name_on_cake}</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
