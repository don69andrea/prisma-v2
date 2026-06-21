# PRISMA V3 — Brainstorming neuer Ansätze & Datenquellen-Recherche

**Stand:** 2026-06-21
**Zweck:** Großanalyse — (A) Warum bisher kein Edge, (B) grundlegend neue Lösungsansätze, (C) wo es bessere/mehr historische Daten gibt, (D) Empfehlung.

> **Hinweis zur Methode:** Die Live-Websuche war beim Erstellen nicht verfügbar. Dieses Dokument
> beruht auf Fachwissen (verlässlich bis ~Mitte 2025). **Konkrete Free-Tier-Limits, Preise und
> Verfügbarkeiten unbedingt vor Nutzung gegenprüfen** — die ändern sich. Was bei uns schon
> verifiziert ist (yfinance, CryptoDataDownload, Coin Metrics, Glassnode=paid, FMP/EODHD CH=paid),
> ist als „✓ geprüft" markiert.

---

## TEIL A · Warum bisher kein Edge — die Wurzeldiagnose

Bevor wir Neues bauen: ehrlich verstehen, *warum* alles scheiterte. Vier Ursachen:

1. **Das Ziel ist fast unmöglich.** Returns liquider Assets auf 7–30 Tage vorherzusagen ist
   das Schwerste überhaupt — Märkte sind auf diesem Horizont weitgehend effizient. Das ist kein
   PRISMA-Problem, das scheitert bei fast allen.
2. **Uns fehlt die *richtige* Information.** Wir nutzten nur Preis/Technik + Makro + Fear&Greed + MVRV.
   Echten Edge holt man heute aus **Daten, die andere nicht (gut) nutzen** — nicht aus dem Modell.
   Genau diese Daten (echte PIT-Fundamentals, Analystenrevisionen, News-Sentiment in der Breite,
   Options-/Flow-Daten) hatten wir nie.
3. **Zu kleine Stichprobe.** Wenige Assets, überlappende Fenster → effektiv wenig unabhängige Beobachtungen.
4. **Falsches Ziel-Framing.** Absolute/relative Return-*Höhe* ist die härteste Größe. Andere Zielgrößen
   sind viel lernbarer (siehe Teil B).

**Die zentrale Erkenntnis:** Wir haben das schwerste Problem mit der dünnsten Information angegriffen.
Beide Stellschrauben — *was* wir vorhersagen und *womit* — sind die echten Hebel.

---

## TEIL B · Neue Lösungsansätze (durchdacht, ehrlich bewertet)

> Bewertung je Ansatz: **Lernbarkeit** (wie gut ist das Ziel überhaupt vorhersagbar) ·
> **Modul-Fit** (BI-Kriterien) · **Aufwand** · **Ehrliche Erfolgschance**.

### B1 · 🟢 Volatilität vorhersagen statt Returns — *der stärkste Reframe*
**Idee:** Nicht „wie viel steigt es" (unvorhersagbar), sondern „**wie riskant wird es**" (gut vorhersagbar).
Volatilität ist wegen Vol-Clustering eines der **am besten prognostizierbaren** Phänomene der Finanzmärkte;
ML schlägt GARCH out-of-sample regelmäßig.
**Warum besser:** Endlich ein Ziel, das das ML **wirklich treffen kann** — also ein *positiver* ML-Befund
statt nur Negativbefunde. Direkt nutzbar für **Position-Sizing & Risiko-Overlay** (Vol-Targeting:
weniger investieren wenn hohe Vol erwartet). Akademisch sauber, etabliert.
**Lernbarkeit:** hoch · **Fit:** hoch (ML + Risiko) · **Aufwand:** mittel · **Chance:** **hoch**.
→ **Top-Empfehlung.** Verwandelt „ML findet nichts" in „ML prognostiziert Risiko, und das steuert das Portfolio."

