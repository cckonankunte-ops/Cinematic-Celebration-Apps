import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { ApiError } from '@/api/client';
import { BookingForm } from './BookingForm';

// Mode the mocked location reports; tests flip this to exercise slot vs open.
let mockBookingMode: 'slot' | 'open' = 'slot';
let mockPlans: { id: number; title: string }[] = [
  { id: 3, title: 'Starlight Package' },
];
let mockSlots: { id: number; description: string; is_available: boolean }[] = [
  { id: 7, description: '9 AM - 12 PM', is_available: true },
];
let mockDurations: {
  duration_minutes: number;
  price_paise: number;
  advance_paise: number;
}[] = [
  { duration_minutes: 60, price_paise: 79900, advance_paise: 0 },
  { duration_minutes: 120, price_paise: 119900, advance_paise: 0 },
];

// Mock the catalog query hooks so the form renders without a QueryClient or a
// live API. Each returns a tiny deterministic option set.
vi.mock('./catalog-queries', () => ({
  usePlans: () => ({ data: mockPlans }),
  useSlotAvailability: () => ({ data: mockSlots }),
  useCakes: () => ({ data: [{ id: 4, name: 'Chocolate', price_paise: 50000 }] }),
  useSpecialDecor: () => ({ data: [{ id: 1, name: 'Balloons', price_paise: 20000 }] }),
  useCombos: () => ({ data: [{ id: 2, name: 'Snacks', price_paise: 30000 }] }),
  useOccasions: () => ({ data: [{ id: 5, name: 'Birthday' }] }),
  useLocationBookingMode: () => ({
    data: [{ id: 1, name: 'Hulimavu', booking_mode: mockBookingMode }],
  }),
  usePlanDurations: () => ({ data: mockDurations }),
  useOpenAvailability: () => ({
    data: [
      { start_time: '15:00:00', is_available: true },
      { start_time: '15:30:00', is_available: false },
    ],
  }),
  // No later booking: the extra-time hint has nothing to limit.
  useExtraTimeAvailability: () => ({ data: undefined }),
}));

// The signed-in role; extra time is only offered to admins.
let mockRole: 'admin' | 'staff' = 'admin';
vi.mock('@/features/auth/useAuth', () => ({
  useAuth: () => ({ user: { role: mockRole } }),
}));

// Mock the preview mutation so the live-summary effect doesn't need a
// QueryClient or a live API. `previewResult` lets a test control what the
// preview "server" returns, so we can drive the coupon apply/remove UI.
let previewResult: { onSuccess?: Record<string, unknown>; onError?: unknown } = {};

vi.mock('./booking-queries', () => ({
  usePreviewBooking: () => ({
    mutate: (
      _body: unknown,
      opts?: {
        onSuccess?: (data: Record<string, unknown>) => void;
        onError?: (err: unknown) => void;
      },
    ) => {
      if (previewResult.onError !== undefined) {
        opts?.onError?.(previewResult.onError);
      } else if (previewResult.onSuccess !== undefined) {
        opts?.onSuccess?.(previewResult.onSuccess);
      }
    },
    mutateAsync: vi.fn().mockResolvedValue({}),
    data: undefined,
    isPending: false,
  }),
}));

/** A minimal successful breakdown with an applied coupon discount. */
function couponBreakdown(discountPaise: number, code: string): Record<string, unknown> {
  return {
    plan_price_paise: 100000,
    extra_guest_paise: 0,
    kid_extra_guest_paise: 0,
    addon_lines: [],
    subtotal_paise: 100000,
    discount_paise: 0,
    food_paise: 0,
    other_paise: 0,
    cleaning_paise: 0,
    coupon_code: code,
    coupon_discount_paise: discountPaise,
    total_paise: 100000 - discountPaise,
    advance_paise: 0,
    amount_paid_paise: 0,
    amount_due_paise: 100000 - discountPaise,
  };
}

