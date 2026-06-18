'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listUsers, patchUser, resetUserData } from '@/lib/api/users';

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: users = [] } = useQuery({ queryKey: ['admin-users'], queryFn: listUsers });
  const user = users.find((u) => u.id === id);

  const [newPassword, setNewPassword] = useState('');
  const [message, setMessage] = useState('');

  const patchMutation = useMutation({
    mutationFn: (payload: { password?: string; is_active?: boolean }) =>
      patchUser(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setMessage('Gespeichert.');
      setNewPassword('');
    },
    onError: (err: Error) => setMessage(`Fehler: ${err.message}`),
  });

  const resetMutation = useMutation({
    mutationFn: () => resetUserData(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      setMessage('Alle Daten wurden gelöscht.');
    },
  });

  if (!user) return <p className="text-muted-foreground">User nicht gefunden.</p>;

  return (
    <div className="space-y-6 max-w-md">
      <div>
        <button
          onClick={() => router.back()}
          className="text-sm text-muted-foreground hover:text-foreground mb-4 inline-flex items-center gap-1"
        >
          ← Zurück
        </button>
        <h1 className="text-xl font-semibold">{user.email}</h1>
        <p className="text-sm text-muted-foreground">
          {user.role} · {user.is_active ? 'Aktiv' : 'Gesperrt'}
        </p>
      </div>

      {message && (
        <p className="text-sm bg-muted px-3 py-2 rounded-md">{message}</p>
      )}

      <div className="space-y-4 border border-border rounded-lg p-4">
        <h2 className="text-sm font-medium">Passwort setzen</h2>
        <input
          type="password"
          placeholder="Neues Passwort"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          className="w-full border border-input rounded-md px-3 py-2 text-sm bg-background"
        />
        <button
          onClick={() => newPassword && patchMutation.mutate({ password: newPassword })}
          disabled={!newPassword || patchMutation.isPending}
          className="text-sm bg-primary text-primary-foreground px-3 py-1.5 rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          Passwort aktualisieren
        </button>
      </div>

      <div className="space-y-3 border border-border rounded-lg p-4">
        <h2 className="text-sm font-medium">Account-Status</h2>
        <button
          onClick={() => patchMutation.mutate({ is_active: !user.is_active })}
          className={`text-sm px-3 py-1.5 rounded-md ${
            user.is_active
              ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
              : 'bg-green-600 text-white hover:bg-green-700'
          }`}
        >
          {user.is_active ? 'User sperren' : 'User aktivieren'}
        </button>
      </div>

      <div className="space-y-3 border border-destructive/30 rounded-lg p-4">
        <h2 className="text-sm font-medium text-destructive">Danger Zone</h2>
        <p className="text-xs text-muted-foreground">
          Löscht alle persönlichen Daten (Portfolio, Alerts, Memos, Backtests …). Der Account bleibt erhalten.
        </p>
        <button
          onClick={() => {
            if (confirm(`Alle Daten von ${user.email} wirklich löschen?`)) {
              resetMutation.mutate();
            }
          }}
          className="text-sm border border-destructive text-destructive px-3 py-1.5 rounded-md hover:bg-destructive/10"
        >
          Alle Daten zurücksetzen
        </button>
      </div>
    </div>
  );
}
