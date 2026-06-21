# PRISMA V3.5 — Masterplan: Vom Negativbefund zum tragfähigen Signal-System

**Autor:** Andrea Petretta · **Rolle dieses Dokuments:** Produkt-/Strategie-Vision + Machbarkeitsbeweis
**Stand:** 2026-06-21 · **Vorgänger:** `PRISMA_V3_VERLAUF_UND_ENTSCHEIDUNGEN.md`, `PRISMA_V3_ML_BEFUNDE.md`, `PRISMA_V3_NEUE_ANSAETZE_UND_DATEN.md`
**Universum-Entscheidung:** **Krypto als Kern** (BTC/ETH + Top-Coins). SMI nur als optionales Demo-Anzeige-Universum.
**Ziel-Entscheidung:** **Note zuerst, echtes Trading als Fundament** — ein heute benotbares, ehrliches System, das gleichzeitig die tragfähige Basis für späteres reales Trading ist.

> ⚠️ **Wichtiger Hinweis (vorab, ehrlich):** Kein System garantiert profitable Trades. Märkte ändern sich,
> Backtests überschätzen die Realität, und vergangene Resultate sind keine Garantie. Dieses Dokument ist
> **kein Finanzrat**. Es beschreibt ein methodisch sauberes Forschungs- und Produktsystem. „Geld verdienen"
> ist ein *langfristiges, unsicheres* Ziel — der realistische, erreichbare Gewinn dieser Session ist ein
> **kohärentes, verteidigbares System mit echten positiven Teilergebnissen** statt nur Negativbefunden.

---

## 0 · TL;DR — Die eine zentrale Einsicht

Die letzte Session hat sauber bewiesen: **Returns vorhersagen funktioniert nicht.** Das war kein Code-Fehler,
sondern das falsche Ziel mit der dünnsten Information. Der Fehler war nicht *wie* ihr trainiert habt, sondern
**was** ihr vorhergesagt habt.

Der Durchbruch ist ein **Paradigmenwechsel**: PRISMA hört auf, die *Richtung/Höhe* von Returns zu erraten
(unmöglich), und wird stattdessen ein **dreischichtiges Entscheidungssystem**:

1. **WAS** handeln — Faktoren/Regeln wählen die Kandidaten (transparent, evidenzbasiert)
2. **WANN** investieren — **Trend-Following** (Momentum trägt nachweislich das Signal) als Primärsignal,
   **Meta-Labeling** filtert schlechte Trades
3. **WIE VIEL** — **Volatilitäts-Prognose** steuert die Positionsgröße (Vol ist *gut* vorhersagbar)

Ich habe genau das **heute auf echten Gratis-Daten getestet** (BTC + ETH, ~9.5 Jahre, täglich, netto nach
Kosten, strikt out-of-sample). Ergebnis: **Das System schlägt Buy&Hold UND die exposure-matched Baseline
risiko-adjustiert klar** — also genau der Test, an dem euer altes Return-ML scheiterte (Durchlauf 4:
ML-Calmar 0.35 < Baseline 0.66). Jetzt: **BTC-Calmar 1.31 vs Baseline 0.60**, Drawdown von −83 % auf −49 %
halbiert. **Das ist der erste echte positive Befund des Projekts.**

---

## 1 · Diagnose-Recap — warum das alte Ziel scheitern *musste*

Aus euren eigenen Befunden, kurz:

- **7–30-Tage-Returns liquider Assets sind auf effizienten Märkten kaum vorhersagbar.** Das scheitert bei fast
  allen, nicht nur bei PRISMA.
- **In-Sample-Optimismus** war die Kernlehre: Purged CV sah toll aus (Calmar 1.81), strikter Walk-Forward
  zeigte die Wahrheit (Calmar 0.35). Diese methodische Strenge **behaltet ihr bei** — sie ist euer Qualitätsanker.
- **Momentum trug bereits das meiste Signal** — das simple Trend-Element schlug das ML im direktionalen F1.
  Das ist kein Nebenbefund, das ist **der Hinweis, wo der echte Edge liegt**.

