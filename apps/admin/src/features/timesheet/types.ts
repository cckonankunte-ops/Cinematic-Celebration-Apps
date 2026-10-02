/**
 * Timesheet domain types, mirroring the API's `TimesheetRow` schema
 * (`schemas/sheets.py`). Money stays in integer paise; the UI converts to
 * rupees for display. `slot_sort_order` + `slot_description` let the UI group
 * rows by slot without a second query.
 */

export interface TimesheetRow {
  slot_id: number;
  slot_sort_order: number;
  slot_description: string;
  plan_title: string;
  booking_name: string;
  phone: string | null;
  people: number;
  name_on_cake: string | null;
  cake: string | null;
  special_decor: string | null;
  combos: string | null;
  occasion: string | null;
  amount_due_paise: number;
}
