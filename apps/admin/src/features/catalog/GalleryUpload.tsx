/**
 * Inline plan gallery upload. Picks a file and runs the presigned-PUT flow
 * (register row -> PUT bytes to R2) via `useUploadGalleryImage`. Minimal UI:
 * a file input plus upload status.
 */

import { useState } from 'react';

import { useUploadGalleryImage } from './gallery';

export function GalleryUpload({ planId }: { planId: number }): JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const upload = useUploadGalleryImage();

  const onUpload = (): void => {
    if (file === null) {
      return;
    }
    upload.mutate(
      { planId, file, sortOrder: 0 },
      { onSuccess: () => setFile(null) },
    );
  };

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
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
      {upload.isSuccess && <span className="text-xs text-green-700">Uploaded.</span>}
      {upload.isError && <span className="text-xs text-red-600">Upload failed.</span>}
    </div>
  );
}
