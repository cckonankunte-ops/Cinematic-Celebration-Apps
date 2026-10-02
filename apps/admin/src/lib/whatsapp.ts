/**
 * Build a WhatsApp share URL carrying a booking confirmation message. Staff
 * tap the WhatsApp button on a booking to send the customer a prefilled
 * confirmation. All fields are URL-encoded via `encodeURIComponent`.
 */

import { formatDate } from './dates';

/** Minimal booking shape needed to compose a confirmation message. */
export interface BookingLike {
  booking_name: string;
  booking_reference: string;
  plan_title: string;
  occasion_name?: string | null;
  booking_date: string;
  slot_description: string;
  cake_name?: string | null;
  /** Optional map/location link to include in the message. */
  location_url?: string | null;
}

/**
 * Compose the human-readable confirmation message. Optional fields are only
 * included when present so the message stays clean.
 */
export function buildWhatsappMessage(booking: BookingLike): string {
  const lines: string[] = [
    `Hi ${booking.booking_name}, your Cinematic Celebration booking is confirmed!`,
    `Reference: ${booking.booking_reference}`,
    `Plan: ${booking.plan_title}`,
  ];
  if (booking.occasion_name) {
    lines.push(`Occasion: ${booking.occasion_name}`);
  }
  lines.push(`Date: ${formatDate(booking.booking_date)}`);
  lines.push(`Slot: ${booking.slot_description}`);
  if (booking.cake_name) {
    lines.push(`Cake: ${booking.cake_name}`);
  }
  if (booking.location_url) {
    lines.push(`Location: ${booking.location_url}`);
  }
  return lines.join('\n');
}

/** Build a `https://wa.me/?text=...` URL with the encoded message. */
export function buildWhatsappUrl(booking: BookingLike): string {
  const text = encodeURIComponent(buildWhatsappMessage(booking));
  return `https://wa.me/?text=${text}`;
}