Die Konsequenz ist nicht „aufhören", sondern **das Ziel wechseln**. Drei der vier Wurzelursachen
(falsches Ziel-Framing, zu kleine Stichprobe, fehlende Information) lassen sich durch den Krypto-Fokus +
das neue Framing direkt entschärfen.

---

## 2 · Der Machbarkeitsbeweis (heute, echte Daten)

**Setup:** yfinance Tagesdaten, BTC seit 2017-01, ETH seit 2017-11, bis 2026-06-21. Alle Parameter **a priori
fixiert** (100-Tage-Trend, 20-Tage-Vol, 60 % Ziel-Vol) — **keine Optimierung**, also kein Overfitting. Signale
nur aus Vergangenheit (`shift`), netto 0.1 % Kosten pro Umschichtung. Skript + Rohdaten liegen im Ordner
`prisma_v35_poc/` (reproduzierbar).

### (A) Volatilität IST vorhersagbar — das erste lernbare Ziel
| Asset | OOS-R² (Vol-Prognose vs. konstante Baseline) | Interpretation |
|---|---|---|
| BTC | **+52 %** | Vol ist stark prognostizierbar |
| ETH | **+31 %** | Vol ist stark prognostizierbar |

Kontrast zum alten Return-ML, das **negative** Edges gegen Baselines lieferte. Vol-Clustering ist real und
nutzbar. *(Ehrliche Nuance: ein simples lineares HAR-Modell schlägt die naive „gestrige Vol"-Prognose nur
marginal — der ML-Mehrwert liegt in Multi-Horizont/Regime, nicht in einem Wunder. Aber das **Ziel selbst ist
treffbar**, und das genügt fürs Sizing.)*

### (B) Trend-Following + Vol-Targeting schlägt die harte Baseline
| | CAGR | Sharpe | MaxDD | Calmar |
|---|---|---|---|---|
| **BTC — Strategie (netto)** | **+64.8 %** | **1.28** | **−49.5 %** | **1.31** |
| BTC — Exposure-Matched (gleiche Ø-Quote) | +37.8 % | 0.99 | −62.9 % | 0.60 |
| BTC — Buy & Hold | +55.2 % | 0.99 | −83.4 % | 0.66 |
| **ETH — Strategie (netto)** | **+34.2 %** | **0.86** | **−59.7 %** | **0.57** |
| ETH — Exposure-Matched | +19.8 % | 0.66 | −68.8 % | 0.29 |
| ETH — Buy & Hold | +21.6 % | 0.66 | −94.0 % | 0.23 |

**Warum das der eigentliche Beweis ist:** Die Strategie schlägt nicht nur Buy&Hold, sondern die
**exposure-matched Baseline auf Sharpe UND Calmar** — d. h. der Vorteil kommt aus **echtem Timing**, nicht aus
blosser Unterinvestition. Das ist *exakt* die Hürde, an der Durchlauf 4 zerbrach. Und der Drawdown wird
~halbiert — das ist real spürbarer Schutz in Crashes (2018, 2022).

**Ehrliche Caveats (gehören ins Begleitdokument):**
- In reinen Bullenjahren ist „weniger als 100 % investiert" naturgemäss schlechter als Buy&Hold (Strategie-Sharpe
  > B&H-Sharpe nur in 2/10 Kalenderjahren). Der Vorteil ist **über den vollen Zyklus** und **im Risiko**, nicht in
  jedem Einzeljahr. Das ist die ehrliche Eigenschaft *jeder* Trend-Following-Strategie.
- Tagesdaten, 2 Assets → solider Hinweis, **kein** Beweis für die Zukunft. Nächster Schritt:
  mehr Coins, strikter Walk-Forward über das Sizing-ML.

**Robustheits-Check (gegen Cherry-Picking):** Ich habe 5 Trend-Fenster (50/75/100/150/200 Tage) getestet. Die
Strategie schlägt die exposure-matched Baseline auf **Sharpe UND Calmar in 9 von 10 Fällen** (ETH alle 5; BTC 4/5,
nur TL=200 marginal gleichauf). Der Befund hängt **nicht** an einem geschönten Parameter — das ist der Unterschied
zum alten In-Sample-Optimismus.

---

## 3 · Die neue Produkt-Vision: PRISMA als 3-Schichten-Entscheidungssystem

