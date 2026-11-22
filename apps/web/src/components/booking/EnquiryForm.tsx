import { useEffect, useId, useState } from 'react';
import { ApiError, publicApi, type EnquiryIn, type Location } from '../../lib/api';
import { todayIsoInIST } from '../../lib/formatters';
import { readLanding } from '../../lib/landing';
import { isValidIndianMobile, telHref } from '../../lib/phone';

/**
 * Shared enquiry form (lead-crm R3): the homepage quick enquiry and the
 * contact page form both post to POST /public/enquiries and become leads.
 *
 * Name, phone and branch are required; values are kept on any error. A hidden
 * honeypot field ("website") is never shown to people; the server treats a
 * filled one as spam and stores nothing.
 */
export interface EnquiryFormProps {
  source: EnquiryIn['source'];
  /** Show the optional preferred date (homepage). */
  showDate?: boolean;
  /** Show the optional email field (contact page). */
  showEmail?: boolean;
  messageLabel?: string;
  submitLabel?: string;
}

type FieldErrors = Partial<Record<'name' | 'phone' | 'location' | 'email', string>>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function EnquiryForm({
  source,
  showDate = false,
  showEmail = false,
  messageLabel = 'Message (optional)',
  submitLabel = 'Send enquiry',
}: EnquiryFormProps) {
  const id = useId();
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [date, setDate] = useState('');
  const [message, setMessage] = useState('');
  const [website, setWebsite] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<{ message: string; branch: Location | null } | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    publicApi
      .listLocations()
      .then((locs) => {
        if (!active) return;
        setLocations(locs);
        if (locs.length === 1) setLocationId(String(locs[0].id));
      })
      .catch(() => {
        if (active) setFormError('Could not load branches. Please try again later.');
      });
    return () => {
      active = false;
    };
  }, []);

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!name.trim()) next.name = 'Please enter your name.';
    if (!isValidIndianMobile(phone)) next.phone = 'Enter a valid Indian mobile number.';
    if (!locationId) next.location = 'Please choose a branch.';
    if (showEmail && email.trim() && !EMAIL.test(email.trim())) {
      next.email = 'Enter a valid email or leave it empty.';
    }
    return next;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      const res = await publicApi.submitEnquiry({
        source,
        location_id: Number(locationId),
        name: name.trim(),
        phone,
        preferred_date: date || undefined,
        message: message.trim() || undefined,
        email: showEmail ? email.trim() || undefined : undefined,
        website: website || undefined,
        attribution: readLanding(),
      });
      const branch = locations.find((l) => String(l.id) === locationId) ?? null;
      setDone({ message: res.message, branch });
    } catch (err) {
      // Keep every value so the visitor can fix and resend (R3.6).
      setFormError(
        err instanceof ApiError && err.status === 422
          ? 'Please check your details and try again.'
          : err instanceof ApiError && err.status === 429
            ? 'Too many attempts. Please wait a minute and try again.'
            : 'Could not send your enquiry. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    const tel = telHref(done.branch?.phone);
    return (
      <div role="status" className="rounded-xl bg-green-50 p-4 text-green-800">
        <p className="font-semibold">{done.message}</p>
        {done.branch && tel && (
          <p className="mt-2 text-sm">
            Need it sooner? Call {done.branch.name}:{' '}
            <a href={tel} className="font-semibold underline">
              {done.branch.phone}
            </a>
          </p>
        )}
      </div>
    );
  }

  const field = (key: keyof FieldErrors) =>
    errors[key] ? (
      <span id={`${id}-${key}-error`} className="text-xs text-red-600">
        {errors[key]}
      </span>
    ) : null;
  const described = (key: keyof FieldErrors) =>
    errors[key] ? `${id}-${key}-error` : undefined;

  return (
    <form onSubmit={onSubmit} noValidate className="grid gap-4">
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Name *</span>
        <input
          type="text"
          autoComplete="name"
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={Boolean(errors.name)}
          aria-describedby={described('name')}
          className="rounded border border-gray-300 px-3 py-2"
        />
        {field('name')}
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Phone *</span>
        <input
          type="tel"
          autoComplete="tel"
          inputMode="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          aria-invalid={Boolean(errors.phone)}
          aria-describedby={described('phone') ?? `${id}-phone-help`}
          className="rounded border border-gray-300 px-3 py-2"
        />
        <span id={`${id}-phone-help`} className="text-xs text-gray-500">
          We&apos;ll use this number to reply to your enquiry.
        </span>
        {field('phone')}
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Branch *</span>
        <select
          value={locationId}
          onChange={(e) => setLocationId(e.target.value)}
          aria-invalid={Boolean(errors.location)}
          aria-describedby={described('location')}
          className="rounded border border-gray-300 bg-white px-3 py-2"
        >
          <option value="">Choose a branch</option>
          {locations.map((l) => (
            <option key={l.id} value={String(l.id)}>
              {l.name}
            </option>
          ))}
        </select>
        {field('location')}
      </label>

      {showEmail && (
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Email (optional)</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={Boolean(errors.email)}
            aria-describedby={described('email')}
            className="rounded border border-gray-300 px-3 py-2"
          />
          {field('email')}
        </label>
      )}

      {showDate && (
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Preferred date (optional)</span>
          <input
            type="date"
            min={todayIsoInIST()}
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2"
          />
        </label>
      )}

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">{messageLabel}</span>
        <textarea
          rows={3}
          maxLength={2000}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="rounded border border-gray-300 px-3 py-2"
        />
      </label>

      {/* Honeypot: off-screen and hidden from assistive tech; people never fill it. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
        <label>
          Website
          <input
            type="text"
            name="website"
            tabIndex={-1}
            autoComplete="off"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
        </label>
      </div>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="rounded-full bg-festive-hero px-5 py-2.5 font-semibold text-white shadow-sm transition hover:opacity-90 disabled:opacity-40"
      >
        {submitting ? 'Sending…' : submitLabel}
      </button>
    </form>
  );
}
