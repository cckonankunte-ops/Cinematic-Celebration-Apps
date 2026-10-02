/**
 * Tiny typed fetch client for the public API.
 *
 * The customer site is a STATIC build; these calls run at RUNTIME inside React
 * islands in the browser. Public routes need no auth/cookies, so we keep the
 * client minimal (no credentials). The base URL comes from the PUBLIC_ env var
 * so it can differ per environment without a code change.
 */

const BASE_URL: string =
  import.meta.env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/** Shape of the API error envelope: `{ error: { code, message } }`. */
export interface ApiErrorBody {
  error: { code: string; message: string };
}

/** Thrown for any non-2xx API response. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

function buildUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const base = BASE_URL.replace(/\/+$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return `${base}${suffix}`;
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const maybe = value as { error?: unknown };
  if (typeof maybe.error !== 'object' || maybe.error === null) {
    return false;
  }
  const err = maybe.error as { code?: unknown; message?: unknown };
  return typeof err.code === 'string' && typeof err.message === 'string';
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) {
    return undefined;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function request<TResponse>(
  method: string,
  path: string,
  body?: unknown,
): Promise<TResponse> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  const response = await fetch(buildUrl(path), init);
  const parsed = await parseBody(response);

  if (!response.ok) {
    if (isErrorBody(parsed)) {
      throw new ApiError(parsed.error.code, parsed.error.message, response.status);
    }
    throw new ApiError(
      'UNKNOWN',
      `Request failed with status ${response.status}`,
      response.status,
    );
  }

  return parsed as TResponse;
}

export const api = {
  get<TResponse>(path: string): Promise<TResponse> {
    return request<TResponse>('GET', path);
  },
  post<TResponse>(path: string, body?: unknown): Promise<TResponse> {
    return request<TResponse>('POST', path, body);
  },
};

const PUBLIC = '/api/v1/public';

// ---------------------------------------------------------------------------
// Types mirroring the backend public contract (schemas/catalog.py, booking.py).
// ---------------------------------------------------------------------------

export interface Location {
  id: number;
  name: string;
  slug: string;
  address: string | null;
  phone: string | null;
}

export interface Plan {
  id: number;
  location_id: number;
  title: string;
  description: string | null;
  details: string | null;
  plan_type: number;
  /** plan.price_paise (list price before discount). */
  list_price_paise: number;
  /** Actual chargeable price (discount already applied server-side). */
  price_paise: number;
  people_allowed: number;
  max_people_allowed: number;
  extra_guest_paise: number;
  advance_paise: number;
  gallery_urls: string[];
}

export interface Slot {
  id: number;
  plan_id: number;
  description: string;
  show_combos: boolean;
  sort_order: number;
}

export interface Cake {
  id: number;
  description: string;
  price_paise: number;
  image_url: string;
}

export interface SpecialDecor {
  id: number;
  name: string;
  description: string;
  price_paise: number;
  image_url: string;
  sort_order: number;
}

export interface Combo {
  id: number;
  name: string;
  description: string;
  price_paise: number;
  image_url: string;
}

export interface Occasion {
  id: number;
  name: string;
}

/** Request body for POST /public/bookings (IDs + details only — no money). */
export interface BookingCreate {
  location_id: number;
  plan_id: number;
  slot_id: number;
  booking_date: string;
  booking_name: string;
  email: string;
  phone?: string;
  special_person_name?: string;
  name_on_cake?: string;
  message?: string;
  people: number;
  occasion_id?: number;
  cake_id?: number;
  special_decor_ids: number[];
  combo_ids: number[];
}

export interface BookingResult {
  booking_token: string;
  advance_paise: number;
  payment_instructions: string;
}

export interface BookingStatus {
  status: string;
  booking_name: string;
  plan_title: string;
  slot_description: string;
  booking_date: string;
  total_paise: number;
  amount_paid_paise: number;
  amount_due_paise: number;
  is_paid: boolean;
}

export interface ContactCreate {
  name: string;
  phone: string;
  email: string;
  message: string;
}

export interface ContactResult {
  message: string;
}

// ---------------------------------------------------------------------------
// Typed endpoint helpers.
// ---------------------------------------------------------------------------

export const publicApi = {
  listLocations(): Promise<Location[]> {
    return api.get<Location[]>(`${PUBLIC}/locations`);
  },
  listPlans(locationId: number): Promise<Plan[]> {
    return api.get<Plan[]>(`${PUBLIC}/locations/${locationId}/plans`);
  },
  listSlots(planId: number): Promise<Slot[]> {
    return api.get<Slot[]>(`${PUBLIC}/plans/${planId}/slots`);
  },
  availableSlots(
    planId: number,
    locationId: number,
    bookingDate: string,
  ): Promise<Slot[]> {
    return api.post<Slot[]>(`${PUBLIC}/plans/${planId}/available-slots`, {
      location_id: locationId,
      booking_date: bookingDate,
    });
  },
  gallery(planId: number): Promise<string[]> {
    return api.get<string[]>(`${PUBLIC}/plans/${planId}/gallery`);
  },
  listCakes(locationId: number): Promise<Cake[]> {
    return api.get<Cake[]>(`${PUBLIC}/locations/${locationId}/cakes`);
  },
  listSpecialDecor(locationId: number): Promise<SpecialDecor[]> {
    return api.get<SpecialDecor[]>(
      `${PUBLIC}/locations/${locationId}/special-decor`,
    );
  },
  listCombos(locationId: number): Promise<Combo[]> {
    return api.get<Combo[]>(`${PUBLIC}/locations/${locationId}/combos`);
  },
  listOccasions(locationId: number): Promise<Occasion[]> {
    return api.get<Occasion[]>(`${PUBLIC}/locations/${locationId}/occasions`);
  },
  createBooking(body: BookingCreate): Promise<BookingResult> {
    return api.post<BookingResult>(`${PUBLIC}/bookings`, body);
  },
  getBookingStatus(token: string): Promise<BookingStatus> {
    return api.get<BookingStatus>(`${PUBLIC}/bookings/${encodeURIComponent(token)}`);
  },
  submitContact(body: ContactCreate): Promise<ContactResult> {
    return api.post<ContactResult>(`${PUBLIC}/contact`, body);
  },
};
