import { render, screen, fireEvent } from '@testing-library/react';
import { ExplainabilityPanel } from '../ExplainabilityPanel';

const mockSignal = {
  coin: 'BTC', asof: '2026-06-24', action: 'BUY' as const,
  size_factor: 0.8, consensus: '3/3',
  sub_scores: { ma_signal: 1, macd_signal: 1, rsi_signal: 1, vol_pred: 0.55, momentum_rank: 2, onchain_score: 0.7 },
  confidence: 0.75, disclaimer: 'test',
};

const mockAudit = {
  audit_trail_id: 'abc-123', coin: 'BTC', asof: '2026-06-24', created_at: '',
  agent_run: {
    technical: { coin: 'BTC', stance: 'BULLISH' as const, consensus: '3/3', key_signals: [], confidence: 0.8, reasoning: 'MA above 200-day' },
    bull: { thesis: 'Strong momentum', strongest_points: [], risks_acknowledged: [] },
    bear: { thesis: 'Overextended', strongest_points: [], counter_to_bull: [] },
    risk: { approve: true, max_size: 1.0, breaches: [], reasoning: 'Within limits' },
  },
};

describe('ExplainabilityPanel', () => {
  it('renders 3 layer rows', () => {
    render(<ExplainabilityPanel signal={mockSignal} audit={null} />);
    expect(screen.getByText('Schicht 1 — WAS')).toBeDefined();
    expect(screen.getByText('Schicht 2 — WANN')).toBeDefined();
    expect(screen.getByText('Schicht 3 — WIEVIEL')).toBeDefined();
  });

  it('shows disclaimer', () => {
    render(<ExplainabilityPanel signal={mockSignal} audit={null} />);
    expect(screen.getByText(/kein Anlagerat/)).toBeDefined();
  });

  it('shows reasoning chain when audit provided and toggled', () => {
    render(<ExplainabilityPanel signal={mockSignal} audit={mockAudit} />);
    const toggle = screen.getByText('Agent-Reasoning-Kette');
    fireEvent.click(toggle);
    expect(screen.getByText(/MA above 200-day/)).toBeDefined();
    expect(screen.getByText(/Strong momentum/)).toBeDefined();
  });

  it('hides reasoning when no audit', () => {
    render(<ExplainabilityPanel signal={mockSignal} audit={null} />);
    expect(screen.queryByText('Agent-Reasoning-Kette')).toBeNull();
  });
});
