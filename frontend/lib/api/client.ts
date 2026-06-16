import { trackRequestStart } from './cold-start-store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

if (!API_KEY && process.env.NODE_ENV === 'development') {
  console.warn('[prisma] NEXT_PUBLIC_API_KEY is not set — authenticated endpoints will return 401.');
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

  const authHeaders: Record<string, string> = API_KEY ? { 'X-API-Key': API_KEY } : {};

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
