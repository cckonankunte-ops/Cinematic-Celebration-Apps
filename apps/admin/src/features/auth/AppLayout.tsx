/**
 * Authenticated shell: a top nav (Bookings, Timesheet, Cakesheet, Analytics for
 * admins, Logout) plus the location switcher for admins. Staff see their single
 * pinned location name. The nav is mobile-first (wraps on small screens).
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { useLocation } from '@/features/location/useLocation';
import { useAuth } from './useAuth';

function navClass({ isActive }: { isActive: boolean }): string {
  const base = 'rounded px-3 py-1.5 text-sm font-medium';
  return isActive ? `${base} bg-gray-900 text-white` : `${base} text-gray-700 hover:bg-gray-100`;
}

function LocationSwitcher(): JSX.Element {
  const { locations, selectedLocationId, canSwitch, selectLocation } = useLocation();

  if (!canSwitch) {
    const current = locations.find((l) => l.id === selectedLocationId);
    return <span className="text-sm text-gray-500">{current?.name ?? '—'}</span>;
  }

  return (
    <select
      aria-label="Location"
      className="rounded border border-gray-300 px-2 py-1 text-sm"
      value={selectedLocationId ?? ''}
      onChange={(e) => selectLocation(Number(e.target.value))}
    >
      {locations.map((l) => (
        <option key={l.id} value={l.id}>
          {l.name}
        </option>
      ))}
    </select>
  );
}

export function AppLayout(): JSX.Element {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async (): Promise<void> => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-3">
          <NavLink to="/bookings" className={navClass}>
            Bookings
          </NavLink>
          <NavLink to="/timesheet" className={navClass}>
            Timesheet
          </NavLink>
          <NavLink to="/cakesheet" className={navClass}>
            Cakesheet
          </NavLink>
          {user?.role === 'admin' && (
            <NavLink to="/analytics" className={navClass}>
              Analytics
            </NavLink>
          )}
          {user?.role === 'admin' && (
            <NavLink to="/catalog" className={navClass}>
              Catalog
            </NavLink>
          )}
          <div className="ml-auto flex items-center gap-3">
            <LocationSwitcher />
            <button
              type="button"
              onClick={onLogout}
              className="rounded px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Logout
            </button>
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl p-4">
        <Outlet />
      </main>
    </div>
  );
}
