/**
 * Zod schemas for the admin booking forms. These mirror the API's
 * `AdminBookingCreate`, the accept request, and the payment-create body so the
 * client validates with the same rules the server enforces. The server remains
 * authoritative on all money; these schemas only guard the request shape.
 */

import { z } from 'zod';

/** `YYYY-MM-DD` calendar date (interpreted in Asia/Kolkata by the API). */
const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be YYYY-MM-DD');

/**
 * A non-negative rupee amount from a number input (whole or decimal). Empty
 * inputs yield NaN via `valueAsNumber`; those coerce to 0 so an untouched
 * optional money field defaults cleanly. Mapped to paise before sending.
 */
const nonNegativeRupees = z.preprocess(
  (v) =>
    v === '' || v === null || (typeof v === 'number' && Number.isNaN(v))
      ? 0
      : v,
  z
    .number({ invalid_type_error: 'Must be a number' })
    .min(0, 'Cannot be negative')
    .default(0),
);

const optionalText = z
  .string()
  .trim()
  .optional()
  .transform((v) => (v === undefined || v.length === 0 ? undefined : v));

/**
 * Indian mobile number. Lenient on input (accepts spaces/dashes and an optional
 * `+91`/`91`/`0` prefix) but mirrors the server's normalize rule: after
 * stripping spaces/dashes and the optional prefix, the last 10 digits must
 * start with 6-9.
 */
const indianMobile = z
  .string()
  .trim()
  .min(1, 'Phone is required')
  .refine(
    (v) => /^(\+?91|0)?[6-9]\d{9}$/.test(v.replace(/[\s-]/g, '')),
    'Enter a valid Indian mobile number',
  );

/**
 * Optional positive integer id from a `<select>`. An unselected option yields
 * an empty string or `NaN` via `valueAsNumber`; both coerce to `undefined` so
 * the field is simply omitted from the request.
 */
const optionalId = z.preprocess(
  (v) =>
    v === '' || v === null || (typeof v === 'number' && Number.isNaN(v)) ? undefined : v,
  z.number().int().positive().optional(),
);

/** Mirrors `AdminBookingCreate`. All money fields are integer paise. */
export const bookingCreateSchema = z.object({
  location_id: z.number().int().positive(),
  plan_id: z.number().int().positive(),
  slot_id: z.number().int().positive(),
  booking_date: isoDate,
  booking_name: z.string().trim().min(1, 'Name is required'),
  email: optionalText,
  phone: indianMobile,
  special_person_name: optionalText,
  name_on_cake: optionalText,
  message: optionalText,
  people: z
    .number({ invalid_type_error: 'People is required' })
    .int('Must be a whole number')
    .min(1, 'At least 1 person'),
  occasion_id: optionalId,
  cake_id: optionalId,
  cake_weight_half_kg: z.number().int().min(1).default(1),
  led_name: optionalText,
  coupon_code: optionalText,
  special_decor: z
    .array(
      z.object({
        id: z.number().int().positive(),
        quantity: z.number().int().min(1),
      }),
    )
    .default([]),
  combos: z.array(z.object({ id: z.number().int().positive() })).default([]),
  // Entered in rupees in the UI (whole or 2-decimal, e.g. 20 or 20.5); mapped
  // to the API's `*_paise` fields via rupeesToPaise before the request is sent.
  // An untouched/empty input yields NaN via valueAsNumber; coerce NaN/'' to 0.
  discount_rupees: nonNegativeRupees,
  food_rupees: nonNegativeRupees,
  other_rupees: nonNegativeRupees,
  cleaning_rupees: nonNegativeRupees,
  // Optional advance recorded at creation (create flow only). Entered in rupees
  // in the UI (like PaymentDialog); mapped to `advance_amount_paise` before the
  // request is sent. Method defaults to cash.
  // Empty number inputs yield NaN via `valueAsNumber`; coerce NaN/'' to
  // undefined so an untouched optional advance field doesn't fail validation.
  advance_rupees: z.preprocess(
    (v) =>
      v === '' || v === null || (typeof v === 'number' && Number.isNaN(v))
        ? undefined
        : v,
    z
      .number({ invalid_type_error: 'Must be a number' })
      .positive('Advance must be greater than zero')
      .optional(),
  ),
  advance_method: z.enum(['cash', 'upi', 'card', 'other']).default('cash'),
});

/** Input type before Zod applies defaults (what react-hook-form holds). */
export type BookingCreateInput = z.input<typeof bookingCreateSchema>;
/** Output type after parsing (what gets sent to the API). */
export type BookingCreateValues = z.output<typeof bookingCreateSchema>;

/** Mirrors `AcceptBookingRequest`. */
export const acceptSchema = z.object({
  override_advance: z.boolean().default(false),
});
export type AcceptValues = z.output<typeof acceptSchema>;

/** Mirrors the payment-create body; amount is entered in rupees in the UI. */
export const paymentFormSchema = z.object({
  method: z.enum(['cash', 'upi', 'card', 'other']),
  amount_rupees: z
    .number({ invalid_type_error: 'Amount is required' })
    .positive('Amount must be greater than zero'),
  note: optionalText,
});
export type PaymentFormValues = z.output<typeof paymentFormSchema>;

/** Mirrors `PaymentVoidRequest`; a blank/missing reason is rejected. */
export const paymentVoidSchema = z.object({
  reason: z.string().trim().min(1, 'A reason is required'),
});
export type PaymentVoidValues = z.output<typeof paymentVoidSchema>;
