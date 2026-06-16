import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { apiFetch } from '@/lib/api/client';
import {
  subscribeColdStart,
  __resetColdStartStateForTests,
} from '@/lib/api/cold-start-store';

function mockFetchWithDelay(delayMs: number) {
  return vi.fn().mockImplementation(
    () =>
      new Promise((resolve) => {
        setTimeout(() => {
          resolve(
            new Response(JSON.stringify({ ok: true }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            })
          );
        }, delayMs);
      })
  );
}

describe('Cold-Start-Hinweis (F-RENDER-2 / W-19)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    __resetColdStartStateForTests();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    __resetColdStartStateForTests();
  });

  it('zeigt den Hinweis, wenn ein Request länger als 5s dauert', async () => {
    vi.stubGlobal('fetch', mockFetchWithDelay(8_000));

    const states: boolean[] = [];
    const unsubscribe = subscribeColdStart((visible) => states.push(visible));

    const promise = apiFetch('/api/v1/slow');

    // Noch unter dem Threshold: kein Hinweis.
    await vi.advanceTimersByTimeAsync(4_000);
    expect(states).not.toContain(true);

    // Threshold überschritten: Hinweis erscheint.
    await vi.advanceTimersByTimeAsync(2_000);
    expect(states).toContain(true);

    // Request schliesst irgendwann ab -> Hinweis verschwindet wieder.
    await vi.advanceTimersByTimeAsync(3_000);
    await promise;
    expect(states[states.length - 1]).toBe(false);

    unsubscribe();
  });

  it('zeigt KEINEN Hinweis bei einer schnellen, normalen Antwort', async () => {
    vi.stubGlobal('fetch', mockFetchWithDelay(200));

    const states: boolean[] = [];
    const unsubscribe = subscribeColdStart((visible) => states.push(visible));

    const promise = apiFetch('/api/v1/fast');

    await vi.advanceTimersByTimeAsync(200);
    await promise;

    // Genug Zeit verstreichen lassen, falls (fälschlicherweise) ein Timer lief.
    await vi.advanceTimersByTimeAsync(10_000);

    expect(states).not.toContain(true);

    unsubscribe();
  });
});
