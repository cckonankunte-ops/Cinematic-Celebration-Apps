import { useEffect, useState } from 'react';
import {
  ApiError,
  publicApi,
  type BookingStatus as Status,
} from '../../lib/api';
import { formatDate, formatRupees } from '../../lib/formatters';

/**
 * Reads `?token=` from the URL and looks up a booking via
 * GET /public/bookings/{token}. Shows the status and derived amounts.
 */
export default function BookingStatus() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token');
    if (!token) {
      setError('No booking token provided.');
      setLoading(false);
      return;
    }
    let active = true;
    publicApi
      .getBookingStatus(token)
      .then((s) => {
        if (active) {
          setStatus(s);
        }
      })
      .catch((err) => {
        if (active) {
          setError(
            err instanceof ApiError && err.status === 404
              ? 'No booking found for that token.'
              : 'Could not load your booking. Please try again.',
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <p className="text-gray-500">Loading your booking…</p>;
  }
  if (error) {
    return <p className="text-red-600">{error}</p>;
  }
  if (!status) {
    return null;
  }

  return (
    <div className="rounded border border-gray-200 p-6">
      <h2 className="text-xl font-semibold capitalize">
        Status: {status.status}
      </h2>
      <dl className="mt-4 space-y-2 text-sm">
        <Row label="Name" value={status.booking_name} />
        <Row label="Plan" value={status.plan_title} />
        <Row label="Slot" value={status.slot_description} />
        <Row label="Date" value={formatDate(status.booking_date)} />
        <Row label="Total" value={formatRupees(status.total_paise)} />
        <Row label="Paid" value={formatRupees(status.amount_paid_paise)} />
        <Row
          label="Amount due"
          value={formatRupees(status.amount_due_paise)}
        />
        <Row label="Fully paid" value={status.is_paid ? 'Yes' : 'No'} />
      </dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
