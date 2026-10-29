import { describe, expect, it } from 'vitest';

import { bookingCreateSchema, paymentFormSchema } from './booking-schema';

/**
 * A minimal valid admin booking payload mirroring `AdminBookingCreate`. Phone
 * is now required; email is optional (omitted here on purpose).
 */
function validPayload(): Record<string, unknown> {
  return {
    location_id: 1,
    plan_id: 3,
    slot_id: 7,
    booking_date: '2025-12-25',
    booking_name: 'Priya S',
    phone: '9876543210',
    people: 4,
  };
}

describe('bookingCreateSchema', () => {
  it('accepts a valid minimal payload and applies money/array defaults', () => {
    const parsed = bookingCreateSchema.parse(validPayload());
    expect(parsed.special_decor).toEqual([]);
    expect(parsed.combos).toEqual([]);
    expect(parsed.cake_weight_half_kg).toBe(1);
    expect(parsed.discount_rupees).toBe(0);
    expect(parsed.food_rupees).toBe(0);
    expect(parsed.other_rupees).toBe(0);
    expect(parsed.cleaning_rupees).toBe(0);
  });

  it('accepts a full payload with add-ons and extra charges', () => {
    const result = bookingCreateSchema.safeParse({
      ...validPayload(),
      email: 'customer@example.com',
      occasion_id: 2,
      cake_id: 4,
      cake_weight_half_kg: 2,
      special_decor: [{ id: 1, quantity: 2 }],
      combos: [{ id: 2 }],
      led_name: 'HAPPY',
      coupon_code: 'SAVE10',
      discount_rupees: 50,
      food_rupees: 200,
      other_rupees: 0,
      cleaning_rupees: 100,
    });
    expect(result.success).toBe(true);
  });

  it('keeps the special_decor quantity on a parsed payload', () => {
    const parsed = bookingCreateSchema.parse({
      ...validPayload(),
      special_decor: [{ id: 1, quantity: 2 }],
    });
    expect(parsed.special_decor).toEqual([{ id: 1, quantity: 2 }]);
  });

  it('accepts a payload with a phone and no email', () => {
    const { email: _omit, ...rest } = { ...validPayload(), email: undefined };
    const result = bookingCreateSchema.safeParse(rest);
    expect(result.success).toBe(true);
  });

  it('rejects a payload with no phone', () => {
    const { phone: _omit, ...rest } = validPayload();
    expect(bookingCreateSchema.safeParse(rest).success).toBe(false);
  });

  it('rejects an invalid phone number', () => {
    const result = bookingCreateSchema.safeParse({ ...validPayload(), phone: '12345' });
    expect(result.success).toBe(false);
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
      discount_rupees: -1,
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
