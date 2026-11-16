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
  /** Kids (3-10 yrs) charged this % of the extra-guest rate (0-100). */
  kid_price_pct: number;
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
  kid_price_pct?: number;
  give_discount: boolean;
  max_discount_paise: number;
  advance_paise: number;
  effective_from: string;
}

/** PATCH body for a plan: every field optional (partial update). */
export interface PlanUpdateBody {
  title?: string;
  description?: string | null;
  details?: string | null;
  plan_type?: number;
  price_paise?: number;
  people_allowed?: number;
  max_people_allowed?: number;
  extra_guest_paise?: number;
  kid_price_pct?: number;
  give_discount?: boolean;
  max_discount_paise?: number;
  advance_paise?: number;
  effective_from?: string;
  effective_to?: string;
  is_active?: boolean;
}

/** Special-decor grouping category (stored lowercase; UI maps to labels). */
export type DecorCategory = 'extra_decoration' | 'gifts' | 'special_service';

/** Display labels for decor categories, in render order. */
export const DECOR_CATEGORY_LABELS: Record<DecorCategory, string> = {
  extra_decoration: 'Extra Decoration',
  gifts: 'Choose Gifts',
  special_service: 'Special Services',
};

/** A per-branch disallowed booking-time range (admin). */
export interface DisallowedTimeRead {
  id: number;
  location_id: number;
  start_time: string; // "HH:MM:SS"
  end_time: string;
  max_duration_minutes: number | null;
  note: string | null;
  is_active: boolean;
}

export interface DisallowedTimeCreateBody {
  start_time: string; // "HH:MM"
  end_time: string;
  max_duration_minutes?: number | null;
  note?: string | null;
  is_active?: boolean;
}

/** A per-branch advance rule: final total >= min_total -> advance. */
export interface AdvanceRuleRead {
  id: number;
  location_id: number;
  min_total_paise: number;
  advance_paise: number;
  is_active: boolean;
}

export interface AdvanceRuleCreateBody {
  min_total_paise: number;
  advance_paise: number;
  is_active?: boolean;
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
  /** 'slot' (pick a configured slot) | 'open' (pick start + duration directly). */
  booking_mode: 'slot' | 'open';
  is_active: boolean;
}

export interface LocationHoursUpdateBody {
  opens_at?: string;
  closes_at?: string;
  last_online_booking_start?: string;
  allow_late_booking?: boolean;
  booking_mode?: 'slot' | 'open';
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
  /** Decor-only: grouping category. Absent for cakes/combos. */
  category?: DecorCategory;
  /** Combo-only: optional cake/LED baselines (paise). Null/absent otherwise. */
  cake_baseline_paise?: number | null;
  led_baseline_paise?: number | null;
  /** Combo-only: display "worth"/compare-at (paise); null when unset. */
  compare_at_paise?: number | null;
  /** Combo-only: server-computed max(0, worth - price), paise. */
  savings_paise?: number;
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
  /** Optional display "worth"/compare-at (paise); null/omitted = no savings. */
  compare_at_paise?: number | null;
  /** Optional image key; combos are not image tiles, so this may be omitted. */
  object_key?: string;
}

/** PATCH body for a combo: every field optional (partial update). */
export type ComboUpdateBody = Partial<
  Omit<ComboCreateBody, 'location_id'>
> & {
  object_key?: string;
  is_active?: boolean;
  effective_to?: string;
};

/** Create body for a cake add-on (object_key from a prior image upload). */
export interface CakeCreateBody {
  location_id: number;
  description: string;
  price_paise: number;
  object_key: string;
  effective_from: string;
}

/** PATCH body for a cake: every field optional (partial update). */
export interface CakeUpdateBody {
  description?: string;
  price_paise?: number;
  object_key?: string;
  is_active?: boolean;
  effective_to?: string;
}

/** Create body for a special-decor add-on. */
export interface DecorCreateBody {
  location_id: number;
  name: string;
  description: string;
  category?: DecorCategory;
  price_paise: number;
  object_key: string;
  sort_order: number;
  effective_from: string;
}

/** PATCH body for a special-decor item: every field optional. */
export interface DecorUpdateBody {
  name?: string;
  description?: string;
  category?: DecorCategory;
  price_paise?: number;
  object_key?: string;
  sort_order?: number;
  is_active?: boolean;
  effective_to?: string;
}

/** Response from the catalog add-on image upload endpoint. */
export interface CatalogImageUploadRead {
  object_key: string;
  upload_url: string;
}

/** The add-on kind for an image upload. */
export type CatalogImageKind = 'cake' | 'decor' | 'combo';

/** The far-future validity end used when (re)activating catalog rows. */
export const FAR_FUTURE_DATE = '2099-12-31';