### B2 · 🟢 Meta-Labeling (López de Prado) — ML als Qualitätsfilter, nicht als Prophet
**Idee:** Das ML sagt **nicht** die Richtung voraus, sondern: „Wird das **Momentum-Signal** jetzt
funktionieren oder nicht?" (binär: Trade nehmen / aussetzen). Das Primärsignal (Momentum, das bei
uns Signal *trägt*) bleibt; das ML filtert nur die schlechten Trades raus.
**Warum besser:** „Funktioniert dieses Signal gerade?" ist eine **viel lernbarere** Frage als „wohin
geht der Preis?". Genau das Reframe, das oft funktioniert, wo direkte Vorhersage scheitert. Nutzt
unsere Erkenntnis „Momentum trägt Signal".
**Lernbarkeit:** mittel-hoch · **Fit:** hoch · **Aufwand:** mittel · **Chance:** mittel-hoch.
→ **Starke Empfehlung**, ideal kombiniert mit B1.

### B3 · 🟢 News-/RAG-Sentiment als Feature (C5) — die ungenutzte Information
**Idee:** Die vorhandene News-/Filings-RAG nicht nur als Schaufenster, sondern als **Feature**
(Sentiment, News-Surprise, Themen-Embeddings). Event-getriebene Returns (rund um News/Earnings)
sind deutlich vorhersagbarer als kontinuierliche Returns.
**Warum besser:** Die **einzige genuin neue Informationsquelle**, die wir noch nicht angefasst haben —
und sie erfüllt die **RAG-Modulvorgabe messbar** (RAG → Feature → Vorhersage, nicht nur Anzeige).
**Lernbarkeit:** mittel · **Fit:** sehr hoch (RAG!) · **Aufwand:** mittel-hoch · **Chance:** mittel.
→ **Empfehlung**, v. a. wegen Modul-Fit. Daten dafür siehe Teil C.

### B4 · 🟢 Transparentes Multi-Faktor-Modell — ehrlich, evidenzbasiert
**Idee:** Statt Black-Box-Vorhersage ein **erklärbares Faktor-Modell** (Value, Momentum, Quality,
Low-Vol, Size). Diese Faktoren haben **Jahrzehnte akademischer Evidenz** für Risikoprämien.
PRISMA rankt/scort Titel transparent nach Faktor-Exposure und backtestet das ehrlich.
**Warum besser:** Knüpft direkt an den vorhandenen `SwissQuantScorer` an, ist **erklärbar** (BI-Note!),
und steht auf solider Evidenz statt auf der Hoffnung, Returns zu „erraten". Faktor-*Prämien* sind real,
auch wenn Punkt-Vorhersagen es nicht sind.
**Lernbarkeit:** n.a. (Prämien-Harvesting) · **Fit:** hoch · **Aufwand:** mittel · **Chance:** hoch (als ehrliches System).

