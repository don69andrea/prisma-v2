# PRISMA V2 — Klärungen & Korrekturen (Revision 3)
## Vier offene Fragen, beantwortet nach echtem Code-Lesen

---

## 1 · DataStewardAgent: Kann er Refresh triggern?

**Ja — und das ist der Kern seines Nutzens.**

Nach dem Lesen von `scripts/ingest_filings.py` ist klar: der Ingestion-Prozess ist bereits
idempotent und sauber strukturiert. Was fehlt ist ein Agent der ihn *programmatisch* aufruft
statt manuell über die CLI.

Das Muster:

```
DataStewardAgent erkennt: "NOVN.SW Preisdaten 48h alt" (STALE)
        ↓
ruft auf: yfinance_adapter.refresh_price("NOVN.SW")
        ↓
schreibt neuen Preis in DB

DataStewardAgent erkennt: "RAG-Korpus letzte Ingestion: 18 Tage" (OUTDATED)
        ↓
ruft auf: ingest_filings.run_for_ticker("NOVN.SW")  ← gleiche Logik wie das Script
        ↓
neue Chunks → Voyage-Embedding → pgvector
```

**Was konkret geändert werden muss:**

Das heutige `scripts/ingest_filings.py` hat `async def ingest()` als Entry Point.
Diese Funktion muss refaktoriert werden zu:

```python
# scripts/ingest_filings.py — refaktoriert
async def ingest_for_ticker(ticker: str, cik: str, form_types=["10-K", "10-Q"]) -> IngestResult:
    """Callable von DataStewardAgent aus — nicht nur via CLI."""
    ...

async def ingest():
    """Bestehende CLI-Funktion — ruft ingest_for_ticker für alle _TICKERS auf."""
    for ticker in _TICKERS:
        await ingest_for_ticker(ticker, _CIK_MAP[ticker])
```

Dann kann der DataStewardAgent direkt aufrufen:

```python
class DataStewardAgent:
    async def _refresh_rag(self, ticker: str) -> None:
        """Triggert RAG-Reingestion für einen einzelnen Ticker."""
        cik = await self._cik_repo.get_cik(ticker)
        if cik is None:
            _logger.warning("%s hat keine CIK (kein SEC-Filing) — RAG-Refresh übersprungen", ticker)
            return
        result = await ingest_for_ticker(ticker, cik)
        _logger.info("RAG-Refresh %s: %d neue Chunks", ticker, result.new_chunks)

    async def _refresh_price(self, ticker: str) -> None:
        """Triggert Preis-Refresh via yfinance."""
        try:
            await self._yf_adapter.refresh_price(ticker)
        except Exception as e:
            _logger.error("Preis-Refresh %s fehlgeschlagen: %s", ticker, e)
            await self._mail_agent.send_alert(f"Preis-Refresh Fehler: {ticker}")
```

**Vollständiger DataSteward-Entscheidungsbaum:**

```
Für jeden aktiven Ticker:
  ├── Preis älter als 36h?
  │   ├── JA  → yfinance refresh → Ergebnis in Memory
  │   └── NEIN → ok, weiter
  │
  ├── Preissprung >15% seit gestern?
  │   ├── JA  → Preis quarantinieren + Mail-Alert (kein Refresh — könnte echter Crash sein)
  │   └── NEIN → ok
  │
  └── RAG-Dokument älter als 14 Tage UND Ticker hat CIK?
      ├── JA  → ingest_for_ticker() aufrufen
      └── NEIN → ok

Zusätzlich (system-weit):
  ├── SNB-Leitzins älter als 7 Tage? → SNB API forcieren + Memory aktualisieren
  └── Voyage-API nicht erreichbar? → Mail-Alert + alle Embeddings als "unverified" flaggen
```

**Wichtige Einschränkung:** Schweizer Aktien (NOVN.SW, NESN.SW) haben KEINE CIK —
CIK ist SEC-spezifisch (US-System). Der RAG-Refresh über SEC-EDGAR funktioniert also
nur für US-Tickers. Für Swiss Stocks bräuchte man SIX Exchange Filings oder
NZZ/SRF-News als Quelle — das ist eine separate Erweiterung.

---

## 2 · HITL in der Web-App — kein Claude Desktop

