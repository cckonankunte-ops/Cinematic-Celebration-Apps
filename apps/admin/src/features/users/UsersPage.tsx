/**
 * Admin-only Staff / Users management.
 *
 * Lists users and lets an admin create a staff/admin account (username,
 * password, role, branch), reset a password, change the branch, and
 * activate/deactivate. All via the admin users API; passwords are argon2-hashed
 * server-side and never returned. Staff accounts are pinned to one branch;
 * admins have no branch (all locations).
 */

import { useState } from 'react';

import { useLocation } from '@/features/location/useLocation';
import {
  useCreateUser,
  useDeactivateUser,
  useUpdateUser,
  useUsers,
  type UserAdminRead,
  type UserRole,
} from './user-queries';

const inputCls = 'rounded border border-gray-300 px-2 py-1 text-sm';

function CreateUserForm(): JSX.Element {
  const { locations } = useLocation();
  const create = useCreateUser();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('staff');
  const [locationId, setLocationId] = useState<number | null>(
    locations[0]?.id ?? null,
  );
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent): void => {
    e.preventDefault();
    setError(null);
    if (username.trim().length < 1 || password.length < 8) {
      setError('Username required and password must be at least 8 characters.');
      return;
    }
    create.mutate(
      {
        username: username.trim(),
        password,
        role,
        // Staff are pinned to a branch; admins see all (no branch).
        location_id: role === 'staff' ? locationId : null,
      },
      {
        onSuccess: () => {
          setUsername('');
          setPassword('');
          setRole('staff');
        },
        onError: () => setError('Could not create user (username may be taken).'),
      },
    );
  };

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-end gap-2 rounded border border-gray-200 bg-white p-3"
    >
      <label className="text-sm">
        <span className="mr-1 text-gray-600">Username</span>
        <input
          className={inputCls}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
      </label>
      <label className="text-sm">
        <span className="mr-1 text-gray-600">Password</span>
        <input
          className={inputCls}
          type="text"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="min 8 chars"
        />
      </label>
      <label className="text-sm">
        <span className="mr-1 text-gray-600">Role</span>
        <select
          className={inputCls}
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
        >
          <option value="staff">Staff</option>
          <option value="admin">Admin</option>
        </select>
      </label>
      {role === 'staff' && (
        <label className="text-sm">
          <span className="mr-1 text-gray-600">Branch</span>
          <select
            className={inputCls}
            value={locationId ?? ''}
            onChange={(e) => setLocationId(Number(e.target.value))}
          >
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        type="submit"
        disabled={create.isPending}
        className="rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {create.isPending ? 'Adding…' : 'Add user'}
      </button>
      {error && <p className="w-full text-xs text-red-600">{error}</p>}
    </form>
  );
}

function UserRow({ user }: { user: UserAdminRead }): JSX.Element {
  const { locations } = useLocation();
  const update = useUpdateUser(user.id);
  const deactivate = useDeactivateUser();
  const [newPw, setNewPw] = useState('');
  const branch = locations.find((l) => l.id === user.location_id)?.name;

  const resetPassword = (): void => {
    if (newPw.length < 8) {
      return;
    }
    update.mutate({ password: newPw }, { onSuccess: () => setNewPw('') });
  };

  return (
    <tr className="border-b border-gray-100 align-top">
      <td className="py-2 pr-4">{user.username}</td>
      <td className="py-2 pr-4 capitalize">{user.role}</td>
      <td className="py-2 pr-4">{user.role === 'admin' ? 'All' : (branch ?? '—')}</td>
      <td className="py-2 pr-4">
        {user.is_active ? (
          <span className="text-green-700">Active</span>
        ) : (
          <span className="text-gray-400">Inactive</span>
        )}
      </td>
      <td className="py-2 pr-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            className={inputCls}
            type="text"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            placeholder="new password"
          />
          <button
            type="button"
            onClick={resetPassword}
            disabled={newPw.length < 8 || update.isPending}
            className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-50"
          >
            Reset password
          </button>
          {user.is_active ? (
            <button
              type="button"
              onClick={() => deactivate.mutate(user.id)}
              className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
            >
              Deactivate
            </button>
          ) : (
            <button
              type="button"
              onClick={() => update.mutate({ is_active: true })}
              className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
            >
              Activate
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export function UsersPage(): JSX.Element {
  const users = useUsers();

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">Staff &amp; Users</h1>
      <CreateUserForm />

      {users.isLoading && <p className="text-sm text-gray-500">Loading users…</p>}
      {users.isError && <p className="text-sm text-red-600">Failed to load users.</p>}

      {users.data && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse whitespace-nowrap text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-500">
                <th className="py-2 pr-4">Username</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2 pr-4">Branch</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <UserRow key={u.id} user={u} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
