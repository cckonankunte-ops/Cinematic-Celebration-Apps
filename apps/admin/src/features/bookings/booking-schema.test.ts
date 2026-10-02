import { describe, expect, it } from 'vitest';

import { bookingCreateSchema, paymentFormSchema } from './booking-schema';

/** A minimal valid admin booking payload mirroring `AdminBookingCreate`. */
function validPayload(): Record<string, unknown> {
  return {
    location_id: 1,
    plan_id: 3,
    slot_id: 7,
    booking_date: '2025-12-25',
    booking_name: 'Priya S',
    email: 'customer@example.com',
    people: 4,
  };
}

describe('bookingCreateSchema', () => {
  it('accepts a valid minimal payload and applies money/array defaults', () => {
    const parsed = bookingCreateSchema.parse(validPayload());
    expect(parsed.special_decor_ids).toEqual([]);
    expect(parsed.combo_ids).toEqual([]);
    expect(parsed.discount_paise).toBe(0);
    expect(parsed.food_paise).toBe(0);
    expect(parsed.other_paise).toBe(0);
    expect(parsed.cleaning_paise).toBe(0);
  });

  it('accepts a full payload with add-ons and extra charges', () => {
    const result = bookingCreateSchema.safeParse({
      ...validPayload(),
      phone: '9876543210',
      occasion_id: 2,
      cake_id: 4,
      special_decor_ids: [1, 3],
      combo_ids: [2],
      discount_paise: 5000,
      food_paise: 20000,
      other_paise: 0,
      cleaning_paise: 10000,
    });
    expect(result.success).toBe(true);
  });

  it('rejects a missing required field (booking_name)', () => {
    const { booking_name: _omit, ...rest } = validPayload();
    expect(bookingCreateSchema.safeParse(rest).success).toBe(false);
  });

  it('rejects people < 1', () => {
    const result = bookingCreateSchema.safeParse({ ...validPayload(), people: 0 });
    expect(result.success).toBe(false);
  });

  it('rejects negative money fields', () => {
    const result = bookingCreateSchema.safeParse({
      ...validPayload(),
      discount_paise: -1,
    });
    expect(result.success).toBe(false);
  });

  it('rejects a malformed booking_date', () => {
    const result = bookingCreateSchema.safeParse({
      ...validPayload(),
      booking_date: '25-12-2025',
    });
    expect(result.success).toBe(false);
  });
});

describe('paymentFormSchema', () => {
  it('accepts a valid payment entry', () => {
    const result = paymentFormSchema.safeParse({ method: 'upi', amount_rupees: 500 });
    expect(result.success).toBe(true);
  });

  it('rejects a non-positive amount', () => {
    expect(paymentFormSchema.safeParse({ method: 'cash', amount_rupees: 0 }).success).toBe(
      false,
    );
  });

  it('rejects an unknown method', () => {
    const result = paymentFormSchema.safeParse({ method: 'cheque', amount_rupees: 100 });
    expect(result.success).toBe(false);
  });
});
