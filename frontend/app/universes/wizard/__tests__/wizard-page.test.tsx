import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';

import WizardPage from '../page';
import * as universesApi from '@/lib/api/universes';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function wrap(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('Universe-Wizard Page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows description input and disabled button initially', () => {
    wrap(<WizardPage />);
    expect(screen.getByPlaceholderText(/Beschreibe/i)).toBeDefined();
    const btn = screen.getByRole('button', { name: /generieren/i });
    expect(btn.hasAttribute('disabled')).toBe(true);
  });

  it('enables generate button when description >= 3 chars', () => {
    wrap(<WizardPage />);
    const input = screen.getByPlaceholderText(/Beschreibe/i) as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: 'Tech' } });
    const btn = screen.getByRole('button', { name: /generieren/i });
    expect(btn.hasAttribute('disabled')).toBe(false);
  });

  it('shows result form with prefilled values after successful suggestion', async () => {
    vi.spyOn(universesApi, 'suggestUniverse').mockResolvedValue({
      name: 'Tech-3',
      region: 'US',
      tickers: ['AAPL', 'MSFT', 'NVDA'],
      reasoning: 'US-Tech-Schwergewichte.',
      available_tickers: ['AAPL', 'MSFT', 'NVDA', 'GOOGL'],
    });

    wrap(<WizardPage />);
    const input = screen.getByPlaceholderText(/Beschreibe/i);
    fireEvent.change(input, { target: { value: 'Tech-Heavy' } });
    fireEvent.click(screen.getByRole('button', { name: /generieren/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue('Tech-3')).toBeDefined();
      expect(screen.getByDisplayValue('US')).toBeDefined();
      expect(screen.getByDisplayValue(/AAPL.*MSFT.*NVDA/)).toBeDefined();
      expect(screen.getByText(/US-Tech-Schwergewichte/)).toBeDefined();
    });
  });

  it('shows error state when suggestion fails', async () => {
    vi.spyOn(universesApi, 'suggestUniverse').mockRejectedValue(
      new Error('LLM-Service nicht erreichbar'),
    );

    wrap(<WizardPage />);
    fireEvent.change(screen.getByPlaceholderText(/Beschreibe/i), {
      target: { value: 'something' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generieren/i }));

    await waitFor(() => {
      expect(screen.getByText(/LLM-Service nicht erreichbar/)).toBeDefined();
    });
  });

  it('reset clears the suggestion form', async () => {
    vi.spyOn(universesApi, 'suggestUniverse').mockResolvedValue({
      name: 'Tech-3',
      region: 'US',
      tickers: ['AAPL', 'MSFT'],
      reasoning: 'Test-Begründung mit ausreichender Länge.',
      available_tickers: [],
    });

    wrap(<WizardPage />);
    fireEvent.change(screen.getByPlaceholderText(/Beschreibe/i), {
      target: { value: 'Tech' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generieren/i }));

    await waitFor(() => expect(screen.getByDisplayValue('Tech-3')).toBeDefined());
    fireEvent.click(screen.getByRole('button', { name: /verwerfen/i }));
    expect(screen.queryByDisplayValue('Tech-3')).toBeNull();
  });
});
