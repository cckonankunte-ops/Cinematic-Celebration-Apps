import { useState } from 'react';

import type { DecorCategory, DecorSelection, SpecialDecor } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

/**
 * Special decor grouped by category, rendered in a fixed order (Extra
 * Decoration → Choose Gifts → Special Service), each a labeled section stacked
 * vertically (single column on mobile). Empty categories are omitted. The
 * customer picks items + quantities; all pricing is server-side.
 */
interface Props {
  specialDecor: SpecialDecor[];
  decor: DecorSelection[];
  onChangeDecor: (next: DecorSelection[]) => void;
}

const CATEGORY_ORDER: DecorCategory[] = [
  'extra_decoration',
  'gifts',
  'special_service',
];

const CATEGORY_LABELS: Record<DecorCategory, string> = {
  extra_decoration: 'Extra Decoration',
  gifts: 'Choose Gifts',
  special_service: 'Special Services',
};

export default function DecorByCategory({
  specialDecor,
  decor,
  onChangeDecor,
}: Props) {
  const findDecor = (id: number): DecorSelection | undefined =>
    decor.find((d) => d.id === id);

  // Raw text per decor id while editing quantity (lets mobile users clear "1").
  const [qtyDrafts, setQtyDrafts] = useState<Record<number, string>>({});

  const toggleDecor = (id: number) => {
    if (findDecor(id)) {
      onChangeDecor(decor.filter((d) => d.id !== id));
      setQtyDrafts((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } else {
      onChangeDecor([...decor, { id, quantity: 1 }]);
    }
  };

  const commitQuantity = (id: number, quantity: number) => {
    onChangeDecor(decor.map((d) => (d.id === id ? { ...d, quantity } : d)));
  };

  const onQuantityInput = (id: number, raw: string) => {
    setQtyDrafts((prev) => ({ ...prev, [id]: raw }));
    const parsed = Number(raw);
    if (raw !== '' && Number.isInteger(parsed) && parsed >= 1) {
      commitQuantity(id, parsed);
    }
  };

  const onQuantityBlur = (id: number) => {
    const raw = qtyDrafts[id];
    if (raw !== undefined) {
      const parsed = Number(raw);
      const resolved =
        raw !== '' && Number.isInteger(parsed) && parsed >= 1 ? parsed : 1;
      commitQuantity(id, resolved);
      setQtyDrafts((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  };

  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: specialDecor.filter((d) => d.category === category),
  })).filter((g) => g.items.length > 0);

  if (groups.length === 0) {
    return <p className="text-sm text-gray-500">No special decor available.</p>;
  }

  return (
    <div className="space-y-5">
      {groups.map(({ category, items }) => (
        <section key={category}>
          <h4 className="mb-2 text-sm font-semibold text-gray-900">
            {CATEGORY_LABELS[category]}
          </h4>
          <ul className="space-y-2">
            {items.map((item) => {
              const selection = findDecor(item.id);
              const selected = selection !== undefined;
              return (
                <li key={item.id} className="flex items-center gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleDecor(item.id)}
                    />
                    <span>
                      {item.name} — {formatRupees(item.price_paise)}
                    </span>
                  </label>
                  {selected && (
                    <label className="flex items-center gap-1 text-sm">
                      <span className="sr-only">Quantity for {item.name}</span>
                      <span aria-hidden="true">×</span>
                      <input
                        type="number"
                        inputMode="numeric"
                        min={1}
                        value={qtyDrafts[item.id] ?? String(selection.quantity)}
                        onChange={(e) => onQuantityInput(item.id, e.target.value)}
                        onBlur={() => onQuantityBlur(item.id)}
                        aria-label={`Quantity for ${item.name}`}
                        className="w-16 rounded border border-gray-300 px-2 py-1"
                      />
                    </label>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
