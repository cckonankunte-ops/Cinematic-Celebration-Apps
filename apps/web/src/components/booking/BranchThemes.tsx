import { useEffect, useState } from 'react';
import { publicApi, type Plan } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

interface Props {
  locationId: number;
  slug: string;
}

/**
 * The decoration themes available at a branch. A plan IS a themed room, so this
 * lists the branch's active plans as image-forward theme cards (first gallery
 * image + title + price), each linking into the booking flow pre-selected.
 * Fetches on mount; kept light so it can live inside an expandable branch card.
 */
export default function BranchThemes({ locationId, slug }: Props) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    publicApi
      .listPlans(locationId)
      .then((result) => {
        if (active) setPlans(result);
      })
      .catch(() => {
        if (active) setError('Could not load themes right now.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [locationId]);

  if (loading) {
    return <p className="text-sm text-gray-500">Loading themes…</p>;
  }
  if (error) {
    return <p className="text-sm text-gray-600">{error}</p>;
  }
  if (plans.length === 0) {
    return <p className="text-sm text-gray-500">No themes listed yet.</p>;
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2">
      {plans.map((plan) => {
        const image = plan.gallery_urls?.[0];
        return (
          <li
            key={plan.id}
            className="card-lift overflow-hidden rounded-2xl border border-gray-200 bg-white"
          >
            <div className="aspect-[16/10] w-full overflow-hidden bg-festive-hero">
              {image ? (
                <img
                  src={image}
                  alt={plan.title}
                  loading="lazy"
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-4xl">
                  🎀
                </div>
              )}
            </div>
            <div className="p-4">
              <div className="flex items-start justify-between gap-2">
                <h4 className="font-semibold text-gray-900">{plan.title}</h4>
                <span className="shrink-0 font-semibold text-brand">
                  {formatRupees(plan.price_paise)}
                </span>
              </div>
              {plan.description && (
                <p className="mt-1 line-clamp-2 text-sm text-gray-600">
                  {plan.description}
                </p>
              )}
              <a
                href={`/book?location=${encodeURIComponent(slug)}&plan=${plan.id}`}
                className="mt-3 inline-block rounded-full bg-festive-hero px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
              >
                Book this theme
              </a>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
