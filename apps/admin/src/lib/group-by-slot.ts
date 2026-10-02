/**
 * Group operational-sheet rows by slot for the timesheet and cakesheet views.
 *
 * Both sheets return flat rows carrying `slot_id`, `slot_sort_order`, and
 * `slot_description`; the UI renders them under per-slot headers ordered by
 * `slot_sort_order` ascending (ties broken by `slot_id` for stability). This
 * generic helper keeps that grouping logic in one place.
 */

/** The minimal slot fields every sheet row carries. */
export interface SlotKeyed {
  slot_id: number;
  slot_sort_order: number;
  slot_description: string;
}

/** A slot header plus its rows, ready to render. */
export interface SlotGroup<T extends SlotKeyed> {
  slotId: number;
  slotSortOrder: number;
  slotDescription: string;
  rows: T[];
}

/**
 * Group rows by `slot_id`, returning groups ordered by `slot_sort_order` asc
 * (then `slot_id` asc). Row order within each group is preserved.
 */
export function groupBySlot<T extends SlotKeyed>(rows: T[]): Array<SlotGroup<T>> {
  const groups = new Map<number, SlotGroup<T>>();
  for (const row of rows) {
    const existing = groups.get(row.slot_id);
    if (existing) {
      existing.rows.push(row);
    } else {
      groups.set(row.slot_id, {
        slotId: row.slot_id,
        slotSortOrder: row.slot_sort_order,
        slotDescription: row.slot_description,
        rows: [row],
      });
    }
  }
  return [...groups.values()].sort(
    (a, b) => a.slotSortOrder - b.slotSortOrder || a.slotId - b.slotId,
  );
}
