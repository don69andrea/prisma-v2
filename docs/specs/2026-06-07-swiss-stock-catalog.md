# Spec: Swiss Stock Catalog — SIX Exchange Integration

**Issue:** #1  
**Milestone:** v2.0 Swiss Foundation  
**Date:** 2026-06-07  
**Author:** Andrea Petretta (Coding-Agent: Claude Sonnet 4.6)  
**Status:** Draft — awaiting approval

---

## Ziel

PRISMA V2 bekommt einen erweiterten Stock-Katalog mit Schweizer Titeln (SMI, SMIM, SPI) als primäres Universum. Dieses Feature legt das Fundament für alle Swiss-Layer-Issues (#2–#9): Swiss RAG, 3a-Eligibility-Filter, Langfrist-Score, ML-Kalibrierung.

---

## Nicht-Ziele

- Echtzeit- oder historische Kursdaten (→ Issue #3)
- SMIM- und SPI-Seeding (→ Issue #2)
- 3a-Eligibility-Prüfung (→ Issue #8)
- Quant-Kalibrierung für CH-Markt (→ Issue #4)
- Live-Abfrage von yfinance beim Deploy/Seed (Seed ist statisch)

---

## Architekturentscheidungen

### ADR-0008: SwissStock als eigene Domain-Entity
`SwissStock` ist kein optionales Overlay auf `Stock`, sondern eine eigenständige Domain-Entity. Begründung: Issues #2–#9 operieren auf Swiss-spezifischen Feldern (ISIN-Validierung, Exchange, 3a-Eligibility, Langfrist-Score). Eine typisierte `SwissStock`-Entity macht diese Anforderungen zur Compile-Zeit sicher.

### ADR-0009: stocks-Tabelle erweitern statt separater Table
`exchange VARCHAR(10)` und `market_cap_chf NUMERIC(18,2)` werden als nullable Spalten zur bestehenden `stocks`-Tabelle hinzugefügt. US-Stocks haben `exchange = NULL`. Kein JOIN nötig, bestehende Endpoints bleiben rückwärtskompatibel. Swiss-Abfragen nutzen partiellen Index `WHERE exchange IS NOT NULL`.

### ADR-0010: yfinance als primärer Adapter (SIX API als späteres Upgrade)
Die SIX Exchange API ist kostenpflichtig und braucht ein API-Agreement. `YFinanceSwissAdapter` nutzt das `.SW`-Suffix (z.B. `NOVN.SW`) für SIX-notierte Titel. Adapter-Skeleton wird in Issue #1 definiert; Live-Abfragen kommen mit Issue #3.

### ADR-0011: Statischer SMI-Seed
Der Seed läuft als eigenständiges Python-Skript (`scripts/seed_smi_universe.py`), **nicht** als Alembic-Migration. Schema-Änderungen gehören in Alembic; Stammdaten gehören in Scripts. Das Script ist idempotent via `ON CONFLICT (ticker) DO UPDATE`. Keine Netzabhängigkeit. Market Cap bleibt `NULL` bis Issue #3.

---

## Domain Entities

### `SwissStock` (`backend/domain/entities/swiss_stock.py`)

```python
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from uuid import UUID

from backend.domain.validators.isin import validate_ch_isin


@dataclass(frozen=True)
class SwissStock:
    id: UUID
    ticker: str                           # Ohne .SW-Suffix, uppercase (z.B. "NOVN")
    isin: str                             # CH-Prefix Pflicht, 12 Zeichen, Luhn-validiert
    name: str                             # Offizieller Firmenname
    exchange: Literal["XSWX"]            # XSWX = offizieller MIC-Code für SIX Swiss Exchange
    sector: str | None                    # GICS-Sektor
    market_cap_chf: Decimal | None        # NULL im Seed; befüllt via Issue #3
    currency: Literal["CHF"] = "CHF"     # Alle SIX-Stocks sind CHF-denominiert

    def __post_init__(self) -> None:
        if not validate_ch_isin(self.isin):
            raise ValueError(f"Ungültiges CH-ISIN: {self.isin!r}")
        object.__setattr__(self, "ticker", self.ticker.upper())
```

> **Hinweis zu `exchange`:** Der MIC-Code für die SIX Swiss Exchange lautet `XSWX`. Der Wert `"SIX"` ist der Markenname, kein Standard-Identifier. Alle 20 SMI-Titel erhalten `exchange="XSWX"`.

### ISIN-Validator (`backend/domain/validators/isin.py`)

Reine Domain-Funktion, kein I/O:

```python
def validate_ch_isin(isin: str) -> bool:
    """Prüft CH-ISIN: Format CH + 9 Ziffern + 1 Luhn-Prüfziffer (12 Zeichen total)."""
```

Regeln:
- Exakt 12 Zeichen
- Beginnt mit `CH`
- Zeichen 3–11: 9 Ziffern
- Zeichen 12: Luhn-Mod-10-Prüfziffer über die gesamte numerische Sequenz

---

## Schema-Änderungen (Datenbank)

### Migration `0013_add_swiss_fields_to_stocks.py`

```sql
ALTER TABLE stocks ADD COLUMN exchange VARCHAR(10);
ALTER TABLE stocks ADD COLUMN market_cap_chf NUMERIC(18, 2);

-- Partieller Index für performante Swiss-Only-Abfragen
CREATE INDEX ix_stocks_exchange
    ON stocks (exchange)
    WHERE exchange IS NOT NULL;
```

Kein `NOT NULL`-Constraint: bestehende US-Stocks behalten `exchange = NULL`.

### `StockORM` erweitern (`backend/infrastructure/persistence/models/stock.py`)

Zwei neue `Mapped`-Felder:
```python
exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)
market_cap_chf: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
```

---

## Repository Port

### `SwissStockRepository` (`backend/domain/repositories/swiss_stock_repository.py`)

```python
class SwissStockRepository(ABC):
    @abstractmethod
    async def get_by_ticker(self, ticker: str) -> SwissStock | None: ...

    @abstractmethod
    async def list_by_exchange(
        self,
        exchange: Literal["XSWX"] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SwissStock]: ...

    @abstractmethod
    async def upsert_batch(self, stocks: list[SwissStock]) -> int:
        """Idempotentes Einfügen/Aktualisieren. Gibt Anzahl betroffener Rows zurück."""
        ...
```

Implementierung: `SqlAlchemySwissStockRepository` in `backend/infrastructure/persistence/`.

---

## Infrastructure Adapter

### `YFinanceSwissAdapter` (`backend/infrastructure/adapters/yfinance_swiss.py`)

Skeleton für Issue #1 (vollständige Implementierung in Issue #3):

```python
class YFinanceSwissAdapter:
    """Adapter für Swiss Market Data via yfinance (.SW-Suffix für SIX-Tickers)."""

    def build_yf_ticker(self, ticker: str) -> str:
        return f"{ticker}.SW"

    async def get_stock_info(self, ticker: str) -> dict:
        """Gibt yfinance .info-Dict zurück. Timeout: 10s. Retry: 2x Exponential Backoff."""
        ...
```

Kein direkter Aufruf im Seed-Skript (statisch). Adapter wird ab Issue #3 in `SwissMarketService` injiziert.

---

## Application Layer

### `SwissMarketService` (`backend/application/services/swiss_market_service.py`)

```python
class SwissMarketService:
    def __init__(self, repo: SwissStockRepository) -> None:
        self._repo = repo

    async def get_swiss_stock(self, ticker: str) -> SwissStock | None:
        return await self._repo.get_by_ticker(ticker.upper())

    async def list_smi_stocks(self) -> list[SwissStock]:
        return await self._repo.list_by_exchange(exchange="SIX")
```

---

## API-Endpunkte

Kein neuer Router. Bestehender `GET /api/v1/stocks` bekommt optionalen Filter:

### `GET /api/v1/stocks?exchange=SIX`

**Query-Parameter:** `exchange: str | None = None`  
**Response:** Wie bisher — `StockListResponse`, aber `StockRead` bekommt:
```python
exchange: str | None = None   # rückwärtskompatibel
market_cap_chf: float | None = None
```

**Beispiel-Response (Swiss Stock):**
```json
{
  "items": [
    {
      "id": "...",
      "ticker": "NOVN",
      "name": "Novartis AG",
      "isin": "CH0012221716",
      "sector": "Healthcare",
      "country": "CH",
      "currency": "CHF",
      "exchange": "SIX",
      "market_cap_chf": null
    }
  ],
  "total": 20
}
```

---

## Seed-Skript

### `scripts/seed_smi_universe.py`

Statische Liste der 20 SMI-Konstituenten (Stand Juni 2026):

| Ticker | ISIN (vorläufig)  | Name                              | Sektor           |
|--------|-------------------|-----------------------------------|------------------|
| NOVN   | CH0012221716      | Novartis AG                       | Healthcare       |
| ROG    | CH0012032048      | Roche Holding AG                  | Healthcare       |
| NESN   | CH0038863350      | Nestlé SA                         | Consumer Staples |
| ABBN   | CH0012221716*     | ABB Ltd                           | Industrials      |
| ZURN   | CH0011075394      | Zurich Insurance Group AG         | Financials       |
| UBSG   | CH0244767585      | UBS Group AG                      | Financials       |
| CSGN   | CH0012138530*     | Credit Suisse Group AG            | Financials       |
| UHR    | CH0012255151      | The Swatch Group AG               | Consumer Disc.   |
| GEBN   | CH0030170408      | Geberit AG                        | Industrials      |
| GIVN   | CH0010645932      | Givaudan SA                       | Materials        |
| LONN   | CH0013841017      | Lonza Group AG                    | Healthcare       |
| SREN   | CH0126881561      | Swiss Re AG                       | Financials       |
| SGKN   | CH0002497458      | SGS SA                            | Industrials      |
| SLHN   | CH0014852781      | Swiss Life Holding AG             | Financials       |
| SCMN   | CH0008742519      | Swisscom AG                       | Communication    |
| BALN   | CH0012221716*     | Baloise Holding AG                | Financials       |
| HOLN   | CH0012214059      | Holcim AG                         | Materials        |
| PGHN   | CH0024608827      | Partners Group Holding AG         | Financials       |
| KRIN   | CH0334776754      | Kühne + Nagel International AG    | Industrials      |
| CFR    | CH0210483332      | Compagnie Financière Richemont SA | Consumer Disc.   |

> **Implementierungshinweis:** Mit `*` markierte ISINs sind Platzhalter. **Alle ISINs müssen bei der Implementierung via [SIX-Publikation](https://www.six-group.com/en/products-services/the-swiss-stock-exchange/market-data/shares/smi.html) oder `yf.Ticker("TICKER.SW").isin` verifiziert werden, bevor das Seed-Script committed wird.**

**Verhalten:**
- `ON CONFLICT (ticker) DO UPDATE SET exchange = EXCLUDED.exchange, ...` — idempotent
- Erstellt `Universe`-Eintrag `"SMI-20"` via `UniverseRepository` falls noch nicht vorhanden
- Läuft als eigenständiges Skript (`python scripts/seed_smi_universe.py`), nicht als Alembic-Migration

---

## Test-Cases

### Unit Tests (`tests/unit/domain/test_isin_validator.py`)

| Test | Input | Erwartet |
|------|-------|----------|
| Valides CH-ISIN | `"CH0012221716"` | `True` |
| Falsches Prefix | `"US0012221716"` | `False` |
| Zu kurz | `"CH001222171"` | `False` |
| Zu lang | `"CH00122217160"` | `False` |
| Falsche Prüfziffer | `"CH0012221715"` | `False` |
| Leerer String | `""` | `False` |
| Buchstaben in Nummernteil | `"CH001222171A"` | `False` |

### Unit Tests (`tests/unit/domain/test_swiss_stock.py`)

- `SwissStock` mit gültigem CH-ISIN erstellen → OK
- `SwissStock` mit nicht-CHF-Währung → `ValidationError`
- `ticker_must_be_uppercase` — Kleinbuchstaben werden normalisiert

### Integration Test (`tests/integration/test_swiss_catalog.py`)

```python
async def test_smi_universe_api(client, db):
    # Arrange: Seed-Skript ausführen
    # Act: GET /api/v1/stocks?exchange=SIX&limit=50
    response = await client.get("/api/v1/stocks?exchange=SIX&limit=50")
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 20
    assert all(s["currency"] == "CHF" for s in data["items"])
    assert all(s["isin"].startswith("CH") for s in data["items"])
    assert all(s["exchange"] == "SIX" for s in data["items"])
```

---

## Dateistruktur (neu)

```
backend/
├── domain/
│   ├── entities/
│   │   └── swiss_stock.py              NEU
│   ├── repositories/
│   │   └── swiss_stock_repository.py   NEU
│   └── validators/
│       └── isin.py                     NEU
├── application/
│   └── services/
│       └── swiss_market_service.py     NEU
├── infrastructure/
│   ├── adapters/
│   │   └── yfinance_swiss.py           NEU (Skeleton)
│   └── persistence/
│       ├── models/
│       │   └── stock.py                ERWEITERT (+exchange, +market_cap_chf)
│       └── repositories/
│           └── swiss_stock_repository.py  NEU
└── alembic/versions/
    └── 0013_add_swiss_fields_to_stocks.py  NEU

scripts/
└── seed_smi_universe.py                NEU

tests/
├── unit/domain/
│   ├── test_isin_validator.py          NEU
│   └── test_swiss_stock.py             NEU
└── integration/
    └── test_swiss_catalog.py           NEU
```

---

## Abhängigkeiten

**Blocks:** Issue #2, #3, #4, #8, #9  
**Blocked by:** — (kein Predecessor)  
**Neue Packages:** keine (yfinance bereits in pyproject.toml als optionale Abhängigkeit prüfen)

---

## Akzeptanzkriterien (Checkliste)

- [ ] `SwissStock`-Dataclass mit allen Feldern existiert und ist frozen
- [ ] ISIN-Validator mit Luhn-Prüfziffer implementiert und getestet (7 Unit-Test-Cases)
- [ ] Migration `0013` fügt `exchange` + `market_cap_chf` nullable hinzu
- [ ] `SwissStockRepository`-Port definiert (3 Methoden)
- [ ] `SqlAlchemySwissStockRepository` implementiert Port vollständig
- [ ] `YFinanceSwissAdapter`-Skeleton mit `.SW`-Suffix-Logik vorhanden
- [ ] `SwissMarketService` in Application-Layer implementiert
- [ ] `GET /api/v1/stocks?exchange=SIX` gibt korrekte Resultate zurück
- [ ] `StockRead`-Schema rückwärtskompatibel erweitert
- [ ] `scripts/seed_smi_universe.py` seeded 20 SMI-Tickers + "SMI-20"-Universe, idempotent
- [ ] Alle 7 ISIN-Unit-Tests grün
- [ ] Integration-Test: 20 Swiss Stocks via API abrufbar
- [ ] CI grün (ruff, mypy, pytest)
- [ ] Kein API-Key oder Ticker hardcoded im Produktionscode

---

*PRISMA V2 · Issue #1 · v2.0 Swiss Foundation · 2026-06-07*
