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
import { formatRupees, rupeesToPaise } from '@/lib/money';
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
  useLocationBookingMode,
  useOccasions,
  useOpenAvailability,
  usePlanDurations,
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
  /**
   * A value that changes when the booking's payments change (e.g. the current
   * amount-paid in paise). Including it re-fires the live preview so the
   * Summary's amount paid/due refresh immediately after recording a payment.
   */
  paymentsVersion?: number;
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

/** "60" -> "1 hour", "90" -> "1.5 hours", "120" -> "2 hours". */
function formatDurationLabel(minutes: number): string {
  const hours = minutes / 60;
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`;
}

/** "15:00" -> "3:00 PM". */
function formatTimeLabel(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number);
  const ampm = h < 12 ? 'AM' : 'PM';
  const hour12 = h % 12 || 12;
  return `${hour12}:${String(m).padStart(2, '0')} ${ampm}`;
}

export function BookingForm({
  locationId,
  initial,
  bookingId,
  paymentsVersion,
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
      discount_rupees: 0,
      food_rupees: 0,
      other_rupees: 0,
      cleaning_rupees: 0,
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
  // The branch's booking mode drives which window UI we render.
  const locationsQuery = useLocationBookingMode(locationId);
  const bookingMode: 'slot' | 'open' =
    locationsQuery.data?.find((l) => l.id === locationId)?.booking_mode ?? 'slot';
  const isOpenMode = bookingMode === 'open';

  // Slot mode: availability is scoped to plan + location + date so held slots
  // are flagged and rendered greyed-out / non-selectable.
  const slots = useSlotAvailability(
    isOpenMode ? null : planId,
    locationId,
    bookingDate ?? null,
    // In edit mode, exclude this booking's own window from availability.
    isEdit ? bookingId : null,
  );

  // Open mode: a Duration selector (plan's priced durations) + a Start-time
  // picker generated from working hours for the chosen duration.
  const durationMinutes = watch('duration_minutes');
  const normalizedDuration = Number.isFinite(durationMinutes)
    ? (durationMinutes as number)
    : null;
  const durations = usePlanDurations(isOpenMode ? planId : null);
  const openStarts = useOpenAvailability(
    isOpenMode ? planId : null,
    locationId,
    bookingDate ?? null,
    isOpenMode ? normalizedDuration : null,
    // In edit mode, exclude this booking's own window so a shrink/move frees it.
    isEdit ? bookingId : null,
  );
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

  // Reset the slot when the plan changes so a stale slot can't be submitted.
  // We track the previous plan id and only clear when it genuinely changes from
  // one real plan to another. This avoids clobbering the pre-filled slot in
  // edit mode, where RHF applies async defaults over one or more renders (the
  // plan id transitions undefined -> <initial plan>, which must NOT clear the
  // pre-filled slot). `prevPlanId` is seeded with the initial plan so that
  // first transition is treated as "no change".
  const prevPlanId = useRef<number | null>(
    initial?.plan_id !== undefined && Number.isFinite(initial.plan_id)
      ? (initial.plan_id as number)
      : null,
  );
  useEffect(() => {
    if (planId === prevPlanId.current) {
      return;
    }
    const hadPlan = prevPlanId.current !== null;
    prevPlanId.current = planId;
    // Only clear when moving away from a previously chosen plan; don't clear on
    // the initial undefined -> plan hydration.
    if (hadPlan) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- RHF reset to empty
      setValue('slot_id', undefined as any);
    }
  }, [planId, setValue]);

  // Reset the chosen time when the booking date changes so a stale slot/start
  // from the old date can't be submitted — the backend also requires re-picking
  // a slot on a date change. Seeded with the initial date so the first async
  // hydration (undefined -> initial date) does NOT clear the pre-filled window.
  const prevDate = useRef<string | null>(initial?.booking_date ?? null);
  useEffect(() => {
    if (bookingDate === prevDate.current) {
      return;
    }
    const hadDate = prevDate.current !== null;
    prevDate.current = bookingDate ?? null;
    if (hadDate) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- RHF reset to empty
      const clear = undefined as any;
      setValue('slot_id', clear);
      setValue('start_time', clear);
    }
  }, [bookingDate, setValue]);

  // --- Live preview summary (server-authoritative) -------------------------
  const preview = usePreviewBooking();
  const [breakdown, setBreakdown] = useState<PriceBreakdownRead | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // --- Coupon apply/remove state -------------------------------------------
  // A coupon is only sent to the pricing preview once APPLIED (never silently
  // as the user types). `appliedCoupon` holds the applied code; while set, the
  // live preview includes it and re-validates on every priced-field change.
  // `couponFieldError` surfaces coupon-specific failures right under the field.
  const [appliedCoupon, setAppliedCoupon] = useState<string | null>(
    initial?.coupon_code && initial.coupon_code.trim().length > 0
      ? initial.coupon_code
      : null,
  );
  const [couponFieldError, setCouponFieldError] = useState<string | null>(null);

  const watched = watch();
  // Serialise the priced fields and debounce so the preview fires ~400ms after
  // the last change rather than on every keystroke.
  const previewKey = useDebounce(
    JSON.stringify({
      plan_id: watched.plan_id,
      slot_id: watched.slot_id,
      start_time: watched.start_time,
      duration_minutes: watched.duration_minutes,
      booking_date: watched.booking_date,
      people: watched.people,
      cake_id: watched.cake_id,
      cake_weight_half_kg: watched.cake_weight_half_kg,
      occasion_id: watched.occasion_id,
      led_name: watched.led_name,
      // Only an APPLIED coupon feeds the preview (not the raw typed field).
      coupon_code: appliedCoupon,
      discount_rupees: watched.discount_rupees,
      food_rupees: watched.food_rupees,
      other_rupees: watched.other_rupees,
      cleaning_rupees: watched.cleaning_rupees,
      special_decor: watched.special_decor,
      combos: watched.combos,
      // Not a priced input, but re-fires the preview after a payment so the
      // Summary's amount paid/due refresh without remounting the form.
      payments_version: paymentsVersion,
    }),
    400,
  );

  const previewMutate = preview.mutate;
  useEffect(() => {
    const parsed = JSON.parse(previewKey) as BookingCreateInput;
    const planIdNum = Number.isFinite(parsed.plan_id) ? (parsed.plan_id as number) : null;
    const slotIdNum = Number.isFinite(parsed.slot_id) ? (parsed.slot_id as number) : null;
    const durationNum = Number.isFinite(parsed.duration_minutes)
      ? (parsed.duration_minutes as number)
      : null;
    const startStr =
      typeof parsed.start_time === 'string' && parsed.start_time.length > 0
        ? parsed.start_time
        : null;
    const bookingDate = parsed.booking_date;
    // A window is defined either by a slot (slot mode) or start+duration (open
    // mode). Don't preview until plan, date, and a complete window are present.
    const hasWindow = slotIdNum !== null || (startStr !== null && durationNum !== null);
    if (!planIdNum || !hasWindow || !bookingDate) {
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
      // Send exactly one window source, matching the branch's mode.
      slot_id: slotIdNum ?? undefined,
      start_time: slotIdNum === null ? (startStr ?? undefined) : undefined,
      duration_minutes: slotIdNum === null ? (durationNum ?? undefined) : undefined,
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
      // UI holds rupees; the preview endpoint expects paise.
      discount_paise: rupeesToPaise(num(parsed.discount_rupees)),
      food_paise: rupeesToPaise(num(parsed.food_rupees)),
      other_paise: rupeesToPaise(num(parsed.other_rupees)),
      cleaning_paise: rupeesToPaise(num(parsed.cleaning_rupees)),
    };

    previewMutate(body, {
      onSuccess: (data) => {
        setBreakdown(data);
        setPreviewError(null);
        // A coupon was applied but the server returned no discount for it
        // (e.g. it no longer applies after a change): surface it at the field
        // and drop the applied state so the UI reflects reality.
        if (body.coupon_code) {
          if (data.coupon_discount_paise <= 0) {
            // An applied coupon returned no discount (e.g. it stopped applying
            // after a change): surface it and drop the applied state.
            setCouponFieldError('This coupon does not apply to the current booking.');
            setAppliedCoupon(null);
          } else {
            // Coupon applied successfully — clear any prior coupon error.
            setCouponFieldError(null);
          }
        }
        // When no coupon is in play (body.coupon_code is null), leave
        // couponFieldError untouched so a prior rejection message persists
        // until the user edits the field or clicks Apply/Remove again.
      },
      onError: (err) => {
        // Route coupon-specific failures to the field; everything else to the
        // summary. On a coupon failure, drop the applied state.
        if (
          err instanceof ApiError &&
          (err.code === 'COUPON_INVALID' || err.code === 'COUPON_NOT_APPLICABLE')
        ) {
          setCouponFieldError(err.message);
          setAppliedCoupon(null);
          setPreviewError(null);
        } else {
          setPreviewError(
            err instanceof ApiError ? err.message : 'Could not compute a live summary.',
          );
        }
      },
    });
  }, [previewKey, locationId, bookingId, previewMutate]);

  // --- Coupon apply/remove handlers ----------------------------------------
  const applyCoupon = (): void => {
    const code = (watched.coupon_code ?? '').trim();
    if (code.length === 0) {
      setCouponFieldError('Enter a coupon code first.');
      return;
    }
    setCouponFieldError(null);
    setAppliedCoupon(code); // triggers a preview that validates + prices it
  };

  const removeCoupon = (): void => {
    setAppliedCoupon(null);
    setCouponFieldError(null);
    setValue('coupon_code', '');
  };

  const couponApplied =
    appliedCoupon !== null &&
    breakdown !== null &&
    breakdown.coupon_discount_paise > 0 &&
    breakdown.coupon_code !== null;

  const submit = handleSubmit((values) => {
    // Only persist a coupon that was actually applied. A code typed but never
    // applied (or one that failed validation) must not be saved.
    // Send exactly one window source matching the branch's mode: slot mode →
    // slot_id only; open mode → start_time + duration_minutes only.
    const windowFields = isOpenMode
      ? { slot_id: undefined, start_time: values.start_time, duration_minutes: values.duration_minutes }
      : { slot_id: values.slot_id, start_time: undefined, duration_minutes: undefined };
    const finalValues = {
      ...values,
      ...windowFields,
      coupon_code: appliedCoupon ?? undefined,
    } as BookingCreateValues;
    onSubmit(finalValues);
  });

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
          <span className="font-medium text-gray-700">
            {isOpenMode ? 'Duration' : 'Slot'}
          </span>
          {isOpenMode ? (
            <select
              aria-label="Duration"
              className={inputClass}
              disabled={!planId}
              {...register('duration_minutes', { valueAsNumber: true })}
            >
              <option value="">Select a duration…</option>
              {durations.data?.map((d) => (
                <option key={d.duration_minutes} value={d.duration_minutes}>
                  {formatDurationLabel(d.duration_minutes)} — {formatRupees(d.price_paise)}
                </option>
              ))}
            </select>
          ) : (
            <select
              aria-label="Slot"
              className={inputClass}
              disabled={!planId}
              {...register('slot_id', { valueAsNumber: true })}
            >
              <option value="">Select a slot…</option>
              {slots.data?.map((s) => {
                // A held slot is non-selectable, EXCEPT the booking's own slot
                // in edit mode (it holds itself) so the pre-fill stays valid.
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
          )}
          {errors.slot_id && <p className="text-xs text-red-600">{errors.slot_id.message}</p>}
        </label>

        {isOpenMode && (
          <label className="space-y-1 text-sm">
            <span className="font-medium text-gray-700">Start time</span>
            <select
              aria-label="Start time"
              className={inputClass}
              disabled={!planId || normalizedDuration === null}
              {...register('start_time')}
            >
              <option value="">Select a start time…</option>
              {(() => {
                const opts = openStarts.data ?? [];
                const currentStart = watched.start_time ?? null;
                // In edit mode the booking's own start is held by itself, so it
                // comes back "unavailable"; keep it selectable so the pre-fill
                // stays valid. Also ensure it appears even if the generator
                // omits it.
                const hasCurrent =
                  currentStart !== null &&
                  opts.some((o) => o.start_time.slice(0, 5) === currentStart);
                const rendered = opts.map((o) => {
                  const hhmm = o.start_time.slice(0, 5);
                  const isCurrent = hhmm === currentStart;
                  const blocked = !o.is_available && !isCurrent;
                  return (
                    <option key={hhmm} value={hhmm} disabled={blocked}>
                      {formatTimeLabel(hhmm)}
                      {blocked ? ' — unavailable' : ''}
                    </option>
                  );
                });
                if (currentStart !== null && !hasCurrent) {
                  rendered.unshift(
                    <option key={currentStart} value={currentStart}>
                      {formatTimeLabel(currentStart)}
                    </option>,
                  );
                }
                return rendered;
              })()}
            </select>
          </label>
        )}

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

        <div className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Coupon code</span>
          <div className="flex gap-2">
            <input
              type="text"
              aria-label="Coupon code"
              className={`${inputClass} ${couponFieldError ? 'border-red-400' : ''}`}
              disabled={couponApplied}
              {...register('coupon_code', {
                // Editing the code starts a fresh attempt: clear any prior
                // rejection so the stale message doesn't linger.
                onChange: () => {
                  if (couponFieldError) {
                    setCouponFieldError(null);
                  }
                },
              })}
            />
            {couponApplied ? (
              <button
                type="button"
                onClick={removeCoupon}
                className="shrink-0 rounded border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Remove
              </button>
            ) : (
              <button
                type="button"
                onClick={applyCoupon}
                className="shrink-0 rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
              >
                Apply
              </button>
            )}
          </div>
          {couponApplied && breakdown !== null && (
            <p className="text-xs font-medium text-green-700">
              Coupon {breakdown.coupon_code} applied — {formatRupees(breakdown.coupon_discount_paise)}{' '}
              off
            </p>
          )}
          {couponFieldError && <p className="text-xs text-red-600">{couponFieldError}</p>}
        </div>
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

        <label className="space-y-1 text-sm md:col-span-2">
          <span className="font-medium text-gray-700">Message</span>
          <textarea
            rows={5}
            className={`${inputClass} resize-y`}
            placeholder="Any detailed notes for this booking…"
            {...register('message')}
          />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {(
          [
            'discount_rupees',
            'food_rupees',
            'other_rupees',
            'cleaning_rupees',
          ] as const
        ).map((name) => (
          <label key={name} className="space-y-1 text-sm">
            <span className="font-medium text-gray-700 capitalize">
              {name.replace('_rupees', '')} (₹)
            </span>
            <input
              type="number"
              min={0}
              step="0.01"
              placeholder="e.g. 20 or 20.5"
              className={inputClass}
              {...register(name, { valueAsNumber: true })}
            />
          </label>
        ))}
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
        // An absorbed cake line is 0-amount (its cost lives in the combo's
        // upgrade) and exists only to persist the selection — don't render it.
        if (line.absorbed_by_combo) {
          return null;
        }
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
