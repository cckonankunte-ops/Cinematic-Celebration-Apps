import { useState } from 'react';

import type { PriceBreakdownRead } from '../../lib/api';
import { formatRupees } from '../../lib/formatters';

/**
 * Collapsible, server-priced booking summary. Collapsed shows Total + Advance
 * payable; expanded shows the full line-item breakdown with Subtotal, coupon,
 * Advance payable, and Balance = Total − Advance payable ("payable at venue").
 *
 * The client computes NO money: every figure comes from the server preview
 * (`breakdown`). Advance payable is `breakdown.advance_paise` (resolved from
 * the branch's threshold rules, else the plan fallback). A Kids line shows when
 * `kid_extra_guest_paise > 0`. Guests (adults + kids) are shown for transparency.
 */
interface Props {
  breakdown: PriceBreakdownRead | null;
  adults: number;
  kids: number;
  previewError?: string | null;
}

export default function BookingSummary({
  breakdown,
  adults,
  kids,
  previewError,
}: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!breakdown) {
    return (
      <div className="text-sm text-gray-500">
        {previewError ?? 'Pick a plan and time to see your total.'}
      </div>
    );
  }

  const balance = breakdown.total_paise - breakdown.advance_paise;
  const adultExtra = breakdown.extra_guest_paise - breakdown.kid_extra_guest_paise;

  return (
    <div>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 text-left"
      >
        <span className="min-w-0">
          <span className="block text-xs text-gray-500">
            Total {expanded ? '▲' : '▼'}
          </span>
          <span className="block text-lg font-bold text-gray-900">
            {formatRupees(breakdown.total_paise)}
          </span>
        </span>
        <span className="text-right">
          <span className="block text-xs text-gray-500">Advance payable</span>
          <span className="block text-base font-semibold text-brand">
            {formatRupees(breakdown.advance_paise)}
          </span>
        </span>
      </button>

      {expanded && (
        <dl className="mt-3 space-y-1 border-t border-gray-100 pt-3 text-sm">
          <div className="flex justify-between text-gray-600">
            <dt>People (above 10 yrs)</dt>
            <dd>{adults}</dd>
          </div>
          {kids > 0 && (
            <div className="flex justify-between text-gray-600">
              <dt>Kids (3–10 yrs)</dt>
              <dd>{kids}</dd>
            </div>
          )}
          <div className="flex justify-between">
            <dt>Plan price</dt>
            <dd>{formatRupees(breakdown.plan_price_paise)}</dd>
          </div>
          {adultExtra > 0 && (
            <div className="flex justify-between">
              <dt>Extra guests</dt>
              <dd>{formatRupees(adultExtra)}</dd>
            </div>
          )}
          {breakdown.kid_extra_guest_paise > 0 && (
            <div className="flex justify-between">
              <dt>Kids ({kids})</dt>
              <dd>{formatRupees(breakdown.kid_extra_guest_paise)}</dd>
            </div>
          )}
          {breakdown.addon_lines.map((line, idx) => (
            <div
              key={`${line.kind}-${line.item_id ?? idx}`}
              className="flex justify-between"
            >
              <dt>
                {line.name_snapshot}
                {line.quantity > 1 ? ` × ${line.quantity}` : ''}
              </dt>
              <dd>{formatRupees(line.amount_paise)}</dd>
            </div>
          ))}
          <div className="flex justify-between border-t border-gray-100 pt-1">
            <dt>Subtotal</dt>
            <dd>{formatRupees(breakdown.subtotal_paise)}</dd>
          </div>
          {breakdown.coupon_code && (
            <div className="flex justify-between text-green-700">
              <dt>Coupon ({breakdown.coupon_code})</dt>
              <dd>-{formatRupees(breakdown.coupon_discount_paise)}</dd>
            </div>
          )}
          <div className="flex justify-between font-semibold">
            <dt>Total</dt>
            <dd>{formatRupees(breakdown.total_paise)}</dd>
          </div>
          <div className="flex justify-between text-brand">
            <dt>Advance payable</dt>
            <dd>{formatRupees(breakdown.advance_paise)}</dd>
          </div>
          <div className="flex justify-between text-gray-600">
            <dt>Balance (payable at venue)</dt>
            <dd>{formatRupees(balance)}</dd>
          </div>
        </dl>
      )}

      {previewError && (
        <p className="mt-2 text-sm text-amber-700">{previewError}</p>
      )}
    </div>
  );
}
