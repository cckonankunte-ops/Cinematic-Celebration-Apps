/**
 * Lead dashboard (admin only, lead-crm R13): where leads come from and how many
 * book. Branch (or all branches) and an IST created-date range (default last
 * 30 days). All figures are server-side aggregates; this page only formats
 * them. Built for a 360 px phone first: stacked cards, no wide tables needed.
 */

import { useMemo, useState } from 'react';

import { formatDate } from '@/lib/dates';
import { useLocation } from '@/features/location/useLocation';
import { useLeadDashboard } from './lead-queries';
import {
  colourFor,
  conversionPercent,
  defaultRange,
  formatMinutes,
  keyLabel,
  pivotByDay,
  reasonLabel,
  type Grouping,
} from './lead-dashboard';
import type { DashboardGroupRow } from './types';

const card = 'rounded border border-gray-200 bg-white p-4';
const field = 'rounded border border-gray-300 px-2 py-1 text-sm';

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }): JSX.Element {
  return (
    <div className={card}>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-gray-900">{value}</p>
      {hint && <p className="text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

function percentText(won: number, total: number): string {
  const pct = conversionPercent(won, total);
  return pct === null ? '—' : `${pct}%`;
}

function GroupTable({
  title,
  rows,
  label,
}: {
  title: string;
  rows: DashboardGroupRow[];
  label: (key: string) => string;
}): JSX.Element {
  return (
    <section className={card} aria-label={title}>
      <h2 className="mb-2 text-base font-semibold text-gray-900">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-500">No leads in this range.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs text-gray-500">
              <th className="py-1.5 pr-2 font-medium">{title.split(' ')[0]}</th>
              <th className="py-1.5 pr-2 text-right font-medium">Leads</th>
              <th className="py-1.5 pr-2 text-right font-medium">Won</th>
              <th className="py-1.5 text-right font-medium">Conv.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-gray-100 last:border-0">
                <td className="py-1.5 pr-2">{label(r.key)}</td>
                <td className="py-1.5 pr-2 text-right tabular-nums">{r.total}</td>
                <td className="py-1.5 pr-2 text-right tabular-nums">{r.won}</td>
                <td className="py-1.5 text-right tabular-nums">{percentText(r.won, r.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export function LeadDashboardPage(): JSX.Element {
  const { locations, selectedLocationId } = useLocation();
  const initial = useMemo(() => defaultRange(), []);
  // '' = all branches (admins only reach this page).
  const [branch, setBranch] = useState<string>(
    selectedLocationId !== null ? String(selectedLocationId) : '',
  );
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [grouping, setGrouping] = useState<Grouping>('source');

  const locationId = branch ? Number(branch) : null;
  const dashboard = useLeadDashboard(locationId, from, to);
  const d = dashboard.data;
  const badRange = from !== '' && to !== '' && from > to;

  const days = d ? pivotByDay(grouping === 'source' ? d.per_day_by_source : d.per_day_by_channel) : [];
  const allKeys = [...new Set(days.flatMap((day) => day.parts.map((p) => p.key)))];
  const maxDay = Math.max(1, ...days.map((day) => day.total));

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Lead dashboard</h1>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="mr-2 text-gray-600">Branch</span>
          <select className={field} value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="">All branches</option>
            {locations.map((l) => (
              <option key={l.id} value={String(l.id)}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">From</span>
          <input type="date" className={field} value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="text-sm">
          <span className="mr-2 text-gray-600">To</span>
          <input type="date" className={field} value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <button
          type="button"
          onClick={() => {
            const r = defaultRange();
            setFrom(r.from);
            setTo(r.to);
          }}
          className="rounded px-2 py-1 text-sm text-gray-600 hover:bg-gray-100"
        >
          Last 30 days
        </button>
      </div>

      {badRange && <p className="text-sm text-red-600">"From" must be on or before "To".</p>}
      {dashboard.isLoading && <p className="text-sm text-gray-500">Loading dashboard…</p>}
      {dashboard.isError && <p className="text-sm text-red-600">Failed to load the dashboard.</p>}

      {d && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Leads" value={String(d.total)} />
            <Stat
              label="Won"
              value={String(d.won)}
              hint={`${percentText(d.won, d.total)} conversion`}
            />
            <Stat
              label="First response (median)"
              value={formatMinutes(d.median_first_response_minutes)}
              hint={`Average ${formatMinutes(d.avg_first_response_minutes)} · ${d.contacted} contacted`}
            />
            <Stat
              label="WhatsApp leads with a code"
              value={`${d.whatsapp_with_code} of ${d.whatsapp_total}`}
              hint={
                d.whatsapp_total > 0
                  ? `${percentText(d.whatsapp_with_code, d.whatsapp_total)} came from the website`
                  : undefined
              }
            />
          </div>

          <section className={card} aria-label="Leads per day">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-gray-900">Leads per day</h2>
              <div role="radiogroup" aria-label="Group by" className="flex gap-1">
                {(['source', 'channel'] as const).map((g) => (
                  <button
                    key={g}
                    type="button"
                    role="radio"
                    aria-checked={grouping === g}
                    onClick={() => setGrouping(g)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      grouping === g
                        ? 'border-gray-900 bg-gray-900 text-white'
                        : 'border-gray-300 text-gray-700'
                    }`}
                  >
                    By {g}
                  </button>
                ))}
              </div>
            </div>
            {days.length === 0 ? (
              <p className="text-sm text-gray-500">No leads in this range.</p>
            ) : (
              <>
                <ul className="mb-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-600" aria-label="Legend">
                  {allKeys.sort().map((key) => (
                    <li key={key} className="flex items-center gap-1">
                      <span className={`inline-block h-2.5 w-2.5 rounded-sm ${colourFor(allKeys, key)}`} />
                      {keyLabel(grouping, key)}
                    </li>
                  ))}
                </ul>
                <ul className="space-y-1.5">
                  {days.map((day) => (
                    <li key={day.day} className="flex items-center gap-2 text-xs">
                      <span className="w-20 shrink-0 text-gray-600">{formatDate(day.day)}</span>
                      <div
                        className="flex h-3 flex-1 overflow-hidden rounded bg-gray-100"
                        role="img"
                        aria-label={`${formatDate(day.day)}: ${day.parts
                          .map((p) => `${keyLabel(grouping, p.key)} ${p.count}`)
                          .join(', ')}`}
                      >
                        <div className="flex h-full" style={{ width: `${(day.total / maxDay) * 100}%` }}>
                          {day.parts.map((p) => (
                            <span
                              key={p.key}
                              className={`h-full ${colourFor(allKeys, p.key)}`}
                              style={{ width: `${(p.count / day.total) * 100}%` }}
                            />
                          ))}
                        </div>
                      </div>
                      <span className="w-6 shrink-0 text-right tabular-nums text-gray-800">
                        {day.total}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            <GroupTable
              title="Source totals"
              rows={d.by_source}
              label={(k) => keyLabel('source', k)}
            />
            <GroupTable
              title="Channel totals"
              rows={d.by_channel}
              label={(k) => keyLabel('channel', k)}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <section className={card} aria-label="Close reasons">
              <h2 className="mb-2 text-base font-semibold text-gray-900">Why leads were lost</h2>
              {d.close_reasons.length === 0 ? (
                <p className="text-sm text-gray-500">No lost or not-interested leads.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {d.close_reasons.map((r) => (
                    <li key={r.reason} className="flex justify-between gap-2">
                      <span>{reasonLabel(r.reason)}</span>
                      <span className="tabular-nums text-gray-800">{r.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <GroupTable title="Campaign totals" rows={d.campaigns} label={(k) => k} />
          </div>
        </>
      )}
    </div>
  );
}
