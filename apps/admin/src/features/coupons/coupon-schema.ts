/**
 * Zod schema for the admin coupon authoring form. Mirrors the API's
 * `CouponBase`: a flat (paise) or percentage (0..100) discount, an optional cap
 * (paise), a percentage base, selectable components, validity dates, and usage
 * limits. The server remains authoritative on how the discount is computed and
 * validated at booking time; this only guards the authoring request shape.
 */

import { z } from 'zod';

/** `YYYY-MM-DD` calendar date, or omitted (open-ended validity). */
const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be YYYY-MM-DD');

const nonNegativePaise = z
  .number({ invalid_type_error: 'Must be a number' })
  .int('Must be a whole number of paise')
  .min(0, 'Cannot be negative');

const optionalDate = z
  .union([isoDate, z.literal('')])
  .optional()
  .transform((v) => (v === undefined || v === '' ? null : v));

const optionalNonNegative = z
  .union([nonNegativePaise, z.nan()])
  .optional()
  .transform((v) => (v === undefined || (typeof v === 'number' && Number.isNaN(v)) ? null : v));

const optionalLimit = z
  .union([z.number().int().min(0), z.nan()])
  .optional()
  .transform((v) => (v === undefined || (typeof v === 'number' && Number.isNaN(v)) ? null : v));

const componentsSchema = z.object({
  plan: z.boolean().default(false),
  extra_guest: z.boolean().default(false),
  decor: z.boolean().default(false),
  combos: z.boolean().default(false),
  cake: z.boolean().default(false),
  food: z.boolean().default(false),
});

export const couponFormSchema = z
  .object({
    code: z.string().trim().min(1, 'Code is required'),
    type: z.enum(['flat', 'percentage']),
    value: z
      .number({ invalid_type_error: 'Value is required' })
      .min(0, 'Cannot be negative'),
    cap_paise: optionalNonNegative,
    percentage_base: z.enum(['total', 'selected_components']),
    components: componentsSchema,
    effective_from: optionalDate,
    effective_to: optionalDate,
    is_active: z.boolean().default(true),
    one_time: z.boolean().default(false),
    total_usage_limit: optionalLimit,
    per_customer_limit: optionalLimit,
    min_order_paise: optionalNonNegative,
  })
  .refine(
    (data) => data.type !== 'percentage' || (data.value >= 0 && data.value <= 100),
    { path: ['value'], message: 'Percentage must be between 0 and 100' },
  );

/** Input type before Zod applies defaults (what react-hook-form holds). */
export type CouponFormInput = z.input<typeof couponFormSchema>;
/** Output type after parsing. */
export type CouponFormValues = z.output<typeof couponFormSchema>;
