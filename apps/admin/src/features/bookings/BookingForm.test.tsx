import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { BookingForm } from './BookingForm';

// Mock the catalog query hooks so the form renders without a QueryClient or a
// live API. Each returns a tiny deterministic option set.
vi.mock('./catalog-queries', () => ({
  usePlans: () => ({ data: [{ id: 3, title: 'Starlight Package' }] }),
  useSlotAvailability: () => ({
    data: [{ id: 7, description: '9 AM - 12 PM', is_available: true }],
  }),
  useCakes: () => ({ data: [{ id: 4, name: 'Chocolate', price_paise: 50000 }] }),
  useSpecialDecor: () => ({ data: [{ id: 1, name: 'Balloons', price_paise: 20000 }] }),
  useCombos: () => ({ data: [{ id: 2, name: 'Snacks', price_paise: 30000 }] }),
  useOccasions: () => ({ data: [{ id: 5, name: 'Birthday' }] }),
}));

// Mock the preview mutation so the live-summary effect doesn't need a
// QueryClient or a live API.
vi.mock('./booking-queries', () => ({
  usePreviewBooking: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn().mockResolvedValue({}),
    data: undefined,
    isPending: false,
  }),
}));

describe('BookingForm', () => {
  it('renders cascading plan/slot selects and add-on options', () => {
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={() => {}}
        isSubmitting={false}
        serverError={null}
      />,
    );
    expect(screen.getByText('Plan')).toBeInTheDocument();
    expect(screen.getByText('Starlight Package')).toBeInTheDocument();
    expect(screen.getByText('9 AM - 12 PM')).toBeInTheDocument();
    expect(screen.getByText('Balloons')).toBeInTheDocument();
    expect(screen.getByText('Snacks')).toBeInTheDocument();
  });

  it('submits a valid payload with the selected plan and slot', async () => {
    const onSubmit = vi.fn();
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={onSubmit}
        isSubmitting={false}
        serverError={null}
      />,
    );

    fireEvent.change(screen.getByRole('combobox', { name: 'Plan' }), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Slot' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Booking name' }), {
      target: { value: 'Priya S' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Phone' }), {
      target: { value: '9876543210' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Email' }), {
      target: { value: 'priya@example.com' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Create booking' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        location_id: 1,
        plan_id: 3,
        slot_id: 7,
        booking_name: 'Priya S',
        phone: '9876543210',
        email: 'priya@example.com',
        special_decor: [],
        combos: [],
      }),
    );
  });

  it('blocks submit when the phone is empty', async () => {
    const onSubmit = vi.fn();
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={onSubmit}
        isSubmitting={false}
        serverError={null}
      />,
    );

    fireEvent.change(screen.getByRole('combobox', { name: 'Plan' }), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Slot' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Booking name' }), {
      target: { value: 'Priya S' },
    });
    // Phone deliberately left empty.
    fireEvent.click(screen.getByRole('button', { name: 'Create booking' }));

    await waitFor(() =>
      expect(screen.getByText('Phone is required')).toBeInTheDocument(),
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('shows a server error when provided', () => {
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={() => {}}
        isSubmitting={false}
        serverError="Slot not available"
      />,
    );
    expect(screen.getByText('Slot not available')).toBeInTheDocument();
  });
});
