import { useEffect, useRef, useState } from 'react';

import type { Cake } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

/**
 * Cake selection for the (skippable) Cake step. Cakes render as image cards
 * (two per row on mobile); tapping one opens a small weight popup that defaults
 * to 0.5 kg (500 g) and can be changed. Clicking outside the popup closes it and
 * keeps the current weight. Weight is in half-kg units (1 = 0.5 kg). Prices are
 * catalog values; the authoritative cake price is computed server-side.
 */
interface Props {
  cakes: Cake[];
  cakeId: number | null;
  cakeWeightHalfKg: number;
  onCakeChange: (cakeId: number | null) => void;
  onCakeWeightChange: (halfKg: number) => void;
  /**
   * Called when the weight popup closes after a cake was chosen: either a
   * weight was picked, or the customer tapped blank space (keeping the 0.5 kg
   * default). The parent uses it to move on to the "Name on cake" field. NOT
   * called when the popup closes because another button/link was tapped.
   */
  onWeightPopupDone?: () => void;
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
  onWeightPopupDone,
}: Props) {
  // Which cake's weight popup is open (null = none).
  const [popupId, setPopupId] = useState<number | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  // Always call the latest callback without re-subscribing the listener.
  const doneRef = useRef(onWeightPopupDone);
  doneRef.current = onWeightPopupDone;

  // Close the popup when clicking outside it. Tapping blank space keeps the
  // current (default 0.5 kg) weight and moves on; tapping another control just
  // closes the popup and lets that control do its own thing.
  useEffect(() => {
    if (popupId === null) return;
    const onDocClick = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        setPopupId(null);
        const target = e.target as HTMLElement | null;
        const onControl = target?.closest?.(
          'button, a, input, select, textarea, label',
        );
        if (!onControl) {
          doneRef.current?.();
        }
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [popupId]);

  const selectCake = (id: number) => {
    if (cakeId === id) {
      // Tapping the chosen cake again opens its weight popup.
      setPopupId(id);
      return;
    }
    onCakeChange(id);
    // Default weight to 0.5 kg (500 g) on a fresh selection, then prompt.
    onCakeWeightChange(1);
    setPopupId(id);
  };

  const clearCake = () => {
    onCakeChange(null);
    onCakeWeightChange(1);
    setPopupId(null);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-600">
          Tap a cake to add it, then pick a weight.
        </p>
        {cakeId !== null && (
          <button
            type="button"
            onClick={clearCake}
            className="text-sm font-semibold text-brand hover:underline"
          >
            Remove cake
          </button>
        )}
      </div>

      {cakes.length === 0 ? (
        <p className="text-sm text-gray-500">No cakes available.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {cakes.map((cake) => {
            const selected = cakeId === cake.id;
            const weightLabel =
              CAKE_WEIGHT_OPTIONS.find((w) => w.halfKg === cakeWeightHalfKg)?.label ??
              '0.5 kg';
            return (
              <li key={cake.id} className="relative">
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => selectCake(cake.id)}
                  className={`flex w-full flex-col overflow-hidden rounded-xl border-2 text-left transition ${
                    selected
                      ? 'border-brand shadow-md'
                      : 'border-gray-200 hover:border-brand/60'
                  }`}
                >
                  <div className="relative aspect-square w-full overflow-hidden bg-festive-hero">
                    {cake.image_url ? (
                      <img
                        src={cake.image_url}
                        alt={cake.description}
                        loading="lazy"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span
                        aria-hidden="true"
                        className="flex h-full w-full items-center justify-center text-3xl"
                      >
                        🎂
                      </span>
                    )}
                    {selected && (
                      <span className="absolute right-1.5 top-1.5 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-brand shadow">
                        ✓ {weightLabel}
                      </span>
                    )}
                  </div>
                  <div className="p-2">
                    <p className="text-sm font-medium text-gray-900">
                      {cake.description}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatRupees(cake.price_paise)} / 0.5 kg
                    </p>
                  </div>
                </button>

                {popupId === cake.id && (
                  <div
                    ref={popupRef}
                    className="absolute left-1/2 top-2 z-20 w-44 -translate-x-1/2 rounded-xl border border-gray-200 bg-white p-3 shadow-lg"
                  >
                    <p className="mb-2 text-xs font-semibold text-gray-700">
                      Choose weight
                    </p>
                    <div className="grid grid-cols-3 gap-1.5">
                      {CAKE_WEIGHT_OPTIONS.map((opt) => (
                        <button
                          key={opt.halfKg}
                          type="button"
                          onClick={() => {
                            onCakeWeightChange(opt.halfKg);
                            setPopupId(null);
                            onWeightPopupDone?.();
                          }}
                          className={`rounded border px-1 py-1 text-xs transition ${
                            cakeWeightHalfKg === opt.halfKg
                              ? 'border-brand bg-brand/5 font-semibold text-brand'
                              : 'border-gray-300 text-gray-700 hover:border-brand/60'
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