### B5 · 🟡 Trend-Following / Managed-Futures mit striktem Risikomanagement
**Idee:** Keine Vorhersage — die **Time-Series-Momentum-Prämie** ernten (Long bei Aufwärtstrend,
raus/short bei Abwärtstrend) mit Vol-Targeting und Stops. Eines der robustesten dokumentierten
systematischen Phänomene über 100+ Jahre und viele Assets.
**Warum besser:** Funktioniert nachweislich langfristig, braucht **keinen** prognostischen Edge.
Ehrlich als „regelbasierte Strategie mit Risikomanagement" positionierbar.
**Lernbarkeit:** n.a. · **Fit:** mittel (weniger „ML") · **Aufwand:** niedrig-mittel · **Chance:** mittel-hoch.

### B6 · 🟡 Mehr Universum / mehr Daten (US-Aktien) für echtes ML
**Idee:** Das eigentliche ML auf einem **großen US-Universum** (S&P 500/1500) mit **kostenlosen
PIT-Fundamentals aus SEC EDGAR** trainieren — dort ist die Stichprobe groß genug, damit ML überhaupt
eine Chance hat. CH/Krypto bleiben das Anwendungs-/Demo-Universum.
**Warum besser:** Löst das „zu wenig Daten"-Problem. Methodisch sauber deklarierbar.
**Lernbarkeit:** mittel · **Fit:** hoch · **Aufwand:** hoch · **Chance:** mittel.

### B7 · 🔴 Reinforcement Learning / Deep-Sequence-Modelle
**Ehrliche Einschätzung: NICHT empfohlen.** RL/LSTM/Transformer für Trading überfitten auf kleinen
Finanzdaten massiv, sind schwer zu validieren und liefern selten robusten OOS-Edge. Hoher Aufwand,
hohes Risiko, schlechte Erklärbarkeit — das Gegenteil dessen, was das BI-Modul belohnt.

### Empfohlenes neues Paket
**Kern:** **B1 (Volatilität) + B2 (Meta-Labeling) + B4 (Faktor-Modell)** — zusammen ergibt das ein
ehrliches, erklärbares System: Faktoren wählen *was*, Meta-Labeling filtert *wann*, Vol-Prognose steuert
*wie viel*. Das ist ein **kohärenter, verteidigbarer Ansatz mit echten positiven Teilergebnissen**.
**Plus B3 (News-RAG)** für den RAG-Modul-Fit. **B5** als robustes Fallback-Backbone.

---

## TEIL C · Wo gibt es (bessere) historische Daten

> Legende: **GRATIS** · **FREEMIUM** · **PAID** · **UNI** (über Hochschule oft gratis).
> ⚠️ = Free-Tier/Verfügbarkeit vor Nutzung verifizieren.

### C1 · Der vielleicht wichtigste Hebel: Hochschul-Zugänge (UNI)
- **WRDS (Wharton Research Data Services) — CRSP + Compustat.** Der **akademische Goldstandard**:
  survivorship-bias-freie Kurse + **echte point-in-time-Fundamentals**. Genau das, was uns bei
  Schweizer Fundamentals gefehlt hat. **Viele Unis (FHNW prüfen!) haben WRDS-Lizenzen für Studierende.**
  → Wenn FHNW das hat, ist das Datenproblem für die ML-Methodik **gelöst** (US + teils global). **Unbedingt prüfen.**
- **Refinitiv/Bloomberg-Terminals** in der Uni-Bibliothek — oft für Studierende nutzbar (Export limitiert).

### C2 · Kostenlose, hochwertige Quellen (GRATIS)
- **SEC EDGAR — „Financial Statement Data Sets".** Komplette US-Fundamentals als Bulk-Download,
  **point-in-time**, kostenlos, offiziell. Ideal für B6 (US-ML). Auch Volltext-Filings für News/NLP.
- **Ken French Data Library.** Fama-French-Faktoren + Momentum als fertige Zeitreihen, gratis —
  direkt für B4 (Faktor-Modell) und als Benchmark.
- **FRED (St. Louis Fed).** ✓ Makro (Zinsen, Inflation, Spreads) — nutzen wir schon.
- **SNB / SIX.** ✓ CH-Makro/Markt, offiziell.

### C3 · Kaggle & Hugging Face (GRATIS, ⚠️ Qualität prüfen)
- **Kaggle — Krypto:** umfangreiche OHLCV-Dumps (Binance/Bitstamp/Kraken, 1m–1d), „Cryptocurrency
  Historical Prices". Gut für Bootstrap (wie unser CryptoDataDownload).
- **Kaggle — Aktien:** „S&P 500 fundamentals", SimFin-Dumps, „Huge Stock Market Dataset" (US EOD).
  Meist **US-lastig** und oft nicht PIT-korrekt → für Methodik-Demo ok, für echte Fundamentals EDGAR/WRDS vorziehen.
- **Kaggle/HF — News & Sentiment (für B3):**
  - **FNSPID** (Financial News and Stock Price Integration Dataset) — Millionen News-Items mit
    Kurs-Verknüpfung. ⚠️ Name/Verfügbarkeit prüfen.
  - **Financial PhraseBank** — Standard-Sentiment-Labels für Finanztexte (Training eines Sentiment-Modells).
  - **„Daily Financial News for 6000+ stocks"**, Twitter/Reddit-Financial-Sentiment-Sets.
  - **Hugging Face Datasets:** `financial_phrasebank`, diverse `financial-news`/`stock-sentiment`-Sets,
    FinGPT-Datensätze. Direkt für RAG/Sentiment-Features.

### C4 · Aggregatoren & Freemium-APIs (FREEMIUM, ⚠️)
- **OpenBB Platform.** Open-Source-Python-Aggregator: *eine* Schnittstelle zu vielen Anbietern
  (yfinance, FMP, Polygon, Intrinio, …). Spart Adapter-Arbeit, free Provider eingebaut. **Stark für uns.**
- **Nasdaq Data Link (ex-Quandl).** Einige Gratis-Datensätze; die guten (Sharadar Fundamentals) sind PAID.
- **Alpha Vantage / Twelve Data / Polygon / Tiingo.** Freemium; ✓ Twelve Data nutzen wir teils.
  Free-Tiers eng, meist US-Fokus. ⚠️
- **yfinance.** ✓ Gratis, CH/Krypto OHLCV — unser Arbeitspferd.

### C5 · Krypto-On-Chain (GRATIS/FREEMIUM)
- **Coin Metrics Community API.** ✓ Gratis, **mehr als nur MVRV**: Realized Cap, aktive Adressen,
  Transaktionsvolumen, Gebühren u. a. (v. a. BTC/ETH). Unausgeschöpft — gut für B1/B3-Krypto-Features.
- **blockchain.com Charts API** (BTC, gratis), **CryptoQuant** (limitiert frei), **Glassnode** (✓ API = PAID).

### C6 · Alternative Daten (GRATIS, kreativ)
- **Google Trends** (`pytrends`), **Wikipedia-Pageviews** — Aufmerksamkeits-/Hype-Proxys, v. a. Krypto.
- **Reddit (PRAW) / Pushshift**, **StockTwits** — Social-Sentiment.
- Diese sind „echte neue Information" und billig — gut für B3, aber rausch-anfällig (sauber validieren!).

---

## TEIL D · Synthese & Empfehlung

**Zwei Dinge gleichzeitig ändern** (beide Wurzelursachen aus Teil A):

1. **Was wir vorhersagen → lernbarere Ziele.** Weg von Return-Prognose, hin zu
   **Volatilität (B1)** + **Meta-Labeling auf Momentum (B2)** + **transparentem Faktor-Modell (B4)**.
   Das gibt zum ersten Mal *positive*, ehrliche ML-Ergebnisse und ein kohärentes System
   (Faktoren = *was*, Meta-Label = *wann*, Vol = *wie viel*).
2. **Womit → bessere Information.** Priorität:
   a) **FHNW auf WRDS/Compustat prüfen** — wäre der größte Sprung (echte PIT-Fundamentals, gratis über Uni).
   b) **SEC EDGAR** für kostenlose US-PIT-Fundamentals (ermöglicht echtes ML auf großem Universum, B6).
   c) **News/Sentiment-Datensätze** (FNSPID/PhraseBank/HF) für B3 + RAG-Modulpunkt.
   d) **Coin Metrics breiter ausschöpfen** + Google Trends für Krypto.

**Konkret als nächster Schritt empfohlen:** Ein kleines, sauberes **Vol-Forecasting-Experiment (B1)**
auf den Daten, die wir schon haben — schnell, hohe Erfolgswahrscheinlichkeit, liefert direkt den
Risiko-/Sizing-Baustein. Parallel **klären, ob FHNW WRDS hat** (entscheidet, wie ambitioniert das
Fundamental-ML werden kann). Beides ist risikoarm und adressiert genau die Wurzelursachen — kein
weiteres Im-Kreis-Drehen am toten Return-Prognose-Ziel.

**Ehrliche Erwartung:** B1 (Vol) liefert mit hoher Wahrscheinlichkeit einen *echten* positiven Befund.
B2/B3 sind „könnte klappen". B4 ist ein solides, ehrliches System unabhängig von Prognose-Edge.
Damit hat PRISMA eine kohärente, verteidigbare und teils *positiv* belegte Geschichte — statt nur
Negativbefunde.

---

*PRISMA V3 — Neue Ansätze & Datenquellen · 2026-06-21 · Andrea Petretta · FHNW BI Modul FS 2026*
