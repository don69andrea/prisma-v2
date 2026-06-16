/**
 * Umfassende E2E-Tests für die Krypto-Seite (/crypto).
 *
 * API-Calls werden via page.route() gemockt → kein Backend nötig.
 * Tested: Fear&Greed Gauge, Simple-Mode Karten, Pro-Mode Tabelle,
 * Score-Aufschlüsselung, Disclaimer, Nav-Link, Fehlerbehandlung, Modus-Toggle.
 */

import { test, expect, Page } from '@playwright/test';

// ── Mock-Daten ────────────────────────────────────────────────────────────────

const MOCK_FEAR_GREED = {
  value: 35,
  label: 'Fear',
  timestamp: '1700000000',
};

const MOCK_SIGNALS = [
  {
    ticker: 'BTC',
    name: 'Bitcoin',
    signal: 'STRONG_BUY',
    score: 82,
    score_components: { momentum: 25, trend: 20, sentiment: 16, markt: 13, risiko: 8 },
    signal_reason_de: 'Bitcoin ist technisch überverkauft (RSI 28) — historisch ein Einstiegssignal.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 28.5,
    macd_signal: 'bullish',
    volatility_30d_pct: 55.2,
    correlation_smi_1y: 0.12,
    has_six_etp: true,
    price_chf: 88500,
    market_cap_chf: 1_750_000_000_000,
    price_change_24h_pct: 2.3,
    price_change_7d_pct: 8.5,
    ath_change_pct: -20.0,
    market_cap_rank: 1,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'ETH',
    name: 'Ethereum',
    signal: 'BUY',
    score: 71,
    score_components: { momentum: 20, trend: 18, sentiment: 14, markt: 12, risiko: 7 },
    signal_reason_de: 'Ethereum zeigt starkes 7-Tage-Momentum (+8.5%) bei Score 71/100.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 42.0,
    macd_signal: 'bullish',
    volatility_30d_pct: 62.1,
    correlation_smi_1y: 0.18,
    has_six_etp: true,
    price_chf: 3200,
    market_cap_chf: 380_000_000_000,
    price_change_24h_pct: 1.8,
    price_change_7d_pct: 6.2,
    ath_change_pct: -35.0,
    market_cap_rank: 2,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'SOL',
    name: 'Solana',
    signal: 'BUY',
    score: 65,
    score_components: { momentum: 18, trend: 16, sentiment: 13, markt: 11, risiko: 7 },
    signal_reason_de: 'Solana zeigt starkes 7-Tage-Momentum (+5.1%) bei Score 65/100.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 48.5,
    macd_signal: 'bullish',
    volatility_30d_pct: 78.5,
    correlation_smi_1y: 0.09,
    has_six_etp: false,
    price_chf: 185,
    market_cap_chf: 85_000_000_000,
    price_change_24h_pct: 0.5,
    price_change_7d_pct: 5.1,
    ath_change_pct: -55.0,
    market_cap_rank: 5,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'BNB',
    name: 'BNB',
    signal: 'HOLD',
    score: 52,
    score_components: { momentum: 15, trend: 13, sentiment: 10, markt: 9, risiko: 5 },
    signal_reason_de: 'BNB in neutralem Bereich (Score 52/100) — Angststimmung, kein klarer Trigger.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 51.2,
    macd_signal: 'bearish',
    volatility_30d_pct: 45.0,
    correlation_smi_1y: 0.22,
    has_six_etp: false,
    price_chf: 580,
    market_cap_chf: 85_000_000_000,
    price_change_24h_pct: -0.3,
    price_change_7d_pct: 1.2,
    ath_change_pct: -25.0,
    market_cap_rank: 4,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'XRP',
    name: 'XRP',
    signal: 'HOLD',
    score: 48,
    score_components: { momentum: 14, trend: 12, sentiment: 10, markt: 8, risiko: 4 },
    signal_reason_de: 'XRP in neutralem Bereich (Score 48/100) — Angststimmung, kein klarer Trigger.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 53.8,
    macd_signal: 'bearish',
    volatility_30d_pct: 50.5,
    correlation_smi_1y: 0.15,
    has_six_etp: false,
    price_chf: 0.58,
    market_cap_chf: 32_000_000_000,
    price_change_24h_pct: -1.1,
    price_change_7d_pct: -2.0,
    ath_change_pct: -65.0,
    market_cap_rank: 6,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'ADA',
    name: 'Cardano',
    signal: 'HOLD',
    score: 44,
    score_components: { momentum: 12, trend: 11, sentiment: 9, markt: 8, risiko: 4 },
    signal_reason_de: 'Cardano in neutralem Bereich (Score 44/100) — Angststimmung, kein klarer Trigger.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 55.0,
    macd_signal: 'bearish',
    volatility_30d_pct: 68.0,
    correlation_smi_1y: 0.08,
    has_six_etp: false,
    price_chf: 0.42,
    market_cap_chf: 15_000_000_000,
    price_change_24h_pct: -2.5,
    price_change_7d_pct: -4.1,
    ath_change_pct: -72.0,
    market_cap_rank: 9,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'DOT',
    name: 'Polkadot',
    signal: 'HOLD',
    score: 41,
    score_components: { momentum: 11, trend: 10, sentiment: 9, markt: 7, risiko: 4 },
    signal_reason_de: 'Polkadot in neutralem Bereich (Score 41/100) — Angststimmung, kein klarer Trigger.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 58.2,
    macd_signal: 'bearish',
    volatility_30d_pct: 72.0,
    correlation_smi_1y: 0.11,
    has_six_etp: false,
    price_chf: 5.8,
    market_cap_chf: 8_500_000_000,
    price_change_24h_pct: -3.2,
    price_change_7d_pct: -6.5,
    ath_change_pct: -88.0,
    market_cap_rank: 12,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'MATIC',
    name: 'Polygon',
    signal: 'SELL',
    score: 32,
    score_components: { momentum: 8, trend: 8, sentiment: 7, markt: 6, risiko: 3 },
    signal_reason_de: 'Polygon zeigt schwaches Momentum bei Angststimmung — Rücksetzer möglich.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 62.5,
    macd_signal: 'bearish',
    volatility_30d_pct: 85.0,
    correlation_smi_1y: 0.05,
    has_six_etp: false,
    price_chf: 0.38,
    market_cap_chf: 3_500_000_000,
    price_change_24h_pct: -4.8,
    price_change_7d_pct: -12.0,
    ath_change_pct: -92.0,
    market_cap_rank: 18,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'LINK',
    name: 'Chainlink',
    signal: 'SELL',
    score: 28,
    score_components: { momentum: 7, trend: 7, sentiment: 6, markt: 5, risiko: 3 },
    signal_reason_de: 'Chainlink zeigt schwaches Momentum bei Angststimmung — Rücksetzer möglich.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 66.8,
    macd_signal: 'bearish',
    volatility_30d_pct: 80.0,
    correlation_smi_1y: 0.14,
    has_six_etp: false,
    price_chf: 12.5,
    market_cap_chf: 7_200_000_000,
    price_change_24h_pct: -5.1,
    price_change_7d_pct: -15.2,
    ath_change_pct: -78.0,
    market_cap_rank: 15,
    timestamp: '2024-01-01T00:00:00Z',
  },
  {
    ticker: 'AVAX',
    name: 'Avalanche',
    signal: 'STRONG_SELL',
    score: 18,
    score_components: { momentum: 4, trend: 5, sentiment: 4, markt: 3, risiko: 2 },
    signal_reason_de: 'Avalanche ist technisch überkauft (RSI 75) — Vorsicht bei neuem Kapital.',
    fear_greed_value: 35,
    fear_greed_label: 'Fear',
    rsi_14: 75.2,
    macd_signal: 'bearish',
    volatility_30d_pct: 95.0,
    correlation_smi_1y: 0.06,
    has_six_etp: false,
    price_chf: 22.1,
    market_cap_chf: 9_100_000_000,
    price_change_24h_pct: -7.3,
    price_change_7d_pct: -22.5,
    ath_change_pct: -90.0,
    market_cap_rank: 14,
    timestamp: '2024-01-01T00:00:00Z',
  },
];

