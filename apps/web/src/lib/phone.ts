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
