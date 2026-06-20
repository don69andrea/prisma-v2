"""Unit-Tests: TransactionCostModel — Kap. 17 / CHALLENGE 03."""

from __future__ import annotations

import pytest

from backend.domain.services.transaction_cost_model import AssetClass, TransactionCostModel

pytestmark = pytest.mark.unit


@pytest.fixture()
def model() -> TransactionCostModel:
    return TransactionCostModel()


class TestRoundTripCost:
    def test_ch_stock_expected_bps(self, model: TransactionCostModel) -> None:
        # 2 × (0.15% stamp + 0.20% brokerage + 0.10% spread) = 0.90%
        expected = 2 * (0.0015 + 0.0020 + 0.0010)
        assert model.round_trip_cost(AssetClass.CH_STOCK) == pytest.approx(expected)

    def test_crypto_expected_bps(self, model: TransactionCostModel) -> None:
        # 2 × (0.15% fee + 0.10% slippage) = 0.50%
        expected = 2 * (0.0015 + 0.0010)
        assert model.round_trip_cost(AssetClass.CRYPTO) == pytest.approx(expected)

    def test_ch_stock_more_expensive_than_crypto(self, model: TransactionCostModel) -> None:
        assert model.ch_stock_round_trip() > model.crypto_round_trip()

    def test_cost_positive(self, model: TransactionCostModel) -> None:
        assert model.round_trip_cost(AssetClass.CH_STOCK) > 0
        assert model.round_trip_cost(AssetClass.CRYPTO) > 0


class TestNetReturn:
    def test_net_less_than_gross(self, model: TransactionCostModel) -> None:
        gross = 0.10
        net_stock = model.net_return(gross, AssetClass.CH_STOCK)
        net_crypto = model.net_return(gross, AssetClass.CRYPTO)
        assert net_stock < gross
        assert net_crypto < gross

    def test_net_return_crypto_exact(self, model: TransactionCostModel) -> None:
        gross = 0.05
        # 0.05 − 0.005 = 0.045
        assert model.net_return(gross, AssetClass.CRYPTO) == pytest.approx(0.045)

    def test_zero_gross_negative_net(self, model: TransactionCostModel) -> None:
        net = model.net_return(0.0, AssetClass.CH_STOCK)
        assert net < 0, "TC machen 0%-Gross-Return netto negativ"

    def test_negative_gross_more_negative_net(self, model: TransactionCostModel) -> None:
        gross = -0.05
        net = model.net_return(gross, AssetClass.CH_STOCK)
        assert net < gross

    def test_convenience_helpers_match(self, model: TransactionCostModel) -> None:
        assert model.ch_stock_round_trip() == model.round_trip_cost(AssetClass.CH_STOCK)
        assert model.crypto_round_trip() == model.round_trip_cost(AssetClass.CRYPTO)
