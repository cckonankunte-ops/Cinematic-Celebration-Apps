import { STATUS_LABELS, type LeadStatus } from './types';

const COLOURS: Record<LeadStatus, string> = {
  new: 'bg-blue-100 text-blue-800',
  contacted: 'bg-indigo-100 text-indigo-800',
  follow_up: 'bg-amber-100 text-amber-800',
  booked: 'bg-teal-100 text-teal-800',
  won: 'bg-green-100 text-green-800',
  not_interested: 'bg-gray-200 text-gray-700',
  lost: 'bg-gray-200 text-gray-700',
};

export function LeadStatusBadge({ status }: { status: LeadStatus }): JSX.Element {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${COLOURS[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
