/** A responsive strip of labelled totals (2 columns on phones). */

export interface SummaryCard {
  label: string;
  value: string;
  tone?: 'default' | 'good' | 'warn';
}

const TONES: Record<NonNullable<SummaryCard['tone']>, string> = {
  default: 'text-gray-900',
  good: 'text-green-700',
  warn: 'text-amber-700',
};

export function SummaryCards({ cards }: { cards: SummaryCard[] }): JSX.Element {
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded border border-gray-200 bg-white px-3 py-2">
          <dt className="text-xs text-gray-500">{card.label}</dt>
          <dd className={`text-base font-semibold ${TONES[card.tone ?? 'default']}`}>
            {card.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
