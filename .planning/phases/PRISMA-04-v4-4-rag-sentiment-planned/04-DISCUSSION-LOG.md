# Phase 4: V4-4 RAG Sentiment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 4 - V4-4 RAG Sentiment
**Areas discussed:** Krypto-News-Quelle, Veto-Verdrahtung, Veto-Trigger-Logik, Corpus-Struktur, Backtest-Messung

---

## Krypto-News-Quelle

| Option | Description | Selected |
|--------|-------------|----------|
| CryptoPanic Free API | JSON-Endpoint, kein Auth-Token, articles haben votes + currency tags | ✓ |
| CoinDesk RSS + RssNewsAdapter | Bestehender Adapter, aber kein ticker NER für Krypto | |
| Beide (CryptoPanic + CoinDesk) | Größerer Corpus, mehr Embedding-Kosten | |

**User's choice:** CryptoPanic Free API
**Notes:** 50 Artikel pro Ingestion-Run (free API Limit). Daily scheduled, DIREKT vor Signal-Generierung (gleicher Morgen) für frischen Corpus. Dedup via url_hash, 7-Tage-TTL (soft). Fallback auf Fear&Greed wenn Corpus leer/zu alt.

---

## Veto-Verdrahtung

| Option | Description | Selected |
|--------|-------------|----------|
| Veto ändert Action + Score skaliert Size | Dual-level: hard veto + downside-only size scaling | ✓ (mit Einschränkung) |
| Nur Veto (reines Action-Override) | Nur action=HOLD, keine size-Skalierung | |
| Nur Score-Skalierung | Kein harter Override, sanfter Einfluss | |

**User's choice:** Option 1, mit wichtiger Einschränkung: size-Skalierung ist **downside-only** (Multiplikator ≤ 1.0). Positives Sentiment vergrößert die Position NICHT. Default: `SENTIMENT_ENABLED=false`, gated hinter Backtest.
**Notes:** Formel: `size_factor *= (1 + min(0, score * 0.3))`. Kein Shorting: clamp auf 0.0.

---

## Veto-Trigger-Logik

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministischer Rule-Set Python | `veto = (regime=="FEAR" and news_surprise and score < -0.3)` | ✓ |
| LLM setzt veto im Prompt | Prompt-Instruktion, subjektiv, Halluzinationsgefahr | |

**User's choice:** Deterministischer Python Rule-Set
**Notes:** LLM produziert NUR `news_surprise: bool` + `reasoning: str` (Pydantic `SentimentLLMOutput`). Score-Formel: `0.7 * votes_ratio + 0.3 * fg_norm` (≥5 Artikel), rein F&G sonst. Veto-Threshold: `score < -0.3`. LLM sieht diese Threshold nicht.

---

## Corpus-Struktur

| Option | Description | Selected |
|--------|-------------|----------|
| Bestehende news_chunks/news_documents (source='CRYPTOPANIC') | Alles wiederverwendbar, kein neuer ORM/Repo/Service | ✓ |
| Neue crypto_news_chunks-Tabelle | Sauberere Trennung, aber vollständige Duplikation | |

**User's choice:** Bestehende Tabellen wiederverwenden
**Notes:** CryptoPanic `currencies` Tags → `tickers[]` Feld direkt. Kein TickerNer-Pass nötig. 7-Tage TTL als Ingestion-Filter. `sources` in SentimentView = URLs der retrieved Chunks → automatisch in audit_trail JSONB gespeichert.

---

## Backtest-Messung

| Option | Description | Selected |
|--------|-------------|----------|
| SENTIMENT_ENABLED=true/false Env-Flag, 2× Walk-Forward | Direkter Vergleich, Sharpe/Calmar/MaxDD | ✓ |
| Separate Backtest-Tabelle mit sentiment_flag | DB-Persistenz, mehr Overhead | |

**User's choice:** Env-Flag, 2× Walk-Forward Run
**Notes:** Analog zu Meta-Labeling-Ehrlichkeit. Wenn Sentiment schadet/neutral: `SENTIMENT_ENABLED=false` bleibt Default, nur optionales konservatives Veto dokumentiert. Ehrlicher Befund in `docs/PRISMA_V4_FORTSCHRITT.md`. KEIN Threshold-Tuning zum Schönreden.

---

## Claude's Discretion

Keine Bereiche explizit an Claude delegiert.

## Deferred Ideas

- Real-time CryptoPanic-Ingestion (alle 30min) → Phase V4-6/Operations
- CoinDesk RSS oder weitere Quellen → Backlog
- UI für Sentiment-Score/news_surprise/sources → Phase V4-5
- EvaluationAgent mit Live-Sentiment-Metriken → Phase V4-6
- Trust-Scores für SentimentAnalystAgent → Phase V4-6
- `SENTIMENT_ENABLED=true` als Production-Default → nach positivem Backtest
