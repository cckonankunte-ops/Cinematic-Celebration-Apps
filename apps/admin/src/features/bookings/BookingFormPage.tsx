/**
 * Create-booking page. Wraps `BookingForm` with the create mutation. On success
 * it shows the server-computed total (the server is authoritative on price) and
 * links back to the list. Requires a selected location from `useLocation`.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { formatRupees } from '@/lib/money';
import { useLocation } from '@/features/location/useLocation';
import { BookingForm } from './BookingForm';
import { useCreateBooking } from './booking-queries';
import type { BookingCreateValues } from './booking-schema';
import type { BookingRead } from './types';

export function BookingFormPage(): JSX.Element {
  const { selectedLocationId } = useLocation();
  const createBooking = useCreateBooking();
  const [created, setCreated] = useState<BookingRead | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  if (selectedLocationId === null) {
    return <p className="text-sm text-gray-500">Select a location first.</p>;
  }

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
      const booking = await createBooking.mutateAsync(values);
      setCreated(booking);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : 'Failed to create booking.');
    }
  };

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">New booking</h1>
      <BookingForm
        locationId={selectedLocationId}
        onSubmit={onSubmit}
        isSubmitting={createBooking.isPending}
        serverError={serverError}
      />
    </section>
  );
}
