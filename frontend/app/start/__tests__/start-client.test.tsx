import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { StartClient } from '../start-client';

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
