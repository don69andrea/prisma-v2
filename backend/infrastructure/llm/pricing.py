"""Pricing-Konstanten für LLM- und Embedding-Modelle.

Single-Source-of-Truth für Token-Preise. Gespeist aus offiziellen
Pricing-Pages — bei Änderung: PR mit Quelle + Datum (Audit-Trail).

Quellen (Stand 2026-04-26 — vor Production-Deploy gegen Live-Pages
verifizieren):
- Anthropic: https://www.anthropic.com/pricing
- Voyage AI: https://docs.voyageai.com/docs/pricing

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §6.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelPricing:
    """Token-Preise pro 1 Mio Tokens für ein einzelnes Modell.

    `None` bedeutet **"trifft auf dieses Modell nicht zu"**, nicht
    "kostenlos" — bei reinen Embedding-Modellen sind `input_per_mtok`
    und `output_per_mtok` daher None, nicht 0. Andersrum ist
    `embed_per_mtok` bei Chat-Modellen None. Aufrufer prüfen `is None`
    und werfen `UnknownModelError`, wenn der Preistyp nicht passt.
    """

    input_per_mtok: Decimal | None
    output_per_mtok: Decimal | None
    embed_per_mtok: Decimal | None


PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4-6": ModelPricing(
        input_per_mtok=Decimal("3.00"),
        output_per_mtok=Decimal("15.00"),
        embed_per_mtok=None,
    ),
    "claude-haiku-4-5": ModelPricing(
        input_per_mtok=Decimal("1.00"),
        output_per_mtok=Decimal("5.00"),
        embed_per_mtok=None,
    ),
    "voyage-3-large": ModelPricing(
        input_per_mtok=None,
        output_per_mtok=None,
        embed_per_mtok=Decimal("0.18"),
    ),
}
