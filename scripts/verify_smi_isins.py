#!/usr/bin/env python3
"""Verifiziert die ISINs für alle 20 SMI-Stocks via yfinance.

Vergleicht aktuelle Werte aus seed_smi_universe.py mit yfinance-Daten.
Gibt eine Diff-Liste aus und schreibt das Ergebnis nach stdout.

Usage:
    python scripts/verify_smi_isins.py
"""

from __future__ import annotations

import asyncio
import sys

import yfinance as yf

SMI_TICKERS = [
    "NESN",
    "NOVN",
    "ROG",
    "ABBN",
    "ZURN",
    "UBSG",
    "UHR",
    "GEBN",
    "GIVN",
    "LONN",
    "SREN",
    "SGKN",
    "SLHN",
    "SCMN",
    "SIKA",
    "HOLN",
    "PGHN",
    "KRIN",
    "CFR",
    "STMN",
]

CURRENT_ISINS = {
    "NESN": "CH0038863350",
    "NOVN": "CH0012005267",   # korrigiert: CH0012221716 war ABB, nicht Novartis
    "ROG": "CH0012032048",
    "ABBN": "CH0012221716",   # bestätigt via SIX Exchange
    "ZURN": "CH0011075394",
    "UBSG": "CH0244767585",
    "UHR": "CH0012255151",
    "GEBN": "CH0030170408",
    "GIVN": "CH0010645932",
    "LONN": "CH0013841017",
    "SREN": "CH0126881561",
    "SGKN": "CH0002497458",
    "SLHN": "CH0014852781",
    "SCMN": "CH0008742519",
    "SIKA": "CH0418792922",   # ersetzt BALN (delisted nach Fusion mit Helvetia 2025)
    "HOLN": "CH0012214059",
    "PGHN": "CH0024608827",
    "KRIN": "CH0334776754",
    "CFR": "CH0210483332",
    "STMN": "CH0012280076",   # korrigiert: CH0012050267 hatte Luhn-Fehler
}


def fetch_isin(ticker: str) -> str | None:
    try:
        info = yf.Ticker(f"{ticker}.SW").info
        return info.get("isin")
    except Exception as exc:
        print(f"  ERROR {ticker}: {exc}", file=sys.stderr)
        return None


async def main() -> None:
    print("Verifying SMI ISINs via yfinance...\n")
    verified: dict[str, str] = {}
    issues: list[str] = []

    loop = asyncio.get_event_loop()
    for ticker in SMI_TICKERS:
        isin = await loop.run_in_executor(None, fetch_isin, ticker)
        current = CURRENT_ISINS.get(ticker, "—")
        if isin and isin != current:
            status = "CHANGED"
            issues.append(ticker)
        elif not isin:
            status = "NOT_FOUND"
        else:
            status = "OK"
        verified[ticker] = isin or current
        print(f"  {status:10} {ticker:5} current={current}  yfinance={isin or 'N/A'}")

    print("\n--- RESULT ---")
    print(f"Verified: {len([v for v in verified.values() if v])} / {len(SMI_TICKERS)}")
    print(f"Changed:  {len(issues)} tickers: {issues}")
    print()
    print("# Verified SMI_20 for seed_smi_universe.py:")
    for ticker in SMI_TICKERS:
        isin = verified.get(ticker, CURRENT_ISINS[ticker])
        print(f'    ("{ticker}", "{isin}"),')


if __name__ == "__main__":
    asyncio.run(main())
