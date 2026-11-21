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

const dateTimeFormatter = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST_TIME_ZONE,
  day: '2-digit',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

const timeFormatter = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST_TIME_ZONE,
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

const istPartsFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: IST_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

/** "14 Nov, 3:30 pm" in IST, from an ISO timestamp. */
export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

/** "3:30 pm" in IST, from an ISO timestamp. */
export function formatTime(iso: string): string {
  return timeFormatter.format(new Date(iso));
}

/** IST calendar date (`YYYY-MM-DD`) of an instant. */
export function istDateOf(date: Date): string {
  return isoPartsFormatter.format(date);
}

/** IST wall-clock parts of an instant: `{ date: 'YYYY-MM-DD', time: 'HH:MM' }`. */
export function istParts(date: Date): { date: string; time: string } {
  const parts = Object.fromEntries(
    istPartsFormatter.formatToParts(date).map((p) => [p.type, p.value]),
  );
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${parts.hour}:${parts.minute}`,
  };
}

/** UTC ISO timestamp for an IST wall-clock date (`YYYY-MM-DD`) and time (`HH:MM`). */
export function istToIso(date: string, time: string): string {
  return new Date(`${date}T${time}:00+05:30`).toISOString();
}

/** `YYYY-MM-DDTHH:MM` in IST for a `datetime-local` input, from an ISO timestamp. */
export function toIstInputValue(iso: string): string {
  const { date, time } = istParts(new Date(iso));
  return `${date}T${time}`;
}
