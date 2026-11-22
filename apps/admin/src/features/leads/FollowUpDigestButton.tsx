import { useLocation } from '@/features/location/useLocation';
import { useFollowUps } from './lead-queries';
import { digestState } from './lead-whatsapp';

/**
 * "Send today's follow-ups to WhatsApp" (lead-crm R11): opens `wa.me/<branch
 * number>` with overdue and due-today leads pre-filled. Disabled, with the
 * reason shown, when the branch has no usable number or nothing is due.
 */
export function FollowUpDigestButton(): JSX.Element {
  const { locations, selectedLocationId } = useLocation();
  const followUps = useFollowUps(selectedLocationId);
  const branch = locations.find((l) => l.id === selectedLocationId);

  const label = "Send today's follow-ups to WhatsApp";
  const base = 'rounded border px-3 py-2 text-sm font-medium';

  if (followUps.isLoading) {
    return (
      <button type="button" disabled className={`${base} border-gray-200 text-gray-400`}>
        {label}
      </button>
    );
  }

  const state = digestState(branch, followUps.data?.items ?? []);
  if (state.kind !== 'ready') {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled
          aria-describedby="digest-hint"
          className={`${base} cursor-not-allowed border-gray-200 text-gray-400`}
        >
          {label}
        </button>
        <span id="digest-hint" className="text-xs text-gray-500">
          {state.hint}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <a
        href={state.url}
        target="_blank"
        rel="noreferrer"
        className={`${base} border-green-600 text-green-700 hover:bg-green-50`}
      >
        💬 {label}
      </a>
      <span className="text-xs text-gray-500">
        {state.digest.included} lead{state.digest.included === 1 ? '' : 's'}
        {state.digest.omitted > 0 ? ` (+${state.digest.omitted} more in admin)` : ''}
      </span>
    </div>
  );
}
