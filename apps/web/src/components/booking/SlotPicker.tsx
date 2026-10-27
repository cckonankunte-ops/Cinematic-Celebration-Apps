import { useEffect, useState } from 'react';
import { publicApi, type SlotAvailability } from '../../lib/api';

interface Props {
  planId: number;
  locationId: number;
  bookingDate: string;
  selectedSlotId: number | null;
  onSelect: (slot: Slot) => void;
}

/**
 * Step 2: fetch the *available* (unheld) slots for the chosen plan + date via
 * POST /public/plans/{id}/available-slots and let the customer pick one.
 */
export default function SlotPicker({
  planId,
  locationId,
  bookingDate,
  selectedSlotId,
  onSelect,
}: Props) {
  const [slots, setSlots] = useState<SlotAvailability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    publicApi
      .availableSlots(planId, locationId, bookingDate)
      .then((result) => {
        if (active) {
          setSlots(result);
        }
      })
      .catch(() => {
        if (active) {
          setError('Could not load available slots. Please try again.');
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
  }, [planId, locationId, bookingDate]);

  if (loading) {
    return <p className="text-gray-500">Checking availability…</p>;
  }
  if (error) {
    return <p className="text-red-600">{error}</p>;
  }
  if (slots.length === 0) {
    return (
      <p className="text-gray-600">
        No slots for this date. Please pick another date.
      </p>
    );
  }

  const anyAvailable = slots.some((s) => s.is_available);

  return (
    <div className="space-y-2">
      <ul className="grid gap-2 sm:grid-cols-2">
        {slots.map((slot) => {
          const selected = slot.id === selectedSlotId;
          const booked = !slot.is_available;
          return (
            <li key={slot.id}>
              <button
                type="button"
                disabled={booked}
                aria-disabled={booked}
                onClick={() => !booked && onSelect(slot)}
                aria-pressed={selected}
                className={`w-full rounded border px-4 py-3 text-left ${
                  booked
                    ? 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-400'
                    : selected
                      ? 'border-brand bg-brand/10 font-semibold'
                      : 'border-gray-300 hover:border-brand'
                }`}
              >
                {slot.description}
                {booked && (
                  <span className="ml-2 text-xs">· Already booked</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      {!anyAvailable && (
        <p className="text-sm text-gray-600">
          All slots for this date are booked. Please pick another date.
        </p>
      )}
    </div>
  );
}
