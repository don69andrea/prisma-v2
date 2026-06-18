import { chromium, type FullConfig } from '@playwright/test';

const API_URL = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@ci-test.local';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'ci-test-password-123';

export default async function globalSetup(_config: FullConfig): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  });

  if (!res.ok) {
    throw new Error(`Login failed: ${res.status} ${await res.text()}`);
  }

  const { access_token } = (await res.json()) as { access_token: string };

  const browser = await chromium.launch();
  const context = await browser.newContext();

  await context.addCookies([
    {
      name: 'prisma_token',
      value: access_token,
      domain: 'localhost',
      path: '/',
      expires: -1,
      httpOnly: false,
      secure: false,
      sameSite: 'Strict',
    },
    {
      name: 'prisma_onboarding',
      value: 'complete',
      domain: 'localhost',
      path: '/',
      expires: -1,
      httpOnly: false,
      secure: false,
      sameSite: 'Lax',
    },
  ]);

  await context.addInitScript((token: string) => {
    localStorage.setItem('prisma_token', token);
  }, access_token);

  await context.storageState({ path: 'e2e/.auth-state.json' });
  await browser.close();
}
