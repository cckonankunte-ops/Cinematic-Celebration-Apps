import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { ApiError } from '@/api/client';
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
    addon_lines: [],
    subtotal_paise: 100000,
    discount_paise: 0,
    food_paise: 0,
    other_paise: 0,
    cleaning_paise: 0,
    coupon_code: code,
    coupon_discount_paise: discountPaise,
    total_paise: 100000 - discountPaise,
    amount_paid_paise: 0,
    amount_due_paise: 100000 - discountPaise,
  };
}

describe('BookingForm', () => {
  beforeEach(() => {
    // Default: the preview "server" does nothing (no breakdown), matching the
    // original tests that don't drive the live summary.
    previewResult = {};
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
