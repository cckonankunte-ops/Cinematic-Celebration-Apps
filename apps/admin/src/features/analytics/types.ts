/**
 * Analytics domain types, mirroring the API's analytics schemas
 * (`schemas/analytics.py`). Admin-only. Money stays in integer paise;
 * `amount_due_paise` may be negative to represent an overpayment.
 */

/** One row of the daily slot-amount report. */
export interface SlotAmountRow {
  booking_name: string;
  booking_reference: string;
  total_paise: number;
  amount_paid_paise: number;
  today_income_paise: number;
  amount_due_paise: number; // may be negative = overpaid
  discount_paise: number;
  food_paise: number;
  cleaning_paise: number;
  other_paise: number;
  created_at: string;
}

/** One row of the daily advance-amount report. */
export interface AdvanceAmountRow {
  booking_name: string;
  booking_reference: string;
  total_paise: number;
  amount_paid_paise: number;
  created_at: string;
}

/** Day-summary totals shared by both reports (slot report uses every field). */
export interface AnalyticsDaySummary {
  total_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
  discount_paise: number;
  food_paise: number;
  cleaning_paise: number;
  other_paise: number;
}

export interface SlotAmountsResult {
  rows: SlotAmountRow[];
  summary: AnalyticsDaySummary;
}

export interface AdvanceAmountsResult {
  rows: AdvanceAmountRow[];
  summary: AnalyticsDaySummary;
}
