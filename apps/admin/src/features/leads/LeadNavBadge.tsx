import { useLocation } from '@/features/location/useLocation';
import { useLeadCounts } from './lead-queries';

/**
 * Two pills next to the Leads nav link (lead-crm R5.9, R10.1): red for
 * uncontacted new leads, amber for overdue + due-today follow-ups. Nothing is
 * shown for a zero count. Refreshed at most once a minute and on focus.
 */
export function LeadNavBadge(): JSX.Element | null {
  const { selectedLocationId } = useLocation();
  const { data } = useLeadCounts(selectedLocationId);
  if (!data) return null;
  const followUps = data.overdue + data.due_today;
  if (data.uncontacted === 0 && followUps === 0) return null;

  return (
    <span className="ml-1.5 inline-flex gap-1 align-middle">
      {data.uncontacted > 0 && (
        <span
          className="rounded-full bg-red-600 px-1.5 text-[11px] font-semibold leading-5 text-white"
          title="New leads not contacted yet"
        >
          {data.uncontacted}
          <span className="sr-only"> not contacted</span>
        </span>
      )}
      {followUps > 0 && (
        <span
          className="rounded-full bg-amber-500 px-1.5 text-[11px] font-semibold leading-5 text-white"
          title="Follow-ups overdue or due today"
        >
          {followUps}
          <span className="sr-only"> follow-ups due</span>
        </span>
      )}
    </span>
  );
}
