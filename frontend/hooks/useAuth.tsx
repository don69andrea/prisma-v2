'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api/client';

export interface AuthUser {
  id: string;
  email: string;
  role: 'admin' | 'viewer';
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

function setTokenCookie(token: string): void {
  const maxAge = 8 * 3600;
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `prisma_token=${token}; path=/; max-age=${maxAge}; SameSite=Strict${secure}`;
  localStorage.setItem('prisma_token', token);
}

function clearTokenCookie(): void {
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `prisma_token=; path=/; max-age=0; SameSite=Strict${secure}`;
  localStorage.removeItem('prisma_token');
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('prisma_token');
    if (!token) {
      setLoading(false);
      return;
    }
    apiFetch<AuthUser>('/api/v1/auth/me')
      .then(setUser)
      .catch(() => {
        clearTokenCookie();
        router.replace('/login');
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string): Promise<void> {
    const res = await apiFetch<{ access_token: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setTokenCookie(res.access_token);
    const me = await apiFetch<AuthUser>('/api/v1/auth/me');
    setUser(me);
    router.push('/');
  }

  function logout(): void {
    clearTokenCookie();
    setUser(null);
    router.push('/login');
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
