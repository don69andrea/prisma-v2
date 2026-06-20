"""Unit-Tests für seed_index_constituents — PIT-Universum-Logik.

Testet die Konstanten und Datums-Logik ohne echte DB.
"""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.unit


class TestIndexConstituentConstants:
    def test_smi_current_has_20_entries(self) -> None:
        from backend.scripts.seed_index_constituents import _SMI_CURRENT

        assert len(_SMI_CURRENT) == 20

    def test_all_smi_tickers_have_sw_suffix(self) -> None:
        from backend.scripts.seed_index_constituents import _SMI_CURRENT

        for ticker, _ in _SMI_CURRENT:
            assert ticker.endswith(".SW"), f"{ticker} fehlt .SW-Suffix"

    def test_csgn_is_in_delisted(self) -> None:
        from backend.scripts.seed_index_constituents import _SMI_DELISTED

        tickers = [t for t, _, _ in _SMI_DELISTED]
        assert "CSGN.SW" in tickers

    def test_csgn_valid_to_is_2023(self) -> None:
        from backend.scripts.seed_index_constituents import _SMI_DELISTED

        csgn = next((row for row in _SMI_DELISTED if row[0] == "CSGN.SW"), None)
        assert csgn is not None
        _, valid_from, valid_to = csgn
        assert valid_to.year == 2023, "CSGN sollte 2023 aus dem SMI ausgetreten sein"
        assert valid_from < valid_to

    def test_current_members_have_no_valid_to(self) -> None:
        # Aktuelle Mitglieder haben valid_to=NULL → im Seed als None übergeben
        from backend.scripts.seed_index_constituents import _SMI_CURRENT

        # Alle current-Einträge haben genau (ticker, valid_from) — kein valid_to
        for entry in _SMI_CURRENT:
            assert len(entry) == 2

    def test_no_duplicate_tickers_in_current_smi(self) -> None:
        from backend.scripts.seed_index_constituents import _SMI_CURRENT

        tickers = [t for t, _ in _SMI_CURRENT]
        assert len(tickers) == len(set(tickers))

    def test_valid_from_dates_are_date_objects(self) -> None:
        from backend.scripts.seed_index_constituents import _SMI_CURRENT, _SMI_DELISTED

        for _ticker, valid_from in _SMI_CURRENT:
            assert isinstance(valid_from, date)
        for _ticker, valid_from, valid_to in _SMI_DELISTED:
            assert isinstance(valid_from, date)
            assert isinstance(valid_to, date)

    def test_csgn_not_in_current_smi(self) -> None:
        from backend.scripts.seed_index_constituents import _SMI_CURRENT

        current_tickers = {t for t, _ in _SMI_CURRENT}
        assert "CSGN.SW" not in current_tickers


class TestPitLogicWithoutDb:
    """Testet die PIT-Datums-Logik rein rechnerisch (kein DB-Aufruf)."""

    def _is_member(
        self,
        valid_from: date,
        valid_to: date | None,
        snap_date: date,
    ) -> bool:
        return valid_from <= snap_date and (valid_to is None or valid_to >= snap_date)

    def test_current_member_is_active_today(self) -> None:
        assert self._is_member(date(2010, 1, 1), None, date.today())

    def test_current_member_was_active_in_2015(self) -> None:
        assert self._is_member(date(2010, 1, 1), None, date(2015, 6, 1))

    def test_csgn_active_before_2023(self) -> None:
        assert self._is_member(date(2010, 1, 1), date(2023, 6, 12), date(2022, 12, 31))

    def test_csgn_active_on_delisting_date(self) -> None:
        # valid_to ist inklusive
        assert self._is_member(date(2010, 1, 1), date(2023, 6, 12), date(2023, 6, 12))

    def test_csgn_not_active_after_delisting(self) -> None:
        assert not self._is_member(date(2010, 1, 1), date(2023, 6, 12), date(2023, 6, 13))

    def test_member_not_active_before_join_date(self) -> None:
        # Partners Group: valid_from=2020-09-21
        assert not self._is_member(date(2020, 9, 21), None, date(2019, 12, 31))
