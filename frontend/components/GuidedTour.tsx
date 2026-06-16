'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { X, ArrowRight, Map } from 'lucide-react';

const TOUR_STEPS = [
  { title: 'So lernt PRISMA dich kennen.', description: 'In 7 kurzen Fragen erstellt PRISMA dein persönliches Investor-Profil. Kein Fachjargon, keine falschen Antworten.', href: '/start' },
  { title: 'Dein tägliches Briefing.', description: 'Das Dashboard zeigt dir jeden Morgen die 3 stärksten Signale aus deinem persönlichen Universum — BUY, HOLD, oder SELL.', href: null },
  { title: 'Dein persönliches Universum.', description: 'PRISMA wählt automatisch Schweizer Aktien die zu deinem Profil passen. Du musst keine Aktien selbst suchen.', href: '/discover' },
  { title: 'Was soll ich mit dieser Aktie tun?', description: 'Das Factsheet erklärt in einfacher Sprache warum PRISMA ein BUY, HOLD oder SELL empfiehlt. Mit historischer Validierung.', href: '/stocks' },
  { title: 'Beweise dass das Signal funktioniert.', description: 'Die Signal-Validierung zeigt: Wie hätte PRISMA in den letzten 3 Jahren abgeschnitten? Vergleich mit Buy & Hold.', href: null },
  { title: 'PRISMA bewertet den ganzen Markt.', description: 'Das Ranking bewertet alle Aktien in deinem Universum und zeigt dir wer heute kaufenswert ist — nach Score sortiert.', href: '/rankings' },
  { title: 'BUY, HOLD oder SELL — auf einen Blick.', description: 'Die Signale-Seite zeigt alle aktuellen Empfehlungen aus deinem Universum. Personalisiert, mit Begründung auf Deutsch.', href: '/decision' },
  { title: 'Frag PRISMA direkt.', description: 'Der Research-Bereich beantwortet deine Fragen zu Aktien, Makro und Dividenden — basierend auf Schweizer Geschäftsberichten und aktuellen Daten.', href: '/research' },
];

interface GuidedTourProps {
  onClose: () => void;
}

export function GuidedTour({ onClose }: GuidedTourProps) {
  const [step, setStep] = useState(0);
  const router = useRouter();
  const current = TOUR_STEPS[step];
  const isLast = step === TOUR_STEPS.length - 1;

  function handleNext() {
    if (isLast) {
      onClose();
      return;
    }
    setStep((s) => s + 1);
  }

  function handleNavigate() {
    if (current.href) router.push(current.href);
    handleNext();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Geführte Tour"
    >
      <div className="relative mx-4 w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl">
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Tour beenden"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Step indicator */}
        <div className="mb-4 flex gap-1.5">
          {TOUR_STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i === step ? 'bg-blue-500' : i < step ? 'bg-blue-300 dark:bg-blue-800' : 'bg-muted-foreground/30'
              }`}
            />
          ))}
        </div>

        <p className="mb-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Schritt {step + 1} von {TOUR_STEPS.length}
        </p>
        <h2 className="mb-3 text-lg font-bold text-foreground">{current.title}</h2>
        <p className="mb-6 text-sm text-muted-foreground leading-relaxed">{current.description}</p>

        <div className="flex items-center gap-3">
          {current.href && (
            <button
              onClick={handleNavigate}
              className="flex items-center gap-1.5 rounded-lg bg-muted px-3 py-2 text-sm text-foreground hover:bg-muted/70 transition-colors"
            >
              Ansehen <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            onClick={handleNext}
            className="ml-auto flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 transition-colors"
          >
            {isLast ? 'Tour beenden' : 'Weiter'}{' '}
            {!isLast && <ArrowRight className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>
    </div>
  );
}

export function GuidedTourButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-muted/60 px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
      >
        <Map className="h-4 w-4" />
        Geführte Tour starten
      </button>
      {open && <GuidedTour onClose={() => setOpen(false)} />}
    </>
  );
}
