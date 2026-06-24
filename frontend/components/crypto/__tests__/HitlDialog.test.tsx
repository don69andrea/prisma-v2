import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { HitlDialog } from '../HitlDialog';

vi.mock('@/lib/api/agent-audit', () => ({
  confirmHitl: vi.fn().mockResolvedValue({ id: 'x', decision: 'proceed', decided_at: '' }),
}));

const mockSignal = {
  coin: 'BTC', action: 'BUY' as const, size_factor: 0.6, confidence: 0.55,
  rationale_by_layer: { technical: 'Weak signal' },
  audit_trail_id: 'abc-123', disclaimer: 'test',
};

describe('HitlDialog', () => {
  it('shows coin name and confidence', () => {
    render(<HitlDialog signal={mockSignal} open={true} onProceed={() => {}} onAbort={() => {}} />);
    expect(screen.getByText(/BTC/)).toBeDefined();
    expect(screen.getByText(/55%/)).toBeDefined();
  });

  it('calls onProceed when user confirms', async () => {
    const onProceed = vi.fn();
    render(<HitlDialog signal={mockSignal} open={true} onProceed={onProceed} onAbort={() => {}} />);
    fireEvent.click(screen.getByText('Verstanden, fortfahren'));
    await waitFor(() => expect(onProceed).toHaveBeenCalled());
  });

  it('calls onAbort when user cancels', async () => {
    const onAbort = vi.fn();
    render(<HitlDialog signal={mockSignal} open={true} onProceed={() => {}} onAbort={onAbort} />);
    fireEvent.click(screen.getByText('Abbrechen'));
    await waitFor(() => expect(onAbort).toHaveBeenCalled());
  });

  it('states kein Handel wird ausgelöst', () => {
    render(<HitlDialog signal={mockSignal} open={true} onProceed={() => {}} onAbort={() => {}} />);
    expect(screen.getByText(/kein Handel wird ausgelöst/)).toBeDefined();
  });
});
