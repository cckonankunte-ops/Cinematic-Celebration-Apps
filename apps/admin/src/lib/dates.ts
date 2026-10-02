/**
 * Date helpers for the admin panel. Booking dates are plain calendar dates
 * interpreted in Asia/Kolkata (IST). We rely on the native `Intl` API so no
 * heavy date library is pulled into the bundle.
 */

const IST_TIME_ZONE = 'Asia/Kolkata';

const displayFormatter = new Intl.DateTimeFormat('en-IN', {
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
 * Format an ISO date or datetime string for display in IST, e.g.
 * "25 Dec 2025". Accepts both `YYYY-MM-DD` and full ISO timestamps.
 */
export function formatDate(iso: string): string {
  const parsed = iso.length === 10 ? new Date(`${iso}T00:00:00+05:30`) : new Date(iso);
  return displayFormatter.format(parsed);
}

/**
 * Return today's calendar date in IST as a `YYYY-MM-DD` string. `en-CA`
 * formats as ISO-ordered parts, which is exactly the shape we want.
 */
export function todayIsoInIST(): string {
  return isoPartsFormatter.format(new Date());
}
