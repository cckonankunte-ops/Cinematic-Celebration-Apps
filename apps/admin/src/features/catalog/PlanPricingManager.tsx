/**
 * Per-plan, per-duration pricing (R11). Lists a plan's price rows and offers a
 * compact create form: duration (minutes) + base price + advance, entered in
 * rupees and sent as integer paise. People allowance / extra-guest stay on the
 * plan (not per duration). Deactivate is a soft-delete.
 */

import { useState } from 'react';

import { formatRupees, rupeesToPaise } from '@/lib/money';
import {
  useCreatePlanPricing,
  useDeactivatePlanPricing,
  usePlanPricing,
} from './queries';
import type { PlanPricingCreateBody } from './types';

const DURATION_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 60, label: '1 hour' },
  { value: 90, label: '1.5 hours' },
  { value: 120, label: '2 hours' },
  { value: 180, label: '3 hours' },
];

export function PlanPricingManager({ planId }: { planId: number }): JSX.Element {
  const pricing = usePlanPricing(planId);
  const createPricing = useCreatePlanPricing(planId);
  const deactivatePricing = useDeactivatePlanPricing(planId);

  const [duration, setDuration] = useState(60);
  const [priceRupees, setPriceRupees] = useState('');
  const [advanceRupees, setAdvanceRupees] = useState('');

  const onCreate = (e: React.FormEvent): void => {
    e.preventDefault();
    const body: PlanPricingCreateBody = {
      plan_id: planId,
      duration_minutes: duration,
      price_paise: rupeesToPaise(Number(priceRupees)),
      advance_paise: advanceRupees.trim() === '' ? 0 : rupeesToPaise(Number(advanceRupees)),
      effective_from: '2020-01-01',
    };
    createPricing.mutate(body, {
      onSuccess: () => {
        setPriceRupees('');
        setAdvanceRupees('');
      },
    });
  };

  const field = 'rounded border border-gray-300 px-2 py-1 text-sm';

  return (
    <div className="mt-2 space-y-2 border-t border-gray-100 pt-2">
      <h4 className="text-xs font-semibold text-gray-600">Pricing by duration</h4>
      {pricing.data && pricing.data.length === 0 && (
        <p className="text-xs text-gray-500">
          No per-duration prices yet (falls back to the plan price).
        </p>
      )}
      <ul className="space-y-1">
        {pricing.data?.map((p) => (
          <li
            key={p.id}
            className="flex items-center justify-between rounded border border-gray-200 px-2 py-1 text-xs"
          >
            <span>
              {p.duration_minutes} min · {formatRupees(p.price_paise)}
              <span className="text-gray-500">
                {' '}
                · advance {formatRupees(p.advance_paise)}
              </span>
              {!p.is_active && <span className="ml-2 text-gray-400">(inactive)</span>}
            </span>
            <button
              type="button"
              disabled={!p.is_active || deactivatePricing.isPending}
              onClick={() => deactivatePricing.mutate(p.id)}
              className="rounded border border-red-300 px-1.5 py-0.5 text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              Deactivate
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={onCreate} className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-gray-600">
          Duration
          <select
            aria-label="Pricing duration"
            className={`${field} ml-1`}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
          >
            {DURATION_OPTIONS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
        <input
          className={field}
          type="number"
          min={0}
          step="0.01"
          placeholder="Price ₹ (e.g. 799)"
          required
          value={priceRupees}
          onChange={(e) => setPriceRupees(e.target.value)}
        />
        <input
          className={field}
          type="number"
          min={0}
          step="0.01"
          placeholder="Advance ₹ (e.g. 500)"
          value={advanceRupees}
          onChange={(e) => setAdvanceRupees(e.target.value)}
        />
        <button
          type="submit"
          disabled={createPricing.isPending}
          className="rounded bg-gray-900 px-2 py-1 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          Add price
        </button>
      </form>
      {createPricing.isError && (
        <p className="text-xs text-red-600">
          Could not add price (one active price per duration).
        </p>
      )}
    </div>
  );
}
