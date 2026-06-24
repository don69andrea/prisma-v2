#!/usr/bin/env python3
# scripts/seed_demo_rag.py
"""Demo-Seed für swiss_rag_chunks — funktioniert ohne Voyage AI API.

Erstellt synthetische, inhaltlich realistische Schweizer Finanz-Chunks
(Jahresbericht-Snippets, Pressemitteilungen) für NESN, NOVN und ROG.
Embeddings sind deterministisch (SHA256-basiert, 2048-dim) — nur für Demo.

Idempotent via ON CONFLICT DO NOTHING (Unique Constraint: url_hash + chunk_idx).

Usage:
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_demo_rag.py
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import uuid
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deterministisches Fake-Embedding (kein Voyage AI nötig)
# ---------------------------------------------------------------------------


def _fake_embedding(text_content: str) -> list[float]:
    """Deterministischer 2048-dim Vektor aus Text-Hash. Nur für Demo."""
    seed = int(hashlib.sha256(text_content.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(2048)
    return (vec / np.linalg.norm(vec)).tolist()


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:64]


# ---------------------------------------------------------------------------
# Synthetische Swiss-Finanz-Chunks (DE)
# ---------------------------------------------------------------------------

DEMO_CHUNKS: list[dict[str, Any]] = [
    # ── NESN (Nestlé SA) ──────────────────────────────────────────────────
    {
        "ticker": "NESN",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 2, 13),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.nestle.com/sites/default/files/2025-02/2024-annual-report-de.pdf#page=12",
        "chunk_idx": 0,
        "content": (
            "Nestlé erzielte im Geschäftsjahr 2024 einen organischen Wachstum von 2,2 Prozent. "
            "Der Gesamtumsatz belief sich auf CHF 91,4 Milliarden. Das Management betont die "
            "fortlaufende Portfolio-Optimierung durch den Rückzug aus margenschwachen Kategorien "
            "sowie gezielte Investitionen in Kaffee (Nespresso, Nescafé) und Heimtiernahrung "
            "(Purina). Die Preiserhöhungen des Vorjahres wurden teilweise durch Volumenrückgänge "
            "kompensiert, was auf eine zunehmende Konsumentensensibilität gegenüber Preisen "
            "hinweist."
        ),
        "metadata": {"page": 12, "section": "Geschäftsergebnisse"},
    },
    {
        "ticker": "NESN",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 2, 13),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.nestle.com/sites/default/files/2025-02/2024-annual-report-de.pdf#page=34",
        "chunk_idx": 1,
        "content": (
            "Das bereinigte operative Ergebnis (EBIT) von Nestlé lag 2024 bei CHF 14,2 Milliarden, "
            "entsprechend einer bereinigten EBIT-Marge von 15,5 Prozent. Der freie Cash-Flow "
            "betrug CHF 9,8 Milliarden. Der Verwaltungsrat schlägt eine Dividende von CHF 3.10 "
            "je Aktie vor, was einer Erhöhung von 5 Rappen gegenüber dem Vorjahr entspricht. "
            "Dies markiert das 30. aufeinanderfolgende Jahr mit einer Dividendenerhöhung."
        ),
        "metadata": {"page": 34, "section": "Finanzielle Kennzahlen"},
    },
    {
        "ticker": "NESN",
        "source": "NZZ_RSS",
        "language": "de",
        "filing_date": date(2025, 4, 24),
        "doc_type": "PRESS_RELEASE",
        "url": "https://www.nzz.ch/wirtschaft/nestle-q1-2025-umsatz-unter-erwartungen-ld.12345",
        "chunk_idx": 0,
        "content": (
            "Nestlé hat im ersten Quartal 2025 einen organischen Umsatzrückgang von 0,4 Prozent "
            "verzeichnet und damit die Erwartungen der Analysten enttäuscht. Besonders das "
            "Nordamerika-Geschäft litt unter dem Wettbewerbsdruck bei abgepackten Lebensmitteln. "
            "CEO Laurent Freixe hält an der Jahresprognose fest und rechnet mit einer Erholung "
            "in der zweiten Jahreshälfte, getrieben durch Produktneuheiten und gezieltes "
            "Marketing-Investment."
        ),
        "metadata": {"source_name": "NZZ", "category": "Wirtschaft"},
    },
    {
        "ticker": "NESN",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 2, 13),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.nestle.com/sites/default/files/2025-02/2024-annual-report-de.pdf#page=67",
        "chunk_idx": 2,
        "content": (
            "Im Rahmen des Aktienrückkaufprogramms hat Nestlé 2024 eigene Aktien im Wert von "
            "CHF 2,0 Milliarden zurückgekauft. Das Programm soll 2025 mit einem weiteren Volumen "
            "von bis zu CHF 2,5 Milliarden fortgesetzt werden. Nestlé verfügt über ein solides "
            "Investment-Grade-Rating (Moody's Aa3, S&P AA-). Die Nettoverschuldung beträgt "
            "CHF 33,7 Milliarden, was einem Verhältnis von Nettoverschuldung zu EBITDA von "
            "2,2x entspricht."
        ),
        "metadata": {"page": 67, "section": "Kapitalallokation"},
    },
    # ── NOVN (Novartis AG) ────────────────────────────────────────────────
    {
        "ticker": "NOVN",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 1, 29),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.novartis.com/sites/default/files/2025-01/2024-annual-report-de.pdf#page=8",
        "chunk_idx": 0,
        "content": (
            "Novartis erzielte 2024 einen Nettoumsatz von USD 45,7 Milliarden, ein Plus von "
            "11 Prozent zu konstanten Wechselkursen. Das Wachstum wurde massgeblich durch "
            "Blockbuster-Medikamente wie Entresto (Herzinsuffizienz), Kisqali (Brustkrebs) "
            "und Cosentyx (Immunologie) getrieben. Das Kernbetriebsergebnis stieg um 23 Prozent "
            "auf USD 16,1 Milliarden. Die Kern-EBIT-Marge verbesserte sich auf 35,2 Prozent."
        ),
        "metadata": {"page": 8, "section": "Jahreshöhepunkte"},
    },
    {
        "ticker": "NOVN",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 1, 29),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.novartis.com/sites/default/files/2025-01/2024-annual-report-de.pdf#page=22",
        "chunk_idx": 1,
        "content": (
            "Die Forschungs- und Entwicklungsausgaben von Novartis beliefen sich 2024 auf "
            "USD 9,0 Milliarden (ca. 20 Prozent des Umsatzes). Die Produktpipeline umfasst "
            "über 100 Projekte in der klinischen Entwicklung, darunter vielversprechende "
            "Kandidaten in den Bereichen kardiovaskuläre Erkrankungen, Neurologie und "
            "Radioligandentherapie (Lutathera, 177Lu-PSMA-617). Novartis erwartet bis 2027 "
            "mehrere wichtige regulatorische Zulassungen."
        ),
        "metadata": {"page": 22, "section": "Forschung & Entwicklung"},
    },
    {
        "ticker": "NOVN",
        "source": "NZZ_RSS",
        "language": "de",
        "filing_date": date(2025, 3, 11),
        "doc_type": "PRESS_RELEASE",
        "url": "https://www.nzz.ch/wirtschaft/novartis-erhoeht-dividende-auf-usd-3-90-ld.67890",
        "chunk_idx": 0,
        "content": (
            "Novartis hat eine Dividendenerhöhung auf USD 3.90 je Aktie angekündigt, was einem "
            "Anstieg von 7 Prozent gegenüber dem Vorjahr entspricht. Der Konzern bekräftigt "
            "seine Absicht, Aktionäre durch wachsende Dividenden und Aktienrückkäufe zu "
            "entschädigen. Das Aktienrückkaufprogramm für 2025 umfasst bis zu USD 6 Milliarden. "
            "Analystenkreise sehen Novartis als defensiven Qualitätswert mit attraktivem "
            "Bewertungsniveau im Vergleich zu globalen Pharma-Peers."
        ),
        "metadata": {"source_name": "NZZ", "category": "Wirtschaft"},
    },
    {
        "ticker": "NOVN",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 1, 29),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.novartis.com/sites/default/files/2025-01/2024-annual-report-de.pdf#page=51",
        "chunk_idx": 2,
        "content": (
            "Novartis plant für 2025 ein Umsatzwachstum im mittleren bis hohen einstelligen "
            "Prozentbereich zu konstanten Wechselkursen. Das Kernbetriebsergebnis soll um "
            "einen niedrigen zweistelligen Prozentsatz wachsen. Risikofaktoren umfassen "
            "potenzielle Patentausläufe (Cosentyx ab 2029 in den USA), Generika-Konkurrenz "
            "sowie regulatorische Unsicherheiten bei der Preisfindung von Medikamenten, "
            "insbesondere im US-Markt unter dem Inflation Reduction Act."
        ),
        "metadata": {"page": 51, "section": "Ausblick 2025"},
    },
    # ── ROG (Roche Holding AG) ────────────────────────────────────────────
    {
        "ticker": "ROG",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 1, 30),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.roche.com/content/dam/rochexx/roche-com/documents/2025/2024-annual-report-de.pdf#page=6",
        "chunk_idx": 0,
        "content": (
            "Roche erzielte im Geschäftsjahr 2024 einen Umsatz von CHF 51,9 Milliarden, ein "
            "Plus von 4 Prozent zu konstanten Wechselkursen. Die Pharma-Division wuchs um "
            "5 Prozent, getragen von neuen Produkten wie Vabysmo (Augenheilkunde), Tecentriq "
            "Hybrezi und dem wachsenden Neurowissenschaften-Portfolio. Die Diagnostics-Division "
            "stabilisierte sich nach dem Covid-Rückgang und zeigte ein Wachstum von 2 Prozent."
        ),
        "metadata": {"page": 6, "section": "Finanzhöhepunkte"},
    },
    {
        "ticker": "ROG",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 1, 30),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.roche.com/content/dam/rochexx/roche-com/documents/2025/2024-annual-report-de.pdf#page=29",
        "chunk_idx": 1,
        "content": (
            "Der Core EPS von Roche stieg 2024 um 6 Prozent auf CHF 22.40 je Genussschein. "
            "Der Verwaltungsrat beantragt eine Dividendenerhöhung auf CHF 9.70 je Titel, "
            "was dem 37. aufeinanderfolgenden Dividendenwachstum entspricht. Roche gehört "
            "damit zu den wenigen Schweizer Blue Chips mit einer mehr als drei Jahrzehnte "
            "langen ununterbrochenen Dividendenwachstumshistorie. Der operative Cash-Flow "
            "betrug CHF 14,3 Milliarden."
        ),
        "metadata": {"page": 29, "section": "Dividende & Aktionärsrendite"},
    },
    {
        "ticker": "ROG",
        "source": "NZZ_RSS",
        "language": "de",
        "filing_date": date(2025, 5, 7),
        "doc_type": "PRESS_RELEASE",
        "url": "https://www.nzz.ch/wirtschaft/roche-krebsmedikament-erhalt-fda-zulassung-ld.11223",
        "chunk_idx": 0,
        "content": (
            "Roche hat von der FDA die Zulassung für sein neues Krebsmedikament Columvi "
            "(Glofitamab) in der Behandlung von diffusem grosszelligem B-Zell-Lymphom "
            "erhalten. Die Zulassung basiert auf Phase-III-Daten, die eine signifikante "
            "Verbesserung des progressionsfreien Überlebens gegenüber der Standardtherapie "
            "zeigen. Analysten schätzen das Peak-Sales-Potenzial von Columvi auf über "
            "CHF 1,5 Milliarden jährlich. Roche stärkt damit seine Onkologie-Pipeline, "
            "nachdem ältere Krebsmittel wie Avastin und Herceptin unter Biosimilar-Druck geraten sind."
        ),
        "metadata": {"source_name": "NZZ", "category": "Wirtschaft"},
    },
    {
        "ticker": "ROG",
        "source": "SIX_FILING",
        "language": "de",
        "filing_date": date(2025, 1, 30),
        "doc_type": "ANNUAL_REPORT",
        "url": "https://www.roche.com/content/dam/rochexx/roche-com/documents/2025/2024-annual-report-de.pdf#page=44",
        "chunk_idx": 2,
        "content": (
            "Roche investierte 2024 CHF 12,6 Milliarden in Forschung und Entwicklung, "
            "entsprechend 24 Prozent des Umsatzes. Schwerpunkte lagen in der Onkologie, "
            "Neurologie (Alzheimer, Multiple Sklerose) und personalisierter Medizin. "
            "Besondere Aufmerksamkeit erhielt der Alzheimer-Kandidat Gantenerumab nach "
            "dem Misserfolg in Phase III. Roche hat seine Neurowissenschaften-Strategie "
            "daraufhin auf weitere Pipeline-Kandidaten wie Trontinemab ausgerichtet."
        ),
        "metadata": {"page": 44, "section": "F&E-Investitionen"},
    },
]


# ---------------------------------------------------------------------------
# Seed-Funktion
# ---------------------------------------------------------------------------


async def seed(session: AsyncSession) -> None:
    _logger.info("Seeding %d Demo-RAG-Chunks in swiss_rag_chunks …", len(DEMO_CHUNKS))

    inserted = 0
    skipped = 0

    for chunk in DEMO_CHUNKS:
        url_hash = _url_hash(chunk["url"])
        embedding = _fake_embedding(chunk["content"])

        result = await session.execute(
            text("""
                INSERT INTO swiss_rag_chunks
                    (id, url_hash, url, ticker, source, language,
                     filing_date, doc_type, chunk_idx, content, embedding, metadata)
                VALUES
                    (:id, :url_hash, :url, :ticker, :source, :language,
                     :filing_date, :doc_type, :chunk_idx, :content, :embedding, :metadata)
                ON CONFLICT (url_hash, chunk_idx) DO NOTHING
            """),
            {
                "id": str(uuid.uuid4()),
                "url_hash": url_hash,
                "url": chunk["url"],
                "ticker": chunk["ticker"],
                "source": chunk["source"],
                "language": chunk["language"],
                "filing_date": chunk["filing_date"].isoformat(),
                "doc_type": chunk["doc_type"],
                "chunk_idx": chunk["chunk_idx"],
                "content": chunk["content"],
                "embedding": str(embedding),
                "metadata": chunk.get("metadata"),
            },
        )
        if result.rowcount == 1:
            inserted += 1
            _logger.info(
                "  ✓ [%s] chunk_idx=%d (%s)",
                chunk["ticker"],
                chunk["chunk_idx"],
                chunk["doc_type"],
            )
        else:
            skipped += 1
            _logger.info(
                "  – [%s] chunk_idx=%d bereits vorhanden, übersprungen",
                chunk["ticker"],
                chunk["chunk_idx"],
            )

    await session.commit()
    _logger.info("Seed complete: %d eingefügt, %d übersprungen.", inserted, skipped)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        _logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
