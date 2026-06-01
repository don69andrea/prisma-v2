"""Unit-Tests fuer NarrativeService — Helpers + Service-Logik."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from backend.application.services.narrative_service import (
    NarrativeService,
    UniverseContext,
    _build_universe_context,
    _extract_ranking_for_ticker,
)
from backend.domain.entities.research_memo import ResearchMemo
from backend.domain.entities.stock import Stock

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _make_service(**overrides: Any) -> NarrativeService:
    """Helper: NarrativeService mit AsyncMock-Defaults bauen (inkl. neuer Batch-Params)."""
    defaults: dict[str, Any] = {
        "memo_repository": AsyncMock(),
        "run_repository": AsyncMock(),
        "stock_repository": AsyncMock(),
        "batch_repository": AsyncMock(),
        "llm_client": AsyncMock(),
        "prompt_loader": AsyncMock(),
        "cost_tracker": AsyncMock(),
        "session_factory": Mock(),
        "stock_repo_factory": Mock(return_value=AsyncMock()),
        "run_repo_factory": Mock(return_value=AsyncMock()),
    }
    defaults.update(overrides)
    return NarrativeService(**defaults)


def _sample_results() -> list[dict[str, Any]]:
    """3-Stock-Mini-Universe."""
    return [
        {
            "ticker": "NESN",
            "total_rank": 1,
            "weighted_avg": 8.4,
            "is_sweet_spot": True,
            "per_model_ranks": {
                "quality_classic": 8,
                "alpha": 12,
                "trend_momentum": 25,
                "value_alpha_potential": 60,
                "diversification": 5,
            },
        },
        {
            "ticker": "ROG",
            "total_rank": 2,
            "weighted_avg": 12.0,
            "is_sweet_spot": False,
            "per_model_ranks": {
                "quality_classic": 15,
                "alpha": 20,
                "trend_momentum": 18,
                "value_alpha_potential": 22,
                "diversification": 10,
            },
        },
        {
            "ticker": "ABBN",
            "total_rank": 3,
            "weighted_avg": 25.0,
            "is_sweet_spot": False,
            "per_model_ranks": {
                "quality_classic": 30,
                "alpha": 28,
                "trend_momentum": 35,
                "value_alpha_potential": 18,
                "diversification": 14,
            },
        },
    ]


def test_extract_ranking_for_ticker_returns_dict() -> None:
    results = _sample_results()
    extracted = _extract_ranking_for_ticker(results, ticker="ROG")

    assert extracted["ticker"] == "ROG"
    assert extracted["total_rank"] == 2
    assert extracted["per_model_ranks"]["quality_classic"] == 15


def test_extract_ranking_for_ticker_raises_when_missing() -> None:
    results = _sample_results()
    with pytest.raises(KeyError):
        _extract_ranking_for_ticker(results, ticker="UNKNOWN")


def test_build_universe_context_computes_correct_metrics() -> None:
    results = _sample_results()
    ctx = _build_universe_context(results)

    assert isinstance(ctx, UniverseContext)
    assert ctx.n_stocks == 3
    assert ctx.median_rank == 2  # median of [1, 2, 3]
    # 20%-Quantile von [1,2,3] mit linear interpolation: 1 + 0.4*(2-1) = 1.4 → round to 1 (we use int)
    # but exact computation depends on implementation; assert reasonable bounds
    assert 1 <= ctx.top20_threshold <= 2


def test_build_universe_context_with_one_stock() -> None:
    """Edge case: Universe mit nur 1 Stock — median=top20=1."""
    results = [
        {
            "ticker": "NESN",
            "total_rank": 1,
            "weighted_avg": 1.0,
            "is_sweet_spot": True,
            "per_model_ranks": {},
        }
    ]
    ctx = _build_universe_context(results)
    assert ctx.n_stocks == 1
    assert ctx.median_rank == 1
    assert ctx.top20_threshold == 1


# ---------------------------------------------------------------------------
# Task 6 — NarrativeService.get_memo
# ---------------------------------------------------------------------------


def _sample_memo(
    stock_id: Any = None,
    run_id: Any = None,
    *,
    one_liner: str = "Kurzfassung des Memos.",
    confidence: Literal["low", "medium", "high"] = "high",
    model_version: str = "claude-sonnet-4-6",
    language: Literal["de", "en"] = "de",
) -> ResearchMemo:
    return ResearchMemo(
        id=uuid4(),
        stock_id=stock_id or uuid4(),
        model_run_id=run_id or uuid4(),
        language=language,
        created_at=datetime.now(tz=UTC),
        one_liner=one_liner,
        ranking_interpretation="x" * 120,
        sweet_spot=True,
        sweet_spot_explanation=None,
        contradictions=[],
        key_strengths=["Top 10% Quality"],
        key_risks=["Bewertungs-Multiples nicht im Modell"],
        confidence=confidence,
        model_version=model_version,
    )


async def test_get_memo_returns_existing() -> None:
    stock_id, run_id = uuid4(), uuid4()
    expected = _sample_memo(stock_id=stock_id, run_id=run_id)

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=expected)

    service = _make_service(memo_repository=memo_repo)
    result = await service.get_memo(stock_id, run_id)

    assert result is expected
    memo_repo.get.assert_awaited_once_with(stock_id, run_id, language="de")


async def test_get_memo_returns_none_when_missing() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)

    service = _make_service(memo_repository=memo_repo)
    result = await service.get_memo(uuid4(), uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# Task 7 — NarrativeService.generate_memo
# ---------------------------------------------------------------------------


def _stock(stock_id: Any | None = None, ticker: str = "NESN") -> Stock:
    return Stock(
        id=stock_id or uuid4(),
        ticker=ticker,
        name="Nestle SA",
        isin="CH0038863350",
        sector="Consumer Staples",
        country="CH",
        currency="CHF",
    )


def _tool_use_response(memo_payload: dict[str, Any]) -> Any:
    """Imitiert Anthropic-Response mit Tool-Use-Block."""
    return SimpleNamespace(
        id="msg_test",
        usage=SimpleNamespace(input_tokens=2300, output_tokens=487),
        content=[SimpleNamespace(type="tool_use", name="submit_memo", input=memo_payload)],
        stop_reason="tool_use",
    )


async def test_generate_memo_returns_cached_when_exists_and_no_force() -> None:
    stock_id, run_id = uuid4(), uuid4()
    cached = _sample_memo(stock_id=stock_id, run_id=run_id)

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=cached)
    memo_repo.save = AsyncMock()

    llm = AsyncMock()
    service = _make_service(
        memo_repository=memo_repo,
        llm_client=llm,
    )

    result = await service.generate_memo(stock_id, run_id, force_regenerate=False)

    assert result is cached
    memo_repo.save.assert_not_awaited()
    llm.messages_create.assert_not_awaited()


async def test_generate_memo_happy_path() -> None:
    stock_id, run_id = uuid4(), uuid4()

    # Persisted memo (was die DB nach save() haelt — das was der Service zurueckgibt)
    persisted = _sample_memo(stock_id=stock_id, run_id=run_id, one_liner="Defensiver Quality-Kern.")

    memo_repo = AsyncMock()
    # 1. Call: Cache-Check → None. 2. Call: Reload nach save() → persisted.
    memo_repo.get = AsyncMock(side_effect=[None, persisted])
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))

    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensiver Quality-Kern.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "Top 25% in 4 Modellen.",
        "contradictions": [],
        "key_strengths": ["Top 10% Quality"],
        "key_risks": ["Bewertungs-Multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))

    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: f"<rendered-{name}>"))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id)

    # LLM wurde aufgerufen
    llm.messages_create.assert_awaited_once()
    call_kwargs = llm.messages_create.await_args.kwargs

    # System ist eine Liste mit cache_control
    assert isinstance(call_kwargs["system"], list)
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

    # Tool-use forced
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "submit_memo"}
    assert any(t["name"] == "submit_memo" for t in call_kwargs["tools"])

    # feature-Tag fuer Cost-Tracking
    assert call_kwargs["feature"] == "narrative_engine"

    # Memo wurde persistiert
    memo_repo.save.assert_awaited_once()
    saved = memo_repo.save.await_args.args[0]
    assert saved.stock_id == stock_id
    assert saved.model_run_id == run_id
    assert saved.one_liner == "Defensiver Quality-Kern."

    # B3: Returnwert ist die persisted Row (nicht die in-memory Entity).
    assert result is persisted


async def test_generate_memo_force_regenerate_returns_persisted_not_inmemory() -> None:
    """B3 (PR #64 review): Bei force_regenerate=True macht das Repo ein UPSERT,
    DB-Row behaelt die Original-id und Original-created_at. Service muss die
    persisted Row zurueckgeben, sonst driftet die response-id von der DB-id.
    """
    stock_id, run_id = uuid4(), uuid4()

    # Persisted Memo: simuliert die DB-Row mit *originalem* id + created_at
    # (anders als das was der Service intern via uuid4()/datetime.now() generiert).
    persisted = _sample_memo(stock_id=stock_id, run_id=run_id, one_liner="Defensiver Quality-Kern.")

    memo_repo = AsyncMock()
    # force_regenerate=True ueberspringt den Cache-Check → get() wird nur
    # einmal nach save() aufgerufen (Reload).
    memo_repo.get = AsyncMock(return_value=persisted)
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensiver Quality-Kern.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "Top 25% in 4 Modellen.",
        "contradictions": [],
        "key_strengths": ["Top 10% Quality"],
        "key_risks": ["Bewertungs-Multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: f"<rendered-{name}>"))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id, force_regenerate=True)

    # save() bekam die in-memory Entity (mit neuer uuid4 und neuem created_at)
    memo_repo.save.assert_awaited_once()
    saved = memo_repo.save.await_args.args[0]

    # Sanity-Check des Bug-Szenarios: in-memory id != persisted id
    assert saved.id != persisted.id

    # Service liefert die persisted Row mit stabiler id + created_at
    assert result is persisted
    assert result.id == persisted.id
    assert result.created_at == persisted.created_at

    # Reload-Aufruf nach save() — exakt einmal mit den richtigen Args
    memo_repo.get.assert_awaited_once_with(stock_id, run_id, language="de")


async def test_generate_memo_404_when_stock_missing() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=None)

    service = _make_service(
        memo_repository=memo_repo,
        stock_repository=stock_repo,
    )

    with pytest.raises(LookupError, match="Stock"):
        await service.generate_memo(uuid4(), uuid4())


async def test_generate_memo_404_when_run_missing() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock())
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=None)

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
    )

    with pytest.raises(LookupError, match="Run"):
        await service.generate_memo(uuid4(), uuid4())


async def test_generate_memo_404_when_stock_not_in_run() -> None:
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(return_value=None)
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(ticker="UNKNOWN"))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())  # nur NESN/ROG/ABBN

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
    )

    with pytest.raises(LookupError, match="UNKNOWN"):
        await service.generate_memo(uuid4(), uuid4())


async def test_generate_memo_renders_en_templates() -> None:
    """EN-Slice: bei language='en' werden narrative_system.en.md.j2 und
    narrative_user.en.md.j2 geladen — Spy auf prompt_loader.render verifiziert das.
    Ersetzt den B2-Guard-Test (PR #64) nach EN-Template-Aktivierung.
    """
    stock_id, run_id = uuid4(), uuid4()
    persisted = _sample_memo(stock_id=stock_id, run_id=run_id, language="en")

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(side_effect=[None, persisted])
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))

    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensive quality core.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "Top 25% in 4 models.",
        "contradictions": [],
        "key_strengths": ["Top 10% quality"],
        "key_risks": ["Valuation multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))

    render_calls: list[str] = []

    def _track_render(name: str, ctx: dict[str, Any]) -> str:
        render_calls.append(name)
        return f"<rendered-{name}>"

    prompt_loader = SimpleNamespace(render=Mock(side_effect=_track_render))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    await service.generate_memo(stock_id, run_id, language="en")

    assert "narrative_system.en.md.j2" in render_calls
    assert "narrative_user.en.md.j2" in render_calls
    # DE-Templates wurden NICHT geladen
    assert "narrative_system.de.md.j2" not in render_calls
    assert "narrative_user.de.md.j2" not in render_calls


# ---------------------------------------------------------------------------
# Task 8 — NarrativeService.generate_memo — Error-Pfade
# ---------------------------------------------------------------------------


async def test_generate_memo_persists_error_memo_when_no_tool_use_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bei Anthropic-Response ohne submit_memo-Tool-Block: error-memo persistieren."""
    monkeypatch.chdir(tmp_path)  # logs/malformed_memos/ landet in tmp

    stock_id, run_id = uuid4(), uuid4()

    expected_error = _sample_memo(
        stock_id=stock_id,
        run_id=run_id,
        one_liner="Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
        confidence="low",
        model_version="error-fallback",
    )
    memo_repo = AsyncMock()
    # 1. Cache-Check: None. 2. Reload nach save(): persisted error-memo.
    memo_repo.get = AsyncMock(side_effect=[None, expected_error])
    memo_repo.save = AsyncMock()
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    bad_response = SimpleNamespace(
        id="msg_x",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        content=[SimpleNamespace(type="text", text="I refuse")],
        stop_reason="end_turn",
    )
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=bad_response)
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: "<rendered>"))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id)

    # Error-Memo wurde persistiert
    memo_repo.save.assert_awaited_once()
    assert result.confidence == "low"
    assert "fehlgeschlagen" in result.one_liner.lower()
    assert result.model_version == "error-fallback"

    # Raw-Response in logs/malformed_memos/
    log_dir = tmp_path / "logs" / "malformed_memos"
    assert log_dir.exists()
    log_files = list(log_dir.glob("*.json"))
    assert len(log_files) == 1
    raw = json.loads(log_files[0].read_text())
    # Mindestens id und content sind im Dump
    assert raw.get("id") == "msg_x"


