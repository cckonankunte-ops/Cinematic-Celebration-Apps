/**
 * Catalog add-on image upload (cake / decor / combo) via a presigned PUT.
 *
 * Unlike the plan gallery (which registers a row then uploads), an add-on's
 * image lives on the entity itself, so we must obtain the object_key BEFORE
 * creating/updating the row:
 *   1. POST /admin/catalog-image-uploads -> { object_key, upload_url }
 *   2. PUT the raw bytes to the presigned upload_url (no auth cookie).
 *   3. Include object_key in the entity's create/update payload.
 */

import { api } from '@/api/client';
import type { CatalogImageKind, CatalogImageUploadRead } from './types';

/** PUT raw bytes to the presigned R2 URL. Throws on a non-2xx response. */
async function putToPresignedUrl(uploadUrl: string, file: File): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    credentials: 'omit', // signed S3 URL — never attach our auth cookie
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
  });
  if (!response.ok) {
    throw new Error(`Image upload failed with status ${response.status}`);
  }
}

/**
 * Upload a catalog add-on image and return its object_key. The caller then
 * includes the key in the create/update request for the cake/decor/combo.
 */
export async function uploadCatalogImage(
  kind: CatalogImageKind,
  file: File,
): Promise<string> {
  const registered = await api.post<CatalogImageUploadRead>(
    '/api/v1/admin/catalog-image-uploads',
    { kind, filename: file.name },
  );
  await putToPresignedUrl(registered.upload_url, file);
  return registered.object_key;
}
