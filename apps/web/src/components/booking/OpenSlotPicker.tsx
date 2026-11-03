import { useEffect, useState } from 'react';
import {
  publicApi,
  type OpenStart,
  type PlanDuration,
} from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

interface Props {
  planId: number;
  locationId: number;
  bookingDate: string;
  selectedStart: string | null;
  selectedDuration: number | null;
  onSelect: (startTime: string, durationMinutes: number) => void;
}

/** "60" -> "1 hour", "90" -> "1.5 hours", "120" -> "2 hours". */
function durationLabel(minutes: number): string {
  const hours = minutes / 60;
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`;
}

/** "15:00:00" | "15:00" -> "3:00 PM". */
function timeLabel(value: string): string {
  const [h, m] = value.split(':').map(Number);
  const ampm = h < 12 ? 'AM' : 'PM';
  const hour12 = h % 12 || 12;
  return `${hour12}:${String(m).padStart(2, '0')} ${ampm}`;
}

/**
 * Open-mode slot picker (Step 2 for 'open' branches): choose a DURATION (the
 * plan's priced durations) then a START TIME generated from working hours, with
 * unavailable starts greyed out. The server stays authoritative on validity and
 * price; the cleaning buffer is never shown.
 */
export default function OpenSlotPicker({
  planId,
  locationId,
  bookingDate,
  selectedStart,
  selectedDuration,
  onSelect,
}: Props) {
  const [durations, setDurations] = useState<PlanDuration[]>([]);
  const [starts, setStarts] = useState<OpenStart[]>([]);
  const [loadingDurations, setLoadingDurations] = useState(true);
  const [loadingStarts, setLoadingStarts] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the plan's bookable durations.
  useEffect(() => {
    let active = true;
    setLoadingDurations(true);
    setError(null);
    publicApi
      .planDurations(planId)
      .then((rows) => {
        if (active) {
          setDurations(rows);
        }
      })
      .catch(() => {
        if (active) {
          setError('Could not load durations. Please try again.');
        }
      })
      .finally(() => {
        if (active) {
          setLoadingDurations(false);
        }
      });
    return () => {
      active = false;
    };
  }, [planId]);

  // Load candidate start times whenever a duration is chosen.
  useEffect(() => {
    if (selectedDuration === null) {
      setStarts([]);
      return;
    }
    let active = true;
    setLoadingStarts(true);
    setError(null);
    publicApi
      .openAvailability(planId, locationId, bookingDate, selectedDuration)
      .then((rows) => {
        if (active) {
          setStarts(rows);
        }
      })
      .catch(() => {
        if (active) {
          setError('Could not load start times. Please try again.');
        }
      })
      .finally(() => {
        if (active) {
          setLoadingStarts(false);
        }
      });
    return () => {
      active = false;
    };
  }, [planId, locationId, bookingDate, selectedDuration]);

  if (loadingDurations) {
    return <p className="text-gray-500">Loading durations…</p>;
  }
  if (error) {
    return <p className="text-red-600">{error}</p>;
  }
  if (durations.length === 0) {
    return (
      <p className="text-gray-600">
        No durations are configured for this plan yet.
      </p>
    );
  }

  const anyStartAvailable = starts.some((s) => s.is_available);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <p className="text-sm font-medium text-gray-700">Duration</p>
        <ul className="grid gap-2 sm:grid-cols-3">
          {durations.map((d) => {
            const selected = d.duration_minutes === selectedDuration;
            return (
              <li key={d.duration_minutes}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() =>
                    // Changing duration clears the start (handled by the parent
                    // via onSelect with an empty start); keep the chosen start
                    // only if it's still offered.
                    onSelect(
                      selected && selectedStart ? selectedStart : '',
                      d.duration_minutes,
                    )
                  }
                  className={`w-full rounded border px-4 py-3 text-left ${
                    selected
                      ? 'border-brand bg-brand/10 font-semibold'
                      : 'border-gray-300 hover:border-brand'
                  }`}
                >
                  {durationLabel(d.duration_minutes)}
                  <span className="ml-2 text-xs text-gray-500">
                    {formatRupees(d.price_paise)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {selectedDuration !== null && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-700">Start time</p>
          {loadingStarts ? (
            <p className="text-gray-500">Checking availability…</p>
          ) : (
            <>
              <ul className="grid gap-2 sm:grid-cols-3">
                {starts.map((s) => {
                  const hhmm = s.start_time.slice(0, 5);
                  const selected = hhmm === selectedStart;
                  const booked = !s.is_available;
                  return (
                    <li key={hhmm}>
                      <button
                        type="button"
                        disabled={booked}
                        aria-disabled={booked}
                        aria-pressed={selected}
                        onClick={() =>
                          !booked && onSelect(hhmm, selectedDuration)
                        }
                        className={`w-full rounded border px-3 py-2 text-center ${
                          booked
                            ? 'cursor-not-allowed border-gray-200 bg-gray-100 text-gray-400'
                            : selected
                              ? 'border-brand bg-brand/10 font-semibold'
                              : 'border-gray-300 hover:border-brand'
                        }`}
                      >
                        {timeLabel(hhmm)}
                      </button>
                    </li>
                  );
                })}
              </ul>
              {!anyStartAvailable && (
                <p className="text-sm text-gray-600">
                  No start times are free for this duration and date. Try another
                  date or duration.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
