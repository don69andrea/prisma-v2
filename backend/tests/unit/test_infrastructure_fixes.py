"""Unit-Tests für Infrastruktur-Fixes: LLMClient.raw_client, MonteCarlo, Discovery."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# FIX-1 Voraussetzung: LLMClient muss raw_client Property exponieren
# ---------------------------------------------------------------------------


def test_llm_client_exposes_raw_client_property() -> None:
    """LLMClient muss eine `raw_client`-Property haben die den Anthropic-SDK-Client
    zurückgibt — ChatService und CryptoAgentService nutzen diese für Streaming."""
    from backend.infrastructure.llm.client import LLMClient
    from backend.infrastructure.llm.pricing import PRICING
    from backend.tests.fixtures.llm.fixture_llm_client import _NullCostLogRepository
    from backend.application.services.cost_tracker import CostTracker

    mock_anthropic = MagicMock()
    tracker = CostTracker(
        repository=_NullCostLogRepository(),
        pricing=PRICING,
        cap_usd=Decimal("20"),
    )
    llm = LLMClient(
        anthropic=mock_anthropic,
        voyage=None,
        cost_tracker=tracker,
        pricing=PRICING,
    )

    assert hasattr(llm, "raw_client"), "LLMClient fehlt `raw_client` Property (FIX-1)"
    assert llm.raw_client is mock_anthropic


# ---------------------------------------------------------------------------
# FIX-6: _run_gbm muss als öffentliche Funktion exportiert sein
# ---------------------------------------------------------------------------


def test_monte_carlo_service_exposes_public_run_gbm() -> None:
    """FIX-6: _run_gbm (private) muss als run_gbm (public) oder via MonteCarloService
    zugänglich sein — der Router darf keine private Funktion importieren."""
    import backend.application.services.monte_carlo_service as mc_module

    assert hasattr(mc_module, "run_gbm"), (
        "monte_carlo_service fehlt öffentliche `run_gbm`-Funktion. "
        "FIX-6: `_run_gbm` → `run_gbm` umbenennen und in Portfolio-Router anpassen."
    )
    assert callable(mc_module.run_gbm)


def test_portfolio_router_does_not_import_private_run_gbm() -> None:
    """FIX-6: portfolio.py Router darf `_run_gbm` nicht importieren."""
    from pathlib import Path

    router_source = (
        Path(__file__).resolve().parents[2]
        / "interfaces"
        / "rest"
        / "routers"
        / "portfolio.py"
    ).read_text()

    assert "_run_gbm" not in router_source, (
        "FIX-6: portfolio.py importiert noch `_run_gbm` (private Funktion). "
        "Auf `run_gbm` (public) umstellen."
    )


# ---------------------------------------------------------------------------
# FIX-3: Chat Router darf require_admin_api_key NICHT im Endpoint-Decorator haben
# ---------------------------------------------------------------------------


def test_chat_router_has_no_duplicate_auth_decorator() -> None:
    """FIX-3: require_admin_api_key ist schon via app.include_router(dependencies=_auth) aktiv.
    Der Endpoint-Decorator in chat.py darf es NICHT nochmal definieren."""
    from pathlib import Path

    chat_source = (
        Path(__file__).resolve().parents[2]
        / "interfaces"
        / "rest"
        / "routers"
        / "chat.py"
    ).read_text()

    # Der Decorator @router.post darf require_admin_api_key nicht als dependency haben
    # (es darf in der Datei importiert sein, aber nicht im @router.post decorator)
    assert "dependencies=[Depends(require_admin_api_key)]" not in chat_source, (
        "FIX-3: chat.py hat require_admin_api_key im Endpoint-Decorator — "
        "Doppelaufruf mit app.include_router(dependencies=_auth). Entfernen."
    )


# ---------------------------------------------------------------------------
# FIX-9: _MAX_LIVE_TICKERS und Docstring in Einklang
# ---------------------------------------------------------------------------


def test_decisions_max_live_tickers_matches_docstring() -> None:
    """FIX-9: _MAX_LIVE_TICKERS in decisions.py muss mit dem Docstring übereinstimmen."""
    from backend.interfaces.rest.routers.decisions import _MAX_LIVE_TICKERS

    # Docstring sagt "Max. 25 Ticker" aber Konstante war 12
    # Nach Fix: Konstante = 25 (oder Docstring angepasst auf 12)
    # Wir prüfen Konsistenz, nicht den spezifischen Wert
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / "interfaces"
        / "rest"
        / "routers"
        / "decisions.py"
    ).read_text()

    docstring_says_25 = "Max. 25 Ticker" in source or "Max 25 Ticker" in source

    if docstring_says_25:
        assert _MAX_LIVE_TICKERS == 25, (
            f"Docstring sagt 'Max. 25 Ticker' aber _MAX_LIVE_TICKERS={_MAX_LIVE_TICKERS}. "
            "FIX-9: Auf 25 setzen."
        )
    else:
        # Docstring wurde angepasst — Wert egal solange konsistent
        assert str(_MAX_LIVE_TICKERS) in source, (
            f"_MAX_LIVE_TICKERS={_MAX_LIVE_TICKERS} erscheint nicht im Docstring."
        )


# ---------------------------------------------------------------------------
# FIX-8: render.yaml pgvector-Kommentar
# ---------------------------------------------------------------------------


def test_render_yaml_pgvector_comment_is_not_misleading() -> None:
    """FIX-8: render.yaml darf nicht sagen pgvector müsse manuell aktiviert werden —
    Migration 0008 macht das via CREATE EXTENSION IF NOT EXISTS vector automatisch."""
    from pathlib import Path

    render_yaml = (
        Path(__file__).resolve().parents[4] / "render.yaml"
    ).read_text()

    misleading = "pgvector extension must be enabled after first deploy"
    assert misleading not in render_yaml, (
        "FIX-8: render.yaml enthält noch den irreführenden Kommentar: "
        f"'{misleading}'. Durch korrekten Hinweis auf Migration 0008 ersetzen."
    )


# ---------------------------------------------------------------------------
# FIX-4: update_smi_market_caps.py muss im Dockerfile referenziert sein
# ---------------------------------------------------------------------------


def test_dockerfile_backend_copies_update_smi_script() -> None:
    """FIX-4: Dockerfile.backend muss update_smi_market_caps.py kopieren —
    backend-start.sh ruft es auf, sonst schlägt jeder Deploy fehl."""
    from pathlib import Path

    dockerfile = (
        Path(__file__).resolve().parents[4] / "Dockerfile.backend"
    ).read_text()

    assert "update_smi_market_caps" in dockerfile, (
        "FIX-4: Dockerfile.backend kopiert update_smi_market_caps.py nicht. "
        "Der backend-start.sh-Aufruf schlägt bei jedem Deploy fehl."
    )
