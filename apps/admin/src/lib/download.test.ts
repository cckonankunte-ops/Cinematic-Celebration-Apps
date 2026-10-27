import { describe, expect, it } from 'vitest';

import { exportUrl } from './download';

// Mirror the module's own base-URL resolution instead of hardcoding localhost:
// a wired Codespace sets VITE_API_BASE_URL in apps/admin/.env, which vitest
// loads, so a hardcoded base would make these exact-match assertions brittle.
const BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/+$/,
  '',
);

describe('exportUrl', () => {
  it('builds an absolute URL with encoded query params', () => {
    const url = exportUrl('/api/v1/admin/timesheet/export', {
      location_id: 2,
      date: '2025-12-25',
    });

    expect(url).toBe(
      `${BASE}/api/v1/admin/timesheet/export?location_id=2&date=2025-12-25`,
    );
  });

  it('normalizes a path without a leading slash', () => {
    const url = exportUrl('api/v1/admin/cakesheet/export', { location_id: 1, date: '2025-01-01' });

    expect(url).toBe(`${BASE}/api/v1/admin/cakesheet/export?location_id=1&date=2025-01-01`);
  });

  it('omits the query string when there are no params', () => {
    const url = exportUrl('/api/v1/admin/timesheet/export', {});

    expect(url).toBe(`${BASE}/api/v1/admin/timesheet/export`);
  });

  it('stringifies numeric params', () => {
    const url = exportUrl('/x', { location_id: 42 });

    expect(url).toContain('location_id=42');
  });
});
