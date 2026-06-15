'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { completeDiscovery, createDiscoverySession, submitAnswer } from '@/lib/api/discovery';
import { PrismaLoader } from '@/components/ui/PrismaLogo';
import { InfoPopover } from '@/components/InfoPopover';
import { Compass } from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Step = 'landing' | 'beruf' | 'ziel' | 'risiko' | 'brands' | 'betrag' | 'nachhaltigkeit' | 'ertrag' | 'reveal' | 'profile-reveal';
type Betrag = 'under_10k' | '10k_100k' | 'over_100k';
type Nachhaltigkeit = 'yes' | 'no' | 'indifferent';
type Ertrag = 'dividends' | 'balanced' | 'growth';

type Ziel = 'housing' | 'retirement' | 'freedom' | 'beat_savings';
type Risiko = 'conservative' | 'moderate' | 'aggressive';

interface Profile {
  beruf: string;
  ziel: Ziel;
  risiko: Risiko;
  brands: string[];
  betrag: Betrag;
  nachhaltigkeit: Nachhaltigkeit;
  ertrag: Ertrag;
}

// ---------------------------------------------------------------------------
// Brand data — alle börsenkotierten Schweizer Titel
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
  { ticker: 'LISN', name: 'Lindt & Sprüngli', abbr: 'LIN', category: 'Konsum', fact: 'Der bekannteste Schweizer Schokoladenhersteller.', color: '#7ee787' },
  { ticker: 'GIVN', name: 'Givaudan', abbr: 'GIV', category: 'Konsum', fact: 'Aromenhersteller hinter tausenden Parfüms und Lebensmitteln.', color: '#7ee787' },
  { ticker: 'BARN', name: 'Barry Callebaut', abbr: 'BAR', category: 'Konsum', fact: 'Grösster Schokoladenproduzent der Welt (B2B).', color: '#7ee787' },
  // Pharma
  { ticker: 'ROG',  name: 'Roche',      abbr: 'ROC', category: 'Pharma',   fact: 'Weltführer in der Onkologie und Diagnostik.', color: '#58a6ff' },
  { ticker: 'NOVN', name: 'Novartis',   abbr: 'NOV', category: 'Pharma',   fact: 'Eines der grössten Pharmaunternehmen der Welt.', color: '#58a6ff' },
  { ticker: 'LONN', name: 'Lonza',      abbr: 'LON', category: 'Pharma',   fact: 'Produziert Wirkstoffe für BioNTech, Moderna & Co.', color: '#58a6ff' },
  { ticker: 'STMN', name: 'Straumann',  abbr: 'STR', category: 'Pharma',   fact: 'Weltmarktführer für Zahnimplantate.', color: '#58a6ff' },
  // Finance
  { ticker: 'UBSG', name: 'UBS',             abbr: 'UBS', category: 'Finanzen', fact: 'Grösste Schweizer Bank — nach CS-Übernahme noch grösser.', color: '#bc8cff' },
  { ticker: 'PGHN', name: 'Partners Group',  abbr: 'PGH', category: 'Finanzen', fact: 'Weltweit führender Private-Equity-Manager.', color: '#bc8cff' },
  { ticker: 'ZURN', name: 'Zurich Insurance',abbr: 'ZUR', category: 'Finanzen', fact: 'Einer der grössten Versicherer weltweit.', color: '#bc8cff' },
  { ticker: 'SLHN', name: 'Swiss Life',      abbr: 'SWL', category: 'Finanzen', fact: 'Schweizer Lebensversicherungskonzern seit 1857.', color: '#bc8cff' },
  // Industrie
  { ticker: 'ABBN', name: 'ABB',          abbr: 'ABB', category: 'Industrie', fact: 'Elektrifizierung, Robotik und Automatisierung.', color: '#ffa657' },
  { ticker: 'GEBN', name: 'Geberit',      abbr: 'GEB', category: 'Industrie', fact: 'Sanitärtechnik — in jedem zweiten Schweizer Bad.', color: '#ffa657' },
  { ticker: 'SCHP', name: 'Schindler',    abbr: 'SCH', category: 'Industrie', fact: 'Aufzüge und Rolltreppen in über 100 Ländern.', color: '#ffa657' },
  { ticker: 'KNIN', name: 'Kühne+Nagel', abbr: 'K+N', category: 'Industrie', fact: 'Weltweit grösster Seefracht-Spediteur.', color: '#ffa657' },
  // Tech
  { ticker: 'LOGN', name: 'Logitech', abbr: 'LOG', category: 'Tech', fact: 'Maus, Tastatur, Webcam — in jedem Büro.', color: '#58a6ff' },
  { ticker: 'VACN', name: 'VAT Group', abbr: 'VAT', category: 'Tech', fact: 'Hochvakuum-Ventile für Chipfabriken weltweit.', color: '#58a6ff' },
  { ticker: 'UBXN', name: 'u-blox',    abbr: 'UBX', category: 'Tech', fact: 'GPS-Module in Autos, Drohnen und IoT-Geräten.', color: '#58a6ff' },
  { ticker: 'IFCN', name: 'Inficon',   abbr: 'IFC', category: 'Tech', fact: 'Messtechnik für Halbleiter- und Kältemittelindustrie.', color: '#58a6ff' },
  // Lifestyle
  { ticker: 'UHR',  name: 'Swatch Group',     abbr: 'SWT', category: 'Lifestyle', fact: 'Omega, Longines, Breguet — alle gehören Swatch.', color: '#f85149' },
  { ticker: 'CFR',  name: 'Richemont',        abbr: 'RIC', category: 'Lifestyle', fact: 'Cartier, IWC, Vacheron — Luxus-Konzern aus Genf.', color: '#f85149' },
  { ticker: 'FHZN', name: 'Flughafen Zürich', abbr: 'FHZ', category: 'Lifestyle', fact: 'Betreibt ZRH — profitabelster Flughafen Europas.', color: '#f85149' },
  { ticker: 'SCMN', name: 'Swisscom',         abbr: 'SCM', category: 'Lifestyle', fact: 'Grösster Telekomkonzern der Schweiz.', color: '#f85149' },
];

const ZIEL_OPTIONS: { value: Ziel; label: string; sub: string }[] = [
  { value: 'housing',      label: 'Neue Wohnung',          sub: 'Ich spare auf etwas Konkretes hin.' },
  { value: 'retirement',   label: 'Altersvorsorge',         sub: 'Ich denke langfristig.' },
  { value: 'freedom',      label: 'Finanzielle Freiheit',   sub: 'Ich will unabhängiger werden.' },
  { value: 'beat_savings', label: 'Besser als Sparkonto',   sub: 'Das Geld soll mehr arbeiten.' },
];

