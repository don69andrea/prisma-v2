# ─────────────────────────────────────────────────────────────────────────
# In backend/config.py in die Settings-Klasse einarbeiten (NICHT als separate
# Datei committen). Folgt dem bestehenden Muster (leerer Default, opt-in).
# ─────────────────────────────────────────────────────────────────────────

    # EODHD (eodhd.com) — Fundamentals + EOD, echte SIX-Coverage.
    # Free-Tier knapp (20 Calls/Tag); Seed braucht ggf. 1 Monat Paid.
    # Leer = EODHD-Adapter deaktiviert, kein HTTP-Call.
    eodhd_api_key: str = ""

    # Steuert, welche Fundamentals-Quelle der Feature-/Seed-Pfad nutzt.
    # auto  = verify_dataset_coverage.py hat den Sieger nach docs/dataset_coverage.md geschrieben
    # eodhd | fmp | simfin_us | yf_derived
    dataset_source_fundamentals: str = "auto"
    dataset_source_prices: str = "yfinance"
    dataset_source_crypto: str = "cryptodatadownload"

    # Trainings-/Seed-Tiefe (überschreibbar per ENV für Tests).
    seed_stocks_from: str = "2015-01-01"
    seed_crypto_daily_from: str = "2017-01-01"
    seed_crypto_hourly_from: str = "2020-01-01"
