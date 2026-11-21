/**
 * Leads page sections (lead-crm R5.1, R5.8). Mirrors the server's ordering in
 * `services/leads.py` (`_section`), so the page can draw section headings over
 * the server-sorted list:
 *   1 Not contacted (uncontacted new leads) - 2 Overdue - 3 Due today -
 *   4 New (no follow-up) - 5 Others
 */

import { istDateOf } from '@/lib/dates';
import { CLOSED_STATUSES, type LeadRead } from './types';

export type LeadSection = 'uncontacted' | 'overdue' | 'due_today' | 'new' | 'other';

export const SECTION_ORDER: LeadSection[] = [
  'uncontacted',
  'overdue',
  'due_today',
  'new',
  'other',
];

export const SECTION_LABELS: Record<LeadSection, string> = {
  uncontacted: 'Not contacted',
  overdue: 'Overdue',
  due_today: 'Due today',
  new: 'New',
  other: 'Others',
};

export function leadSection(lead: LeadRead, now: Date): LeadSection {
  if (lead.is_uncontacted) {
    return 'uncontacted';
  }
  const open = !CLOSED_STATUSES.includes(lead.status);
  if (open && lead.follow_up_at) {
    const at = new Date(lead.follow_up_at);
    if (at < now) {
      return 'overdue';
    }
    if (istDateOf(at) === istDateOf(now)) {
      return 'due_today';
    }
  }
  if (lead.status === 'new' && !lead.follow_up_at) {
    return 'new';
  }
  return 'other';
}

/** Consecutive runs of the (already sorted) leads, one per section. */
export function groupBySection(
  leads: LeadRead[],
  now: Date,
): Array<{ section: LeadSection; leads: LeadRead[] }> {
  const groups: Array<{ section: LeadSection; leads: LeadRead[] }> = [];
  for (const lead of leads) {
    const section = leadSection(lead, now);
    const last = groups[groups.length - 1];
    if (last && last.section === section) {
      last.leads.push(lead);
    } else {
      groups.push({ section, leads: [lead] });
    }
  }
  return groups;
}

/** Red label for an uncontacted lead (R5.8): "Not contacted · 25 min". */
export function uncontactedLabel(minutes: number): string {
  if (minutes < 60) {
    return `Not contacted · ${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `Not contacted · ${hours} h ${minutes % 60} min`;
  }
  return `Not contacted · ${Math.floor(hours / 24)} d`;
}
