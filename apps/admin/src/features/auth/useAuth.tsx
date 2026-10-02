/**
 * Authentication context + provider for the admin panel.
 *
 * On mount it calls `GET /auth/me` to restore the session from the httpOnly
 * cookie. `login` posts credentials and stores the returned user; `logout`
 * clears the server cookie and local state. A 401 from `/auth/me` simply means
 * no active session, so `user` becomes null (not an error).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, ApiError } from '@/api/client';
import type { AuthUser } from './types';

interface AuthContextValue {
  user: AuthUser | null;
  /** True while the initial `/auth/me` session restore is in flight. */
  isLoading: boolean;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refresh = useCallback(async () => {
    try {
      const me = await api.get<AuthUser>('/api/v1/auth/me');
      setUser(me);
    } catch (err) {
      // A 401 just means "not signed in"; anything else we also treat as
      // logged-out for the UI but let unexpected errors surface in the console.
      if (!(err instanceof ApiError) || err.status !== 401) {
        // eslint-disable-next-line no-console
        console.error('Session restore failed', err);
      }
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      await refresh();
      if (active) {
        setIsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    const next = await api.post<AuthUser>('/api/v1/auth/login', {
      username,
      password,
    });
    setUser(next);
    return next;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post<unknown>('/api/v1/auth/logout');
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, logout, refresh }),
    [user, isLoading, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Access the auth context. Throws if used outside `AuthProvider`. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
