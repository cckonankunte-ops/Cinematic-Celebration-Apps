/**
 * Auth domain types mirroring the API's `CurrentUserRead` schema.
 * `location_id` is null for admins (who see all locations).
 */

/** receptionist = staff + the lead CRM (see `roles.ts`). */
export type UserRole = 'admin' | 'staff' | 'receptionist';

/** The authenticated user returned by `/auth/login` and `/auth/me`. */
export interface AuthUser {
  id: number;
  username: string;
  role: UserRole;
  location_id: number | null;
}
