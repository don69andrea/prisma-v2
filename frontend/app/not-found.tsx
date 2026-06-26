import Link from 'next/link';
import { PrismaLogo } from '@/components/ui/PrismaLogo';

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center">
      <PrismaLogo size={48} className="text-foreground/30" />
      <div className="space-y-2">
        <h1 className="text-6xl font-black tracking-tighter text-foreground/20">404</h1>
        <p className="text-lg font-semibold text-foreground">Seite nicht gefunden</p>
        <p className="text-sm text-muted-foreground max-w-sm">
          Diese Seite existiert nicht oder wurde verschoben.
        </p>
      </div>
      <Link
        href="/"
        className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
      >
        Zurück zum Dashboard
      </Link>
    </div>
  );
}
