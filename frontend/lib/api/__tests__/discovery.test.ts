import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/lib/api/client', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '@/lib/api/client';
import {
  createDiscoverySession,
  submitAnswer,
  completeDiscovery,
} from '@/lib/api/discovery';

const mockApiFetch = vi.mocked(apiFetch);

beforeEach(() => {
  mockApiFetch.mockReset();
});

describe('createDiscoverySession', () => {
  it('gibt session_id zurück', async () => {
    mockApiFetch.mockResolvedValueOnce({ session_id: 'abc-123' });

    const result = await createDiscoverySession();

    expect(result.session_id).toBe('abc-123');
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/discovery/session', {
      method: 'POST',
    });
  });
});

describe('submitAnswer', () => {
  it('sendet korrekten turn und answer (string)', async () => {
    const mockResponse = {
      session_id: 'abc-123',
      next_turn: 2,
      confidence: 0.5,
      partial_profile: {
        beruf: 'Entwickler',
        ziel: 'freedom',
        risiko: 'moderate',
        brands: [],
      },
    };
    mockApiFetch.mockResolvedValueOnce(mockResponse);

    const result = await submitAnswer('abc-123', 1, 'Entwickler');

    expect(result.session_id).toBe('abc-123');
    expect(result.next_turn).toBe(2);
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/discovery/answer', {
      method: 'POST',
      body: JSON.stringify({ session_id: 'abc-123', turn: 1, answer: 'Entwickler' }),
    });
  });

  it('sendet korrekten turn und answer (string-Array)', async () => {
    const mockResponse = {
      session_id: 'abc-123',
      next_turn: null,
      confidence: 0.9,
      partial_profile: {
        beruf: 'Entwickler',
        ziel: 'freedom',
        risiko: 'moderate',
        brands: ['NESN', 'ROG'],
      },
    };
    mockApiFetch.mockResolvedValueOnce(mockResponse);

    const result = await submitAnswer('abc-123', 4, ['NESN', 'ROG']);

    expect(result.next_turn).toBeNull();
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/discovery/answer', {
      method: 'POST',
      body: JSON.stringify({ session_id: 'abc-123', turn: 4, answer: ['NESN', 'ROG'] }),
    });
  });
});

describe('completeDiscovery', () => {
  it('gibt profile und recommended_stocks zurück', async () => {
    const mockResponse = {
      profile: {
        beruf: 'Entwickler',
        ziel: 'freedom' as const,
        risiko: 'moderate' as const,
        brands: ['NESN'],
      },
      recommended_stocks: [
        { ticker: 'NESN', name: 'Nestlé', score: 0.92, reason: 'Stabile Dividenden' },
        { ticker: 'ROG', name: 'Roche', score: 0.88, reason: 'Defensiver Wert' },
      ],
    };
    mockApiFetch.mockResolvedValueOnce(mockResponse);

    const result = await completeDiscovery('abc-123');

    expect(result.recommended_stocks).toHaveLength(2);
    expect(result.recommended_stocks[0].ticker).toBe('NESN');
    expect(result.profile.ziel).toBe('freedom');
    expect(mockApiFetch).toHaveBeenCalledWith('/api/v1/discovery/complete', {
      method: 'POST',
      body: JSON.stringify({ session_id: 'abc-123' }),
    });
  });
});