// ── Setup: API-Mocking ────────────────────────────────────────────────────────

async function mockCryptoApi(page: Page) {
  await page.route('**/api/v1/crypto/signals', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SIGNALS) });
  });
  await page.route('**/api/v1/crypto/fear-greed', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FEAR_GREED) });
  });
}

async function setSimpleMode(page: Page) {
  // addInitScript statt evaluate: evaluate() vor dem ersten goto() läuft auf
  // about:blank (null origin), wo Chromium den Zugriff auf localStorage mit
  // einem SecurityError verweigert. addInitScript wird stattdessen erst bei
  // der nächsten Navigation im Kontext der echten Origin ausgeführt.
  await page.addInitScript(() => localStorage.setItem('prisma-mode', 'simple'));
}

async function setProMode(page: Page) {
  await page.addInitScript(() => localStorage.setItem('prisma-mode', 'pro'));
}

// ── Seiten-Grundstruktur ──────────────────────────────────────────────────────

test.describe('Krypto-Seite — Grundstruktur', () => {
  test.beforeEach(async ({ page }) => {
    await mockCryptoApi(page);
    await page.goto('/crypto');
  });

  test('zeigt Seitenheader "Krypto."', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Krypto.' })).toBeVisible();
  });

  test('zeigt Untertitel mit 10-Krypto-Beschreibung', async ({ page }) => {
    await expect(page.getByText('10 Top-Kryptowährungen')).toBeVisible();
  });

  test('zeigt "Crypto Fear & Greed Index" Label', async ({ page }) => {
    await expect(page.getByText('Crypto Fear & Greed Index')).toBeVisible();
  });

  test('zeigt Contrarian-Hinweis', async ({ page }) => {
    await expect(page.getByText(/Extreme Angst = Einstiegsgelegenheit/)).toBeVisible();
  });
});

