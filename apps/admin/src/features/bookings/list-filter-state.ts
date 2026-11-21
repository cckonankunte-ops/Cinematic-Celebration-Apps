/**
 * Remembers the bookings-list filters for the browser tab (sessionStorage), so
 * coming back from the edit form restores the date, status, search and page the
 * admin was looking at instead of resetting to today. Closing the tab clears it.
 */

import type { BookingSearchField } from './booking-queries';
import type { BookingStatus } from './types';

export interface ListFilterState {
  q: string;
  searchIn: BookingSearchField;
  status: '' | BookingStatus;
  dateFrom: string;
  dateTo: string;
  limit: number;
  offset: number;
}

const KEY = 'cc.admin.bookingListFilters';

/** Stored filters merged over the defaults; any bad/missing value falls back. */
export function loadListFilters(defaults: ListFilterState): ListFilterState {
  if (typeof window === 'undefined') {
    return defaults;
  }
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (raw === null) {
      return defaults;
    }
    const parsed = JSON.parse(raw) as Partial<ListFilterState>;
    return {
      q: typeof parsed.q === 'string' ? parsed.q : defaults.q,
      searchIn: parsed.searchIn ?? defaults.searchIn,
      status: parsed.status ?? defaults.status,
      dateFrom: typeof parsed.dateFrom === 'string' ? parsed.dateFrom : defaults.dateFrom,
      dateTo: typeof parsed.dateTo === 'string' ? parsed.dateTo : defaults.dateTo,
      limit: typeof parsed.limit === 'number' ? parsed.limit : defaults.limit,
      offset: typeof parsed.offset === 'number' ? parsed.offset : defaults.offset,
    };
  } catch {
    return defaults;
  }
}

export function saveListFilters(state: ListFilterState): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Storage full or blocked: the filters just won't be remembered.
  }
}
