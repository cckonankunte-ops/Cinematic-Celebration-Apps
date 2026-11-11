/**
 * Staff/admin control to enable or disable late online booking for a branch.
 *
 * Staff flip this off when they log off for the day. The control is only
 * enabled for staff after 21:15 IST (the server enforces the same gate);
 * admins may use it any time. The booking cutoff itself is a separate branch
 * setting; this only flips whether late starts are offered to the public.
 */

import { useMemo, useState } from 'react';

import { ApiError } from '@/api/client';
import { useAuth } from '@/features/auth/useAuth';
import { useSetLateBooking } from './booking-queries';

interface LateBookingToggleProps {
  locationId: number;
  /** Current switch value for the branch (from the locations query). */
  allowLateBooking: boolean;
}

/** IST "HH:MM" now, used only to enable/disable the control for staff. */
function istHourMinute(): { h: number; m: number } {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date());
  const h = Number(parts.find((p) => p.type === 'hour')?.value ?? '0');
  const m = Number(parts.find((p) => p.type === 'minute')?.value ?? '0');
  return { h, m };
}

export function LateBookingToggle({
  locationId,
  allowLateBooking,
}: LateBookingToggleProps): JSX.Element {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const setLate = useSetLateBooking(locationId);
  const [error, setError] = useState<string | null>(null);

  // Staff gate: control enabled only after 21:15 IST. Admins any time.
  const afterCutoff = useMemo(() => {
    const { h, m } = istHourMinute();
    return h > 21 || (h === 21 && m >= 15);
  }, []);
  const disabled = setLate.isPending || (!isAdmin && !afterCutoff);

  const onToggle = async (): Promise<void> => {
    setError(null);
    try {
      await setLate.mutateAsync({ allow: !allowLateBooking });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Could not update late booking.',
      );
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={allowLateBooking}
          disabled={disabled}
          onChange={onToggle}
        />
        Allow late online booking
      </label>
      {!isAdmin && !afterCutoff && (
        <span className="text-xs text-gray-500">
          Available after 9:15 PM
        </span>
      )}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
