import { useEffect, useState } from 'react';
import {
  ApiError,
  publicApi,
  type BookingResult,
  type Location,
  type Plan,
  type PriceBreakdownRead,
  type PublicPreviewRequest,
  type Slot,
} from '../../lib/api';
import { formatRupees, todayIsoInIST } from '../../lib/formatters';
import { isValidIndianMobile } from '../../lib/phone';
import AddonSelector from './AddonSelector';
import BookingForm from './BookingForm';
import OpenSlotPicker from './OpenSlotPicker';
import SlotPicker from './SlotPicker';
import { emptyDraft, type BookingDraft, type Catalog } from './types';

type Step = 1 | 2 | 3;

/**
 * Multi-step booking wizard (client:load island).
 *
 * Reads the location slug from the query string (`?location=slug`) at mount —
 * the page is a static shell, so routing data lives in the URL rather than a
 * dynamic path segment. All catalog/availability/pricing is fetched at runtime.
 */
export default function BookingWizard() {
  const [location, setLocation] = useState<Location | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<BookingDraft>(() =>
    emptyDraft(todayIsoInIST()),
  );
  const [step, setStep] = useState<Step>(1);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<BookingResult | null>(null);
  const [preview, setPreview] = useState<PriceBreakdownRead | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Resolve the location by slug, then load its catalog (plans + add-ons).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const slug = params.get('location');
    const planParam = params.get('plan');

    let active = true;
    publicApi
      .listLocations()
      .then(async (locations) => {
        const match = slug
          ? locations.find((l) => l.slug === slug)
          : locations[0];
        if (!match) {
          throw new Error('location-not-found');
        }
        const [plans, cakes, specialDecor, combos, occasions] =
          await Promise.all([
            publicApi.listPlans(match.id),
            publicApi.listCakes(match.id),
            publicApi.listSpecialDecor(match.id),
            publicApi.listCombos(match.id),
            publicApi.listOccasions(match.id),
          ]);
        if (!active) {
          return;
        }
        setLocation(match);
        setCatalog({ plans, cakes, specialDecor, combos, occasions });
        if (planParam) {
          const preselected = plans.find((p) => p.id === Number(planParam));
          if (preselected) {
            setDraft((d) => ({ ...d, plan: preselected }));
          }
        }
      })
      .catch(() => {
        if (active) {
          setLoadError('Could not load this location. Please try again later.');
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const patch = (p: Partial<BookingDraft>) =>
    setDraft((d) => ({ ...d, ...p }));

  // The branch's booking mode decides which Step-2 picker is shown and which
  // window fields are sent. Defaults to 'slot' until the location loads.
  const isOpenMode = location?.booking_mode === 'open';

  const selectPlan = (plan: Plan) =>
    patch({ plan, slotId: null, startTime: null, durationMinutes: null });

  const selectSlot = (slot: Slot) =>
    patch({
      slotId: slot.id,
      startTime: null,
      durationMinutes: null,
      showCombos: slot.show_combos,
    });

  // Open mode: choosing a start+duration sets the window; an empty start means
  // only the duration changed (start reset). Combos are shown in open mode.
  const selectOpenWindow = (startTime: string, durationMinutes: number) =>
    patch({
      slotId: null,
      durationMinutes,
      startTime: startTime === '' ? null : startTime,
      showCombos: true,
    });

  // True when the draft has a complete booking window for the current mode.
  const hasWindow = isOpenMode
    ? draft.startTime !== null && draft.durationMinutes !== null
    : draft.slotId !== null;

  const toggleId = (list: number[], id: number): number[] =>
    list.includes(id) ? list.filter((x) => x !== id) : [...list, id];

  // Build the preview request body from the current draft (priced inputs only,
  // never money). Returns null when the draft isn't ready to price.
  const buildPreviewRequest = (): PublicPreviewRequest | null => {
    if (!location || !draft.plan || !hasWindow) {
      return null;
    }
    const windowFields = isOpenMode
      ? {
          start_time: draft.startTime ?? undefined,
          duration_minutes: draft.durationMinutes ?? undefined,
        }
      : { slot_id: draft.slotId ?? undefined };
    return {
      location_id: location.id,
      plan_id: draft.plan.id,
      ...windowFields,
      booking_date: draft.bookingDate,
      people: draft.people,
      cake_id: draft.cakeId ?? undefined,
      cake_weight_half_kg: draft.cakeWeightHalfKg,
      special_decor: draft.specialDecor,
      combos: draft.comboIds.map((id) => ({ id })),
      led_name: draft.ledName || undefined,
      occasion_id: draft.occasionId ?? undefined,
      coupon_code: draft.couponCode || undefined,
    };
  };

  // Serialized priced inputs: fetching the authoritative server preview is
  // keyed on this so we only re-price when something that affects the price
  // actually changes.
  const pricedInputs = JSON.stringify({
    plan: draft.plan?.id ?? null,
    slot: draft.slotId,
    start: draft.startTime,
    duration: draft.durationMinutes,
    date: draft.bookingDate,
    people: draft.people,
    cake: draft.cakeId,
    weight: draft.cakeWeightHalfKg,
    decor: draft.specialDecor,
    combos: draft.comboIds,
    led: draft.ledName,
    coupon: draft.couponCode,
  });

  // Fetch the authoritative price breakdown from the server when the review
  // step is active (and whenever a priced input changes while there). Preview
  // errors (e.g. an invalid coupon) surface inline without blocking editing.
  useEffect(() => {
    // Price the draft as soon as it's priceable (plan + window), on ANY step,
    // so the sticky bar can show a live running total from step 1 onward and
    // update as add-ons change in step 2. When not yet priceable, clear the
    // total so the bar falls back to the step indicator.
    const body = buildPreviewRequest();
    if (!body) {
      setPreview(null);
      return;
    }
    let active = true;
    publicApi
      .previewBooking(body)
      .then((breakdown) => {
        if (!active) {
          return;
        }
        setPreview(breakdown);
        setPreviewError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        const message =
          err instanceof ApiError
            ? err.message
            : 'Could not calculate the price. Please try again.';
        setPreviewError(message);
      });
    return () => {
      active = false;
    };
    // `pricedInputs` captures every input that affects the price; re-price
    // whenever any of them change (independent of the current step).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pricedInputs]);

  async function submit() {
    if (!location || !draft.plan || !hasWindow) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const windowFields = isOpenMode
        ? {
            start_time: draft.startTime ?? undefined,
            duration_minutes: draft.durationMinutes ?? undefined,
          }
        : { slot_id: draft.slotId ?? undefined };
      const res = await publicApi.createBooking({
        location_id: location.id,
        plan_id: draft.plan.id,
        ...windowFields,
        booking_date: draft.bookingDate,
        booking_name: draft.bookingName,
        email: draft.email || undefined,
        phone: draft.phone,
        special_person_name: draft.specialPersonName || undefined,
        name_on_cake: draft.nameOnCake || undefined,
        message: draft.message || undefined,
        people: draft.people,
        occasion_id: draft.occasionId ?? undefined,
        cake_id: draft.cakeId ?? undefined,
        cake_weight_half_kg: draft.cakeWeightHalfKg,
        led_name: draft.ledName || undefined,
        coupon_code: draft.couponCode || undefined,
        special_decor: draft.specialDecor,
        combos: draft.comboIds.map((id) => ({ id })),
      });
      setResult(res);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Something went wrong submitting your request. Please try again.';
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loadError) {
    return <p className="text-red-600">{loadError}</p>;
  }
  if (!location || !catalog) {
    return <p className="text-gray-500">Loading…</p>;
  }

  if (result) {
    return (
      <div className="animate-pop rounded-3xl border border-festive-mint/40 bg-white p-8 text-center shadow-lg">
        <div className="text-5xl">🎉</div>
        <h2 className="mt-3 text-2xl font-extrabold text-gradient">
          Booking request received!
        </h2>
        <p className="mt-3 text-gray-700">
          Advance to pay:{' '}
          <strong className="text-brand">{formatRupees(result.advance_paise)}</strong>
        </p>
        <p className="mt-2 whitespace-pre-line text-sm text-gray-600">
          {result.payment_instructions}
        </p>
        <p className="mt-4 text-sm text-gray-500">
          Your reference token:{' '}
          <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-gray-700">
            {result.booking_token}
          </code>
        </p>
        <a
          className="mt-6 inline-block rounded-full bg-festive-hero px-7 py-3 font-semibold text-white shadow transition hover:scale-105"
          href={`/booking-status?token=${encodeURIComponent(result.booking_token)}`}
        >
          Track this booking
        </a>
      </div>
    );
  }

  const canNextFromPlan = draft.plan !== null;
  const canNextFromSlot = hasWindow;
  const canSubmit =
    draft.bookingName.trim() !== '' &&
    isValidIndianMobile(draft.phone) &&
    draft.people >= 1 &&
    draft.plan !== null &&
    draft.people <= draft.plan.max_people_allowed;

  // Mobile-first 3-step flow: celebration (plan+date+time), make-it-special
  // (add-ons + your details), review & request.
  const stepLabels = ['Celebration', 'Details', 'Review'];
  const canNext =
    (step === 1 && canNextFromPlan && canNextFromSlot) || step === 2;

  return (
    <div className="space-y-6">
      {/* Festive step header + progress */}
      <div className="rounded-2xl bg-festive-hero px-5 py-4 text-white shadow-sm">
        <p className="text-sm text-white/90">
          Booking at <strong>{location.name}</strong>
        </p>
        <div className="mt-3 flex items-center gap-2">
          {stepLabels.map((label, i) => {
            const n = (i + 1) as Step;
            const done = n < step;
            const active = n === step;
            return (
              <div key={label} className="flex flex-1 flex-col items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold transition ${
                    active
                      ? 'bg-white text-brand'
                      : done
                        ? 'bg-white/80 text-brand'
                        : 'bg-white/20 text-white'
                  }`}
                >
                  {done ? '✓' : n}
                </div>
                <span className="mt-1 hidden text-xs text-white/90 sm:block">{label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {step === 1 && (
        <section className="animate-fade-up space-y-4 rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">Choose a plan and date</h2>
          <ul className="grid gap-3">
            {catalog.plans.map((plan) => {
              const selected = draft.plan?.id === plan.id;
              return (
                <li key={plan.id}>
                  <button
                    type="button"
                    onClick={() => selectPlan(plan)}
                    aria-pressed={selected}
                    className={`w-full rounded-xl border-2 px-4 py-3 text-left transition ${
                      selected
                        ? 'border-brand bg-brand/10 shadow-sm'
                        : 'border-gray-200 hover:border-brand hover:bg-brand/5'
                    }`}
                  >
                    <span className="font-semibold text-gray-900">{plan.title}</span>
                    <span className="float-right font-semibold text-brand">
                      {formatRupees(plan.price_paise)}
                    </span>
                    {plan.description && (
                      <p className="mt-1 text-sm text-gray-600">
                        {plan.description}
                      </p>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-gray-700">Booking date</span>
            <input
              type="date"
              min={todayIsoInIST()}
              value={draft.bookingDate}
              onChange={(e) => patch({ bookingDate: e.target.value })}
              className="rounded-lg border border-gray-300 px-3 py-2 focus:border-brand focus:outline-none"
            />
          </label>

          {/* Time appears right after plan + date (same step) so the first
              screen captures the whole "when" in one place. */}
          {draft.plan && (
            <div className="border-t border-gray-100 pt-4">
              <h3 className="font-semibold text-gray-900">
                {isOpenMode ? 'Choose a time' : 'Pick an available slot'}
              </h3>
              <div className="mt-3">
                {isOpenMode ? (
                  <OpenSlotPicker
                    planId={draft.plan.id}
                    locationId={location.id}
                    bookingDate={draft.bookingDate}
                    selectedStart={draft.startTime}
                    selectedDuration={draft.durationMinutes}
                    onSelect={selectOpenWindow}
                  />
                ) : (
                  <SlotPicker
                    planId={draft.plan.id}
                    locationId={location.id}
                    bookingDate={draft.bookingDate}
                    selectedSlotId={draft.slotId}
                    onSelect={selectSlot}
                  />
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {step === 2 && (
        <section className="animate-fade-up space-y-4 rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">Add-ons</h2>
          <AddonSelector
            cakes={catalog.cakes}
            specialDecor={catalog.specialDecor}
            combos={catalog.combos}
            showCombos={draft.showCombos}
            cakeId={draft.cakeId}
            cakeWeightHalfKg={draft.cakeWeightHalfKg}
            decor={draft.specialDecor}
            comboIds={draft.comboIds}
            ledName={draft.ledName}
            couponCode={draft.couponCode}
            onCakeChange={(cakeId) => patch({ cakeId })}
            onCakeWeightChange={(cakeWeightHalfKg) =>
              patch({ cakeWeightHalfKg })
            }
            onChangeDecor={(specialDecor) => patch({ specialDecor })}
            onToggleCombo={(id) =>
              patch({ comboIds: toggleId(draft.comboIds, id) })
            }
            onLedNameChange={(ledName) => patch({ ledName })}
            onCouponChange={(couponCode) => patch({ couponCode })}
          />

          {/* Your details live on the same "make it special" step so there's
              one screen between choosing and reviewing. */}
          {draft.plan && (
            <div className="border-t border-gray-100 pt-5">
              <h3 className="font-semibold text-gray-900">Your details</h3>
              <div className="mt-3">
                <BookingForm
                  draft={draft}
                  occasions={catalog.occasions}
                  maxPeople={draft.plan.max_people_allowed}
                  onChange={patch}
                />
              </div>
            </div>
          )}
        </section>
      )}

      {step === 3 && (
        <section className="animate-fade-up space-y-4 rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">Review &amp; request</h2>
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            This is a booking <strong>request</strong>. The final price and
            advance are confirmed by our team. The total below is the
            authoritative amount calculated by the server.
          </p>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt>Plan</dt>
              <dd>{draft.plan?.title}</dd>
            </div>
            <div className="flex justify-between">
              <dt>People</dt>
              <dd>{draft.people}</dd>
            </div>
            {preview && (
              <>
                <div className="flex justify-between">
                  <dt>Plan price</dt>
                  <dd>{formatRupees(preview.plan_price_paise)}</dd>
                </div>
                {preview.extra_guest_paise > 0 && (
                  <div className="flex justify-between">
                    <dt>Extra guests</dt>
                    <dd>{formatRupees(preview.extra_guest_paise)}</dd>
                  </div>
                )}
                {preview.addon_lines.map((line, idx) => {
                  const cakeUpgrade = line.cake_upgrade_paise ?? 0;
                  const ledUpgrade = line.led_upgrade_paise ?? 0;
                  const hasUpgrades =
                    line.kind === 'combo' &&
                    line.combo_base_paise !== null &&
                    (cakeUpgrade > 0 || ledUpgrade > 0);

                  if (hasUpgrades) {
                    return (
                      <div
                        key={`combo-${line.item_id ?? idx}`}
                        className="space-y-1"
                      >
                        <div className="flex justify-between">
                          <dt>{line.name_snapshot}</dt>
                          <dd>
                            {formatRupees(line.combo_base_paise as number)}
                          </dd>
                        </div>
                        {cakeUpgrade > 0 && (
                          <div className="flex justify-between pl-4 text-gray-600">
                            <dt>↳ Cake upgrade</dt>
                            <dd>{formatRupees(cakeUpgrade)}</dd>
                          </div>
                        )}
                        {ledUpgrade > 0 && (
                          <div className="flex justify-between pl-4 text-gray-600">
                            <dt>↳ LED upgrade</dt>
                            <dd>{formatRupees(ledUpgrade)}</dd>
                          </div>
                        )}
                      </div>
                    );
                  }

                  return (
                    <div
                      key={`${line.kind}-${line.item_id ?? idx}`}
                      className="flex justify-between"
                    >
                      <dt>
                        {line.name_snapshot}
                        {line.quantity > 1 ? ` × ${line.quantity}` : ''}
                      </dt>
                      <dd>{formatRupees(line.amount_paise)}</dd>
                    </div>
                  );
                })}
                <div className="flex justify-between">
                  <dt>Subtotal</dt>
                  <dd>{formatRupees(preview.subtotal_paise)}</dd>
                </div>
                {preview.coupon_code && (
                  <div className="flex justify-between text-green-700">
                    <dt>Coupon ({preview.coupon_code})</dt>
                    <dd>-{formatRupees(preview.coupon_discount_paise)}</dd>
                  </div>
                )}
                <div className="flex justify-between font-semibold">
                  <dt>Total</dt>
                  <dd>{formatRupees(preview.total_paise)}</dd>
                </div>
              </>
            )}
          </dl>
          {previewError && <p className="text-amber-700">{previewError}</p>}
          {submitError && <p className="text-red-600">{submitError}</p>}
        </section>
      )}

      {/* Spacer so content isn't hidden behind the sticky action bar. */}
      <div className="h-20" aria-hidden="true"></div>

      {/* Sticky bottom action bar: live total + primary action, always in thumb
          reach on mobile. The total shows once the server has priced the draft. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/40 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            {preview ? (
              <>
                <p className="text-xs text-gray-500">Total</p>
                <p className="text-lg font-bold text-gray-900">
                  {formatRupees(preview.total_paise)}
                </p>
              </>
            ) : (
              <p className="text-sm text-gray-500">Step {step} of 3</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep((s) => (s - 1) as Step)}
                className="rounded-full border border-gray-300 px-5 py-2.5 font-medium text-gray-700 transition hover:bg-gray-50"
              >
                Back
              </button>
            )}
            {step < 3 ? (
              <button
                type="button"
                onClick={() => setStep((s) => (s + 1) as Step)}
                disabled={!canNext}
                className="rounded-full bg-festive-hero px-7 py-2.5 font-semibold text-white shadow-sm transition hover:opacity-90 disabled:opacity-40"
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={submitting || !canSubmit}
                className="rounded-full bg-festive-hero px-7 py-2.5 font-semibold text-white shadow-sm transition hover:opacity-90 disabled:opacity-40"
              >
                {submitting ? 'Submitting…' : 'Submit request'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
