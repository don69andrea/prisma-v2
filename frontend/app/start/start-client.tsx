'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { createDiscoverySession, submitAnswer, completeDiscovery } from '@/lib/api/discovery';
import { LoadingState } from '@/components/ui/LoadingState';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Step = 'landing' | 'beruf' | 'ziel' | 'risiko' | 'brands' | 'reveal';

type Ziel = 'housing' | 'retirement' | 'freedom' | 'beat_savings';
type Risiko = 'conservative' | 'moderate' | 'aggressive';

interface Profile {
  beruf: string;
  ziel: Ziel;
  risiko: Risiko;
  brands: string[];
}

// ---------------------------------------------------------------------------
// Brand data — alle börsenkotierte Schweizer Titel
// ---------------------------------------------------------------------------

interface Brand {
  ticker: string;
  name: string;
  abbr: string;
  category: string;
  fact: string;
  color: string;
}

const BRANDS: Brand[] = [
  // Consumer
  { ticker: 'NESN', name: 'Nestlé', abbr: 'NES', category: 'Konsum', fact: 'Nespresso, KitKat, Maggi — alles Nestlé.', color: '#7ee787' },
  { ticker: 'LISP', name: 'Lindt & Sprüngli', abbr: 'LIN', category: 'Konsum', fact: 'Der bekannteste Schweizer Schokoladenhersteller.', color: '#7ee787' },
  { ticker: 'GIVN', name: 'Givaudan', abbr: 'GIV', category: 'Konsum', fact: 'Aromenhersteller hinter tausenden Parfüms und Lebensmitteln.', color: '#7ee787' },
  { ticker: 'BARN', name: 'Barry Callebaut', abbr: 'BAR', category: 'Konsum', fact: 'Grösster Schokoladenproduzent der Welt (B2B).', color: '#7ee787' },
  // Pharma
  { ticker: 'ROG', name: 'Roche', abbr: 'ROC', category: 'Pharma', fact: 'Weltführer in der Onkologie und Diagnostik.', color: '#58a6ff' },
  { ticker: 'NOVN', name: 'Novartis', abbr: 'NOV', category: 'Pharma', fact: 'Eines der grössten Pharmaunternehmen der Welt.', color: '#58a6ff' },
  { ticker: 'LONN', name: 'Lonza', abbr: 'LON', category: 'Pharma', fact: 'Produziert Wirkstoffe für Biontech, Moderna & Co.', color: '#58a6ff' },
  { ticker: 'STMN', name: 'Straumann', abbr: 'STR', category: 'Pharma', fact: 'Weltmarktführer für Zahnimplantate.', color: '#58a6ff' },
  // Finance
  { ticker: 'UBSG', name: 'UBS', abbr: 'UBS', category: 'Finanzen', fact: 'Grösste Schweizer Bank — nach Credit Suisse-Übernahme noch grösser.', color: '#bc8cff' },
  { ticker: 'PGHN', name: 'Partners Group', abbr: 'PGH', category: 'Finanzen', fact: 'Weltweit führender Private-Equity-Manager.', color: '#bc8cff' },
  { ticker: 'ZURN', name: 'Zurich Insurance', abbr: 'ZUR', category: 'Finanzen', fact: 'Einer der grössten Versicherer weltweit.', color: '#bc8cff' },
  { ticker: 'SLHN', name: 'Swiss Life', abbr: 'SWL', category: 'Finanzen', fact: 'Schweizer Lebensversicherungskonzern seit 1857.', color: '#bc8cff' },
  // Industrie
  { ticker: 'ABBN', name: 'ABB', abbr: 'ABB', category: 'Industrie', fact: 'Elektrifizierung, Robotik und Automatisierung.', color: '#ffa657' },
  { ticker: 'GEBN', name: 'Geberit', abbr: 'GEB', category: 'Industrie', fact: 'Sanitärtechnik — in jedem zweiten Schweizer Bad.', color: '#ffa657' },
  { ticker: 'SCHP', name: 'Schindler', abbr: 'SCH', category: 'Industrie', fact: 'Aufzüge und Rolltreppen in über 100 Ländern.', color: '#ffa657' },
  { ticker: 'KNIN', name: 'Kühne+Nagel', abbr: 'K+N', category: 'Industrie', fact: 'Weltweit grösster Seefracht-Spediteur.', color: '#ffa657' },
  // Tech
  { ticker: 'LOGN', name: 'Logitech', abbr: 'LOG', category: 'Tech', fact: 'Maus, Tastatur, Webcam — in jedem Büro.', color: '#58a6ff' },
  { ticker: 'VACN', name: 'VAT Group', abbr: 'VAT', category: 'Tech', fact: 'Hochvakuum-Ventile für Chipfabriken weltweit.', color: '#58a6ff' },
  { ticker: 'UBXN', name: 'u-blox', abbr: 'UBX', category: 'Tech', fact: 'GPS-Module in Autos, Drohnen und IoT-Geräten.', color: '#58a6ff' },
  { ticker: 'IFCN', name: 'Inficon', abbr: 'IFC', category: 'Tech', fact: 'Messtechnik für Halbleiter- und Kältemittelindustrie.', color: '#58a6ff' },
  // Lifestyle
  { ticker: 'UHR', name: 'Swatch Group', abbr: 'SWT', category: 'Lifestyle', fact: 'Omega, Longines, Breguet — alle gehören Swatch.', color: '#f85149' },
  { ticker: 'CFR', name: 'Richemont', abbr: 'RIC', category: 'Lifestyle', fact: 'Cartier, IWC, Vacheron — Luxus-Konzern aus Genf.', color: '#f85149' },
  { ticker: 'FHZN', name: 'Flughafen Zürich', abbr: 'FHZ', category: 'Lifestyle', fact: 'Betreibt ZRH — profitabelster Flughafen Europas.', color: '#f85149' },
  { ticker: 'SCMN', name: 'Swisscom', abbr: 'SCM', category: 'Lifestyle', fact: 'Grösster Telekomkonzern der Schweiz.', color: '#f85149' },
];

