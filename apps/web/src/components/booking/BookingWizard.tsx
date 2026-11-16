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
import { formatDate, formatRupees, todayIsoInIST } from '../../lib/formatters';
import { isValidIndianMobile } from '../../lib/phone';
import BookingSummary from './BookingSummary';
import CakePicker from './CakePicker';
import DecorByCategory from './DecorByCategory';
import GuestCounter from './GuestCounter';
import OccasionPicker from './OccasionPicker';
import OpenSlotPicker from './OpenSlotPicker';
import SlotPicker from './SlotPicker';
import { emptyDraft, type BookingDraft, type Catalog } from './types';
import type { Combo } from '../../lib/api';

type Step = 1 | 2 | 3 | 4 | 5;

const STEP_LABELS = ['Details', 'Occasion', 'Cake', 'Add-ons', 'Payment'];

/**
 * Customer booking flow (client:load island) mounted on /book.
 *
 * Folds the branch screen and the 5-step wizard into one island so draft state
 * is shared without serializing through the URL. Reads `?location=slug`,
 * `?date=YYYY-MM-DD`, and optional `?plan=` at mount. Steps:
 *   1 Basic Details (branch/date overview + plan + time + guests + name)
 *   2 Occasion (skippable)   3 Cake (skippable)   4 Add-ons (skippable)
 *   5 Payment (terms + submit).
 * All catalog/availability/pricing is fetched at runtime; the client sends only
 * IDs/quantities/guest counts and never computes money.
 */
