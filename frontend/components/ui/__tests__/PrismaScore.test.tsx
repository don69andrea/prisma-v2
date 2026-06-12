import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PrismaScore } from '../PrismaScore';

describe('PrismaScore', () => {
  it('rendert Label und Score', () => {
    render(<PrismaScore label="Quality" score={82} />);
    expect(screen.getByText('Quality')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
  });

  it('progressbar hat aria-valuenow', () => {
    render(<PrismaScore label="Trend" score={61} />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '61');
  });

  it('? Button ruft onExplain auf', () => {
    const onExplain = vi.fn();
    render(<PrismaScore label="Value" score={34} showExplain onExplain={onExplain} />);
    fireEvent.click(screen.getByRole('button', { name: /erklären/i }));
    expect(onExplain).toHaveBeenCalledOnce();
  });

  it('klemmt Score bei 0', () => {
    render(<PrismaScore label="X" score={-5} />);
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('klemmt Score bei 100', () => {
    render(<PrismaScore label="X" score={150} />);
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('kein Explain-Button wenn showExplain nicht gesetzt', () => {
    render(<PrismaScore label="Quality" score={70} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
