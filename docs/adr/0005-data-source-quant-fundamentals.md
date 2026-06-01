# ADR 0005: Datenquelle für Quant-Fundamentaldaten

- **Status**: Accepted
- **Datum**: 2026-04-22
- **Kontext**: Phase-2-MVP — Datenversorgung der 8 Quality-Classic-Metriken (P/E, P/B, FCF Yield, Operating Margin, Dividendenrendite, D/E, EPS-Wachstum 3J, Sales-Wachstum 3J)
- **Supersedes**: Implizite Annahme in §13 des Design-Dokuments, dass yfinance zur Laufzeit als primäre Fundamentaldatenquelle dient

## Kontext

PRISMA berechnet Rankings aus 5 Modellen. Das Quality-Classic-Modell benötigt 8 Fundamentalkennzahlen pro Aktie, die aus einer externen Quelle stammen müssen. Für die Capstone-Präsentation gelten drei harte Randbedingungen:

1. **Demo-Stabilität**: Ein Netzwerkfehler oder Rate-Limit während der Abschlusspräsentation ist inakzeptabel.
2. **Reproduzierbarkeit**: Tests und Rankings müssen ohne Netzwerkzugang deterministisch reproduzierbar sein.
3. **Architektur-Sichtbarkeit**: Das Ports/Adapters-Pattern muss im Code erkennbar bleiben, weil es in die 40%-AI-Development-Achse des Bewertungsrasters einzahlt.

Scope dieses ADR: ausschliesslich die 8 Quality-Classic-Fundamentalkennzahlen. Nicht betroffen: Finnhub (News), SEC EDGAR (RAG), Preisdaten (nicht im MVP Phase 2).

## Evaluierte Optionen

### Option 1: yfinance als primäre Laufzeitquelle

- ➕ Immer aktuell — kein manueller Refresh nötig
- ➕ Kein zusätzlicher Datenpflege-Aufwand
- ➕ Einfachste Implementierung
- ➖ **Kein offizielles Rate-Limit-Versprechen** — Blocking-Fehler können jederzeit auftreten
- ➖ Netzwerkabhängigkeit während der Präsentation; Ausfall = Demo kaputt
- ➖ Nicht deterministisch — Testisolation erfordert aufwändiges Mocking
- ➖ Verletzt das Capstone-Prinzip der CLAUDE.md: externe APIs dürfen nicht direkt aus Application-Services aufgerufen werden

### Option 2: Reines CSV-Snapshot-Modell (kein Adapter im Code)

- ➕ Maximale Demo-Stabilität — keine Netzwerkabhängigkeit überhaupt
- ➕ CSV ist versioniert, diffbar und jederzeit reproduzierbar
- ➕ Tests laufen vollständig offline
- ➕ Einfachste Infrastruktur
- ➖ **Kein Adapter im Codebase** — Ports/Adapters-Pattern fehlt, schadet der Architektur-Bewertungsachse
- ➖ Kein klarer Upgrade-Pfad auf Live-Daten — spätere Migration wäre ein Rewrite
- ➖ Ohne definierte Refresh-Mechanik veraltet der Snapshot unbemerkt

### Option 3: Hybrid — CSV-Snapshot als Wahrheitsquelle, yfinance-Adapter für manuellen Refresh (gewählt)

- ➕ **Demo-Stabilität**: Laufzeit-Ranking liest ausschliesslich aus Postgres — kein externes API-Call
- ➕ **Architektur sichtbar**: Port `FundamentalsPort` + `YFinanceAdapter` existieren im Codebase (`backend/infrastructure/data/yfinance_adapter.py`)
- ➕ CSV ist committed und diffbar; Snapshot-Datum sichtbar im `snapshot_date`-Feld
- ➕ Test-Fixtures sind deterministische Golden-CSVs (konsistent mit §14.1 Design-Dokument)
- ➕ **Upgrade-Pfad additive**: Adapter ist fertig — auf Live-Fetching umschalten erfordert nur Router-Änderung, keinen Rewrite
- ➖ Datensnapshot kann zwischen Refreshes veralten
- ➖ Manuelle Refresh-Disziplin vor jeder Präsentation nötig

### Option 4: Alpha Vantage oder Finnhub als Quant-Fundamentalquelle