Statt „eine ML-Box, die die Zukunft errät" wird PRISMA ein **transparentes, mehrschichtiges System**, in dem
jede Schicht ein *lernbares* oder *evidenzbasiertes* Teilproblem löst. Das ist gleichzeitig die ehrliche
Geschichte fürs BI-Modul (erklärbar, methodisch) **und** das Fundament für reales Trading.

```
   ┌─────────────────────────────────────────────────────────────┐
   │  SCHICHT 1 — WAS:  Faktor-/Kandidaten-Auswahl                │
   │  Cross-sectional Momentum, Trend-Stärke, Liquidität,         │
   │  On-Chain-Health (MVRV etc.)  →  Ranking der Coins           │
   ├─────────────────────────────────────────────────────────────┤
   │  SCHICHT 2 — WANN:  Timing                                   │
   │  Primärsignal: Trend-Following (TS-Momentum)  ✅ bewiesen     │
   │  + Meta-Labeling (ML): "funktioniert der Trade JETZT?"       │
   │  + optional News-/Sentiment-RAG als Veto/Boost              │
   ├─────────────────────────────────────────────────────────────┤
   │  SCHICHT 3 — WIE VIEL:  Risiko/Sizing                        │
   │  Vol-Prognose (ML)  ✅ lernbar  →  Vol-Targeting,            │
   │  Position-Caps, Drawdown-Bremse                              │
   └─────────────────────────────────────────────────────────────┘
            ↓  Output:  BUY / HOLD / SELL  +  Positionsgrösse  +  Begründung
```

