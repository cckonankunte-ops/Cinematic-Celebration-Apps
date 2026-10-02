/**
 * Cakesheet domain types, mirroring the API's `CakesheetRow` schema
 * (`schemas/sheets.py`). `slot_sort_order` + `slot_description` let the UI group
 * cake orders by slot without a second query.
 */

export interface CakesheetRow {
  slot_id: number;
  slot_sort_order: number;
  slot_description: string;
  cake: string;
  name_on_cake: string | null;
}
