import { useEffect, useState } from 'react';

import { publicApi, type PublicOffer } from '../../lib/api';
import { formatDate } from '../../lib/formatters';

/**
 * Home-page offers showcase. Fetches the public, in-validity coupon offers at
 * runtime and renders them compactly. Renders NOTHING when there are no public
 * offers, so the hero stays clean.
 *
 * Space-saving design (most visitors are on phones):
 * - Identical offers (same code, name, description, validity) that exist in
 *   several branches are GROUPED into one card listing the branches, so a promo
 *   created in all 3 branches is one card, not three.
 * - On phones the cards sit in a single swipeable row (scroll-snap, with the
 *   next card peeking in), so the block is one card tall however many offers
 *   exist. From `sm` up they flow into a grid.
 */

interface OfferGroup {
  key: string;
  code: string;
  name: string | null;
  description: string | null;
  effective_from: string | null;
  effective_to: string | null;
  branches: string[];
}

/** Group offers that are identical except for the branch. Order is preserved. */
export function groupOffers(offers: PublicOffer[]): OfferGroup[] {
  const groups = new Map<string, OfferGroup>();
  for (const o of offers) {
    const key = [
      o.code,
      o.name ?? '',
      o.description ?? '',
      o.effective_from ?? '',
      o.effective_to ?? '',
    ].join('|');
    const existing = groups.get(key);
    if (existing) {
      if (!existing.branches.includes(o.location_name)) {
        existing.branches.push(o.location_name);
      }
    } else {
      groups.set(key, {
        key,
        code: o.code,
        name: o.name,
        description: o.description,
        effective_from: o.effective_from,
        effective_to: o.effective_to,
        branches: [o.location_name],
      });
    }
  }
  return Array.from(groups.values());
}

function validityText(g: OfferGroup): string | null {
  if (g.effective_from && g.effective_to) {
    return `Valid ${formatDate(g.effective_from)} – ${formatDate(g.effective_to)}`;
  }
  if (g.effective_to) {
    return `Valid until ${formatDate(g.effective_to)}`;
  }
  if (g.effective_from) {
    return `Valid from ${formatDate(g.effective_from)}`;
  }
  return null;
}

export default function OffersShowcase() {
  const [offers, setOffers] = useState<PublicOffer[] | null>(null);

  useEffect(() => {
    let active = true;
    publicApi
      .listOffers()
      .then((result) => {
        if (active) setOffers(result);
      })
      .catch(() => {
        // Offers are a nice-to-have; on failure render nothing rather than an
        // error, to keep the hero uncluttered.
        if (active) setOffers([]);
      });
    return () => {
      active = false;
    };
  }, []);

  if (offers === null || offers.length === 0) {
    return null;
  }

  const groups = groupOffers(offers);
  const single = groups.length === 1;

  return (
    <div className="mx-auto max-w-3xl">
      <ul
        aria-label="Current offers"
        className={`flex snap-x snap-mandatory gap-3 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:grid sm:overflow-visible ${
          single ? 'sm:grid-cols-1' : 'sm:grid-cols-2'
        }`}
      >
        {groups.map((g) => {
          const validity = validityText(g);
          const multi = g.branches.length > 1;
          // Meta line: validity, plus the branch list when it applies to several.
          const meta = [validity, multi ? g.branches.join(', ') : null]
            .filter(Boolean)
            .join(' · ');
          return (
            <li
              key={g.key}
              className={`snap-center rounded-2xl border border-white/60 bg-white/95 p-3 text-left shadow-sm sm:p-4 ${
                single ? 'w-full' : 'w-[88%] shrink-0 sm:w-auto'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-lg" aria-hidden="true">
                  🎁
                </span>
                <span className="rounded-md bg-brand/10 px-2 py-0.5 font-mono text-sm font-bold text-brand">
                  {g.code}
                </span>
                <span className="ml-auto rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                  {multi ? `${g.branches.length} branches` : g.branches[0]}
                </span>
              </div>
              {g.name && (
                <p className="mt-1.5 text-sm font-semibold text-gray-900">{g.name}</p>
              )}
              {g.description && (
                <p className="line-clamp-1 text-xs text-gray-600 sm:line-clamp-2 sm:text-sm">
                  {g.description}
                </p>
              )}
              {meta && (
                <p className="mt-1 truncate text-[11px] text-gray-500 sm:text-xs">
                  {meta}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
