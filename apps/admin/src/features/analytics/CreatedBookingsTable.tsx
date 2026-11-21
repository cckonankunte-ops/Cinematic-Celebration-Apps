/**
 * Bookings-created report: bookings created in the range, for which
 * celebration date, with cake / special decor / combos, total, paid and due.
 */

import { formatDate } from '@/lib/dates';
import { formatRupees } from '@/lib/money';
import { SummaryCards } from './SummaryCards';
import type { CreatedBookingsResult } from './types';

function list(items: string[]): string {
  return items.length > 0 ? items.join(', ') : '—';
}

export function CreatedBookingsTable({
  result,
}: {
  result: CreatedBookingsResult;
}): JSX.Element {
  const { rows, summary } = result;

  return (
    <div className="space-y-3">
      <SummaryCards
        cards={[
          { label: 'Bookings created', value: String(summary.booking_count) },
          { label: 'Total amount', value: formatRupees(summary.total_paise) },
          { label: 'Paid', value: formatRupees(summary.amount_paid_paise), tone: 'good' },
          { label: 'Due', value: formatRupees(summary.amount_due_paise), tone: 'warn' },
        ]}
      />

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="py-2 pr-4">Reference</th>
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Created</th>
              <th className="py-2 pr-4">Celebration</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Plan</th>
              <th className="py-2 pr-4">Cake</th>
              <th className="py-2 pr-4">Special decor</th>
              <th className="py-2 pr-4">Combos</th>
              <th className="py-2 pr-4 text-right">Total</th>
              <th className="py-2 pr-4 text-right">Paid</th>
              <th className="py-2 pr-4 text-right">Due</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.booking_reference} className="border-b border-gray-100 align-top">
                <td className="py-2 pr-4 font-mono text-xs">{row.booking_reference}</td>
                <td className="py-2 pr-4">{row.booking_name}</td>
                <td className="whitespace-nowrap py-2 pr-4">{formatDate(row.created_at)}</td>
                <td className="whitespace-nowrap py-2 pr-4">{formatDate(row.booking_date)}</td>
                <td className="py-2 pr-4 capitalize">{row.status}</td>
                <td className="py-2 pr-4">{row.plan_title}</td>
                <td className="py-2 pr-4">{row.cake ?? '—'}</td>
                <td className="py-2 pr-4">{list(row.special_decor)}</td>
                <td className="py-2 pr-4">{list(row.combos)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.total_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.amount_paid_paise)}</td>
                <td className="py-2 pr-4 text-right">{formatRupees(row.amount_due_paise)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={12} className="py-6 text-center text-gray-500">
                  No bookings created in this range for the chosen status.
                </td>
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-gray-300 font-semibold">
              <td className="py-2 pr-4" colSpan={9}>
                Summary
              </td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.total_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.amount_paid_paise)}</td>
              <td className="py-2 pr-4 text-right">{formatRupees(summary.amount_due_paise)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
