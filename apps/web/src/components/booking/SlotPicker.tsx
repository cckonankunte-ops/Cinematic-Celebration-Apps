import { useEffect, useState } from 'react';
import { publicApi, type Slot } from '../../lib/api';

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
  const [slots, setSlots] = useState<Slot[]>([]);
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
        No slots available for this date. Please pick another date.
      </p>
    );
  }

  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {slots.map((slot) => {
        const selected = slot.id === selectedSlotId;
        return (
          <li key={slot.id}>
            <button
              type="button"
              onClick={() => onSelect(slot)}
              aria-pressed={selected}
              className={`w-full rounded border px-4 py-3 text-left ${
                selected
                  ? 'border-brand bg-brand/10 font-semibold'
                  : 'border-gray-300 hover:border-brand'
              }`}
            >
              {slot.description}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
