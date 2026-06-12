import type { Metadata } from 'next';

import Link from 'next/link';

import { Providers } from '@/app/providers';
import { NavLinks } from '@/app/nav-links';
import { ChatDrawer } from '@/components/chat/ChatDrawer';
import { ApiStatusBadge } from '@/components/ui/ApiStatusBadge';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { PrismaLogo } from '@/components/ui/PrismaLogo';
import '@/app/globals.css';

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

const SPECTRUM_GRADIENT = 'linear-gradient(to right, #8b5cf6 0%, #3b82f6 25%, #10b981 50%, #f59e0b 75%, #ef4444 100%)';

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="de" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          <header className="sticky top-0 z-50 bg-background/90 backdrop-blur-md supports-[backdrop-filter]:bg-background/70 border-b border-border/40">
            <div className="container flex flex-col gap-2 py-2 sm:h-14 sm:flex-row sm:items-center sm:gap-0 sm:py-0">
              <Link
                href="/"
                className="flex items-center gap-2 font-bold tracking-tight text-foreground sm:mr-8 group"
              >
                <PrismaLogo size={18} className="text-foreground opacity-90 transition-opacity group-hover:opacity-100" />
                <span className="text-lg font-black uppercase tracking-widest">PRISMA</span>
              </Link>
              <NavLinks />
              <div className="ml-auto flex items-center gap-2 pl-4">
                <ApiStatusBadge />
                <ThemeToggle />
              </div>
            </div>
            {/* PRISMA-Spektrum: zerlegt weisses Licht in 5 quantitative Dimensionen */}
            <div className="relative" aria-hidden="true">
              {/* Glow-Bloom darunter */}
              <div
                className="absolute inset-x-0 top-0 h-[8px] blur-[6px] opacity-60"
                style={{ background: SPECTRUM_GRADIENT }}
              />
              {/* Hauptbalken */}
              <div
                className="relative h-[4px] w-full overflow-hidden spectrum-shimmer"
                style={{ background: SPECTRUM_GRADIENT }}
              />
            </div>
          </header>
          <main className="container py-8">{children}</main>
          <ChatDrawer />
        </Providers>
      </body>
    </html>
  );
}