async def test_generate_memo_persists_error_memo_on_pydantic_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bei Schema-Verletzung (z.B. one_liner zu kurz): error-memo persistieren."""
    monkeypatch.chdir(tmp_path)

    stock_id, run_id = uuid4(), uuid4()

    expected_error = _sample_memo(
        stock_id=stock_id,
        run_id=run_id,
        one_liner="Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
        confidence="low",
        model_version="error-fallback",
    )
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(side_effect=[None, expected_error])
    memo_repo.save = AsyncMock()
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    invalid_payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "x",  # zu kurz (min_length=10)
        "ranking_interpretation": "y" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": None,
        "contradictions": [],
        "key_strengths": ["a"],
        "key_risks": ["b"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(invalid_payload))
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: "<rendered>"))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id)

    memo_repo.save.assert_awaited_once()
    assert result.confidence == "low"
    assert result.model_version == "error-fallback"


# ---------------------------------------------------------------------------
# Task 7 (Coverage-Gap) — force_regenerate=True bypasst Cache
# ---------------------------------------------------------------------------


async def test_generate_memo_force_regenerate_bypasses_cache() -> None:
    """force_regenerate=True ueberspringt Cache-Check und ruft LLM."""
    stock_id, run_id = uuid4(), uuid4()

    # Was die DB nach UPSERT haelt (Reload-Result).
    persisted = _sample_memo(
        stock_id=stock_id,
        run_id=run_id,
        one_liner="Frischer Memo nach force_regenerate.",
    )

    memo_repo = AsyncMock()
    # force_regenerate=True ueberspringt Cache-Check; get() wird nur einmal
    # nach save() aufgerufen (Reload).
    memo_repo.get = AsyncMock(return_value=persisted)
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Frischer Memo nach force_regenerate.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "Top 25% in 4 Modellen.",
        "contradictions": [],
        "key_strengths": ["Top 10% Quality"],
        "key_risks": ["Bewertungs-Multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: f"<rendered-{name}>"))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
    )

    result = await service.generate_memo(stock_id, run_id, force_regenerate=True)

    # LLM was called (cache was bypassed)
    llm.messages_create.assert_awaited_once()
    # New memo was saved (replacing cached)
    memo_repo.save.assert_awaited_once()
    # Returned memo is the freshly generated one
    assert result.one_liner == "Frischer Memo nach force_regenerate."


# ---------------------------------------------------------------------------
# B1 (PR #64 Deep-Review) — Defense-in-depth: Entity-Konstruktion in try/except
# ---------------------------------------------------------------------------


async def test_generate_memo_persists_error_memo_on_entity_validation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falls Schema-Validation passt aber Entity-Konstruktion mit ValidationError
    fehlschlaegt (kuenftige Schema/Entity-Drift), darf NICHT 500 escalieren —
    Error-Memo-Pfad muss wie bei Schema-Verletzung greifen.
    """
    monkeypatch.chdir(tmp_path)

    stock_id, run_id = uuid4(), uuid4()

    expected_error = _sample_memo(
        stock_id=stock_id,
        run_id=run_id,
        one_liner="Memo-Generierung fehlgeschlagen — bitte Run regenerieren",
        confidence="low",
        model_version="error-fallback",
    )
    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(side_effect=[None, expected_error])
    memo_repo.save = AsyncMock()
    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    # Entity-invalid: ranking_interpretation > Entity max=1000. Bypasst Schema-
    # Validation via Monkeypatch — simuliert exakt das Schema/Entity-Drift-Szenario.
    entity_invalid = SimpleNamespace(
        one_liner="Defensiver Quality-Kern.",
        ranking_interpretation="x" * 1500,
        sweet_spot=True,
        sweet_spot_explanation=None,
        contradictions=[],
        key_strengths=["Top 10% Quality"],
        key_risks=["Bewertungs-Multiples"],
        confidence="high",
        model_version="claude-sonnet-4-6",
    )
    monkeypatch.setattr(
        NarrativeService,
        "_try_validate_tool_response",
        lambda self, response: entity_invalid,
    )

    response_stub = SimpleNamespace(
        id="msg_drift",
        usage=SimpleNamespace(input_tokens=2300, output_tokens=487),
        content=[SimpleNamespace(type="tool_use", name="submit_memo", input={})],
        stop_reason="tool_use",
    )
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=response_stub)
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: "<rendered>"))

    service = NarrativeService(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        batch_repository=AsyncMock(),
        llm_client=llm,
        prompt_loader=prompt_loader,  # type: ignore[arg-type]
        cost_tracker=AsyncMock(),
        session_factory=Mock(),
        stock_repo_factory=Mock(return_value=AsyncMock()),
        run_repo_factory=Mock(return_value=AsyncMock()),
    )

    result = await service.generate_memo(stock_id, run_id)

    # Error-Memo wurde persistiert — kein 500-Crash
    memo_repo.save.assert_awaited_once()
    saved = memo_repo.save.await_args.args[0]
    assert saved.model_version == "error-fallback"
    assert "fehlgeschlagen" in saved.one_liner.lower()

    # Returnwert ist die persisted Error-Row (Reload-Pattern wie bei Happy-Path)
    assert result is expected_error

    # Raw-Response in logs/malformed_memos/ (Forensik-Pfad bleibt aktiv)
    log_dir = tmp_path / "logs" / "malformed_memos"
    assert log_dir.exists()
    assert len(list(log_dir.glob("*.json"))) == 1


