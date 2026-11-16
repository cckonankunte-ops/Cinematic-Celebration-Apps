import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import HomeBookingWidget from './HomeBookingWidget';
import { publicApi, type Location } from '../../lib/api';

function loc(id: number, name: string, slug: string, phone: string | null): Location {
  return { id, name, slug, address: null, phone };
}

// Make window.location.href settable so we can assert navigation.
const originalLocation = window.location;
let hrefValue = 'http://localhost/';

beforeEach(() => {
  hrefValue = 'http://localhost/';
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: {
      ...originalLocation,
      get href() {
        return hrefValue;
      },
      set href(v: string) {
        hrefValue = v;
      },
      search: '',
    },
  });
});

afterEach(() => {
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: originalLocation,
  });
  vi.restoreAllMocks();
});

describe('HomeBookingWidget', () => {
  it('navigates to /book with the selected branch slug and date', async () => {
    vi.spyOn(publicApi, 'listLocations').mockResolvedValue([
      loc(1, 'Hulimavu', 'hulimavu', '9876543210'),
      loc(2, 'JP Nagar', 'jp-nagar', '9876500000'),
    ]);

    render(<HomeBookingWidget />);

    // Wait for branches to load (dropdown populated).
    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'Hulimavu' })).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText('Branch'), { target: { value: 'jp-nagar' } });
    fireEvent.change(screen.getByLabelText('Booking date'), {
      target: { value: '2027-01-15' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Book Now' }));

    expect(hrefValue).toBe('/book?location=jp-nagar&date=2027-01-15');
  });

  it('dials the selected branch on Call now', async () => {
    vi.spyOn(publicApi, 'listLocations').mockResolvedValue([
      loc(1, 'Hulimavu', 'hulimavu', '9876543210'),
    ]);

    render(<HomeBookingWidget />);
    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'Hulimavu' })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Call now' }));
    expect(hrefValue).toBe('tel:+919876543210');
  });

  it('shows a hint instead of dialing when the branch has no phone', async () => {
    vi.spyOn(publicApi, 'listLocations').mockResolvedValue([
      loc(1, 'Hulimavu', 'hulimavu', null),
    ]);

    render(<HomeBookingWidget />);
    await waitFor(() =>
      expect(screen.getByRole('option', { name: 'Hulimavu' })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Call now' }));
    expect(screen.getByText(/no phone number listed/i)).toBeInTheDocument();
    expect(hrefValue).toBe('http://localhost/');
  });
});
