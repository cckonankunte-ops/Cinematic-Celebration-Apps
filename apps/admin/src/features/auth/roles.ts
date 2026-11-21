/**
 * Roles (mirrors `app/core/security.py`):
 * - admin: everything, all branches;
 * - staff: bookings, payments, time and cake sheets for their branch;
 * - receptionist: everything staff can do, plus the lead CRM for their branch.
 */

import type { UserRole } from './types';

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Admin',
  staff: 'Staff',
  receptionist: 'Receptionist',
};

/** Roles that can open the lead CRM (customer numbers and sales notes). */
export const LEAD_ROLES: UserRole[] = ['admin', 'receptionist'];

export function canUseLeads(role: UserRole | null | undefined): boolean {
  return role !== null && role !== undefined && LEAD_ROLES.includes(role);
}
