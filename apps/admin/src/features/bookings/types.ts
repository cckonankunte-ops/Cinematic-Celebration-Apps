/**
 * Booking + payment read types mirroring the API response schemas. These are
 * hand-written here (the generated `api/schema.ts` is the source of truth once
 * `npm run gen:api` runs, but these keep the feature typed in the meantime).
 */

export type BookingStatus = 'pending' | 'accepted' | 'rejected' | 'expired';

export type PaymentMethod = 'cash' | 'upi' | 'card' | 'other';

/** One add-on line item snapshot on a booking. */
export interface BookingItem {
  kind: string;
  item_id: number | null;
  name_snapshot: string;
  price_paise: number;
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
  email: string;
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
  total_paise: number;
  advance_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
  is_paid: boolean;
  items: BookingItem[];
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
}
