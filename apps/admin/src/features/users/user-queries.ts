/**
 * TanStack Query hooks for admin user management (admin-only API).
 * Create / list / update / deactivate staff + admin users. Password hashes are
 * never returned by the API; we only ever send a new password.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import { api } from '@/api/client';

export type UserRole = 'admin' | 'staff';

export interface UserAdminRead {
  id: number;
  username: string;
  role: string;
  location_id: number | null;
  is_active: boolean;
}

export interface UserCreateBody {
  username: string;
  password: string;
  role: UserRole;
  location_id: number | null;
}

export type UserUpdateBody = Partial<{
  username: string;
  password: string;
  role: UserRole;
  location_id: number | null;
  is_active: boolean;
}>;

export function useUsers(): UseQueryResult<UserAdminRead[]> {
  return useQuery<UserAdminRead[]>({
    queryKey: ['users'],
    queryFn: () => api.get<UserAdminRead[]>('/api/v1/admin/users'),
  });
}

export function useCreateUser(): UseMutationResult<
  UserAdminRead,
  unknown,
  UserCreateBody
> {
  const qc = useQueryClient();
  return useMutation<UserAdminRead, unknown, UserCreateBody>({
    mutationFn: (body) => api.post<UserAdminRead>('/api/v1/admin/users', body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useUpdateUser(
  id: number,
): UseMutationResult<UserAdminRead, unknown, UserUpdateBody> {
  const qc = useQueryClient();
  return useMutation<UserAdminRead, unknown, UserUpdateBody>({
    mutationFn: (body) => api.patch<UserAdminRead>(`/api/v1/admin/users/${id}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] });
    },
  });
}

export function useDeactivateUser(): UseMutationResult<
  UserAdminRead,
  unknown,
  number
> {
  const qc = useQueryClient();
  return useMutation<UserAdminRead, unknown, number>({
    mutationFn: (id) => api.del<UserAdminRead>(`/api/v1/admin/users/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] });
    },
  });
}
