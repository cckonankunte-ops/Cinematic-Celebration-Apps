import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LeadNavBadge } from './LeadNavBadge';
import { LeadsPage } from './LeadsPage';
import { QuickAddLeadPage } from './QuickAddLeadPage';
import type { LeadCounts, LeadListPage, LeadRead } from './types';

let page: LeadListPage | undefined;
let counts: LeadCounts | undefined;
const createLead = vi.fn();

vi.mock('./lead-queries', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lead-queries')>();
  return {
    ...actual,
    useLeads: () => ({ data: page, isLoading: false, isError: false }),
    useAssignableUsers: () => ({ data: [], isLoading: false, isError: false }),
    useLeadCounts: () => ({ data: counts }),
    useCreateLead: () => ({ mutateAsync: createLead, isPending: false }),
  };
});

vi.mock('@/features/location/useLocation', () => ({
  useLocation: () => ({
    locations: [{ id: 1, name: 'Hulimavu', slug: 'hulimavu' }],
    selectedLocationId: 1,
    canSwitch: false,
    selectLocation: vi.fn(),
  }),
}));

const iso = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString();

function lead(overrides: Partial<LeadRead>): LeadRead {
  return {
    id: 1,
    location_id: 1,
    phone: '9876543210',
    name: null,
    source: 'whatsapp',
    status: 'new',
    channel: 'manual',
    close_reason: null,
    close_reason_text: null,
    assigned_user_id: null,
    assigned_user_name: null,
    follow_up_at: null,
    last_activity_at: iso(-5),
    first_contacted_at: null,
    is_uncontacted: false,
    minutes_since_created: 5,
    booking_id: null,
    booking_reference: null,
    preferred_date: null,
    plan_id: null,
    plan_title: null,
    start_time: null,
    duration_minutes: null,
    guests: null,
    message: null,
    attribution: {
      utm_source: null,
      utm_medium: null,
      utm_campaign: null,
      landing_path: null,
      referrer_domain: null,
      has_fbclid: false,
      has_gclid: false,
    },
    enquiry_code: null,
    created_at: iso(-5),
    ...overrides,
  };
}

function renderPage(): void {
  render(
    <MemoryRouter>
      <LeadsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.sessionStorage.clear();
  page = undefined;
  counts = undefined;
  createLead.mockReset();
});

describe('LeadsPage', () => {
  it('shows an empty state when there are no leads', () => {
    page = { items: [], total: 0, limit: 50, offset: 0 };
    renderPage();
    expect(screen.getAllByText(/No leads yet/).length).toBeGreaterThan(0);
  });

  it('shows sections in order with the red "Not contacted" label', () => {
    page = {
      items: [
        lead({ id: 1, name: 'Asha', is_uncontacted: true, minutes_since_created: 25 }),
        lead({ id: 2, name: 'Ravi', status: 'follow_up', follow_up_at: iso(-30) }),
        lead({ id: 3, name: 'Meena', status: 'contacted' }),
      ],
      total: 3,
      limit: 50,
      offset: 0,
    };
    renderPage();

    const headings = screen
      .getAllByRole('heading', { level: 2 })
      .map((h) => h.textContent);
    expect(headings).toEqual(['Not contacted (1)', 'Overdue (1)', 'Others (1)']);

    const uncontacted = screen.getByRole('region', { name: 'Not contacted' });
    expect(within(uncontacted).getByText('Not contacted · 25 min')).toBeInTheDocument();
    expect(within(uncontacted).getByText('Asha')).toBeInTheDocument();
    expect(screen.getByText('Showing 1–3 of 3')).toBeInTheDocument();
  });
});

describe('LeadNavBadge', () => {
  it('shows the uncontacted and follow-up pills', () => {
    counts = { uncontacted: 2, overdue: 1, due_today: 3 };
    render(<LeadNavBadge />);
    expect(screen.getByTitle('New leads not contacted yet')).toHaveTextContent('2');
    expect(screen.getByTitle('Follow-ups overdue or due today')).toHaveTextContent('4');
  });

  it('shows nothing when all counts are zero', () => {
    counts = { uncontacted: 0, overdue: 0, due_today: 0 };
    const { container } = render(<LeadNavBadge />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('QuickAddLeadPage', () => {
  it('sends a normalised phone and opens the lead', async () => {
    createLead.mockResolvedValue({
      lead: lead({ id: 42 }),
      created: true,
      warning: null,
      code_used_by_lead_id: null,
    });
    render(
      <MemoryRouter initialEntries={['/leads/new']}>
        <Routes>
          <Route path="/leads/new" element={<QuickAddLeadPage />} />
          <Route path="/leads/:leadId" element={<p>Lead page</p>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText(/^Phone/), { target: { value: '+91 98765 43210' } });
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Asha' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save lead' }));

    await waitFor(() => expect(screen.getByText('Lead page')).toBeInTheDocument());
    expect(createLead).toHaveBeenCalledWith(
      expect.objectContaining({
        phone: '9876543210',
        source: 'whatsapp',
        location_id: 1,
        name: 'Asha',
      }),
    );
  });

  it('shows a field error and does not save an invalid phone', async () => {
    render(
      <MemoryRouter>
        <QuickAddLeadPage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText(/^Phone/), { target: { value: '12345' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save lead' }));
    expect(await screen.findByText('Enter a valid Indian mobile number')).toBeInTheDocument();
    expect(createLead).not.toHaveBeenCalled();
  });
});
