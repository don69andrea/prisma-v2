import type { Metadata } from 'next';
import { Inter } from 'next/font/google';

import Link from 'next/link';

import { Providers } from '@/app/providers';
import { NavLinks } from '@/app/nav-links';
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

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="de" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          <header className="sticky top-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex flex-col gap-2 py-2 sm:h-14 sm:flex-row sm:items-center sm:gap-0 sm:py-0">
              <Link
                href="/"
                className="flex items-center gap-2 font-bold tracking-tight text-foreground sm:mr-8"
              >
                <span className="text-lg font-black uppercase tracking-widest">PRISMA</span>
              </Link>
              <NavLinks />
            </div>
            {/* PRISMA-Spektrum: zerlegt weisses Licht in 5 quantitative Dimensionen */}
            <div
              className="h-[3px] w-full"
              style={{
                background:
                  'linear-gradient(to right, #8b5cf6 0%, #3b82f6 25%, #10b981 50%, #f59e0b 75%, #ef4444 100%)',
              }}
              aria-hidden="true"
            />
          </header>
          <main className="container py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
