import { render, screen } from '@testing-library/react';
import { CryptoSignalBadge } from '../CryptoSignalBadge';

describe('CryptoSignalBadge', () => {
  it('renders BUY badge', () => {
    render(<CryptoSignalBadge action="BUY" confidence={0.8} />);
    expect(screen.getByText('BUY')).toBeDefined();
    expect(screen.getByText('80%')).toBeDefined();
  });
  it('renders SELL badge', () => {
    render(<CryptoSignalBadge action="SELL" confidence={0.3} />);
    expect(screen.getByText('SELL')).toBeDefined();
  });
  it('renders HOLD badge', () => {
    render(<CryptoSignalBadge action="HOLD" confidence={0.55} />);
    expect(screen.getByText('HOLD')).toBeDefined();
    expect(screen.getByText('55%')).toBeDefined();
  });
});
