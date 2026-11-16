import type { DecorCategory, DecorSelection, SpecialDecor } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

/**
 * Special decor grouped by category, rendered in a fixed order (Extra
 * Decoration → Choose Gifts → Special Services), each a labeled section. Items
 * render as image cards, two per row on mobile. Tap a card to add it (quantity
 * 1); a small inline "− 1 +" stepper appears only once an item is selected, so
 * the common single-quantity case stays one tap and multi-quantity (party
 * popper, sash) is a couple of taps. Empty categories are omitted. All pricing
 * is server-side; the client sends only ids + quantities.
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

  const toggleDecor = (id: number) => {
    if (findDecor(id)) {
      onChangeDecor(decor.filter((d) => d.id !== id));
    } else {
      onChangeDecor([...decor, { id, quantity: 1 }]);
    }
  };

  const setQuantity = (id: number, quantity: number) => {
    if (quantity < 1) {
      // Dropping below 1 removes the item.
      onChangeDecor(decor.filter((d) => d.id !== id));
      return;
    }
    onChangeDecor(decor.map((d) => (d.id === id ? { ...d, quantity } : d)));
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
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {items.map((item) => {
              const selection = findDecor(item.id);
              const selected = selection !== undefined;
              return (
                <li key={item.id} className="flex flex-col">
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => toggleDecor(item.id)}
                    className={`flex w-full flex-col overflow-hidden rounded-xl border-2 text-left transition ${
                      selected
                        ? 'border-brand shadow-md'
                        : 'border-gray-200 hover:border-brand/60'
                    }`}
                  >
                    <div className="relative aspect-square w-full overflow-hidden bg-festive-hero">
                      {item.image_url ? (
                        <img
                          src={item.image_url}
                          alt={item.name}
                          loading="lazy"
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <span
                          aria-hidden="true"
                          className="flex h-full w-full items-center justify-center text-3xl"
                        >
                          🎀
                        </span>
                      )}
                      {selected && (
                        <span className="absolute right-1.5 top-1.5 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-brand shadow">
                          ✓
                        </span>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="text-sm font-medium text-gray-900">{item.name}</p>
                      <p className="text-xs text-gray-500">
                        {formatRupees(item.price_paise)}
                      </p>
                    </div>
                  </button>

                  {selected && (
                    <div className="mt-1.5 flex items-center justify-center gap-3">
                      <button
                        type="button"
                        aria-label={`Decrease quantity for ${item.name}`}
                        onClick={() => setQuantity(item.id, selection.quantity - 1)}
                        className="flex h-7 w-7 items-center justify-center rounded-full border border-gray-300 text-lg font-bold text-gray-700 transition hover:bg-gray-50"
                      >
                        −
                      </button>
                      <span
                        aria-label={`Quantity for ${item.name}`}
                        className="min-w-[1.5rem] text-center text-sm font-semibold"
                      >
                        {selection.quantity}
                      </span>
                      <button
                        type="button"
                        aria-label={`Increase quantity for ${item.name}`}
                        onClick={() => setQuantity(item.id, selection.quantity + 1)}
                        className="flex h-7 w-7 items-center justify-center rounded-full border border-gray-300 text-lg font-bold text-gray-700 transition hover:bg-gray-50"
                      >
                        +
                      </button>
                    </div>
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
