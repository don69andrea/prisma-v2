"""Unit-Tests fuer PromptTemplateLoader (Jinja2)."""

from pathlib import Path

import pytest
from jinja2.exceptions import TemplateNotFound

from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "prompts"


def test_render_user_prompt_matches_snapshot() -> None:
    loader = PromptTemplateLoader()
    rendered = loader.render(
        "narrative_user.md.j2",
        {
            "ticker": "NESN",
            "name": "Nestle SA",
            "sector": "Consumer Staples",
            "country": "CH",
            "run_id": "550e8400-e29b-41d4-a716-446655440001",
            "universe_name": "Swiss-Mid-Cap",
            "n_stocks": 80,
            "median_rank": 40,
            "top20_threshold": 16,
            "rankings": {
                "Quality Classic": {"rank": 8, "score": 0.87},
                "Alpha": {"rank": 12, "score": 0.74},
                "Trend Momentum": {"rank": 25, "score": 0.62},
                "Value Alpha Potential": {"rank": 60, "score": 0.31},
                "Diversification": {"rank": 5, "score": 0.91},
            },
            "total_rank": 11,
            "sweet_spot": True,
            "weights": "equal-weighted (0.20 each)",
        },
    )

    expected = (FIXTURES / "expected_user_prompt.md").read_text(encoding="utf-8").rstrip()
    assert rendered.rstrip() == expected


def test_render_unknown_template_raises() -> None:
    loader = PromptTemplateLoader()
    with pytest.raises(TemplateNotFound):
        loader.render("does_not_exist.md.j2", {})


def test_render_de_system_template_succeeds() -> None:
    """System-Template darf einfach gerendert werden (keine Slots — alles statisch)."""
    loader = PromptTemplateLoader()
    rendered = loader.render("narrative_system.de.md.j2", {})
    assert "quantitativer Research-Analyst" in rendered
    assert "submit_memo" in rendered
    assert "Sweet Spot" in rendered