const BETRAG_OPTIONS: { value: Betrag; label: string; sub: string }[] = [
  { value: 'under_10k',  label: 'Einsteiger',  sub: "< CHF 10'000 — Ideal zum Starten ohne grosses Risiko" },
  { value: '10k_100k',   label: 'Wachstum',    sub: "CHF 10'000 – 100'000 — Echtes Depot aufbauen" },
  { value: 'over_100k',  label: 'Investor',    sub: "> CHF 100'000 — Professionelle Portfoliooptimierung" },
];

const NACHHALTIGKEIT_OPTIONS: { value: Nachhaltigkeit; label: string; sub: string }[] = [
  { value: 'yes',         label: 'Nachhaltigkeit ist wichtig', sub: 'Ich bevorzuge ESG-konforme Unternehmen' },
  { value: 'no',          label: 'Rendite geht vor',           sub: 'Performance ist mein primäres Ziel' },
  { value: 'indifferent', label: 'Spielt keine Rolle',         sub: 'Ich möchte alle Möglichkeiten sehen' },
];

const ERTRAG_OPTIONS: { value: Ertrag; label: string; sub: string }[] = [
  { value: 'dividends', label: 'Dividenden', sub: 'Ich möchte regelmässige Ausschüttungen erhalten' },
  { value: 'balanced',  label: 'Ausgewogen', sub: 'Mix aus Ausschüttungen und Kursgewinnen' },
  { value: 'growth',    label: 'Wachstum',   sub: 'Ich setze auf langfristige Kurssteigerungen' },
];

/** SVG-Gesichtsicons als Emoji-Ersatz für Risiko-Buttons. */
function FaceScared({ color }: { color: string }) {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M8 15c1-2 6-2 8 0" />
      <circle cx="9" cy="10" r="1.2" fill={color} stroke="none" />
      <circle cx="15" cy="10" r="1.2" fill={color} stroke="none" />
      <path d="M9 8l-1.5-1.5M15 8l1.5-1.5" strokeWidth="1" />
    </svg>
  );
}

function FaceNeutral({ color }: { color: string }) {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="9" y1="15" x2="15" y2="15" />
      <circle cx="9" cy="10" r="1.2" fill={color} stroke="none" />
      <circle cx="15" cy="10" r="1.2" fill={color} stroke="none" />
    </svg>
  );
}

function FaceConfident({ color }: { color: string }) {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M8 13c1 2.5 6 2.5 8 0" />
      {/* Sonnenbrillengläser */}
      <rect x="7" y="8.5" width="4" height="2.5" rx="1.2" fill={color} opacity="0.7" stroke="none"/>
      <rect x="13" y="8.5" width="4" height="2.5" rx="1.2" fill={color} opacity="0.7" stroke="none"/>
      <line x1="11" y1="9.75" x2="13" y2="9.75" strokeWidth="1" />
    </svg>
  );
}

const RISIKO_OPTIONS: {
  value: Risiko;
  label: string;
  sub: string;
  color: string;
  bg: string;
  icon: (color: string) => React.ReactNode;
}[] = [
  { value: 'conservative', label: 'Fehler gemacht. Alles raus.',  sub: 'Sicherheit ist mir wichtiger als Rendite.',   color: '#f85149', bg: '#2d0d0d', icon: (c) => <FaceScared color={c} /> },
  { value: 'moderate',     label: 'Das ist normal. Ich warte.',   sub: 'Kurzfristige Schwankungen akzeptiere ich.',  color: '#ffa657', bg: '#2d1a0d', icon: (c) => <FaceNeutral color={c} /> },
  { value: 'aggressive',   label: 'Jetzt kaufe ich mehr.',         sub: 'Krisen sind Kaufgelegenheiten.',             color: '#7ee787', bg: '#0d2d1a', icon: (c) => <FaceConfident color={c} /> },
];

const PROFILE_LABELS: Record<Risiko, string> = {
  conservative: 'Stabiler Qualitätsinvestor',
  moderate:     'Ausgewogener Wachstumsinvestor',
  aggressive:   'Chancenorientierter Investor',
};

const ZIEL_HORIZON: Record<Ziel, string> = {
  housing:      '2–5 Jahre',
  retirement:   '10+ Jahre',
  freedom:      '5–10 Jahre',
  beat_savings: 'Flexibel',
};

const ZIEL_TO_HORIZON: Record<Ziel, 'short' | 'medium' | 'long'> = {
  housing:      'short',
  retirement:   'long',
  freedom:      'medium',
  beat_savings: 'medium',
};

const CATEGORY_TO_SECTOR: Record<string, string> = {
  Konsum:    'consumer',
  Pharma:    'pharma',
  Finanzen:  'finance',
  Industrie: 'industrial',
  Tech:      'tech',
  Lifestyle: 'luxury',
};

export const DISCOVER_STORAGE_KEY = 'prisma_discover_result';
export const PROFILE_STORAGE_KEY  = 'prisma_profile';

// ---------------------------------------------------------------------------
// DownChart SVG — Risk-Feeling-Test
// ---------------------------------------------------------------------------

function DownChart() {
  return (
    <svg viewBox="0 0 300 120" className="w-full max-w-sm mx-auto" aria-hidden="true">
      <defs>
        <linearGradient id="redGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f85149" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#f85149" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[20, 60, 100].map((y) => (
        <line key={y} x1="0" y1={y} x2="300" y2={y} stroke="#e6edf3" strokeOpacity="0.08" strokeWidth="1" />
      ))}
      <path
        d="M 0,20 C 30,22 60,25 90,35 C 120,45 130,50 160,65 C 190,80 220,90 260,105 L 260,120 L 0,120 Z"
        fill="url(#redGrad)"
      />
      <path
        d="M 0,20 C 30,22 60,25 90,35 C 120,45 130,50 160,65 C 190,80 220,90 260,105"
        fill="none" stroke="#f85149" strokeWidth="2.5" strokeLinecap="round"
      />
      <circle cx="0" cy="20" r="4" fill="#f85149" />
      <circle cx="260" cy="105" r="4" fill="#f85149" />
      <text x="265" y="109" fill="#f85149" fontSize="11" fontWeight="bold">–25%</text>
      <text x="2"   y="118" fill="#8b949e" fontSize="10">Jan</text>
      <text x="115" y="118" fill="#8b949e" fontSize="10">Feb</text>
      <text x="230" y="118" fill="#8b949e" fontSize="10">März</text>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Step components