- ➕ Offizielle, stabile API mit definierten Rate-Limits
- ➕ Strukturiertes JSON — weniger Parsing-Aufwand als yfinance
- ➕ Alpha Vantage Free Tier verfügbar
- ➖ **25 Calls/Tag** (Alpha Vantage Free) — für 50+ Aktien unzureichend
- ➖ Finnhub Free: Fundamentaldaten-Qualität unzuverlässig, Coverage lückenhaft
- ➖ Zweiter API-Schlüssel, zweites Billing-System, zweite Fehlerquelle
- ➖ Löst das Demo-Stabilitätsproblem nicht — bleibt Netzwerkabhängigkeit
- ➖ Keine Verbesserung gegenüber Option 1 beim entscheidenden Risiko

## Entscheidung

**Option 3: Hybrid — CSV-Snapshot als Wahrheitsquelle, yfinance-Adapter für manuellen Refresh.**

- `backend/data/fundamentals_demo_2026Q1.csv` ist die versionierte Wahrheitsquelle (Seeding via Issue #14).
- Der Seed-Script lädt die CSV in die `Factsheet`-Tabelle in Postgres. Laufzeit-Rankings lesen aus Postgres — kein API-Call zur Laufzeit.
- `backend/infrastructure/data/yfinance_adapter.py` implementiert den `FundamentalsPort`. Er wird ausschliesslich durch `scripts/refresh_fundamentals.py` aufgerufen — nie durch Application-Services. Damit gilt die CLAUDE.md-Regel: externe APIs (yfinance, finnhub) müssen hinter einem Port in der Infrastruktur-Schicht liegen.
- `scripts/refresh_fundamentals.py` regeneriert die CSV vor einer Präsentation; Fehler aus dem Adapter überschreiben die committed CSV nicht.

## Konsequenzen

### Positiv

- **Deterministische Demo**: kein Netzwerk-Timeout, kein Rate-Limit-Risiko während der Abschlusspräsentation
- **Architektur-Achse erfüllt**: Port/Adapter-Pattern ist im Code nachweisbar sichtbar und dokumentiert
- **Einfache Test-Story**: Quant-Tests laufen vollständig gegen Golden-CSV-Fixtures, kein Mocking externer HTTP-Calls
- **Diffbarkeit**: CSV-Snapshot ist committed — Änderungen zwischen Refreshes sind per `git diff` sichtbar
- **Additive Weiterentwicklung**: Adapter existiert — Live-Fetching in einer späteren Milestone-Phase erfordert keinen Rewrite

### Negativ

- **Datenstaleness**: Fundamentaldaten können zwischen zwei manuellen Refreshes veralten
- **Manuelle Refresh-Disziplin**: vor jeder Präsentation muss `scripts/refresh_fundamentals.py` ausgeführt und der neue Snapshot committed werden
- **Leichte Widersprüchlichkeit**: §13 des Design-Dokuments listet yfinance als primäre Fundamentaldatenquelle — dieser ADR supersedes diese Lesart für Phase-2-MVP

### Mitigationen

- Die CSV enthält eine `snapshot_date`-Spalte; der Seed-Script loggt das Snapshot-Datum beim Start, damit Staleness sofort sichtbar ist
- `scripts/refresh_fundamentals.py` ist im `README.md` dokumentiert und wird in AI-USAGE-relevanten Dokumenten referenziert
- `DataNotAvailableError` vom Adapter wird klar geloggt; ein Refresh-Fehler lässt die committed CSV unberührt (atomares Schreiben)

### Follow-up-Entscheidungen

- Issue #14: Seed-Script implementieren (CSV-Load in `Factsheet`-Tabelle)
- `FundamentalsPort` ABC/Protocol in `backend/domain/ports/` definieren (vor Adapter-Implementierung)
- Staleness-Schwellwert für zukünftige Auto-Refresh-Logik festlegen (ausserhalb MVP-Scope)

## Referenzen

- CLAUDE.md Regel: externe APIs (yfinance, finnhub) dürfen nicht direkt aus Application-Services aufgerufen werden — müssen hinter einem Port in der Infrastruktur-Schicht liegen
- AGENTS.md: Ports/Adapters-Pattern, Verzeichniskonvention `backend/infrastructure/`
- Design-Dokument §13 (Datenquellen), §14.1 (Golden-Dataset CSV-Fixtures)
- ADR-0001: Technologie-Entscheidung PostgreSQL als primäre Datenbank
