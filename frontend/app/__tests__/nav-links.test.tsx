import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
}));
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import { usePathname } from 'next/navigation';
import { NavLinks } from '../nav-links';

describe('NavLinks', () => {
  it('zeigt alle 5 Gruppenbezeichnungen', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByText('ENTDECKEN')).toBeInTheDocument();
    expect(screen.getByText('VERSTEHEN')).toBeInTheDocument();
    expect(screen.getByText('VERGLEICHEN')).toBeInTheDocument();
    expect(screen.getByText('ENTSCHEIDEN')).toBeInTheDocument();
    expect(screen.getByText('PORTFOLIO')).toBeInTheDocument();
  });

  it('hebt den aktiven Link hervor und setzt aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings');
    render(<NavLinks />);
    const active = screen.getByRole('link', { name: 'Rankings' });
    expect(active).toHaveAttribute('aria-current', 'page');
    expect(active.className).toContain('text-foreground');
  });

  it('matched verschachtelte Pfade — /rankings/abc aktiviert Rankings', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings/some-run-id');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Rankings' })).toHaveAttribute('aria-current', 'page');
  });

  it('Universen- und Signale-Link sind vorhanden', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Universen' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Signale' })).toBeInTheDocument();
  });

  it('inaktiver Link hat keine aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Aktien' })).not.toHaveAttribute('aria-current');
  });
});
