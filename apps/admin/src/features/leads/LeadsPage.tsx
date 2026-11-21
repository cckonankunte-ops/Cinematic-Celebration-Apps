/**
 * Leads page (lead-crm R5): who to call first, then everyone else.
 *
 * Sections follow the server's order: Not contacted (red "Not contacted · N
 * min"), Overdue, Due today, New, Others. Cards below 768 px (staff use phones
 * on the floor), a table from 768 px. Filters are kept for the browser tab.
 */

import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useDebounce } from '@/hooks/useDebounce';
import { formatDateTime } from '@/lib/dates';
import { useLocation } from '@/features/location/useLocation';
import { LeadStatusBadge } from './LeadStatusBadge';
import {
  DEFAULT_LEAD_FILTERS,
  loadLeadFilters,
  saveLeadFilters,
  type LeadFilterState,
} from './lead-filter-state';
import { SEARCH_MIN_CHARS, useAssignableUsers, useLeads } from './lead-queries';
import { SECTION_LABELS, groupBySection, uncontactedLabel, type LeadSection } from './lead-sections';
import {
  CHANNEL_LABELS,
  SOURCE_LABELS,
  STATUS_LABELS,
  type LeadChannel,
  type LeadRead,
  type LeadSource,
  type LeadStatus,
} from './types';

const SECTION_STYLES: Record<LeadSection, string> = {
  uncontacted: 'text-red-700',
  overdue: 'text-amber-700',
  due_today: 'text-amber-700',
  new: 'text-blue-700',
  other: 'text-gray-600',
};

const field = 'rounded border border-gray-300 px-2 py-1 text-sm';
const PAGE_SIZES = [50, 100, 200];

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function displayName(lead: LeadRead): string {
  return lead.name?.trim() || lead.phone;
}

function UncontactedLabel({ lead }: { lead: LeadRead }): JSX.Element | null {
  if (!lead.is_uncontacted) return null;
  return (
    <span className="inline-block rounded bg-red-600 px-1.5 py-0.5 text-xs font-semibold text-white">
      {uncontactedLabel(lead.minutes_since_created)}
    </span>
  );
}

function FollowUpCell({ lead }: { lead: LeadRead }): JSX.Element {
  return lead.follow_up_at ? (
    <span>{formatDateTime(lead.follow_up_at)}</span>
  ) : (
    <span className="text-gray-400">—</span>
  );
}

function LeadCard({ lead }: { lead: LeadRead }): JSX.Element {
  return (
    <Link
      to={`/leads/${lead.id}`}
      className="block rounded border border-gray-200 bg-white p-3 shadow-sm active:bg-gray-50"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900">{displayName(lead)}</p>
          {lead.name && <p className="text-xs text-gray-500">{lead.phone}</p>}
        </div>
        <LeadStatusBadge status={lead.status} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600">
        <UncontactedLabel lead={lead} />
        <span>{SOURCE_LABELS[lead.source]}</span>
        {lead.follow_up_at && <span>Follow up {formatDateTime(lead.follow_up_at)}</span>}
        {lead.booking_reference && (
          <span className="font-medium text-teal-700">{lead.booking_reference}</span>
        )}
        <span className="text-gray-400">Last activity {formatDateTime(lead.last_activity_at)}</span>
      </div>
    </Link>
  );
}

function LeadTableRows({ leads }: { leads: LeadRead[] }): JSX.Element {
  const navigate = useNavigate();
  return (
    <>
      {leads.map((lead) => (
        <tr
          key={lead.id}
          className="cursor-pointer border-b border-gray-100 align-top hover:bg-gray-50"
          onClick={() => navigate(`/leads/${lead.id}`)}
        >
          <td className="py-2 pr-4">
            <Link to={`/leads/${lead.id}`} className="font-medium text-gray-900 hover:underline">
              {displayName(lead)}
            </Link>
            {lead.name && <div className="text-xs text-gray-500">{lead.phone}</div>}
            <div className="mt-1">
              <UncontactedLabel lead={lead} />
            </div>
          </td>
          <td className="py-2 pr-4">{SOURCE_LABELS[lead.source]}</td>
          <td className="py-2 pr-4">
            <LeadStatusBadge status={lead.status} />
          </td>
          <td className="py-2 pr-4">
            <FollowUpCell lead={lead} />
          </td>
          <td className="py-2 pr-4">{formatDateTime(lead.last_activity_at)}</td>
          <td className="py-2 pr-4">
            {lead.booking_reference ?? <span className="text-gray-400">—</span>}
          </td>
          <td className="py-2 pr-4 text-gray-600">{lead.assigned_user_name ?? '—'}</td>
        </tr>
      ))}
    </>
  );
}

