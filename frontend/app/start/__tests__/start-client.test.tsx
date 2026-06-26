import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/api/discovery', () => ({
  createDiscoverySession: vi.fn(),
  submitAnswer: vi.fn(),
  completeDiscovery: vi.fn(),
}));

import { StartClient, DISCOVERY_FLOW_STORAGE_KEY } from '../start-client';
import { createDiscoverySession, submitAnswer, completeDiscovery } from '@/lib/api/discovery';

// StartClient liest beim Mount aus sessionStorage (W-1 / F-DISC-1). Ohne
// Cleanup würde ein Test, der den Flow-State persistiert, alle nachfolgenden
// Tests verseuchen (sie würden nicht mehr bei "landing" starten).
afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

describe('StartClient — Landing', () => {
  it('zeigt beide Einstiegs-Optionen', () => {
    render(<StartClient />);
    expect(screen.getByTestId('btn-entdecker')).toBeInTheDocument();
    expect(screen.getByTestId('btn-kenner')).toBeInTheDocument();
  });

  it('wechselt zu Beruf-Schritt wenn Entdecker gewählt', () => {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-entdecker'));
    expect(screen.getByTestId('input-beruf')).toBeInTheDocument();
  });

  it('wechselt zu Kenner-Suche wenn Kenner gewählt', () => {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-kenner'));
    expect(screen.getByTestId('kenner-search-input')).toBeInTheDocument();
  });
});

describe('StartClient — StepBeruf', () => {
  beforeEach(() => {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-entdecker'));
  });

  it('deaktiviert Weiter-Button wenn Eingabe leer', () => {
    const buttons = screen.getAllByRole('button');
    const weiterBtn = buttons.find((b) => b.textContent === 'Weiter');
    expect(weiterBtn).toBeDisabled();
  });

  it('aktiviert Weiter-Button wenn Text eingegeben', () => {
    fireEvent.change(screen.getByTestId('input-beruf'), { target: { value: 'Entwickler' } });
    const buttons = screen.getAllByRole('button');
    const weiterBtn = buttons.find((b) => b.textContent === 'Weiter');
    expect(weiterBtn).not.toBeDisabled();
  });

  it('wechselt zu Ziel-Schritt nach Bestätigung', () => {
    fireEvent.change(screen.getByTestId('input-beruf'), { target: { value: 'Entwickler' } });
    const buttons = screen.getAllByRole('button');
    const weiterBtn = buttons.find((b) => b.textContent === 'Weiter')!;
    fireEvent.click(weiterBtn);
    expect(screen.getByTestId('ziel-housing')).toBeInTheDocument();
  });
});

describe('StartClient — StepZiel', () => {
  function goToZiel() {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-entdecker'));
    fireEvent.change(screen.getByTestId('input-beruf'), { target: { value: 'Lehrer' } });
    const weiterBtn = screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!;
    fireEvent.click(weiterBtn);
  }

  it('zeigt alle 4 Ziel-Optionen', () => {
    goToZiel();
    expect(screen.getByTestId('ziel-housing')).toBeInTheDocument();
    expect(screen.getByTestId('ziel-retirement')).toBeInTheDocument();
    expect(screen.getByTestId('ziel-freedom')).toBeInTheDocument();
    expect(screen.getByTestId('ziel-beat_savings')).toBeInTheDocument();
  });

  it('wechselt zu Risiko-Schritt nach Ziel-Auswahl', () => {
    goToZiel();
    fireEvent.click(screen.getByTestId('ziel-retirement'));
    const weiterBtn = screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!;
    fireEvent.click(weiterBtn);
    expect(screen.getByTestId('risiko-conservative')).toBeInTheDocument();
  });
});

