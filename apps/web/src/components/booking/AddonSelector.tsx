import type { Cake, Combo, SpecialDecor } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

interface Props {
  cakes: Cake[];
  specialDecor: SpecialDecor[];
  combos: Combo[];
  /** Combos are offered only when the chosen slot has show_combos = true. */
  showCombos: boolean;
  cakeId: number | null;
  specialDecorIds: number[];
  comboIds: number[];
  onCakeChange: (cakeId: number | null) => void;
  onToggleDecor: (id: number) => void;
  onToggleCombo: (id: number) => void;
}

/**
 * Step 3: optional add-ons. The customer only picks IDs; all pricing is
 * computed server-side at submission time (prices shown here are informational
 * catalog prices only).
 */
export default function AddonSelector({
  cakes,
  specialDecor,
  combos,
  showCombos,
  cakeId,
  specialDecorIds,
  comboIds,
  onCakeChange,
  onToggleDecor,
  onToggleCombo,
}: Props) {
  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-2 font-semibold">Cake (optional)</h3>
        <select
          className="w-full rounded border border-gray-300 px-3 py-2"
          value={cakeId ?? ''}
          onChange={(e) =>
            onCakeChange(e.target.value === '' ? null : Number(e.target.value))
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
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Special decor (optional)</h3>
        <ul className="space-y-2">
          {specialDecor.map((item) => (
            <li key={item.id}>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={specialDecorIds.includes(item.id)}
                  onChange={() => onToggleDecor(item.id)}
                />
                <span>
                  {item.name} — {formatRupees(item.price_paise)}
                </span>
              </label>
            </li>
          ))}
        </ul>
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
