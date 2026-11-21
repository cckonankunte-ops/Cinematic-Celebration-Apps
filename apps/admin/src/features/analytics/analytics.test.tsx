import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { buildAnalyticsQuery } from './queries';
import { methodLabel, orderedMethods } from './methods';
import { TodayIncomeTable } from './TodayIncomeTable';
import type { TodayIncomeResult } from './types';

describe('orderedMethods', () => {
  it('puts known methods first in a fixed order, then new ones alphabetically', () => {
    expect(
      orderedMethods({ upi: 1, wallet: 2 }, { cash: 3, cheque: 4 }, { card: 5 }),
    ).toEqual(['cash', 'upi', 'card', 'cheque', 'wallet']);
  });

  it('labels UPI in capitals and others capitalised', () => {
    expect(methodLabel('upi')).toBe('UPI');
    expect(methodLabel('cash')).toBe('Cash');
    expect(methodLabel('wallet')).toBe('Wallet');
  });
});

describe('buildAnalyticsQuery', () => {
  it('repeats status and sends the date range', () => {
    const q = buildAnalyticsQuery(3, {
      dateFrom: '2026-11-18',
      dateTo: '2026-11-24',
      statuses: ['accepted', 'pending'],
    });
    expect(q.get('location_id')).toBe('3');
    expect(q.get('date_from')).toBe('2026-11-18');
    expect(q.get('date_to')).toBe('2026-11-24');
    expect(q.getAll('status')).toEqual(['accepted', 'pending']);
  });

  it('sends no status when none is selected', () => {
    const q = buildAnalyticsQuery(1, { dateFrom: 'a', dateTo: 'b', statuses: [] });
    expect(q.getAll('status')).toEqual([]);
  });
});

describe('TodayIncomeTable', () => {
  const result: TodayIncomeResult = {
    rows: [
      {
        booking_name: 'Priya',
        booking_reference: 'CC-ABC',
        booking_date: '2026-11-21',
        status: 'accepted',
        received_paise: 70000,
        received_by_method: { upi: 50000, wallet: 20000 },
        total_paise: 400000,
        amount_paid_paise: 70000,
        amount_due_paise: 330000,
      },
    ],
    summary: {
      booking_count: 1,
      payment_count: 2,
      received_paise: 70000,
      received_by_method: { upi: 50000, wallet: 20000 },
    },
  };

  it('shows a column and card for every method, including new ones', () => {
    render(<TodayIncomeTable result={result} />);
    const table = screen.getByRole('table');
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((h) => h.textContent);
    expect(headers).toContain('UPI');
    expect(headers).toContain('Wallet');
    expect(screen.getByText('CC-ABC')).toBeInTheDocument();
    expect(screen.getByText('Bookings paid')).toBeInTheDocument();
  });
});