// ── Fear & Greed Gauge ────────────────────────────────────────────────────────

test.describe('Fear & Greed Gauge', () => {
  test.beforeEach(async ({ page }) => {
    await mockCryptoApi(page);
    await page.goto('/crypto');
  });

  test('Gauge-Widget ist sichtbar', async ({ page }) => {
    await expect(page.getByTestId('fear-greed-gauge')).toBeVisible();
  });

  test('zeigt Fear&Greed-Wert 35', async ({ page }) => {
    await expect(page.getByTestId('fear-greed-value')).toContainText('35');
  });

  test('zeigt deutsches Label "Angst" für Wert 35', async ({ page }) => {
    // fearGreedLabel(35) → "Angst"
    await expect(page.getByTestId('fear-greed-gauge')).toContainText('Angst');
  });
});

// ── Simple Mode ───────────────────────────────────────────────────────────────

test.describe('Simple Mode — Beste Einstiegschancen', () => {
  test.beforeEach(async ({ page }) => {
    await mockCryptoApi(page);
    await setSimpleMode(page);
    await page.goto('/crypto');
  });

  test('zeigt Abschnitt "Beste Einstiegschancen"', async ({ page }) => {
    await expect(page.getByText('Beste Einstiegschancen')).toBeVisible();
  });

  test('zeigt exakt 3 Signal-Karten (Top-BUY)', async ({ page }) => {
    await expect(page.getByTestId('crypto-signal-card')).toHaveCount(3);
  });

  test('erste Karte zeigt Bitcoin', async ({ page }) => {
    const cards = page.getByTestId('crypto-signal-card');
    await expect(cards.first()).toContainText('Bitcoin');
  });

  test('erste Karte zeigt Score 82', async ({ page }) => {
    const cards = page.getByTestId('crypto-signal-card');
    await expect(cards.first()).toContainText('82');
  });

  test('erste Karte zeigt "STRONG BUY" Badge', async ({ page }) => {
    const cards = page.getByTestId('crypto-signal-card');
    await expect(cards.first()).toContainText('STRONG BUY');
  });

  test('erste Karte zeigt Signalgrund-Text', async ({ page }) => {
    const cards = page.getByTestId('crypto-signal-card');
    await expect(cards.first()).toContainText('technisch überverkauft');
  });

  test('Bitcoin-Karte zeigt SIX ETP Badge', async ({ page }) => {
    const btcCard = page.getByTestId('crypto-signal-card').first();
    await expect(btcCard).toContainText('SIX ETP');
  });

  test('Solana-Karte zeigt kein SIX ETP Badge', async ({ page }) => {
    // SOL ist der dritte BUY-Signal (has_six_etp=false)
    const solCard = page.getByTestId('crypto-signal-card').nth(2);
    await expect(solCard).toContainText('Solana');
    await expect(solCard).not.toContainText('SIX ETP');
  });

  test('kein Pro-Abschnitt sichtbar', async ({ page }) => {
    await expect(page.getByTestId('pro-section')).not.toBeVisible();
  });
});

