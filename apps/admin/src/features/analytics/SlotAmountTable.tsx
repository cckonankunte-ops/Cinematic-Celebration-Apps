/**
 * Slot-amount report: bookings celebrated in the range, with ALL their
 * payments (any received date) split by method. Summary cards on top, then a
 * scrollable table with a totals footer. Totals come from the server.
 */

import { formatDate } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { methodLabel, orderedMethods } from './methods';
import { SummaryCards } from './SummaryCards';
import type { SlotAmountsResult } from './types';

export function SlotAmountTable({ result }: { result: SlotAmountsResult }): JSX.Element {
  const { rows, summary } = result;
  const methods = orderedMethods(summary.paid_by_method, ...rows.map((r) => r.paid_by_method));

  return (
    <div className="space-y-3">
      <SummaryCards
        cards={[
          { label: 'Bookings', value: String(summary.booking_count) },
          { label: 'Total amount', value: formatRupees(summary.total_paise) },
          { label: 'Collected', value: formatRupees(summary.amount_paid_paise), tone: 'good' },
          ...methods.map((m) => ({
            label: `Collected · ${methodLabel(m)}`,
            value: formatRupees(summary.paid_by_method[m] ?? 0),
          })),
          { label: 'Due', value: formatRupees(summary.amount_due_paise), tone: 'warn' },
          { label: 'Discount', value: formatRupees(summary.discount_paise) },
          { label: 'Food', value: formatRupees(summary.food_paise) },
          { label: 'Cleaning', value: formatRupees(summary.cleaning_paise) },
          { label: 'Other', value: formatRupees(summary.other_paise) },
        ]}
      />

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 pr-4">Reference</th>
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Date</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4 text-right">Total</th>
              <th className="py-2 pr-4 text-right">Paid</th>
              {methods.map((m) => (
                <th key={m} className="py-2 pr-4 text-right">
                  {methodLabel(m)}
                </th>
              ))}
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
                <td className="whitespace-nowrap py-2 pr-4">{formatDate(row.booking_date)}</td>
                <td className="py-2 pr-4 capitalize">{row.status}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.total_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.amount_paid_paise)}</td>
                {methods.map((m) => (
                  <td key={m} className="py-2 pr-4 text-right">
                    {formatRupees(row.paid_by_method[m] ?? 0)}
                  </td>
                ))}
                <td className="py-2 pr-4 text-right">{formatRupees(row.amount_due_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.discount_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.food_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.cleaning_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.other_paise)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={11 + methods.length} className="py-6 text-center text-gray-500">
                  No bookings for this range and status.
                </td>
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-gray-300 font-semibold">
              <td className="py-2 pr-4" colSpan={4}>
                Summary
              </td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.total_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.amount_paid_paise)}</td>
              {methods.map((m) => (
                <td key={m} className="py-2 pr-4 text-right">
                  {formatRupees(summary.paid_by_method[m] ?? 0)}
                </td>
              ))}
              <td className="py-2 pr-4 text-right">{formatRupees(summary.amount_due_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.discount_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.food_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.cleaning_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.other_paise)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
