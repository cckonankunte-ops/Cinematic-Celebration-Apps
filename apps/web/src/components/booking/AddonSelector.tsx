import type { Cake, Combo, DecorSelection, SpecialDecor } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

interface Props {
  cakes: Cake[];
  specialDecor: SpecialDecor[];
  combos: Combo[];
  /** Combos are offered only when the chosen slot has show_combos = true. */
  showCombos: boolean;
  cakeId: number | null;
  cakeWeightHalfKg: number;
  decor: DecorSelection[];
  comboIds: number[];
  ledName: string;
  couponCode: string;
  onCakeChange: (cakeId: number | null) => void;
  onCakeWeightChange: (halfKg: number) => void;
  onChangeDecor: (next: DecorSelection[]) => void;
  onToggleCombo: (id: number) => void;
  onLedNameChange: (value: string) => void;
  onCouponChange: (value: string) => void;
}

/** Cake weight options: 0.5kg..3kg mapped to half-kg units 1..6. */
const CAKE_WEIGHT_OPTIONS: Array<{ halfKg: number; label: string }> = [
  { halfKg: 1, label: '0.5 kg' },
  { halfKg: 2, label: '1 kg' },
  { halfKg: 3, label: '1.5 kg' },
  { halfKg: 4, label: '2 kg' },
  { halfKg: 5, label: '2.5 kg' },
  { halfKg: 6, label: '3 kg' },
];

/**
 * Step 3: optional add-ons. The customer picks IDs, quantities, a cake weight,
 * a LED name, and an optional coupon code; all pricing is computed server-side
 * (prices shown here are informational catalog prices only).
 */
export default function AddonSelector({
  cakes,
  specialDecor,
  combos,
  showCombos,
  cakeId,
  cakeWeightHalfKg,
  decor,
  comboIds,
  ledName,
  couponCode,
  onCakeChange,
  onCakeWeightChange,
  onChangeDecor,
  onToggleCombo,
  onLedNameChange,
  onCouponChange,
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

  const setDecorQuantity = (id: number, quantity: number) => {
    const safe = Number.isFinite(quantity) && quantity >= 1 ? quantity : 1;
    onChangeDecor(
      decor.map((d) => (d.id === id ? { ...d, quantity: safe } : d)),
    );
  };

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-2 font-semibold">Cake (optional)</h3>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            className="w-full rounded border border-gray-300 px-3 py-2"
            value={cakeId ?? ''}
            onChange={(e) =>
              onCakeChange(
                e.target.value === '' ? null : Number(e.target.value),
              )
            }
            aria-label="Cake"
          >
            <option value="">No cake</option>
            {cakes.map((cake) => (
              <option key={cake.id} value={cake.id}>
                {cake.description} — {formatRupees(cake.price_paise)}
              </option>
            ))}
          </select>
          <select
            className="rounded border border-gray-300 px-3 py-2"
            value={cakeWeightHalfKg}
            onChange={(e) => onCakeWeightChange(Number(e.target.value))}
            aria-label="Cake weight"
          >
            {CAKE_WEIGHT_OPTIONS.map((opt) => (
              <option key={opt.halfKg} value={opt.halfKg}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Special decor (optional)</h3>
        <ul className="space-y-2">
          {specialDecor.map((item) => {
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
                    <span className="sr-only">
                      Quantity for {item.name}
                    </span>
                    <span aria-hidden="true">×</span>
                    <input
                      type="number"
                      min={1}
                      value={selection.quantity}
                      onChange={(e) =>
                        setDecorQuantity(item.id, Number(e.target.value))
                      }
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

      <section>
        <h3 className="mb-2 font-semibold">LED name (optional)</h3>
        <label className="flex flex-col gap-1">
          <input
            type="text"
            value={ledName}
            onChange={(e) => onLedNameChange(e.target.value)}
            aria-label="LED name"
            className="rounded border border-gray-300 px-3 py-2"
          />
          <span className="text-xs text-gray-500">₹40 per letter</span>
        </label>
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Coupon code (optional)</h3>
        <input
          type="text"
          value={couponCode}
          onChange={(e) => onCouponChange(e.target.value)}
          aria-label="Coupon code"
          className="w-full rounded border border-gray-300 px-3 py-2"
        />
      </section>

      {showCombos && (
        <section>
          <h3 className="mb-2 font-semibold">Combos (optional)</h3>
          <ul className="space-y-2">
            {combos.map((item) => (
              <li key={item.id}>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={comboIds.includes(item.id)}
                    onChange={() => onToggleCombo(item.id)}
                  />
                  <span>
                    {item.name} — {formatRupees(item.price_paise)}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
