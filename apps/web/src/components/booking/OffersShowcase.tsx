import { useEffect, useState } from 'react';

import { publicApi, type PublicOffer } from '../../lib/api';
import { formatDate } from '../../lib/formatters';

/**
 * Home-page offers showcase. Fetches the public, in-validity coupon offers at
 * runtime and renders each as a card (code + optional name/description +
 * validity). Renders NOTHING when there are no public offers, so the hero
 * stays clean — the server only returns active, public, in-validity coupons
 * with display-safe fields.
 */
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

  return (
    <div className="mx-auto max-w-3xl">
      <ul className="grid gap-3 sm:grid-cols-2">
        {offers.map((offer) => (
          <li
            key={`${offer.location_name}:${offer.code}`}
            className="rounded-2xl border border-white/60 bg-white/95 p-4 text-left shadow-sm"
          >
            <div className="flex items-center gap-2">
              <span className="text-xl" aria-hidden="true">
                🎁
              </span>
              <span className="rounded-md bg-brand/10 px-2 py-0.5 font-mono text-sm font-bold text-brand">
                {offer.code}
              </span>
              <span className="ml-auto rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                {offer.location_name}
              </span>
            </div>
            {offer.name && (
              <p className="mt-2 font-semibold text-gray-900">{offer.name}</p>
            )}
            {offer.description && (
              <p className="mt-1 text-sm text-gray-600">{offer.description}</p>
            )}
            {(offer.effective_from || offer.effective_to) && (
              <p className="mt-2 text-xs text-gray-500">
                {offer.effective_from && offer.effective_to
                  ? `Valid ${formatDate(offer.effective_from)} – ${formatDate(offer.effective_to)}`
                  : offer.effective_to
                    ? `Valid until ${formatDate(offer.effective_to)}`
                    : `Valid from ${formatDate(offer.effective_from as string)}`}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
