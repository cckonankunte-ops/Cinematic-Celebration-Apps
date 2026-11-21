import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppLayout } from '@/features/auth/AppLayout';
import { LeadDashboardPage } from './LeadDashboardPage';
import {
  conversionPercent,
  defaultRange,
  formatMinutes,
  pivotByDay,
} from './lead-dashboard';
import type { LeadDashboard } from './types';

let dashboard: LeadDashboard | undefined;
let role: 'admin' | 'staff' = 'admin';

vi.mock('./lead-queries', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lead-queries')>();
  return {
    ...actual,
    useLeadDashboard: () => ({ data: dashboard, isLoading: false, isError: false }),
    useLeadCounts: () => ({ data: undefined }),
  };
});

vi.mock('@/features/location/useLocation', () => ({
  useLocation: () => ({
    locations: [{ id: 1, name: 'Hulimavu', slug: 'hulimavu' }],
    selectedLocationId: 1,
    canSwitch: role === 'admin',
    selectLocation: vi.fn(),
  }),
}));

vi.mock('@/features/auth/useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'u', role, location_id: role === 'admin' ? null : 1 },
    isLoading: false,
    logout: vi.fn(),
  }),
}));

const DATA: LeadDashboard = {
  location_id: 1,
  date_from: '2026-11-04',
  date_to: '2026-11-10',
  total: 4,
  won: 1,
  per_day_by_source: [
    { day: '2026-11-10', key: 'website', count: 2 },
    { day: '2026-11-10', key: 'whatsapp', count: 1 },
    { day: '2026-11-09', key: 'whatsapp_ad', count: 1 },
  ],
  per_day_by_channel: [
    { day: '2026-11-10', key: 'meta_ads', count: 3 },
    { day: '2026-11-09', key: 'manual', count: 1 },
  ],
  by_source: [
    { key: 'website', total: 2, won: 1 },
    { key: 'whatsapp', total: 1, won: 0 },
    { key: 'whatsapp_ad', total: 1, won: 0 },
  ],
  by_channel: [
    { key: 'meta_ads', total: 3, won: 1 },
    { key: 'manual', total: 1, won: 0 },
  ],
  contacted: 3,
  avg_first_response_minutes: 20,
  median_first_response_minutes: 75,
  close_reasons: [{ reason: 'price_budget', count: 1 }],
  campaigns: [{ key: 'diwali', total: 2, won: 1 }],
  whatsapp_total: 2,
  whatsapp_with_code: 1,
};

beforeEach(() => {
  dashboard = DATA;
  role = 'admin';
});

describe('LeadDashboardPage', () => {
  it('shows the figures from the API', () => {
    render(<LeadDashboardPage />);
    expect(screen.getByText('25% conversion')).toBeInTheDocument();
    expect(screen.getByText('1 h 15 min')).toBeInTheDocument();
    expect(screen.getByText('1 of 2')).toBeInTheDocument();

    const sources = screen.getByRole('region', { name: 'Source totals' });
    expect(within(sources).getByText('Website booking')).toBeInTheDocument();
    expect(within(sources).getByText('50%')).toBeInTheDocument();

    expect(within(screen.getByRole('region', { name: 'Campaign totals' })).getByText('diwali'))
      .toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Close reasons' })).getByText('Price / budget'))
      .toBeInTheDocument();
  });

  it('switches leads per day between source and channel', () => {
    render(<LeadDashboardPage />);
    const perDay = screen.getByRole('region', { name: 'Leads per day' });
    const legend = () => within(perDay).getByRole('list', { name: 'Legend' });
    expect(within(legend()).getByText('WhatsApp')).toBeInTheDocument();

    fireEvent.click(within(perDay).getByRole('radio', { name: 'By channel' }));
    expect(within(legend()).getByText('Meta ads')).toBeInTheDocument();
    expect(within(legend()).queryByText('WhatsApp')).toBeNull();
  });

  it('shows empty states', () => {
    dashboard = {
      ...DATA,
      total: 0,
      won: 0,
      per_day_by_source: [],
      per_day_by_channel: [],
      by_source: [],
      by_channel: [],
      campaigns: [],
      close_reasons: [],
      whatsapp_total: 0,
      whatsapp_with_code: 0,
    };
    render(<LeadDashboardPage />);
    expect(screen.getAllByText('No leads in this range.').length).toBeGreaterThan(0);
  });
});

describe('Lead dashboard nav', () => {
  function renderLayout(): void {
    render(
      <MemoryRouter initialEntries={['/leads']}>
        <AppLayout />
      </MemoryRouter>,
    );
  }

  it('is shown to admins', () => {
    renderLayout();
    expect(screen.getByRole('link', { name: 'Lead dashboard' })).toHaveAttribute(
      'href',
      '/leads/dashboard',
    );
  });

  it('is hidden from staff', () => {
    role = 'staff';
    renderLayout();
    expect(screen.queryByRole('link', { name: 'Lead dashboard' })).toBeNull();
    expect(screen.getByRole('link', { name: /^Leads/ })).toBeInTheDocument();
  });
});

describe('dashboard helpers', () => {
  it('computes conversion and formats durations', () => {
    expect(conversionPercent(1, 4)).toBe(25);
    expect(conversionPercent(0, 0)).toBeNull();
    expect(formatMinutes(null)).toBe('—');
    expect(formatMinutes(45)).toBe('45 min');
    expect(formatMinutes(120)).toBe('2 h');
    expect(formatMinutes(26 * 60)).toBe('1 d 2 h');
  });

  it('pivots rows into one bar per day, newest first', () => {
    const bars = pivotByDay(DATA.per_day_by_source);
    expect(bars.map((b) => [b.day, b.total])).toEqual([
      ['2026-11-10', 3],
      ['2026-11-09', 1],
    ]);
    expect(bars[0].parts[0]).toEqual({ key: 'website', count: 2 });
  });

  it('defaults to the last 30 days in IST', () => {
    expect(defaultRange(new Date('2026-11-10T20:00:00Z'))).toEqual({
      from: '2026-10-13',
      to: '2026-11-11',
    });
  });
});
