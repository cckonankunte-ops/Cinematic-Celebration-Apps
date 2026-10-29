/**
 * Build a WhatsApp click-to-chat URL carrying a booking confirmation message.
 * Staff tap the WhatsApp button on a booking row to open WhatsApp with the
 * customer's number prefilled and a ready-to-send confirmation. The message
 * mirrors the legacy confirmation format (bold `*...*` markers render in
 * WhatsApp). All content comes from the booking's own details.
 */

import { formatDate } from './dates';

/** Minimal booking shape needed to compose a confirmation message. */
export interface BookingLike {
  booking_name: string;
  booking_reference: string;
  plan_title: string;
  /** Combo add-on names, appended to the plan as the "Space" line. */
  combos?: string[];
  occasion_name?: string | null;
  booking_date: string;
  special_person_name?: string | null;
  /** Cake add-on names (a booking carries at most one cake). */
  cakes?: string[];
  name_on_cake?: string | null;
  /** Cake weight in half-kg units (1 = 0.5 kg … 6 = 3 kg). */
  cake_weight_half_kg?: number | null;
  slot_description: string;
  /** Customer phone (any format); non-digits are stripped for the wa.me path. */
  phone?: string | null;
  /** Google Maps share link for the booking's location. */
  map_url?: string | null;
}

const NOTE =
  'Note: Party Poppers (Blasters) and Spray not allowed from outside.';
const REFUND_POLICY_URL = 'https://cinematiccelebration.in/refund-policy';

// Emoji as Unicode escapes so the source can't be corrupted by editor/encoding
// issues (which previously turned 🥳 into mojibake in the sent message).
const PARTY = '\u{1F973}'; // 🥳
const STAR_STRUCK = '\u{1F929}'; // 🤩
const HUGGING = '\u{1F917}'; // 🤗

/**
 * Wrap a value in WhatsApp bold markers. WhatsApp only renders `*text*` as bold
 * when the asterisks sit directly against non-space characters, so the value is
 * trimmed first — otherwise a stray leading/trailing space leaves the literal
 * `*` visible and the text un-bolded.
 */
function bold(value: string): string {
  return `*${value.trim()}*`;
}

/** Render cake weight half-kg units as a human label, e.g. 1 -> "1/2 KG". */
function cakeWeightLabel(halfKg: number): string {
  return halfKg % 2 === 0 ? `${halfKg / 2} KG` : `${halfKg}/2 KG`;
}

/**
 * Compose the "Space" line: the plan title plus any combo names, joined with
 * " + " and suffixed with " Package" to match the legacy format.
 */
function spaceLine(plan: string, combos: string[] | undefined): string {
  const parts = [plan, ...(combos ?? [])];
  return `${parts.join(' + ')} Package`;
}

/**
 * Compose the "Cake details" value: "<cake name> | <name on cake> <weight>".
 * Returns null when there's no cake so the line can be omitted.
 */
function cakeDetails(booking: BookingLike): string | null {
  const name = booking.cakes?.[0];
  if (!name) {
    return null;
  }
  const bits = [name];
  const onCake = booking.name_on_cake?.trim();
  const weight =
    booking.cake_weight_half_kg != null
      ? cakeWeightLabel(booking.cake_weight_half_kg)
      : null;
  const tail = [onCake, weight].filter(Boolean).join(' ');
  if (tail) {
    bits.push(tail);
  }
  return bits.join(' | ');
}

/**
 * Compose the human-readable confirmation message matching the legacy format.
 * Optional lines (occasion, special person, cake, location) are only included
 * when present so the message stays clean.
 */
export function buildWhatsappMessage(booking: BookingLike): string {
  const lines: string[] = [
    `Your Booking is confirmed${PARTY}`,
    '',
    `Booking name: ${bold(booking.booking_name)}`,
    `Booking Id: ${bold(booking.booking_reference)}`,
    `Space: ${bold(spaceLine(booking.plan_title, booking.combos))}`,
  ];
  if (booking.occasion_name) {
    lines.push(`Occasion: ${bold(booking.occasion_name)}`);
  }
  lines.push(`Date: ${bold(formatDate(booking.booking_date))}`);
  if (booking.special_person_name?.trim()) {
    lines.push(`Special person name: ${bold(booking.special_person_name)}`);
  }
  const cake = cakeDetails(booking);
  if (cake) {
    lines.push(`Cake details: ${bold(cake)}`);
  }
  lines.push(`Slot: ${bold(booking.slot_description)}`);
  if (booking.map_url?.trim()) {
    lines.push(`Location: ${booking.map_url.trim()}`);
  }
  lines.push('');
  lines.push(bold(NOTE));
  lines.push(`Refund Policy: ${REFUND_POLICY_URL}`);
  lines.push('');
  lines.push(
    "If you have any questions or concerns, please don't hesitate to contact us.",
  );
  lines.push(`We look forward to hosting you ${STAR_STRUCK}${HUGGING}`);
  lines.push('');
  lines.push('Warmly,');
  lines.push('Cinematic Celebration Team');
  return lines.join('\n');
}

/**
 * Normalise an Indian phone number to the wa.me digits form (country code +
 * national number, no symbols). A bare 10-digit number is prefixed with 91.
 * Returns '' when no usable number is present (caller falls back to no number).
 */
export function waPhoneDigits(phone: string | null | undefined): string {
  if (!phone) {
    return '';
  }
  const digits = phone.replace(/\D/g, '');
  if (digits.length === 10) {
    return `91${digits}`;
  }
  // Strip a leading 0 before a 10-digit national number (e.g. 0 98765...).
  if (digits.length === 11 && digits.startsWith('0')) {
    return `91${digits.slice(1)}`;
  }
  return digits;
}

/**
 * Build a `https://wa.me/<number>?text=...` URL. When the number can't be
 * resolved, falls back to `https://wa.me/?text=...` (WhatsApp prompts for a
 * recipient) so the button still works.
 */
export function buildWhatsappUrl(booking: BookingLike): string {
  const text = encodeURIComponent(buildWhatsappMessage(booking));
  const number = waPhoneDigits(booking.phone);
  return number
    ? `https://wa.me/${number}?text=${text}`
    : `https://wa.me/?text=${text}`;
}
