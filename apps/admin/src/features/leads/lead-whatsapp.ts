/**
 * Call / WhatsApp links for leads and the "send today's follow-ups to the
 * branch WhatsApp" digest (lead-crm R10.3, R11.1-R11.5, R11.7). Pure functions.
 *
 * The business uses the WhatsApp Business app (no API), so every message is a
 * `wa.me` link that opens WhatsApp with the text pre-filled; a person sends it.
 */

import { formatDateTime } from '@/lib/dates';
import { normaliseIndianMobile } from '@/lib/phone';
import { STATUS_LABELS, type FollowUpItem, type LeadRead } from './types';

/** WhatsApp message limit we stay under (R11.5); wa.me links get long fast. */
export const DIGEST_MAX_CHARS = 3500;
export const NOTE_MAX_CHARS = 60;

export interface BranchNumbers {
  name: string;
  phone?: string | null;
  whatsapp_phone?: string | null;
}

/** `tel:+91XXXXXXXXXX` for a lead phone, or null when it isn't a usable mobile. */
export function telHref(phone: string | null | undefined): string | null {
  const mobile = normaliseIndianMobile(phone);
  return mobile ? `tel:+91${mobile}` : null;
}

/** First name for a greeting ("Asha Rao" → "Asha"), or null. */
function firstName(name: string | null): string | null {
  const first = name?.trim().split(/\s+/)[0];
  return first ? first : null;
}

/** Greeting to the customer, using their name and the branch (R10.3). */
export function customerGreeting(lead: Pick<LeadRead, 'name'>, branchName: string): string {
  const who = firstName(lead.name);
  return (
    `Hi${who ? ` ${who}` : ''}, this is Cinematic Celebration (${branchName}). ` +
    'Thanks for your enquiry! How can we help you plan your celebration?'
  );
}

/** `https://wa.me/91XXXXXXXXXX?text=…` to chat with the customer, or null. */
export function customerWhatsappUrl(
  lead: Pick<LeadRead, 'name' | 'phone'>,
  branchName: string,
): string | null {
  const mobile = normaliseIndianMobile(lead.phone);
  if (!mobile) return null;
  return `https://wa.me/91${mobile}?text=${encodeURIComponent(customerGreeting(lead, branchName))}`;
}

/**
 * The branch's WhatsApp digits for `wa.me`: `whatsapp_phone` when set, else the
 * branch phone (R11.3). Null when neither is a usable Indian mobile.
 */
export function branchWhatsappNumber(branch: BranchNumbers | null | undefined): string | null {
  if (!branch) return null;
  const mobile =
    normaliseIndianMobile(branch.whatsapp_phone) ?? normaliseIndianMobile(branch.phone);
  return mobile ? `91${mobile}` : null;
}

function truncate(text: string, max: number): string {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean.length <= max ? clean : `${clean.slice(0, max - 1).trimEnd()}…`;
}

/** One digest entry (R11.2): name or "Unknown", +91 phone, time, status, last note. */
export function digestEntry(item: FollowUpItem, index: number): string {
  const when = `${item.is_overdue ? 'Overdue' : 'Due'} ${formatDateTime(item.follow_up_at)}`;
  const lines = [
    `${index}. ${item.name?.trim() || 'Unknown'} · +91 ${item.phone}`,
    `   ${when} · ${STATUS_LABELS[item.status]}`,
  ];
  if (item.last_note) {
    lines.push(`   Note: ${truncate(item.last_note, NOTE_MAX_CHARS)}`);
  }
  return lines.join('\n');
}

export interface Digest {
  text: string;
  included: number;
  omitted: number;
}

/**
 * The follow-up message for the branch WhatsApp. Entries are added in order
 * while they fit under `DIGEST_MAX_CHARS`; the rest become "+N more in admin".
 */
export function buildFollowUpDigest(
  items: FollowUpItem[],
  branchName: string,
  maxChars: number = DIGEST_MAX_CHARS,
): Digest {
  const overdue = items.filter((i) => i.is_overdue).length;
  const header =
    `Follow-ups for ${branchName}: ${items.length}` +
    (overdue > 0 ? ` (${overdue} overdue)` : '');
  const more = (n: number) => `\n\n+${n} more in admin`;

  let text = header;
  let included = 0;
  for (const [i, item] of items.entries()) {
    const next = `${text}\n\n${digestEntry(item, i + 1)}`;
    const remaining = items.length - (i + 1);
    // Keep room for the "+N more" line whenever entries would be left out.
    const reserve = remaining > 0 ? more(remaining).length : 0;
    if (next.length + reserve > maxChars) break;
    text = next;
    included += 1;
  }
  const omitted = items.length - included;
  if (omitted > 0) text += more(omitted);
  return { text, included, omitted };
}

export type DigestState =
  | { kind: 'no_number'; hint: string }
  | { kind: 'nothing_due'; hint: string }
  | { kind: 'ready'; url: string; digest: Digest };

/** What the "Send today's follow-ups" action should do (R11.4, R11.7). */
export function digestState(
  branch: BranchNumbers | null | undefined,
  items: FollowUpItem[],
): DigestState {
  const number = branchWhatsappNumber(branch);
  if (!number || !branch) {
    return { kind: 'no_number', hint: 'Add a branch WhatsApp number in Location settings' };
  }
  if (items.length === 0) {
    return { kind: 'nothing_due', hint: 'No follow-ups due' };
  }
  const digest = buildFollowUpDigest(items, branch.name);
  return {
    kind: 'ready',
    url: `https://wa.me/${number}?text=${encodeURIComponent(digest.text)}`,
    digest,
  };
}
