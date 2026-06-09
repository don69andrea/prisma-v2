"""Seed-Skript: ESTV-Steuerrecht-Corpus für den Steuer-Implikations-Agenten.

Erstellt Document + EmbeddingChunk-Einträge mit statischen ESTV-Inhalten.
Erfordert gesetzten VOYAGE_API_KEY und laufende DB.

Ausführung (im prisma-v2-Verzeichnis):
    python -m scripts.seed_estv_corpus
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime

# Statischer ESTV-Corpus — key rules als Text-Dokumente
_CORPUS: list[dict[str, str]] = [
    {
        "ticker": "CH",
        "doc_type": "ESTV",
        "title": "Verrechnungssteuer auf Dividenden",
        "content": (
            "Die Verrechnungssteuer (VST) beträgt 35% auf Dividenden und Zinsen von "
            "Schweizer Gesellschaften (Art. 4 VStG). Die Steuer wird an der Quelle erhoben "
            "und von der auszahlenden Gesellschaft abgeführt. Inländische Steuerpflichtige "
            "können die VST durch Deklaration in der Steuererklärung zurückfordern "
            "(Formular 103). Bei Säule-3a-Konten wird die VST-Rückerstattung durch die "
            "Vorsorgestiftung beantragt. Ausländische Anleger können die VST nur im Rahmen "
            "von Doppelbesteuerungsabkommen (DBA) teilweise zurückfordern."
        ),
        "url": "https://www.estv.admin.ch/estv/de/home/verrechnungssteuer.html",
    },
    {
        "ticker": "CH",
        "doc_type": "ESTV",
        "title": "Säule 3a — Steuerliche Behandlung",
        "content": (
            "Bei der gebundenen Selbstvorsorge (Säule 3a) sind laufende Erträge "
            "(Dividenden, Zinsen, Kursgewinne) während der Ansparphase von der "
            "Einkommens- und Vermögenssteuer befreit. Das angesparte Kapital wird "
            "bei der Auszahlung separat vom übrigen Einkommen zu einem reduzierten "
            "Satz besteuert (Vorsorgesatz, ca. 1/5 des ordentlichen Steuersatzes). "
            "Jährlich können Erwerbstätige mit Pensionskasse max. CHF 7'258 (2026) "
            "abziehen. Die VST auf Dividenden wird durch die Stiftung zurückgefordert. "
            "Bezug frühestens 5 Jahre vor Rentenalter möglich."
        ),
        "url": "https://www.estv.admin.ch/estv/de/home/direkte-bundessteuer/saeule3a.html",
    },
    {
        "ticker": "CH",
        "doc_type": "BVV2",
        "title": "BVV2 — Anlagevorschriften für berufliche Vorsorge",
        "content": (
            "BVV2 Art. 53-57 regeln die Anlagevorschriften für Pensionskassen. "
            "Aktienanlagen sind bis 50% des Vermögens zulässig (Kategorie Aktien). "
            "Für VIAC-ähnliche 3a-Anlagen (freie Vorsorge) gelten ähnliche Grundsätze. "
            "Fremdwährungsrisiken sind zu begrenzen: max. 30% ohne Währungssicherung. "
            "Einzeltitel: max. 5% pro Schuldner (Klumpenrisiko). "
            "Nachhaltigkeitskriterien: FINMA-Empfehlung für ESG-Integration."
        ),
        "url": "https://www.admin.ch/opc/de/classified-compilation/19840067/index.html",
    },
    {
        "ticker": "CH",
        "doc_type": "ESTV",
        "title": "Quellensteuer ausländische Dividenden (DA-1)",
        "content": (
            "Erhebt ein ausländischer Staat Quellensteuer auf Dividenden (z.B. USA 15-30%, "
            "Deutschland 25%), kann diese via Formular DA-1 auf die Schweizer Einkommenssteuer "
            "angerechnet werden. Voraussetzung: DBA zwischen der Schweiz und dem Quellenstaat. "
            "CH-USA DBA: max. 15% anrechenbar. CH-Deutschland DBA: max. 15% anrechenbar. "
            "Nicht anrechenbare Quellensteuer wird als Aufwand anerkannt. "
            "Bei Säule 3a: Quellensteuer-Rückforderung durch die Vorsorgestiftung."
        ),
        "url": "https://www.estv.admin.ch/estv/de/home/direkte-bundessteuer/quellensteuer/da-1.html",
    },
    {
        "ticker": "CH",
        "doc_type": "ESTV",
        "title": "Vermögenssteuer auf Wertschriften",
        "content": (
            "Börsenkotierte Aktien werden zum Kurswert per 31. Dezember der Vermögenssteuer "
            "unterworfen. Steuersätze sind kantonal unterschiedlich (ca. 0.1–0.5‰ pro CHF). "
            "Zug: 0.067‰, Schwyz: 0.075‰, Zürich: 0.3‰ (inkl. Gemeinden). "
            "Freibeträge: nat. Personen je nach Kanton CHF 50'000–200'000. "
            "Bei Säule 3a: Vorsorgevermögen ist von der Vermögenssteuer befreit. "
            "Bewertung via ESTV-Kursliste (Kurswert letzter Handelstag Dezember)."
        ),
        "url": "https://www.estv.admin.ch/estv/de/home/kantonale-steuern/vermoegenssteuer.html",
    },
]


async def main() -> None:
    import voyageai
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from backend.domain.entities.document import Document
    from backend.domain.entities.embedding_chunk import EmbeddingChunk
    from backend.domain.repositories.embedding_repository import DuplicateUrl
    from backend.infrastructure.persistence.repositories.embedding_repository import (
        SQLAEmbeddingRepository,
    )

    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://prisma:prisma@localhost:5432/prisma"
    )
    voyage_key = os.environ.get("VOYAGE_API_KEY", "")
    if not voyage_key:
        print("VOYAGE_API_KEY nicht gesetzt — überspringe Embedding-Schritt")
        return

    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    repo = SQLAEmbeddingRepository(session_factory=factory)
    voyage = voyageai.Client(api_key=voyage_key)

    now = datetime.now(UTC)
    ingested = 0

    for entry in _CORPUS:
        url = entry["url"]
        try:
            doc = Document(
                id=uuid.uuid4(),
                ticker=entry["ticker"],
                doc_type=entry["doc_type"],
                filing_date=now.date(),
                url=url,
                raw_text_hash=hashlib.sha256(entry["content"].encode()).hexdigest(),
                ingested_at=now,
            )
            await repo.save_document(doc)
        except DuplicateUrl:
            print(f"  ⏭  Bereits vorhanden: {url[:60]}")
            continue

        result = voyage.embed([entry["content"]], model="voyage-3-large")
        embedding = result.embeddings[0]

        chunk = EmbeddingChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_idx=0,
            content=entry["content"],
            embedding=embedding,
            metadata={"title": entry["title"], "doc_type": entry["doc_type"]},
        )
        await repo.save_chunks([chunk])
        print(f"  ✅ Eingebettet: {entry['title']}")
        ingested += 1

    await engine.dispose()
    print(f"\nFertig: {ingested}/{len(_CORPUS)} ESTV-Dokumente eingebettet.")


if __name__ == "__main__":
    asyncio.run(main())
