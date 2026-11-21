/**
 * Landing_Store (lead-crm R17): remembers where a visitor first came from.
 *
 * Runs on every page (bundled script in Base.astro). Rules:
 * - campaign params (utm_*, fbclid, gclid) on the URL replace the store;
 * - with no campaign params, an existing fresh store is kept unchanged;
 * - an empty or > 30-day-old store is written with whatever is present
 *   (a referrer, or just the landing path for a direct visit);
 * - stored landing path and referrer never include a query string;
 * - only URL data is stored: never a name, phone or email (R17.7);
 * - storage errors are swallowed; without storage the current page's
 *   attribution is used (R17.6).
 *
 * Field names match the API's `AttributionIn` so the object is sent as is.
 */

export interface Landing {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  fbclid?: string;
  gclid?: string;
  landing_path?: string;
  referrer?: string;
  /** ISO timestamp of when this attribution was captured. */
  landed_at: string;
}

export const LANDING_KEY = 'cc.landing.v1';
export const LANDING_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

const UTM_KEYS = [
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'utm_term',
] as const;
const CLICK_KEYS = ['fbclid', 'gclid'] as const;
const CAMPAIGN_KEYS = [...UTM_KEYS, ...CLICK_KEYS] as const;
// Same limits as the API (UTM_MAX / URLISH_MAX); longer values are cut, not sent.
const UTM_MAX = 200;
const URLISH_MAX = 500;

function safeLocalStorage(): Storage | null {
  try {
    const storage = window.localStorage;
    // Accessing it can throw (privacy modes); a read proves it is usable.
    storage.getItem(LANDING_KEY);
    return storage;
  } catch {
    return null;
  }
}

function clean(value: string | null, max: number): string | undefined {
  const trimmed = (value ?? '').trim();
  return trimmed ? trimmed.slice(0, max) : undefined;
}

/** Origin + path of the referrer, or undefined when absent, invalid or our own site. */
function cleanReferrer(referrer: string, pageHost: string): string | undefined {
  if (!referrer) {
    return undefined;
  }
  try {
    const ref = new URL(referrer);
    if (ref.host === pageHost) {
      return undefined;
    }
    return `${ref.origin}${ref.pathname}`.slice(0, URLISH_MAX);
  } catch {
    return undefined;
  }
}

/** Attribution for one page view (no storage involved). */
export function attributionFromPage(href: string, referrer: string, now: Date): Landing {
  const url = new URL(href);
  const landing: Landing = { landed_at: now.toISOString() };
  for (const key of UTM_KEYS) {
    const value = clean(url.searchParams.get(key), UTM_MAX);
    if (value) landing[key] = value;
  }
  for (const key of CLICK_KEYS) {
    const value = clean(url.searchParams.get(key), URLISH_MAX);
    if (value) landing[key] = value;
  }
  landing.landing_path = url.pathname.slice(0, URLISH_MAX);
  const ref = cleanReferrer(referrer, url.host);
  if (ref) landing.referrer = ref;
  return landing;
}

export function hasCampaign(landing: Landing): boolean {
  return CAMPAIGN_KEYS.some((key) => Boolean(landing[key]));
}

function parseStored(raw: string | null, now: Date): Landing | null {
  if (!raw) {
    return null;
  }
  try {
    const value = JSON.parse(raw) as unknown;
    if (typeof value !== 'object' || value === null) {
      return null;
    }
    const landing = value as Landing;
    const at = Date.parse(landing.landed_at);
    if (Number.isNaN(at) || now.getTime() - at > LANDING_MAX_AGE_MS) {
      return null;
    }
    return landing;
  } catch {
    return null;
  }
}

/** Read a fresh stored landing, or null (missing, expired, unreadable). */
function readStored(storage: Storage | null, now: Date): Landing | null {
  if (!storage) {
    return null;
  }
  try {
    return parseStored(storage.getItem(LANDING_KEY), now);
  } catch {
    return null;
  }
}

/**
 * Apply the Landing_Store rules for this page view and return the attribution
 * that should be used from now on.
 */
export function captureLanding(href: string, referrer: string, now: Date): Landing {
  const current = attributionFromPage(href, referrer, now);
  const storage = safeLocalStorage();
  const stored = readStored(storage, now);
  if (stored && !hasCampaign(current)) {
    return stored;
  }
  if (storage) {
    try {
      storage.setItem(LANDING_KEY, JSON.stringify(current));
    } catch {
      // Quota or privacy mode: keep working with the current page only.
    }
  }
  return current;
}

/**
 * Attribution to send with a lead or enquiry code: the fresh stored landing,
 * else the current page's attribution (storage unavailable or empty).
 */
export function readLanding(now: Date = new Date()): Landing | null {
  const stored = readStored(safeLocalStorage(), now);
  if (stored) {
    return stored;
  }
  try {
    return attributionFromPage(window.location.href, document.referrer, now);
  } catch {
    return null;
  }
}
