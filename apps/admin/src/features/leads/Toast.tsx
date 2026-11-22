import { useEffect } from 'react';

/**
 * Minimal local toast for the leads feature (there is no shared toast yet; it
 * moves to `components/` once a second feature needs it). Announced politely to
 * screen readers and auto-dismissed.
 */
export interface ToastProps {
  message: string;
  tone?: 'success' | 'warning';
  onDismiss: () => void;
  /** Auto-dismiss after this many ms (0 keeps it until dismissed). */
  durationMs?: number;
}

export function Toast({
  message,
  tone = 'success',
  onDismiss,
  durationMs = 5000,
}: ToastProps): JSX.Element {
  useEffect(() => {
    if (durationMs <= 0) return undefined;
    const id = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(id);
  }, [durationMs, onDismiss]);

  const colours =
    tone === 'success'
      ? 'border-green-200 bg-green-50 text-green-900'
      : 'border-amber-200 bg-amber-50 text-amber-900';

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-md items-start gap-3 rounded border px-4 py-3 text-sm shadow-lg ${colours}`}
    >
      <p className="flex-1">{message}</p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="rounded px-1 text-lg leading-none opacity-70 hover:opacity-100"
      >
        ×
      </button>
    </div>
  );
}
