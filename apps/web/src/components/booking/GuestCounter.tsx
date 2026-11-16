/**
 * Adults + kids steppers for the Basic Details step. Adults must stay >= 1
 * (a booking needs at least one adult); kids >= 0. Total guests = adults + kids
 * and must not exceed the plan's max; the parent surfaces the cap message, this
 * only enforces the per-field floors. All pricing is server-side; this collects
 * counts only.
 */
interface Props {
  adults: number;
  kids: number;
  /** Plan's max total guests (adults + kids), shown as a hint. */
  maxPeople: number;
  onChange: (next: { adults: number; kids: number }) => void;
}

function Stepper({
  label,
  hint,
  value,
  min,
  onChange,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 px-3 py-2">
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500">{hint}</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          onClick={() => onChange(Math.max(min, value - 1))}
          disabled={value <= min}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-300 text-lg font-bold text-gray-700 transition hover:bg-gray-50 disabled:opacity-40"
        >
          −
        </button>
        <input
          type="number"
          min={min}
          aria-label={label}
          value={value}
          onChange={(e) => {
            const parsed = Number(e.target.value);
            onChange(Number.isInteger(parsed) && parsed >= min ? parsed : min);
          }}
          className="w-12 rounded border border-gray-300 px-2 py-1 text-center text-sm"
        />
        <button
          type="button"
          aria-label={`Increase ${label}`}
          onClick={() => onChange(value + 1)}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-gray-300 text-lg font-bold text-gray-700 transition hover:bg-gray-50"
        >
          +
        </button>
      </div>
    </div>
  );
}

export default function GuestCounter({ adults, kids, maxPeople, onChange }: Props) {
  const total = adults + kids;
  const over = total > maxPeople;
  return (
    <div className="space-y-2">
      <Stepper
        label="People (above 10 yrs)"
        hint="At least 1 adult"
        value={adults}
        min={1}
        onChange={(v) => onChange({ adults: v, kids })}
      />
      <Stepper
        label="Kids (3–10 yrs)"
        hint="Charged a reduced rate"
        value={kids}
        min={0}
        onChange={(v) => onChange({ adults, kids: v })}
      />
      <p className={`text-xs ${over ? 'text-red-600' : 'text-gray-500'}`}>
        Total guests: {total} (max {maxPeople})
        {over ? ' — please reduce to fit this plan.' : ''}
      </p>
    </div>
  );
}
