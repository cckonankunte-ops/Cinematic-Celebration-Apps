/**
 * Route guard. Redirects to `/login` when there is no authenticated user
 * (after the initial session restore completes). An optional `requiredRole`
 * (one role or a list) gates restricted areas; other users are redirected to
 * `/bookings`.
 */

import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from './useAuth';
import type { UserRole } from './types';

interface ProtectedRouteProps {
  children: ReactNode;
  requiredRole?: UserRole | UserRole[];
}

export function ProtectedRoute({
  children,
  requiredRole,
}: ProtectedRouteProps): JSX.Element {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-gray-500">
        Loading…
      </div>
    );
  }

  if (user === null) {
    return <Navigate to="/login" replace />;
  }

  const allowed =
    requiredRole === undefined ||
    (Array.isArray(requiredRole) ? requiredRole.includes(user.role) : user.role === requiredRole);
  if (!allowed) {
    return <Navigate to="/bookings" replace />;
  }

  return <>{children}</>;
}
