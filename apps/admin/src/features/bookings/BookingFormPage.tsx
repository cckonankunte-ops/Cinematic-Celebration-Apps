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
import { formatRupees, rupeesToPaise } from '@/lib/money';
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
    discount_paise: booking.discount_paise,
    food_paise: booking.food_paise,
    other_paise: booking.other_paise,
    cleaning_paise: booking.cleaning_paise,
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
      // The form holds a UI-only rupee advance; the API wants paise. Strip
      // `advance_rupees` and send `advance_amount_paise`/`advance_method` only
      // when an advance was actually entered. Overpayment is allowed server-side.
      const { advance_rupees, advance_method, ...rest } = values;
      const body: CreateBookingBody =
        advance_rupees !== undefined
          ? {
              ...rest,
              advance_method,
              advance_amount_paise: rupeesToPaise(advance_rupees),
            }
          : rest;
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
      const { advance_rupees: _ar, advance_method: _am, ...rest } = values;
      await updateBooking.mutateAsync(rest);
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
