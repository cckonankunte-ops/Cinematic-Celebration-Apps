/**
 * "Create booking" from a lead (lead-crm R9.2, R9.3): the lead page navigates to
 * `/bookings/new` with this router state. The form is pre-filled and the
 * booking is sent with `lead_id`, so the lead links to it (server-side, in the
 * same transaction). A direct visit to `/bookings/new` has no state and is unchanged.
 */

import type { BookingCreateInput } from './booking-schema';

export interface LeadPrefill {
  leadId: number;
  locationId: number;
  /** Name or phone, for the banner. */
  label: string;
  initial: Partial<BookingCreateInput>;
}

export interface LeadPrefillState {
  fromLead: LeadPrefill;
}

/** The pre-fill from router state, only when it targets the branch being booked. */
export function readLeadPrefill(state: unknown, locationId: number): LeadPrefill | null {
  if (typeof state !== 'object' || state === null || !('fromLead' in state)) {
    return null;
  }
  const p = (state as Partial<LeadPrefillState>).fromLead;
  if (
    !p ||
    typeof p.leadId !== 'number' ||
    typeof p.locationId !== 'number' ||
    typeof p.label !== 'string' ||
    typeof p.initial !== 'object' ||
    p.initial === null
  ) {
    return null;
  }
  return p.locationId === locationId ? p : null;
}