const ZIEL_OPTIONS: { value: Ziel; label: string; sub: string }[] = [
  { value: 'housing', label: 'Neue Wohnung', sub: 'Ich spare auf etwas Konkretes hin.' },
  { value: 'retirement', label: 'Altersvorsorge', sub: 'Ich denke langfristig.' },
  { value: 'freedom', label: 'Finanzielle Freiheit', sub: 'Ich will unabhängiger werden.' },
  { value: 'beat_savings', label: 'Besser als Sparkonto', sub: 'Das Geld soll mehr arbeiten.' },
];

const RISIKO_OPTIONS: { value: Risiko; label: string; emoji: string; sub: string }[] = [
  { value: 'conservative', emoji: '😱', label: 'Fehler gemacht. Alles raus.', sub: 'Sicherheit ist mir wichtiger als Rendite.' },
  { value: 'moderate', emoji: '😐', label: 'Das ist normal. Ich warte.', sub: 'Kurzfristige Schwankungen akzeptiere ich.' },
  { value: 'aggressive', emoji: '😎', label: 'Jetzt kaufe ich mehr.', sub: 'Krisen sind Kaufgelegenheiten.' },
];

const PROFILE_LABELS: Record<Risiko, string> = {
  conservative: 'Stabiler Qualitätsinvestor',
  moderate: 'Ausgewogener Wachstumsinvestor',
  aggressive: 'Chancenorientierter Investor',
};

const ZIEL_HORIZON: Record<Ziel, string> = {
  housing: '2–5 Jahre',
  retirement: '10+ Jahre',
  freedom: '5–10 Jahre',
  beat_savings: 'Flexibel',
};

// ---------------------------------------------------------------------------
// Down-chart SVG (Risk-Feeling-Test)
// ---------------------------------------------------------------------------

