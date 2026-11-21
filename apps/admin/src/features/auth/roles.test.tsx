import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProtectedRoute } from './ProtectedRoute';
import { LEAD_ROLES, canUseLeads } from './roles';
import type { UserRole } from './types';

let role: UserRole = 'staff';

vi.mock('./useAuth', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'u', role, location_id: role === 'admin' ? null : 1 },
    isLoading: false,
  }),
}));

function renderLeadsRoute(): void {
  render(
    <MemoryRouter initialEntries={['/leads']}>
      <Routes>
        <Route
          path="/leads"
          element={
            <ProtectedRoute requiredRole={LEAD_ROLES}>
              <p>Leads page</p>
            </ProtectedRoute>
          }
        />
        <Route path="/bookings" element={<p>Bookings page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  role = 'staff';
});

describe('canUseLeads', () => {
  it('allows admins and receptionists only', () => {
    expect(canUseLeads('admin')).toBe(true);
    expect(canUseLeads('receptionist')).toBe(true);
    expect(canUseLeads('staff')).toBe(false);
    expect(canUseLeads(null)).toBe(false);
  });
});

describe('ProtectedRoute with a role list', () => {
  it.each(['admin', 'receptionist'] as const)('lets %s open the Leads page', (r) => {
    role = r;
    renderLeadsRoute();
    expect(screen.getByText('Leads page')).toBeInTheDocument();
  });

  it('sends staff to Bookings', () => {
    role = 'staff';
    renderLeadsRoute();
    expect(screen.getByText('Bookings page')).toBeInTheDocument();
    expect(screen.queryByText('Leads page')).toBeNull();
  });
});
