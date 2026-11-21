import { beforeEach, describe, expect, it } from 'vitest';

import { presetToIso } from './follow-up-presets';
import {
  DEFAULT_LEAD_FILTERS,
  loadLeadFilters,
  saveLeadFilters,
} from './lead-filter-state';
import { buildLeadListQuery } from './lead-queries';
import { quickAddSchema } from './lead-schema';
import { groupBySection, leadSection, uncontactedLabel } from './lead-sections';
import { quickAddToast } from './lead-toast';
import type { LeadRead } from './types';

// 12:00 IST on 10 Nov 2026.
const NOW = new Date('2026-11-10T06:30:00Z');
const at = (minutes: number) => new Date(NOW.getTime() + minutes * 60_000).toISOString();

function lead(overrides: Partial<LeadRead> = {}): LeadRead {
  return {
    id: 1,
    location_id: 1,
    phone: '9876543210',
    name: null,
    source: 'whatsapp',
    status: 'new',
    channel: 'manual',
    close_reason: null,
    close_reason_text: null,
    assigned_user_id: null,
    assigned_user_name: null,
    follow_up_at: null,
    last_activity_at: at(-5),
    first_contacted_at: null,
    is_uncontacted: false,
    minutes_since_created: 5,
    booking_id: null,
    booking_reference: null,
    preferred_date: null,
    plan_id: null,
    plan_title: null,
    start_time: null,
    duration_minutes: null,
    guests: null,
    message: null,
    attribution: {
      utm_source: null,
      utm_medium: null,
      utm_campaign: null,
      landing_path: null,
      referrer_domain: null,
      has_fbclid: false,
      has_gclid: false,
    },
    enquiry_code: null,
    created_at: at(-5),
    ...overrides,
  };
}

describe('leadSection', () => {
  it('puts each lead in its section, in the server order', () => {
    expect(leadSection(lead({ is_uncontacted: true, minutes_since_created: 30 }), NOW)).toBe(
      'uncontacted',
    );
    expect(leadSection(lead({ status: 'follow_up', follow_up_at: at(-30) }), NOW)).toBe('overdue');
    expect(leadSection(lead({ status: 'follow_up', follow_up_at: at(120) }), NOW)).toBe(
      'due_today',
    );
    expect(leadSection(lead(), NOW)).toBe('new');
    expect(leadSection(lead({ status: 'follow_up', follow_up_at: at(24 * 60) }), NOW)).toBe(
      'other',
    );
    expect(leadSection(lead({ status: 'contacted' }), NOW)).toBe('other');
  });

  it('never counts a closed lead as overdue', () => {
    expect(
      leadSection(lead({ status: 'lost', follow_up_at: at(-30), close_reason: 'other' }), NOW),
    ).toBe('other');
  });

  it('groups consecutive leads under one heading', () => {
    const groups = groupBySection(
      [
        lead({ id: 1, is_uncontacted: true }),
        lead({ id: 2, is_uncontacted: true }),
        lead({ id: 3, status: 'follow_up', follow_up_at: at(-10) }),
        lead({ id: 4 }),
      ],
      NOW,
    );
    expect(groups.map((g) => [g.section, g.leads.map((l) => l.id)])).toEqual([
      ['uncontacted', [1, 2]],
      ['overdue', [3]],
      ['new', [4]],
    ]);
  });
});

describe('uncontactedLabel', () => {
  it('shows minutes, then hours, then days', () => {
    expect(uncontactedLabel(25)).toBe('Not contacted · 25 min');
    expect(uncontactedLabel(135)).toBe('Not contacted · 2 h 15 min');
    expect(uncontactedLabel(3 * 24 * 60)).toBe('Not contacted · 3 d');
  });
});

