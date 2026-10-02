/** Small coloured pill for a booking status. */

import type { BookingStatus } from './types';

const STYLES: Record<BookingStatus, string> = {
  pending: 'bg-amber-100 text-amber-800',
  accepted: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  expired: 'bg-gray-200 text-gray-600',
};

export function StatusBadge({ status }: { status: BookingStatus }): JSX.Element {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {status}
    </span>
  );
}
