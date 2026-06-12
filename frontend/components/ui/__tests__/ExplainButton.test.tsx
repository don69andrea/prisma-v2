import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('@/lib/api/chat', () => ({
  streamChat: vi.fn(() => () => {}),
}));

vi.mock('@/components/ui/popover', () => ({
  Popover: ({
    children,
    onOpenChange,
  }: {
    children: React.ReactNode;
    onOpenChange?: (v: boolean) => void;
  }) => <div onClick={() => onOpenChange?.(true)}>{children}</div>,
  PopoverTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PopoverContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { ExplainButton } from '../ExplainButton';

describe('ExplainButton', () => {
  it('rendert den ? Button', () => {
    render(<ExplainButton context="quality_score" />);
    expect(screen.getByRole('button', { name: /erklären/i })).toBeInTheDocument();
  });

  it('ruft streamChat auf wenn geöffnet', async () => {
    const { streamChat } = await import('@/lib/api/chat');
    render(<ExplainButton context="quality_score" />);
    const btn = screen.getByRole('button', { name: /erklären/i });
    fireEvent.click(btn);
    expect(streamChat).toHaveBeenCalled();
  });

  it('custom Label wird angezeigt', () => {
    render(<ExplainButton context="signal" label="ℹ" />);
    expect(screen.getByRole('button')).toHaveTextContent('ℹ');
  });
});