// ---------------------------------------------------------------------------

function StepLanding({ onEntdecker, onKenner }: { onEntdecker: () => void; onKenner: () => void }) {
  return (
    <div className="flex flex-col items-center gap-10 py-12" style={{ animation: 'fadeIn 0.5s ease' }}>
      <div className="text-center space-y-3">
        {/* Mini crystal */}
        <div className="flex justify-center mb-2">
          <div
            data-testid="crystal"
            className="w-8 h-8 rotate-45 rounded-sm animate-pulse"
            style={{
              background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 50%, #bc8cff 100%)',
              boxShadow: '0 0 20px rgba(88,166,255,0.5)',
            }}
          />
        </div>
        <div className="text-3xl font-black tracking-widest text-[#e6edf3]">PRISMA</div>
        <p className="text-[#8b949e] max-w-md text-sm leading-relaxed">
          Dein persönlicher Investment-Companion. Wir helfen dir herauszufinden,
          was zu dir passt — ohne Fachjargon, ohne Druck.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 w-full max-w-lg">
        <button
          onClick={onEntdecker}
          data-testid="btn-entdecker"
          className="group flex-1 rounded-xl p-6 text-left transition-all hover:scale-[1.01]"
          style={{
            background: 'rgba(22,27,34,0.8)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(88,166,255,0.15)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          }}
        >
          <Compass className="h-8 w-8 mb-3 text-blue-400 mx-auto" />
          <div className="font-semibold text-[#e6edf3]">Ich weiss noch nicht, wo ich anfangen soll.</div>
          <div className="text-sm text-[#8b949e] mt-1">Zeig mir den Weg.</div>
          <div className="mt-4 text-xs text-[#58a6ff] group-hover:translate-x-1 transition-transform inline-block">
            Geführte Entdeckung →
          </div>
        </button>

        <button
          onClick={onKenner}
          data-testid="btn-kenner"
          className="group flex-1 rounded-xl p-6 text-left transition-all hover:scale-[1.01]"
          style={{
            background: 'rgba(22,27,34,0.8)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(88,166,255,0.15)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" strokeWidth="1.5" strokeLinecap="round" className="mb-3">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="6" />
            <circle cx="12" cy="12" r="2" />
            <line x1="12" y1="2" x2="12" y2="4" /><line x1="12" y1="20" x2="12" y2="22" />
            <line x1="2" y1="12" x2="4" y2="12" /><line x1="20" y1="12" x2="22" y2="12" />
          </svg>
          <div className="font-semibold text-[#e6edf3]">Ich weiss, was ich suche.</div>
          <div className="text-sm text-[#8b949e] mt-1">Direkt zu den Titeln.</div>
          <div className="mt-4 text-xs text-[#58a6ff] group-hover:translate-x-1 transition-transform inline-block">
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

  useEffect(() => { inputRef.current?.focus(); }, []);

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <StepIndicator current={1} total={7} />
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">PRISMA fragt</div>
        <h2 className="text-xl font-semibold text-[#e6edf3]">Was machst du beruflich?</h2>
        <p className="text-sm text-[#8b949e]">
          Keine richtige oder falsche Antwort — ich will nur verstehen, wie du denkst.
        </p>
        <p className="text-xs text-[#8b949e] italic mt-1 mb-3">
          Warum wir das fragen: Damit wir einschätzen können wie viel Finanzwissen wir voraussetzen dürfen.
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
          data-testid="input-beruf"
          className="w-full rounded-lg px-4 py-3 text-sm text-[#e6edf3] placeholder-[#8b949e] outline-none transition-all"
          style={{
            background: '#161b22',
            border: '1px solid #21262d',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.05)',
          }}
          onFocus={(e) => { e.currentTarget.style.borderColor = '#58a6ff'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(88,166,255,0.15)'; }}
          onBlur={(e)  => { e.currentTarget.style.borderColor = '#21262d'; e.currentTarget.style.boxShadow = 'inset 0 1px 0 rgba(255,255,255,0.05)'; }}
        />
        <PrismaButton onClick={() => value.trim() && onNext(value.trim())} disabled={!value.trim()}>
          Weiter
        </PrismaButton>
      </div>
    </div>
  );
}

function StepZiel({ onNext }: { onNext: (ziel: Ziel) => void }) {
  const [selected, setSelected] = useState<Ziel | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <StepIndicator current={2} total={7} />
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">PRISMA fragt</div>
        <h2 className="text-xl font-semibold text-[#e6edf3] flex items-center justify-center gap-1">
          Wofür ist das Geld irgendwann gedacht?
          <InfoPopover ariaLabel="Mehr Info zu Anlageziel">Was du mit deinem Geld erreichen möchtest</InfoPopover>
        </h2>
        <p className="text-sm text-[#8b949e]">Kein falsches oder richtiges Ziel — ich will nur verstehen.</p>
        <p className="text-xs text-[#8b949e] italic mt-1 mb-3">
          Warum wir das fragen: Ein Rentner und ein Wachstumsinvestor brauchen komplett unterschiedliche Aktien.
        </p>
      </div>
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3">
        {ZIEL_OPTIONS.map((opt) => {
          const active = selected === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setSelected(opt.value)}
              data-testid={`ziel-${opt.value}`}
              className="rounded-xl p-4 text-left transition-all"
              style={{
                background: active ? 'rgba(88,166,255,0.12)' : '#161b22',
                border: `1px solid ${active ? '#58a6ff' : '#21262d'}`,
                boxShadow: active ? '0 0 16px rgba(88,166,255,0.2)' : 'none',
              }}
            >
              <div className="font-medium text-sm text-[#e6edf3]">{opt.label}</div>
              <div className="text-xs text-[#8b949e] mt-1">{opt.sub}</div>
            </button>
          );
        })}
      </div>
      <PrismaButton onClick={() => selected && onNext(selected)} disabled={!selected}>
        Weiter
      </PrismaButton>
    </div>
  );
}

function StepRisiko({ onNext }: { onNext: (risiko: Risiko) => void }) {
  const [selected, setSelected] = useState<Risiko | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <StepIndicator current={3} total={7} />
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">PRISMA fragt</div>
        <h2 className="text-xl font-semibold text-[#e6edf3] flex items-center justify-center gap-1">
          Stell dir vor: Du siehst das auf deinem Konto.
          <InfoPopover ariaLabel="Mehr Info zu Risikotyp">Wie du auf Wertverluste reagierst</InfoPopover>
        </h2>
        <p className="text-sm text-[#8b949e]">
          Du hast CHF 10&apos;000 investiert. Nach 3 Monaten öffnest du die App.
        </p>
        <p className="text-xs text-[#8b949e] italic mt-1 mb-3">
          Warum wir das fragen: Damit wir dir keine Biotech-Titel empfehlen wenn du nachts schlecht schläfst wenn dein Depot im Minus ist.
        </p>
      </div>

      {/* Risk chart */}
      <div
        className="w-full rounded-xl p-4"
        style={{ background: '#161b22', border: '1px solid #21262d' }}
      >
        <div className="text-xs text-[#8b949e] mb-3">Dein Portfolio — letzte 3 Monate</div>
        <DownChart />
      </div>

      <div className="text-center text-sm font-medium text-[#e6edf3]">Was denkst du zuerst?</div>

      <div className="w-full space-y-2">
        {RISIKO_OPTIONS.map((opt) => {
          const active = selected === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setSelected(opt.value)}
              data-testid={`risiko-${opt.value}`}
              className="w-full rounded-xl p-4 text-left transition-all"
              style={{
                background: active ? opt.bg : '#161b22',
                border: `1px solid ${active ? opt.color : '#21262d'}`,
                boxShadow: active ? `0 0 16px ${opt.color}33` : 'none',
              }}
            >
              <div className="flex items-start gap-3">
                <span className="shrink-0">{opt.icon(opt.color)}</span>
                <div>
                  <div className="font-medium text-sm text-[#e6edf3]">{opt.label}</div>
                  <div className="text-xs text-[#8b949e] mt-0.5">{opt.sub}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <p className="text-[11px] text-[#8b949e] text-center max-w-xs">
        Es gibt keine falsche Antwort. Deine ehrliche Reaktion hilft PRISMA dir die richtigen Titel zu zeigen.
      </p>

      <PrismaButton onClick={() => selected && onNext(selected)} disabled={!selected}>
        Weiter
      </PrismaButton>
    </div>
  );
}

function StepBrands({ onNext }: { onNext: (brands: string[]) => void }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [tooltip, setTooltip] = useState<string | null>(null);

  function toggle(ticker: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
    setTooltip(ticker);
    setTimeout(() => setTooltip(null), 2500);
  }

  const categories = Array.from(new Set(BRANDS.map((b) => b.category)));

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-2xl mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <StepIndicator current={4} total={7} />
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">PRISMA fragt</div>
        <h2 className="text-xl font-semibold text-[#e6edf3]">Welche dieser Schweizer Firmen kennst du?</h2>
        <p className="text-sm text-[#8b949e]">
          Aus dem Alltag, der Arbeit, den Nachrichten. Einfach anklicken.
        </p>
        <p className="text-xs text-[#8b949e] italic mt-1 mb-3">
          Warum wir das fragen: Damit dein Universum Aktien enthält die du auch wirklich verstehst.
        </p>
      </div>

      {/* Selected counter */}
      {selected.size > 0 && (
        <div
          className="text-sm text-center px-4 py-2 rounded-full"
          style={{ background: 'rgba(88,166,255,0.1)', border: '1px solid rgba(88,166,255,0.25)', color: '#58a6ff' }}
          data-testid="brands-counter"
        >
          Du kennst bereits{' '}
          <span className="font-bold">{selected.size}</span>{' '}
          investierbare Schweizer Firmen.
        </div>
      )}

      <div className="w-full space-y-5">
        {categories.map((cat) => (
          <div key={cat}>
            <div className="text-[10px] text-[#8b949e] mb-2 uppercase tracking-[0.1em]">{cat}</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {BRANDS.filter((b) => b.category === cat).map((brand) => {
                const isSelected = selected.has(brand.ticker);
                const showTip = tooltip === brand.ticker;
                return (
                  <div key={brand.ticker} className="relative">
                    <button
                      onClick={() => toggle(brand.ticker)}
                      data-testid={`brand-${brand.ticker}`}
                      className="relative w-full rounded-lg p-3 text-center transition-all"
                      style={{
                        background: isSelected ? `${brand.color}18` : '#161b22',
                        border: `1px solid ${isSelected ? brand.color : '#21262d'}`,
                        boxShadow: isSelected ? `0 0 14px ${brand.color}44, inset 0 1px 0 rgba(255,255,255,0.05)` : 'none',
                      }}
                    >
                      {/* Logo circle */}
                      <div
                        className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold mx-auto mb-1.5"
                        style={{ backgroundColor: `${brand.color}22`, color: brand.color }}
                      >
                        {brand.abbr}
                      </div>
                      <div className="text-xs font-medium text-[#e6edf3] truncate">{brand.name}</div>
                      <div className="text-[10px] text-[#8b949e]">{brand.ticker}.SW</div>

                      {/* Checkmark */}
                      {isSelected && (
                        <div
                          className="absolute top-1.5 right-1.5 w-3.5 h-3.5 rounded-full flex items-center justify-center"
                          style={{ backgroundColor: brand.color }}
                        >
                          <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                            <path d="M1.5 4L3 5.5L6.5 2" stroke="#0d1117" strokeWidth="1.5" strokeLinecap="round" />
                          </svg>
                        </div>
                      )}
                    </button>

                    {/* Fact tooltip */}
                    {showTip && (
                      <div
                        className="absolute z-10 bottom-full mb-2 left-1/2 -translate-x-1/2 w-48 rounded-lg p-2.5 text-[11px] text-[#e6edf3] leading-snug pointer-events-none"
                        style={{
                          background: '#161b22',
                          border: `1px solid ${brand.color}66`,
                          boxShadow: `0 4px 20px rgba(0,0,0,0.5), 0 0 8px ${brand.color}22`,
                          animation: 'fadeIn 0.2s ease',
                        }}
                        data-testid={`tooltip-${brand.ticker}`}
                      >
                        <div className="font-semibold mb-0.5" style={{ color: brand.color }}>{brand.name} · {brand.ticker}.SW</div>
                        {brand.fact}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <PrismaButton onClick={() => onNext(Array.from(selected))}>
        {selected.size > 0 ? 'Profil fertigstellen →' : 'Überspringen'}
      </PrismaButton>
    </div>
  );
}

function StepBetrag({ onNext }: { onNext: (betrag: Betrag) => void }) {
  const [selected, setSelected] = useState<Betrag | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <StepIndicator current={5} total={7} />
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">PRISMA fragt</div>
        <h2 className="text-xl font-semibold text-[#e6edf3] flex items-center justify-center gap-1">
          Wie viel möchtest du ungefähr investieren?
          <InfoPopover ariaLabel="Mehr Info zu Anlagebetrag">Dein ungefähres Startkapital hilft uns, passende Aktien zu empfehlen</InfoPopover>
        </h2>
        <p className="text-sm text-[#8b949e]">Es geht nur um eine grobe Einschätzung.</p>
        <p className="text-xs text-[#8b949e] italic mt-1 mb-3">
          Warum wir das fragen: Damit der Sicherheits-Check auf deinem Factsheet in echten CHF-Beträgen rechnet.
        </p>
      </div>
      <div className="w-full space-y-3">
        {BETRAG_OPTIONS.map((opt) => {
          const active = selected === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setSelected(opt.value)}
              data-testid={`betrag-${opt.value}`}
              className="w-full rounded-xl p-4 text-left transition-all"
              style={{
                background: active ? 'rgba(88,166,255,0.12)' : '#161b22',
                border: `1px solid ${active ? '#58a6ff' : '#21262d'}`,
                boxShadow: active ? '0 0 16px rgba(88,166,255,0.2)' : 'none',
              }}
            >
              <div className="font-medium text-sm text-[#e6edf3]">{opt.label}</div>
              <div className="text-xs text-[#8b949e] mt-1">{opt.sub}</div>
            </button>
          );
        })}
      </div>
      <PrismaButton onClick={() => selected && onNext(selected)} disabled={!selected}>
        Weiter
      </PrismaButton>
    </div>
  );
}

function StepNachhaltigkeit({ onNext }: { onNext: (nachhaltigkeit: Nachhaltigkeit) => void }) {
  const [selected, setSelected] = useState<Nachhaltigkeit | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <StepIndicator current={6} total={7} />
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">PRISMA fragt</div>
        <h2 className="text-xl font-semibold text-[#e6edf3] flex items-center justify-center gap-1">
          Wie wichtig ist dir Nachhaltigkeit?
          <InfoPopover ariaLabel="Mehr Info zu Nachhaltigkeit">ESG = Environment (Umwelt), Social (Soziales), Governance (Unternehmensführung) — nachhaltige Unternehmen</InfoPopover>
        </h2>
        <p className="text-sm text-[#8b949e]">ESG-Aktien sind Firmen die nachhaltig wirtschaften.</p>
        <p className="text-xs text-[#8b949e] italic mt-1 mb-3">
          Warum wir das fragen: ESG-Filter schliessen bestimmte Sektoren aus deinem Universum aus.
        </p>
      </div>
      <div className="w-full space-y-3">
        {NACHHALTIGKEIT_OPTIONS.map((opt) => {
          const active = selected === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setSelected(opt.value)}
              data-testid={`nachhaltigkeit-${opt.value}`}
              className="w-full rounded-xl p-4 text-left transition-all"
              style={{
                background: active ? 'rgba(126,231,135,0.1)' : '#161b22',
                border: `1px solid ${active ? '#7ee787' : '#21262d'}`,
                boxShadow: active ? '0 0 16px rgba(126,231,135,0.2)' : 'none',
              }}
            >
              <div className="font-medium text-sm text-[#e6edf3]">{opt.label}</div>
              <div className="text-xs text-[#8b949e] mt-1">{opt.sub}</div>
            </button>
          );
        })}
      </div>
      <PrismaButton onClick={() => selected && onNext(selected)} disabled={!selected}>
        Weiter
      </PrismaButton>
    </div>
  );
}

function StepErtrag({ onNext }: { onNext: (ertrag: Ertrag) => void }) {
  const [selected, setSelected] = useState<Ertrag | null>(null);

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <StepIndicator current={7} total={7} />
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">PRISMA fragt</div>
        <h2 className="text-xl font-semibold text-[#e6edf3] flex items-center justify-center gap-1">
          Was ist dir bei der Rendite wichtiger?
          <InfoPopover ariaLabel="Mehr Info zu Rendite-Fokus">Dividenden = regelmässige Auszahlungen, Wachstum = Kursgewinne</InfoPopover>
        </h2>
        <p className="text-sm text-[#8b949e]">Du kannst das später noch anpassen.</p>
        <p className="text-xs text-[#8b949e] italic mt-1 mb-3">
          Warum wir das fragen: Dividenden-Aktien und Wachstums-Aktien verhalten sich fundamental anders.
        </p>
      </div>
      <div className="w-full space-y-3">
        {ERTRAG_OPTIONS.map((opt) => {
          const active = selected === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setSelected(opt.value)}
              data-testid={`ertrag-${opt.value}`}
              className="w-full rounded-xl p-4 text-left transition-all"
              style={{
                background: active ? 'rgba(188,140,255,0.1)' : '#161b22',
                border: `1px solid ${active ? '#bc8cff' : '#21262d'}`,
                boxShadow: active ? '0 0 16px rgba(188,140,255,0.2)' : 'none',
              }}
            >
              <div className="font-medium text-sm text-[#e6edf3]">{opt.label}</div>
              <div className="text-xs text-[#8b949e] mt-1">{opt.sub}</div>
            </button>
          );
        })}
      </div>
      <PrismaButton onClick={() => selected && onNext(selected)} disabled={!selected}>
        Profil fertigstellen
      </PrismaButton>
    </div>
  );
}

function StepReveal({ profile, onContinue }: { profile: Profile; onContinue: () => void }) {
  const [phase, setPhase] = useState<'crystal' | 'card'>('crystal');
  const risikoLabel = PROFILE_LABELS[profile.risiko];
  const horizon     = ZIEL_HORIZON[profile.ziel];
  const knownBrands = BRANDS.filter((b) => profile.brands.includes(b.ticker));

  const sectorCounts: Record<string, number> = {};
  BRANDS.filter((b) => profile.brands.includes(b.ticker)).forEach((b) => {
    sectorCounts[b.category] = (sectorCounts[b.category] ?? 0) + 1;
  });
  const topSectors = Object.entries(sectorCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([cat]) => cat);

  useEffect(() => {
    const t = setTimeout(() => setPhase('card'), 1400);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.6s ease' }}>
      {/* Prisma crystal animation */}
      <div className="relative flex items-center justify-center h-20">
        <div
          className="w-12 h-12 rotate-45 rounded-md"
          style={{
            background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 50%, #bc8cff 100%)',
            boxShadow: phase === 'card'
              ? '0 0 60px rgba(88,166,255,0.5), 0 0 30px rgba(126,231,135,0.4), 0 0 15px rgba(188,140,255,0.3)'
              : '0 0 20px rgba(88,166,255,0.3)',
            transition: 'box-shadow 0.8s ease',
            animation: 'spin 2s linear infinite',
          }}
          data-testid="crystal"
        />
        {/* Spectrum rays — visible after crystal phase */}
        {phase === 'card' && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            {['#58a6ff', '#7ee787', '#bc8cff', '#ffa657', '#f85149'].map((color, i) => (
              <div
                key={color}
                className="absolute w-0.5 rounded-full opacity-40"
                style={{
                  height: '40px',
                  backgroundColor: color,
                  transformOrigin: 'center top',
                  transform: `rotate(${i * 36 - 72}deg) translateY(-28px)`,
                  animation: 'fadeIn 0.5s ease',
                }}
              />
            ))}
          </div>
        )}
      </div>

      <div className="text-center space-y-1">
        <div className="text-xs text-[#8b949e] tracking-widest uppercase">PRISMA hat dein Investorprofil erstellt</div>
        <h2 className="text-2xl font-bold text-[#e6edf3]">Dein Profil.</h2>
      </div>

      {/* Profile card — glass morphism */}
      {phase === 'card' && (
        <div
          className="w-full rounded-xl p-5 space-y-4"
          style={{
            background: 'rgba(22,27,34,0.85)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(88,166,255,0.2)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
            animation: 'fadeIn 0.6s ease',
          }}
          data-testid="profile-card"
        >
          <ProfileRow label="Typ"          value={risikoLabel} />
          <ProfileRow label="Zeithorizont" value={horizon} />
          <ProfileRow
            label="Kenntnisse"
            value={
              profile.beruf ? 'Erfasst' : 'Einsteiger'
            }
          />
          <ProfileRow
            label="Anlageziel"
            value={
              profile.ziel === 'housing'      ? 'Neue Wohnung'
              : profile.ziel === 'retirement' ? 'Altersvorsorge'
              : profile.ziel === 'freedom'    ? 'Finanzielle Freiheit'
              :                                 'Besser als Sparkonto'
            }
          />
          <ProfileRow
            label="Risikotyp"
            value={
              profile.risiko === 'conservative' ? 'Sicherheitsorientiert'
              : profile.risiko === 'moderate'   ? 'Ausgewogen'
              :                                   'Chancenorientiert'
            }
          />
          <ProfileRow
            label="Anlagebetrag"
            value={
              profile.betrag === 'under_10k'  ? "< CHF 10'000"
              : profile.betrag === '10k_100k' ? "CHF 10'000 – 100'000"
              :                                 "> CHF 100'000"
            }
          />
          <ProfileRow
            label="Nachhaltigkeit"
            value={
              profile.nachhaltigkeit === 'yes'         ? 'ESG-Fokus'
              : profile.nachhaltigkeit === 'no'        ? 'Rendite-Fokus'
              :                                          'Neutral'
            }
          />
          <ProfileRow
            label="Rendite"
            value={
              profile.ertrag === 'dividends' ? 'Dividenden'
              : profile.ertrag === 'balanced' ? 'Ausgewogen'
              :                                 'Wachstum'
            }
          />
          {topSectors.length > 0 && (
            <ProfileRow label="Affinität" value={topSectors.join(' + ')} />
          )}

          {knownBrands.length > 0 && (
            <div>
              <div className="text-xs text-[#8b949e] mb-2">Du kennst bereits</div>
              <div className="flex flex-wrap gap-1.5">
                {knownBrands.map((b) => (
                  <span
                    key={b.ticker}
                    className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium"
                    style={{ backgroundColor: `${b.color}22`, color: b.color }}
                  >
                    {b.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="border-t pt-4" style={{ borderColor: '#21262d' }}>
            <div className="text-xs text-[#8b949e]">
              PRISMA hat Schweizer Titel für dein Profil ausgewählt.
            </div>
          </div>
        </div>
      )}

      {phase === 'card' && (
        <button
          onClick={onContinue}
          data-testid="btn-continue"
          className="w-full rounded-lg px-4 py-3 text-sm font-semibold text-[#0d1117] transition-all hover:opacity-90 hover:shadow-xl hover:scale-[1.01] active:scale-[0.99]"
          style={{
            background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)',
            boxShadow: '0 4px 20px rgba(88,166,255,0.3)',
            animation: 'fadeIn 0.6s ease',
          }}
        >
          Zeig mir mein personalisiertes Dashboard →
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Kenner: fast-lane search
// ---------------------------------------------------------------------------

const QUICK_FILTERS = [
  { label: 'SMI-20',     tickers: ['NESN', 'ROG', 'NOVN', 'ABBN', 'UBSG'] },
  { label: 'Pharma',     tickers: ['ROG', 'NOVN', 'LONN', 'STMN'] },
  { label: 'Tech',       tickers: ['LOGN', 'VACN', 'UBXN', 'IFCN'] },
  { label: 'Dividenden', tickers: ['SCMN', 'ZURN', 'SLHN', 'NESN'] },
  { label: 'Industrie',  tickers: ['ABBN', 'GEBN', 'KNIN', 'SCHP'] },
];

function KennerSearch({ onBack }: { onBack: () => void }) {
  const [query, setQuery] = useState('');
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

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
    <div className="flex flex-col items-center gap-6 py-10 max-w-lg mx-auto" style={{ animation: 'fadeIn 0.4s ease' }}>
      <button
        onClick={onBack}
        className="self-start text-xs text-[#8b949e] hover:text-[#e6edf3] transition-colors"
      >
        ← Zurück
      </button>

      <div className="text-center space-y-1">
        <h2 className="text-xl font-semibold text-[#e6edf3]">Direkt zur Analyse</h2>
        <p className="text-sm text-[#8b949e]">Suche nach Firma, Ticker oder Sektor.</p>
      </div>

      <div className="w-full relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Nestlé, NESN, Pharma..."
          data-testid="kenner-search-input"
          className="w-full rounded-lg px-4 py-3 text-sm text-[#e6edf3] placeholder-[#8b949e] outline-none transition-all"
          style={{ background: '#161b22', border: '1px solid #21262d' }}
          onFocus={(e) => { e.currentTarget.style.borderColor = '#58a6ff'; }}
          onBlur={(e)  => { e.currentTarget.style.borderColor = '#21262d'; }}
        />
        {suggestions.length > 0 && (
          <div
            className="absolute top-full mt-1 w-full rounded-lg z-10 overflow-hidden"
            style={{ background: '#161b22', border: '1px solid #21262d', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}
          >
            {suggestions.map((b) => (
              <button
                key={b.ticker}
                onClick={() => goToStock(b.ticker)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[#21262d] text-sm"
              >
                <span
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                  style={{ backgroundColor: `${b.color}22`, color: b.color }}
                >
                  {b.abbr}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-[#e6edf3] truncate">{b.name}</div>
                  <div className="text-xs text-[#8b949e]">{b.ticker}.SW · {b.category}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="w-full space-y-2">
        <div className="text-xs text-[#8b949e]">Schnellfilter</div>
        <div className="flex flex-wrap gap-2">
          {QUICK_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => goToStock(f.tickers[0])}
              className="rounded-full px-3 py-1.5 text-xs text-[#8b949e] hover:text-[#58a6ff] transition-colors"
              style={{ background: '#161b22', border: '1px solid #21262d' }}
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
// Shared primitives
// ---------------------------------------------------------------------------

function PrismaButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full max-w-sm rounded-lg px-4 py-3 text-sm font-semibold text-[#0d1117] transition-all hover:opacity-90 hover:scale-[1.01] active:scale-[0.99] disabled:opacity-30 disabled:cursor-not-allowed disabled:scale-100"
      style={{
        background: disabled
          ? '#21262d'
          : 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)',
        color: disabled ? '#8b949e' : '#0d1117',
        boxShadow: disabled ? 'none' : '0 4px 20px rgba(88,166,255,0.25)',
      }}
    >
      {children}
    </button>
  );
}

function ConfidenceBar({ currentTurn }: { currentTurn: number }) {
  const pct = Math.round((currentTurn / 7) * 100);
  return (
    <div className="space-y-1 mt-4 max-w-lg mx-auto px-2">
      <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-[10px] text-center text-muted-foreground">
        Dein Profil wird immer präziser. · {pct}%
      </p>
    </div>
  );
}

function StepIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          className="h-1 rounded-full transition-all duration-300"
          style={{
            width: i < current ? '24px' : '16px',
            background: i < current ? '#58a6ff' : '#21262d',
          }}
        />
      ))}
      <span className="ml-2 text-xs text-[#8b949e]">{current} / {total}</span>
    </div>
  );
}

function ProfileRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-xs text-[#8b949e] shrink-0">{label}</span>
      <span className="text-sm font-medium text-[#e6edf3] text-right">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Profile Reveal Screen (shown after completeDiscovery() resolves)
// ---------------------------------------------------------------------------

function DiscoveryProfileReveal({
  result,
  onDiscover,
}: {
  result: {
    risk_profile?: string;
    investment_goal?: string;
    preferred_sectors?: string[];
    investment_amount?: string;
    sustainability_preference?: string;
    return_focus?: string;
    profile_type?: string;
  };
  onDiscover: () => void;
}) {
  // Set cookie as soon as this screen renders
  useEffect(() => {
    document.cookie = 'prisma_onboarding=complete; path=/; max-age=31536000';
  }, []);

  const rows: { label: string; value: string }[] = [
    { label: 'Risiko',         value: result.risk_profile ?? '—' },
    { label: 'Ziel',           value: result.investment_goal ?? '—' },
    { label: 'Sektoren',       value: (result.preferred_sectors ?? []).join(' · ') || '—' },
    { label: 'Betrag',         value: result.investment_amount ?? '—' },
    { label: 'Nachhaltigkeit', value: result.sustainability_preference ?? '—' },
    { label: 'Dividenden',     value: result.return_focus ?? '—' },
  ];

  return (
    <div
      className="flex flex-col items-center gap-6 py-10 max-w-sm mx-auto"
      style={{ animation: 'fadeIn 0.6s ease' }}
      data-testid="discovery-profile-reveal"
    >
      <div className="text-center space-y-2">
        <div className="text-xs text-[#58a6ff] tracking-widest uppercase">Fertig</div>
        <h2 className="text-2xl font-bold text-[#e6edf3]">Dein Profil ist bereit.</h2>
        {result.profile_type && (
          <p className="text-base text-[#8b949e]">{result.profile_type}</p>
        )}
      </div>

      <div
        className="w-full rounded-xl p-5 space-y-3"
        style={{
          background: 'rgba(22,27,34,0.85)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(88,166,255,0.2)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
        }}
      >
        {rows.map((row) => (
          <ProfileRow key={row.label} label={row.label} value={row.value} />
        ))}
      </div>

      <button
        onClick={onDiscover}
        data-testid="btn-meine-aktien"
        className="w-full rounded-lg px-4 py-3 text-sm font-semibold text-[#0d1117] transition-all hover:opacity-90 hover:shadow-xl hover:scale-[1.01] active:scale-[0.99]"
        style={{
          background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)',
          boxShadow: '0 4px 20px rgba(88,166,255,0.3)',
        }}
      >
        Meine Aktien entdecken →
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function StartClient() {
  const [step, setStep]                       = useState<Step>('landing');
  const [beruf, setBeruf]                     = useState('');
  const [ziel, setZiel]                       = useState<Ziel | null>(null);
  const [risiko, setRisiko]                   = useState<Risiko | null>(null);
  const [brands, setBrands]                   = useState<string[]>([]);
  const [betrag, setBetrag]                   = useState<Betrag | null>(null);
  const [nachhaltigkeit, setNachhaltigkeit]   = useState<Nachhaltigkeit | null>(null);
  const [ertrag, setErtrag]                   = useState<Ertrag | null>(null);
  const [sessionId, setSessionId]             = useState<string | null>(null);
  const [kennerMode, setKennerMode]           = useState(false);
  const [loading, setLoading]                 = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState<{
    risk_profile?: string;
    investment_goal?: string;
    preferred_sectors?: string[];
    investment_amount?: string;
    sustainability_preference?: string;
    return_focus?: string;
    profile_type?: string;
  } | null>(null);
  const router = useRouter();

  // Build brand_data map for turn 4 (ticker → {sector, name})
  const brandDataMap = BRANDS.reduce<Record<string, Record<string, string>>>((acc, b) => {
    acc[b.ticker] = { sector: CATEGORY_TO_SECTOR[b.category] ?? b.category, name: b.name };
    return acc;
  }, {});

  const handleContinue = useCallback(
    async (
      finalBrands: string[],
      finalZiel: Ziel,
      finalRisiko: Risiko,
      finalBetrag: Betrag,
      finalNachhaltigkeit: Nachhaltigkeit,
      finalErtrag: Ertrag,
      sid: string,
    ) => {
      setLoading(true);
      const knownBrandObjs = BRANDS.filter((b) => finalBrands.includes(b.ticker));

      try {
        await submitAnswer(sid, 5, finalBetrag);
        await submitAnswer(sid, 6, finalNachhaltigkeit);
        await submitAnswer(sid, 7, finalErtrag);
        const result = await completeDiscovery(sid);
        const discovery = {
          session_id: sid,
          total: result.recommended_stocks.length,
          stocks: result.recommended_stocks,
        };
        localStorage.setItem(DISCOVER_STORAGE_KEY, JSON.stringify(discovery));
        localStorage.setItem(PROFILE_STORAGE_KEY, finalRisiko);

        // Set onboarding cookie before showing profile reveal
        document.cookie = 'prisma_onboarding=complete; path=/; max-age=31536000';

        setDiscoveryResult({
          risk_profile: result.profile.risk_profile ?? finalRisiko,
          investment_goal: result.profile.investment_goal ?? finalZiel,
          preferred_sectors: result.profile.sector_affinity ?? [],
          investment_amount: result.profile.investment_amount ?? finalBetrag,
          sustainability_preference: result.profile.esg_preference ?? finalNachhaltigkeit,
          return_focus: result.profile.income_preference ?? finalErtrag,
          profile_type: PROFILE_LABELS[result.profile.risk_profile as Risiko] ?? PROFILE_LABELS[finalRisiko],
        });
        setLoading(false);
        setStep('profile-reveal');
      } catch {
        const defaultTickers = ['NESN', 'ROG', 'NOVN', 'ABBN', 'UBSG', 'LOGN', 'CFR', 'ZURN'];
        const stocksToShow = knownBrandObjs.length > 0
          ? knownBrandObjs
          : BRANDS.filter((b) => defaultTickers.includes(b.ticker));
        const fallback = {
          session_id: sid,
          total: stocksToShow.length,
          stocks: stocksToShow.map((b) => ({
            ticker: b.ticker,
            name: b.name,
            sector: CATEGORY_TO_SECTOR[b.category] ?? null,
            market_cap_chf: null,
            exchange: 'XSWX',
          })),
        };
        localStorage.setItem(DISCOVER_STORAGE_KEY, JSON.stringify(fallback));
        localStorage.setItem(PROFILE_STORAGE_KEY, finalRisiko);

        // Set onboarding cookie even on fallback
        document.cookie = 'prisma_onboarding=complete; path=/; max-age=31536000';

        setDiscoveryResult({
          risk_profile: finalRisiko,
          investment_goal: finalZiel,
          preferred_sectors: [],
          investment_amount: finalBetrag,
          sustainability_preference: finalNachhaltigkeit,
          return_focus: finalErtrag,
          profile_type: PROFILE_LABELS[finalRisiko],
        });
        setLoading(false);
        setStep('profile-reveal');
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // Handles turns 1-4 sequentially before showing the reveal step
  async function handleBrandsSubmit(finalBrands: string[]) {
    setBrands(finalBrands);
    setStep('betrag');

    // Fire off turns 1-4 in background
    try {
      const { session_id: sid } = await createDiscoverySession();
      setSessionId(sid);
      await submitAnswer(sid, 1, beruf || '');
      await submitAnswer(sid, 2, ziel!);
      await submitAnswer(sid, 3, risiko!);
      await submitAnswer(sid, 4, finalBrands, { brand_data: brandDataMap });
    } catch {
      // session will be null; handleContinue will use fallback
      setSessionId(crypto.randomUUID());
    }
  }

  if (loading) {
    return <PrismaLoader label="Dein Universe wird zusammengestellt" />;
  }

  if (kennerMode) {
    return <div className="min-h-[60vh]"><KennerSearch onBack={() => setKennerMode(false)} /></div>;
  }

  const STEP_TO_TURN: Partial<Record<Step, number>> = {
    beruf: 1,
    ziel: 2,
    risiko: 3,
    brands: 4,
    betrag: 5,
    nachhaltigkeit: 6,
    ertrag: 7,
  };
  const confidenceTurn = STEP_TO_TURN[step] ?? null;

  return (
    <div className="min-h-[60vh]">
      {step === 'landing' && (
        <StepLanding
          onEntdecker={() => { setKennerMode(false); setStep('beruf'); }}
          onKenner={() => setKennerMode(true)}
        />
      )}
      {step === 'beruf'   && <StepBeruf  onNext={(v) => { setBeruf(v);   setStep('ziel'); }} />}
      {step === 'ziel'    && <StepZiel   onNext={(v) => { setZiel(v);    setStep('risiko'); }} />}
      {step === 'risiko'  && <StepRisiko onNext={(v) => { setRisiko(v);  setStep('brands'); }} />}
      {step === 'brands'  && <StepBrands onNext={handleBrandsSubmit} />}
      {step === 'betrag'  && (
        <StepBetrag onNext={(v) => { setBetrag(v); setStep('nachhaltigkeit'); }} />
      )}
      {step === 'nachhaltigkeit' && (
        <StepNachhaltigkeit onNext={(v) => { setNachhaltigkeit(v); setStep('ertrag'); }} />
      )}
      {step === 'ertrag' && (
        <StepErtrag onNext={(v) => {
          setErtrag(v);
          handleContinue(brands, ziel!, risiko!, betrag!, nachhaltigkeit!, v, sessionId ?? crypto.randomUUID());
        }} />
      )}
      {step === 'reveal' && ziel && risiko && betrag && nachhaltigkeit && ertrag && (
        <StepReveal
          profile={{ beruf, ziel, risiko, brands, betrag, nachhaltigkeit, ertrag }}
          onContinue={() => handleContinue(brands, ziel, risiko, betrag, nachhaltigkeit, ertrag, sessionId ?? crypto.randomUUID())}
        />
      )}
      {step === 'profile-reveal' && discoveryResult && (
        <DiscoveryProfileReveal
          result={discoveryResult}
          onDiscover={() => {
            document.cookie = 'prisma_onboarding=complete; path=/; max-age=31536000';
            router.push('/discover');
          }}
        />
      )}
      {confidenceTurn !== null && <ConfidenceBar currentTurn={confidenceTurn} />}
    </div>
  );
}
