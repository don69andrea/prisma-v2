#!/usr/bin/env python3
"""Seed script: agent_audit_trail für 10 Crypto-Coins (V4-3 SignalDirector).

Zwei Modi (automatische Wahl):
  1. API-Modus (bevorzugt): ruft GET /api/v1/agent-signal/{coin}-USD auf dem
     laufenden Backend auf — setzt voraus, dass das Backend mit FIX 2a deployed ist.
     Jeder Aufruf triggert den echten SignalDirector (inkl. LLM-Agents) und
     persistiert automatisch in agent_audit_trail.

  2. Demo-Modus (Fallback): falls Backend nicht erreichbar oder SEED_DEMO_ONLY=1
     gesetzt ist — fügt Beispiel-Einträge direkt in die DB ein. ALLE
     Reasoning-Felder sind als "[DEMO-DATEN]" markiert (Ehrlichkeits-Regel).

Usage:
    # Mit laufendem Backend (nach Docker-Rebuild):
    python scripts/seed_crypto_audit_trail.py

    # Demo-Modus erzwingen:
    SEED_DEMO_ONLY=1 python scripts/seed_crypto_audit_trail.py

    # Anderen DB-Host (für Demo-Modus):
    DATABASE_URL=postgresql+asyncpg://prisma:prisma@localhost:5432/prisma \\
        python scripts/seed_crypto_audit_trail.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
_logger = logging.getLogger(__name__)

_BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
_DEMO_ONLY = os.environ.get("SEED_DEMO_ONLY", "") == "1"
_DEFAULT_DB_URL = "postgresql+asyncpg://prisma:prisma@localhost:5432/prisma"
_API_KEY = os.environ.get("API_KEY", "")

_ALL_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "MATIC", "DOT", "LINK"]

# ---------------------------------------------------------------------------
# Mode 1: API-basierter Seed (real SignalDirector via laufendes Backend)
# ---------------------------------------------------------------------------


async def _seed_via_api(coins: list[str]) -> list[str]:
    """Ruft /api/v1/agent-signal/{coin}-USD für jeden Coin auf.

    Das Backend persistiert die Ergebnisse automatisch in agent_audit_trail.
    Gibt Liste der erfolgreich geseedeten Coins zurück.
    """
    try:
        import httpx
    except ImportError:
        _logger.warning("httpx nicht installiert — API-Modus nicht verfügbar")
        return []

    seeded: list[str] = []
    headers = {"X-API-Key": _API_KEY} if _API_KEY else {}

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Gesundheitscheck
        try:
            health = await client.get(_BACKEND_URL + "/health")
            if health.status_code != 200:
                _logger.warning("Backend nicht erreichbar (%s) — API-Modus übersprungen", health.status_code)
                return []
        except Exception as exc:
            _logger.warning("Backend nicht erreichbar (%s) — API-Modus übersprungen", exc)
            return []

        for coin in coins:
            url = f"{_BACKEND_URL}/api/v1/agent-signal/{coin}-USD"
            _logger.info("▶ %s — %s", coin, url)
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    _logger.info(
                        "  ✓ geseedet (action=%s, confidence=%.2f)",
                        data.get("action"),
                        data.get("confidence", 0),
                    )
                    seeded.append(coin)
                else:
                    _logger.warning("  ✗ HTTP %s: %s", resp.status_code, resp.text[:200])
            except Exception as exc:
                _logger.warning("  ✗ Fehler: %s", exc)

    return seeded


# ---------------------------------------------------------------------------
# Mode 2: Demo-Daten direkt in DB einfügen (ehrlich als Demo gekennzeichnet)
# ---------------------------------------------------------------------------

_DEMO = "[DEMO-DATEN] "


def _make_demo_agent_run(coin: str) -> dict[str, Any]:
    """Erstellt einen demo agent_run-Eintrag mit korrekten AgentRunDetail-Keys.

    ALLE Felder sind als Demo-Daten gekennzeichnet — niemals erfundenes
    Reasoning als echt ausgegeben (Ehrlichkeits-Regel).
    Keys spiegeln exakt AgentRunDetail (crypto_dashboard.py) + Frontend.
    """
    return {
        "technical": {
            "coin": coin,
            "stance": "NEUTRAL",
            "consensus": "0/3",
            "key_signals": [
                f"{_DEMO}Kein echtes Signal — Demo-Eintrag",
            ],
            "confidence": 0.0,
            "reasoning": (
                f"{_DEMO}Technische Analyse für {coin} wurde nicht ausgeführt. "
                "Backend-Verbindung fehlgeschlagen oder SEED_DEMO_ONLY=1. "
                "Für echte Signale: Backend starten und Seed-Script erneut ausführen."
            ),
        },
        "onchain": {
            "coin": coin,
            "valuation": "FAIR",
            "network_health": "NEUTRAL",
            "confidence": 0.0,
            "reasoning": f"{_DEMO}On-Chain-Daten für {coin} nicht ausgewertet (Demo-Eintrag).",
        },
        "sentiment": {
            "coin": coin,
            "score": 0.0,
            "regime": "NEUTRAL",
            "news_surprise": None,
            "veto": False,
            "reasoning": f"{_DEMO}Fear-&-Greed-Score nicht berechnet (Demo-Eintrag).",
            "sources": [],
        },
        "macro": {
            "regime": "NEUTRAL",
            "drivers": [f"{_DEMO}Keine Makro-Analyse (Demo-Eintrag)"],
            "confidence": 0.0,
            "reasoning": f"{_DEMO}Makro-Regime-Einschätzung: NEUTRAL (Demo-Eintrag).",
        },
        "bull": {
            "thesis": f"{_DEMO}Bull-These für {coin}: Beispieldaten, keine echte Analyse.",
            "strongest_points": [f"{_DEMO}Demo-Punkt (keine echten Daten)"],
            "risks_acknowledged": [f"{_DEMO}Demo-Risiko"],
        },
        "bear": {
            "thesis": f"{_DEMO}Bear-These für {coin}: Minority-Protection-Eintrag (Demo).",
            "strongest_points": [f"{_DEMO}Demo-Risikofaktor"],
            "counter_to_bull": [f"{_DEMO}Demo-Gegenargument"],
        },
        "risk": {
            "approve": False,
            "max_size": 0.0,
            "breaches": [f"{_DEMO}Kein echtes Risk-Assessment (Demo-Eintrag)"],
            "reasoning": (
                f"{_DEMO}Risikobewertung für {coin}: Demo-Eintrag. "
                "max_size=0.0 — kein Auto-Trading. "
                "Für echte Signale: Backend starten und Seed-Script erneut ausführen."
            ),
        },
        "trade_signal": {
            "coin": coin,
            "action": "HOLD",
            "size_factor": 0.0,
            "confidence": 0.0,
            "rationale_by_layer": {
                "technical": f"{_DEMO}Demo",
                "onchain": f"{_DEMO}Demo",
                "sentiment": f"{_DEMO}Demo",
                "macro": f"{_DEMO}Demo",
                "bull": f"{_DEMO}Demo",
                "bear": f"{_DEMO}Demo",
                "risk": f"{_DEMO}Demo",
            },
            "audit_trail_id": "00000000-0000-0000-0000-000000000000",
            "disclaimer": f"{_DEMO}Entscheidungsunterstützung, kein Anlagerat.",
        },
    }


async def _seed_demo_direct(coins: list[str], database_url: str) -> list[str]:
    """Fügt Demo-Einträge direkt in agent_audit_trail ein (kein LLM nötig).

    Idempotent: überspringt Coins, die bereits einen Eintrag für heute haben.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.infrastructure.persistence.repositories.agent_audit_trail_repository import (
        AgentAuditTrailRepository,
    )

    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    seeded: list[str] = []
    asof = date.today()

    async with async_session() as session:
        repo = AgentAuditTrailRepository(session=session)

        for coin in coins:
            existing = await repo.find_latest_by_coin(coin)
            if existing is not None and existing.asof == asof:
                _logger.info("  ↩ %s — bereits für heute geseedet, skip", coin)
                seeded.append(coin)
                continue

            agent_run = _make_demo_agent_run(coin)
            uid = await repo.insert(coin=coin, asof=asof, agent_run=agent_run)
            _logger.info("  ✓ %s — Demo-Eintrag eingefügt (id=%s)", coin, uid)
            seeded.append(coin)

        await session.commit()

    await engine.dispose()
    return seeded


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------


