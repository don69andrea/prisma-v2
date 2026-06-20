"""Unit-Tests für backend.domain.data.macro_profiles (FIX-03)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestMacroProfiles:
    def test_export_heavy_is_frozenset(self) -> None:
        from backend.domain.data.macro_profiles import EXPORT_HEAVY

        assert isinstance(EXPORT_HEAVY, frozenset)
        assert len(EXPORT_HEAVY) > 0

    def test_export_heavy_contains_nesn(self) -> None:
        from backend.domain.data.macro_profiles import EXPORT_HEAVY

        assert "NESN.SW" in EXPORT_HEAVY

    def test_domestic_focus_is_frozenset(self) -> None:
        from backend.domain.data.macro_profiles import DOMESTIC_FOCUS

        assert isinstance(DOMESTIC_FOCUS, frozenset)
        assert "UBSG.SW" in DOMESTIC_FOCUS

    def test_no_overlap_between_export_and_domestic(self) -> None:
        from backend.domain.data.macro_profiles import DOMESTIC_FOCUS, EXPORT_HEAVY

        assert EXPORT_HEAVY.isdisjoint(DOMESTIC_FOCUS)

    def test_all_tickers_have_sw_suffix(self) -> None:
        from backend.domain.data.macro_profiles import DOMESTIC_FOCUS, EXPORT_HEAVY

        for t in EXPORT_HEAVY | DOMESTIC_FOCUS:
            assert t.endswith(".SW"), f"{t} fehlt .SW-Suffix"

    def test_export_sectors_nonempty(self) -> None:
        from backend.domain.data.macro_profiles import EXPORT_SECTORS

        assert "pharma" in EXPORT_SECTORS

    def test_chf_thresholds_ordering(self) -> None:
        from backend.domain.data.macro_profiles import CHF_STRONG_THRESHOLD, CHF_WEAK_THRESHOLD

        assert CHF_WEAK_THRESHOLD < CHF_STRONG_THRESHOLD


class TestMacroAgentImports:
    """Stellt sicher, dass beide Agenten ihre Profile aus macro_profiles beziehen."""

    def test_macro_agent_v1_uses_shared_export_heavy(self) -> None:
        import backend.application.agents.macro_agent as agent_v1
        from backend.domain.data.macro_profiles import EXPORT_HEAVY

        # Der Agent darf keine eigene Kopie mehr haben
        assert not hasattr(agent_v1, "_EXPORT_HEAVY") or agent_v1._EXPORT_HEAVY is EXPORT_HEAVY

    def test_macro_agent_v2_uses_shared_export_heavy(self) -> None:
        import backend.application.agents.macro_agent_v2 as agent_v2
        from backend.domain.data.macro_profiles import EXPORT_HEAVY

        assert not hasattr(agent_v2, "_EXPORT_HEAVY") or agent_v2._EXPORT_HEAVY is EXPORT_HEAVY
