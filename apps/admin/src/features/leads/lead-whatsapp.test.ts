import { describe, expect, it } from 'vitest';

import { readLeadPrefill } from '@/features/bookings/lead-prefill';
import { activityAuthor, activitySummary } from './lead-activity';
import { buildLeadPrefill, canConvert } from './lead-convert';
import {
  DIGEST_MAX_CHARS,
  branchWhatsappNumber,
  buildFollowUpDigest,
  customerWhatsappUrl,
  digestEntry,
  digestState,
  telHref,
} from './lead-whatsapp';
import type { ActivityRead, FollowUpItem, LeadRead } from './types';

function item(i: number, overrides: Partial<FollowUpItem> = {}): FollowUpItem {
  return {
    id: i,
    name: `Customer ${i}`,
    phone: `98765${String(i).padStart(5, '0')}`,
    status: 'follow_up',
    follow_up_at: '2026-11-10T06:30:00Z',
    is_overdue: false,
    last_note: null,
    ...overrides,
  };
}

const BRANCH = { name: 'Hulimavu', phone: '080 4123 4567', whatsapp_phone: '9000000001' };

describe('telHref / customerWhatsappUrl', () => {
  it('builds +91 links from a 10-digit phone', () => {
    expect(telHref('9876543210')).toBe('tel:+919876543210');
    expect(telHref('12345')).toBeNull();
    const url = customerWhatsappUrl({ name: 'Asha Rao', phone: '9876543210' }, 'Hulimavu');
    expect(url?.startsWith('https://wa.me/919876543210?text=')).toBe(true);
    const text = decodeURIComponent(url?.split('?text=')[1] ?? '');
    expect(text).toContain('Hi Asha, this is Cinematic Celebration (Hulimavu).');
  });

  it('greets without a name when there is none', () => {
    const url = customerWhatsappUrl({ name: null, phone: '9876543210' }, 'Ecity');
    expect(decodeURIComponent(url?.split('?text=')[1] ?? '')).toMatch(/^Hi, this is/);
  });
});

describe('branchWhatsappNumber', () => {
  it('prefers the WhatsApp number, else the branch phone', () => {
    expect(branchWhatsappNumber(BRANCH)).toBe('919000000001');
    expect(branchWhatsappNumber({ name: 'X', phone: '+91 98765 43210', whatsapp_phone: null })).toBe(
      '919876543210',
    );
  });

  it('is null without a usable mobile', () => {
    expect(branchWhatsappNumber({ name: 'X', phone: '080 4123 4567', whatsapp_phone: null })).toBeNull();
    expect(branchWhatsappNumber(null)).toBeNull();
  });
});

describe('digestEntry', () => {
  it('lists name (or Unknown), +91 phone, time, status and a 60-char note', () => {
    const text = digestEntry(
      item(1, { name: null, is_overdue: true, last_note: 'x'.repeat(100) }),
      1,
    );
    const [first, second, third] = text.split('\n');
    expect(first).toBe('1. Unknown · +91 9876500001');
    expect(second).toMatch(/^ {3}Overdue .* · Follow-up$/);
    expect(third).toBe(`   Note: ${'x'.repeat(59)}…`);
  });
});

describe('buildFollowUpDigest (property 9 cases)', () => {
  it('includes every lead when it fits', () => {
    const d = buildFollowUpDigest([item(1, { is_overdue: true }), item(2)], 'Hulimavu');
    expect(d.included).toBe(2);
    expect(d.omitted).toBe(0);
    expect(d.text.startsWith('Follow-ups for Hulimavu: 2 (1 overdue)')).toBe(true);
    expect(d.text).not.toContain('more in admin');
  });

  it('stops before the cap and ends with "+N more in admin"', () => {
    const items = Array.from({ length: 80 }, (_, i) =>
      item(i + 1, { last_note: 'Wants a birthday setup with balloons and a cake' }),
    );
    const d = buildFollowUpDigest(items, 'Hulimavu');
    expect(d.text.length).toBeLessThanOrEqual(DIGEST_MAX_CHARS);
    expect(d.included).toBeGreaterThan(0);
    expect(d.included + d.omitted).toBe(80);
    expect(d.text.endsWith(`+${d.omitted} more in admin`)).toBe(true);
  });

  it.each([1, 2, 5, 20, 60])('never exceeds the cap with %i leads', (n) => {
    const items = Array.from({ length: n }, (_, i) => item(i + 1, { last_note: 'n'.repeat(80) }));
    const d = buildFollowUpDigest(items, 'Hulimavu', 600);
    expect(d.text.length).toBeLessThanOrEqual(600);
    expect(d.included + d.omitted).toBe(n);
  });
});

