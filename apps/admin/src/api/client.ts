/**
 * Thin typed fetch wrapper for the admin panel.
 *
 * - Base URL comes from `VITE_API_BASE_URL` (defaults to http://localhost:8000).
 * - Every request sends cookies (`credentials: 'include'`) for the httpOnly
 *   auth cookie set by the API.
 * - Error responses using the `{ error: { code, message } }` envelope are
 *   parsed into a typed `ApiError`.
 */

const BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

/** Shape of the API error envelope: `{ error: { code, message } }`. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
  };
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
  const init: RequestInit = {
    method,
    headers,
    credentials: 'include',
  };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  const response = await fetch(buildUrl(path), init);
  const parsed = await parseBody(response);

  if (!response.ok) {
    if (isErrorBody(parsed)) {
      throw new ApiError(
        parsed.error.code,
        parsed.error.message,
        response.status,
      );
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
  patch<TResponse>(path: string, body?: unknown): Promise<TResponse> {
    return request<TResponse>('PATCH', path, body);
  },
  del<TResponse>(path: string): Promise<TResponse> {
    return request<TResponse>('DELETE', path);
  },
};
