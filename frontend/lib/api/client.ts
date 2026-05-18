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

  return response.json() as Promise<T>;
}
