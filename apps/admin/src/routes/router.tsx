import { createBrowserRouter, Navigate } from 'react-router-dom';

import { AppLayout } from '@/features/auth/AppLayout';
import { LoginPage } from '@/features/auth/LoginPage';
import { ProtectedRoute } from '@/features/auth/ProtectedRoute';
import { LEAD_ROLES } from '@/features/auth/roles';
import { LocationGate } from '@/features/location/LocationGate';
import { BookingListPage } from '@/features/bookings/BookingListPage';
import { BookingFormPage } from '@/features/bookings/BookingFormPage';
import { TimesheetPage } from '@/features/timesheet/TimesheetPage';
import { CakesheetPage } from '@/features/cakesheet/CakesheetPage';
import { AnalyticsPage } from '@/features/analytics/AnalyticsPage';
import { CatalogPage } from '@/features/catalog/CatalogPage';
import { CouponsPage } from '@/features/coupons/CouponsPage';
import { UsersPage } from '@/features/users/UsersPage';
import { LeadsPage } from '@/features/leads/LeadsPage';
import { QuickAddLeadPage } from '@/features/leads/QuickAddLeadPage';
import { LeadDetailPage } from '@/features/leads/LeadDetailPage';
import { LeadDashboardPage } from '@/features/leads/LeadDashboardPage';

/**
 * Route tree. `/login` is public; everything else is wrapped in
 * `ProtectedRoute` + the authenticated `AppLayout` shell (which supplies nav,
 * logout, and the location switcher via `LocationGate`). Analytics is further
 * gated to the `admin` role.
 */

function ProtectedShell(): JSX.Element {
  return (
    <ProtectedRoute>
      <LocationGate>
        <AppLayout />
      </LocationGate>
    </ProtectedRoute>
  );
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <ProtectedShell />,
    children: [
      { index: true, element: <Navigate to="/bookings" replace /> },
      { path: 'bookings', element: <BookingListPage /> },
      { path: 'bookings/new', element: <BookingFormPage /> },
      { path: 'bookings/:bookingId/edit', element: <BookingFormPage /> },
      // Leads: admins and receptionists only (staff are sent to /bookings; the
      // API also refuses them). Static paths come before `:leadId`; the
      // dashboard is admin-only (R12.5).
      {
        path: 'leads',
        element: (
          <ProtectedRoute requiredRole={LEAD_ROLES}>
            <LeadsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'leads/new',
        element: (
          <ProtectedRoute requiredRole={LEAD_ROLES}>
            <QuickAddLeadPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'leads/dashboard',
        element: (
          <ProtectedRoute requiredRole="admin">
            <LeadDashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'leads/:leadId',
        element: (
          <ProtectedRoute requiredRole={LEAD_ROLES}>
            <LeadDetailPage />
          </ProtectedRoute>
        ),
      },
      { path: 'timesheet', element: <TimesheetPage /> },
      { path: 'cakesheet', element: <CakesheetPage /> },
      {
        path: 'analytics',
        element: (
          <ProtectedRoute requiredRole="admin">
            <AnalyticsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'catalog',
        element: (
          <ProtectedRoute requiredRole="admin">
            <CatalogPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'coupons',
        element: (
          <ProtectedRoute requiredRole="admin">
            <CouponsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'users',
        element: (
          <ProtectedRoute requiredRole="admin">
            <UsersPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
  { path: '*', element: <Navigate to="/bookings" replace /> },
]);