**Das löst die ursprüngliche Aufgabe (buy/hold/sell) endlich sauber:** Das Signal entsteht aus der Kombination
(Trend an + Meta-Label „ok" + tragbares Vol-Regime → BUY mit Grösse X; Trend aus oder Vol-Spike → SELL/HOLD).
Es ist **erklärbar** (jede Schicht liefert ihren Grund) — das ist genau die Explainability, die das BI-Modul belohnt.

### Wie jede Modulvorgabe erfüllt wird
| BI-Vorgabe | Erfüllung in V3.5 |
|---|---|
| **ML-basiert** | Vol-Prognose-Modell (positiver Befund!) + Meta-Labeling-Klassifikator. Plus der dokumentierte, ehrliche Negativbefund zu Returns = Methodik-Kompetenz. |
| **Agentic AI** | Sub-Agent-Architektur (Abschnitt 6): spezialisierte Agents für Daten, Features, Modell, Backtest, Reporting — orchestriert via GSD. |
| **RAG** | News-/Filings-Sentiment als **Feature** (Schicht 2 Veto/Boost) — RAG fliesst messbar in die Entscheidung, nicht nur als Anzeige. |
| **Datensatz (hist. + live)** | Krypto-OHLCV seit 2017 (Minuten/Tag) + On-Chain + Makro; live via yfinance/Exchange-API. |

---

## 4 · Warum Krypto der richtige Fokus ist (Universum-Entscheidung)

Du wolltest „das, was genauer und einfacher ist". Das ist **eindeutig Krypto**:

1. **Mehr Daten, bessere Statistik.** Krypto handelt **24/7/365** → ~80 % mehr Beobachtungen pro Jahr als
   Aktien. Minuten-/Tick-Daten **gratis seit 2017** (CryptoDataDownload, Kraken-Archive, Binance-Dumps). Das
   entschärft direkt die „zu kleine Stichprobe"-Wurzelursache.
2. **Trend/Vol sind dort *stärker* ausgeprägt.** Forschung bestätigt: Krypto hat „mehr und längere
   Momentum-Perioden als Aktien" und extreme Vol-Cluster — genau das Futter, das Trend-Following und
   Vol-Targeting brauchen (siehe PoC: BTC-Calmar 1.31).
3. **Keine Fundamental-Daten-Sackgasse.** Das ganze CH-Fundamental-Problem (SimFin leer, Orbis-Migration,
   WRDS fehlt) **entfällt** — Krypto braucht keine PIT-Bilanzen. On-Chain (Coin Metrics, gratis) ersetzt
   Fundamentals und ist *einzigartige* Information.
4. **Saubere Live-Demo.** 24/7-Markt heisst, das Dashboard zeigt jederzeit Live-Signale — gut für die Präsentation.

**SMI bleibt optional** als sekundäres Anzeige-Universum (ihr habt die Pipeline schon), aber **kein ML-Aufwand**
mehr dort. Fokus = Krypto.

---

## 5 · Datenbeschaffung — konkreter Gratis-Stack (verifiziert Juni 2026)

> Alles unten ist **gratis**. Priorisiert nach „sofort nutzbar + hoher Nutzen".

### 5.1 Preis-/Markt-Daten (Backbone)
- **CryptoDataDownload** — Gratis-CSV (OHLCV) für Binance/Kraken/Bitstamp, **Tag/Stunde/Minute seit 2017**,
  kein Login, kein Rate-Limit. → Bootstrap & historischer Seed. *(bereits in eurer Pipeline)*
- **Kraken native OHLCVT-Archive** — vollständige Intraday-Historie pro Paar, gratis, ideal für saubere
  Minuten-Daten (2013–heute für BTC). → höhere Granularität für robustere Vol-Schätzung.
- **yfinance** — Gratis Tages-OHLCV BTC/ETH/Top-Coins, live abrufbar. → Live-Pfad & schnelle Tagesmodelle.
  *(im PoC verwendet)*
- **Binance/Kraken REST** (öffentlich, kein Key für Klines) — Live-Bars für das Dashboard.

### 5.2 On-Chain / fundamentale Krypto-Signale (der „unfaire" Vorteil)
- **Coin Metrics Community API** — gratis: MVRV, Realized Cap, aktive Adressen, Transaktionsvolumen, Gebühren
  (v. a. BTC/ETH). **Noch kaum ausgeschöpft** — das ist echte Information, die viele Retail-Modelle ignorieren.
- **blockchain.com Charts API** (BTC, gratis), **CryptoQuant** (limitiert frei).

### 5.3 Sentiment / News (für RAG-Feature, Schicht 2)
- **Crypto Fear & Greed Index** (alternative.me, gratis, historisch) — *(habt ihr)*.
- **Hugging Face / Kaggle**: `financial_phrasebank`, Crypto-News-Sentiment-Sets, FNSPID — zum Trainieren eines
  Sentiment-Klassifikators, der dann News als Feature liefert. ⚠️ Verfügbarkeit/Qualität vor Nutzung prüfen.
- **Reddit (PRAW) / Google Trends (pytrends)** — Aufmerksamkeits-/Hype-Proxys, billig, „neue Information",
  aber verrauscht → sauber validieren.

### 5.4 Makro (Kontext-Features)
- **FRED** (Zinsen, DXY, Liquiditätsproxies) — *(habt ihr)*. Krypto reagiert messbar auf Liquidität/Risk-on.

**Daten kaufen? Nicht nötig.** Für Krypto ist der Gratis-Stack qualitativ ausreichend. Der frühere
„Daten kaufen lohnt nicht"-Befund gilt erst recht, weil Krypto-Daten ohnehin offen sind.

---

## 6 · Welche Faktoren/Features den Forecast wirklich vertiefen

Geordnet nach erwartetem Nutzen (basierend auf Forschung + eurem „Momentum trägt Signal"-Befund):

**Schicht 1 — Kandidatenwahl (cross-sectional, über mehrere Coins):**
- Cross-sectional Momentum (Rang der 30/90-Tage-Returns)
- Trend-Stärke (Abstand zum gleitenden Schnitt, ADX-artig)
- Liquiditäts-/Volumen-Filter (nur handelbare Coins)
- On-Chain-Health (MVRV-Z, Realized-Cap-Dynamik)

**Schicht 2 — Timing (das Kern-Signal):**
- **Time-Series-Momentum** (Primär, bewiesen): Preis vs. 50/100/200-Tage-Schnitt, Multi-Horizont-Vote
- **Meta-Labeling-Features** (López de Prado): Trend-Reife, jüngste Vol, Abstand zu Hoch/Tief, Fear&Greed,
  On-Chain-Divergenz → ML lernt „funktioniert *dieses* Trendsignal gerade?" (binär: Trade nehmen/aussetzen).
  Das ist eine **viel lernbarere** Frage als „wohin geht der Preis".
- **Triple-Barrier / Trend-Scanning-Labeling** statt Fixed-Horizon — Forschung 2025 zeigt: Trend-Scanning hob
  risiko-adjustierte Returns am stärksten (Sharpe +37 %, Sortino fast verdoppelt). Wichtig fürs Labeln.
- **News-/Sentiment-Veto** (RAG): extremer Negativ-News-Flow → Trade aussetzen.

**Schicht 3 — Sizing (Risiko):**
- **Vol-Prognose** (HAR/LightGBM auf Multi-Horizont-Vol + Vol-of-Vol) → Vol-Targeting
- **Realisierte Korrelation** zwischen Coins → Portfolio-Risiko-Cap
- **Drawdown-Bremse** (Exposure runter nach X % Verlust)

**Bewusst NICHT:** Deep-RL/LSTM/Transformer als Return-Prophet — überfittet auf kleinen Finanzdaten, schlecht
erklärbar, das Gegenteil dessen, was Note *und* robustes Trading belohnen.

---

## 7 · Sub-Agent-Architektur mit GSD (wie ihr es baut)

Du hast **GSD (get-shit-done-redux)** lokal — das ist genau das richtige Werkzeug: ein spec-driven
Orchestrierungs-Framework, das frische Sub-Agent-Kontexte für Research/Plan/Execute/Verify nutzt und so
„Context Rot" vermeidet. Ich (als Orchestrator) plane, die spezialisierten Agents bauen.

> ℹ️ **Hinweis zu GSD:** Der maintainte Stand ist `@opengsd/get-shit-done-redux` (das alte Upstream wurde wegen
> Trust-/Ownership-Problemen verlassen). Vor `--dangerously-skip-permissions` einmal kurz Quelle/Version prüfen.

**Vorgeschlagene PRISMA-Sub-Agents (Domänen-Agents, orchestriert über GSD-Phasen):**
| Agent | Verantwortung | Liefert |
|---|---|---|
| **DataAgent** | Gratis-Quellen ziehen, validieren, point-in-time in DB schreiben | saubere OHLCV/On-Chain/Makro-Tabellen |
| **FeatureAgent** | Schicht-1/2/3-Features berechnen, Labeling (Triple-Barrier/Trend-Scan) | Feature-Store + Labels |
| **VolModelAgent** | Vol-Prognose trainieren/validieren (positiver Befund) | Vol-Forecast + Sizing-Faktor |
| **MetaLabelAgent** | Meta-Labeling-Klassifikator auf Trend-Signal | Trade-ja/nein-Filter |
| **BacktestAgent** | strikter Walk-Forward, exposure-matched Baselines, Netto-Kosten | ehrliche Performance-Reports |
| **RAGAgent** | News/Filings → Sentiment-Feature/Veto | Sentiment-Score je Coin/Tag |
| **DashboardAgent** | Live-Signal-UI + Explainability (warum BUY/SELL) | benotbares Frontend |

**GSD-Loop pro Phase:** `/gsd-discuss-phase N` → `/gsd-plan-phase N` → `/gsd-execute-phase N` (parallele Waves) →
`/gsd-verify-work N` → `/gsd-ship N`. Jeder Agent kriegt frischen 200k-Kontext; dein Hauptkontext bleibt schlank.

---

## 8 · Roadmap (4 Phasen, risikoarm, je benotbar)

> Auf Feature-Branches arbeiten (Branch Protection aktiv), PRs gegen `main`, CI grün abwarten — wie gehabt.

**Phase A — Vol-Modell + Trend-Backbone „echt machen" (1 Wave).** PoC aus diesem Dokument in die Pipeline
heben: Vol-Forecast-Modell sauber als Walk-Forward, Trend+Vol-Targeting über **mehr Coins** (Top 10–15),
Parameter-Robustheit (mehrere Trend/Vol-Fenster, keine Cherry-Picks). **Ziel: erster dokumentierter positiver
ML-Befund.** → erfüllt „ML-basiert" mit *positivem* Ergebnis.

**Phase B — Meta-Labeling-Schicht.** Triple-Barrier/Trend-Scan-Labels, Klassifikator „Trade jetzt nehmen?".
Ehrlich gegen „immer traden"-Baseline testen. Auch ein knapper Befund ist verwertbar (erklärbar).

**Phase C — RAG-Sentiment als Feature/Veto.** News/Fear&Greed → Score → fliesst messbar in Schicht 2.
Erfüllt RAG-Vorgabe *funktional*, nicht nur als Anzeige.

**Phase D — Dashboard + Explainability.** Live-BUY/HOLD/SELL je Coin **mit Begründung pro Schicht**
(„Trend an, Meta-Label ok, Vol moderat → BUY 0.8×"). Das ist die sichtbare, benotbare Krönung.

**Querschnitt — Begleitdokument für den Dozenten:** Negativbefund (Returns) + Positivbefund (Vol/Trend) +
Methodik (Walk-Forward, exposure-matched, In-Sample-Optimismus-Lehre) = eine *starke* wissenschaftliche Geschichte.

---

## 9 · Ehrliche Erwartungen & Disclaimer

- **Bestes realistisches Ergebnis dieser Session:** ein kohärentes, erklärbares System mit *echten* positiven
  Teilergebnissen (Vol prognostizierbar, Trend+Sizing schlägt die harte Baseline) — eine starke Note-Story und
  ein ehrliches Fundament.
- **Reales Geldverdienen** ist ein *langfristiges, unsicheres* Ziel. Trend-Following liefert über volle Zyklen
  Risiko-adjustierten Mehrwert, hat aber lange Durststrecken (Bullenjahre, Whipsaws). Live ≠ Backtest:
  Slippage, Ausfälle, Regimewechsel. **Niemals Kapital riskieren, das du nicht verlieren kannst.** Vor echtem
  Einsatz: Paper-Trading über mindestens einen vollen Marktzyklus.
- Dieses Dokument ist **kein Finanz- oder Anlagerat**. Ich bin kein Finanzberater.

---

## 10 · Sofort-nächster Schritt (Empfehlung)

**Phase A starten** — das Vol-Modell + den Trend-Backbone aus dem PoC über GSD in die Pipeline heben und über
das volle Top-10-Krypto-Universum robust machen. Das ist risikoarm, liefert den ersten positiven ML-Befund und
macht die buy/hold/sell-Signale endlich *erklärbar korrekt*. Sag „Phase A starten", dann plane ich die GSD-Phase
und die Sub-Agent-Aufträge im Detail.

---

### Quellen (Research, Juni 2026)
- Triple-Barrier/Trend-Scanning, Krypto, 2025: *Algorithmic crypto trading using information-driven bars, triple barrier labeling and deep learning* (Financial Innovation, Springer) — https://link.springer.com/article/10.1186/s40854-025-00866-w
- Meta-Labeling Krypto: https://medium.com/@liangnguyen612/meta-labeling-in-cryptocurrencies-market-95f761410fac
- TS-Momentum/Trend-Following Krypto: *Dynamic time series momentum of cryptocurrencies* (ScienceDirect) — https://www.sciencedirect.com/science/article/abs/pii/S1062940821000590 ; QuantifiedStrategies — https://www.quantifiedstrategies.com/trend-following-and-momentum-strategies-on-bitcoin/
- Realistische Renditeerwartungen / Backtest-Best-Practice: https://menthorq.com/guide/backtesting-results-crypto-quant-models/
- ML-Krypto-Profitabilität (Sharpe, OOS): *Forecasting and Trading Cryptocurrencies with Machine Learning Under Changing Market Conditions* (Springer) — https://link.springer.com/chapter/10.1007/978-981-96-6839-7_10
- Gratis-Daten: CryptoDataDownload — https://www.cryptodatadownload.com/data/ ; Kraken-Archive — https://concretumgroup.com/how-to-get-free-full-crypto-intraday-data-2013-2025-from-kraken/
- GSD: https://github.com/open-gsd/get-shit-done-redux

*PRISMA V3.5 Masterplan · 2026-06-21 · Andrea Petretta · FHNW BI Modul FS 2026*