function DownChart() {
  return (
    <svg
      viewBox="0 0 300 120"
      className="w-full max-w-sm mx-auto"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="redGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f85149" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#f85149" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Grid lines */}
      {[20, 60, 100].map((y) => (
        <line key={y} x1="0" y1={y} x2="300" y2={y} stroke="currentColor" strokeOpacity="0.1" strokeWidth="1" />
      ))}
      {/* Area fill */}
      <path
        d="M 0,20 C 30,22 60,25 90,35 C 120,45 130,50 160,65 C 190,80 220,90 260,105 L 260,120 L 0,120 Z"
        fill="url(#redGrad)"
      />
      {/* Line */}
      <path
        d="M 0,20 C 30,22 60,25 90,35 C 120,45 130,50 160,65 C 190,80 220,90 260,105"
        fill="none"
        stroke="#f85149"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Start dot */}
      <circle cx="0" cy="20" r="4" fill="#f85149" />
      {/* End dot */}
      <circle cx="260" cy="105" r="4" fill="#f85149" />
      {/* –25% label */}
      <text x="265" y="108" fill="#f85149" fontSize="12" fontWeight="bold">–25%</text>
      {/* Time labels */}
      <text x="0" y="118" fill="currentColor" fontSize="10" opacity="0.4">Jan</text>
      <text x="115" y="118" fill="currentColor" fontSize="10" opacity="0.4">Feb</text>
      <text x="230" y="118" fill="currentColor" fontSize="10" opacity="0.4">März</text>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Step components
// ---------------------------------------------------------------------------

function StepLanding({ onEntdecker, onKenner }: { onEntdecker: () => void; onKenner: () => void }) {
  return (
    <div className="flex flex-col items-center gap-8 py-8 animate-in fade-in duration-500">
      <div className="text-center space-y-3">
        <div className="text-4xl font-black tracking-widest text-foreground">PRISMA</div>
        <p className="text-muted-foreground max-w-md">
          Dein persönlicher Investment-Companion. Wir helfen dir herauszufinden,
          was zu dir passt — ohne Fachjargon, ohne Druck.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 w-full max-w-lg">
        <button
          onClick={onEntdecker}
          className="group flex-1 rounded-xl border border-border bg-card p-6 text-left transition-all hover:border-primary hover:shadow-lg hover:shadow-primary/10 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <div className="text-2xl mb-3">🧭</div>
          <div className="font-semibold text-foreground">Ich weiss noch nicht, wo ich anfangen soll.</div>
          <div className="text-sm text-muted-foreground mt-1">Zeig mir den Weg.</div>
          <div className="mt-4 text-xs text-primary group-hover:translate-x-1 transition-transform inline-block">
            Geführte Entdeckung →
          </div>
        </button>

        <button
          onClick={onKenner}
          className="group flex-1 rounded-xl border border-border bg-card p-6 text-left transition-all hover:border-primary hover:shadow-lg hover:shadow-primary/10 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <div className="text-2xl mb-3">🎯</div>
          <div className="font-semibold text-foreground">Ich weiss, was ich suche.</div>
          <div className="text-sm text-muted-foreground mt-1">Direkt zu den Titeln.</div>
          <div className="mt-4 text-xs text-primary group-hover:translate-x-1 transition-transform inline-block">
            Direkt zur Suche →
          </div>
        </button>
      </div>
    </div>
  );
}

function StepBeruf({ onNext }: { onNext: (beruf: string) => void }) {
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col items-center gap-6 py-8 animate-in fade-in duration-500 max-w-lg mx-auto">
      <StepIndicator current={1} total={4} />
      <div className="text-center space-y-2">
        <div className="text-sm text-muted-foreground">PRISMA fragt</div>
        <h2 className="text-xl font-semibold">Was machst du beruflich?</h2>
        <p className="text-sm text-muted-foreground">
          Keine richtige oder falsche Antwort — ich will nur verstehen, wie du denkst.
        </p>
      </div>
      <div className="w-full space-y-3">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && value.trim() && onNext(value.trim())}
          placeholder="z.B. Softwareentwickler, Lehrerin, Arzt..."
          className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary transition-all"
        />
        <button
          onClick={() => value.trim() && onNext(value.trim())}
          disabled={!value.trim()}
          className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Weiter
        </button>
      </div>
    </div>
  );
}

function StepZiel({ onNext }: { onNext: (ziel: Ziel) => void }) {
  const [selected, setSelected] = useState<Ziel | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 py-8 animate-in fade-in duration-500 max-w-lg mx-auto">
      <StepIndicator current={2} total={4} />
      <div className="text-center space-y-2">
        <div className="text-sm text-muted-foreground">PRISMA fragt</div>
        <h2 className="text-xl font-semibold">Wofür ist das Geld irgendwann gedacht?</h2>
        <p className="text-sm text-muted-foreground">
          Kein falsches oder richtiges Ziel — ich will nur verstehen.
        </p>
      </div>
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3">
        {ZIEL_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setSelected(opt.value)}
            className={`rounded-xl border p-4 text-left transition-all focus:outline-none focus:ring-2 focus:ring-primary ${
              selected === opt.value
                ? 'border-primary bg-primary/10 text-foreground'
                : 'border-border bg-card text-foreground hover:border-primary/50'
            }`}
          >
            <div className="font-medium text-sm">{opt.label}</div>
            <div className="text-xs text-muted-foreground mt-1">{opt.sub}</div>
          </button>
        ))}
      </div>
      <button
        onClick={() => selected && onNext(selected)}
        disabled={!selected}
        className="w-full max-w-sm rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Weiter
      </button>
    </div>
  );
}

