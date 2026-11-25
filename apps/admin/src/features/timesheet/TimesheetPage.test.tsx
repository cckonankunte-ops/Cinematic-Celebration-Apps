import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { TimesheetPage } from './TimesheetPage';
import type { TimesheetRow } from './types';

function row(overrides: Partial<TimesheetRow>): TimesheetRow {
  return {
    slot_id: 0,
    slot_sort_order: 0,
    slot_description: '11:00 AM - 1:00 PM',
    plan_title: 'Starlight',
    booking_name: 'Asha',
    phone: '9876543210',
    people: 4,
    name_on_cake: null,
    led_name: null,
    cake: null,
    special_decor: null,
    combos: null,
    occasion: null,
    amount_due_paise: 100000,
    ...overrides,
  };
}

let mockRows: TimesheetRow[] = [];

vi.mock('./queries', () => ({
  useTimesheet: () => ({ data: mockRows, isLoading: false, isError: false }),
}));
vi.mock('@/features/location/useLocation', () => ({
  useLocation: () => ({ selectedLocationId: 1 }),
}));

describe('TimesheetPage', () => {
  it('shows the time range next to the booking name', () => {
    mockRows = [row({})];
    render(<TimesheetPage />);
    expect(screen.getByText('Asha - 11:00 AM - 1:00 PM')).toBeInTheDocument();
  });

  it('lists every booking in the order the API returns (start time), with no slot headings', () => {
    mockRows = [
      row({ booking_name: 'First', slot_description: '10:00 AM - 11:00 AM' }),
      row({ booking_name: 'Second', slot_description: '2:00 PM - 3:00 PM' }),
      row({ booking_name: 'Third', slot_description: '6:00 PM - 8:00 PM' }),
    ];
    render(<TimesheetPage />);
    expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument();
    const names = screen
      .getAllByText(/^(First|Second|Third) - /)
      .map((el) => el.textContent?.split(' - ')[0]);
    expect(names).toEqual(['First', 'Second', 'Third']);
  });

  it('bolds the plan name and shows LED and decor quantity', () => {
    mockRows = [row({ led_name: 'ASHA', special_decor: '2 Party popper, Balloons' })];
    render(<TimesheetPage />);
    expect(screen.getByText('Starlight')).toHaveClass('font-bold');
    expect(screen.getByText('ASHA')).toBeInTheDocument();
    expect(screen.getByText('2 Party popper, Balloons')).toBeInTheDocument();
  });

  it('omits the LED line when there is no LED text', () => {
    mockRows = [row({ led_name: null })];
    render(<TimesheetPage />);
    expect(screen.queryByText('LED:')).not.toBeInTheDocument();
  });
});
