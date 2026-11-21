import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { BookingFormPage } from './BookingFormPage';
import type { BookingCreateInput } from './booking-schema';

const createBooking = vi.fn();
let receivedInitial: Partial<BookingCreateInput> | undefined;

vi.mock('./booking-queries', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./booking-queries')>();
  return {
    ...actual,
    useCreateBooking: () => ({ mutateAsync: createBooking, isPending: false }),
    useBooking: () => ({ data: undefined, isLoading: true }),
    useUpdateBooking: () => ({ mutateAsync: vi.fn(), isPending: false }),
  };
});

// The real form needs the whole catalog; a stub shows what it was given and
// submits fixed values, which is all this page-level test needs.
vi.mock('./BookingForm', () => ({
  BookingForm: (props: {
    initial?: Partial<BookingCreateInput>;
    onSubmit: (values: Record<string, unknown>) => Promise<void>;
  }) => {
    receivedInitial = props.initial;
    return (
      <button
        type="button"
        onClick={() =>
          void props.onSubmit({
            location_id: 2,
            plan_id: 3,
            booking_date: '2026-11-20',
            booking_name: 'Asha',
            phone: '9876543210',
            people: 5,
            kids: 0,
            cake_weight_half_kg: 1,
            special_decor: [],
            combos: [],
            discount_rupees: 0,
            food_rupees: 0,
            other_rupees: 0,
            cleaning_rupees: 0,
            advance_method: 'cash',
          })
        }
      >
        Submit stub
      </button>
    );
  },
}));

vi.mock('@/features/location/useLocation', () => ({
  useLocation: () => ({
    locations: [{ id: 2, name: 'Hulimavu', slug: 'hulimavu' }],
    selectedLocationId: 2,
    canSwitch: false,
    selectLocation: vi.fn(),
  }),
}));

const fromLead = {
  fromLead: {
    leadId: 7,
    locationId: 2,
    label: 'Asha',
    initial: { location_id: 2, booking_name: 'Asha', phone: '9876543210', people: 5, plan_id: 3 },
  },
};

function renderAt(state: unknown): void {
  render(
    <MemoryRouter initialEntries={[{ pathname: '/bookings/new', state }]}>
      <Routes>
        <Route path="/bookings/new" element={<BookingFormPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  createBooking.mockReset();
  receivedInitial = undefined;
  createBooking.mockResolvedValue({
    booking_reference: 'CC-1',
    total_paise: 100000,
    advance_paise: 50000,
  });
});

describe('Create booking from a lead', () => {
  it('pre-fills the form, shows the lead banner and sends lead_id', async () => {
    renderAt(fromLead);
    expect(screen.getByText(/Creating a booking for lead/)).toHaveTextContent('Asha');
    expect(receivedInitial).toEqual(fromLead.fromLead.initial);

    fireEvent.click(screen.getByRole('button', { name: 'Submit stub' }));
    await waitFor(() => expect(createBooking).toHaveBeenCalled());
    expect(createBooking.mock.calls[0][0].lead_id).toBe(7);
    expect(await screen.findByRole('link', { name: 'Back to lead' })).toHaveAttribute(
      'href',
      '/leads/7',
    );
  });

  it('is unchanged on a direct visit (no lead, no lead_id)', async () => {
    renderAt(null);
    expect(screen.queryByText(/Creating a booking for lead/)).toBeNull();
    expect(receivedInitial).toBeUndefined();
    fireEvent.click(screen.getByRole('button', { name: 'Submit stub' }));
    await waitFor(() => expect(createBooking).toHaveBeenCalled());
    expect(createBooking.mock.calls[0][0]).not.toHaveProperty('lead_id');
  });
});