def test_rankings_for_template_returns_only_rank_no_score() -> None:
    """Issue #66: erfundener Score (1/rank) entfernt — nur reale Rank-Daten."""
    from backend.application.services.narrative_service import _rankings_for_template

    out = _rankings_for_template(
        {
            "per_model_ranks": {
                "quality_classic": 8,
                "alpha": 12,
                "trend_momentum": 25,
                "value_alpha_potential": 60,
                "diversification": 5,
            }
        }
    )

    assert out == {
        "Quality Classic": {"rank": 8},
        "Alpha": {"rank": 12},
        "Trend Momentum": {"rank": 25},
        "Value Alpha Potential": {"rank": 60},
        "Diversification": {"rank": 5},
    }
    for model_data in out.values():
        assert "score" not in model_data


class TestBuildMemoEntityIsError:
    """_build_memo_entity setzt is_error aus schema.model_version (#67)."""

    def _make_schema(self, *, model_version: str) -> Any:
        from backend.domain.schemas.research_memo_schema import ResearchMemoSchema

        return ResearchMemoSchema(
            ticker="NESN",
            total_rank=1,
            one_liner="Test-Memo fuer Unit-Test",
            ranking_interpretation="x" * 100,
            sweet_spot=False,
            sweet_spot_explanation=None,
            contradictions=[],
            key_strengths=["s1"],
            key_risks=["r1"],
            confidence="low",
            generated_at=datetime.now(tz=UTC),
            model_version=model_version,
        )

    def test_error_fallback_model_version_marks_is_error_true(self) -> None:
        from backend.domain.entities.research_memo import ERROR_FALLBACK_MODEL_VERSION

        schema = self._make_schema(model_version=ERROR_FALLBACK_MODEL_VERSION)
        entity = NarrativeService._build_memo_entity(
            None,  # type: ignore[arg-type]
            schema,
            stock_id=uuid4(),
            model_run_id=uuid4(),
            language="de",
        )
        assert entity.is_error is True

    def test_normal_model_version_keeps_is_error_false(self) -> None:
        schema = self._make_schema(model_version="claude-sonnet-4-6")
        entity = NarrativeService._build_memo_entity(
            None,  # type: ignore[arg-type]
            schema,
            stock_id=uuid4(),
            model_run_id=uuid4(),
            language="de",
        )
        assert entity.is_error is False


