/**
 * Booking + payment read types mirroring the API response schemas. These are
 * hand-written here to keep the feature typed in the meantime.
 *
 * `npm run gen:api` regenerates `src/api/schema.ts` from the live OpenAPI
 * schema (the real source of truth) and should be run in the Codespace once the
 * API is up. These hand-written types mirror that generated schema until then.
 */

export type BookingStatus = 'pending' | 'accepted' | 'rejected' | 'expired';

export type PaymentMethod = 'cash' | 'upi' | 'card' | 'other';

/** One add-on line item snapshot on a booking. Mirrors `BookingItemRead`. */
export interface BookingItem {
  kind: string;
  item_id: number | null;
  name_snapshot: string;
  price_paise: number;
  quantity: number;
  weight_half_kg: number | null;
}

/** Mirrors the API `BookingRead`. */
export interface BookingRead {
  id: number;
  booking_reference: string;
  public_token: string;
  location_id: number;
  plan_id: number;
  slot_id: number;
  booking_date: string;
  status: BookingStatus;
  booking_name: string;
  email: string | null;
  phone: string | null;
  people: number;
  occasion_id: number | null;
  plan_price_paise: number;
  extra_guest_paise: number;
  subtotal_paise: number;
  discount_paise: number;
  food_paise: number;
  other_paise: number;
  cleaning_paise: number;
  led_name: string | null;
  coupon_code: string | null;
  coupon_discount_paise: number;
  total_paise: number;
  advance_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
  is_paid: boolean;
  items: BookingItem[];
  payments: PaymentRead[];
  created_at: string;
}

/**
 * Mirrors the API `BookingListItem`. The payment-derived fields may be absent
 * on some deployments, so they are optional and handled defensively in the UI.
 */
export interface BookingListItem {
  id: number;
  booking_reference: string;
  booking_date: string;
  slot_id?: number;
  status: BookingStatus;
  booking_name: string;
  phone?: string | null;
  people: number;
  total_paise: number;
  advance_paise?: number;
  amount_paid_paise?: number;
  amount_due_paise?: number;
  is_paid?: boolean;
}

/** Mirrors the API `PaymentRead`. */
export interface PaymentRead {
  id: number;
  booking_id: number;
  method: string;
  amount_paise: number;
  received_at: string;
  recorded_by_user_id: number | null;
  provider: string | null;
  provider_ref: string | null;
  note: string | null;
  reverses_payment_id: number | null;
  is_voided: boolean;
  voided_by_payment_id: number | null;
}

/** One priced add-on line in a breakdown. Mirrors the API `AddonLineRead`. */
export interface AddonLineRead {
  kind: string;
  item_id: number | null;
  name_snapshot: string;
  unit_price_paise: number;
  quantity: number;
  weight_half_kg: number | null;
  amount_paise: number;
}

/** Full server-computed price breakdown. Mirrors the API `PriceBreakdownRead`. */
export interface PriceBreakdownRead {
  plan_price_paise: number;
  extra_guest_paise: number;
  addon_lines: AddonLineRead[];
  subtotal_paise: number;
  discount_paise: number;
  food_paise: number;
  other_paise: number;
  cleaning_paise: number;
  coupon_code: string | null;
  coupon_discount_paise: number;
  total_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
}
