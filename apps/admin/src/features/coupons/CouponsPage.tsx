/**
 * Admin-only coupon management for the selected location. Lists existing
 * coupons and offers a create/edit form (type, value, cap, percentage base +
 * component checkboxes, validity dates, active, one-time, usage limits). The
 * server validates and computes discounts at booking time; this screen only
 * authors the rule. Money is entered in rupees and sent as paise.
 */

import { useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { ApiError } from '@/api/client';
import { formatRupees } from '@/lib/money';
import { useAuth } from '@/features/auth/useAuth';
import { useLocation } from '@/features/location/useLocation';
import {
  useCoupons,
  useCreateCoupon,
  useUpdateCoupon,
  type CouponComponents,
  type CouponCreateBody,
  type CouponRead,
} from './coupon-queries';
import { couponFormSchema, type CouponFormInput } from './coupon-schema';

const inputClass =
  'w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none';

const COMPONENT_KEYS: (keyof CouponComponents)[] = [
  'plan',
  'extra_guest',
  'decor',
  'combos',
  'cake',
  'food',
];

const EMPTY_COMPONENTS: CouponComponents = {
  plan: false,
  extra_guest: false,
  decor: false,
  combos: false,
  cake: false,
  food: false,
};

/** Default form values for a brand-new coupon. */
function emptyForm(): CouponFormInput {
  return {
    code: '',
    type: 'flat',
    value: 0,
    cap_paise: undefined,
    percentage_base: 'total',
    components: { ...EMPTY_COMPONENTS },
    effective_from: '',
    effective_to: '',
    is_active: true,
    one_time: false,
    total_usage_limit: undefined,
    per_customer_limit: undefined,
    min_order_paise: undefined,
  };
}

/** Map a loaded coupon into form values for editing. */
function toForm(coupon: CouponRead): CouponFormInput {
  return {
    code: coupon.code,
    type: coupon.type,
    value: coupon.value,
    cap_paise: coupon.cap_paise ?? undefined,
    percentage_base: coupon.percentage_base,
    components: coupon.components ?? { ...EMPTY_COMPONENTS },
    effective_from: coupon.effective_from ?? '',
    effective_to: coupon.effective_to ?? '',
    is_active: coupon.is_active,
    one_time: coupon.one_time,
    total_usage_limit: coupon.total_usage_limit ?? undefined,
    per_customer_limit: coupon.per_customer_limit ?? undefined,
    min_order_paise: coupon.min_order_paise ?? undefined,
  };
}

export function CouponsPage(): JSX.Element {
  const { user } = useAuth();
  const { selectedLocationId } = useLocation();
  const [editing, setEditing] = useState<CouponRead | null>(null);

  const coupons = useCoupons(selectedLocationId);

  if (user?.role !== 'admin') {
    return <p className="text-sm text-red-600">Coupons are available to admins only.</p>;
  }

  if (selectedLocationId === null) {
    return <p className="text-sm text-gray-500">Select a location first.</p>;
  }

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900">Coupons</h1>

      <div className="space-y-2">
        {coupons.isPending && <p className="text-sm text-gray-500">Loading coupons…</p>}
        {coupons.isError && <p className="text-sm text-red-600">Failed to load coupons.</p>}
        {coupons.data && coupons.data.length === 0 && (
          <p className="text-sm text-gray-500">No coupons yet.</p>
        )}
        <ul className="space-y-2">
          {coupons.data?.map((c) => (
            <li
              key={c.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded border border-gray-200 bg-white p-3 text-sm"
            >
              <span>
                <span className="font-mono font-medium text-gray-900">{c.code}</span>{' '}
                <span className="text-gray-500">
                  ·{' '}
                  {c.type === 'flat'
                    ? formatRupees(c.value)
                    : `${c.value}% (${c.percentage_base})`}
                </span>
                {!c.is_active && <span className="ml-2 text-xs text-gray-500">(inactive)</span>}
              </span>
              <button
                type="button"
                onClick={() => setEditing(c)}
                className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
              >
                Edit
              </button>
            </li>
          ))}
        </ul>
      </div>

      <CouponForm
        key={editing?.id ?? 'new'}
        locationId={selectedLocationId}
        editing={editing}
        onDone={() => setEditing(null)}
      />
    </section>
  );
}

interface CouponFormProps {
  locationId: number;
  editing: CouponRead | null;
  onDone: () => void;
}

function CouponForm({ locationId, editing, onDone }: CouponFormProps): JSX.Element {
  const createCoupon = useCreateCoupon();
  const updateCoupon = useUpdateCoupon(editing?.id ?? 0);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    formState: { errors },
  } = useForm<CouponFormInput>({
    resolver: zodResolver(couponFormSchema),
    defaultValues: editing ? toForm(editing) : emptyForm(),
  });

  const type = watch('type');
  const percentageBase = watch('percentage_base');
  const isSubmitting = createCoupon.isPending || updateCoupon.isPending;

  const submit = handleSubmit(async (values) => {
    setServerError(null);
    // Normalise optional/defaulted fields so the body matches the API shape
    // regardless of react-hook-form's input-vs-output typing.
    const toNullableNumber = (v: number | undefined): number | null =>
      typeof v === 'number' && Number.isFinite(v) ? v : null;
    const toNullableDate = (v: string | undefined): string | null =>
      v === undefined || v === '' ? null : v;
    const components: CouponComponents = {
      plan: Boolean(values.components?.plan),
      extra_guest: Boolean(values.components?.extra_guest),
      decor: Boolean(values.components?.decor),
      combos: Boolean(values.components?.combos),
      cake: Boolean(values.components?.cake),
      food: Boolean(values.components?.food),
    };

    // Shared authoring fields (everything except the immutable location scope).
    const fields: Omit<CouponCreateBody, 'location_id'> = {
      code: values.code,
      type: values.type,
      value: values.value,
      cap_paise: toNullableNumber(values.cap_paise),
      percentage_base: values.percentage_base,
      components:
        values.type === 'percentage' && values.percentage_base === 'selected_components'
          ? components
          : null,
      effective_from: toNullableDate(values.effective_from),
      effective_to: toNullableDate(values.effective_to),
      is_active: Boolean(values.is_active),
      one_time: Boolean(values.one_time),
      total_usage_limit: toNullableNumber(values.total_usage_limit),
      per_customer_limit: toNullableNumber(values.per_customer_limit),
      min_order_paise: toNullableNumber(values.min_order_paise),
    };
    try {
      if (editing) {
        await updateCoupon.mutateAsync(fields);
      } else {
        await createCoupon.mutateAsync({ location_id: locationId, ...fields });
        reset(emptyForm());
      }
      onDone();
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : 'Failed to save coupon.');
    }
  });

  return (
    <form onSubmit={submit} className="space-y-4 rounded border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-800">
        {editing ? `Edit coupon ${editing.code}` : 'New coupon'}
      </h2>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Code</span>
          <input type="text" className={inputClass} {...register('code')} />
          {errors.code && <p className="text-xs text-red-600">{errors.code.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Type</span>
          <select className={inputClass} {...register('type')}>
            <option value="flat">Flat (paise)</option>
            <option value="percentage">Percentage</option>
          </select>
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">
            {type === 'percentage' ? 'Value (%)' : 'Value (paise)'}
          </span>
          <input
            type="number"
            min={0}
            className={inputClass}
            {...register('value', { valueAsNumber: true })}
          />
          {errors.value && <p className="text-xs text-red-600">{errors.value.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Cap (paise, optional)</span>
          <input
            type="number"
            min={0}
            className={inputClass}
            {...register('cap_paise', { valueAsNumber: true })}
          />
        </label>
      </div>

      {type === 'percentage' && (
        <div className="space-y-3 rounded border border-gray-100 bg-gray-50 p-3">
          <label className="space-y-1 text-sm">
            <span className="font-medium text-gray-700">Percentage base</span>
            <select className={inputClass} {...register('percentage_base')}>
              <option value="total">Total</option>
              <option value="selected_components">Selected components</option>
            </select>
          </label>

          {percentageBase === 'selected_components' && (
            <Controller
              control={control}
              name="components"
              render={({ field }) => {
                const value = field.value ?? { ...EMPTY_COMPONENTS };
                return (
                  <div className="flex flex-wrap gap-3 text-sm">
                    {COMPONENT_KEYS.map((key) => (
                      <label key={key} className="flex items-center gap-1.5">
                        <input
                          type="checkbox"
                          checked={value[key]}
                          onChange={(e) =>
                            field.onChange({ ...value, [key]: e.target.checked })
                          }
                        />
                        {key.replace('_', ' ')}
                      </label>
                    ))}
                  </div>
                );
              }}
            />
          )}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Effective from (optional)</span>
          <input type="date" className={inputClass} {...register('effective_from')} />
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Effective to (optional)</span>
          <input type="date" className={inputClass} {...register('effective_to')} />
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Total usage limit (optional)</span>
          <input
            type="number"
            min={0}
            className={inputClass}
            {...register('total_usage_limit', { valueAsNumber: true })}
          />
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Per-customer limit (optional)</span>
          <input
            type="number"
            min={0}
            className={inputClass}
            {...register('per_customer_limit', { valueAsNumber: true })}
          />
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">
            Min order (paise, optional{' '}
            {watch('min_order_paise')
              ? `· ${formatRupees(Number(watch('min_order_paise')) || 0)}`
              : ''}
            )
          </span>
          <input
            type="number"
            min={0}
            className={inputClass}
            {...register('min_order_paise', { valueAsNumber: true })}
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" {...register('is_active')} />
          Active
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" {...register('one_time')} />
          One-time use
        </label>
      </div>

      {serverError && <p className="text-sm text-red-600">{serverError}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-60"
        >
          {isSubmitting ? 'Saving…' : editing ? 'Save coupon' : 'Create coupon'}
        </button>
        {editing && (
          <button
            type="button"
            onClick={onDone}
            className="rounded px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