# ---------------------------------------------------------------------------
# RAG-Kontext Integration (Issue #138)
# ---------------------------------------------------------------------------


def _make_retrieval_result(content: str = "Apple revenue grew 12%.") -> object:
    """Minimales RetrievalResult-Objekt fuer Tests."""
    from uuid import uuid4

    from backend.domain.entities.retrieval_result import RetrievalResult

    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_idx=0,
        content=content,
        similarity=0.92,
        ticker="AAPL",
        doc_type="10-K",
    )


def _make_full_service_with_retrieval(retrieval_mock: AsyncMock) -> NarrativeService:
    """Baut einen NarrativeService mit vollstaendiger Mock-Infrastruktur + RAG."""

    # retrieval_mock ist ein AsyncMock der RetrievalService — wrap in spec
    return _make_service(retrieval_service=retrieval_mock)


async def test_rag_chunks_appear_in_rendered_prompt() -> None:
    """Wenn RetrievalService konfiguriert ist, sollen Chunks im User-Prompt landen."""
    stock_id, run_id = uuid4(), uuid4()
    persisted = _sample_memo(stock_id=stock_id, run_id=run_id)

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(side_effect=[None, persisted])
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensiver Quality-Kern.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "4 Modelle.",
        "contradictions": [],
        "key_strengths": ["Top Quality"],
        "key_risks": ["Multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))

    captured_ctx: dict[str, Any] = {}

    def capturing_render(name: str, ctx: dict[str, Any]) -> str:
        captured_ctx.update(ctx)
        return f"<rendered-{name}>"

    prompt_loader = SimpleNamespace(render=Mock(side_effect=capturing_render))

    chunk_content = "NESN reported CHF 89.5B revenue in FY2024."
    retrieval_mock = AsyncMock()
    retrieval_mock.retrieve = AsyncMock(return_value=[_make_retrieval_result(chunk_content)])

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
        retrieval_service=retrieval_mock,
    )

    await service.generate_memo(stock_id, run_id)

    retrieval_mock.retrieve.assert_awaited_once()
    call_kwargs = retrieval_mock.retrieve.await_args.kwargs
    assert call_kwargs["ticker"] == "NESN"
    assert call_kwargs["k"] == 5

    assert "rag_context" in captured_ctx
    assert chunk_content in captured_ctx["rag_context"]


