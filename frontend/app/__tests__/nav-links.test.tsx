import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
}));
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

import { usePathname } from 'next/navigation';
import { NavLinks } from '../nav-links';

describe('NavLinks', () => {
  it('hebt den aktiven Link hervor und setzt aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/universes');
    render(<NavLinks />);

    const activeLink = screen.getByRole('link', { name: 'Universen' });
    expect(activeLink).toHaveAttribute('aria-current', 'page');
    expect(activeLink.className).toContain('text-foreground');

    const inactiveLink = screen.getByRole('link', { name: 'Rankings' });
    expect(inactiveLink).not.toHaveAttribute('aria-current');
    expect(inactiveLink.className).toContain('text-muted-foreground');
  });

  it('matched auch verschachtelte Pfade — /rankings/abc aktiviert Rankings', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings/some-run-id');
    render(<NavLinks />);

    expect(screen.getByRole('link', { name: 'Rankings' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Universen' })).not.toHaveAttribute('aria-current');
  });

  it('Dashboard nur bei exakt /', () => {
    vi.mocked(usePathname).mockReturnValue('/universes');
    render(<NavLinks />);

    expect(screen.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current');
  });
});
