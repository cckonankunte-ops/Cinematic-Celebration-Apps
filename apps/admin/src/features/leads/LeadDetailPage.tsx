/**
 * Lead detail (lead-crm R7). This first version shows the lead and its
 * timeline; editing, quick contact actions and convert-to-booking are added in
 * the next step (tasks group 11).
 */

import { useCallback, useState } from 'react';
import { Link, useLocation as useRouterLocation, useNavigate, useParams } from 'react-router-dom';

import { formatDate, formatDateTime } from '@/lib/dates';
import { LeadStatusBadge } from './LeadStatusBadge';
import { useLead } from './lead-queries';
import { uncontactedLabel } from './lead-sections';
import type { LeadToastState } from './lead-toast';
import { Toast } from './Toast';
import { CHANNEL_LABELS, SOURCE_LABELS, type ActivityRead } from './types';

function authorLabel(activity: ActivityRead): string {
  if (activity.author_name) return activity.author_name;
  return activity.type === 'system' || activity.type === 'status_change' ? 'System' : 'Customer';
}

export function LeadDetailPage(): JSX.Element {
  const { leadId } = useParams<{ leadId: string }>();
  const id = Number(leadId);
  const lead = useLead(Number.isFinite(id) ? id : null);
  const routerLocation = useRouterLocation();
  const navigate = useNavigate();
  const [toast, setToast] = useState((routerLocation.state as LeadToastState | null)?.toast);

  const dismiss = useCallback(() => {
    setToast(undefined);
    // Drop the toast from history so a refresh or Back doesn't show it again.
    navigate('.', { replace: true, state: null });
  }, [navigate]);

  if (lead.isLoading) return <p className="text-sm text-gray-500">Loading lead…</p>;
  if (lead.isError || !lead.data) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-red-600">Could not load this lead.</p>
        <Link to="/leads" className="text-sm text-gray-700 hover:underline">
          ← Back to leads
        </Link>
      </div>
    );
  }
  const l = lead.data;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link to="/leads" className="text-sm text-gray-600 hover:underline">
        ← Leads
      </Link>

      <div className="rounded border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{l.name || l.phone}</h1>
            {l.name && <p className="text-sm text-gray-600">{l.phone}</p>}
          </div>
          <LeadStatusBadge status={l.status} />
        </div>
        {l.is_uncontacted && (
          <p className="mt-2 inline-block rounded bg-red-600 px-1.5 py-0.5 text-xs font-semibold text-white">
            {uncontactedLabel(l.minutes_since_created)}
          </p>
        )}
        <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-gray-500">Source</dt>
            <dd>{SOURCE_LABELS[l.source]}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Channel</dt>
            <dd>{CHANNEL_LABELS[l.channel]}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Follow-up</dt>
            <dd>{l.follow_up_at ? formatDateTime(l.follow_up_at) : '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">Assigned to</dt>
            <dd>{l.assigned_user_name ?? '—'}</dd>
          </div>
          {l.preferred_date && (
            <div>
              <dt className="text-xs text-gray-500">Preferred date</dt>
              <dd>{formatDate(l.preferred_date)}</dd>
            </div>
          )}
          {l.plan_title && (
            <div>
              <dt className="text-xs text-gray-500">Plan</dt>
              <dd>{l.plan_title}</dd>
            </div>
          )}
          {l.guests && (
            <div>
              <dt className="text-xs text-gray-500">Guests</dt>
              <dd>{l.guests}</dd>
            </div>
          )}
          {l.booking_reference && (
            <div>
              <dt className="text-xs text-gray-500">Booking</dt>
              <dd className="font-medium text-teal-700">{l.booking_reference}</dd>
            </div>
          )}
          {l.enquiry_code && (
            <div>
              <dt className="text-xs text-gray-500">Enquiry code</dt>
              <dd className="font-mono">{l.enquiry_code}</dd>
            </div>
          )}
          <div>
            <dt className="text-xs text-gray-500">Created</dt>
            <dd>{formatDateTime(l.created_at)}</dd>
          </div>
        </dl>
      </div>

      <section className="rounded border border-gray-200 bg-white p-4">
        <h2 className="text-base font-semibold text-gray-900">Timeline</h2>
        {(l.activities ?? []).length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">No activity yet.</p>
        ) : (
          <ol className="mt-3 space-y-3">
            {(l.activities ?? []).map((a) => (
              <li key={a.id} className="border-l-2 border-gray-200 pl-3 text-sm">
                <p className="text-xs text-gray-500">
                  {formatDateTime(a.created_at)} · {authorLabel(a)}
                </p>
                {a.text && <p className="whitespace-pre-line text-gray-800">{a.text}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>

      {toast && <Toast message={toast.message} tone={toast.tone} onDismiss={dismiss} />}
    </div>
  );
}
