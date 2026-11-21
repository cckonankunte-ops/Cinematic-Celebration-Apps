/**
 * Remembers the Leads page filters for the browser tab (sessionStorage), so
 * coming back from a lead restores them (lead-crm R5.5), like the Bookings page.
 */

import type { LeadChannel, LeadSource, LeadStatus } from './types';

export interface LeadFilterState {
  q: string;
  statuses: LeadStatus[];
  sources: LeadSource[];
  channel: '' | LeadChannel;
  assignedUserId: string;
  createdFrom: string;
  createdTo: string;
  followFrom: string;
  followTo: string;
  limit: number;
  offset: number;
}

export const DEFAULT_LEAD_FILTERS: LeadFilterState = {
  q: '',
  statuses: [],
  sources: [],
  channel: '',
  assignedUserId: '',
  createdFrom: '',
  createdTo: '',
  followFrom: '',
  followTo: '',
  limit: 50,
  offset: 0,
};

const KEY = 'cc.admin.leadListFilters';

const str = (value: unknown, fallback: string): string =>
  typeof value === 'string' ? value : fallback;

const strList = <T extends string>(value: unknown, fallback: T[]): T[] =>
  Array.isArray(value) && value.every((v) => typeof v === 'string') ? (value as T[]) : fallback;

/** Stored filters merged over the defaults; any bad or missing value falls back. */
export function loadLeadFilters(defaults: LeadFilterState = DEFAULT_LEAD_FILTERS): LeadFilterState {
  if (typeof window === 'undefined') {
    return defaults;
  }
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (raw === null) {
      return defaults;
    }
    const p = JSON.parse(raw) as Partial<Record<keyof LeadFilterState, unknown>>;
    return {
      q: str(p.q, defaults.q),
      statuses: strList(p.statuses, defaults.statuses),
      sources: strList(p.sources, defaults.sources),
      channel: str(p.channel, defaults.channel) as LeadFilterState['channel'],
      assignedUserId: str(p.assignedUserId, defaults.assignedUserId),
      createdFrom: str(p.createdFrom, defaults.createdFrom),
      createdTo: str(p.createdTo, defaults.createdTo),
      followFrom: str(p.followFrom, defaults.followFrom),
      followTo: str(p.followTo, defaults.followTo),
      limit: typeof p.limit === 'number' ? p.limit : defaults.limit,
      offset: typeof p.offset === 'number' ? p.offset : defaults.offset,
    };
  } catch {
    return defaults;
  }
}

export function saveLeadFilters(state: LeadFilterState): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Storage full or blocked: the filters just won't be remembered.
  }
}