// ── Pro Mode ──────────────────────────────────────────────────────────────────

test.describe('Pro Mode — Vollständige Tabelle', () => {
  test.beforeEach(async ({ page }) => {
    await mockCryptoApi(page);
    await setProMode(page);
    await page.goto('/crypto');
  });

  test('zeigt Abschnitt "Alle Signale (Pro)"', async ({ page }) => {
    await expect(page.getByText('Alle Signale (Pro)')).toBeVisible();
  });

  test('zeigt Pro-Tabellen-Header "Asset"', async ({ page }) => {
    await expect(page.getByRole('columnheader', { name: 'Asset' })).toBeVisible();
  });

  test('zeigt Pro-Tabellen-Header "Signal"', async ({ page }) => {
    await expect(page.getByRole('columnheader', { name: 'Signal' })).toBeVisible();
  });

  test('zeigt Pro-Tabellen-Header "Score"', async ({ page }) => {
    await expect(page.getByRole('columnheader', { name: 'Score' })).toBeVisible();
  });

  test('zeigt Pro-Tabellen-Header "RSI"', async ({ page }) => {
    await expect(page.getByRole('columnheader', { name: 'RSI' })).toBeVisible();
  });

  test('zeigt Pro-Tabellen-Header "SMI-Korr"', async ({ page }) => {
    await expect(page.getByRole('columnheader', { name: 'SMI-Korr' })).toBeVisible();
  });

  test('zeigt 10 Tabellenzeilen (alle Kryptos)', async ({ page }) => {
    const rows = page.locator('tbody tr');
    await expect(rows).toHaveCount(10);
  });

  test('zeigt BTC-Ticker in Tabelle', async ({ page }) => {
    await expect(page.getByRole('cell', { name: 'BTC' })).toBeVisible();
  });

  test('zeigt STRONG BUY Badge in Tabelle', async ({ page }) => {
    await expect(page.getByText('STRONG BUY')).toBeVisible();
  });

  test('zeigt STRONG SELL Badge in Tabelle', async ({ page }) => {
    await expect(page.getByText('STRONG SELL')).toBeVisible();
  });

  test('zeigt CHF-Preis für BTC', async ({ page }) => {
    await expect(page.getByText(/CHF/)).toBeVisible();
  });

  test('kein Simple-Abschnitt sichtbar', async ({ page }) => {
    await expect(page.getByTestId('simple-section')).not.toBeVisible();
  });
});

// ── Score-Aufschlüsselung (ScoreBreakdown) ───────────────────────────────────

