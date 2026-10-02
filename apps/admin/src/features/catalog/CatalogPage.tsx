/**
 * Minimal admin catalog management (admin-only). Lists plans for the selected
 * location with a soft-delete (deactivate) action and an inline gallery upload,
 * plus a compact create-plan form and read-only add-on lists (cakes, decor,
 * combos) with deactivate. Money is entered in rupees and sent as paise.
 *
 * This is a deliberately small management surface — full editing is out of
 * scope for Phase 1; it covers create, deactivate, and gallery upload.
 */

import { useState } from 'react';

import { todayIsoInIST } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { useAuth } from '@/features/auth/useAuth';
import { useLocation } from '@/features/location/useLocation';
import { CreatePlanForm } from './CreatePlanForm';
import { GalleryUpload } from './GalleryUpload';
import {
  useCakes,
  useCombos,
  useDeactivateCake,
  useDeactivatePlan,
  usePlans,
  useSpecialDecor,
} from './queries';
import type { NamedAddonAdminRead } from './types';

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

function AddonList({
  title,
  rows,
}: {
  title: string;
  rows: NamedAddonAdminRead[] | undefined;
}): JSX.Element {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
      {rows && rows.length === 0 && <p className="text-xs text-gray-500">None.</p>}
      <ul className="space-y-1">
        {rows?.map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between rounded border border-gray-200 bg-white px-3 py-2 text-sm"
          >
            <span>
              {r.name} <span className="text-gray-500">· {formatRupees(r.price_paise)}</span>
            </span>
            <ActiveTag active={r.is_active} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CatalogPage(): JSX.Element {
  const { user } = useAuth();
  const { selectedLocationId } = useLocation();
  const [expandedPlanId, setExpandedPlanId] = useState<number | null>(null);

  const plans = usePlans(selectedLocationId);
  const cakes = useCakes(selectedLocationId);
  const decor = useSpecialDecor(selectedLocationId);
  const combos = useCombos(selectedLocationId);
  const deactivatePlan = useDeactivatePlan(selectedLocationId);
  const deactivateCake = useDeactivateCake(selectedLocationId);

  if (user?.role !== 'admin') {
    return <p className="text-sm text-red-600">Catalog management is available to admins only.</p>;
  }

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Catalog</h1>

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
                    onClick={() =>
                      setExpandedPlanId((id) => (id === plan.id ? null : plan.id))
                    }
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
              {expandedPlanId === plan.id && <GalleryUpload planId={plan.id} />}
            </li>
          ))}
        </ul>
      </div>

      <CreatePlanForm
        locationId={selectedLocationId}
        defaultEffectiveFrom={todayIsoInIST()}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-gray-700">Cakes</h3>
          {cakes.data && cakes.data.length === 0 && (
            <p className="text-xs text-gray-500">None.</p>
          )}
          <ul className="space-y-1">
            {cakes.data?.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded border border-gray-200 bg-white px-3 py-2 text-sm"
              >
                <span>
                  {c.description}{' '}
                  <span className="text-gray-500">· {formatRupees(c.price_paise)}</span>
                </span>
                <div className="flex items-center gap-2">
                  <ActiveTag active={c.is_active} />
                  <button
                    type="button"
                    disabled={!c.is_active || deactivateCake.isPending}
                    onClick={() => deactivateCake.mutate(c.id)}
                    className="rounded border border-red-300 px-1.5 py-0.5 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    Deactivate
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <AddonList title="Special decor" rows={decor.data} />
        <AddonList title="Combos" rows={combos.data} />
      </div>
    </section>
  );
}
