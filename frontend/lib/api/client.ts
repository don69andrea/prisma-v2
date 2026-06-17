import { trackRequestStart } from './cold-start-store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('prisma_token');
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const token = getToken();
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  // Render-Free-Tier-Backends können nach Inaktivität (Cold Start) bis zu
  // ~52s zum Aufwachen brauchen. Ohne Hinweis wirkt das wie ein Hänger.
  // trackRequestStart() startet einen Timer, der nach COLD_START_THRESHOLD_MS
  // global einen Hinweis sichtbar macht — zentral hier statt pro Seite.
  const finishTracking = trackRequestStart();

  try {
    const response = await fetch(url, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...init?.headers,
      },
    });

    if (!response.ok) {
      let message = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const body = (await response.json()) as { detail?: string | Array<{ msg: string }> };
        if (typeof body?.detail === 'string') {
          message = body.detail;
        } else if (Array.isArray(body?.detail)) {
          message = body.detail.map((e) => e.msg).join(', ');
        }
      } catch {
        // ignore JSON parse failures — use default message
      }
      if (response.status === 401 && typeof window !== 'undefined') {
        localStorage.removeItem('prisma_token');
        document.cookie = 'prisma_token=; path=/; max-age=0; SameSite=Strict';
        window.location.href = '/login';
      }
      throw new ApiError(response.status, message);
    }

    if (response.status === 204 || response.headers.get('content-length') === '0') {
      return undefined as T;
    }
    return (await response.json()) as T;
  } finally {
    finishTracking();
  }
}
