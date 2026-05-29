import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { MemoEmpty } from '../MemoEmpty';

describe('MemoEmpty', () => {
  it('shows hint and generate button', () => {
    render(<MemoEmpty onGenerate={() => {}} isGenerating={false} />);
    expect(screen.getByText(/Noch kein Memo/)).toBeDefined();
    expect(screen.getByRole('button', { name: /Memo generieren/ })).toBeDefined();
  });

  it('calls onGenerate when button clicked', () => {
    const onGenerate = vi.fn();
    render(<MemoEmpty onGenerate={onGenerate} isGenerating={false} />);
    fireEvent.click(screen.getByRole('button', { name: /Memo generieren/ }));
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it('shows generating state when isGenerating', () => {
    render(<MemoEmpty onGenerate={() => {}} isGenerating={true} />);
    expect(screen.getByText(/Memo wird generiert/)).toBeDefined();
    const btn = screen.getByRole('button');
    expect(btn.hasAttribute('disabled')).toBe(true);
  });
});
