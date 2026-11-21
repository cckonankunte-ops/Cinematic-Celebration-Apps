/**
 * Analytics domain types, mirroring the API's analytics schemas
 * (`schemas/analytics.py`). Admin-only. Money stays in integer paise;
 * `amount_due_paise` may be negative to represent an overpayment.
 *
 * `*_by_method` maps are keyed by payment method (cash, upi, card, other, and
 * any method added later), so new methods show up without code changes.
 */

export type BookingStatusName =
  | 'pending'
  | 'accepted'
  | 'rejected'
  | 'expired'
  | 'cancelled';

export type MethodAmounts = Record<string, number>;

export interface AnalyticsSummary {
  booking_count: number;
  total_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
  discount_paise: number;
  food_paise: number;
  cleaning_paise: number;
  other_paise: number;
  paid_by_method: MethodAmounts;
}

/** Slot amount: bookings whose celebration date is in the range. */
export interface SlotAmountRow {
  booking_name: string;
  booking_reference: string;
  booking_date: string;
  status: string;
  total_paise: number;
  amount_paid_paise: number;
  paid_by_method: MethodAmounts;
  amount_due_paise: number; // may be negative = overpaid
  discount_paise: number;
  food_paise: number;
  cleaning_paise: number;
  other_paise: number;
}

export interface SlotAmountsResult {
  rows: SlotAmountRow[];
  summary: AnalyticsSummary;
}

/** Bookings created in the range, with what they ordered. */
export interface CreatedBookingRow {
  booking_name: string;
  booking_reference: string;
  created_at: string;
  booking_date: string;
  status: string;
  plan_title: string;
  cake: string | null;
  special_decor: string[];
  combos: string[];
  total_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
}

export interface CreatedBookingsResult {
  rows: CreatedBookingRow[];
  summary: AnalyticsSummary;
}

/** Payments received in the range. */
export interface TodayIncomeRow {
  booking_name: string;
  booking_reference: string;
  booking_date: string;
  status: string;
  received_paise: number;
  received_by_method: MethodAmounts;
  total_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
}

export interface TodayIncomeSummary {
  booking_count: number;
  payment_count: number;
  received_paise: number;
  received_by_method: MethodAmounts;
}

export interface TodayIncomeResult {
  rows: TodayIncomeRow[];
  summary: TodayIncomeSummary;
}

/** Shared filter state for the analytics page. */
export interface AnalyticsFilters {
  dateFrom: string;
  dateTo: string;
  statuses: BookingStatusName[];
}
