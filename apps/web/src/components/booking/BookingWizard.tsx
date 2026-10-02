import { useEffect, useMemo, useState } from 'react';
import {
  ApiError,
  publicApi,
  type BookingResult,
  type Location,
  type Plan,
  type Slot,
} from '../../lib/api';
import { formatRupees, todayIsoInIST } from '../../lib/formatters';
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

  // A compact client-side estimate for the review step. The authoritative
  // total is always computed by the server when the booking is created.
  const estimate = useMemo(() => {
    if (!draft.plan || !catalog) {
      return 0;
    }
    const extraGuests = Math.max(0, draft.people - draft.plan.people_allowed);
    let total =
      draft.plan.price_paise + extraGuests * draft.plan.extra_guest_paise;
    if (draft.cakeId !== null) {
      const cake = catalog.cakes.find((c) => c.id === draft.cakeId);
      total += cake?.price_paise ?? 0;
    }
    for (const id of draft.specialDecorIds) {
      total += catalog.specialDecor.find((d) => d.id === id)?.price_paise ?? 0;
    }
    for (const id of draft.comboIds) {
      total += catalog.combos.find((c) => c.id === id)?.price_paise ?? 0;
    }
    return total;
  }, [draft, catalog]);

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
        email: draft.email,
        phone: draft.phone || undefined,
        special_person_name: draft.specialPersonName || undefined,
        name_on_cake: draft.nameOnCake || undefined,
        message: draft.message || undefined,
        people: draft.people,
        occasion_id: draft.occasionId ?? undefined,
        cake_id: draft.cakeId ?? undefined,
        special_decor_ids: draft.specialDecorIds,
        combo_ids: draft.comboIds,
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
    draft.email.trim() !== '' &&
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
            specialDecorIds={draft.specialDecorIds}
            comboIds={draft.comboIds}
            onCakeChange={(cakeId) => patch({ cakeId })}
            onToggleDecor={(id) =>
              patch({ specialDecorIds: toggleId(draft.specialDecorIds, id) })
            }
            onToggleCombo={(id) =>
              patch({ comboIds: toggleId(draft.comboIds, id) })
            }
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
            advance are confirmed by our team. The estimate below is indicative;
            the server calculates the authoritative total.
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
            <div className="flex justify-between font-semibold">
              <dt>Estimated total</dt>
              <dd>{formatRupees(estimate)}</dd>
            </div>
          </dl>
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
