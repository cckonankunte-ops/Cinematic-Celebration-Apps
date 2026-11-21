/**
 * Toast passed through router state when a lead page opens after a save
 * (quick-add today; the detail page reads it).
 */

import type { LeadCreateResult } from './types';

export interface LeadToast {
  message: string;
  tone: 'success' | 'warning';
}

export interface LeadToastState {
  toast?: LeadToast;
}

/** Toast text for a save result: created vs attached, plus any code warning/notice. */
export function quickAddToast(result: LeadCreateResult): LeadToast {
  const parts = [
    result.created
      ? 'Lead added.'
      : 'This number already has an open lead, so the details were added to it.',
  ];
  if (result.warning) parts.push(result.warning);
  if (result.code_used_by_lead_id) {
    parts.push(`This enquiry code is also on lead #${result.code_used_by_lead_id}.`);
  }
  return {
    message: parts.join(' '),
    tone: result.warning || result.code_used_by_lead_id ? 'warning' : 'success',
  };
}
