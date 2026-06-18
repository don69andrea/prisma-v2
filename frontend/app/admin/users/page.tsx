'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { listUsers, createUser, type UserItem } from '@/lib/api/users';

export default function UsersPage() {
  const qc = useQueryClient();
  const { data: users = [], isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: listUsers,
  });

  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'viewer' | 'admin'>('viewer');
  const [formError, setFormError] = useState('');

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setShowForm(false);
      setEmail('');
      setPassword('');
    },
    onError: (err: Error) => setFormError(err.message),
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError('');
    createMutation.mutate({ email, password, role });
  }

  if (isLoading) return <p className="text-muted-foreground">Lädt …</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">User-Verwaltung</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90"
        >
          + Neuer User
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="border border-border rounded-lg p-4 space-y-3"
        >
          {formError && <p className="text-sm text-destructive">{formError}</p>}
          <input
            type="email"
            placeholder="E-Mail"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
          />
          <input
            type="password"
            placeholder="Passwort"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as 'viewer' | 'admin')}
            className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
          >
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              Erstellen
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="text-sm px-3 py-1.5 rounded-md border border-border hover:bg-muted"
            >
              Abbrechen
            </button>
          </div>
        </form>
      )}

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="text-left px-4 py-2 font-medium">E-Mail</th>
              <th className="text-left px-4 py-2 font-medium">Rolle</th>
              <th className="text-left px-4 py-2 font-medium">Status</th>
              <th className="text-left px-4 py-2 font-medium">Erstellt</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {users.map((user: UserItem) => (
              <tr key={user.id} className="border-t border-border hover:bg-muted/40">
                <td className="px-4 py-2">{user.email}</td>
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      user.role === 'admin'
                        ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {user.role}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      user.is_active
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    }`}
                  >
                    {user.is_active ? 'Aktiv' : 'Gesperrt'}
                  </span>
                </td>
                <td className="px-4 py-2 text-muted-foreground">
                  {new Date(user.created_at).toLocaleDateString('de-CH')}
                </td>
                <td className="px-4 py-2 text-right">
                  <Link
                    href={`/admin/users/${user.id}`}
                    className="text-primary hover:underline text-xs"
                  >
                    Verwalten
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
