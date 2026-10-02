import { describe, expect, it } from 'vitest';

import { groupBySlot, type SlotKeyed } from './group-by-slot';

interface Row extends SlotKeyed {
  label: string;
}

function row(
  slotId: number,
  sortOrder: number,
  label: string,
  description = `slot-${slotId}`,
): Row {
  return {
    slot_id: slotId,
    slot_sort_order: sortOrder,
    slot_description: description,
    label,
  };
}

describe('groupBySlot', () => {
  it('groups rows by slot id and preserves row order within a group', () => {
    const groups = groupBySlot([
      row(1, 0, 'a'),
      row(1, 0, 'b'),
      row(2, 1, 'c'),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0].slotId).toBe(1);
    expect(groups[0].rows.map((r) => r.label)).toEqual(['a', 'b']);
    expect(groups[1].rows.map((r) => r.label)).toEqual(['c']);
  });

  it('orders groups by slot sort order ascending', () => {
    const groups = groupBySlot([
      row(3, 2, 'late'),
      row(1, 0, 'early'),
      row(2, 1, 'mid'),
    ]);

    expect(groups.map((g) => g.slotId)).toEqual([1, 2, 3]);
  });

  it('breaks sort-order ties by slot id for stability', () => {
    const groups = groupBySlot([row(5, 0, 'x'), row(2, 0, 'y')]);

    expect(groups.map((g) => g.slotId)).toEqual([2, 5]);
  });

  it('returns an empty array for no rows', () => {
    expect(groupBySlot<Row>([])).toEqual([]);
  });
});
