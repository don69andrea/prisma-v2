"""Unit-Tests für den CH-ISIN-Validator (Luhn-Algorithmus)."""

import pytest

from backend.domain.validators.isin import validate_ch_isin

pytestmark = pytest.mark.unit


class TestValidateChIsin:
    def test_valid_nesn_isin(self) -> None:
        # NESN = Nestlé SA, CH0038863350 — verified via Luhn
        assert validate_ch_isin("CH0038863350") is True

    def test_invalid_prefix_us(self) -> None:
        assert validate_ch_isin("US0038863350") is False

    def test_invalid_prefix_de(self) -> None:
        assert validate_ch_isin("DE0038863350") is False

    def test_too_short(self) -> None:
        assert validate_ch_isin("CH003886335") is False

    def test_too_long(self) -> None:
        assert validate_ch_isin("CH00388633500") is False

    def test_wrong_check_digit(self) -> None:
        # CH0038863350 is valid; change last digit to 1
        assert validate_ch_isin("CH0038863351") is False

    def test_empty_string(self) -> None:
        assert validate_ch_isin("") is False

    def test_letters_in_numeric_part(self) -> None:
        # Digits 3–11 must be numeric
        assert validate_ch_isin("CH003886335X") is False
