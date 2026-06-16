"""Domain-Exceptions — frei von externen Framework-Abhängigkeiten.

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §8.
"""

from decimal import Decimal


class UnknownModelError(Exception):
    """Wird geworfen, wenn ein Modell nicht in der `PRICING`-Registry steht
    oder nicht den passenden Preistyp hat (z.B. embed-Pricing für einen
    Chat-Call). Tritt an die Stelle eines blanken `KeyError`, damit
    Aufrufer-Code die Ursache erkennen kann.
    """

    def __init__(self, model: str, *, reason: str = "unbekannt") -> None:
        self.model = model
        self.reason = reason
        super().__init__(f"Modell {model!r} nicht in PRICING-Registry: {reason}")


class BudgetCapExceeded(Exception):
    """Wird geworfen, wenn ein LLM-Call das Monats-Budget-Cap überschreiten würde.

    Die strukturierten Attribute (`current_usd`, `attempted_usd`, `cap_usd`)
    werden vom FastAPI-Exception-Handler in den HTTP-503-Response-Body
    eingebettet und vom MCP-Layer in den Tool-Error übersetzt.
    """

    def __init__(
        self,
        *,
        current_usd: Decimal,
        attempted_usd: Decimal,
        cap_usd: Decimal,
    ) -> None:
        self.current_usd = current_usd
        self.attempted_usd = attempted_usd
        self.cap_usd = cap_usd
        super().__init__(
            f"Budget-Cap erreicht: {current_usd:.2f} + {attempted_usd:.2f} "
            f"USD würde {cap_usd:.2f} USD überschreiten."
        )


class SwissDataUnavailableError(Exception):
    """yfinance liefert keinen Datensatz für diesen .SW-Ticker.

    Wird geworfen wenn yfinance ein leeres .info-Dict zurückgibt
    oder der Ticker nicht als .SW-Ticker bekannt ist.
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(f"Keine yfinance-Daten für Swiss Ticker '{ticker}.SW'")


class YahooFinanceBlockedError(SwissDataUnavailableError):
    """Yahoo Finance blockiert den Request (z.B. HTTP 401 "Invalid Crumb").

    Tritt bekanntermassen auf, wenn yfinance von Cloud-Hosting-IP-Ranges
    (z.B. Render) aus aufgerufen wird — Yahoo blockt diese Ranges dauerhaft.
    Kein Bug in unserem Code, sondern eine externe Einschränkung.

    Subklasse von SwissDataUnavailableError, damit bestehende
    `except SwissDataUnavailableError`-Blöcke beide Fälle weiterhin
    einheitlich abfangen — Router können bei Bedarf trotzdem zwischen
    "Ticker unbekannt" (404) und "Datenquelle blockiert" (503) unterscheiden,
    indem sie zuerst auf diese spezifischere Klasse matchen.
    """

    def __init__(self, ticker: str, *, cause: str = "") -> None:
        self.ticker = ticker
        detail = f" ({cause})" if cause else ""
        Exception.__init__(
            self,
            f"Yahoo Finance blockiert den Zugriff für '{ticker}.SW'{detail} — "
            "Marktdaten momentan nicht verfügbar (externe Datenquelle eingeschränkt).",
        )
