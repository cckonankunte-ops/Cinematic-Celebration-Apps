/**
 * Plan gallery upload via the presigned-PUT flow.
 *
 * Step 1: `POST /admin/plans/{id}/gallery` registers the gallery row and
 * returns `{ object_key, upload_url }` (through our authenticated API client).
 * Step 2: `PUT` the raw file bytes directly to the presigned `upload_url` on
 * R2. The PUT must NOT carry our auth cookie (it is a signed S3 URL on a
 * different origin), so it uses a bare `fetch` with `credentials: 'omit'`.
 */

import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from '@tanstack/react-query';

import { api } from '@/api/client';
import type { GalleryImageRead } from './types';

/** Inputs for a single gallery upload. */
export interface GalleryUploadArgs {
  planId: number;
  file: File;
  sortOrder: number;
}

/** PUT raw bytes to the presigned R2 URL. Throws on a non-2xx response. */
async function putToPresignedUrl(uploadUrl: string, file: File): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    credentials: 'omit', // signed S3 URL — never attach our auth cookie
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
  });
  if (!response.ok) {
    throw new Error(`Gallery upload failed with status ${response.status}`);
  }
}

/**
 * Register a gallery image then upload the file to the returned presigned URL.
 * Invalidates the plan's gallery list on success.
 */
export function useUploadGalleryImage(): UseMutationResult<
  GalleryImageRead,
  unknown,
  GalleryUploadArgs
> {
  const qc = useQueryClient();
  return useMutation<GalleryImageRead, unknown, GalleryUploadArgs>({
    mutationFn: async ({ planId, file, sortOrder }) => {
      const registered = await api.post<GalleryImageRead>(
        `/api/v1/admin/plans/${planId}/gallery`,
        { filename: file.name, sort_order: sortOrder },
      );
      if (registered.upload_url !== null) {
        await putToPresignedUrl(registered.upload_url, file);
      }
      return registered;
    },
    onSuccess: (_data, { planId }) => {
      void qc.invalidateQueries({ queryKey: ['catalog', 'gallery', planId] });
    },
  });
}
