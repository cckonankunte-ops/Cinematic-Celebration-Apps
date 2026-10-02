/**
 * Browser-download helpers for server-generated `.xlsx` exports.
 *
 * The admin API streams spreadsheets as attachments from authenticated
 * endpoints. The auth cookie is httpOnly + SameSite=Lax, so a plain top-level
 * navigation (same-site) sends it automatically — we build an absolute URL
 * against the same base as `api/client` and open it, letting the browser's
 * download manager handle the attachment response.
 */

const BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

/** Query params for an export link; values are stringified. */
export type ExportParams = Record<string, string | number>;

/**
 * Build an absolute export URL from an API path and query params, using the
 * same base URL as the fetch client so downloads hit the real API host.
 */
export function exportUrl(path: string, params: ExportParams): string {
  const base = BASE_URL.replace(/\/+$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    search.set(key, String(value));
  }
  const query = search.toString();
  return query.length > 0 ? `${base}${suffix}?${query}` : `${base}${suffix}`;
}

/**
 * Trigger a browser download for the given absolute URL. Uses a transient
 * anchor click so the attachment response is handled by the download manager
 * without replacing the current SPA view.
 */
export function triggerDownload(url: string): void {
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.rel = 'noopener';
  // Same-site navigation keeps the httpOnly auth cookie attached.
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
}
