"""CryptoAsset — Domain-Entity für eine Kryptowährung."""
from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_CRYPTOS: list[tuple[str, str, str, str, bool]] = [
    # (ticker_coingecko, ticker_yfinance, name, kategorie, has_six_etp)
    ("bitcoin",      "BTC-CHF",  "Bitcoin",      "Layer1/Store of Value", True),
    ("ethereum",     "ETH-CHF",  "Ethereum",     "Layer1/Smart Contract", True),
    ("solana",       "SOL-USD",  "Solana",       "Layer1/High Speed",     True),
    ("ripple",       "XRP-USD",  "XRP",          "Payment/Layer1",        True),
    ("cardano",      "ADA-USD",  "Cardano",      "Layer1/ESG",            True),
    ("polkadot",     "DOT-USD",  "Polkadot",     "Layer0/Interop",        True),
    ("chainlink",    "LINK-USD", "Chainlink",    "DeFi/Oracle",           False),
    ("avalanche-2",  "AVAX-USD", "Avalanche",    "Layer1/Subnets",        True),
    ("uniswap",      "UNI-USD",  "Uniswap",      "DeFi/DEX",              False),
    ("bitcoin-cash", "BCH-USD",  "Bitcoin Cash", "Payment",               True),
]


@dataclass
class CryptoAsset:
    """Repräsentiert eine Kryptowährung mit Live-Marktdaten."""

    ticker_cg: str
    ticker_yf: str
    name: str
    symbol: str
    kategorie: str
    has_six_etp: bool

    price_chf: float | None = None
    market_cap_chf: float | None = None
    volume_24h_chf: float | None = None
    price_change_24h_pct: float | None = None
    price_change_7d_pct: float | None = None
    ath_change_pct: float | None = None
    market_cap_rank: int | None = None
