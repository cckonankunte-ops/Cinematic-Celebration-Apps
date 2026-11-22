/** Labels and summaries for lead timeline entries (lead-crm R7.8). */

import { formatDateTime } from '@/lib/dates';
import { STATUS_LABELS, type ActivityRead, type LeadStatus } from './types';

export const ACTIVITY_TYPE_LABELS: Record<ActivityRead['type'], string> = {
  note: 'Note',
  call: 'Call',
  whatsapp: 'WhatsApp',
  status_change: 'Status',
  follow_up_set: 'Follow-up',
  booking_linked: 'Booking',
  system: 'System',
};

const MANUAL_TYPES: ActivityRead['type'][] = ['note', 'call', 'whatsapp'];

/** Author name, else "Customer" for an unauthored note (enquiry text), else "System". */
export function activityAuthor(activity: ActivityRead): string {
  if (activity.author_name) return activity.author_name;
  return MANUAL_TYPES.includes(activity.type) ? 'Customer' : 'System';
}

function statusLabel(value: unknown): string {
  return typeof value === 'string' && value in STATUS_LABELS
    ? STATUS_LABELS[value as LeadStatus]
    : String(value ?? '');
}

/** One-line summary for entries whose meaning lives in `data`. */
export function activitySummary(activity: ActivityRead): string | null {
  const data = activity.data ?? {};
  if (activity.type === 'status_change' && 'from' in data && 'to' in data) {
    return `${statusLabel(data.from)} → ${statusLabel(data.to)}`;
  }
  if (activity.type === 'follow_up_set' && typeof data.follow_up_at === 'string') {
    return `Follow up ${formatDateTime(data.follow_up_at)}`;
  }
  return null;
}
