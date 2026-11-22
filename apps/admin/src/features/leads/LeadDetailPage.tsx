/**
 * Lead detail (lead-crm R7, R9, R10, R18.12): contact actions, enquiry details,
 * source / Channel / attribution, linked booking or "Create booking", same-phone
 * leads, enquiry code, editors for name, status (with close reason), assignee
 * and follow-up, then the timeline with "add a note / call / WhatsApp".
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Link,
  useLocation as useRouterLocation,
  useNavigate,
  useParams,
} from 'react-router-dom';

import { ApiError } from '@/api/client';
import { formatDate, formatDateTime, todayIsoInIST } from '@/lib/dates';
import { useLocation } from '@/features/location/useLocation';
import { ActivityTimeline } from './ActivityTimeline';
import { AddActivityForm } from './AddActivityForm';
import { CloseLeadDialog } from './CloseLeadDialog';
import { ContactActions } from './ContactActions';
import { FollowUpPicker } from './FollowUpPicker';
import { LeadStatusBadge } from './LeadStatusBadge';
import { buildLeadPrefill, canConvert } from './lead-convert';
import {
  useAssignableUsers,
  useLead,
  useLinkEnquiryCode,
  useUpdateLead,
} from './lead-queries';
import { uncontactedLabel } from './lead-sections';
import type { LeadToast, LeadToastState } from './lead-toast';
import { Toast } from './Toast';
import {
  CHANNEL_LABELS,
  CLOSE_REASON_LABELS,
  MANUAL_STATUSES,
  SOURCE_LABELS,
  STATUS_LABELS,
  type CloseReason,
  type LeadRead,
  type LeadStatus,
  type LeadUpdateBody,
} from './types';

const card = 'rounded border border-gray-200 bg-white p-4';
const field = 'rounded border border-gray-300 px-2 py-1.5 text-sm';

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

function Detail({ label, children }: { label: string; children: React.ReactNode }): JSX.Element {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="text-gray-900">{children}</dd>
    </div>
  );
}

function windowLabel(lead: LeadRead): string | null {
  if (!lead.start_time) return null;
  const start = lead.start_time.slice(0, 5);
  return lead.duration_minutes ? `${start} · ${lead.duration_minutes} min` : start;
}

function Editors({ lead }: { lead: LeadRead }): JSX.Element {
  const update = useUpdateLead(lead.id);
  const users = useAssignableUsers(lead.location_id);
  const [name, setName] = useState(lead.name ?? '');
  const [closing, setClosing] = useState<'lost' | 'not_interested' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const followsBooking = lead.status === 'booked' || lead.status === 'won';
  const closed = ['won', 'lost', 'not_interested'].includes(lead.status);

  useEffect(() => setName(lead.name ?? ''), [lead.name]);

  const save = (body: LeadUpdateBody, onDone?: () => void): void => {
    setError(null);
    update.mutate(body, {
      onSuccess: () => onDone?.(),
      onError: (err) => setError(errorText(err, 'Could not save the change.')),
    });
  };

  const onStatus = (next: LeadStatus): void => {
    if (next === lead.status) return;
    if (next === 'lost' || next === 'not_interested') {
      setClosing(next);
      return;
    }
    save({ status: next });
  };

  return (
    <section className={`${card} space-y-4`} aria-label="Edit lead">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block space-y-1 text-sm">
          <span className="text-xs text-gray-500">Name</span>
          <div className="flex gap-2">
            <input
              className={`${field} min-w-0 flex-1`}
              value={name}
              maxLength={120}
              onChange={(e) => setName(e.target.value)}
            />
            {name.trim() !== (lead.name ?? '') && (
              <button
                type="button"
                onClick={() => save({ name: name.trim() || null })}
                className="rounded bg-gray-900 px-3 text-xs font-medium text-white"
              >
                Save
              </button>
            )}
          </div>
        </label>

        <label className="block space-y-1 text-sm">
          <span className="text-xs text-gray-500">Status</span>
          {followsBooking ? (
            <p className="py-1.5 text-gray-700">
              {STATUS_LABELS[lead.status]} — follows the linked booking.
            </p>
          ) : (
            <select
              className={`${field} w-full`}
              value={lead.status}
              disabled={update.isPending}
              onChange={(e) => onStatus(e.target.value as LeadStatus)}
            >
              {MANUAL_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          )}
          {lead.close_reason && (
            <span className="block text-xs text-gray-600">
              Reason: {CLOSE_REASON_LABELS[lead.close_reason as CloseReason]}
              {lead.close_reason_text ? ` — ${lead.close_reason_text}` : ''}
            </span>
          )}
        </label>

        <label className="block space-y-1 text-sm">
          <span className="text-xs text-gray-500">Assigned to</span>
          <select
            className={`${field} w-full`}
            value={lead.assigned_user_id ?? ''}
            disabled={update.isPending}
            onChange={(e) =>
              save({ assigned_user_id: e.target.value ? Number(e.target.value) : null })
            }
          >
            <option value="">Nobody</option>
            {(users.data ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!closed && (
        <div className="space-y-1 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">
              Follow-up
              {lead.follow_up_at ? `: ${formatDateTime(lead.follow_up_at)}` : ''}
            </span>
            {lead.follow_up_at && (
              <button
                type="button"
                onClick={() => save({ follow_up_at: null })}
                className="text-xs text-gray-600 hover:underline"
              >
                Clear
              </button>
            )}
          </div>
          <FollowUpPicker
            value=""
            allowNone={false}
            onChange={(iso) => {
              if (iso) save({ follow_up_at: iso });
            }}
          />
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {closing && (
        <CloseLeadDialog
          status={closing}
          isSaving={update.isPending}
          error={error}
          onCancel={() => setClosing(null)}
          onConfirm={(reason, text) =>
            save(
              { status: closing, close_reason: reason, close_reason_text: text },
              () => setClosing(null),
            )
          }
        />
      )}
    </section>
  );
}

function EnquiryCodeLink({
  lead,
  onToast,
}: {
  lead: LeadRead;
  onToast: (t: LeadToast) => void;
}): JSX.Element {
  const link = useLinkEnquiryCode(lead.id);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (lead.enquiry_code) {
    return <span className="font-mono">{lead.enquiry_code}</span>;
  }
  return (
    <form
      className="flex flex-wrap gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const value = code.trim().toUpperCase();
        if (!value) return;
        setError(null);
        link.mutate(value, {
          onSuccess: (result) => {
            setCode('');
            if (result.warning) {
              onToast({ message: result.warning, tone: 'warning' });
            } else if (result.code_used_by_lead_id) {
              onToast({
                message: `Linked enquiry code ${value}. It is also on lead #${result.code_used_by_lead_id}.`,
                tone: 'warning',
              });
            } else {
              onToast({ message: `Linked enquiry code ${value}.`, tone: 'success' });
            }
          },
          onError: (err) => setError(errorText(err, 'Could not link the code.')),
        });
      }}
    >
      <input
        aria-label="Enquiry code"
        placeholder="e.g. W4K7XQ"
        maxLength={12}
        autoCapitalize="characters"
        className={`${field} w-28 font-mono uppercase`}
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />
      <button
        type="submit"
        disabled={link.isPending || !code.trim()}
        className="rounded border border-gray-300 px-2 text-xs font-medium disabled:opacity-40"
      >
        Link
      </button>
      {error && <span className="w-full text-xs text-red-600">{error}</span>}
    </form>
  );
}

export function LeadDetailPage(): JSX.Element {
  const { leadId } = useParams<{ leadId: string }>();
  const id = Number(leadId);
  const lead = useLead(Number.isFinite(id) ? id : null);
  const { locations, canSwitch, selectLocation } = useLocation();
  const routerLocation = useRouterLocation();
  const navigate = useNavigate();
  const [toast, setToast] = useState<LeadToast | undefined>(
    (routerLocation.state as LeadToastState | null)?.toast,
  );

  const dismiss = useCallback(() => {
    setToast(undefined);
    // Drop the toast from history so a refresh or Back doesn't show it again.
    if (routerLocation.state) navigate('.', { replace: true, state: null });
  }, [navigate, routerLocation.state]);

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
  const branch = locations.find((loc) => loc.id === l.location_id);
  const branchName = branch?.name ?? 'our branch';
  const a = l.attribution;
  const hasAttribution =
    a.utm_source || a.utm_medium || a.utm_campaign || a.landing_path || a.referrer_domain ||
    a.has_fbclid || a.has_gclid;

  const createBooking = (): void => {
    // The booking form books the selected branch: switch to the lead's branch
    // first (admins; staff are already on it), then open the pre-filled form.
    if (canSwitch) selectLocation(l.location_id);
    navigate('/bookings/new', { state: buildLeadPrefill(l, todayIsoInIST()) });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link to="/leads" className="text-sm text-gray-600 hover:underline">
        ← Leads
      </Link>

      <section className={card} aria-label="Contact">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{l.name || l.phone}</h1>
            <p className="text-sm text-gray-600">
              +91 {l.phone} · {branchName}
            </p>
          </div>
          <LeadStatusBadge status={l.status} />
        </div>
        {l.is_uncontacted && (
          <p className="mt-2 inline-block rounded bg-red-600 px-1.5 py-0.5 text-xs font-semibold text-white">
            {uncontactedLabel(l.minutes_since_created)}
          </p>
        )}
        <div className="mt-3">
          <ContactActions lead={l} branchName={branchName} />
        </div>
        <div className="mt-3 border-t border-gray-100 pt-3 text-sm">
          {l.booking_id && l.booking_reference ? (
            <p>
              Booking{' '}
              <Link
                to={`/bookings/${l.booking_id}/edit`}
                className="font-mono font-medium text-teal-700 underline"
              >
                {l.booking_reference}
              </Link>
            </p>
          ) : canConvert(l) ? (
            <button
              type="button"
              onClick={createBooking}
              className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
            >
              Create booking
            </button>
          ) : null}
        </div>
      </section>

      <Editors lead={l} />

      <section className={card} aria-label="Enquiry">
        <h2 className="mb-3 text-base font-semibold text-gray-900">Enquiry</h2>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Detail label="Source">{SOURCE_LABELS[l.source]}</Detail>
          <Detail label="Channel">{CHANNEL_LABELS[l.channel]}</Detail>
          {l.preferred_date && <Detail label="Preferred date">{formatDate(l.preferred_date)}</Detail>}
          {windowLabel(l) && <Detail label="Time">{windowLabel(l)}</Detail>}
          {l.plan_title && <Detail label="Plan">{l.plan_title}</Detail>}
          {l.guests && <Detail label="Guests">{l.guests}</Detail>}
          <Detail label="Created">{formatDateTime(l.created_at)}</Detail>
          {l.first_contacted_at && (
            <Detail label="First contacted">{formatDateTime(l.first_contacted_at)}</Detail>
          )}
          <Detail label="Enquiry code">
            <EnquiryCodeLink lead={l} onToast={setToast} />
          </Detail>
        </dl>
        {l.message && (
          <p className="mt-3 whitespace-pre-line rounded bg-gray-50 p-2 text-sm text-gray-800">
            {l.message}
          </p>
        )}
        {hasAttribution && (
          <div className="mt-3 border-t border-gray-100 pt-3">
            <h3 className="mb-2 text-xs font-semibold uppercase text-gray-500">Came from</h3>
            <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
              {a.utm_source && <Detail label="utm_source">{a.utm_source}</Detail>}
              {a.utm_medium && <Detail label="utm_medium">{a.utm_medium}</Detail>}
              {a.utm_campaign && <Detail label="utm_campaign">{a.utm_campaign}</Detail>}
              {a.landing_path && <Detail label="Landing page">{a.landing_path}</Detail>}
              {a.referrer_domain && <Detail label="Referrer">{a.referrer_domain}</Detail>}
              {(a.has_fbclid || a.has_gclid) && (
                <Detail label="Ad click">
                  {[a.has_fbclid && 'Meta (fbclid)', a.has_gclid && 'Google (gclid)']
                    .filter(Boolean)
                    .join(', ')}
                </Detail>
              )}
            </dl>
          </div>
        )}
      </section>

      {(l.same_phone_leads ?? []).length > 0 && (
        <section className={card} aria-label="Other leads with this number">
          <h2 className="mb-2 text-base font-semibold text-gray-900">Same number</h2>
          <ul className="space-y-1 text-sm">
            {(l.same_phone_leads ?? []).map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-2">
                <Link to={`/leads/${o.id}`} className="text-blue-700 underline">
                  Lead #{o.id}
                </Link>
                <span className="text-gray-600">{o.location_name}</span>
                <LeadStatusBadge status={o.status} />
                <span className="text-xs text-gray-500">
                  {SOURCE_LABELS[o.source]} · {formatDate(o.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={`${card} space-y-4`} aria-label="Timeline">
        <h2 className="text-base font-semibold text-gray-900">Timeline</h2>
        <AddActivityForm leadId={l.id} />
        <ActivityTimeline activities={l.activities ?? []} />
      </section>

      {toast && <Toast message={toast.message} tone={toast.tone} onDismiss={dismiss} />}
    </div>
  );
}
