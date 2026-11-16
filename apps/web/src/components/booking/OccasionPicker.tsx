import type { Occasion } from '../../lib/api';

/**
 * Occasion tiles for the (skippable) Occasion step. Tapping a selected tile
 * clears it, so "no occasion" is always reachable and Next is never blocked.
 */
interface Props {
  occasions: Occasion[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}

export default function OccasionPicker({ occasions, selectedId, onSelect }: Props) {
  if (occasions.length === 0) {
    return <p className="text-sm text-gray-500">No occasions configured.</p>;
  }
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {occasions.map((o) => {
        const selected = selectedId === o.id;
        return (
          <li key={o.id}>
            <button
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(selected ? null : o.id)}
              className={`w-full rounded-xl border-2 px-4 py-3 text-center text-sm font-semibold transition ${
                selected
                  ? 'border-brand bg-brand/5 text-brand'
                  : 'border-gray-200 text-gray-700 hover:border-brand/60'
              }`}
            >
              {o.name}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
