/**
 * Admin catalog management (admin-only). Lists plans for the selected location
 * with deactivate + inline gallery/slots/pricing panels and a create-plan form,
 * plus full add-on management (cakes, decor, combos) via AddonManagers:
 * create/edit with image upload, activate/deactivate, and a shared show-inactive
 * toggle. Money is entered in rupees and sent as paise.
 */

import { useState } from 'react';

import { todayIsoInIST } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { useAuth } from '@/features/auth/useAuth';
import { useLocation } from '@/features/location/useLocation';
import { AddonManagers } from './AddonManagers';
import { CreatePlanForm } from './CreatePlanForm';
import { GalleryUpload } from './GalleryUpload';
import { LocationSettings } from './LocationSettings';
import { PlanPricingManager } from './PlanPricingManager';
import { SlotManager } from './SlotManager';
import { useDeactivatePlan, usePlans } from './queries';

function ActiveTag({ active }: { active: boolean }): JSX.Element {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs ${
        active ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-600'
      }`}
    >
      {active ? 'active' : 'inactive'}
    </span>
  );
}

export function CatalogPage(): JSX.Element {
  const { user } = useAuth();
  const { selectedLocationId } = useLocation();
  // Which expandable panel is open for a plan: gallery | slots | pricing.
  const [expanded, setExpanded] = useState<{
    planId: number;
    panel: 'gallery' | 'slots' | 'pricing';
  } | null>(null);

  const togglePanel = (
    planId: number,
    panel: 'gallery' | 'slots' | 'pricing',
  ): void =>
    setExpanded((cur) =>
      cur && cur.planId === planId && cur.panel === panel
        ? null
        : { planId, panel },
    );

  const plans = usePlans(selectedLocationId);
  const deactivatePlan = useDeactivatePlan(selectedLocationId);

  if (user?.role !== 'admin') {
    return <p className="text-sm text-red-600">Catalog management is available to admins only.</p>;
  }

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Catalog</h1>

      <LocationSettings />

      <div className="space-y-2">
        <h2 className="text-base font-semibold text-gray-800">Plans</h2>
        {plans.isLoading && <p className="text-sm text-gray-500">Loading plans…</p>}
        {plans.isError && <p className="text-sm text-red-600">Failed to load plans.</p>}
        <ul className="space-y-2">
          {plans.data?.map((plan) => (
            <li key={plan.id} className="rounded border border-gray-200 bg-white p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-gray-900">
                  {plan.title}{' '}
                  <span className="text-gray-500">· {formatRupees(plan.price_paise)}</span>
                </span>
                <div className="flex items-center gap-2">
                  <ActiveTag active={plan.is_active} />
                  <button
                    type="button"
                    onClick={() => togglePanel(plan.id, 'slots')}
                    className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
                  >
                    Slots
                  </button>
                  <button
                    type="button"
                    onClick={() => togglePanel(plan.id, 'pricing')}
                    className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
                  >
                    Pricing
                  </button>
                  <button
                    type="button"
                    onClick={() => togglePanel(plan.id, 'gallery')}
                    className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
                  >
                    Gallery
                  </button>
                  <button
                    type="button"
                    disabled={!plan.is_active || deactivatePlan.isPending}
                    onClick={() => deactivatePlan.mutate(plan.id)}
                    className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    Deactivate
                  </button>
                </div>
              </div>
              {expanded?.planId === plan.id && expanded.panel === 'gallery' && (
                <GalleryUpload planId={plan.id} />
              )}
              {expanded?.planId === plan.id && expanded.panel === 'slots' && (
                <SlotManager planId={plan.id} />
              )}
              {expanded?.planId === plan.id && expanded.panel === 'pricing' && (
                <PlanPricingManager planId={plan.id} />
              )}
            </li>
          ))}
        </ul>
      </div>

      <CreatePlanForm
        locationId={selectedLocationId}
        defaultEffectiveFrom={todayIsoInIST()}
      />

      <AddonManagers locationId={selectedLocationId} />
    </section>
  );
}