describe('BookingForm', () => {
  beforeEach(() => {
    // Default: the preview "server" does nothing (no breakdown), matching the
    // original tests that don't drive the live summary.
    previewResult = {};
    mockBookingMode = 'slot';
    mockRole = 'admin';
    mockPlans = [{ id: 3, title: 'Starlight Package' }];
    mockSlots = [{ id: 7, description: '9 AM - 12 PM', is_available: true }];
    mockDurations = [
      { duration_minutes: 60, price_paise: 79900, advance_paise: 0 },
      { duration_minutes: 120, price_paise: 119900, advance_paise: 0 },
    ];
  });

  it('keeps prefilled plan and duration selected when options load later', () => {
    mockBookingMode = 'open';
    mockPlans = [];
    mockDurations = [];
    const props = {
      locationId: 1,
      bookingId: 10,
      initial: {
        plan_id: 3,
        duration_minutes: 120,
        start_time: '15:00',
        booking_date: '2030-01-01',
      },
      submitLabel: 'Save changes',
      onSubmit: () => {},
      isSubmitting: false,
      serverError: null,
    };
    const { rerender } = render(<BookingForm {...props} />);

    mockPlans = [{ id: 3, title: 'Starlight Package' }];
    mockDurations = [
      { duration_minutes: 60, price_paise: 79900, advance_paise: 0 },
      { duration_minutes: 120, price_paise: 119900, advance_paise: 0 },
    ];
    rerender(<BookingForm {...props} />);

    expect(screen.getByRole('combobox', { name: 'Plan' })).toHaveValue('3');
    expect(screen.getByRole('combobox', { name: 'Duration' })).toHaveValue('120');
  });

  it('keeps the prefilled slot through plan hydration and submits it in edit mode', async () => {
    mockPlans = [];
    mockSlots = [];
    const onSubmit = vi.fn();
    const props = {
      locationId: 1,
      bookingId: 10,
      initial: {
        plan_id: 3,
        slot_id: 7,
        booking_date: '2030-01-01',
        booking_name: 'Priya S',
        phone: '9876543210',
      },
      submitLabel: 'Save changes',
      onSubmit,
      isSubmitting: false,
      serverError: null,
    };
    const { rerender } = render(<BookingForm {...props} />);

    mockPlans = [{ id: 3, title: 'Starlight Package' }];
    mockSlots = [{ id: 7, description: '9 AM - 12 PM', is_available: true }];
    rerender(<BookingForm {...props} />);

    expect(screen.getByRole('combobox', { name: 'Plan' })).toHaveValue('3');
    expect(screen.getByRole('combobox', { name: 'Slot' })).toHaveValue('7');
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ plan_id: 3, slot_id: 7 }),
      ),
    );
  });

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

  it('guards Apply when the coupon field is empty', async () => {
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={() => {}}
        isSubmitting={false}
        serverError={null}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() =>
      expect(screen.getByText('Enter a coupon code first.')).toBeInTheDocument(),
    );
  });

  it('applies a coupon and shows the discount, then allows removing it', async () => {
    // Preview "server" returns a valid coupon discount of ₹100 (10000 paise).
    previewResult = { onSuccess: couponBreakdown(10000, 'SAVE10') };
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={() => {}}
        isSubmitting={false}
        serverError={null}
      />,
    );
    // A plan + slot + date are needed for the preview effect to fire.
    fireEvent.change(screen.getByRole('combobox', { name: 'Plan' }), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Slot' }), {
      target: { value: '7' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Coupon code' }), {
      target: { value: 'SAVE10' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() =>
      expect(screen.getByText(/Coupon SAVE10 applied/)).toBeInTheDocument(),
    );
    // Now a Remove button is shown; clicking it drops the applied state.
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument(),
    );
  });

  it('renders the slot picker in slot mode', () => {
    mockBookingMode = 'slot';
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={() => {}}
        isSubmitting={false}
        serverError={null}
      />,
    );
    expect(screen.getByRole('combobox', { name: 'Slot' })).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Duration' })).not.toBeInTheDocument();
  });

  it('renders duration + start-time pickers in open mode', () => {
    mockBookingMode = 'open';
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={() => {}}
        isSubmitting={false}
        serverError={null}
      />,
    );
    // Open mode shows Duration + Start time instead of Slot.
    expect(screen.getByRole('combobox', { name: 'Duration' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Start time' })).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Slot' })).not.toBeInTheDocument();
  });

  it('submits an open-mode window (start_time + duration, no slot_id)', async () => {
    mockBookingMode = 'open';
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
    fireEvent.change(screen.getByRole('combobox', { name: 'Duration' }), {
      target: { value: '60' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Start time' }), {
      target: { value: '15:00' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Booking name' }), {
      target: { value: 'Priya S' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Phone' }), {
      target: { value: '9876543210' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create booking' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const values = onSubmit.mock.calls[0][0];
    expect(values.start_time).toBe('15:00');
    expect(values.duration_minutes).toBe(60);
    expect(values.slot_id).toBeUndefined();
  });

  const renderForm = (onSubmit: () => void = () => {}): void => {
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={onSubmit}
        isSubmitting={false}
        serverError={null}
      />,
    );
  };

  it('offers extra time to an admin in open mode', () => {
    mockBookingMode = 'open';
    mockRole = 'admin';
    renderForm();
    expect(screen.getByLabelText(/Extra minutes/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Extra time price/)).toBeInTheDocument();
  });

  it('hides extra time from staff in open mode', () => {
    mockBookingMode = 'open';
    mockRole = 'staff';
    renderForm();
    expect(screen.queryByLabelText(/Extra minutes/)).not.toBeInTheDocument();
  });

  it('hides extra time in slot mode, even for an admin', () => {
    mockBookingMode = 'slot';
    mockRole = 'admin';
    renderForm();
    expect(screen.queryByLabelText(/Extra minutes/)).not.toBeInTheDocument();
  });

  it('submits the extra minutes and price for an open-mode booking', async () => {
    mockBookingMode = 'open';
    mockRole = 'admin';
    const onSubmit = vi.fn();
    renderForm(onSubmit);
    fireEvent.change(screen.getByRole('combobox', { name: 'Plan' }), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Duration' }), {
      target: { value: '120' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Start time' }), {
      target: { value: '15:00' },
    });
    fireEvent.change(screen.getByLabelText(/Extra minutes/), { target: { value: '45' } });
    fireEvent.change(screen.getByLabelText(/Extra time price/), {
      target: { value: '500' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Booking name' }), {
      target: { value: 'Priya S' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Phone' }), {
      target: { value: '9876543210' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create booking' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const values = onSubmit.mock.calls[0][0];
    expect(values.extra_minutes).toBe(45);
    expect(values.extra_time_rupees).toBe(500);
  });

  it('shows a field-level error when the coupon is rejected', async () => {
    // Preview "server" rejects the coupon with a COUPON_INVALID ApiError.
    const err = new ApiError('COUPON_INVALID', 'The coupon code is not valid.', 422);
    previewResult = { onError: err };
    render(
      <BookingForm
        locationId={1}
        submitLabel="Create booking"
        onSubmit={() => {}}
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
    fireEvent.change(screen.getByRole('textbox', { name: 'Coupon code' }), {
      target: { value: 'BADCODE' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() =>
      expect(screen.getByText('The coupon code is not valid.')).toBeInTheDocument(),
    );
  });
});
