/**
 * Quick-add lead form schema (lead-crm R4). Mirrors the API's `LeadCreate`:
 * the phone is normalised to 10 digits the same way as the server
 * (`app/core/phone.py`), so "+91 98765 43210" and "098765 43210" both work.
 */

import { z } from 'zod';

import { normaliseIndianMobile } from '@/lib/phone';
import { MANUAL_SOURCES, type ManualSource } from './types';

const ENQUIRY_CODE = /^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$/;

const optionalText = (max: number) =>
  z
    .string()
    .trim()
    .max(max, `Keep it under ${max} characters`)
    .optional()
    .transform((v) => (v ? v : undefined));

export const quickAddSchema = z.object({
  phone: z
    .string()
    .trim()
    .min(1, 'Phone is required')
    .refine((v) => normaliseIndianMobile(v) !== null, 'Enter a valid Indian mobile number')
    .transform((v) => normaliseIndianMobile(v) as string),
  source: z.enum(MANUAL_SOURCES as [ManualSource, ...ManualSource[]]),
  location_id: z.number({ invalid_type_error: 'Choose a branch' }).int().positive('Choose a branch'),
  name: optionalText(120),
  note: optionalText(2000),
  /** ISO timestamp from the follow-up picker, or empty for none. */
  follow_up_at: z
    .string()
    .optional()
    .transform((v) => (v ? v : undefined)),
  enquiry_code: z
    .string()
    .trim()
    .toUpperCase()
    .optional()
    .transform((v) => (v ? v : undefined))
    .refine((v) => v === undefined || ENQUIRY_CODE.test(v), 'Codes are 6 letters/digits, e.g. W4K7XQ'),
});

export type QuickAddInput = z.input<typeof quickAddSchema>;
export type QuickAddValues = z.output<typeof quickAddSchema>;
