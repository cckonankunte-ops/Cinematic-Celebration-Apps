import type { Cake } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

/**
 * Cake + weight selection for the (skippable) Cake step. "No cake" is the
 * default; the weight is in half-kg units (1 = 0.5kg). Prices shown are catalog
 * values; the authoritative cake price is computed server-side from weight.
 */
interface Props {
  cakes: Cake[];
  cakeId: number | null;
  cakeWeightHalfKg: number;
  onCakeChange: (cakeId: number | null) => void;
  onCakeWeightChange: (halfKg: number) => void;
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

export default function CakePicker({
  cakes,
  cakeId,
  cakeWeightHalfKg,
  onCakeChange,
  onCakeWeightChange,
}: Props) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
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
      <select
        className="rounded border border-gray-300 px-3 py-2"
        value={cakeWeightHalfKg}
        onChange={(e) => onCakeWeightChange(Number(e.target.value))}
        aria-label="Cake weight"
        disabled={cakeId === null}
      >
        {CAKE_WEIGHT_OPTIONS.map((opt) => (
          <option key={opt.halfKg} value={opt.halfKg}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