export function LeadsPage(): JSX.Element {
  const { selectedLocationId } = useLocation();
  const [filters, setFilters] = useState<LeadFilterState>(() => loadLeadFilters());
  const [showFilters, setShowFilters] = useState(false);
  const debouncedQ = useDebounce(filters.q, 350);
  const queryFilters = useMemo(() => ({ ...filters, q: debouncedQ }), [filters, debouncedQ]);

  useEffect(() => saveLeadFilters(filters), [filters]);

  const leads = useLeads(selectedLocationId, queryFilters);
  const users = useAssignableUsers(selectedLocationId);

  // Any filter change goes back to the first page.
  const update = (patch: Partial<LeadFilterState>): void =>
    setFilters((f) => ({ ...f, ...patch, offset: 'offset' in patch ? (patch.offset ?? 0) : 0 }));

  const activeCount = [
    filters.statuses.length > 0,
    filters.sources.length > 0,
    filters.channel !== '',
    filters.assignedUserId !== '',
    filters.createdFrom !== '' || filters.createdTo !== '',
    filters.followFrom !== '' || filters.followTo !== '',
  ].filter(Boolean).length;

  const shortQuery = filters.q.trim().length > 0 && filters.q.trim().length < SEARCH_MIN_CHARS;
  const data = leads.data;
  const now = new Date();
  const groups = data ? groupBySection(data.items, now) : [];
  const from = data && data.total > 0 ? data.offset + 1 : 0;
  const to = data ? data.offset + data.items.length : 0;

  if (selectedLocationId === null) {
    return <p className="text-sm text-gray-500">Select a location first.</p>;
  }

  const chip = (pressed: boolean) =>
    `rounded-full border px-2.5 py-1 text-xs font-medium ${
      pressed ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-700'
    }`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Leads</h1>
        <Link
          to="/leads/new"
          className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          + Add lead
        </Link>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-0 flex-1 text-sm sm:max-w-xs">
          <span className="sr-only">Search leads</span>
          <input
            type="search"
            placeholder="Search name or phone"
            className={`${field} w-full`}
            value={filters.q}
            onChange={(e) => update({ q: e.target.value })}
          />
        </label>
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          aria-expanded={showFilters}
          aria-controls="lead-filters"
          className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-100"
        >
          Filters{activeCount > 0 ? ` (${activeCount})` : ''}
        </button>
        {(activeCount > 0 || filters.q) && (
          <button
            type="button"
            onClick={() => setFilters(DEFAULT_LEAD_FILTERS)}
            className="rounded px-2 py-1 text-sm text-gray-600 hover:bg-gray-100"
          >
            ↺ Reset
          </button>
        )}
      </div>
      {shortQuery && (
        <p className="text-xs text-gray-500">Type at least {SEARCH_MIN_CHARS} characters to search.</p>
      )}

      {showFilters && (
        <div id="lead-filters" className="space-y-3 rounded border border-gray-200 bg-white p-3">
          <fieldset>
            <legend className="mb-1 text-xs font-medium text-gray-600">Status</legend>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(STATUS_LABELS) as LeadStatus[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={filters.statuses.includes(s)}
                  className={chip(filters.statuses.includes(s))}
                  onClick={() => update({ statuses: toggle(filters.statuses, s) })}
                >
                  {STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="mb-1 text-xs font-medium text-gray-600">Source</legend>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(SOURCE_LABELS) as LeadSource[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={filters.sources.includes(s)}
                  className={chip(filters.sources.includes(s))}
                  onClick={() => update({ sources: toggle(filters.sources, s) })}
                >
                  {SOURCE_LABELS[s]}
                </button>
              ))}
            </div>
          </fieldset>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="mr-2 text-gray-600">Channel</span>
              <select
                className={field}
                value={filters.channel}
                onChange={(e) => update({ channel: e.target.value as '' | LeadChannel })}
              >
                <option value="">Any</option>
                {(Object.keys(CHANNEL_LABELS) as LeadChannel[]).map((c) => (
                  <option key={c} value={c}>
                    {CHANNEL_LABELS[c]}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mr-2 text-gray-600">Assigned to</span>
              <select
                className={field}
                value={filters.assignedUserId}
                onChange={(e) => update({ assignedUserId: e.target.value })}
              >
                <option value="">Anyone</option>
                {(users.data ?? []).map((u) => (
                  <option key={u.id} value={String(u.id)}>
                    {u.username}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mr-2 text-gray-600">Created</span>
              <input
                type="date"
                aria-label="Created from"
                className={field}
                value={filters.createdFrom}
                onChange={(e) => update({ createdFrom: e.target.value })}
              />
              <span className="mx-1 text-gray-500">to</span>
              <input
                type="date"
                aria-label="Created to"
                className={field}
                value={filters.createdTo}
                onChange={(e) => update({ createdTo: e.target.value })}
              />
            </label>
            <label className="text-sm">
              <span className="mr-2 text-gray-600">Follow-up</span>
              <input
                type="date"
                aria-label="Follow-up from"
                className={field}
                value={filters.followFrom}
                onChange={(e) => update({ followFrom: e.target.value })}
              />
              <span className="mx-1 text-gray-500">to</span>
              <input
                type="date"
                aria-label="Follow-up to"
                className={field}
                value={filters.followTo}
                onChange={(e) => update({ followTo: e.target.value })}
              />
            </label>
          </div>
        </div>
      )}

      {leads.isLoading && <p className="text-sm text-gray-500">Loading leads…</p>}
      {leads.isError && <p className="text-sm text-red-600">Failed to load leads.</p>}
      {data && data.items.length === 0 && (
        <p className="rounded border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-500">
          {activeCount > 0 || filters.q
            ? 'No leads match these filters.'
            : 'No leads yet. New website enquiries and leads you add will appear here.'}
        </p>
      )}

      {data && data.items.length > 0 && (
        <>
          {/* Phones: cards grouped by section. */}
          <div className="space-y-4 md:hidden">
            {groups.map((g, i) => (
              <section key={`${g.section}-${i}`} aria-label={SECTION_LABELS[g.section]}>
                <h2 className={`mb-2 text-sm font-semibold ${SECTION_STYLES[g.section]}`}>
                  {SECTION_LABELS[g.section]} ({g.leads.length})
                </h2>
                <div className="space-y-2">
                  {g.leads.map((lead) => (
                    <LeadCard key={lead.id} lead={lead} />
                  ))}
                </div>
              </section>
            ))}
          </div>

          {/* Tablet and up: one table, a heading row per section. */}
          <div className="hidden overflow-x-auto rounded border border-gray-200 bg-white md:block">
            <table className="w-full border-collapse whitespace-nowrap text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
                  <th className="py-2 pl-0 pr-4">Lead</th>
                  <th className="py-2 pr-4">Source</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Follow-up</th>
                  <th className="py-2 pr-4">Last activity</th>
                  <th className="py-2 pr-4">Booking</th>
                  <th className="py-2 pr-4">Assigned</th>
                </tr>
              </thead>
              {groups.map((g, i) => (
                <tbody key={`${g.section}-${i}`}>
                  <tr>
                    <th
                      colSpan={7}
                      scope="colgroup"
                      className={`bg-gray-50 py-1.5 text-left text-xs font-semibold ${SECTION_STYLES[g.section]}`}
                    >
                      {SECTION_LABELS[g.section]} ({g.leads.length})
                    </th>
                  </tr>
                  <LeadTableRows leads={g.leads} />
                </tbody>
              ))}
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-gray-600">
            <span>
              Showing {from}–{to} of {data.total}
            </span>
            <div className="flex items-center gap-2">
              <select
                aria-label="Leads per page"
                className={field}
                value={filters.limit}
                onChange={(e) => update({ limit: Number(e.target.value) })}
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n} / page
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
                disabled={filters.offset === 0}
                onClick={() => update({ offset: Math.max(0, filters.offset - filters.limit) })}
              >
                Prev
              </button>
              <button
                type="button"
                className="rounded border border-gray-300 px-3 py-1 disabled:opacity-40"
                disabled={to >= data.total}
                onClick={() => update({ offset: filters.offset + filters.limit })}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
