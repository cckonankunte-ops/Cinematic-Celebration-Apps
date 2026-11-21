/**
 * Booking wizard Step 1 lead capture (lead-crm R2.4-R2.6, R2.8).
 *
 * `sendStep1Lead` posts the Step 1 details when the visitor taps Next. It is
 * fire-and-forget: callers do not await it, it never throws, and a failed or
 * slow request never blocks the wizard. The returned lead token is kept in
 * sessionStorage (this tab only) so later Next taps update the same lead and
 * the final booking request links to it.
 */

import { publicApi, type WebsiteLeadIn } from './api';
import { readLanding } from './landing';
import { normaliseIndianMobile } from './phone';

export const LEAD_TOKEN_KEY = 'cc.leadToken';

export interface Step1Details {
  locationId: number;
  phone: string;
  name?: string;
  preferredDate?: string;
  planId?: number;
  /** "HH:MM" or "HH:MM:SS" (IST); omitted when no time is chosen yet. */
  startTime?: string | null;
  durationMinutes?: number | null;
  guests?: number;
}

function session(): Storage | null {
  try {
    const storage = window.sessionStorage;
    storage.getItem(LEAD_TOKEN_KEY);
    return storage;
  } catch {
    return null;
  }
}

export function getLeadToken(): string | null {
  try {
    return session()?.getItem(LEAD_TOKEN_KEY) || null;
  } catch {
    return null;
  }
}

function saveLeadToken(token: string): void {
  try {
    session()?.setItem(LEAD_TOKEN_KEY, token);
  } catch {
    // Storage full or blocked: the booking still works without the link.
  }
}

/**
 * Send (or update) the Step 1 lead. Resolves when done and never rejects, so
 * tests can await it; the wizard calls it with `void` and moves on at once.
 */
export function sendStep1Lead(details: Step1Details): Promise<void> {
  try {
    const phone = normaliseIndianMobile(details.phone);
    if (!phone) {
      return Promise.resolve();
    }
    const body: WebsiteLeadIn = {
      location_id: details.locationId,
      phone,
      name: details.name?.trim() || undefined,
      preferred_date: details.preferredDate || undefined,
      plan_id: details.planId,
      start_time: details.startTime || undefined,
      duration_minutes: details.durationMinutes ?? undefined,
      guests: details.guests && details.guests > 0 ? details.guests : undefined,
      lead_token: getLeadToken() ?? undefined,
      attribution: readLanding(),
    };
    return publicApi
      .createLead(body)
      .then((res) => {
        if (res?.lead_token) saveLeadToken(res.lead_token);
      })
      .catch(() => undefined);
  } catch {
    return Promise.resolve();
  }
}
