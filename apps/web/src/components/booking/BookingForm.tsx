import type { Occasion } from '../../lib/api';
import type { BookingDraft } from './types';

interface Props {
  draft: BookingDraft;
  occasions: Occasion[];
  maxPeople: number;
  onChange: (patch: Partial<BookingDraft>) => void;
}

/**
 * Step 4: customer contact + party details. Validation mirrors the API
 * (people >= 1 and <= plan.max_people_allowed; name + email required). All
 * money stays server-side; this collects only IDs and text fields.
 */
export default function BookingForm({
  draft,
  occasions,
  maxPeople,
  onChange,
}: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Your name *</span>
        <input
          type="text"
          required
          value={draft.bookingName}
          onChange={(e) => onChange({ bookingName: e.target.value })}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Email *</span>
        <input
          type="email"
          required
          value={draft.email}
          onChange={(e) => onChange({ email: e.target.value })}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Phone</span>
        <input
          type="tel"
          value={draft.phone}
          onChange={(e) => onChange({ phone: e.target.value })}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">
          Number of people (max {maxPeople}) *
        </span>
        <input
          type="number"
          min={1}
          max={maxPeople}
          required
          value={draft.people}
          onChange={(e) => onChange({ people: Number(e.target.value) })}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Occasion</span>
        <select
          value={draft.occasionId ?? ''}
          onChange={(e) =>
            onChange({
              occasionId: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="rounded border border-gray-300 px-3 py-2"
        >
          <option value="">Select…</option>
          {occasions.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Special person's name</span>
        <input
          type="text"
          value={draft.specialPersonName}
          onChange={(e) => onChange({ specialPersonName: e.target.value })}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Name on cake</span>
        <input
          type="text"
          value={draft.nameOnCake}
          onChange={(e) => onChange({ nameOnCake: e.target.value })}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1 sm:col-span-2">
        <span className="text-sm font-medium">Message / special requests</span>
        <textarea
          rows={3}
          value={draft.message}
          onChange={(e) => onChange({ message: e.target.value })}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>
    </div>
  );
}