**Du hast recht: MCP / Claude Desktop ist falsch gedacht.**

PRISMA ist eine Web-App. Das Human-in-the-Loop muss im Browser funktionieren.
Der richtige Ansatz für eine FastAPI + Next.js Web-App: **Server-Sent Events (SSE)**.

### Warum SSE besser als WebSocket:

| | SSE | WebSocket |
|--|-----|-----------|
| Richtung | Server → Client (one-way) | Bidirektional |
| Komplexität | Einfach (HTTP) | Komplex (eigenes Protokoll) |
| FastAPI Support | Native (`EventSourceResponse`) | Extra Library |
| Reconnect | Automatisch | Manuell |
| Für diesen Use Case | Perfekt | Overkill |

Der Director schickt Events während er arbeitet → Browser zeigt sie live an →
bei einem Checkpoint-Event erscheint ein Dialog → User klickt → POST-Request zurück.

### Ablauf im Browser:

```
User: "Soll ich NOVN.SW kaufen?"
          ↓
Browser: EventSource('/api/v1/analyze/stream?ticker=NOVN.SW&...')
          ↓
Server sendet Events:
  data: {"type":"step","agent":"MarketDataAgent","status":"running"}
  data: {"type":"step","agent":"MarketDataAgent","status":"done","result":"Preis: CHF 89.40"}
  data: {"type":"step","agent":"QuantAgent","status":"running"}
  data: {"type":"step","agent":"QuantAgent","status":"done","result":"Score: 7.8/10"}
  data: {"type":"checkpoint","id":"cp_1","message":"Für welches Konto? 3a oder freie Mittel?",
         "options":["3a-Konto (VIAC)","Freie Mittel","Beides"]}
          ↓
Browser: zeigt Dialog "Für welches Konto?"
User: klickt "3a-Konto (VIAC)"
Browser: POST /api/v1/analyze/checkpoint/cp_1 {"answer": "3a"}
          ↓
Server: Director nimmt Answer entgegen, fährt weiter
  data: {"type":"step","agent":"SteuerAgent","status":"running"}
  ...
  data: {"type":"done","report_id":"rpt_abc","signal":"HOLD","confidence":0.82}
```

### Backend (FastAPI):

```python
# backend/interfaces/rest/routers/analyze.py

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse  # pip install sse-starlette
import asyncio

router = APIRouter()

@router.get("/api/v1/analyze/stream")
async def analyze_stream(ticker: str, context: str = "unknown"):
    """SSE-Endpoint: Director schickt Events während er arbeitet."""

    async def event_generator():
        run_id = str(uuid.uuid4())
        queue = asyncio.Queue()  # Director schreibt Events hier rein

        # Director in Background-Task starten
        director = get_director()
        asyncio.create_task(
            director.run_with_events(
                ticker=ticker,
                context=context,
                run_id=run_id,
                event_queue=queue,
            )
        )

        # Events aus Queue an Browser streamen
        while True:
            event = await queue.get()
            yield {"data": json.dumps(event)}
            if event.get("type") == "done" or event.get("type") == "error":
                break

    return EventSourceResponse(event_generator())


@router.post("/api/v1/analyze/checkpoint/{checkpoint_id}")
async def submit_checkpoint(checkpoint_id: str, body: CheckpointAnswer):
    """User-Antwort auf einen Director-Checkpoint."""
    director = get_director()
    await director.resolve_checkpoint(checkpoint_id, body.answer)
    return {"status": "received"}
```

### Director mit Event-Queue:

