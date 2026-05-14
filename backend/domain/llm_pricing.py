"""LLM-Pricing-Type — Domain-Layer.

`ModelPricing` ist Bestandteil der Budget-Cap-Business-Rule (Spec
`docs/specs/2026-04-25-budget-cap.md` §6): Kosten werden token-basiert
berechnet, getrennt nach Chat- (Input/Output) und Embedding-Modellen.

Der konkrete Pricing-Katalog (Anthropic-/Voyage-spezifische Werte) lebt in
`backend/infrastructure/llm/pricing.py` und wird via DI in `CostTracker`
injiziert (AGENTS.md §2 — Application kennt Infrastructure nicht).
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelPricing:
    """Token-Preise pro 1 Mio Tokens fuer ein einzelnes Modell.

    `None` bedeutet **"trifft auf dieses Modell nicht zu"**, nicht
    "kostenlos" — bei reinen Embedding-Modellen sind `input_per_mtok`
    und `output_per_mtok` daher None, nicht 0. Andersrum ist
    `embed_per_mtok` bei Chat-Modellen None. Aufrufer pruefen `is None`
    und werfen `UnknownModelError`, wenn der Preistyp nicht passt.
    """

    input_per_mtok: Decimal | None
    output_per_mtok: Decimal | None
    embed_per_mtok: Decimal | None
