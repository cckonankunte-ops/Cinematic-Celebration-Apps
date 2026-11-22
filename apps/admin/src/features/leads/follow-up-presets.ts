/**
 * Follow-up presets (lead-crm R10.5), all in IST: in 1 hour, this evening
 * (7 pm), tomorrow 11 am, in 3 days (11 am). "This evening" moves to tomorrow
 * 7 pm once 7 pm has passed, so a preset is never in the past.
 */

import { istParts, istToIso } from '@/lib/dates';

export type FollowUpPreset = 'in_1h' | 'this_evening' | 'tomorrow_11' | 'in_3_days';

export const PRESET_LABELS: Record<FollowUpPreset, string> = {
  in_1h: 'In 1 hour',
  this_evening: 'This evening 7 pm',
  tomorrow_11: 'Tomorrow 11 am',
  in_3_days: 'In 3 days',
};

export const PRESETS: FollowUpPreset[] = ['in_1h', 'this_evening', 'tomorrow_11', 'in_3_days'];

const DAY_MS = 24 * 60 * 60 * 1000;

function istDatePlus(now: Date, days: number): string {
  return istParts(new Date(now.getTime() + days * DAY_MS)).date;
}

/** ISO timestamp for a preset, relative to `now`. */
export function presetToIso(preset: FollowUpPreset, now: Date = new Date()): string {
  switch (preset) {
    case 'in_1h':
      return new Date(now.getTime() + 60 * 60 * 1000).toISOString();
    case 'this_evening': {
      const today = istToIso(istParts(now).date, '19:00');
      return new Date(today) > now ? today : istToIso(istDatePlus(now, 1), '19:00');
    }
    case 'tomorrow_11':
      return istToIso(istDatePlus(now, 1), '11:00');
    case 'in_3_days':
      return istToIso(istDatePlus(now, 3), '11:00');
  }
}
