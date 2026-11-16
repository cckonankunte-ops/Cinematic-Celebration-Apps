/**
 * Indian-mobile validity check for the customer booking flow.
 *
 * Mirrors the server's `normalize_indian_mobile` rule: strip spaces and dashes,
 * allow a single optional `+91` / `91` / `0` prefix, and require the last 10
 * digits to start with 6-9. The UI uses this to gate submission and to show an
 * inline hint; the server remains authoritative.
 */

const INDIAN_MOBILE = /^(\+?91|0)?[6-9]\d{9}$/;

/** Return true iff `raw` is a valid Indian mobile number (lenient on format). */
export function isValidIndianMobile(raw: string): boolean {
  const despaced = raw.replace(/[\s-]/g, '');
  return INDIAN_MOBILE.test(despaced);
}

/**
 * Build a `tel:` href from a raw phone string. Strips non-digits; a bare
 * 10-digit Indian mobile is prefixed with the `91` country code (mirrors the
 * WhatsApp FAB's `waDigits` and LocationList's tel: logic). Returns null when
 * there are no digits so callers can omit the link entirely.
 */
export function telHref(raw: string | null | undefined): string | null {
  const digits = String(raw ?? '').replace(/\D/g, '');
  if (digits.length === 0) {
    return null;
  }
  const normalized = digits.length === 10 ? `91${digits}` : digits.replace(/^0+/, '');
  return `tel:+${normalized}`;
}
