'use client';

import { useCallback, useState } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function getAuthHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('prisma_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function useCryptoAgentAnalysis() {
  const [analysis, setAnalysis] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (ticker: string) => {
    setLoading(true);
    setAnalysis('');
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/crypto/analyze/${ticker}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          setAnalysis((prev) => prev + data);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysefehler');
    } finally {
      setLoading(false);
    }
  }, []);

  return { analysis, loading, error, analyze };
}
