import { apiFetch } from './client';

export interface UserItem {
  id: string;
  email: string;
  role: 'admin' | 'viewer';
  is_active: boolean;
  created_at: string;
}

export async function listUsers(): Promise<UserItem[]> {
  return apiFetch<UserItem[]>('/api/v1/users');
}

export async function createUser(payload: {
  email: string;
  password: string;
  role?: string;
}): Promise<UserItem> {
  return apiFetch<UserItem>('/api/v1/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function patchUser(
  id: string,
  payload: { password?: string; is_active?: boolean }
): Promise<void> {
  return apiFetch<void>(`/api/v1/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function resetUserData(id: string): Promise<void> {
  return apiFetch<void>(`/api/v1/users/${id}/data`, { method: 'DELETE' });
}
