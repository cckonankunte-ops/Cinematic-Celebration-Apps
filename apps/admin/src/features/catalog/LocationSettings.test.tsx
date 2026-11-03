import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import { LocationSettings } from './LocationSettings';
import type { LocationAdminRead } from './types';

const updateMutate = vi.fn();

let locationRows: LocationAdminRead[] = [];

vi.mock('./queries', () => ({
  useLocationsAdmin: () => ({ data: locationRows, isLoading: false, isError: false }),
  useUpdateLocationHours: () => ({ mutate: updateMutate, isPending: false, isError: false }),
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
    locationRows = [loc('slot')];
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