```python
class InvestmentDirector:
    async def run_with_events(
        self,
        ticker: str,
        context: str,
        run_id: str,
        event_queue: asyncio.Queue,
    ) -> None:
        """Director-Loop der Events in die Queue schreibt."""

        async def emit(event: dict) -> None:
            await event_queue.put(event)

        await emit({"type": "step", "agent": "Director", "status": "planning"})

        # MarketData
        await emit({"type": "step", "agent": "MarketDataAgent", "status": "running"})
        market_data = await self._market_agent.run(ticker)
        await emit({"type": "step", "agent": "MarketDataAgent", "status": "done",
                    "result": f"Preis: CHF {market_data.price:.2f}"})

        # Checkpoint: Kontext klären wenn unbekannt
        if context == "unknown":
            cp_id = f"cp_{uuid.uuid4().hex[:8]}"
            await emit({
                "type": "checkpoint",
                "id": cp_id,
                "message": f"Für welches Konto analysiere ich {ticker}?",
                "options": ["3a-Konto (VIAC)", "Freie Mittel", "Beides analysieren"],
            })
            # Warten bis User antwortet (max 10 Minuten)
            context = await self._wait_for_checkpoint(cp_id, timeout=600)

        # Weiter mit bekanntem Kontext...
        await emit({"type": "step", "agent": "QuantAgent", "status": "running"})
        quant = await self._quant_agent.run(market_data)
        await emit({"type": "step", "agent": "QuantAgent", "status": "done",
                    "result": f"Score: {quant.overall_score:.1f}/10"})

        # ... weitere Agents ...

        await emit({"type": "done", "run_id": run_id, "signal": report.signal,
                    "confidence": report.confidence})
```

### Frontend (Next.js):

```typescript
// frontend/app/analyze/page.tsx
const [steps, setSteps] = useState<AnalysisStep[]>([]);
const [checkpoint, setCheckpoint] = useState<Checkpoint | null>(null);

const startAnalysis = (ticker: string) => {
  const source = new EventSource(`/api/v1/analyze/stream?ticker=${ticker}`);

  source.onmessage = (e) => {
    const event = JSON.parse(e.data);

    if (event.type === "step") {
      setSteps(prev => [...prev, event]);
    }
    if (event.type === "checkpoint") {
      setCheckpoint(event);  // → zeigt Dialog im UI
    }
    if (event.type === "done") {
      source.close();
      router.push(`/report/${event.run_id}`);
    }
  };
};

const answerCheckpoint = async (checkpointId: string, answer: string) => {
  await fetch(`/api/v1/analyze/checkpoint/${checkpointId}`, {
    method: "POST",
    body: JSON.stringify({ answer }),
  });
  setCheckpoint(null);  // Dialog schliessen
};
```

**Das Ergebnis:** Der User sieht im Browser live wie der Director arbeitet —
welcher Agent gerade läuft, was er gefunden hat, und bei Unklarheit erscheint
ein Dialog. Kein Polling, kein Timeout-Problem, kein separates System.

---

## 3 · Krypto-Agent: Coins, nicht Fonds

**Klar — ETPs waren falsch gedacht. Hier ist was wirklich interessant wäre.**

### Warum die bisherige Idee (SIX ETPs) langweilig ist

ETPs sind einfach nur "kaufe Bitcoin ohne Bitcoin zu kaufen". Das ist kein
spannender analytischer Mehrwert — das ist Produktberatung.

### Was wirklich interessant ist: On-Chain Intelligence

Crypto hat im Gegensatz zu Aktien etwas einzigartiges: **öffentlich einsehbare
On-Chain-Daten**. Du kannst sehen wie viele BTC seit über einem Jahr nicht
bewegt wurden. Du kannst berechnen ob der Markt überbewertet ist. Das ist bei
Aktien unmöglich.

**Der CointelligenceAgent** nutzt diese Daten:

