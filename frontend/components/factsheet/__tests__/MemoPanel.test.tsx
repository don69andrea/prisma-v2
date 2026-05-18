import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MemoPanel } from '../MemoPanel';

describe('MemoPanel', () => {
  it('renders placeholder text', () => {
    render(<MemoPanel />);
    expect(screen.getByText(/KI-Memo/)).toBeDefined();
  });

  it('renders placeholder heading', () => {
    render(<MemoPanel />);
    expect(screen.getByText('Research Memo')).toBeDefined();
  });
});