function StepRisiko({ onNext }: { onNext: (risiko: Risiko) => void }) {
  const [selected, setSelected] = useState<Risiko | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 py-8 animate-in fade-in duration-500 max-w-lg mx-auto">
      <StepIndicator current={3} total={4} />
      <div className="text-center space-y-2">
        <div className="text-sm text-muted-foreground">PRISMA fragt</div>
        <h2 className="text-xl font-semibold">Stell dir vor: Du siehst das auf deinem Konto.</h2>
        <p className="text-sm text-muted-foreground">
          Du hast CHF 10&apos;000 investiert. Nach 3 Monaten öffnest du die App.
        </p>
      </div>

      <div className="w-full rounded-xl border border-border bg-card p-4">
        <div className="text-xs text-muted-foreground mb-3">Dein Portfolio — letzte 3 Monate</div>
        <DownChart />
      </div>

      <div className="text-center text-sm font-medium">Was denkst du zuerst?</div>

      <div className="w-full space-y-2">
        {RISIKO_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setSelected(opt.value)}
            className={`w-full rounded-xl border p-4 text-left transition-all focus:outline-none focus:ring-2 focus:ring-primary ${
              selected === opt.value
                ? 'border-primary bg-primary/10'
                : 'border-border bg-card hover:border-primary/50'
            }`}
          >
            <div className="flex items-start gap-3">
              <span className="text-xl shrink-0">{opt.emoji}</span>
              <div>
                <div className="font-medium text-sm">{opt.label}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{opt.sub}</div>
              </div>
            </div>
          </button>
        ))}
      </div>

      <button
        onClick={() => selected && onNext(selected)}
        disabled={!selected}
        className="w-full max-w-sm rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Weiter
      </button>
    </div>
  );
}