```
CointelligenceAgent
├── Data Sources (alle kostenlos / free-tier)
│   ├── CoinGecko API (kein API-Key nötig)
│   │   ├── Preis in USD + CHF (via CHF/USD aus MacroService)
│   │   ├── 30d Volatilität
│   │   ├── Market Cap, 24h Volume
│   │   └── Fear & Greed Index (alternative.me)
│   │
│   └── On-Chain Metriken (Glassnode free tier / CryptoQuant)
│       ├── MVRV-Z-Score (BTC): Markt vs. Realized Value — beste Überbewertungs-Metrik
│       ├── NVT-Ratio: "Krypto-KGV" — Netzwerkwert / Transaktionsvolumen
│       ├── Bitcoin Dominance: BTC-Anteil am Gesamtmarkt (Risikostimmung)
│       └── ETH Staking Yield: annualisierte Rendite aus Ethereum-Staking
│
├── Analyse-Tools (Claude Tool-Use Loop)
│   ├── get_coin_price(coin: "BTC"|"ETH") → Preis in CHF + USD
│   ├── get_mvrv_z_score() → float (>7=teuer, <0=günstig)
│   ├── get_nvt_ratio() → float
│   ├── get_fear_greed() → int (0-100)
│   ├── get_staking_yield() → float (ETH only)
│   ├── compare_sharpe_vs_smi(coin, days=365) → {crypto: float, smi: float}
│   └── get_chf_usd() → float (vom MacroService)
│
└── Output: CointelligenceReport (Pydantic)
    ├── coin: "BTC" | "ETH"
    ├── price_chf: float
    ├── mvrv_zone: "UNDERBOUGHT" | "FAIR" | "EXPENSIVE" | "EXTREME"
    ├── nvt_signal: "UNDERVALUED" | "FAIR" | "OVERVALUED"
    ├── fear_greed: int (0-100)
    ├── sharpe_1y_crypto: float
    ├── sharpe_1y_smi: float
    ├── chf_impact: str  ← CHF/USD für Schweizer Investor relevant
    ├── regime_signal: "ACCUMULATE" | "HOLD" | "CAUTION" | "AVOID"
    ├── reasoning: str  ← LLM erklärt die Kombination
    └── disclaimer: str  ← IMMER: "Hochrisikoanlage, keine Anlageberatung"
```

### Was der MVRV-Z-Score ist — und warum er wichtig ist:

```
MVRV = Market Cap / Realized Cap

Market Cap = aktueller Preis × alle Coins im Umlauf
Realized Cap = Preis jedes Coins zum Zeitpunkt seiner letzten Bewegung × Coin-Anzahl

Wenn MVRV-Z > 7:   historisch immer Markttop (2017, 2021)
Wenn MVRV-Z 3-7:   Vorsicht, Markt warm
Wenn MVRV-Z 0-3:   faire Bewertung
Wenn MVRV-Z < 0:   historisch immer gute Einstiegsmöglichkeit (2018, 2022)
```

Das ist analytisch viel interessanter als ein ETH-ETP-Preis.

### Implementation:

