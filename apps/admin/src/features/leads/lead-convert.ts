/**
 * Build the booking-form pre-fill for "Create booking" on a lead (lead-crm
 * R9.1, R9.2): name, phone, branch, preferred date (not in the past), plan and
 * guests where present.
 */

import type { LeadPrefillState } from '@/features/bookings/lead-prefill';
import { CONVERTIBLE_STATUSES, type LeadRead } from './types';

/** "Create booking" is offered on an open lead with no booking yet (R9.1, R9.5). */
export function canConvert(lead: Pick<LeadRead, 'status' | 'booking_id'>): boolean {
  return lead.booking_id === null && CONVERTIBLE_STATUSES.includes(lead.status);
}

export function buildLeadPrefill(lead: LeadRead, todayIso: string): LeadPrefillState {
  const date =
    lead.preferred_date && lead.preferred_date >= todayIso ? lead.preferred_date : todayIso;
  return {
    fromLead: {
      leadId: lead.id,
      locationId: lead.location_id,
      label: lead.name?.trim() || lead.phone,
      initial: {
        location_id: lead.location_id,
        booking_name: lead.name?.trim() ?? '',
        phone: lead.phone,
        booking_date: date,
        people: lead.guests && lead.guests > 0 ? lead.guests : 1,
        ...(lead.plan_id ? { plan_id: lead.plan_id } : {}),
      },
    },
  };
}
