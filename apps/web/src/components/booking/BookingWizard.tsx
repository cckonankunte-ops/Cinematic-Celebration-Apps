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
import SlotPicker from './SlotPicker';
import { emptyDraft, type BookingDraft, type Catalog } from './types';

type Step = 1 | 2 | 3 | 4 | 5;

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

  const selectPlan = (plan: Plan) => patch({ plan, slotId: null });

  const selectSlot = (slot: Slot) =>
    patch({ slotId: slot.id, showCombos: slot.show_combos });

  const toggleId = (list: number[], id: number): number[] =>
    list.includes(id) ? list.filter((x) => x !== id) : [...list, id];

  // Build the preview request body from the current draft (priced inputs only,
  // never money). Returns null when the draft isn't ready to price.
  const buildPreviewRequest = (): PublicPreviewRequest | null => {
    if (!location || !draft.plan || draft.slotId === null) {
      return null;
    }
    return {
      location_id: location.id,
      plan_id: draft.plan.id,
      slot_id: draft.slotId,
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
    if (step !== 5) {
      return;
    }
    const body = buildPreviewRequest();
    if (!body) {
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
    // `pricedInputs` captures every input that affects the price; `step` gates
    // the fetch to the review step.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, pricedInputs]);

  async function submit() {
    if (!location || !draft.plan || draft.slotId === null) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await publicApi.createBooking({
        location_id: location.id,
        plan_id: draft.plan.id,
        slot_id: draft.slotId,
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
      <div className="rounded border border-green-300 bg-green-50 p-6">
        <h2 className="text-xl font-semibold text-green-800">
          Booking request received!
        </h2>
        <p className="mt-2">
          Advance to pay:{' '}
          <strong>{formatRupees(result.advance_paise)}</strong>
        </p>
        <p className="mt-2 whitespace-pre-line">{result.payment_instructions}</p>
        <p className="mt-4 text-sm">
          Your reference token: <code>{result.booking_token}</code>
        </p>
        <a
          className="mt-4 inline-block rounded bg-brand px-4 py-2 text-white"
          href={`/booking-status?token=${encodeURIComponent(result.booking_token)}`}
        >
          Track this booking
        </a>
      </div>
    );
  }

  const canNextFromPlan = draft.plan !== null;
  const canNextFromSlot = draft.slotId !== null;
  const canSubmit =
    draft.bookingName.trim() !== '' &&
    isValidIndianMobile(draft.phone) &&
    draft.people >= 1 &&
    draft.plan !== null &&
    draft.people <= draft.plan.max_people_allowed;

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500">
        Booking at <strong>{location.name}</strong> · Step {step} of 5
      </p>

      {step === 1 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Choose a plan and date</h2>
          <ul className="grid gap-3">
            {catalog.plans.map((plan) => {
              const selected = draft.plan?.id === plan.id;
              return (
                <li key={plan.id}>
                  <button
                    type="button"
                    onClick={() => selectPlan(plan)}
                    aria-pressed={selected}
                    className={`w-full rounded border px-4 py-3 text-left ${
                      selected
                        ? 'border-brand bg-brand/10'
                        : 'border-gray-300 hover:border-brand'
                    }`}
                  >
                    <span className="font-semibold">{plan.title}</span>
                    <span className="float-right">
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
            <span className="text-sm font-medium">Booking date</span>
            <input
              type="date"
              min={todayIsoInIST()}
              value={draft.bookingDate}
              onChange={(e) => patch({ bookingDate: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2"
            />
          </label>
        </section>
      )}

      {step === 2 && draft.plan && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Pick an available slot</h2>
          <SlotPicker
            planId={draft.plan.id}
            locationId={location.id}
            bookingDate={draft.bookingDate}
            selectedSlotId={draft.slotId}
            onSelect={selectSlot}
          />
        </section>
      )}

      {step === 3 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Add-ons</h2>
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
        </section>
      )}

      {step === 4 && draft.plan && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Your details</h2>
          <BookingForm
            draft={draft}
            occasions={catalog.occasions}
            maxPeople={draft.plan.max_people_allowed}
            onChange={patch}
          />
        </section>
      )}

      {step === 5 && (
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Review &amp; request</h2>
          <p className="rounded bg-amber-50 p-3 text-sm text-amber-800">
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
                {preview.addon_lines.map((line) => (
                  <div
                    key={`${line.kind}-${line.item_id}`}
                    className="flex justify-between"
                  >
                    <dt>
                      {line.name_snapshot}
                      {line.quantity > 1 ? ` × ${line.quantity}` : ''}
                    </dt>
                    <dd>{formatRupees(line.amount_paise)}</dd>
                  </div>
                ))}
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

      <div className="flex justify-between pt-4">
        <button
          type="button"
          disabled={step === 1}
          onClick={() => setStep((s) => (s - 1) as Step)}
          className="rounded border border-gray-300 px-4 py-2 disabled:opacity-40"
        >
          Back
        </button>
        {step < 5 ? (
          <button
            type="button"
            onClick={() => setStep((s) => (s + 1) as Step)}
            disabled={
              (step === 1 && !canNextFromPlan) ||
              (step === 2 && !canNextFromSlot)
            }
            className="rounded bg-brand px-4 py-2 text-white disabled:opacity-40"
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={submitting || !canSubmit}
            className="rounded bg-brand px-4 py-2 text-white disabled:opacity-40"
          >
            {submitting ? 'Submitting…' : 'Submit request'}
          </button>
        )}
      </div>
    </div>
  );
}
