/** Pure helpers for the lead dashboard (lead-crm R13). */

import { istDateOf } from '@/lib/dates';
import {
  CHANNEL_LABELS,
  CLOSE_REASON_LABELS,
  SOURCE_LABELS,
  type CloseReason,
  type DashboardDayRow,
  type LeadChannel,
  type LeadSource,
} from './types';

export type Grouping = 'source' | 'channel';

export const DEFAULT_RANGE_DAYS = 30;

/** Default range: the last 30 days in IST, ending today (R13.1). */
export function defaultRange(now: Date = new Date()): { from: string; to: string } {
  const from = new Date(now.getTime() - (DEFAULT_RANGE_DAYS - 1) * 24 * 60 * 60 * 1000);
  return { from: istDateOf(from), to: istDateOf(now) };
}

/** Whole-number conversion percentage, or null when there are no leads. */
export function conversionPercent(won: number, total: number): number | null {
  return total > 0 ? Math.round((won / total) * 100) : null;
}

/** "12 min", "1 h 5 min", "2 d 3 h"; "—" when unknown. */
export function formatMinutes(minutes: number | null): string {
  if (minutes === null) return '—';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const rest = minutes % 60;
    return rest ? `${hours} h ${rest} min` : `${hours} h`;
  }
  const days = Math.floor(hours / 24);
  const restHours = hours % 24;
  return restHours ? `${days} d ${restHours} h` : `${days} d`;
}

export function keyLabel(grouping: Grouping, key: string): string {
  return grouping === 'source'
    ? (SOURCE_LABELS[key as LeadSource] ?? key)
    : (CHANNEL_LABELS[key as LeadChannel] ?? key);
}

export function reasonLabel(reason: string): string {
  return CLOSE_REASON_LABELS[reason as CloseReason] ?? reason;
}

export interface DayBar {
  day: string;
  total: number;
  parts: Array<{ key: string; count: number }>;
}

/** Rows (day, key, count) to one bar per day, newest day first, parts largest first. */
export function pivotByDay(rows: DashboardDayRow[]): DayBar[] {
  const byDay = new Map<string, Map<string, number>>();
  for (const row of rows) {
    const parts = byDay.get(row.day) ?? new Map<string, number>();
    parts.set(row.key, (parts.get(row.key) ?? 0) + row.count);
    byDay.set(row.day, parts);
  }
  return [...byDay.entries()]
    .sort(([a], [b]) => (a < b ? 1 : -1))
    .map(([day, parts]) => {
      const list = [...parts.entries()]
        .map(([key, count]) => ({ key, count }))
        .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
      return { day, total: list.reduce((sum, p) => sum + p.count, 0), parts: list };
    });
}

/** Stable colour per key, so a source/channel keeps its colour across days. */
const PALETTE = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-fuchsia-500',
  'bg-sky-500',
  'bg-rose-500',
  'bg-lime-500',
  'bg-violet-500',
  'bg-gray-400',
];

export function colourFor(keys: string[], key: string): string {
  const index = [...keys].sort().indexOf(key);
  return PALETTE[(index >= 0 ? index : 0) % PALETTE.length];
}
