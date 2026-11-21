/**
 * Income report: payments received in the chosen date(s), per booking and per
 * method (reversals net out). Independent of the booking's celebration date.
 */

import { formatDate } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { methodLabel, orderedMethods } from './methods';
import { SummaryCards } from './SummaryCards';
import type { TodayIncomeResult } from './types';

export function TodayIncomeTable({ result }: { result: TodayIncomeResult }): JSX.Element {
  const { rows, summary } = result;
  const methods = orderedMethods(
    summary.received_by_method,
    ...rows.map((r) => r.received_by_method),
  );

  return (
    <div className="space-y-3">
      <SummaryCards
        cards={[
          {
            label: 'Total received',
            value: formatRupees(summary.received_paise),
            tone: 'good',
          },
          ...methods.map((m) => ({
            label: methodLabel(m),
            value: formatRupees(summary.received_by_method[m] ?? 0),
          })),
          { label: 'Bookings paid', value: String(summary.booking_count) },
          { label: 'Payments', value: String(summary.payment_count) },
        ]}
      />

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 pr-4">Reference</th>
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Celebration</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4 text-right">Received</th>
              {methods.map((m) => (
                <th key={m} className="py-2 pr-4 text-right">
                  {methodLabel(m)}
                </th>
              ))}
              <th className="py-2 pr-4 text-right">Total</th>
              <th className="py-2 pr-4 text-right">Paid to date</th>
              <th className="py-2 pr-4 text-right">Due</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.booking_reference} className="border-b border-gray-100">
                <td className="py-2 pr-4 font-mono text-xs">{row.booking_reference}</td>
                <td className="py-2 pr-4">{row.booking_name}</td>
                <td className="whitespace-nowrap py-2 pr-4">{formatDate(row.booking_date)}</td>
                <td className="py-2 pr-4 capitalize">{row.status}</td>
                <td className="py-2 pr-4 text-right font-medium">
                  {formatRupees(row.received_paise)}
                </td>
                {methods.map((m) => (
                  <td key={m} className="py-2 pr-4 text-right">
                    {formatRupees(row.received_by_method[m] ?? 0)}
                  </td>
                ))}
                <td className="py-2 pr-4 text-right">{formatRupees(row.total_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.amount_paid_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.amount_due_paise)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={8 + methods.length} className="py-6 text-center text-gray-500">
                  No payments received in this range.
                </td>
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-gray-300 font-semibold">
              <td className="py-2 pr-4" colSpan={4}>
                Summary
              </td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.received_paise)}</td>
              {methods.map((m) => (
                <td key={m} className="py-2 pr-4 text-right">
                  {formatRupees(summary.received_by_method[m] ?? 0)}
                </td>
              ))}
              <td className="py-2 pr-4" colSpan={3} />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
