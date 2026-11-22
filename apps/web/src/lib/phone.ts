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
 * Build a `tel:` href from a raw phone string, always as `+91` + the 10-digit
 * Indian mobile. Strips non-digits, drops a leading `91` country code or a
 * leading `0` trunk prefix, and keeps the last 10 digits. Returns null when
 * there is no usable 10-digit number so callers can omit the link entirely.
 *
 * Examples: "9876543210" -> tel:+919876543210; "09876543210" ->
 * tel:+919876543210; "+91 98765 43210" -> tel:+919876543210.
 */
export function telHref(raw: string | null | undefined): string | null {
  let digits = String(raw ?? '').replace(/\D/g, '');
  if (digits.length === 0) {
    return null;
  }
  // Drop an explicit country code or trunk prefix so we're left with the
  // national 10-digit number, then re-apply a single +91.
  if (digits.length > 10 && digits.startsWith('91')) {
    digits = digits.slice(2);
  }
  digits = digits.replace(/^0+/, '');
  if (digits.length !== 10) {
    // Not a recognizable 10-digit Indian mobile; don't produce a broken link.
    return null;
  }
  return `tel:+91${digits}`;
}

/**
 * Normalise a raw phone to the canonical 10-digit Indian mobile, or null.
 *
 * Same rule as the server's `normalize_indian_mobile` (app/core/phone.py):
 * strip spaces and dashes, drop one leading `+91`, `91` (only when longer than
 * 10 digits) or `0`s, keep the last 10 digits, and require a 6-9 first digit.
 */
export function normaliseIndianMobile(raw: string | null | undefined): string | null {
  if (raw === null || raw === undefined) {
    return null;
  }
  let s = raw.trim().replace(/[\s-]/g, '');
  if (s.startsWith('+91')) {
    s = s.slice(3);
  } else if (s.startsWith('91') && s.length > 10) {
    s = s.slice(2);
  } else if (s.startsWith('0')) {
    s = s.replace(/^0+/, '');
  }
  const last10 = s.replace(/\D/g, '').slice(-10);
  return /^[6-9]\d{9}$/.test(last10) ? last10 : null;
}
