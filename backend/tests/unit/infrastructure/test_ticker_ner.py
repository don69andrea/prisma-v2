"""Unit-Tests für TickerNer — Dictionary-basierte Ticker-Erkennung."""

import pytest

from backend.infrastructure.adapters.ticker_ner import SWISS_TICKERS, TickerNer

pytestmark = pytest.mark.unit

_ner = TickerNer(SWISS_TICKERS)


class TestTickerNer:
    def test_finds_single_ticker_in_title(self) -> None:
        result = _ner.extract("NESN steigt um 2% nach Quartalsbericht")
        assert "NESN" in result

    def test_finds_multiple_tickers(self) -> None:
        result = _ner.extract("NOVN und ABBN profitieren vom CHF-Rückgang")
        assert "NOVN" in result
        assert "ABBN" in result

    def test_case_insensitive_match(self) -> None:
        result = _ner.extract("nesn meldet Rekordumsatz")
        assert "NESN" in result

    def test_no_false_positive_partial_match(self) -> None:
        # "ROG" should not match in "PROGRAM" (word boundary required)
        result = _ner.extract("Das PROGRAM läuft gut")
        assert "ROG" not in result

    def test_returns_uppercase_tickers(self) -> None:
        result = _ner.extract("novn und nesn")
        assert all(t == t.upper() for t in result)

    def test_deduplicates_repeated_tickers(self) -> None:
        result = _ner.extract("NESN, NESN, NESN — dreimal erwähnt")
        assert result.count("NESN") == 1

    def test_empty_text_returns_empty(self) -> None:
        result = _ner.extract("")
        assert result == ()

    def test_empty_known_tickers_returns_empty(self) -> None:
        ner_empty = TickerNer(frozenset())
        result = ner_empty.extract("NESN NOVN ABBN")
        assert result == ()

    def test_ticker_rog_matches_as_word(self) -> None:
        result = _ner.extract("ROG meldet gute Zahlen")
        assert "ROG" in result

    def test_finds_ticker_from_company_name_nestle(self) -> None:
        # Realistischer NZZ/SRF-Artikeltext: erwähnt nur den Firmennamen
        # "Nestlé", nirgends das Ticker-Symbol "NESN" selbst.
        article = (
            "Der Lebensmittelkonzern Nestlé hat heute seine Quartalszahlen "
            "veröffentlicht. Der Umsatz des Vevey-Konzerns stieg im "
            "Vergleich zum Vorjahr um 3.2 Prozent. Analysten zeigten sich "
            "zufrieden mit der Entwicklung des Schweizer Nahrungsmittelriesen."
        )
        result = _ner.extract(article)
        assert "NESN" in result

    def test_finds_ticker_from_company_name_novartis(self) -> None:
        article = (
            "Der Pharmakonzern Novartis meldet eine Zulassung für ein neues "
            "Medikament in den USA. Die Aktie des Basler Unternehmens "
            "reagierte positiv auf die Nachricht."
        )
        result = _ner.extract(article)
        assert "NOVN" in result
