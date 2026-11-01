/**
 * Admin catalog domain types, mirroring the API's `catalog_admin` schemas.
 * Admin reads expose `is_active` and the validity window; money is integer
 * paise. Create/Update bodies send plain IDs + money as paise. "Delete" is a
 * soft-delete (deactivate) server-side.
 */

/** Fields shared by every catalog validity window. */
interface Validity {
  effective_from: string;
  effective_to: string;
  is_active: boolean;
}

export interface PlanAdminRead extends Validity {
  id: number;
  location_id: number;
  title: string;
  description: string | null;
  details: string | null;
  plan_type: number;
  price_paise: number;
  people_allowed: number;
  max_people_allowed: number;
  extra_guest_paise: number;
  give_discount: boolean;
  max_discount_paise: number;
  advance_paise: number;
}

export interface PlanCreateBody {
  location_id: number;
  title: string;
  plan_type: number;
  price_paise: number;
  people_allowed: number;
  max_people_allowed: number;
  extra_guest_paise: number;
  give_discount: boolean;
  max_discount_paise: number;
  advance_paise: number;
  effective_from: string;
}

export interface SlotAdminRead extends Validity {
  id: number;
  plan_id: number;
  /** IST "HH:MM:SS" (or null for legacy rows). */
  start_time: string | null;
  duration_minutes: number | null;
  description: string;
  show_combos: boolean;
  sort_order: number;
}

export interface SlotCreateBody {
  plan_id: number;
  /** IST "HH:MM"; must be on the hour or half-hour. */
  start_time: string;
  duration_minutes: number;
  /** Optional label; derived from start+duration when blank. */
  description?: string;
  show_combos: boolean;
  sort_order: number;
  effective_from: string;
}

/** Per-duration base price + advance for a plan (R11). Money is integer paise. */
export interface PlanPricingAdminRead extends Validity {
  id: number;
  plan_id: number;
  duration_minutes: number;
  price_paise: number;
  advance_paise: number;
}

export interface PlanPricingCreateBody {
  plan_id: number;
  duration_minutes: number;
  price_paise: number;
  advance_paise: number;
  effective_from: string;
}

/** Admin view of a location's working hours + online-booking policy. */
export interface LocationAdminRead {
  id: number;
  name: string;
  slug: string;
  opens_at: string;
  closes_at: string;
  last_online_booking_start: string;
  allow_late_booking: boolean;
  is_active: boolean;
}

export interface LocationHoursUpdateBody {
  opens_at?: string;
  closes_at?: string;
  last_online_booking_start?: string;
  allow_late_booking?: boolean;
}

/** Shared shape for location add-ons (cakes/decor/combos) with an image URL. */
export interface AddonAdminRead extends Validity {
  id: number;
  location_id: number;
  price_paise: number;
  object_key: string;
  image_url: string;
}

export interface CakeAdminRead extends AddonAdminRead {
  description: string;
}

export interface NamedAddonAdminRead extends AddonAdminRead {
  name: string;
  description: string;
  /** Combo-only: optional cake/LED baselines (paise). Null/absent otherwise. */
  cake_baseline_paise?: number | null;
  led_baseline_paise?: number | null;
}

export interface GalleryImageRead {
  id: number;
  plan_id: number;
  object_key: string;
  image_url: string;
  sort_order: number;
  upload_url: string | null;
}

export interface GalleryUploadBody {
  filename: string;
  sort_order: number;
}

/**
 * Create body for a combo add-on. Combos may optionally carry a cake and/or LED
 * baseline (integer paise) that the pricing engine floors combo deltas against.
 * A null baseline means the combo does not absorb that component.
 */
export interface ComboCreateBody {
  location_id: number;
  name: string;
  description: string;
  price_paise: number;
  effective_from: string;
  cake_baseline_paise?: number | null;
  led_baseline_paise?: number | null;
}

/** PATCH body for a combo: every field optional (partial update). */
export type ComboUpdateBody = Partial<Omit<ComboCreateBody, 'location_id'>>;