describe('quickAddSchema', () => {
  it('normalises the phone to 10 digits and drops blanks', () => {
    const parsed = quickAddSchema.parse({
      phone: '+91 98765 43210',
      source: 'whatsapp',
      location_id: 2,
      name: '  ',
      note: '',
      follow_up_at: '',
      enquiry_code: 'w4k7xq',
    });
    expect(parsed).toEqual({
      phone: '9876543210',
      source: 'whatsapp',
      location_id: 2,
      name: undefined,
      note: undefined,
      follow_up_at: undefined,
      enquiry_code: 'W4K7XQ',
    });
  });

  it('rejects an invalid phone and a malformed enquiry code', () => {
    const result = quickAddSchema.safeParse({
      phone: '12345',
      source: 'whatsapp',
      location_id: 1,
      enquiry_code: 'ABC',
    });
    expect(result.success).toBe(false);
    const paths = result.success ? [] : result.error.issues.map((i) => i.path[0]);
    expect(paths).toEqual(expect.arrayContaining(['phone', 'enquiry_code']));
  });

  it('is idempotent, so parsing already-parsed values is safe', () => {
    const once = quickAddSchema.parse({ phone: '098765 43210', source: 'phone', location_id: 1 });
    expect(quickAddSchema.parse(once)).toEqual(once);
  });
});

describe('quickAddToast', () => {
  const base = { lead: lead({ id: 9 }), created: true, warning: null, code_used_by_lead_id: null };

  it('says created or attached', () => {
    expect(quickAddToast(base)).toEqual({ message: 'Lead added.', tone: 'success' });
    expect(quickAddToast({ ...base, created: false }).message).toMatch(/already has an open lead/);
  });

  it('adds the code warning and the shared-code notice', () => {
    const t = quickAddToast({ ...base, warning: 'Unknown or expired enquiry code.', code_used_by_lead_id: 4 });
    expect(t.tone).toBe('warning');
    expect(t.message).toContain('Unknown or expired enquiry code.');
    expect(t.message).toContain('lead #4');
  });
});

describe('buildLeadListQuery', () => {
  it('repeats multi-value filters and skips short searches', () => {
    const qs = buildLeadListQuery(3, {
      ...DEFAULT_LEAD_FILTERS,
      statuses: ['new', 'follow_up'],
      sources: ['whatsapp'],
      channel: 'meta_ads',
      q: 'as',
    });
    const params = new URLSearchParams(qs);
    expect(params.get('location_id')).toBe('3');
    expect(params.getAll('status')).toEqual(['new', 'follow_up']);
    expect(params.getAll('source')).toEqual(['whatsapp']);
    expect(params.get('channel')).toBe('meta_ads');
    expect(params.has('q')).toBe(false);
    expect(new URLSearchParams(buildLeadListQuery(3, { ...DEFAULT_LEAD_FILTERS, q: 'asha' })).get('q')).toBe(
      'asha',
    );
  });
});

describe('lead filter state', () => {
  beforeEach(() => window.sessionStorage.clear());

  it('round-trips through sessionStorage', () => {
    const state = { ...DEFAULT_LEAD_FILTERS, q: 'ravi', statuses: ['new' as const], offset: 50 };
    saveLeadFilters(state);
    expect(loadLeadFilters()).toEqual(state);
  });

  it('falls back to defaults for bad stored values', () => {
    window.sessionStorage.setItem('cc.admin.leadListFilters', '{"statuses": 5, "limit": "x"}');
    expect(loadLeadFilters()).toEqual(DEFAULT_LEAD_FILTERS);
  });
});

describe('presetToIso (IST)', () => {
  it('computes each preset from now', () => {
    expect(presetToIso('in_1h', NOW)).toBe('2026-11-10T07:30:00.000Z');
    expect(presetToIso('this_evening', NOW)).toBe('2026-11-10T13:30:00.000Z'); // 7 pm IST
    expect(presetToIso('tomorrow_11', NOW)).toBe('2026-11-11T05:30:00.000Z'); // 11 am IST
    expect(presetToIso('in_3_days', NOW)).toBe('2026-11-13T05:30:00.000Z');
  });

  it('moves "this evening" to tomorrow after 7 pm IST', () => {
    const late = new Date('2026-11-10T14:00:00Z'); // 7:30 pm IST
    expect(presetToIso('this_evening', late)).toBe('2026-11-11T13:30:00.000Z');
  });
});
