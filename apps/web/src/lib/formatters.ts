/**
 * Display formatters for the customer site.
 *
 * Self-contained: these use only the native `Intl` API (no date library) so
 * they stay cheap in the booking-page bundle and are trivially unit-testable.
 * The API exchanges integer paise; the UI converts to rupees for display only.
 */

const PAISE_PER_RUPEE = 100;
const IST_TIME_ZONE = 'Asia/Kolkata';

const rupeeFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST_TIME_ZONE,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});

const isoPartsFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: IST_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

/**
 * Format integer paise as an INR currency string (en-IN), e.g. 50000 ->
 * "₹500.00". Handles zero, large values, and negative values (used to show an
 * overpaid balance). `Intl.NumberFormat` renders the leading minus sign.
 */
export function formatRupees(paise: number): string {
  return rupeeFormatter.format(paise / PAISE_PER_RUPEE);
}

/**
 * Format an ISO date or datetime string for display in IST, e.g.
 * "25 Dec 2025". Accepts `YYYY-MM-DD` (interpreted at IST midnight) and full
 * ISO timestamps.
 */
export function formatDate(iso: string): string {
  const parsed =
    iso.length === 10 ? new Date(`${iso}T00:00:00+05:30`) : new Date(iso);
  return dateFormatter.format(parsed);
}

/** Return today's calendar date in IST as a `YYYY-MM-DD` string. */
export function todayIsoInIST(): string {
  return isoPartsFormatter.format(new Date());
}