```python
# backend/application/agents/cointelligence_agent.py

COIN_TOOLS = [
    {
        "name": "get_coin_data",
        "description": "Aktueller Preis, Market Cap, 30d Volatilität für BTC oder ETH",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "enum": ["bitcoin", "ethereum"]}
            },
            "required": ["coin"],
        },
    },
    {
        "name": "get_mvrv_z_score",
        "description": "Bitcoin MVRV-Z-Score — Bewertungsindikator (>7=teuer, <0=günstig)",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fear_greed_index",
        "description": "Crypto Fear & Greed Index (0=extreme Angst, 100=extreme Gier)",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_sharpe_comparison",
        "description": "Vergleicht Sharpe Ratio von BTC/ETH vs. SMI über 1 Jahr",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "enum": ["BTC-USD", "ETH-USD"]}
            },
            "required": ["coin"],
        },
    },
    {
        "name": "get_chf_usd_rate",
        "description": "Aktueller CHF/USD-Kurs für Währungsadjustierung",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


async def _fetch_coingecko(coin: str) -> dict:
    """CoinGecko public API — kein API-Key nötig."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin}"
    params = {"localization": "false", "sparkline": "false"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    mdd = data["market_data"]
    return {
        "price_usd": mdd["current_price"]["usd"],
        "market_cap_usd": mdd["market_cap"]["usd"],
        "vol_24h_usd": mdd["total_volume"]["usd"],
        "price_change_30d_pct": mdd.get("price_change_percentage_30d", 0),
        "ath_usd": mdd["ath"]["usd"],
        "ath_change_pct": mdd["ath_change_percentage"]["usd"],
    }


async def _fetch_mvrv_z() -> dict:
    """
    MVRV-Z von Glassnode (free) oder LookIntoBitcoin-ähnliche Quelle.
    Glassnode free endpoint: https://api.glassnode.com/v1/metrics/market/mvrv_z_score
    Braucht API-Key (kostenlos registrierbar).
    Alternativ: CryptoQuant oder on-chain berechneter Wert via CoinGecko.
    """
    # Implementierung via Glassnode free tier
    # GLASSNODE_API_KEY aus .env
    url = "https://api.glassnode.com/v1/metrics/market/mvrv_z_score"
    params = {"a": "BTC", "api_key": settings.glassnode_api_key, "i": "24h", "f": "JSON"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        if r.status_code == 200:
            data = r.json()
            latest = data[-1]["v"] if data else None
            zone = (
                "EXTREME" if latest and latest > 7
                else "EXPENSIVE" if latest and latest > 3
                else "FAIR" if latest and latest > 0
                else "UNDERBOUGHT" if latest is not None
                else "UNKNOWN"
            )
            return {"mvrv_z": latest, "zone": zone}
    return {"mvrv_z": None, "zone": "UNKNOWN", "note": "Glassnode nicht verfügbar"}


async def _fetch_fear_greed() -> dict:
    """Alternative.me Fear & Greed Index — komplett kostenlos."""
    url = "https://api.alternative.me/fng/"
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()["data"][0]
        return {"value": int(data["value"]), "label": data["value_classification"]}


async def _calculate_sharpe(coin_yf_ticker: str, days: int = 365) -> dict:
    """Sharpe Ratio Vergleich: Coin vs. ^SSMI (SMI Index)."""
    def _sync():
        import yfinance as yf
        import numpy as np
        coin_hist = yf.Ticker(coin_yf_ticker).history(period=f"{days}d")["Close"].pct_change().dropna()
        smi_hist  = yf.Ticker("^SSMI").history(period=f"{days}d")["Close"].pct_change().dropna()
        rf = 0.0025 / 252  # SNB Leitzins 0.25% / 252

        def sharpe(r):
            if r.std() < 1e-8: return 0.0
            return float((r.mean() - rf) / r.std() * (252**0.5))

        return {"crypto_sharpe": sharpe(coin_hist), "smi_sharpe": sharpe(smi_hist)}
    return await asyncio.to_thread(_sync)


class CointelligenceAgent:
    """
    On-Chain Intelligence Agent für BTC und ETH.
    Nutzt echte Marktdaten + On-Chain-Metriken für risikobewusste Einschätzung.
    Zielgruppe: Schweizer Privatanleger mit freien Mitteln (NICHT 3a).
    """

    async def analyze(self, coin: Literal["BTC", "ETH"]) -> CointelligenceReport:
        coingecko_id = "bitcoin" if coin == "BTC" else "ethereum"
        yf_ticker = "BTC-USD" if coin == "BTC" else "ETH-USD"

        messages = [{
            "role": "user",
            "content": (
                f"Analysiere {coin} für einen Schweizer Privatanleger (freie Mittel, nicht 3a). "
                "Nutze alle Tools um ein vollständiges Bild zu bekommen. "
                "Berücksichtige: CHF-Denomination, On-Chain-Bewertung, Risikostimmung, "
                "Sharpe vs. SMI. Gib einen strukturierten CointelligenceReport zurück."
            )
        }]

        for _ in range(6):  # Max 6 Tool-Use Iterationen
            response = await self._llm.messages_create(
                model="claude-haiku-4-5",
                system=self._system_prompt(),
                messages=messages,
                tools=COIN_TOOLS,
                max_tokens=1024,
                feature="cointelligence",
            )

            if response.stop_reason == "end_turn":
                return self._parse_report(response.content[-1].text, coin)

            tool_results = await self._execute_tools(response.content, coingecko_id, yf_ticker)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return self._fallback_report(coin)

    def _system_prompt(self) -> str:
        return """Du bist ein nüchterner Krypto-Analyst der speziell für Schweizer Investoren arbeitet.

Du analysierst BTC und ETH als alternative Anlageklasse — nicht als Spekulationsobjekte.
Du berücksichtigst immer die CHF-Denomination (CHF/USD Wechselkursrisiko).
Du nutzt On-Chain-Metriken (MVRV, NVT, Fear&Greed) um Marktphasen zu identifizieren.

Output-Schema (NUR JSON):
{
  "price_chf": float,
  "mvrv_zone": "UNDERBOUGHT|FAIR|EXPENSIVE|EXTREME",
  "fear_greed": int,
  "sharpe_vs_smi": {"crypto": float, "smi": float},
  "chf_usd_impact": "GÜNSTIG|NEUTRAL|UNGÜNSTIG",
  "regime_signal": "ACCUMULATE|HOLD|CAUTION|AVOID",
  "reasoning": "Max 3 Sätze. Nüchtern, faktenbasiert.",
  "max_allocation_pct": float,  // Empfohlene Max-Allocation (0-10% für konservative Anleger)
  "disclaimer": "Kryptowährungen sind hochspekulative Anlagen..."
}

WICHTIG: 
- Nie mehr als 10% Allokation empfehlen (auch bei bullishem Signal)
- Immer Disclaimer setzen
- Bei MVRV > 5 oder Fear&Greed > 80: Signal ist CAUTION oder AVOID"""
```

