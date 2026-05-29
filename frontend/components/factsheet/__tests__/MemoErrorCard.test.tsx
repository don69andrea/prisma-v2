import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { MemoErrorCard } from '../MemoErrorCard';
import type { Memo } from '@/lib/api/memos';

const errorMemo: Memo = {
  id: 'memo-err',
  stock_id: 'stock-1',
  model_run_id: 'run-1',
  language: 'de',
  one_liner: '',
  ranking_interpretation: '',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: [],
  key_risks: [],
  confidence: 'low',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: true,
};

describe('MemoErrorCard', () => {
  it('shows error state and regenerate button', () => {
    render(<MemoErrorCard memo={errorMemo} onRegenerate={() => {}} isGenerating={false} />);
    expect(screen.getByText(/fehlgeschlagen/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Erneut generieren/ })).toBeDefined();
  });

  it('calls onRegenerate on click', () => {
    const onRegenerate = vi.fn();
    render(<MemoErrorCard memo={errorMemo} onRegenerate={onRegenerate} isGenerating={false} />);
    fireEvent.click(screen.getByRole('button', { name: /Erneut generieren/ }));
    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it('disables button while regenerating', () => {
    render(<MemoErrorCard memo={errorMemo} onRegenerate={() => {}} isGenerating={true} />);
    const btn = screen.getByRole('button');
    expect(btn.hasAttribute('disabled')).toBe(true);
  });
});
