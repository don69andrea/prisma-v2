export const MODEL_KEYS = [
  'quality_classic',
  'alpha',
  'trend_momentum',
  'value_alpha_potential',
  'diversification',
] as const;

export type ModelKey = (typeof MODEL_KEYS)[number];

export const MODEL_INFO: Record<ModelKey, { label: string; description: string }> = {
  quality_classic: {
    label: 'Quality',
    description:
      'Fundamental gesund & günstig bewertet — Kombiniert 8 klassische Kennzahlen (Marge, Verschuldung, ROE, KGV …) zu einem Score.',
  },
  alpha: {
    label: 'Alpha',
    description:
      'Konsistent besser als der Index — Outperformance vs. Benchmark über mehrere Zeithorizonte, mit Sharpe gewichtet.',
  },
  trend_momentum: {
    label: 'Trend',
    description:
      'Aktuelles Momentum — Welche Aktien zuletzt stärker als der Markt liefen, jüngere Daten zählen mehr.',
  },
  value_alpha_potential: {
    label: 'Value',
    description:
      'Mean-Reversion-Kandidaten — Wie weit unter dem eigenen historischen Outperformance-Hoch der Titel steht.',
  },
  diversification: {
    label: 'Diversification',
    description:
      'Risiko-Diversifikatoren — Niedrige Eigenvolatilität und niedrige Korrelation zu anderen Titeln im Universum.',
  },
};

export const SWEET_SPOT_DEFINITION =
  'Sweet-Spot-Aktien liegen im Top-25 % in mindestens 3 von 5 Modellen — also auf mehreren unabhängigen Achsen überzeugend, nicht nur in einer Disziplin.';

/**
 * Gibt die Modelle zurück, in denen der Ticker im Top-25 % liegt.
 * Schwelle: rank <= ceil(totalStocks * 0.25), spiegelt Backend-Logik
 * aus test_top25_in_3_of_5_models_is_sweet_spot.
 */
export function getSweetSpotModels(
  perModelRanks: Record<string, number | null>,
  totalStocks: number,
): ModelKey[] {
  const threshold = Math.ceil(totalStocks * 0.25);
  return MODEL_KEYS.filter((key) => {
    const rank = perModelRanks[key];
    return rank !== null && rank !== undefined && rank <= threshold;
  });
}
