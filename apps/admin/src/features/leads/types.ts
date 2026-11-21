/**
 * Lead CRM types for the admin panel. Hand-written to match the API's
 * `app/schemas/lead.py` (see `src/api/schema.ts` for the generated contract).
 */

export type LeadStatus =
  | 'new'
  | 'contacted'
  | 'follow_up'
  | 'booked'
  | 'won'
  | 'not_interested'
  | 'lost';

export type LeadSource =
  | 'website'
  | 'homepage_form'
  | 'contact_form'
  | 'whatsapp'
  | 'whatsapp_ad'
  | 'phone'
  | 'walk_in'
  | 'instagram_dm'
  | 'other';

/** Sources a receptionist can pick in quick-add (API `ManualSource`). */
export type ManualSource = 'whatsapp' | 'whatsapp_ad' | 'phone' | 'walk_in' | 'instagram_dm' | 'other';

export type LeadChannel =
  | 'meta_ads'
  | 'google_ads'
  | 'google_business_profile'
  | 'google_search'
  | 'instagram_organic'
  | 'facebook_organic'
  | 'other_referral'
  | 'direct'
  | 'manual';

export type CloseReason =
  | 'price_budget'
  | 'date_not_available'
  | 'booked_elsewhere'
  | 'no_response'
  | 'just_enquiring'
  | 'other';

export type ActivityType =
  | 'note'
  | 'call'
  | 'whatsapp'
  | 'status_change'
  | 'follow_up_set'
  | 'booking_linked'
  | 'system';

export interface ActivityRead {
  id: number;
  type: ActivityType;
  text: string | null;
  data: Record<string, unknown> | null;
  author_user_id: number | null;
  author_name: string | null;
  created_at: string;
}

export interface LeadBrief {
  id: number;
  location_id: number;
  location_name: string;
  status: LeadStatus;
  source: LeadSource;
  created_at: string;
}

export interface AttributionSummary {
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  landing_path: string | null;
  referrer_domain: string | null;
  has_fbclid: boolean;
  has_gclid: boolean;
}

export interface LeadRead {
  id: number;
  location_id: number;
  phone: string;
  name: string | null;
  source: LeadSource;
  status: LeadStatus;
  channel: LeadChannel;
  close_reason: CloseReason | null;
  close_reason_text: string | null;
  assigned_user_id: number | null;
  assigned_user_name: string | null;
  follow_up_at: string | null;
  last_activity_at: string;
  first_contacted_at: string | null;
  is_uncontacted: boolean;
  minutes_since_created: number;
  booking_id: number | null;
  booking_reference: string | null;
  preferred_date: string | null;
  plan_id: number | null;
  plan_title: string | null;
  start_time: string | null;
  duration_minutes: number | null;
  guests: number | null;
  message: string | null;
  attribution: AttributionSummary;
  enquiry_code: string | null;
  created_at: string;
  activities?: ActivityRead[];
  same_phone_leads?: LeadBrief[];
}

export interface LeadListPage {
  items: LeadRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface LeadCounts {
  uncontacted: number;
  overdue: number;
  due_today: number;
}

/** One overdue / due-today lead for the branch WhatsApp digest (R11.2). */
export interface FollowUpItem {
  id: number;
  name: string | null;
  phone: string;
  status: LeadStatus;
  follow_up_at: string;
  is_overdue: boolean;
  last_note: string | null;
}

export interface FollowUpDigest {
  items: FollowUpItem[];
}

export interface AssignableUser {
  id: number;
  username: string;
  role: 'admin' | 'receptionist';
}

export interface LeadCreateBody {
  location_id: number;
  phone: string;
  source: ManualSource;
  name?: string;
  note?: string;
  follow_up_at?: string;
  enquiry_code?: string;
}

export interface LeadCreateResult {
  lead: LeadRead;
  created: boolean;
  warning: string | null;
  code_used_by_lead_id: number | null;
}

/** PATCH body. Omitted fields are unchanged; `null` clears assignee / follow-up. */
export interface LeadUpdateBody {
  name?: string | null;
  status?: LeadStatus;
  close_reason?: CloseReason | null;
  close_reason_text?: string | null;
  assigned_user_id?: number | null;
  follow_up_at?: string | null;
}

export type ManualActivityType = 'note' | 'call' | 'whatsapp';

export interface ActivityCreateBody {
  type: ManualActivityType;
  text?: string;
}

/** Statuses a user may pick by hand (booked / won follow the booking, R7.7). */
export const MANUAL_STATUSES: LeadStatus[] = [
  'new',
  'contacted',
  'follow_up',
  'not_interested',
  'lost',
];

/** Open leads without a booking can be converted (R9.1). */
export const CONVERTIBLE_STATUSES: LeadStatus[] = ['new', 'contacted', 'follow_up'];

/** GET /admin/leads/dashboard (R13). Counts only; the UI computes percentages. */
export interface DashboardDayRow {
  day: string;
  key: string;
  count: number;
}

export interface DashboardGroupRow {
  key: string;
  total: number;
  won: number;
}

export interface LeadDashboard {
  location_id: number | null;
  date_from: string;
  date_to: string;
  total: number;
  won: number;
  per_day_by_source: DashboardDayRow[];
  per_day_by_channel: DashboardDayRow[];
  by_source: DashboardGroupRow[];
  by_channel: DashboardGroupRow[];
  contacted: number;
  avg_first_response_minutes: number | null;
  median_first_response_minutes: number | null;
  close_reasons: Array<{ reason: string; count: number }>;
  campaigns: DashboardGroupRow[];
  whatsapp_total: number;
  whatsapp_with_code: number;
}

export const STATUS_LABELS: Record<LeadStatus, string> = {
  new: 'New',
  contacted: 'Contacted',
  follow_up: 'Follow-up',
  booked: 'Booked',
  won: 'Won',
  not_interested: 'Not interested',
  lost: 'Lost',
};

export const SOURCE_LABELS: Record<LeadSource, string> = {
  website: 'Website booking',
  homepage_form: 'Homepage form',
  contact_form: 'Contact form',
  whatsapp: 'WhatsApp',
  whatsapp_ad: 'WhatsApp (from ad)',
  phone: 'Phone call',
  walk_in: 'Walk-in',
  instagram_dm: 'Instagram DM',
  other: 'Other',
};

export const CHANNEL_LABELS: Record<LeadChannel, string> = {
  meta_ads: 'Meta ads',
  google_ads: 'Google ads',
  google_business_profile: 'Google Business Profile',
  google_search: 'Google search',
  instagram_organic: 'Instagram (organic)',
  facebook_organic: 'Facebook (organic)',
  other_referral: 'Other referral',
  direct: 'Direct',
  manual: 'Manual',
};

export const CLOSE_REASON_LABELS: Record<CloseReason, string> = {
  price_budget: 'Price / budget',
  date_not_available: 'Date not available',
  booked_elsewhere: 'Booked elsewhere',
  no_response: 'No response',
  just_enquiring: 'Just enquiring',
  other: 'Other',
};

/** Quick-add sources in the order shown (WhatsApp first: most leads). */
export const MANUAL_SOURCES: ManualSource[] = [
  'whatsapp',
  'whatsapp_ad',
  'phone',
  'walk_in',
  'instagram_dm',
  'other',
];

export const CLOSED_STATUSES: LeadStatus[] = ['won', 'not_interested', 'lost'];
