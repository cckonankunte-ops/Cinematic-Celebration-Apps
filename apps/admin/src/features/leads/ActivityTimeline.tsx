import { formatDateTime } from '@/lib/dates';
import { ACTIVITY_TYPE_LABELS, activityAuthor, activitySummary } from './lead-activity';
import type { ActivityRead } from './types';

/**
 * Lead activity timeline, newest first (lead-crm R7.1, R7.8): type, text,
 * author (or "Customer" / "System") and IST time.
 */
export function ActivityTimeline({ activities }: { activities: ActivityRead[] }): JSX.Element {
  if (activities.length === 0) {
    return <p className="text-sm text-gray-500">No activity yet.</p>;
  }
  return (
    <ol className="space-y-3">
      {activities.map((a) => {
        const summary = activitySummary(a);
        return (
          <li key={a.id} className="border-l-2 border-gray-200 pl-3 text-sm">
            <p className="text-xs text-gray-500">
              <span className="font-medium text-gray-700">{ACTIVITY_TYPE_LABELS[a.type]}</span> ·{' '}
              {activityAuthor(a)} · {formatDateTime(a.created_at)}
            </p>
            {summary && <p className="text-gray-800">{summary}</p>}
            {a.text && <p className="whitespace-pre-line text-gray-800">{a.text}</p>}
          </li>
        );
      })}
    </ol>
  );
}
