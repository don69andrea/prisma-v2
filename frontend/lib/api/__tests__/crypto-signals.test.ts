import { describe, it, expect } from 'vitest';
import type {
  SignalVector,
  BacktestReport,
  PortfolioCoinStats,
  PortfolioBacktestReport,
  MetaLabelReport,
  TradeSignal,
} from '../crypto-signals';
import type { AgentAuditResponse, HitlConfirmResponse } from '../agent-audit';
import type { OHLCVBar, OHLCVResponse } from '../ohlcv';

// Tests verify shape of type-guard functions (no network calls)

describe('SignalVector shape', () => {
  it('accepts valid BUY signal', () => {
    const v: SignalVector = {
      coin: 'BTC',
      asof: '2026-06-24',
      action: 'BUY',
      size_factor: 0.8,
      consensus: '3/3',
      sub_scores: { ma_signal: 1, macd_signal: 1, rsi_signal: 1 },
      confidence: 0.75,
      disclaimer: 'test',
    };
    expect(v.action).toBe('BUY');
    expect(v.size_factor).toBeGreaterThanOrEqual(0);
  });

  it('BacktestReport has equity_curve as tuple array', () => {
    const r: BacktestReport = {
      coin: 'BTC',
      cagr: 0.3,
      sharpe: 1.5,
      max_dd: -0.5,
      calmar: 1.3,
      beats_exposure_matched: true,
      n_trades: 42,
      equity_curve: [
        ['2026-01-01', 1.0],
        ['2026-06-01', 1.4],
      ],
    };
    expect(r.equity_curve[0][0]).toBeTypeOf('string');
    expect(r.equity_curve[0][1]).toBeTypeOf('number');
  });
});

describe('PortfolioBacktestReport shape', () => {
  it('accepts valid portfolio report', () => {
    const stats: PortfolioCoinStats = { avg_weight: 0.3, days_in_portfolio: 90 };
    const p: PortfolioBacktestReport = {
      coins: ['BTC', 'ETH'],
      sharpe: 1.2,
      calmar: 0.9,
      max_dd: -0.3,
      cagr: 0.25,
      avg_exposure: 0.7,
      n_rebalances: 12,
      beats_equal_weight_bh: true,
      beats_exposure_matched: false,
      equity_curve: [['2026-01-01', 1.0]],
      per_coin_stats: { BTC: stats },
      pit_universe: { BTC: '2025-01-01' },
      costs: 0.002,
    };
    expect(p.coins).toContain('BTC');
    expect(p.per_coin_stats['BTC'].avg_weight).toBeGreaterThan(0);
  });
});

describe('MetaLabelReport shape', () => {
  it('accepts valid meta-label report', () => {
    const m: MetaLabelReport = {
      coin: 'ETH',
      label_method: 'triple_barrier',
      classifier: 'lgbm',
      n_folds: 5,
      oos_precision: 0.62,
      oos_recall: 0.58,
      always_trade_sharpe: 0.9,
      always_trade_calmar: 0.7,
      meta_filtered_sharpe: 1.1,
      meta_filtered_calmar: 0.95,
      n_trades_always: 100,
      n_trades_filtered: 61,
      beats_baseline: true,
      finding: 'positive',
      finding_reason: 'Meta filter improves Sharpe by 22%',
    };
    expect(m.finding).toBe('positive');
    expect(m.classifier).toBe('lgbm');
  });
});

describe('TradeSignal shape', () => {
  it('accepts valid trade signal', () => {
    const s: TradeSignal = {
      coin: 'BTC',
      action: 'HOLD',
      size_factor: 0.5,
      confidence: 0.6,
      rationale_by_layer: { technical: 'neutral', macro: 'risk-off' },
      audit_trail_id: '550e8400-e29b-41d4-a716-446655440000',
      disclaimer: 'Not financial advice',
    };
    expect(s.action).toBe('HOLD');
    expect(s.audit_trail_id).toBeTypeOf('string');
  });
});

describe('AgentAuditResponse shape', () => {
  it('accepts valid audit response with optional fields', () => {
    const a: AgentAuditResponse = {
      audit_trail_id: '550e8400-e29b-41d4-a716-446655440000',
      coin: 'BTC',
      asof: '2026-06-24',
      agent_run: {
        technical: {
          coin: 'BTC',
          stance: 'BULLISH',
          consensus: '3/3',
          key_signals: ['MA crossover', 'MACD positive'],
          confidence: 0.8,
          reasoning: 'Strong uptrend',
        },
      },
      created_at: '2026-06-24T10:00:00Z',
    };
    expect(a.agent_run.technical?.stance).toBe('BULLISH');
    expect(a.agent_run.onchain).toBeUndefined();
  });
});

describe('HitlConfirmResponse shape', () => {
  it('accepts valid HITL confirm response', () => {
    const h: HitlConfirmResponse = {
      id: 'abc-123',
      audit_trail_id: '550e8400-e29b-41d4-a716-446655440000',
      coin: 'BTC',
      decision: 'proceed',
      decided_at: '2026-06-24T10:05:00Z',
    };
    expect(h.decision).toBe('proceed');
  });
});

describe('OHLCVResponse shape', () => {
  it('accepts valid OHLCV response', () => {
    const bar: OHLCVBar = {
      date: '2026-06-24',
      open: 65000,
      high: 67000,
      low: 64500,
      close: 66500,
      volume: 25000,
    };
    const r: OHLCVResponse = { coin: 'BTC', symbol: 'BTC-USD', bars: [bar] };
    expect(r.bars[0].close).toBeGreaterThan(0);
    expect(r.bars[0].date).toBeTypeOf('string');
  });
});
