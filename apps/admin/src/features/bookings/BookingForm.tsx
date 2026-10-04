/**
 * Admin booking create form. react-hook-form + zod (`bookingCreateSchema`)
 * with cascading selects: picking a plan loads its slots; add-ons come from the
 * location catalog. The server is authoritative on price, so we show the total
 * only after creation (handled by the parent page). All money inputs are paise.
 */

import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { todayIsoInIST } from '@/lib/dates';
import {
  bookingCreateSchema,
  type BookingCreateInput,
  type BookingCreateValues,
} from './booking-schema';
import {
  useCakes,
  useCombos,
  useOccasions,
  usePlans,
  useSlots,
  useSpecialDecor,
} from './catalog-queries';

interface BookingFormProps {
  locationId: number;
  onSubmit: (values: BookingCreateValues) => void;
  isSubmitting: boolean;
  serverError: string | null;
}

const inputClass =
  'w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none';

export function BookingForm({
  locationId,
  onSubmit,
  isSubmitting,
  serverError,
}: BookingFormProps): JSX.Element {
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
      special_decor_ids: [],
      combo_ids: [],
      discount_paise: 0,
      food_paise: 0,
      other_paise: 0,
      cleaning_paise: 0,
    },
  });

  const rawPlanId = watch('plan_id');
  // valueAsNumber on an empty <select> yields NaN, not null. Normalize to null
  // so the slots query stays disabled until a real plan is chosen.
  const planId = Number.isFinite(rawPlanId) ? rawPlanId : null;
  const plans = usePlans(locationId);
  const slots = useSlots(planId);
  const cakes = useCakes(locationId);
  const decor = useSpecialDecor(locationId);
  const combos = useCombos(locationId);
  const occasions = useOccasions(locationId);

  // Keep the submitted location_id in sync with the selected location and clear
  // every location-scoped selection when the location changes. Otherwise a
  // stale plan/slot/cake/decor from a previously viewed location gets submitted
  // against the new location_id, which the server rejects as ITEM_INVALID.
  useEffect(() => {
    setValue('location_id', locationId);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- RHF reset to empty
    const clear = undefined as any;
    setValue('plan_id', clear);
    setValue('slot_id', clear);
    setValue('cake_id', clear);
    setValue('occasion_id', clear);
    setValue('special_decor_ids', []);
    setValue('combo_ids', []);
  }, [locationId, setValue]);

  // Reset the slot when the plan changes so a stale slot can't be submitted.
  // The field is cleared to NaN (empty number input) rather than a real id.
  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- RHF reset to empty
    setValue('slot_id', undefined as any);
  }, [planId, setValue]);

  const submit = handleSubmit((values) => onSubmit(values as BookingCreateValues));

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Plan</span>
          <select className={inputClass} {...register('plan_id', { valueAsNumber: true })}>
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
            className={inputClass}
            disabled={!planId}
            {...register('slot_id', { valueAsNumber: true })}
          >
            <option value="">Select a slot…</option>
            {slots.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.description}
              </option>
            ))}
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
      </div>

      <fieldset className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Special decor</span>
          <Controller
            control={control}
            name="special_decor_ids"
            render={({ field }) => (
              <div className="space-y-1">
                {decor.data?.map((d) => (
                  <label key={d.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={field.value?.includes(d.id) ?? false}
                      onChange={(e) => {
                        const set = new Set(field.value ?? []);
                        if (e.target.checked) {
                          set.add(d.id);
                        } else {
                          set.delete(d.id);
                        }
                        field.onChange([...set]);
                      }}
                    />
                    {d.name}
                  </label>
                ))}
              </div>
            )}
          />
        </div>

        <div className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Combos</span>
          <Controller
            control={control}
            name="combo_ids"
            render={({ field }) => (
              <div className="space-y-1">
                {combos.data?.map((c) => (
                  <label key={c.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={field.value?.includes(c.id) ?? false}
                      onChange={(e) => {
                        const set = new Set(field.value ?? []);
                        if (e.target.checked) {
                          set.add(c.id);
                        } else {
                          set.delete(c.id);
                        }
                        field.onChange([...set]);
                      }}
                    />
                    {c.name}
                  </label>
                ))}
              </div>
            )}
          />
        </div>
      </fieldset>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Booking name</span>
          <input type="text" className={inputClass} {...register('booking_name')} />
          {errors.booking_name && (
            <p className="text-xs text-red-600">{errors.booking_name.message}</p>
          )}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Email</span>
          <input type="text" className={inputClass} {...register('email')} />
          {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Phone</span>
          <input type="text" className={inputClass} {...register('phone')} />
        </label>

        <label className="space-y-1 text-sm">
          <span className="font-medium text-gray-700">Name on cake</span>
          <input type="text" className={inputClass} {...register('name_on_cake')} />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        {(['discount_paise', 'food_paise', 'other_paise', 'cleaning_paise'] as const).map(
          (name) => (
            <label key={name} className="space-y-1 text-sm">
              <span className="font-medium text-gray-700">{name.replace('_paise', '')} (paise)</span>
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

      {serverError && <p className="text-sm text-red-600">{serverError}</p>}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-60"
      >
        {isSubmitting ? 'Creating…' : 'Create booking'}
      </button>
    </form>
  );
}
