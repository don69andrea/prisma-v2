'use client';

interface PrismaLogoProps {
  size?: number;
  className?: string;
  animated?: boolean;
}

/** Geometrisches Prisma-Logo — Dreieck mit ausfächernden Spektrallinien. */
export function PrismaLogo({ size = 20, className = '', animated = false }: PrismaLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Prisma-Dreieck */}
      <path
        d="M16 3L29 27H3L16 3Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* Innere Achse */}
      <line x1="16" y1="3" x2="16" y2="27" stroke="currentColor" strokeWidth="0.75" strokeOpacity="0.3" />
      {/* Spektrallinien rechts */}
      <line
        x1="26" y1="25" x2="31" y2="17"
        stroke="#58a6ff" strokeWidth="1.5" strokeLinecap="round"
        style={animated ? { animation: 'prismaRay1 2s ease-in-out infinite' } : undefined}
      />
      <line
        x1="27" y1="26" x2="32" y2="22"
        stroke="#7ee787" strokeWidth="1.5" strokeLinecap="round"
        style={animated ? { animation: 'prismaRay2 2s ease-in-out infinite 0.1s' } : undefined}
      />
      <line
        x1="27" y1="27" x2="32" y2="27"
        stroke="#f59e0b" strokeWidth="1.5" strokeLinecap="round"
        style={animated ? { animation: 'prismaRay3 2s ease-in-out infinite 0.2s' } : undefined}
      />
      <line
        x1="26" y1="27" x2="31" y2="31"
        stroke="#bc8cff" strokeWidth="1.5" strokeLinecap="round"
        style={animated ? { animation: 'prismaRay4 2s ease-in-out infinite 0.3s' } : undefined}
      />
    </svg>
  );
}

/** Vollbild-Ladeanimation mit Prisma-Logo — zeigt nach Profil-Reveal. */
export function PrismaLoader({ label = 'Dein Universe wird zusammengestellt' }: { label?: string }) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/95 backdrop-blur-sm">
      <style>{`
        @keyframes prismaSpin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes prismaGlow {
          0%, 100% { filter: drop-shadow(0 0 6px rgba(88,166,255,0.5)); }
          50%       { filter: drop-shadow(0 0 18px rgba(88,166,255,0.9)) drop-shadow(0 0 8px rgba(126,231,135,0.6)); }
        }
        @keyframes prismaFade {
          0%, 100% { opacity: 0.4; transform: scaleX(0.7); }
          50%       { opacity: 1;   transform: scaleX(1); }
        }
        @keyframes prismaDot {
          0%, 80%, 100% { opacity: 0; }
          40%            { opacity: 1; }
        }
      `}</style>

      {/* Animiertes Prisma */}
      <div style={{ animation: 'prismaSpin 3s linear infinite, prismaGlow 2s ease-in-out infinite' }}>
        <PrismaLogo size={56} className="text-foreground" />
      </div>

      {/* Spektrumbalken */}
      <div className="mt-8 h-[2px] w-40 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{
            background: 'linear-gradient(to right, #8b5cf6, #3b82f6, #10b981, #f59e0b, #ef4444)',
            animation: 'prismaFade 1.8s ease-in-out infinite',
          }}
        />
      </div>

      {/* Text */}
      <p className="mt-5 text-sm text-muted-foreground tracking-wide">
        {label}
        <span style={{ animation: 'prismaDot 1.4s 0.0s infinite' }}>.</span>
        <span style={{ animation: 'prismaDot 1.4s 0.2s infinite' }}>.</span>
        <span style={{ animation: 'prismaDot 1.4s 0.4s infinite' }}>.</span>
      </p>
    </div>
  );
}
