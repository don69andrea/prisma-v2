"""Pricing-Konstanten fuer LLM- und Embedding-Modelle (Vendor-Werte).

Single-Source-of-Truth fuer Token-Preise. Gespeist aus offiziellen
Pricing-Pages — bei Aenderung: PR mit Quelle + Datum (Audit-Trail).

Der `ModelPricing`-Type lebt im Domain-Layer (`backend.domain.llm_pricing`),
weil token-basierte Cost-Calc Bestandteil der Budget-Cap-Business-Rule ist.
Die konkreten Vendor-Werte (Anthropic/Voyage) bleiben hier in Infrastructure
und werden via DI in `CostTracker` injiziert.

Quellen (Stand 2026-04-26 — vor Production-Deploy gegen Live-Pages
verifizieren):
- Anthropic: https://www.anthropic.com/pricing
- Voyage AI: https://docs.voyageai.com/docs/pricing

Spezifiziert in `docs/specs/2026-04-25-budget-cap.md` §6.
"""

from decimal import Decimal

from backend.domain.llm_pricing import ModelPricing

__all__ = ["ModelPricing", "PRICING"]


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
