/**
 * WhatsApp links with an enquiry code (lead-crm R18.1, R18.3, R18.4, R18.14).
 *
 * The link's number is the branch WhatsApp number, falling back to the branch
 * phone. The pre-filled message ends with "Enquiry code: <code>". On tap the
 * code is registered with a keepalive request (never awaited, errors ignored),
 * so WhatsApp always opens. The request carries only the code, the branch id
 * and URL-derived attribution: never a phone, name or chat text.
 */

import { buildUrl } from './api';
import { readLanding } from './landing';
import { normaliseIndianMobile } from './phone';

export interface WhatsappBranch {
  id: number;
  name: string;
  phone: string | null;
  whatsapp_phone?: string | null;
}

/** `wa.me` number (country code + digits) for a branch, or null when unusable. */
export function whatsappNumber(branch: WhatsappBranch): string | null {
  const mobile =
    normaliseIndianMobile(branch.whatsapp_phone) ?? normaliseIndianMobile(branch.phone);
  if (mobile) {
    return `91${mobile}`;
  }
  // Not an Indian mobile (e.g. a landline with country code): use its digits.
  const digits = (branch.whatsapp_phone || branch.phone || '')
    .replace(/\D/g, '')
    .replace(/^0+/, '');
  return digits.length >= 10 ? digits : null;
}

export function whatsappMessage(branchName: string, code: string | null): string {
  const greeting =
    `Hi Cinematic Celebration (${branchName})! ` +
    "I'd like to know more about booking a celebration. 🎬";
  return code ? `${greeting}\nEnquiry code: ${code}` : greeting;
}

/** Full `https://wa.me/...` link, or null when the branch has no usable number. */
export function buildWhatsappLink(branch: WhatsappBranch, code: string | null): string | null {
  const number = whatsappNumber(branch);
  if (!number) {
    return null;
  }
  return `https://wa.me/${number}?text=${encodeURIComponent(whatsappMessage(branch.name, code))}`;
}

/**
 * Fire-and-forget registration of the code for the tapped branch. Never throws
 * and is never awaited by callers, so it cannot delay or block WhatsApp.
 */
export function registerEnquiryCode(
  code: string,
  locationId: number | null,
  fetchImpl: typeof fetch = fetch,
): void {
  try {
    const body = { code, location_id: locationId, attribution: readLanding() };
    void fetchImpl(buildUrl('/api/v1/public/enquiry-codes'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // e.g. fetch unavailable: WhatsApp still opens.
  }
}
