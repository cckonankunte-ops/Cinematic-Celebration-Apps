/**
 * TanStack Query hooks for the lead CRM (`/api/v1/admin/leads`).
 *
 * Query keys: ['leads', locationId, filters] for the list, ['lead', id] for one
 * lead, ['lead-counts', locationId] for the header badge. Mutations invalidate
 * the list, the counts and the touched lead.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { api } from '@/api/client';
import type { LeadFilterState } from './lead-filter-state';
import type {
  ActivityCreateBody,
  AssignableUser,
  FollowUpDigest,
  LeadCounts,
  LeadCreateBody,
  LeadCreateResult,
  LeadDashboard,
  LeadListPage,
  LeadRead,
  LeadUpdateBody,
} from './types';

const BASE = '/api/v1/admin/leads';
export const SEARCH_MIN_CHARS = 3;
/** Badge refresh: at most once a minute, plus on window focus (R10.2). */
export const COUNTS_REFETCH_MS = 60_000;

/** Query string for GET /admin/leads. Repeated params for multi-value filters. */
export function buildLeadListQuery(locationId: number, f: LeadFilterState): string {
  const params = new URLSearchParams({ location_id: String(locationId) });
  f.statuses.forEach((s) => params.append('status', s));
  f.sources.forEach((s) => params.append('source', s));
  if (f.channel) params.append('channel', f.channel);
  if (f.assignedUserId) params.set('assigned_user_id', f.assignedUserId);
  if (f.createdFrom) params.set('created_from', f.createdFrom);
  if (f.createdTo) params.set('created_to', f.createdTo);
  if (f.followFrom) params.set('follow_from', f.followFrom);
  if (f.followTo) params.set('follow_to', f.followTo);
  const q = f.q.trim();
  // The API needs at least 3 characters; shorter input just isn't sent yet.
  if (q.length >= SEARCH_MIN_CHARS) params.set('q', q);
  params.set('limit', String(f.limit));
  params.set('offset', String(f.offset));
  return params.toString();
}

export function useLeads(
  locationId: number | null,
  filters: LeadFilterState,
): UseQueryResult<LeadListPage> {
  return useQuery({
    queryKey: ['leads', locationId, filters],
    queryFn: () =>
      api.get<LeadListPage>(`${BASE}?${buildLeadListQuery(locationId as number, filters)}`),
    enabled: locationId !== null,
    placeholderData: (previous) => previous,
  });
}

export function useLead(leadId: number | null): UseQueryResult<LeadRead> {
  return useQuery({
    queryKey: ['lead', leadId],
    queryFn: () => api.get<LeadRead>(`${BASE}/${leadId}`),
    enabled: leadId !== null,
  });
}

export function useLeadCounts(locationId: number | null): UseQueryResult<LeadCounts> {
  return useQuery({
    queryKey: ['lead-counts', locationId],
    queryFn: () => api.get<LeadCounts>(`${BASE}/counts?location_id=${locationId}`),
    enabled: locationId !== null,
    refetchInterval: COUNTS_REFETCH_MS,
    refetchOnWindowFocus: true,
    staleTime: COUNTS_REFETCH_MS / 2,
  });
}

export function useAssignableUsers(
  locationId: number | null,
): UseQueryResult<AssignableUser[]> {
  return useQuery({
    queryKey: ['lead-assignable-users', locationId],
    queryFn: () =>
      api.get<AssignableUser[]>(`${BASE}/assignable-users?location_id=${locationId}`),
    enabled: locationId !== null,
    staleTime: 5 * 60_000,
  });
}

function useInvalidateLeads(): (leadId?: number) => void {
  const qc = useQueryClient();
  return (leadId?: number) => {
    void qc.invalidateQueries({ queryKey: ['leads'] });
    void qc.invalidateQueries({ queryKey: ['lead-counts'] });
    void qc.invalidateQueries({ queryKey: ['lead-follow-ups'] });
    if (leadId !== undefined) {
      void qc.invalidateQueries({ queryKey: ['lead', leadId] });
    }
  };
}

export function useCreateLead(): UseMutationResult<LeadCreateResult, unknown, LeadCreateBody> {
  const invalidate = useInvalidateLeads();
  return useMutation({
    mutationFn: (body: LeadCreateBody) => api.post<LeadCreateResult>(BASE, body),
    onSuccess: (result) => invalidate(result.lead.id),
  });
}

/** Lead dashboard (admin only, R13). `locationId` null = all branches. */
export function useLeadDashboard(
  locationId: number | null,
  dateFrom: string,
  dateTo: string,
): UseQueryResult<LeadDashboard> {
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (locationId !== null) params.set('location_id', String(locationId));
  return useQuery({
    queryKey: ['lead-dashboard', locationId, dateFrom, dateTo],
    queryFn: () => api.get<LeadDashboard>(`${BASE}/dashboard?${params.toString()}`),
    enabled: dateFrom !== '' && dateTo !== '' && dateFrom <= dateTo,
    placeholderData: (previous) => previous,
  });
}

/** Overdue + due-today leads for the branch WhatsApp digest (R11.2). */
export function useFollowUps(locationId: number | null): UseQueryResult<FollowUpDigest> {
  return useQuery({
    queryKey: ['lead-follow-ups', locationId],
    queryFn: () => api.get<FollowUpDigest>(`${BASE}/follow-ups?location_id=${locationId}`),
    enabled: locationId !== null,
  });
}

export function useUpdateLead(
  leadId: number,
): UseMutationResult<LeadRead, unknown, LeadUpdateBody> {
  const invalidate = useInvalidateLeads();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: LeadUpdateBody) => api.patch<LeadRead>(`${BASE}/${leadId}`, body),
    onSuccess: (lead) => {
      qc.setQueryData(['lead', leadId], lead);
      invalidate();
    },
  });
}

/** Add a note / call / WhatsApp activity. The lead id is given per call so list rows can use it. */
export function useAddActivity(): UseMutationResult<
  LeadRead,
  unknown,
  { leadId: number; body: ActivityCreateBody }
> {
  const invalidate = useInvalidateLeads();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ leadId, body }) =>
      api.post<LeadRead>(`${BASE}/${leadId}/activities`, body),
    onSuccess: (lead) => {
      qc.setQueryData(['lead', lead.id], lead);
      invalidate();
    },
  });
}

export function useLinkEnquiryCode(
  leadId: number,
): UseMutationResult<LeadCreateResult, unknown, string> {
  const invalidate = useInvalidateLeads();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api.post<LeadCreateResult>(`${BASE}/${leadId}/enquiry-code`, { code }),
    onSuccess: (result) => {
      qc.setQueryData(['lead', leadId], result.lead);
      invalidate();
    },
  });
}
