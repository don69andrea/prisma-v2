import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { CryptoAgentPanel } from '../CryptoAgentPanel';

function makeStreamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
  return new Response(stream, { status: 200 });
}

describe('CryptoAgentPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('zeigt erkannte Patterns als Badges', () => {
    render(<CryptoAgentPanel ticker="BTC" detectedPatterns={['GOLDEN_CROSS', 'BULLISH_ENGULFING']} />);
    expect(screen.getByText('GOLDEN CROSS')).toBeInTheDocument();
    expect(screen.getByText('BULLISH ENGULFING')).toBeInTheDocument();
  });

  it('zeigt cachedAnalysis wenn vorhanden und noch nicht neu analysiert wurde', () => {
    render(<CryptoAgentPanel ticker="BTC" cachedAnalysis="Letzte Analyse vom Cron." />);
    expect(screen.getByText('Letzte Analyse vom Cron.')).toBeInTheDocument();
    expect(screen.getByText('(letzter Snapshot)')).toBeInTheDocument();
  });

  it('streamt Token-Chunks ins Analyse-Feld nach Klick auf "Neu analysieren"', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(makeStreamResponse(['data: Bitcoin ', 'data: zeigt Stärke.', 'data: [DONE]']))
    );

    render(<CryptoAgentPanel ticker="BTC" />);
    fireEvent.click(screen.getByTestId('crypto-agent-analyze-button'));

    await waitFor(() => {
      expect(screen.getByTestId('crypto-agent-text').textContent).toContain('Bitcoin');
    });
  });

  it('zeigt Fehlermeldung wenn der Stream-Request fehlschlägt', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

    render(<CryptoAgentPanel ticker="BTC" />);
    fireEvent.click(screen.getByTestId('crypto-agent-analyze-button'));

    await waitFor(() => {
      expect(screen.getByText(/Fehler:/)).toBeInTheDocument();
    });
  });
});