test.describe('Pro Mode — Score-Aufschlüsselung', () => {
  test.beforeEach(async ({ page }) => {
    await mockCryptoApi(page);
    await setProMode(page);
    await page.goto('/crypto');
  });

  test('zeigt "Score-Aufschlüsselung" für erste 5 Assets', async ({ page }) => {
    const breakdownButtons = page.getByRole('button', { name: 'Score-Aufschlüsselung' });
    // Erste 5 Assets haben ScoreBreakdown
    await expect(breakdownButtons).toHaveCount(5);
  });

  test('Accordion öffnet bei Klick', async ({ page }) => {
    const firstButton = page.getByRole('button', { name: 'Score-Aufschlüsselung' }).first();
    await firstButton.click();
    // Nach Öffnen: Komponenten-Labels sichtbar
    await expect(page.getByText('Momentum')).toBeVisible();
    // exact: true, da "14d Trend"-Spaltenheader in Pro-Tabelle sonst auch matcht
    await expect(page.getByText('Trend', { exact: true })).toBeVisible();
    // exact: true, da "Sentiment" sonst auch im Seiten-Untertitel
    // ("...technisch-sentimentale Prognose...") als Substring matcht.
    await expect(page.getByText('Sentiment', { exact: true })).toBeVisible();
  });

  test('Accordion zeigt Risiko-Komponente', async ({ page }) => {
    const firstButton = page.getByRole('button', { name: 'Score-Aufschlüsselung' }).first();
    await firstButton.click();
    await expect(page.getByText('Risiko')).toBeVisible();
  });

  test('Accordion schliesst bei erneutem Klick', async ({ page }) => {
    const firstButton = page.getByRole('button', { name: 'Score-Aufschlüsselung' }).first();
    await firstButton.click();
    await expect(page.getByText('Momentum')).toBeVisible();
    await firstButton.click();
    await expect(page.getByText('Momentum')).not.toBeVisible();
  });
});

// ── Disclaimer ────────────────────────────────────────────────────────────────

test.describe('Disclaimer — immer sichtbar', () => {
  test('Disclaimer im Simple Mode sichtbar', async ({ page }) => {
    await mockCryptoApi(page);
    await setSimpleMode(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('crypto-disclaimer')).toBeVisible();
  });

  test('Disclaimer im Pro Mode sichtbar', async ({ page }) => {
    await mockCryptoApi(page);
    await setProMode(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('crypto-disclaimer')).toBeVisible();
  });

  test('Disclaimer enthält "Kein 3a-Instrument"', async ({ page }) => {
    await mockCryptoApi(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('crypto-disclaimer')).toContainText('Kein 3a-Instrument');
  });

  test('Disclaimer enthält steuerlichen Hinweis', async ({ page }) => {
    await mockCryptoApi(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('crypto-disclaimer')).toContainText('steuerfrei');
  });

  test('Disclaimer enthält "Keine Anlageberatung"', async ({ page }) => {
    await mockCryptoApi(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('crypto-disclaimer')).toContainText('keine Anlageberatung');
  });
});

// ── Modus-Toggle ──────────────────────────────────────────────────────────────

test.describe('Mode-Toggle Simple ↔ Pro', () => {
  test.beforeEach(async ({ page }) => {
    await mockCryptoApi(page);
    await setSimpleMode(page);
    await page.goto('/crypto');
  });

  test('Toggle-Schalter ist in der Navigation sichtbar', async ({ page }) => {
    const toggle = page.getByRole('switch');
    await expect(toggle).toBeVisible();
  });

  test('Klick auf Toggle wechselt zu Pro Mode', async ({ page }) => {
    const toggle = page.getByRole('switch');
    await toggle.click();
    await expect(page.getByTestId('pro-section')).toBeVisible();
    await expect(page.getByTestId('simple-section')).not.toBeVisible();
  });

  test('zweiter Klick wechselt zurück zu Simple Mode', async ({ page }) => {
    const toggle = page.getByRole('switch');
    await toggle.click();
    await toggle.click();
    await expect(page.getByTestId('simple-section')).toBeVisible();
    await expect(page.getByTestId('pro-section')).not.toBeVisible();
  });
});

// ── Navigation ────────────────────────────────────────────────────────────────

