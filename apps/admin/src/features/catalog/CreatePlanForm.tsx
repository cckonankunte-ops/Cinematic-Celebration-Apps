/**
 * Compact create-plan form. Money fields are entered in rupees and converted to
 * integer paise before posting (the API only accepts paise). On success the
 * plans list is invalidated by the mutation and the form resets.
 */

import { useState } from 'react';

import { rupeesToPaise } from '@/lib/money';
import { useCreatePlan } from './queries';
import type { PlanCreateBody } from './types';

interface CreatePlanFormProps {
  locationId: number | null;
  defaultEffectiveFrom: string;
}

const EMPTY = {
  title: '',
  priceRupees: '',
  peopleAllowed: '4',
  maxPeople: '',
  extraGuestRupees: '0',
  advanceRupees: '0',
};

export function CreatePlanForm({
  locationId,
  defaultEffectiveFrom,
}: CreatePlanFormProps): JSX.Element {
  const [form, setForm] = useState({ ...EMPTY });
  const createPlan = useCreatePlan(locationId);

  const update = (key: keyof typeof EMPTY) => (value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const onSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (locationId === null) {
      return;
    }
    const body: PlanCreateBody = {
      location_id: locationId,
      title: form.title.trim(),
      plan_type: 1,
      price_paise: rupeesToPaise(Number(form.priceRupees)),
      people_allowed: Number(form.peopleAllowed),
      max_people_allowed: Number(form.maxPeople),
      extra_guest_paise: rupeesToPaise(Number(form.extraGuestRupees)),
      give_discount: false,
      max_discount_paise: 0,
      advance_paise: rupeesToPaise(Number(form.advanceRupees)),
      effective_from: defaultEffectiveFrom,
    };
    createPlan.mutate(body, { onSuccess: () => setForm({ ...EMPTY }) });
  };

  const field = 'rounded border border-gray-300 px-2 py-1 text-sm';

  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded border border-gray-200 bg-white p-3">
      <h2 className="text-base font-semibold text-gray-800">New plan</h2>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <input
          className={field}
          placeholder="Title"
          required
          value={form.title}
          onChange={(e) => update('title')(e.target.value)}
        />
        <input
          className={field}
          type="number"
          min={0}
          step="0.01"
          placeholder="Price (₹)"
          required
          value={form.priceRupees}
          onChange={(e) => update('priceRupees')(e.target.value)}
        />
        <input
          className={field}
          type="number"
          min={0}
          placeholder="People allowed"
          required
          value={form.peopleAllowed}
          onChange={(e) => update('peopleAllowed')(e.target.value)}
        />
        <input
          className={field}
          type="number"
          min={0}
          placeholder="Max people"
          required
          value={form.maxPeople}
          onChange={(e) => update('maxPeople')(e.target.value)}
        />
        <input
          className={field}
          type="number"
          min={0}
          step="0.01"
          placeholder="Extra guest (₹)"
          value={form.extraGuestRupees}
          onChange={(e) => update('extraGuestRupees')(e.target.value)}
        />
        <input
          className={field}
          type="number"
          min={0}
          step="0.01"
          placeholder="Advance (₹)"
          value={form.advanceRupees}
          onChange={(e) => update('advanceRupees')(e.target.value)}
        />
      </div>
      {createPlan.isError && (
        <p className="text-xs text-red-600">Could not create plan.</p>
      )}
      <button
        type="submit"
        disabled={locationId === null || createPlan.isPending}
        className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {createPlan.isPending ? 'Creating…' : 'Create plan'}
      </button>
    </form>
  );
}
