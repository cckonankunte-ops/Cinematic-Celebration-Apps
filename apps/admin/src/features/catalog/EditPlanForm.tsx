/**
 * Edit an existing plan in place. Exposes every editable plan field (the create
 * form only collects a subset). Money fields are entered in rupees and converted
 * to integer paise before the PATCH. Only changed values are sent. On success the
 * plans list is invalidated by the mutation.
 */

import { useState } from 'react';

import { paiseToRupees, rupeesToPaise } from '@/lib/money';
import { useUpdatePlan } from './queries';
import type { PlanAdminRead, PlanUpdateBody } from './types';

interface EditPlanFormProps {
  plan: PlanAdminRead;
  locationId: number | null;
  onDone: () => void;
}

export function EditPlanForm({
  plan,
  locationId,
  onDone,
}: EditPlanFormProps): JSX.Element {
  const [form, setForm] = useState({
    title: plan.title,
    description: plan.description ?? '',
    details: plan.details ?? '',
    priceRupees: String(paiseToRupees(plan.price_paise)),
    peopleAllowed: String(plan.people_allowed),
    maxPeople: String(plan.max_people_allowed),
    extraGuestRupees: String(paiseToRupees(plan.extra_guest_paise)),
    advanceRupees: String(paiseToRupees(plan.advance_paise)),
    giveDiscount: plan.give_discount,
    maxDiscountRupees: String(paiseToRupees(plan.max_discount_paise)),
  });
  const updatePlan = useUpdatePlan(locationId, plan.id);

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]): void =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const onSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    // Send the full editable set; the server treats this as a partial update and
    // only the fields present are applied (all are present here).
    const body: PlanUpdateBody = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      details: form.details.trim() || null,
      price_paise: rupeesToPaise(Number(form.priceRupees)),
      people_allowed: Number(form.peopleAllowed),
      max_people_allowed: Number(form.maxPeople),
      extra_guest_paise: rupeesToPaise(Number(form.extraGuestRupees)),
      advance_paise: rupeesToPaise(Number(form.advanceRupees)),
      give_discount: form.giveDiscount,
      max_discount_paise: rupeesToPaise(Number(form.maxDiscountRupees)),
    };
    updatePlan.mutate(body, { onSuccess: onDone });
  };

  const field = 'rounded border border-gray-300 px-2 py-1 text-sm';
  const label = 'flex flex-col gap-1 text-xs text-gray-600';

  return (
    <form
      onSubmit={onSubmit}
      className="mt-3 space-y-3 rounded border border-gray-200 bg-gray-50 p-3"
    >
      <h3 className="text-sm font-semibold text-gray-800">Edit plan</h3>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <label className={label}>
          Title
          <input
            className={field}
            required
            value={form.title}
            onChange={(e) => set('title', e.target.value)}
          />
        </label>
        <label className={label}>
          Price (₹)
          <input
            className={field}
            type="number"
            min={0}
            step="0.01"
            required
            value={form.priceRupees}
            onChange={(e) => set('priceRupees', e.target.value)}
          />
        </label>
        <label className={label}>
          People allowed
          <input
            className={field}
            type="number"
            min={0}
            required
            value={form.peopleAllowed}
            onChange={(e) => set('peopleAllowed', e.target.value)}
          />
        </label>
        <label className={label}>
          Max people
          <input
            className={field}
            type="number"
            min={0}
            required
            value={form.maxPeople}
            onChange={(e) => set('maxPeople', e.target.value)}
          />
        </label>
        <label className={label}>
          Extra guest (₹)
          <input
            className={field}
            type="number"
            min={0}
            step="0.01"
            value={form.extraGuestRupees}
            onChange={(e) => set('extraGuestRupees', e.target.value)}
          />
        </label>
        <label className={label}>
          Advance (₹)
          <input
            className={field}
            type="number"
            min={0}
            step="0.01"
            value={form.advanceRupees}
            onChange={(e) => set('advanceRupees', e.target.value)}
          />
        </label>
        <label className={label}>
          Max discount (₹)
          <input
            className={field}
            type="number"
            min={0}
            step="0.01"
            value={form.maxDiscountRupees}
            onChange={(e) => set('maxDiscountRupees', e.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-gray-700">
          <input
            type="checkbox"
            checked={form.giveDiscount}
            onChange={(e) => set('giveDiscount', e.target.checked)}
          />
          Allow discount
        </label>
      </div>
      <label className={label}>
        Description
        <textarea
          className={field}
          rows={2}
          value={form.description}
          onChange={(e) => set('description', e.target.value)}
        />
      </label>
      <label className={label}>
        Details
        <textarea
          className={field}
          rows={2}
          value={form.details}
          onChange={(e) => set('details', e.target.value)}
        />
      </label>
      {updatePlan.isError && (
        <p className="text-xs text-red-600">Could not update plan.</p>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={updatePlan.isPending}
          className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {updatePlan.isPending ? 'Saving…' : 'Save changes'}
        </button>
        <button
          type="button"
          onClick={onDone}
          className="rounded px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
