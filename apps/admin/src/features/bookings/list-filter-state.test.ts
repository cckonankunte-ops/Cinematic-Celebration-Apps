import { beforeEach, describe, expect, it } from 'vitest';

import { loadListFilters, saveListFilters, type ListFilterState } from './list-filter-state';

const DEFAULTS: ListFilterState = {
  q: '',
  searchIn: 'any',
  status: '',
  dateFrom: '2026-11-21',
  dateTo: '',
  limit: 50,
  offset: 0,
};

describe('list filter state', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it('returns the defaults when nothing is stored', () => {
    expect(loadListFilters(DEFAULTS)).toEqual(DEFAULTS);
  });

  it('restores what was saved (e.g. after returning from the edit form)', () => {
    const saved: ListFilterState = {
      ...DEFAULTS,
      dateFrom: '2026-11-01',
      dateTo: '2026-11-01',
      status: 'accepted',
      offset: 50,
    };
    saveListFilters(saved);
    expect(loadListFilters(DEFAULTS)).toEqual(saved);
  });

  it('falls back to the defaults on corrupt storage', () => {
    window.sessionStorage.setItem('cc.admin.bookingListFilters', '{not json');
    expect(loadListFilters(DEFAULTS)).toEqual(DEFAULTS);
  });
});
