import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { LocationSettings } from './LocationSettings';
import type {
  AdvanceRuleRead,
  DisallowedTimeRead,
  LocationAdminRead,
} from './types';

const updateMutate = vi.fn();
const createDisallowed = vi.fn();
const deleteDisallowed = vi.fn();
const createAdvance = vi.fn();
const deleteAdvance = vi.fn();

let locationRows: LocationAdminRead[] = [];
let disallowedRows: DisallowedTimeRead[] = [];
let advanceRows: AdvanceRuleRead[] = [];

vi.mock('./queries', () => ({
  useLocationsAdmin: () => ({ data: locationRows, isLoading: false, isError: false }),
  useUpdateLocationHours: () => ({ mutate: updateMutate, isPending: false, isError: false }),
  useDisallowedTimes: () => ({ data: disallowedRows, isLoading: false }),
  useCreateDisallowedTime: () => ({ mutate: createDisallowed, isPending: false }),
  useDeleteDisallowedTime: () => ({ mutate: deleteDisallowed, isPending: false }),
  useAdvanceRules: () => ({ data: advanceRows, isLoading: false }),
  useCreateAdvanceRule: () => ({ mutate: createAdvance, isPending: false }),
  useDeleteAdvanceRule: () => ({ mutate: deleteAdvance, isPending: false }),
}));

function loc(mode: 'slot' | 'open'): LocationAdminRead {
  return {
    id: 1,
    name: 'Hulimavu',
    slug: 'hulimavu',
    opens_at: '10:00:00',
    closes_at: '01:00:00',
    last_online_booking_start: '22:00:00',
    allow_late_booking: false,
    booking_mode: mode,
    is_active: true,
  };
}

describe('LocationSettings booking mode', () => {
  beforeEach(() => {
    updateMutate.mockClear();
    createDisallowed.mockClear();
    deleteDisallowed.mockClear();
    createAdvance.mockClear();
    deleteAdvance.mockClear();
    locationRows = [loc('slot')];
    disallowedRows = [];
    advanceRows = [];
  });

  it('renders the booking-mode select with the current value', () => {
    render(<LocationSettings />);
    const select = screen.getByRole('combobox', {
      name: 'Booking mode for Hulimavu',
    }) as HTMLSelectElement;
    expect(select.value).toBe('slot');
  });

  it('saves the chosen booking mode', () => {
    render(<LocationSettings />);
    const select = screen.getByRole('combobox', { name: 'Booking mode for Hulimavu' });
    fireEvent.change(select, { target: { value: 'open' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(updateMutate).toHaveBeenCalledTimes(1);
    const arg = updateMutate.mock.calls[0][0];
    expect(arg.locationId).toBe(1);
    expect(arg.body.booking_mode).toBe('open');
  });
});

describe('AdvanceRulesManager', () => {
  beforeEach(() => {
    updateMutate.mockClear();
    createAdvance.mockClear();
    deleteAdvance.mockClear();
    locationRows = [loc('slot')];
    disallowedRows = [];
    advanceRows = [];
  });

  it('lists advance rules sorted by threshold (high → low) in rupees', () => {
    advanceRows = [
      { id: 1, location_id: 1, min_total_paise: 500000, advance_paise: 200000, is_active: true },
      { id: 2, location_id: 1, min_total_paise: 1000000, advance_paise: 500000, is_active: true },
    ];
    render(<LocationSettings />);
    const items = screen.getAllByText(/Total ≥/);
    // Highest threshold (₹10,000) must render first.
    expect(items[0].textContent).toContain('10,000');
    expect(items[1].textContent).toContain('5,000');
  });

  it('submits a new advance rule converting rupees to paise', () => {
    render(<LocationSettings />);
    fireEvent.change(screen.getByRole('spinbutton', { name: /Total ≥/ }), {
      target: { value: '8000' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: /Advance ₹/ }), {
      target: { value: '3000' },
    });
    const addButtons = screen.getAllByRole('button', { name: 'Add' });
    fireEvent.click(addButtons[addButtons.length - 1]);

    expect(createAdvance).toHaveBeenCalledTimes(1);
    const body = createAdvance.mock.calls[0][0];
    expect(body.min_total_paise).toBe(800000);
    expect(body.advance_paise).toBe(300000);
  });
});