export default function BookingWizard() {
  const [locations, setLocations] = useState<Location[]>([]);
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
  const [agreedTerms, setAgreedTerms] = useState(false);

  // Load a branch's full catalog and set it as the active location.
  const loadBranch = (match: Location, preselectPlanId?: number) => {
    return Promise.all([
      publicApi.listPlans(match.id),
      publicApi.listCakes(match.id),
      publicApi.listSpecialDecor(match.id),
      publicApi.listCombos(match.id),
      publicApi.listOccasions(match.id),
    ]).then(([plans, cakes, specialDecor, combos, occasions]) => {
      setLocation(match);
      setCatalog({ plans, cakes, specialDecor, combos, occasions });
      if (preselectPlanId) {
        const preselected = plans.find((p) => p.id === preselectPlanId);
        if (preselected) {
          setDraft((d) => ({ ...d, plan: preselected }));
        }
      }
    });
  };

  // Resolve the location by slug, then load its catalog (plans + add-ons).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const slug = params.get('location');
    const planParam = params.get('plan');
    const dateParam = params.get('date');

    // Prefill the date from the home widget's `?date=` when it's a valid
    // YYYY-MM-DD that isn't in the past; otherwise keep today's default.
    if (dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam)) {
      const today = todayIsoInIST();
      if (dateParam >= today) {
        setDraft((d) => ({ ...d, bookingDate: dateParam }));
      }
    }

    let active = true;
    publicApi
      .listLocations()
      .then(async (locs) => {
        if (!active) return;
        setLocations(locs);
        const match = slug ? locs.find((l) => l.slug === slug) : locs[0];
        if (!match) {
          throw new Error('location-not-found');
        }
        await loadBranch(match, planParam ? Number(planParam) : undefined);
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

  const patch = (p: Partial<BookingDraft>) => setDraft((d) => ({ ...d, ...p }));

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

  const selectOpenWindow = (startTime: string, durationMinutes: number) =>
    patch({
      slotId: null,
      durationMinutes,
      startTime: startTime === '' ? null : startTime,
      showCombos: true,
    });

  const hasWindow = isOpenMode
    ? draft.startTime !== null && draft.durationMinutes !== null
    : draft.slotId !== null;

  // Change branch in place (from the Overview "Update" control). Resets the
  // plan/window since they belong to the old branch's catalog.
  const changeBranch = (slug: string) => {
    const match = locations.find((l) => l.slug === slug);
    if (!match || match.id === location?.id) return;
    setLocation(null);
    setCatalog(null);
    setPreview(null);
    setDraft((d) => ({
      ...d,
      plan: null,
      slotId: null,
      startTime: null,
      durationMinutes: null,
    }));
    void loadBranch(match);
  };

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
      people: draft.adults,
      kids: draft.kids,
      cake_id: draft.cakeId ?? undefined,
      cake_weight_half_kg: draft.cakeWeightHalfKg,
      special_decor: draft.specialDecor,
      combos: draft.comboIds.map((id) => ({ id })),
      led_name: draft.ledName || undefined,
      occasion_id: draft.occasionId ?? undefined,
      coupon_code: draft.couponCode || undefined,
    };
  };

  const pricedInputs = JSON.stringify({
    plan: draft.plan?.id ?? null,
    slot: draft.slotId,
    start: draft.startTime,
    duration: draft.durationMinutes,
    date: draft.bookingDate,
    adults: draft.adults,
    kids: draft.kids,
    cake: draft.cakeId,
    weight: draft.cakeWeightHalfKg,
    decor: draft.specialDecor,
    combos: draft.comboIds,
    led: draft.ledName,
    coupon: draft.couponCode,
  });

  useEffect(() => {
    const body = buildPreviewRequest();
    if (!body) {
      setPreview(null);
      return;
    }
    let active = true;
    publicApi
      .previewBooking(body)
      .then((breakdown) => {
        if (!active) return;
        setPreview(breakdown);
        setPreviewError(null);
      })
      .catch((err) => {
        if (!active) return;
        const message =
          err instanceof ApiError
            ? err.message
            : 'Could not calculate the price. Please try again.';
        setPreviewError(message);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pricedInputs]);

  async function submit() {
    if (!location || !draft.plan || !hasWindow || !agreedTerms) {
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
        people: draft.adults,
        kids: draft.kids,
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

  const totalGuests = draft.adults + draft.kids;
  const withinCap = draft.plan ? totalGuests <= draft.plan.max_people_allowed : false;

  // Step 1 (Basic Details) gates the rest: a plan, an available window, a name,
  // a valid phone, and guests within the plan cap.
  const basicDetailsComplete =
    draft.plan !== null &&
    hasWindow &&
    draft.bookingName.trim() !== '' &&
    isValidIndianMobile(draft.phone) &&
    draft.adults >= 1 &&
    withinCap;

  const canSubmit = basicDetailsComplete && agreedTerms;

  // Steps 2-4 are skippable; only step 1 blocks Next.
  const canNext = step === 1 ? basicDetailsComplete : true;

  const combos: Combo[] = catalog.combos;

  return (
    <div className="space-y-6">
      {/* Step header + progress */}
      <div className="rounded-2xl bg-festive-hero px-5 py-4 text-white shadow-sm">
        <p className="text-sm text-white/90">
          Booking at <strong>{location.name}</strong>
        </p>
        <div className="mt-3 flex items-center gap-2">
          {STEP_LABELS.map((label, i) => {
            const n = (i + 1) as Step;
            const done = n < step;
            const current = n === step;
            return (
              <div key={label} className="flex flex-1 flex-col items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold transition ${
                    current
                      ? 'bg-white text-brand'
                      : done
                        ? 'bg-white/80 text-brand'
                        : 'bg-white/20 text-white'
                  }`}
                >
                  {done ? '✓' : n}
                </div>
                <span className="mt-1 hidden text-xs text-white/90 sm:block">
                  {label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Overview + Update (branch + date) — shown on every step. */}
      <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="font-medium text-gray-700">Branch</span>
            <select
              aria-label="Branch"
              value={location.slug}
              onChange={(e) => changeBranch(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 focus:border-brand focus:outline-none"
            >
              {locations.map((l) => (
                <option key={l.id} value={l.slug}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-medium text-gray-700">Date</span>
            <input
              type="date"
              aria-label="Booking date"
              min={todayIsoInIST()}
              value={draft.bookingDate}
              onChange={(e) => patch({ bookingDate: e.target.value })}
              className="rounded-lg border border-gray-300 px-3 py-2 focus:border-brand focus:outline-none"
            />
          </label>
          {location.address && (
            <p className="text-xs text-gray-500">{location.address}</p>
          )}
        </div>
      </div>

      {/* STEP 1 — Basic Details: plan + time + guests + name */}
      {step === 1 && (
        <section className="animate-fade-up space-y-5 rounded-2xl bg-white p-6 shadow-sm">
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              Choose a decoration theme
            </h2>
            <ul className="mt-3 grid gap-4 sm:grid-cols-2">
              {catalog.plans.map((plan) => {
                const selected = draft.plan?.id === plan.id;
                const image = plan.gallery_urls?.[0];
                return (
                  <li key={plan.id}>
                    <button
                      type="button"
                      onClick={() => selectPlan(plan)}
                      aria-pressed={selected}
                      className={`group w-full overflow-hidden rounded-2xl border-2 text-left transition ${
                        selected
                          ? 'border-brand shadow-md'
                          : 'border-gray-200 hover:border-brand hover:shadow'
                      }`}
                    >
                      <div className="relative aspect-[16/10] w-full overflow-hidden bg-festive-hero">
                        {image ? (
                          <img
                            src={image}
                            alt={plan.title}
                            loading="lazy"
                            className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-4xl">
                            🎀
                          </div>
                        )}
                        {selected && (
                          <span className="absolute right-2 top-2 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-brand shadow">
                            ✓ Selected
                          </span>
                        )}
                      </div>
                      <div className="p-4">
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-semibold text-gray-900">
                            {plan.title}
                          </span>
                          <span className="shrink-0 font-semibold text-brand">
                            {formatRupees(plan.price_paise)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">
                          For up to {plan.people_allowed} people · max{' '}
                          {plan.max_people_allowed}
                        </p>
                        {plan.description && (
                          <p className="mt-1 line-clamp-2 text-sm text-gray-600">
                            {plan.description}
                          </p>
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

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

          {draft.plan && (
            <div className="border-t border-gray-100 pt-4">
              <h3 className="font-semibold text-gray-900">Guests</h3>
              <div className="mt-3">
                <GuestCounter
                  adults={draft.adults}
                  kids={draft.kids}
                  maxPeople={draft.plan.max_people_allowed}
                  onChange={({ adults, kids }) => patch({ adults, kids })}
                />
              </div>
            </div>
          )}

          <div className="border-t border-gray-100 pt-4">
            <h3 className="font-semibold text-gray-900">Your details</h3>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium">Booking name *</span>
                <input
                  type="text"
                  required
                  value={draft.bookingName}
                  onChange={(e) => patch({ bookingName: e.target.value })}
                  className="rounded border border-gray-300 px-3 py-2"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium">Phone *</span>
                <input
                  type="tel"
                  required
                  value={draft.phone}
                  onChange={(e) => patch({ phone: e.target.value })}
                  aria-invalid={
                    draft.phone.trim() !== '' && !isValidIndianMobile(draft.phone)
                  }
                  className="rounded border border-gray-300 px-3 py-2"
                />
                {draft.phone.trim() !== '' &&
                  !isValidIndianMobile(draft.phone) && (
                    <span className="text-xs text-red-600">
                      Enter a valid Indian mobile number
                    </span>
                  )}
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium">Email</span>
                <input
                  type="email"
                  value={draft.email}
                  onChange={(e) => patch({ email: e.target.value })}
                  className="rounded border border-gray-300 px-3 py-2"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium">Special person's name</span>
                <input
                  type="text"
                  value={draft.specialPersonName}
                  onChange={(e) => patch({ specialPersonName: e.target.value })}
                  className="rounded border border-gray-300 px-3 py-2"
                />
              </label>
            </div>
          </div>
        </section>
      )}

      {/* STEP 2 — Occasion (skippable) */}
      {step === 2 && (
        <section className="animate-fade-up space-y-4 rounded-2xl bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">What's the occasion?</h2>
            <button
              type="button"
              onClick={() => setStep(3)}
              className="text-sm font-semibold text-brand hover:underline"
            >
              Skip
            </button>
          </div>
          <OccasionPicker
            occasions={catalog.occasions}
            selectedId={draft.occasionId}
            onSelect={(occasionId) => patch({ occasionId })}
          />
        </section>
      )}

      {/* STEP 3 — Cake (skippable) */}
      {step === 3 && (
        <section className="animate-fade-up space-y-4 rounded-2xl bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">Add a cake</h2>
            <button
              type="button"
              onClick={() => {
                patch({ cakeId: null });
                setStep(4);
              }}
              className="text-sm font-semibold text-brand hover:underline"
            >
              Skip
            </button>
          </div>
          <CakePicker
            cakes={catalog.cakes}
            cakeId={draft.cakeId}
            cakeWeightHalfKg={draft.cakeWeightHalfKg}
            onCakeChange={(cakeId) => patch({ cakeId })}
            onCakeWeightChange={(cakeWeightHalfKg) => patch({ cakeWeightHalfKg })}
          />
          {draft.cakeId !== null && (
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium">Name on cake</span>
              <input
                type="text"
                value={draft.nameOnCake}
                onChange={(e) => patch({ nameOnCake: e.target.value })}
                placeholder="e.g. Happy Birthday Arun"
                className="rounded border border-gray-300 px-3 py-2"
              />
            </label>
          )}
        </section>
      )}

      {/* STEP 4 — Add-ons (skippable) */}
      {step === 4 && (
        <section className="animate-fade-up space-y-5 rounded-2xl bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">Make it special</h2>
            <button
              type="button"
              onClick={() => {
                patch({ specialDecor: [], comboIds: [] });
                setStep(5);
              }}
              className="text-sm font-semibold text-brand hover:underline"
            >
              Add later after booking
            </button>
          </div>

          {draft.showCombos && combos.length > 0 && (
            <section>
              <h3 className="mb-2 font-semibold text-gray-900">Save with Combos</h3>
              <ul className="grid gap-3 sm:grid-cols-2">
                {combos.map((item) => {
                  const selected = draft.comboIds.includes(item.id);
                  const saves = item.savings_paise > 0;
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        aria-pressed={selected}
                        onClick={() =>
                          patch({
                            comboIds: draft.comboIds.includes(item.id)
                              ? []
                              : [item.id],
                          })
                        }
                        className={`flex w-full overflow-hidden rounded-xl border text-left transition ${
                          selected
                            ? 'border-festive-magenta ring-2 ring-festive-magenta'
                            : 'border-gray-200 hover:border-festive-magenta/60'
                        }`}
                      >
                        <div className="relative h-24 w-24 flex-none overflow-hidden bg-festive-hero">
                          {item.image_url ? (
                            <img
                              src={item.image_url}
                              alt={item.name}
                              loading="lazy"
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <span
                              aria-hidden="true"
                              className="flex h-full w-full items-center justify-center text-2xl"
                            >
                              🎀
                            </span>
                          )}
                        </div>
                        <div className="flex flex-1 flex-col gap-0.5 p-2">
                          <span className="font-semibold text-gray-900">
                            {item.name}
                          </span>
                          {item.description && (
                            <span className="text-xs text-gray-500">
                              {item.description}
                            </span>
                          )}
                          <span className="mt-auto flex items-baseline gap-2">
                            {saves && item.worth_paise !== null && (
                              <span className="text-xs text-gray-400 line-through">
                                {formatRupees(item.worth_paise)}
                              </span>
                            )}
                            <span className="font-bold text-festive-magenta">
                              {formatRupees(item.price_paise)}
                            </span>
                          </span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          <DecorByCategory
            specialDecor={catalog.specialDecor}
            decor={draft.specialDecor}
            onChangeDecor={(specialDecor) => patch({ specialDecor })}
          />

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Message / special requests</span>
            <textarea
              rows={3}
              value={draft.message}
              onChange={(e) => patch({ message: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2"
            />
          </label>
        </section>
      )}

      {/* STEP 5 — Payment: terms + submit */}
      {step === 5 && (
        <section className="animate-fade-up space-y-4 rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">Confirm &amp; request</h2>
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            This is a booking <strong>request</strong>. The total and advance
            below are calculated by our team's system (server-authoritative). Pay
            the advance to confirm; the balance is payable at the venue.
          </p>

          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt>Plan</dt>
              <dd>{draft.plan?.title}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Date</dt>
              <dd>{formatDate(draft.bookingDate)}</dd>
            </div>
            <div className="flex justify-between">
              <dt>People (above 10 yrs)</dt>
              <dd>{draft.adults}</dd>
            </div>
            {draft.kids > 0 && (
              <div className="flex justify-between">
                <dt>Kids (3–10 yrs)</dt>
                <dd>{draft.kids}</dd>
              </div>
            )}
          </dl>

          <details className="rounded-xl border border-gray-200 p-3">
            <summary className="cursor-pointer font-semibold text-gray-900">
              Add a LED name
            </summary>
            <label className="mt-3 flex flex-col gap-1">
              <input
                type="text"
                value={draft.ledName}
                onChange={(e) => patch({ ledName: e.target.value })}
                aria-label="LED name"
                className="rounded border border-gray-300 px-3 py-2"
              />
              <span className="text-xs text-gray-500">₹40 per letter</span>
            </label>
          </details>

          <details className="rounded-xl border border-gray-200 p-3">
            <summary className="cursor-pointer font-semibold text-gray-900">
              Have a coupon code?
            </summary>
            <input
              type="text"
              value={draft.couponCode}
              onChange={(e) => patch({ couponCode: e.target.value })}
              aria-label="Coupon code"
              className="mt-3 w-full rounded border border-gray-300 px-3 py-2"
            />
          </details>

          <div className="rounded-lg border border-gray-200 p-3 text-sm text-gray-600">
            <p className="font-semibold text-gray-800">Terms &amp; Conditions</p>
            <p className="mt-1">
              Bookings are confirmed only after the advance is received. The
              advance is non-refundable. Outside food and decoration are subject
              to branch policy. Please arrive on time; the slot ends as scheduled.
            </p>
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={agreedTerms}
              onChange={(e) => setAgreedTerms(e.target.checked)}
              className="mt-0.5"
            />
            <span>I agree to the Terms &amp; Conditions.</span>
          </label>

          {submitError && <p className="text-red-600">{submitError}</p>}
        </section>
      )}

      {/* Spacer so content isn't hidden behind the sticky bar. */}
      <div className="h-28" aria-hidden="true"></div>

      {/* Sticky summary + action bar. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/40 bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-5xl px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <BookingSummary
                breakdown={preview}
                adults={draft.adults}
                kids={draft.kids}
                previewError={previewError}
              />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {step > 1 && (
                <button
                  type="button"
                  onClick={() => setStep((s) => (s - 1) as Step)}
                  className="rounded-full border border-gray-300 px-5 py-2.5 font-medium text-gray-700 transition hover:bg-gray-50"
                >
                  Back
                </button>
              )}
              {step < 5 ? (
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
    </div>
  );
}
