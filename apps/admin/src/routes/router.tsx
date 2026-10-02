import { createBrowserRouter, Navigate } from 'react-router-dom';

import { AppLayout } from '@/features/auth/AppLayout';
import { LoginPage } from '@/features/auth/LoginPage';
import { ProtectedRoute } from '@/features/auth/ProtectedRoute';
import { LocationGate } from '@/features/location/LocationGate';
import { BookingListPage } from '@/features/bookings/BookingListPage';
import { BookingFormPage } from '@/features/bookings/BookingFormPage';
import { TimesheetPage } from '@/features/timesheet/TimesheetPage';
import { CakesheetPage } from '@/features/cakesheet/CakesheetPage';
import { AnalyticsPage } from '@/features/analytics/AnalyticsPage';
import { CatalogPage } from '@/features/catalog/CatalogPage';

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
    ],
  },
  { path: '*', element: <Navigate to="/bookings" replace /> },
]);
