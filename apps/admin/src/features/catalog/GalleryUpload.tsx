/**
 * Inline plan gallery manager. Shows the plan's saved gallery images as
 * thumbnails (each deletable), plus a file input to upload a new one via the
 * presigned-PUT flow (register row -> PUT bytes to R2).
 */

import { useState } from 'react';

import {
  useDeleteGalleryImage,
  usePlanGallery,
  useUploadGalleryImage,
} from './gallery';

export function GalleryUpload({ planId }: { planId: number }): JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const gallery = usePlanGallery(planId);
  const upload = useUploadGalleryImage();
  const remove = useDeleteGalleryImage(planId);

  const onUpload = (): void => {
    if (file === null) {
      return;
    }
    upload.mutate(
      { planId, file, sortOrder: gallery.data?.length ?? 0 },
      { onSuccess: () => setFile(null) },
    );
  };

  const images = gallery.data ?? [];

  return (
    <div className="mt-3 space-y-3 border-t border-gray-100 pt-3">
      {/* Saved images */}
      {gallery.isLoading && (
        <p className="text-xs text-gray-500">Loading images…</p>
      )}
      {!gallery.isLoading && images.length === 0 && (
        <p className="text-xs text-gray-500">No images yet.</p>
      )}
      {images.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {images.map((img) => (
            <li key={img.id} className="relative">
              <img
                src={img.image_url}
                alt="Plan gallery"
                className="h-20 w-20 rounded border border-gray-200 object-cover"
              />
              <button
                type="button"
                onClick={() => remove.mutate(img.id)}
                disabled={remove.isPending}
                aria-label="Delete image"
                className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white hover:bg-red-700 disabled:opacity-50"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Upload a new image */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="file"
          accept="image/*"
          aria-label="Gallery image"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-xs"
        />
        <button
          type="button"
          onClick={onUpload}
          disabled={file === null || upload.isPending}
          className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-50"
        >
          {upload.isPending ? 'Uploading…' : 'Upload'}
        </button>
        {upload.isSuccess && (
          <span className="text-xs text-green-700">Uploaded.</span>
        )}
        {upload.isError && (
          <span className="text-xs text-red-600">Upload failed.</span>
        )}
        {remove.isError && (
          <span className="text-xs text-red-600">Delete failed.</span>
        )}
      </div>
    </div>
  );
}