test.describe('Navigation', () => {
  test('Nav-Link "Krypto." ist von der Startseite sichtbar', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Krypto.' })).toBeVisible();
  });

  test('Nav-Link "Krypto." führt zu /crypto', async ({ page }) => {
    await mockCryptoApi(page);
    await page.goto('/');
    await page.getByRole('link', { name: 'Krypto.' }).click();
    await expect(page).toHaveURL('/crypto');
    await expect(page.getByRole('heading', { name: 'Krypto.' })).toBeVisible();
  });
});

// ── Fehlerbehandlung ──────────────────────────────────────────────────────────

test.describe('Fehlerbehandlung', () => {
  test('zeigt Fehlermeldung wenn API 500 zurückgibt', async ({ page }) => {
    await page.route('**/api/v1/crypto/signals', async (route) => {
      await route.fulfill({ status: 500, body: 'Internal Server Error' });
    });
    await page.route('**/api/v1/crypto/fear-greed', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FEAR_GREED) });
    });
    await setSimpleMode(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('signals-error')).toBeVisible();
    await expect(page.getByTestId('signals-error')).toContainText('nicht geladen werden');
  });

  test('Fehlermeldung erscheint auch im Pro Mode', async ({ page }) => {
    await page.route('**/api/v1/crypto/signals', async (route) => {
      await route.fulfill({ status: 500, body: 'Internal Server Error' });
    });
    await page.route('**/api/v1/crypto/fear-greed', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FEAR_GREED) });
    });
    await setProMode(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('signals-error')).toBeVisible();
  });

  test('Disclaimer immer sichtbar trotz API-Fehler', async ({ page }) => {
    await page.route('**/api/v1/crypto/signals', async (route) => {
      await route.fulfill({ status: 500, body: 'error' });
    });
    await page.route('**/api/v1/crypto/fear-greed', async (route) => {
      await route.fulfill({ status: 500, body: 'error' });
    });
    await page.goto('/crypto');
    await expect(page.getByTestId('crypto-disclaimer')).toBeVisible();
  });

  test('zeigt "Keine BUY-Signale" wenn alle Signale HOLD/SELL sind', async ({ page }) => {
    const onlyHoldSignals = MOCK_SIGNALS.map((s) => ({ ...s, signal: 'HOLD' as const }));
    await page.route('**/api/v1/crypto/signals', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(onlyHoldSignals) });
    });
    await page.route('**/api/v1/crypto/fear-greed', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FEAR_GREED) });
    });
    await setSimpleMode(page);
    await page.goto('/crypto');
    await expect(page.getByTestId('no-buy-signals')).toBeVisible();
    await expect(page.getByTestId('no-buy-signals')).toContainText('Keine BUY-Signale');
  });
});

// ── Go-Live-Readiness ─────────────────────────────────────────────────────────

test.describe('Go-Live Readiness', () => {
  test.beforeEach(async ({ page }) => {
    await mockCryptoApi(page);
    await page.goto('/crypto');
  });

  test('Seite hat keinen JavaScript-Fehler beim Laden', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.goto('/crypto');
    await page.waitForLoadState('networkidle');
    expect(errors).toHaveLength(0);
  });

  test('Seite ist auf Mobilgeräten (375px) korrekt dargestellt', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/crypto');
    await expect(page.getByRole('heading', { name: 'Krypto.' })).toBeVisible();
    await expect(page.getByTestId('crypto-disclaimer')).toBeVisible();
  });

  test('Seite lädt innerhalb von 5 Sekunden', async ({ page }) => {
    const start = Date.now();
    await page.goto('/crypto');
    await page.waitForLoadState('networkidle');
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(5000);
  });

  test('Krypto.-Link ist klar im Navigationsbereich auffindbar', async ({ page }) => {
    await page.goto('/');
    const link = page.getByRole('link', { name: 'Krypto.' });
    await expect(link).toBeVisible();
    await expect(link).toBeEnabled();
  });

  test('Fear & Greed Gauge zeigt Wert ohne Layout-Überlauf', async ({ page }) => {
    const gauge = page.getByTestId('fear-greed-gauge');
    await expect(gauge).toBeVisible();
    const box = await gauge.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(0);
    expect(box!.height).toBeGreaterThan(0);
  });
});
