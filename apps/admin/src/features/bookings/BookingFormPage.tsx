/**
 * Create/Edit booking page. The route param `bookingId` selects the mode:
 * absent → create (`useCreateBooking`, shows the server-computed total on
 * success); present → edit (loads the `BookingRead`, pre-fills the form, and
 * PATCHes via `useUpdateBooking`). The server is authoritative on price, so the
 * create success panel shows the server totals. Requires a selected location.
 */

import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { formatRupees, paiseToRupees, rupeesToPaise } from '@/lib/money';
import { useLocation } from '@/features/location/useLocation';
import { BookingForm } from './BookingForm';
import { PaymentHistory } from './PaymentHistory';
import {
  useBooking,
  useCreateBooking,
  useUpdateBooking,
  type CreateBookingBody,
} from './booking-queries';
import type { BookingCreateInput, BookingCreateValues } from './booking-schema';
import type { BookingRead } from './types';

/** Map a loaded `BookingRead` into form pre-fill values. */
function toInitialValues(booking: BookingRead): Partial<BookingCreateInput> {
  const cakeItem = booking.items.find((it) => it.kind === 'cake');
  return {
    location_id: booking.location_id,
    plan_id: booking.plan_id,
    slot_id: booking.slot_id,
    booking_date: booking.booking_date,
    booking_name: booking.booking_name,
    phone: booking.phone ?? '',
    email: booking.email ?? undefined,
    special_person_name: booking.special_person_name ?? undefined,
    name_on_cake: booking.name_on_cake ?? undefined,
    message: booking.message ?? undefined,
    people: booking.people,
    occasion_id: booking.occasion_id ?? undefined,
    cake_id: cakeItem?.item_id ?? undefined,
    cake_weight_half_kg: cakeItem?.weight_half_kg ?? 1,
    special_decor: booking.items
      .filter((it) => it.kind === 'decor' && it.item_id !== null)
      .map((it) => ({ id: it.item_id as number, quantity: it.quantity })),
    combos: booking.items
      .filter((it) => it.kind === 'combo' && it.item_id !== null)
      .map((it) => ({ id: it.item_id as number })),
    led_name: booking.led_name ?? undefined,
    coupon_code: booking.coupon_code ?? undefined,
    // Stored as paise; the form edits rupees.
    discount_rupees: paiseToRupees(booking.discount_paise),
    food_rupees: paiseToRupees(booking.food_paise),
    other_rupees: paiseToRupees(booking.other_paise),
    cleaning_rupees: paiseToRupees(booking.cleaning_paise),
  };
}

/**
 * Map the form's UI-only rupee money fields to the API's integer-paise fields,
 * stripping the `*_rupees` and advance inputs (advance is attached separately
 * on create; never sent on edit). Shared by the create and edit submit paths.
 */
function toApiMoney(
  values: BookingCreateValues,
): Omit<CreateBookingBody, 'advance_amount_paise' | 'advance_method'> {
  const {
    discount_rupees,
    food_rupees,
    other_rupees,
    cleaning_rupees,
    advance_rupees: _ar,
    advance_method: _am,
    ...rest
  } = values;
  void _ar;
  void _am;
  return {
    ...rest,
    discount_paise: rupeesToPaise(discount_rupees),
    food_paise: rupeesToPaise(food_rupees),
    other_paise: rupeesToPaise(other_rupees),
    cleaning_paise: rupeesToPaise(cleaning_rupees),
  };
}

export function BookingFormPage(): JSX.Element {
  const { selectedLocationId } = useLocation();
  const params = useParams<{ bookingId?: string }>();
  const bookingId = params.bookingId ? Number(params.bookingId) : undefined;
  const mode: 'create' | 'edit' = bookingId ? 'edit' : 'create';

  if (mode === 'edit' && bookingId !== undefined) {
    return <EditBooking bookingId={bookingId} />;
  }

  if (selectedLocationId === null) {
    return <p className="text-sm text-gray-500">Select a location first.</p>;
  }

  return <CreateBooking locationId={selectedLocationId} />;
}

function CreateBooking({ locationId }: { locationId: number }): JSX.Element {
  const createBooking = useCreateBooking();
  const [created, setCreated] = useState<BookingRead | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  if (created !== null) {
    return (
      <section className="space-y-3">
        <h1 className="text-xl font-semibold text-gray-900">Booking created</h1>
        <p className="text-sm text-gray-700">
          Reference <span className="font-mono">{created.booking_reference}</span>
        </p>
        <p className="text-sm text-gray-700">Total: {formatRupees(created.total_paise)}</p>
        <p className="text-sm text-gray-700">
          Required advance: {formatRupees(created.advance_paise)}
        </p>
        <Link to="/bookings" className="text-sm text-blue-600 underline">
          Back to bookings
        </Link>
      </section>
    );
  }

  const onSubmit = async (values: BookingCreateValues): Promise<void> => {
    setServerError(null);
    try {
      // The form holds UI-only rupee money fields; the API wants paise. Map the
      // rupee fields to their `*_paise` counterparts and send the advance only
      // when entered. Overpayment is allowed server-side.
      const body: CreateBookingBody = {
        ...toApiMoney(values),
        ...(values.advance_rupees !== undefined
          ? {
              advance_method: values.advance_method,
              advance_amount_paise: rupeesToPaise(values.advance_rupees),
            }
          : {}),
      };
      const booking = await createBooking.mutateAsync(body);
      setCreated(booking);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : 'Failed to create booking.');
    }
  };

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">New booking</h1>
      <BookingForm
        locationId={locationId}
        submitLabel="Create booking"
        onSubmit={onSubmit}
        isSubmitting={createBooking.isPending}
        serverError={serverError}
      />
    </section>
  );
}

function EditBooking({ bookingId }: { bookingId: number }): JSX.Element {
  const navigate = useNavigate();
  const bookingQuery = useBooking(bookingId);
  const updateBooking = useUpdateBooking(bookingId);
  const [serverError, setServerError] = useState<string | null>(null);

  if (bookingQuery.isPending) {
    return <p className="text-sm text-gray-500">Loading booking…</p>;
  }

  if (bookingQuery.isError || bookingQuery.data === undefined) {
    const message =
      bookingQuery.error instanceof ApiError
        ? bookingQuery.error.message
        : 'Failed to load booking.';
    return <p className="text-sm text-red-600">{message}</p>;
  }

  const booking = bookingQuery.data;

  const onSubmit = async (values: BookingCreateValues): Promise<void> => {
    setServerError(null);
    try {
      // Advance-on-create is a create-only concern; never send advance fields
      // on edit (the edit flow uses PaymentHistory/record-payment instead).
      await updateBooking.mutateAsync(toApiMoney(values));
      navigate('/bookings');
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : 'Failed to save changes.');
    }
  };

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">
        Edit booking <span className="font-mono">{booking.booking_reference}</span>
      </h1>
      <BookingForm
        locationId={booking.location_id}
        bookingId={bookingId}
        initial={toInitialValues(booking)}
        paymentsVersion={booking.amount_paid_paise}
        submitLabel="Save changes"
        onSubmit={onSubmit}
        isSubmitting={updateBooking.isPending}
        serverError={serverError}
      />
      <PaymentHistory
        bookingId={bookingId}
        payments={booking.payments}
        totalPaise={booking.total_paise}
      />
    </section>
  );
}
