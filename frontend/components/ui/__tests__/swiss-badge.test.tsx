import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SwissBadge } from '../swiss-badge';

describe('SwissBadge', () => {
  it('renders for XSWX exchange', () => {
    render(<SwissBadge exchange="XSWX" />);
    expect(screen.getByText(/XSWX/)).toBeInTheDocument();
  });

  it('renders nothing for non-XSWX exchange', () => {
    const { container } = render(<SwissBadge exchange="XNAS" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing for null exchange', () => {
    const { container } = render(<SwissBadge exchange={null} />);
    expect(container.firstChild).toBeNull();
  });
});
