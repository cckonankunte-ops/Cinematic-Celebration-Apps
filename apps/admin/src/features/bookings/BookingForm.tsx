/**
 * Admin booking form used for BOTH create and edit — one identical field set so
 * the two flows stay in parity. react-hook-form + zod (`bookingCreateSchema`)
 * with cascading selects: picking a plan loads its slots; add-ons come from the
 * location catalog. Special decor carries per-item quantities
 * (`special_decor: [{id, quantity}]`); combos are `{id}` selections. A live
 * summary is driven by the server preview endpoint (the server is authoritative
 * on all money); the priced fields are watched and debounced before each
 * preview call.
 */

import { useEffect, useRef, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { ApiError } from '@/api/client';
import { todayIsoInIST } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { useDebounce } from '@/hooks/useDebounce';
import {
  bookingCreateSchema,
  type BookingCreateInput,
  type BookingCreateValues,
} from './booking-schema';
import { usePreviewBooking, type AdminPreviewBody } from './booking-queries';
import {
  useCakes,
  useCombos,
  useOccasions,
  usePlans,
  useSlotAvailability,
  useSpecialDecor,
} from './catalog-queries';
import type { PriceBreakdownRead } from './types';

interface BookingFormProps {
  locationId: number;
  /** Pre-fill values (edit mode). Merged over the create defaults. */
  initial?: Partial<BookingCreateInput>;
  /** Present in edit mode (preview self-exclusion). */
  bookingId?: number;
  submitLabel: string;
  onSubmit: (values: BookingCreateValues) => void;
  isSubmitting: boolean;
  serverError: string | null;
}

const inputClass =
  'w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none';

/** Cake weight options: value is a count of half-kilos (1 = 0.5 kg … 6 = 3 kg). */
const CAKE_WEIGHT_OPTIONS = [1, 2, 3, 4, 5, 6] as const;

function cakeWeightLabel(halfKg: number): string {
  return `${halfKg / 2} kg`;
}

export function BookingForm({
  locationId,
  initial,
  bookingId,
  submitLabel,
  onSubmit,
  isSubmitting,
  serverError,
}: BookingFormProps): JSX.Element {
  const isEdit = bookingId !== undefined;

  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors },
  } = useForm<BookingCreateInput>({
    resolver: zodResolver(bookingCreateSchema),
    defaultValues: {
      location_id: locationId,
      booking_date: todayIsoInIST(),
      people: 1,
      cake_weight_half_kg: 1,
      special_decor: [],
      combos: [],
      discount_paise: 0,
      food_paise: 0,
      other_paise: 0,
      cleaning_paise: 0,
      // Edit pre-fill wins over the create defaults above.
      ...initial,
    },
  });

  const rawPlanId = watch('plan_id');
  // valueAsNumber on an empty <select> yields NaN, not null. Normalize to null
  // so the slots query stays disabled until a real plan is chosen.
  const planId = Number.isFinite(rawPlanId) ? rawPlanId : null;
  const bookingDate = watch('booking_date');
  // In edit mode the booking is pinned to its own location; in create mode the
  // selected location drives availability. `locationId` already reflects this.
  const currentSlotId = watch('slot_id');

  const plans = usePlans(locationId);
  // Availability is scoped to plan + location + date so held slots are flagged
  // and rendered greyed-out / non-selectable.
  const slots = useSlotAvailability(planId, locationId, bookingDate ?? null);
  const cakes = useCakes(locationId);
  const decor = useSpecialDecor(locationId);
  const combos = useCombos(locationId);
  const occasions = useOccasions(locationId);

  // Keep the submitted location_id in sync with the selected location and clear
  // every location-scoped selection when the location changes. Otherwise a
  // stale plan/slot/cake/decor from a previously viewed location gets submitted
  // against the new location_id, which the server rejects. Only applies in
  // create mode: edit mode is pinned to the booking's own location and must not
  // wipe the pre-filled selections.
  useEffect(() => {
    if (isEdit) {
      return;
    }
    setValue('location_id', locationId);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- RHF reset to empty
    const clear = undefined as any;
    setValue('plan_id', clear);
    setValue('slot_id', clear);
    setValue('cake_id', clear);
    setValue('occasion_id', clear);
    setValue('special_decor', []);
    setValue('combos', []);
  }, [locationId, isEdit, setValue]);

  // Reset the slot when the plan changes so a stale slot can't be submitted. In
  // edit mode we must NOT clobber the pre-filled slot on the very first render,
  // so skip the first run there via a ref.
  const skipFirstSlotClear = useRef<boolean>(isEdit);
  useEffect(() => {
    if (skipFirstSlotClear.current) {
      skipFirstSlotClear.current = false;
      return;
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- RHF reset to empty
    setValue('slot_id', undefined as any);
  }, [planId, setValue]);

  // --- Live preview summary (server-authoritative) -------------------------
  const preview = usePreviewBooking();
  const [breakdown, setBreakdown] = useState<PriceBreakdownRead | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const watched = watch();
  // Serialise the priced fields and debounce so the preview fires ~400ms after
  // the last change rather than on every keystroke.
  const previewKey = useDebounce(
    JSON.stringify({
      plan_id: watched.plan_id,
      slot_id: watched.slot_id,
      booking_date: watched.booking_date,
      people: watched.people,
      cake_id: watched.cake_id,
      cake_weight_half_kg: watched.cake_weight_half_kg,
      occasion_id: watched.occasion_id,
      led_name: watched.led_name,
      coupon_code: watched.coupon_code,
      discount_paise: watched.discount_paise,
      food_paise: watched.food_paise,
      other_paise: watched.other_paise,
      cleaning_paise: watched.cleaning_paise,
      special_decor: watched.special_decor,
      combos: watched.combos,
    }),
    400,
  );

  const previewMutate = preview.mutate;
  useEffect(() => {
    const parsed = JSON.parse(previewKey) as BookingCreateInput;
    const planIdNum = Number.isFinite(parsed.plan_id) ? (parsed.plan_id as number) : null;
    const slotIdNum = Number.isFinite(parsed.slot_id) ? (parsed.slot_id as number) : null;
    const bookingDate = parsed.booking_date;
    if (!planIdNum || !slotIdNum || !bookingDate) {
      setBreakdown(null);
      setPreviewError(null);
      return;
    }

    const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
    const optionalId = (v: unknown): number | undefined =>
      typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : undefined;
    const optionalText = (v: unknown): string | undefined =>
      typeof v === 'string' && v.trim().length > 0 ? v : undefined;

    const body: AdminPreviewBody = {
      location_id: locationId,
      plan_id: planIdNum,
      slot_id: slotIdNum,
      booking_date: bookingDate,
      people: num(parsed.people) || 1,
      cake_id: optionalId(parsed.cake_id),
      cake_weight_half_kg: num(parsed.cake_weight_half_kg) || 1,
      special_decor: (parsed.special_decor ?? []).map((d) => ({
        id: d.id,
        quantity: d.quantity,
      })),
      combos: (parsed.combos ?? []).map((c) => ({ id: c.id })),
      led_name: optionalText(parsed.led_name),
      occasion_id: optionalId(parsed.occasion_id),
      coupon_code: optionalText(parsed.coupon_code),
      booking_id: bookingId,
      discount_paise: num(parsed.discount_paise),
      food_paise: num(parsed.food_paise),
      other_paise: num(parsed.other_paise),
      cleaning_paise: num(parsed.cleaning_paise),
    };

    previewMutate(body, {
      onSuccess: (data) => {
        setBreakdown(data);
        setPreviewError(null);
      },
      onError: (err) => {
        setPreviewError(
          err instanceof ApiError ? err.message : 'Could not compute a live summary.',
        );
      },
    });
  }, [previewKey, locationId, bookingId, previewMutate]);

  const submit = handleSubmit((values) => onSubmit(values as BookingCreateValues));

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Plan</span>
          <select
            aria-label="Plan"
            className={inputClass}
            {...register('plan_id', { valueAsNumber: true })}
          >
            <option value="">Select a plan…</option>
            {plans.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
          {errors.plan_id && <p className="text-xs text-red-600">{errors.plan_id.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Slot</span>
          <select
            aria-label="Slot"
            className={inputClass}
            disabled={!planId}
            {...register('slot_id', { valueAsNumber: true })}
          >
            <option value="">Select a slot…</option>
            {slots.data?.map((s) => {
              // A held slot is non-selectable, EXCEPT the booking's own slot in
              // edit mode (it holds itself) so the pre-filled value stays valid.
              const isCurrent = currentSlotId === s.id;
              const blocked = !s.is_available && !isCurrent;
              return (
                <option key={s.id} value={s.id} disabled={blocked}>
                  {s.description}
                  {blocked ? ' — already booked' : ''}
                </option>
              );
            })}
          </select>
          {errors.slot_id && <p className="text-xs text-red-600">{errors.slot_id.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Date</span>
          <input type="date" className={inputClass} {...register('booking_date')} />
          {errors.booking_date && (
            <p className="text-xs text-red-600">{errors.booking_date.message}</p>
          )}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">People</span>
          <input
            type="number"
            min={1}
            className={inputClass}
            {...register('people', { valueAsNumber: true })}
          />
          {errors.people && <p className="text-xs text-red-600">{errors.people.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Occasion</span>
          <select className={inputClass} {...register('occasion_id', { valueAsNumber: true })}>
            <option value="">None</option>
            {occasions.data?.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Cake</span>
          <select className={inputClass} {...register('cake_id', { valueAsNumber: true })}>
            <option value="">None</option>
            {cakes.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Cake weight</span>
          <select
            className={inputClass}
            {...register('cake_weight_half_kg', { valueAsNumber: true })}
          >
            {CAKE_WEIGHT_OPTIONS.map((w) => (
              <option key={w} value={w}>
                {cakeWeightLabel(w)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Special decor</span>
          <Controller
            control={control}
            name="special_decor"
            render={({ field }) => {
              const selections = field.value ?? [];
              return (
                <div className="space-y-1">
                  {decor.data?.map((d) => {
                    const existing = selections.find((s) => s.id === d.id);
                    const checked = existing !== undefined;
                    return (
                      <div key={d.id} className="flex items-center gap-2">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                field.onChange([...selections, { id: d.id, quantity: 1 }]);
                              } else {
                                field.onChange(selections.filter((s) => s.id !== d.id));
                              }
                            }}
                          />
                          {d.name}
                        </label>
                        {checked && (
                          <input
                            type="number"
                            min={1}
                            aria-label={`${d.name} quantity`}
                            className="w-16 rounded border border-gray-300 px-2 py-1 text-sm"
                            value={existing?.quantity ?? 1}
                            onChange={(e) => {
                              const qty = Number(e.target.value);
                              field.onChange(
                                selections.map((s) =>
                                  s.id === d.id
                                    ? {
                                        id: s.id,
                                        quantity:
                                          Number.isFinite(qty) && qty >= 1 ? qty : 1,
                                      }
                                    : s,
                                ),
                              );
                            }}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            }}
          />
        </div>

        <div className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Combos</span>
          <Controller
            control={control}
            name="combos"
            render={({ field }) => {
              const selections = field.value ?? [];
              return (
                <div className="space-y-1">
                  {combos.data?.map((c) => {
                    const checked = selections.some((s) => s.id === c.id);
                    return (
                      <label key={c.id} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              field.onChange([...selections, { id: c.id }]);
                            } else {
                              field.onChange(selections.filter((s) => s.id !== c.id));
                            }
                          }}
                        />
                        {c.name}
                      </label>
                    );
                  })}
                </div>
              );
            }}
          />
        </div>
      </fieldset>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">LED name</span>
          <input type="text" className={inputClass} {...register('led_name')} />
          <span className="text-xs text-gray-500">₹40 per letter</span>
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Coupon code</span>
          <input type="text" className={inputClass} {...register('coupon_code')} />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Booking name</span>
          <input
            type="text"
            aria-label="Booking name"
            className={inputClass}
            {...register('booking_name')}
          />
          {errors.booking_name && (
            <p className="text-xs text-red-600">{errors.booking_name.message}</p>
          )}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Email (optional)</span>
          <input
            type="text"
            aria-label="Email"
            className={inputClass}
            {...register('email')}
          />
          {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Phone</span>
          <input
            type="text"
            aria-label="Phone"
            className={inputClass}
            {...register('phone')}
          />
          {errors.phone && <p className="text-xs text-red-600">{errors.phone.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Special person name</span>
          <input type="text" className={inputClass} {...register('special_person_name')} />
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Name on cake</span>
          <input type="text" className={inputClass} {...register('name_on_cake')} />
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Message</span>
          <input type="text" className={inputClass} {...register('message')} />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {(['discount_paise', 'food_paise', 'other_paise', 'cleaning_paise'] as const).map(
          (name) => (
            <label key={name} className="space-y-1 text-sm">
              <span className="font-medium text-gray-700">
                {name.replace('_paise', '')} (paise)
              </span>
              <input
                type="number"
                min={0}
                className={inputClass}
                {...register(name, { valueAsNumber: true })}
              />
            </label>
          ),
        )}
      </div>

      {!isEdit && (
        <fieldset className="grid gap-4 md:grid-cols-2">
          <legend className="text-sm font-medium text-gray-700">
            Advance paid now (optional)
          </legend>
          <label className="space-y-1 text-sm">
            <span className="font-medium text-gray-700">Advance (₹)</span>
            <input
              type="number"
              step="0.01"
              min={0}
              aria-label="Advance in rupees"
              placeholder="Advance in ₹, optional (e.g. 500)"
              className={inputClass}
              {...register('advance_rupees', { valueAsNumber: true })}
            />
          </label>

          <label className="space-y-1 text-sm">
            <span className="font-medium text-gray-700">Method</span>
            <select
              aria-label="Advance method"
              className={inputClass}
              {...register('advance_method')}
            >
              <option value="cash">Cash</option>
              <option value="upi">UPI</option>
              <option value="card">Card</option>
              <option value="other">Other</option>
            </select>
          </label>
        </fieldset>
      )}

      <PreviewSummary breakdown={breakdown} error={previewError} />

      {serverError && <p className="text-sm text-red-600">{serverError}</p>}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-60"
      >
        {isSubmitting ? 'Saving…' : submitLabel}
      </button>
    </form>
  );
}

interface PreviewSummaryProps {
  breakdown: PriceBreakdownRead | null;
  error: string | null;
}

/**
 * Server-computed price summary. Every add-on (including each combo) is its own
 * row; the coupon is shown as a distinct line when it discounts anything. The
 * total is authoritative — this panel never does any price math itself.
 */
function PreviewSummary({ breakdown, error }: PreviewSummaryProps): JSX.Element | null {
  if (error) {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-3 text-sm">
        <p className="font-medium text-gray-700">Summary</p>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  if (breakdown === null) {
    return null;
  }

  return (
    <div className="space-y-1 rounded border border-gray-200 bg-gray-50 p-3 text-sm">
      <p className="font-medium text-gray-700">Summary</p>

      <div className="flex justify-between">
        <span>Plan</span>
        <span>{formatRupees(breakdown.plan_price_paise)}</span>
      </div>

      {breakdown.extra_guest_paise > 0 && (
        <div className="flex justify-between">
          <span>Extra guests</span>
          <span>{formatRupees(breakdown.extra_guest_paise)}</span>
        </div>
      )}

      {breakdown.addon_lines.map((line, idx) => {
        const cakeUpgrade = line.cake_upgrade_paise ?? 0;
        const ledUpgrade = line.led_upgrade_paise ?? 0;
        const hasUpgrades =
          line.kind === 'combo' &&
          line.combo_base_paise !== null &&
          (cakeUpgrade > 0 || ledUpgrade > 0);

        if (hasUpgrades) {
          return (
            <div key={`combo-${line.item_id ?? idx}`} className="space-y-1">
              <div className="flex justify-between">
                <span>{line.name_snapshot}</span>
                <span>{formatRupees(line.combo_base_paise as number)}</span>
              </div>
              {cakeUpgrade > 0 && (
                <div className="flex justify-between pl-4 text-gray-600">
                  <span>↳ Cake upgrade</span>
                  <span>{formatRupees(cakeUpgrade)}</span>
                </div>
              )}
              {ledUpgrade > 0 && (
                <div className="flex justify-between pl-4 text-gray-600">
                  <span>↳ LED upgrade</span>
                  <span>{formatRupees(ledUpgrade)}</span>
                </div>
              )}
            </div>
          );
        }

        return (
          <div key={`${line.kind}-${line.item_id ?? idx}`} className="flex justify-between">
            <span>
              {line.name_snapshot}
              {line.weight_half_kg !== null
                ? ` (${line.weight_half_kg / 2} kg)`
                : line.quantity > 1
                  ? ` ×${line.quantity}`
                  : ''}
            </span>
            <span>{formatRupees(line.amount_paise)}</span>
          </div>
        );
      })}

      <div className="flex justify-between border-t border-gray-200 pt-1">
        <span>Subtotal</span>
        <span>{formatRupees(breakdown.subtotal_paise)}</span>
      </div>

      {breakdown.discount_paise > 0 && (
        <div className="flex justify-between text-gray-600">
          <span>Discount</span>
          <span>−{formatRupees(breakdown.discount_paise)}</span>
        </div>
      )}

      {breakdown.food_paise > 0 && (
        <div className="flex justify-between">
          <span>Food</span>
          <span>{formatRupees(breakdown.food_paise)}</span>
        </div>
      )}

      {breakdown.other_paise > 0 && (
        <div className="flex justify-between">
          <span>Other</span>
          <span>{formatRupees(breakdown.other_paise)}</span>
        </div>
      )}

      {breakdown.cleaning_paise > 0 && (
        <div className="flex justify-between">
          <span>Cleaning</span>
          <span>{formatRupees(breakdown.cleaning_paise)}</span>
        </div>
      )}

      {breakdown.coupon_discount_paise > 0 && (
        <div className="flex justify-between text-gray-600">
          <span>Coupon {breakdown.coupon_code ?? ''}</span>
          <span>−{formatRupees(breakdown.coupon_discount_paise)}</span>
        </div>
      )}

      <div className="flex justify-between border-t border-gray-200 pt-1 font-semibold text-gray-900">
        <span>Total</span>
        <span>{formatRupees(breakdown.total_paise)}</span>
      </div>

      <div className="flex justify-between text-gray-600">
        <span>Amount paid</span>
        <span>{formatRupees(breakdown.amount_paid_paise)}</span>
      </div>

      <div className="flex justify-between text-gray-600">
        <span>Amount due</span>
        <span>{formatRupees(breakdown.amount_due_paise)}</span>
      </div>
    </div>
  );
}
