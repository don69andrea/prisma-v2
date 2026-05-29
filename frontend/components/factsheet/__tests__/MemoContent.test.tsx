import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MemoContent } from '../MemoContent';
import type { Memo } from '@/lib/api/memos';

const baseMemo: Memo = {
  id: 'memo-1',
  stock_id: 'stock-1',
  model_run_id: 'run-1',
  language: 'de',
  one_liner: 'Solide Wachstums-Geschichte mit Trend-Rückenwind.',
  ranking_interpretation: 'Stock liegt im Top-Quintil aller 5 Modelle.',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: ['Strong ROE', 'Low Debt'],
  key_risks: ['China-Exposure'],
  confidence: 'high',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

describe('MemoContent', () => {
  it('renders one_liner as hero', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/Solide Wachstums-Geschichte/)).toBeDefined();
  });

  it('renders all key_strengths', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText('Strong ROE')).toBeDefined();
    expect(screen.getByText('Low Debt')).toBeDefined();
  });

  it('renders all key_risks', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText('China-Exposure')).toBeDefined();
  });

  it('renders confidence badge', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/high|Hoh/i)).toBeDefined();
  });

  it('hides sweet-spot card when sweet_spot is false', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.queryByText(/Sweet-Spot/)).toBeNull();
  });

  it('shows sweet-spot card with explanation when sweet_spot=true', () => {
    const sweetMemo: Memo = {
      ...baseMemo,
      sweet_spot: true,
      sweet_spot_explanation: 'Top-Quintil in allen 5 Modellen.',
    };
    render(<MemoContent memo={sweetMemo} />);
    expect(screen.getByText(/Sweet-Spot/)).toBeDefined();
    expect(screen.getByText(/Top-Quintil in allen 5 Modellen/)).toBeDefined();
  });

  it('hides contradictions section when array is empty', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.queryByText(/Widersprüche/)).toBeNull();
  });

  it('shows contradictions with model_a, model_b, description', () => {
    const contraMemo: Memo = {
      ...baseMemo,
      contradictions: [
        { model_a: 'Quality', model_b: 'Value', description: 'Hohe Margen, aber teuer.' },
      ],
    };
    render(<MemoContent memo={contraMemo} />);
    expect(screen.getByText(/Widersprüche/)).toBeDefined();
    expect(screen.getByText(/Quality/)).toBeDefined();
    expect(screen.getByText(/Value/)).toBeDefined();
    expect(screen.getByText(/Hohe Margen, aber teuer/)).toBeDefined();
  });

  it('renders ranking_interpretation', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/Top-Quintil aller 5 Modelle/)).toBeDefined();
  });

  it('renders model_version in footer', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/claude-sonnet-4-6/)).toBeDefined();
  });
});
