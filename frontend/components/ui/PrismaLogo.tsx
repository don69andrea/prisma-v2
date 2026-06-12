'use client';

interface PrismaLogoProps {
  size?: number;
  className?: string;
  animated?: boolean;
}

/** Geometrisches Prisma-Logo mit Spektralstrahlen. */
export function PrismaLogo({ size = 20, className = '', animated = false }: PrismaLogoProps) {
  const rays = [
    { x1: 22, y1: 11, x2: 35, y2: 3,  color: '#58a6ff', delay: '0s'   },
    { x1: 24, y1: 16, x2: 37, y2: 12, color: '#7ee787', delay: '0.1s' },
    { x1: 26, y1: 21, x2: 38, y2: 21, color: '#f59e0b', delay: '0.2s' },
    { x1: 27, y1: 26, x2: 37, y2: 32, color: '#bc8cff', delay: '0.3s' },
  ];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
      overflow="visible"
    >
      {/* Prisma-Körper mit subtiler Füllung */}
      <path
        d="M16 3L29 27H3L16 3Z"
        fill="currentColor"
        fillOpacity="0.07"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeOpacity="0.85"
      />
      {/* Kristall-Facettenlinie (3D-Schnitt-Effekt) */}
      <line
        x1="16" y1="3" x2="22" y2="27"
        stroke="currentColor"
        strokeWidth="0.6"
        strokeOpacity="0.22"
      />
      {/* Spektralstrahlen — treten aus der rechten Prismafläche aus */}
      {rays.map((ray, i) => (
        <line
          key={i}
          x1={ray.x1} y1={ray.y1}
          x2={ray.x2} y2={ray.y2}
          stroke={ray.color}
          strokeWidth="1.75"
          strokeLinecap="round"
          style={animated ? { animation: `prismaRay${i + 1} 2s ease-in-out infinite`, animationDelay: ray.delay } : undefined}
        />
      ))}
    </svg>
  );
}

/** Vollbild-Ladeanimation mit Prisma-Logo. */
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

      <div style={{ animation: 'prismaSpin 3s linear infinite, prismaGlow 2s ease-in-out infinite' }}>
        <PrismaLogo size={56} className="text-foreground" />
      </div>

      <div className="mt-8 h-[2px] w-40 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{
            background: 'linear-gradient(to right, #8b5cf6, #3b82f6, #10b981, #f59e0b, #ef4444)',
            animation: 'prismaFade 1.8s ease-in-out infinite',
          }}
        />
      </div>

      <p className="mt-5 text-sm text-muted-foreground tracking-wide">
        {label}
        <span style={{ animation: 'prismaDot 1.4s 0.0s infinite' }}>.</span>
        <span style={{ animation: 'prismaDot 1.4s 0.2s infinite' }}>.</span>
        <span style={{ animation: 'prismaDot 1.4s 0.4s infinite' }}>.</span>
      </p>
    </div>
  );
}
