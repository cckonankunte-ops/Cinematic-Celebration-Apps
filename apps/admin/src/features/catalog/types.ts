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
  description: string;
  show_combos: boolean;
  sort_order: number;
}

export interface SlotCreateBody {
  plan_id: number;
  description: string;
  show_combos: boolean;
  sort_order: number;
  effective_from: string;
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
