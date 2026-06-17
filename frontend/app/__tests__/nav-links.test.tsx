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
vi.mock('@/hooks/usePrismaMode', () => ({
  usePrismaMode: () => ({ mode: 'simple', toggle: vi.fn(), isSimple: true, isPro: false }),
}));
vi.mock('@/app/start/start-client', () => ({
  PROFILE_STORAGE_KEY: 'prisma_profile_type',
}));

import { usePathname } from 'next/navigation';
import { NavLinks } from '../nav-links';

describe('NavLinks', () => {
  it('zeigt alle primären Navigationslinks', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Profil' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Universum' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Rankings' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Signale' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Watchlist' })).toBeInTheDocument();
  });

  it('hebt den aktiven Link hervor und setzt aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings');
    render(<NavLinks />);
    const active = screen.getByRole('link', { name: 'Rankings' });
    expect(active).toHaveAttribute('aria-current', 'page');
  });

  it('matched verschachtelte Pfade — /rankings/abc aktiviert Rankings', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings/some-run-id');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Rankings' })).toHaveAttribute('aria-current', 'page');
  });

  it('Universum- und Signale-Link sind vorhanden', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Universum' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Signale' })).toBeInTheDocument();
  });

  it('inaktiver Link hat keine aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Aktien' })).not.toHaveAttribute('aria-current');
  });

  it('Profil-Link ersetzt den alten Start-Link', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Profil' })).toHaveAttribute('href', '/start');
    expect(screen.queryByRole('link', { name: 'Start' })).not.toBeInTheDocument();
  });
});