async def main() -> None:
    _logger.info("=== seed_crypto_audit_trail.py ===")
    _logger.info("Coins: %s", _ALL_COINS)

    seeded: list[str] = []

    if not _DEMO_ONLY:
        _logger.info("\n--- Modus 1: API-Seed (echte SignalDirector-Runs) ---")
        _logger.info("Backend: %s", _BACKEND_URL)
        seeded = await _seed_via_api(_ALL_COINS)

    missing = [c for c in _ALL_COINS if c not in seeded]

    if missing:
        if _DEMO_ONLY:
            _logger.info("\n--- Modus 2: Demo-Seed (SEED_DEMO_ONLY=1) ---")
        else:
            _logger.warning("\n%d Coins via API nicht geseedet: %s", len(missing), missing)
            _logger.info("Fallback: Demo-Daten direkt in DB einfügen …")

        database_url = os.environ.get("DATABASE_URL", _DEFAULT_DB_URL)
        if not database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        db_host = database_url.split("@")[-1] if "@" in database_url else database_url
        _logger.info("DB: %s", db_host)

        demo_seeded = await _seed_demo_direct(missing, database_url)
        seeded += demo_seeded

    _logger.info("\n=== Ergebnis ===")
    _logger.info("Geseedet: %d/%d Coins", len(seeded), len(_ALL_COINS))

    final_missing = [c for c in _ALL_COINS if c not in seeded]
    if final_missing:
        _logger.error("Fehlgeschlagen: %s", final_missing)
        sys.exit(1)

    _logger.info("✓ Seed abgeschlossen.")


if __name__ == "__main__":
    asyncio.run(main())
