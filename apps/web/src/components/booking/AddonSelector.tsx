import { useState } from 'react';
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
 * Step 2 add-ons. Combos are shown FIRST as image-forward "savings" hero cards
 * (strike-through worth + "Save ₹X" when the server reports a positive saving),
 * then the individual add-ons (cake, decor, LED, coupon) in collapsible
 * sections so the step stays short on mobile. The customer only sends IDs /
 * quantities; all pricing (including the saving) is computed server-side —
 * prices shown here are informational catalog values.
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

  // Raw text per decor id while the quantity field is being edited. Keeping the
  // field as a free string (not the coerced number) lets the user clear "1" and
  // type a replacement on mobile, where the number stepper arrows aren't shown.
  // The committed DecorSelection.quantity stays a valid number ≥ 1 at all times.
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
    onChangeDecor(
      decor.map((d) => (d.id === id ? { ...d, quantity } : d)),
    );
  };

  // While typing, hold the raw text (including empty). Digits that parse to a
  // valid quantity are committed live so the price preview stays in sync; an
  // empty/invalid value is allowed to persist in the field until blur.
  const onQuantityInput = (id: number, raw: string) => {
    setQtyDrafts((prev) => ({ ...prev, [id]: raw }));
    const parsed = Number(raw);
    if (raw !== '' && Number.isInteger(parsed) && parsed >= 1) {
      commitQuantity(id, parsed);
    }
  };

  // On blur, resolve the field. If there's no active draft (the user focused
  // the field but didn't change it), keep the already-committed quantity — a
  // no-op blur must never clobber a valid value like 6 back to 1. Only an
  // actually-edited field that ends empty/invalid falls back to 1 so a ticked
  // decor always keeps qty ≥ 1. Either way, drop the draft.
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

  return (
    <div className="space-y-5">
      {/* Combos first: image-forward savings hero cards. */}
      {showCombos && combos.length > 0 && (
        <section>
          <h3 className="mb-2 font-semibold text-gray-900">
            Save with Combos
          </h3>
          <ul className="grid gap-3 sm:grid-cols-2">
            {combos.map((item) => {
              const selected = comboIds.includes(item.id);
              const saves = item.savings_paise > 0;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onToggleCombo(item.id)}
                    aria-pressed={selected}
                    className={`flex w-full overflow-hidden rounded-xl border text-left transition ${
                      selected
                        ? 'border-festive-magenta ring-2 ring-festive-magenta'
                        : 'border-gray-200 hover:border-festive-magenta/60'
                    }`}
                  >
                    {/* Theme/combo image or festive placeholder. */}
                    <div className="relative h-24 w-24 flex-none overflow-hidden bg-festive-hero">
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
                          className="flex h-full w-full items-center justify-center text-2xl"
                        >
                          🎀
                        </span>
                      )}
                      {saves && (
                        <span className="absolute left-1 top-1 rounded bg-green-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                          Save {formatRupees(item.savings_paise)}
                        </span>
                      )}
                    </div>
                    <div className="flex flex-1 flex-col gap-0.5 p-2">
                      <span className="font-semibold text-gray-900">
                        {item.name}
                      </span>
                      {item.description && (
                        <span className="text-xs text-gray-500">
                          {item.description}
                        </span>
                      )}
                      <span className="mt-auto flex items-baseline gap-2">
                        {saves && item.worth_paise !== null && (
                          <span className="text-xs text-gray-400 line-through">
                            {formatRupees(item.worth_paise)}
                          </span>
                        )}
                        <span className="font-bold text-festive-magenta">
                          {formatRupees(item.price_paise)}
                        </span>
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="mt-2 text-[11px] text-gray-400">
            Images are for representation only. Colours are subject to
            availability. Prices are inclusive of taxes.
          </p>
        </section>
      )}

      {/* Individual add-ons, collapsible to keep the step short on mobile. */}
      <details className="rounded-xl border border-gray-200 p-3">
        <summary className="cursor-pointer font-semibold text-gray-900">
          Add a cake
        </summary>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
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
      </details>

      <details className="rounded-xl border border-gray-200 p-3">
        <summary className="cursor-pointer font-semibold text-gray-900">
          Add special decor
        </summary>
        <ul className="mt-3 space-y-2">
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
                    <span className="sr-only">Quantity for {item.name}</span>
                    <span aria-hidden="true">×</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      value={qtyDrafts[item.id] ?? String(selection.quantity)}
                      onChange={(e) =>
                        onQuantityInput(item.id, e.target.value)
                      }
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
      </details>

      <details className="rounded-xl border border-gray-200 p-3">
        <summary className="cursor-pointer font-semibold text-gray-900">
          Add a LED name
        </summary>
        <label className="mt-3 flex flex-col gap-1">
          <input
            type="text"
            value={ledName}
            onChange={(e) => onLedNameChange(e.target.value)}
            aria-label="LED name"
            className="rounded border border-gray-300 px-3 py-2"
          />
          <span className="text-xs text-gray-500">₹40 per letter</span>
        </label>
      </details>

      <details className="rounded-xl border border-gray-200 p-3">
        <summary className="cursor-pointer font-semibold text-gray-900">
          Have a coupon code?
        </summary>
        <input
          type="text"
          value={couponCode}
          onChange={(e) => onCouponChange(e.target.value)}
          aria-label="Coupon code"
          className="mt-3 w-full rounded border border-gray-300 px-3 py-2"
        />
      </details>
    </div>
  );
}