describe('StartClient — StepRisiko (Risk-Feeling-Test)', () => {
  function goToRisiko() {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-entdecker'));
    fireEvent.change(screen.getByTestId('input-beruf'), { target: { value: 'Arzt' } });
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
    fireEvent.click(screen.getByTestId('ziel-freedom'));
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
  }

  it('zeigt alle 3 Risiko-Optionen mit Emojis', () => {
    goToRisiko();
    expect(screen.getByTestId('risiko-conservative')).toBeInTheDocument();
    expect(screen.getByTestId('risiko-moderate')).toBeInTheDocument();
    expect(screen.getByTestId('risiko-aggressive')).toBeInTheDocument();
  });

  it('zeigt Erklärungs-Text unter den Optionen', () => {
    goToRisiko();
    expect(screen.getByText(/keine falsche Antwort/i)).toBeInTheDocument();
  });

  it('wechselt zu Brand-Schritt nach Risiko-Auswahl', () => {
    goToRisiko();
    fireEvent.click(screen.getByTestId('risiko-moderate'));
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
    expect(screen.getByTestId('brand-NESN')).toBeInTheDocument();
  });
});

describe('StartClient — StepBrands (Brand Logo Grid)', () => {
  function goToBrands() {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-entdecker'));
    fireEvent.change(screen.getByTestId('input-beruf'), { target: { value: 'Ingenieur' } });
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
    fireEvent.click(screen.getByTestId('ziel-housing'));
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
    fireEvent.click(screen.getByTestId('risiko-aggressive'));
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
  }

  it('zeigt 24 Brand-Buttons', () => {
    goToBrands();
    const brands = screen.getAllByTestId(/^brand-/);
    expect(brands).toHaveLength(24);
  });

  it('zeigt Counter nach erstem Klick', () => {
    goToBrands();
    fireEvent.click(screen.getByTestId('brand-NESN'));
    expect(screen.getByTestId('brands-counter')).toBeInTheDocument();
  });

  it('Counter zählt mehrere Auswahlen', () => {
    goToBrands();
    fireEvent.click(screen.getByTestId('brand-NESN'));
    fireEvent.click(screen.getByTestId('brand-ROG'));
    expect(screen.getByTestId('brands-counter').textContent).toMatch(/2/);
  });

  it('Deselektieren entfernt vom Counter', () => {
    goToBrands();
    fireEvent.click(screen.getByTestId('brand-NESN'));
    fireEvent.click(screen.getByTestId('brand-NESN'));
    expect(screen.queryByTestId('brands-counter')).not.toBeInTheDocument();
  });

  it('Überspringen-Button zeigt wenn nichts ausgewählt', () => {
    goToBrands();
    expect(screen.getByRole('button', { name: 'Überspringen' })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// W-1 (F-DISC-1): Reload-Robustheit — Flow-State muss sessionStorage überleben
// ---------------------------------------------------------------------------

describe('StartClient — Reload-Robustheit (W-1 / F-DISC-1)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.mocked(createDiscoverySession).mockReset();
    vi.mocked(submitAnswer).mockReset();
    vi.mocked(completeDiscovery).mockReset();
  });

  it('fällt NICHT auf Landing zurück, wenn beim Mount bereits ein Flow-State (Step risiko) in sessionStorage liegt', () => {
    // Simuliert einen Reload mitten im Flow: Step 3 (risiko), inkl. bereits
    // beantworteter Turns 1-2 (beruf, ziel) und einer registrierten sessionId.
    sessionStorage.setItem(
      DISCOVERY_FLOW_STORAGE_KEY,
      JSON.stringify({
        step: 'risiko',
        beruf: 'Ingenieur',
        ziel: 'housing',
        risiko: null,
        brands: [],
        betrag: null,
        nachhaltigkeit: null,
        ertrag: null,
        sessionId: 'session-abc-123',
      }),
    );

    render(<StartClient />);

    // Erwartung: Wir landen direkt im Risiko-Schritt, nicht auf der Landing-Page.
    expect(screen.queryByTestId('btn-entdecker')).not.toBeInTheDocument();
    expect(screen.getByTestId('risiko-conservative')).toBeInTheDocument();
  });

  it('persistiert step + sessionId in sessionStorage, sobald sich der Step ändert', () => {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-entdecker'));
    fireEvent.change(screen.getByTestId('input-beruf'), { target: { value: 'Pilot' } });
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);

    const raw = sessionStorage.getItem(DISCOVERY_FLOW_STORAGE_KEY);
    expect(raw).not.toBeNull();
    const persisted = JSON.parse(raw!);
    expect(persisted.step).toBe('ziel');
    expect(persisted.beruf).toBe('Pilot');
  });
});

// ---------------------------------------------------------------------------
// W-2 (F-DISC-2): Race Condition — handleContinue muss auf echte sessionId warten
// ---------------------------------------------------------------------------

describe('StartClient — Race Condition Turns 1-4 vs. 5-7 (W-2 / F-DISC-2)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.mocked(createDiscoverySession).mockReset();
    vi.mocked(submitAnswer).mockReset();
    vi.mocked(completeDiscovery).mockReset();
  });

  function goToBrands() {
    render(<StartClient />);
    fireEvent.click(screen.getByTestId('btn-entdecker'));
    fireEvent.change(screen.getByTestId('input-beruf'), { target: { value: 'Ingenieur' } });
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
    fireEvent.click(screen.getByTestId('ziel-housing'));
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
    fireEvent.click(screen.getByTestId('risiko-aggressive'));
    fireEvent.click(screen.getAllByRole('button').find((b) => b.textContent === 'Weiter')!);
  }

  function clickWeiter() {
    const buttons = screen.getAllByRole('button');
    const weiterBtn = buttons.find((b) => b.textContent === 'Weiter' || b.textContent === 'Profil fertigstellen')!;
    fireEvent.click(weiterBtn);
  }

  it('wartet bei schnellem Durchklicken auf die echte Session statt eine randomUUID zu verwenden', async () => {
    const REAL_SESSION_ID = 'real-session-from-backend-999';

    // createDiscoverySession() wird künstlich verzögert, um die Race Condition
    // zu simulieren: Der Nutzer klickt schneller durch, als Turns 1-4 brauchen.
    let resolveSession: (value: { session_id: string }) => void;
    vi.mocked(createDiscoverySession).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSession = resolve;
        }),
    );
    vi.mocked(submitAnswer).mockResolvedValue({
      session_id: REAL_SESSION_ID,
      next_turn: null,
      confidence: 1,
      partial_profile: {
        session_id: REAL_SESSION_ID,
        risk_profile: 'aggressive',
        sector_affinity: [],
        time_horizon: 'long',
        investment_goal: 'housing',
        confidence_score: 1,
        onboarding_complete: false,
      },
    });
    vi.mocked(completeDiscovery).mockResolvedValue({
      profile: {
        session_id: REAL_SESSION_ID,
        risk_profile: 'aggressive',
        sector_affinity: [],
        time_horizon: 'long',
        investment_goal: 'housing',
        confidence_score: 1,
        onboarding_complete: true,
      },
      recommended_stocks: [],
    });

    goToBrands();

    // Brands-Submit auslösen (feuert createDiscoverySession + Turns 1-4 im Hintergrund)
    fireEvent.click(screen.getByTestId('brand-NESN'));
    fireEvent.click(screen.getByRole('button', { name: /Profil fertigstellen/ })); // -> Step "betrag"

    // Sofort weiter durchklicken, OHNE auf die Session zu warten (race!).
    fireEvent.click(screen.getByTestId('betrag-10k_100k'));
    clickWeiter(); // -> Step "nachhaltigkeit"
    fireEvent.click(screen.getByTestId('nachhaltigkeit-yes'));
    clickWeiter(); // -> Step "ertrag"
    fireEvent.click(screen.getByTestId('ertrag-growth'));
    clickWeiter(); // -> triggert handleContinue (Turns 5-7 + complete)

    // Jetzt erst löst die Session-Erstellung auf (verzögert wie im echten Race-Fall).
    resolveSession!({ session_id: REAL_SESSION_ID });

    await waitFor(() => {
      expect(submitAnswer).toHaveBeenCalledWith(REAL_SESSION_ID, 5, '10k_100k');
    });

    // Keiner der submitAnswer-Aufrufe darf mit einer anderen sessionId als der
    // vom Mock zurückgegebenen echten Session-ID erfolgt sein (kein randomUUID-Fallback).
    const calledSessionIds = vi.mocked(submitAnswer).mock.calls.map((call) => call[0]);
    expect(calledSessionIds.every((id) => id === REAL_SESSION_ID)).toBe(true);

    expect(completeDiscovery).toHaveBeenCalledWith(REAL_SESSION_ID);
  });
});