function StepBrands({ onNext }: { onNext: (brands: string[]) => void }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  function toggle(ticker: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  }

  const categories = Array.from(new Set(BRANDS.map((b) => b.category)));

  return (
    <div className="flex flex-col items-center gap-6 py-8 animate-in fade-in duration-500 max-w-2xl mx-auto">
      <StepIndicator current={4} total={4} />
      <div className="text-center space-y-2">
        <div className="text-sm text-muted-foreground">PRISMA fragt</div>
        <h2 className="text-xl font-semibold">Welche dieser Schweizer Firmen kennst du?</h2>
        <p className="text-sm text-muted-foreground">
          Aus dem Alltag, der Arbeit, den Nachrichten. Einfach anklicken.
        </p>
      </div>

      <div className="w-full space-y-4">
        {categories.map((cat) => (
          <div key={cat}>
            <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">{cat}</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {BRANDS.filter((b) => b.category === cat).map((brand) => {
                const isSelected = selected.has(brand.ticker);
                return (
                  <button
                    key={brand.ticker}
                    onClick={() => toggle(brand.ticker)}
                    title={brand.fact}
                    className={`relative rounded-lg border p-3 text-center transition-all focus:outline-none focus:ring-2 focus:ring-primary group ${
                      isSelected
                        ? 'border-primary bg-primary/10 shadow-sm shadow-primary/20'
                        : 'border-border bg-card hover:border-primary/50'
                    }`}
                  >
                    <div
                      className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold mx-auto mb-1"
                      style={{ backgroundColor: brand.color + '22', color: brand.color }}
                    >
                      {brand.abbr}
                    </div>
                    <div className="text-xs font-medium truncate">{brand.name}</div>
                    <div className="text-[10px] text-muted-foreground">{brand.ticker}.SW</div>
                    {isSelected && (
                      <div className="absolute top-1.5 right-1.5 w-3 h-3 rounded-full bg-primary flex items-center justify-center">
                        <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                          <path d="M1.5 4L3 5.5L6.5 2" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {selected.size > 0 && (
        <div className="text-sm text-muted-foreground">
          Du kennst bereits{' '}
          <span className="font-semibold text-foreground">{selected.size}</span>{' '}
          investierbare Schweizer Firmen. Das ist dein Ausgangspunkt.
        </div>
      )}

      <button
        onClick={() => onNext(Array.from(selected))}
        className="w-full max-w-sm rounded-lg bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-all hover:opacity-90"
      >
        {selected.size > 0 ? 'Profil fertigstellen →' : 'Überspringen'}
      </button>
    </div>
  );
}

function StepReveal({ profile, onContinue }: { profile: Profile; onContinue: () => void }) {
  const risikoLabel = PROFILE_LABELS[profile.risiko];
  const horizon = ZIEL_HORIZON[profile.ziel];
  const knownBrands = BRANDS.filter((b) => profile.brands.includes(b.ticker));

  // Derive sector affinities from selected brands
  const sectorCounts: Record<string, number> = {};
  BRANDS.filter((b) => profile.brands.includes(b.ticker)).forEach((b) => {
    sectorCounts[b.category] = (sectorCounts[b.category] ?? 0) + 1;
  });
  const topSectors = Object.entries(sectorCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([cat]) => cat);

  return (
    <div className="flex flex-col items-center gap-6 py-8 animate-in fade-in duration-700 max-w-lg mx-auto">
      {/* Prisma crystal — CSS only */}
      <div className="relative w-16 h-16 flex items-center justify-center">
        <div
          className="w-10 h-10 rotate-45 rounded-sm animate-pulse"
          style={{
            background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 50%, #bc8cff 100%)',
            boxShadow: '0 0 30px rgba(88,166,255,0.4)',
          }}
        />
      </div>

      <div className="text-center space-y-1">
        <div className="text-xs text-muted-foreground tracking-widest uppercase">PRISMA hat dein Investorprofil erstellt</div>
        <h2 className="text-2xl font-bold">Dein Profil</h2>
      </div>

      <div className="w-full rounded-xl border border-border bg-card p-5 space-y-4">
        <ProfileRow label="Typ" value={risikoLabel} />
        <ProfileRow label="Zeithorizont" value={horizon} />
        <ProfileRow
          label="Risikoprofil"
          value={
            profile.risiko === 'conservative'
              ? 'Konservativ — Stabilität vor Rendite'
              : profile.risiko === 'moderate'
              ? 'Moderat — du wartest bei –20%'
              : 'Chancenorientiert — Krisen nutzen'
          }
        />
        {topSectors.length > 0 && (
          <ProfileRow label="Affinität" value={topSectors.join(' + ')} />
        )}

        {knownBrands.length > 0 && (
          <div>
            <div className="text-xs text-muted-foreground mb-2">Du kennst bereits</div>
            <div className="flex flex-wrap gap-1.5">
              {knownBrands.map((b) => (
                <span
                  key={b.ticker}
                  className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium"
                  style={{ backgroundColor: b.color + '22', color: b.color }}
                >
                  {b.name}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-border pt-4">
          <div className="text-xs text-muted-foreground">
            PRISMA hat Schweizer Titel für dein Profil ausgewählt.
          </div>
        </div>
      </div>

      <button
        onClick={onContinue}
        className="w-full rounded-lg px-4 py-3 text-sm font-semibold text-white transition-all hover:opacity-90 hover:shadow-lg hover:scale-[1.01] active:scale-[0.99]"
        style={{
          background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)',
          boxShadow: '0 4px 20px rgba(88,166,255,0.3)',
        }}
      >
        Zeig mir mein personalisiertes Dashboard →
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Kenner: fast-lane search
// ---------------------------------------------------------------------------

const QUICK_FILTERS = [
  { label: 'SMI-20', tickers: ['NESN', 'ROG', 'NOVN', 'ABBN', 'UBSG'] },
  { label: 'Pharma', tickers: ['ROG', 'NOVN', 'LONN', 'STMN'] },
  { label: 'Tech', tickers: ['LOGN', 'VACN', 'UBXN', 'IFCN'] },
  { label: 'Dividenden', tickers: ['SCMN', 'ZURN', 'SLHN', 'NESN'] },
  { label: 'Industrie', tickers: ['ABBN', 'GEBN', 'KNIN', 'SCHP'] },
];

function KennerSearch({ onBack }: { onBack: () => void }) {
  const [query, setQuery] = useState('');
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const suggestions = query.length >= 1
    ? BRANDS.filter(
        (b) =>
          b.name.toLowerCase().includes(query.toLowerCase()) ||
          b.ticker.toLowerCase().includes(query.toLowerCase()),
      ).slice(0, 5)
    : [];

  function goToStock(ticker: string) {
    router.push(`/stocks/${ticker}`);
  }

  return (
    <div className="flex flex-col items-center gap-6 py-8 animate-in fade-in duration-500 max-w-lg mx-auto">
      <button
        onClick={onBack}
        className="self-start text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        ← Zurück
      </button>

      <div className="text-center space-y-1">
        <h2 className="text-xl font-semibold">Direkt zur Analyse</h2>
        <p className="text-sm text-muted-foreground">Suche nach Firma, Ticker oder Sektor.</p>
      </div>

      <div className="w-full relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Nestlé, NESN, Pharma..."
          className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary transition-all"
        />
        {suggestions.length > 0 && (
          <div className="absolute top-full mt-1 w-full rounded-lg border border-border bg-card shadow-lg z-10 overflow-hidden">
            {suggestions.map((b) => (
              <button
                key={b.ticker}
                onClick={() => goToStock(b.ticker)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-accent transition-colors text-sm"
              >
                <span
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                  style={{ backgroundColor: b.color + '22', color: b.color }}
                >
                  {b.abbr}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{b.name}</div>
                  <div className="text-xs text-muted-foreground">{b.ticker}.SW · {b.category}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="w-full space-y-2">
        <div className="text-xs text-muted-foreground">Schnellfilter</div>
        <div className="flex flex-wrap gap-2">
          {QUICK_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => goToStock(f.tickers[0])}
              className="rounded-full border border-border bg-card px-3 py-1.5 text-xs hover:border-primary hover:text-primary transition-colors"
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StepIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          className={`h-1.5 rounded-full transition-all duration-300 ${
            i < current ? 'bg-primary w-6' : i === current - 1 ? 'bg-primary w-6' : 'bg-border w-4'
          }`}
        />
      ))}
      <span className="ml-2 text-xs text-muted-foreground">{current} / {total}</span>
    </div>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className="text-sm font-medium text-right">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function StartClient() {
  const [step, setStep] = useState<Step>('landing');
  const [beruf, setBeruf] = useState('');
  const [ziel, setZiel] = useState<Ziel | null>(null);
  const [risiko, setRisiko] = useState<Risiko | null>(null);
  const [brands, setBrands] = useState<string[]>([]);
  const [kennerMode, setKennerMode] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  async function handleEntdecker() {
    setKennerMode(false);
    setIsLoading(true);
    try {
      const session = await createDiscoverySession();
      setSessionId(session.session_id);
    } catch {
      // Proceed without session — fallback to local-only flow
    } finally {
      setIsLoading(false);
    }
    setStep('beruf');
  }

  function handleKenner() {
    setKennerMode(true);
  }

  async function handleBeruf(value: string) {
    setBeruf(value);
    if (sessionId) {
      try {
        await submitAnswer(sessionId, 1, value);
      } catch {
        // Non-blocking — continue local flow
      }
    }
    setStep('ziel');
  }

  async function handleZiel(value: Ziel) {
    setZiel(value);
    if (sessionId) {
      try {
        await submitAnswer(sessionId, 2, value);
      } catch {
        // Non-blocking — continue local flow
      }
    }
    setStep('risiko');
  }

  async function handleRisiko(value: Risiko) {
    setRisiko(value);
    if (sessionId) {
      try {
        await submitAnswer(sessionId, 3, value);
      } catch {
        // Non-blocking — continue local flow
      }
    }
    setStep('brands');
  }

  async function handleBrands(value: string[]) {
    setBrands(value);
    if (sessionId) {
      setIsLoading(true);
      try {
        await submitAnswer(sessionId, 4, value);
        await completeDiscovery(sessionId);
        localStorage.setItem('prisma_session_id', sessionId);
        router.push('/stocks');
        return;
      } catch {
        // Fallback to local reveal view on error
      } finally {
        setIsLoading(false);
      }
    }
    setStep('reveal');
  }

  function handleContinue() {
    router.push('/stocks');
  }

  if (kennerMode) {
    return (
      <div className="min-h-[60vh]">
        <KennerSearch onBack={() => setKennerMode(false)} />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingState type="discover" />
      </div>
    );
  }

  return (
    <div className="min-h-[60vh]">
      {step === 'landing' && (
        <StepLanding onEntdecker={handleEntdecker} onKenner={handleKenner} />
      )}
      {step === 'beruf' && <StepBeruf onNext={handleBeruf} />}
      {step === 'ziel' && <StepZiel onNext={handleZiel} />}
      {step === 'risiko' && <StepRisiko onNext={handleRisiko} />}
      {step === 'brands' && <StepBrands onNext={handleBrands} />}
      {step === 'reveal' && ziel && risiko && (
        <StepReveal
          profile={{ beruf, ziel, risiko, brands }}
          onContinue={handleContinue}
        />
      )}
    </div>
  );
}
