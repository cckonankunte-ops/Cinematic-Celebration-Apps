import { useEffect, useState } from 'react';

import { publicApi, type PublicOffer } from '../../lib/api';

/**
 * Home-page offers showcase. Fetches the public, currently-valid coupon offers
 * at runtime and renders them compactly. Renders NOTHING when there are no
 * public offers, so the hero stays clean.
 *
 * Space-saving design (most visitors are on phones):
 * - The same offer in several branches is GROUPED into one card listing those
 *   branches. Offers are "the same" when their code, name and description match;
 *   validity dates are deliberately NOT part of the match. The API only returns
 *   offers valid today (IST), so each branch drops out of the list on its own
 *   when its window ends, and the card's branch list always reflects the
 *   branches where the offer can be used right now.
 * - Validity dates are not shown on the cards.
 * - On phones the cards sit in a single swipeable row (scroll-snap, with the
 *   next card peeking in), so the block is one card tall however many offers
 *   exist. From `sm` up they flow into a grid.
 */

interface OfferGroup {
  key: string;
  code: string;
  name: string | null;
  description: string | null;
  branches: string[];
}

/**
 * Group offers that share code + name + description (dates are ignored). Order
 * of first appearance is preserved, and a branch is listed once per group.
 */
export function groupOffers(offers: PublicOffer[]): OfferGroup[] {
  const groups = new Map<string, OfferGroup>();
  for (const o of offers) {
    const key = [o.code, o.name ?? '', o.description ?? ''].join('|');
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
        branches: [o.location_name],
      });
    }
  }
  return Array.from(groups.values());
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
              </div>
              {g.name && (
                <p className="mt-1.5 text-sm font-semibold text-gray-900">{g.name}</p>
              )}
              {g.description && (
                <p className="line-clamp-1 text-xs text-gray-600 sm:line-clamp-2 sm:text-sm">
                  {g.description}
                </p>
              )}
              {/* Branch names are always spelled out (and may wrap) so customers
                  can see exactly where the offer applies. */}
              <p className="mt-1.5 flex gap-1 text-[11px] font-medium leading-snug text-gray-700 sm:text-xs">
                <span aria-hidden="true">📍</span>
                <span>{g.branches.join(', ')}</span>
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
