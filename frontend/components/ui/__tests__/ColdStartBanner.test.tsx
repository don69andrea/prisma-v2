import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

import { ColdStartBanner } from '../ColdStartBanner';
import {
  trackRequestStart,
  __resetColdStartStateForTests,
} from '@/lib/api/cold-start-store';

describe('ColdStartBanner', () => {
  beforeEach(() => {
    __resetColdStartStateForTests();
  });

  it('ist standardmässig nicht sichtbar', () => {
    render(<ColdStartBanner />);
    expect(screen.queryByText(/App startet/i)).not.toBeInTheDocument();
  });

  it('zeigt den Hinweis, sobald der Store ihn als sichtbar markiert', async () => {
    render(<ColdStartBanner />);

    let done: () => void = () => {};
    act(() => {
      done = trackRequestStart(0); // Threshold 0 -> Timer feuert sofort
    });

    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(screen.getByText(/App startet/i)).toBeInTheDocument();

    act(() => done());
    expect(screen.queryByText(/App startet/i)).not.toBeInTheDocument();
  });
});
