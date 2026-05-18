import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Link from 'next/link';

import { Providers } from '@/app/providers';
import { ROUTES } from '@/lib/routes';
import '@/app/globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'PRISMA',
    template: '%s | PRISMA',
  },
  description:
    'Quantitative Stock-Selection — analytische Dimensionen fur institutionelle Aktienauswahl.',
};

const navLinks = [
  { href: ROUTES.dashboard, label: 'Dashboard' },
  { href: ROUTES.universes, label: 'Universen' },
  { href: ROUTES.rankings,  label: 'Rankings' },
  { href: ROUTES.backtest,  label: 'Backtest' },
] as const;

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="de" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-14 items-center">
              <Link
                href="/"
                className="mr-8 flex items-center gap-2 font-bold tracking-tight text-foreground"
              >
                <span className="text-lg font-black uppercase tracking-widest">PRISMA</span>
              </Link>
              <nav className="flex items-center gap-6 text-sm">
                {navLinks.map((link) => (
                  <Link
                    key={`${link.href}-${link.label}`}
                    href={link.href}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>
          <main className="container py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
