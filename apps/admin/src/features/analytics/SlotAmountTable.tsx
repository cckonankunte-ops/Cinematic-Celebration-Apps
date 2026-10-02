/**
 * Slot-amount report table with a Day Summary footer row that sums the money
 * columns from the server-provided `summary` (not re-summed on the client, so
 * the footer always matches the authoritative backend totals). Horizontally
 * scrollable on small screens. Money via `formatRupees` (paise -> INR).
 */

import { formatRupees } from '@/lib/money';
import type { SlotAmountsResult } from './types';

export function SlotAmountTable({ result }: { result: SlotAmountsResult }): JSX.Element {
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
            <th className="py-2 pr-4 text-right">Today income</th>
            <th className="py-2 pr-4 text-right">Due</th>
            <th className="py-2 pr-4 text-right">Discount</th>
            <th className="py-2 pr-4 text-right">Food</th>
            <th className="py-2 pr-4 text-right">Cleaning</th>
            <th className="py-2 pr-4 text-right">Other</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.booking_reference} className="border-b border-gray-100">
              <td className="py-2 pr-4 font-mono text-xs">{row.booking_reference}</td>
              <td className="py-2 pr-4">{row.booking_name}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.total_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.amount_paid_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.today_income_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.amount_due_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.discount_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.food_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.cleaning_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(row.other_paise)}</td>
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
            <td className="py-2 pr-4 text-right">—</td>
            <td className="py-2 pr-4 text-right">{formatRupees(summary.amount_due_paise)}</td>
            <td className="py-2 pr-4 text-right">{formatRupees(summary.discount_paise)}</td>
            <td className="py-2 pr-4 text-right">{formatRupees(summary.food_paise)}</td>
            <td className="py-2 pr-4 text-right">{formatRupees(summary.cleaning_paise)}</td>
            <td className="py-2 pr-4 text-right">{formatRupees(summary.other_paise)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