describe('digestState', () => {
  it.each([
    [{ name: 'X', phone: null, whatsapp_phone: null }, [item(1)], 'no_number'],
    [{ name: 'X', phone: '080 4123 4567', whatsapp_phone: null }, [item(1)], 'no_number'],
    [BRANCH, [], 'nothing_due'],
    [BRANCH, [item(1)], 'ready'],
  ] as const)('%o with %i items → %s', (branch, items, kind) => {
    expect(digestState(branch, [...items]).kind).toBe(kind);
  });

  it('shows the hints from the requirements', () => {
    const none = digestState({ name: 'X', phone: null }, [item(1)]);
    expect(none.kind === 'no_number' && none.hint).toBe(
      'Add a branch WhatsApp number in Location settings',
    );
    const empty = digestState(BRANCH, []);
    expect(empty.kind === 'nothing_due' && empty.hint).toBe('No follow-ups due');
  });

  it('opens the branch WhatsApp with the digest', () => {
    const ready = digestState(BRANCH, [item(1)]);
    expect(ready.kind).toBe('ready');
    if (ready.kind === 'ready') {
      expect(ready.url.startsWith('https://wa.me/919000000001?text=')).toBe(true);
      expect(decodeURIComponent(ready.url.split('?text=')[1])).toBe(ready.digest.text);
    }
  });
});

describe('convert to booking', () => {
  const lead = {
    id: 7,
    location_id: 2,
    phone: '9876543210',
    name: ' Asha ',
    status: 'contacted',
    booking_id: null,
    preferred_date: '2026-11-20',
    plan_id: 3,
    guests: 5,
  } as LeadRead;

  it('pre-fills name, phone, branch, date, plan and guests', () => {
    const state = buildLeadPrefill(lead, '2026-11-14');
    expect(state.fromLead).toEqual({
      leadId: 7,
      locationId: 2,
      label: 'Asha',
      initial: {
        location_id: 2,
        booking_name: 'Asha',
        phone: '9876543210',
        booking_date: '2026-11-20',
        people: 5,
        plan_id: 3,
      },
    });
  });

  it('uses today instead of a past preferred date', () => {
    expect(buildLeadPrefill(lead, '2026-11-25').fromLead.initial.booking_date).toBe('2026-11-25');
  });

  it('is read back only for the same branch', () => {
    const state = buildLeadPrefill(lead, '2026-11-14');
    expect(readLeadPrefill(state, 2)?.leadId).toBe(7);
    expect(readLeadPrefill(state, 1)).toBeNull();
    expect(readLeadPrefill(null, 2)).toBeNull();
    expect(readLeadPrefill({ fromLead: { leadId: 'x' } }, 2)).toBeNull();
  });

  it('is offered only for open leads without a booking', () => {
    expect(canConvert(lead)).toBe(true);
    expect(canConvert({ ...lead, booking_id: 3 })).toBe(false);
    expect(canConvert({ ...lead, status: 'lost' })).toBe(false);
    expect(canConvert({ ...lead, status: 'booked' })).toBe(false);
  });
});

describe('timeline labels', () => {
  const base: ActivityRead = {
    id: 1,
    type: 'note',
    text: 'Hi',
    data: null,
    author_user_id: null,
    author_name: null,
    created_at: '2026-11-10T06:30:00Z',
  };

  it('names the author, the customer or the system', () => {
    expect(activityAuthor({ ...base, author_name: 'priya' })).toBe('priya');
    expect(activityAuthor(base)).toBe('Customer');
    expect(activityAuthor({ ...base, type: 'system' })).toBe('System');
  });

  it('summarises status changes', () => {
    expect(
      activitySummary({ ...base, type: 'status_change', data: { from: 'new', to: 'contacted' } }),
    ).toBe('New → Contacted');
  });
});