### Abgrenzung zu Stocks:

Der CointelligenceAgent hat **keine Verbindung zur `SwissStock`-Entity**.
Crypto braucht kein ISIN, kein `Literal["XSWX"]`, kein CH-Präfix.
Es ist ein eigenständiger Service mit eigenen Endpoints:

```
POST /api/v1/crypto/analyze  {"coin": "BTC"}  → CointelligenceReport
POST /api/v1/crypto/analyze  {"coin": "ETH"}  → CointelligenceReport
```

Kein Ranking, kein Quant-Score, keine 3a-Eligibility — alles komplett separat.

---

## 4 · Funds (iShares, VanEck etc.) — sind sie in PRISMA?

**Nein — und sie können aktuell auch nicht rein.**

Nach dem Code-Lesen ist klar: Die `SwissStock`-Entity hat zwei harte Constraints:

```python
isin: str          # validate_ch_isin() → MUSS mit "CH" beginnen
exchange: Literal["XSWX"]  # NUR SIX Swiss Exchange
```

Ein iShares ETF (z.B. `IE00B4L5Y983` — iShares Core MSCI World) hat eine IE-ISIN
(Irland, weil UCITS-Domizil) und wäre an XETRA, Euronext oder SIX kotiert.
Die CH-ISIN-Validierung würde ihn sofort ablehnen.

**Was das bedeutet für meine früheren Konzepte:**
Mein Vorschlag "SIX-kotierte Krypto-ETPs von 21Shares" war technisch falsch gedacht.
21Shares ETPs haben CH-ISINs (z.B. AMUN.SW = CH0445689208) und könnten *technisch*
als `SwissStock` gespeichert werden — aber die Quant-Modelle (Piotroski F-Score,
P/E-Ratio, Dividendenrendite) machen für ETPs keinen Sinn. Das ist eine andere
Anlageklasse mit anderen Metriken (TER, Tracking Error, AUM, Replikationsmethode).

**Die ehrliche Antwort:**
Fonds und ETFs sind in PRISMA nicht integriert, nicht geplant, und würden
signifikante Schema-Änderungen + neue Quant-Modelle erfordern. Für das
BI-Modul-Projekt: **nicht angehen**. Fokus auf das was existiert.

---

## 5 · Zusammenfassung: Was bauen wir wirklich?

```
PRISMA V2 Multi-Agent System — finale Architektur

┌────────────────────────────────────────────────────────────────┐
│              INVESTMENT DIRECTOR                               │
│  (SSE-basierter Web-Flow, Checkpoint-Dialoge im Browser)      │
└──┬──────┬──────┬──────┬──────┬───────────────────────────────┘
   │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼
MARKET  MACRO²  QUANT STEUER REPORT     ← Stocks (Swiss)
 DATA   AGENT  AGENT  AGENT  AGENT

COINTELLIGENCE AGENT                    ← Crypto (BTC/ETH) — separat
DATA STEWARD AGENT (Background, 06:00) ← Datenpflege + Refresh-Trigger
```

| Agent | Status | Kernänderung |
|-------|--------|-------------|
| MacroAgent V2 | **Rebuild** | LLM Tool-Use statt if/elif |
| DataStewardAgent | **Neu** | Freshness + Refresh-Trigger |
| CointelligenceAgent | **Neu** | On-Chain (MVRV, Fear&Greed, Sharpe vs. SMI) |
| InvestmentDirector | **Neu** | SSE-basiert, Checkpoint-Dialoge |
| SteuerAgent | **Behalten** | Bereits solid |
| PortfolioAgent | **Mini-Extension** | Delta-View (~100 Zeilen) |
| ReportAgent | **Neu** | HTML-Dashboard |

---

*PRISMA V2 Revision 3 · 2026-06-18*
