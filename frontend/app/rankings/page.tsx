'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { usePrismaMode } from '@/hooks/usePrismaMode';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PrismaBar } from '@/components/ui/PrismaBar';
import { RankingsForm } from './rankings-form';
import { RunHistoryList } from './run-history-list';
import { listUniverses } from '@/lib/api/universes';
import { createRun } from '@/lib/api/runs';

// ---------------------------------------------------------------------------
// Simple Mode — 3-question inline wizard
// ---------------------------------------------------------------------------

type WizardStep = 0 | 1 | 2 | 3;

type UniverseChoice = 'mein' | 'smi' | 'spi';
type TopNChoice = 5 | 10 | 20;
type WeightChoice = 'sicherheit' | 'rendite' | 'ausgewogen';

function resolveUniverseId(
  choice: UniverseChoice,
  universes: Array<{ id: string; name: string }>,
): string {
  if (choice === 'mein') {
    return universes[0]?.id ?? '';
  }
  const label = choice === 'smi' ? 'smi' : 'spi';
  const found = universes.find((u) => u.name.toLowerCase().includes(label));
  return found?.id ?? universes[0]?.id ?? '';
}

function WizardCard({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      {children}
    </div>
  );
}

function ChoiceButton({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-lg border px-6 py-4 text-left text-sm font-medium transition-colors',
        selected
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-border bg-background hover:bg-muted',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

function SimpleRankingsWizard() {
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>(0);
  const [universeChoice, setUniverseChoice] = useState<UniverseChoice | null>(null);
  const [topN, setTopN] = useState<TopNChoice | null>(null);
  const [weightChoice, setWeightChoice] = useState<WeightChoice | null>(null);

  const universesQuery = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
    staleTime: 30 * 1000,
    enabled: step >= 1,
  });

  const universes = universesQuery.data?.items ?? [];

  const mutation = useMutation({
    mutationFn: (universeId: string) => createRun(universeId),
    onSuccess: (run) => router.push(`/rankings/${run.id}`),
  });

  // Step 0 — landing prompt
  if (step === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-16 text-center">
        <div className="space-y-2">
          <p className="text-lg font-semibold">Ranking starten.</p>
          <p className="text-sm text-muted-foreground max-w-sm">
            PRISMA bewertet alle Aktien in deinem Universum
            und zeigt dir wer heute kaufenswert ist.
          </p>
        </div>
        <Button size="lg" onClick={() => setStep(1)}>
          Ranking starten
        </Button>
      </div>
    );
  }

  // Loading / error states for universe fetch
  if (step >= 1 && universesQuery.isLoading) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Universen werden geladen…
      </div>
    );
  }

  if (step >= 1 && universesQuery.isError) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-destructive text-sm" role="alert">
        <XCircle className="h-4 w-4 shrink-0" />
        <span>
          Universen konnten nicht geladen werden:{' '}
          {universesQuery.error instanceof Error
            ? universesQuery.error.message
            : 'Unbekannter Fehler'}
        </span>
      </div>
    );
  }

  // Running / error after Q3 is answered
  if (mutation.isPending) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <p className="text-sm font-medium text-muted-foreground">
          PRISMA analysiert Aktien…
        </p>
        <PrismaBar />
      </div>
    );
  }

  if (mutation.isError) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-center">
        <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
          <XCircle className="h-4 w-4 shrink-0" />
          <span>
            {mutation.error instanceof Error
              ? mutation.error.message
              : 'Analyse konnte nicht gestartet werden'}
          </span>
        </div>
        <Button variant="outline" onClick={() => { mutation.reset(); setStep(1); }}>
          Nochmal versuchen
        </Button>
      </div>
    );
  }

  // Step 1 — which universe?
  if (step === 1) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-12">
        <p className="text-base font-semibold">Welche Aktien sollen bewertet werden?</p>
        <WizardCard>
          {(
            [
              { value: 'mein', label: 'Mein Universum' },
              { value: 'smi', label: 'SMI' },
              { value: 'spi', label: 'SPI' },
            ] as Array<{ value: UniverseChoice; label: string }>
          ).map(({ value, label }) => (
            <ChoiceButton
              key={value}
              label={label}
              selected={universeChoice === value}
              onClick={() => {
                setUniverseChoice(value);
                setStep(2);
              }}
            />
          ))}
        </WizardCard>
      </div>
    );
  }

  // Step 2 — top N
  if (step === 2) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-12">
        <p className="text-base font-semibold">Wie viele Titel willst du sehen?</p>
        <WizardCard>
          {([5, 10, 20] as TopNChoice[]).map((n) => (
            <ChoiceButton
              key={n}
              label={`Top ${n}`}
              selected={topN === n}
              onClick={() => {
                setTopN(n);
                setStep(3);
              }}
            />
          ))}
        </WizardCard>
      </div>
    );
  }

  // Step 3 — priority preference
  if (step === 3) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-12">
        <p className="text-base font-semibold">Was ist dir wichtiger?</p>
        <WizardCard>
          {(
            [
              { value: 'sicherheit', label: 'Sicherheit' },
              { value: 'rendite', label: 'Rendite' },
              { value: 'ausgewogen', label: 'Ausgewogen' },
            ] as Array<{ value: WeightChoice; label: string }>
          ).map(({ value, label }) => (
            <ChoiceButton
              key={value}
              label={label}
              selected={weightChoice === value}
              onClick={() => {
                setWeightChoice(value);
                const resolvedId = resolveUniverseId(universeChoice!, universes);
                mutation.mutate(resolvedId);
              }}
            />
          ))}
        </WizardCard>
      </div>
    );
  }

  return null;
}

// ---------------------------------------------------------------------------
// Page root — switches between Simple and Pro based on mode
// ---------------------------------------------------------------------------

export default function RankingsPage() {
  const { isSimple } = usePrismaMode();

  if (isSimple) {
    return (
      <div className="max-w-3xl">
        <SimpleRankingsWizard />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Rankings.</h1>
        <p className="text-muted-foreground text-sm">
          Wähle ein Universum und starte eine Analyse über alle 5 Modelle.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Neue Analyse</CardTitle>
        </CardHeader>
        <CardContent>
          <RankingsForm />
        </CardContent>
      </Card>

      <RunHistoryList />
    </div>
  );
}
