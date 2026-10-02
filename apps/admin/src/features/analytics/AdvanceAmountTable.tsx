/**
 * Advance-amount report table with a Day Summary footer. Advances are derived
 * from the payments ledger server-side; the footer uses the authoritative
 * `summary` totals (not re-summed on the client). Money via `formatRupees`.
 */

import { formatRupees } from '@/lib/money';
import type { AdvanceAmountsResult } from './types';

export function AdvanceAmountTable({
  result,
}: {
  result: AdvanceAmountsResult;
}): JSX.Element {
  const { rows, summary } = result;

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-gray-500">
            <th className="py-2 pr-4">Reference</th>
            <th className="py-2 pr-4">Name</th>
            <th className="py-2 pr-4 text-right">Total</th>
            <th className="py-2 pr-4 text-right">Paid</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.booking_reference} className="border-b border-gray-100">
              <td className="py-2 pr-4 font-mono text-xs">{row.booking_reference}</td>
              <td className="py-2 pr-4">{row.booking_name}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.total_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.amount_paid_paise)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-gray-300 font-semibold">
            <td className="py-2 pr-4" colSpan={2}>
              Day summary
            </td>
            <td className="py-2 pr-4 text-right">{formatRupees(summary.total_paise)}</td>
            <td className="py-2 pr-4 text-right">{formatRupees(summary.amount_paid_paise)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