async def test_generate_memo_without_retrieval_service_works() -> None:
    """Backward-Compat: ohne RetrievalService laeuft generate_memo normal durch."""
    stock_id, run_id = uuid4(), uuid4()
    persisted = _sample_memo(stock_id=stock_id, run_id=run_id)

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(side_effect=[None, persisted])
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensiver Quality-Kern.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "4 Modelle.",
        "contradictions": [],
        "key_strengths": ["Top Quality"],
        "key_risks": ["Multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))

    captured_ctx: dict[str, Any] = {}

    def capturing_render(name: str, ctx: dict[str, Any]) -> str:
        captured_ctx.update(ctx)
        return f"<rendered-{name}>"

    prompt_loader = SimpleNamespace(render=Mock(side_effect=capturing_render))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
        retrieval_service=None,
    )

    result = await service.generate_memo(stock_id, run_id)

    assert result is persisted
    assert captured_ctx.get("rag_context") == ""


async def test_rag_failure_does_not_block_memo_generation() -> None:
    """Wenn RAG-Retrieval wirft, wird das Memo trotzdem generiert (graceful degradation)."""
    stock_id, run_id = uuid4(), uuid4()
    persisted = _sample_memo(stock_id=stock_id, run_id=run_id)

    memo_repo = AsyncMock()
    memo_repo.get = AsyncMock(side_effect=[None, persisted])
    memo_repo.save = AsyncMock()

    stock_repo = AsyncMock()
    stock_repo.get = AsyncMock(return_value=_stock(stock_id=stock_id))
    run_repo = AsyncMock()
    run_repo.get_results = AsyncMock(return_value=_sample_results())

    payload = {
        "ticker": "NESN",
        "total_rank": 1,
        "one_liner": "Defensiver Quality-Kern.",
        "ranking_interpretation": "x" * 120,
        "sweet_spot": True,
        "sweet_spot_explanation": "4 Modelle.",
        "contradictions": [],
        "key_strengths": ["Top Quality"],
        "key_risks": ["Multiples"],
        "confidence": "high",
        "generated_at": "2026-05-04T10:00:00Z",
        "model_version": "claude-sonnet-4-6",
    }
    llm = AsyncMock()
    llm.messages_create = AsyncMock(return_value=_tool_use_response(payload))
    prompt_loader = SimpleNamespace(render=Mock(side_effect=lambda name, ctx: f"<rendered-{name}>"))

    failing_retrieval = AsyncMock()
    failing_retrieval.retrieve = AsyncMock(side_effect=RuntimeError("Voyage API down"))

    service = _make_service(
        memo_repository=memo_repo,
        run_repository=run_repo,
        stock_repository=stock_repo,
        llm_client=llm,
        prompt_loader=prompt_loader,
        retrieval_service=failing_retrieval,
    )

    result = await service.generate_memo(stock_id, run_id)

    assert result is persisted
    llm.messages_create.assert_awaited_once()
