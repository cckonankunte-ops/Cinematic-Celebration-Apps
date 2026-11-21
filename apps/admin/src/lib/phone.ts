/**
 * Indian mobile normalisation, same rule as the API (`app/core/phone.py`):
 * strip spaces and dashes, drop one leading `+91`, `91` (only when longer than
 * 10 digits) or `0`s, keep the last 10 digits, and require a 6-9 first digit.
 * "+91 98765 43210", "098765 43210" and "9876543210" all give "9876543210".
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
