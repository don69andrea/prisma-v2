"""RankingAggregator — kombiniert 5 Modell-Ränge zum gewichteten Total-Rank.

Spec: docs/specs/2026-04-21-prisma-capstone-design.md §7

Formel:
    weighted_avg(ticker) = Σ(rank_i × w_i) / Σ(w_i)  für verfügbare Modelle i
    Total-Rank aufsteigend: kleinster weighted_avg = Rang 1

Fehlende Ränge (rank=None): Gewicht dieses Modells wird auf die anderen
verfügbaren Modelle umverteilt (Normalisierung). Ticker ohne jeglichen
verfügbaren Rang erhalten total_rank=None.

Sweet Spot (§7.3): Ticker in Top-25% von mind. 3 der 5 Modelle.
"""

from dataclasses import dataclass

from backend.domain.entities.universe import WeightConfig
from backend.domain.models.base import ModelRankingResult


@dataclass(frozen=True)
class TotalRankResult:
    ticker: str
    total_rank: int | None
    weighted_avg: float | None
    is_sweet_spot: bool


class RankingAggregator:
    def aggregate(
        self,
        per_model: dict[str, list[ModelRankingResult]],
        weights: WeightConfig,
    ) -> list[TotalRankResult]:
        if not per_model:
            return []

        # Alle Ticker aus allen Modellen sammeln
        all_tickers: set[str] = set()
        for results in per_model.values():
            all_tickers.update(r.ticker for r in results)

        # {model_name: {ticker: rank}}
        rank_by_model: dict[str, dict[str, int | None]] = {
            model: {r.ticker: r.rank for r in results} for model, results in per_model.items()
        }

        # Universum-Grösse je Modell (für Sweet-Spot-Berechnung)
        universe_size = max(
            (len(ranks) for ranks in rank_by_model.values()),
            default=0,
        )

        weighted_avgs: dict[str, float | None] = {}
        sweet_spot_counts: dict[str, int] = {}

        for ticker in all_tickers:
            available: list[tuple[float, float]] = []  # (rank, weight)
            top25_count = 0

            for model, model_weights in weights.weights.items():
                ranks = rank_by_model.get(model, {})
                rank = ranks.get(ticker)
                if rank is not None:
                    available.append((float(rank), model_weights))
                    threshold = max(1, round(universe_size * 0.25))
                    if rank <= threshold:
                        top25_count += 1

            sweet_spot_counts[ticker] = top25_count

            if not available:
                weighted_avgs[ticker] = None
                continue

            total_weight = sum(w for _, w in available)
            weighted_avgs[ticker] = sum(r * w for r, w in available) / total_weight

        return _rank_results(weighted_avgs, sweet_spot_counts)


def _rank_results(
    weighted_avgs: dict[str, float | None],
    sweet_spot_counts: dict[str, int],
) -> list[TotalRankResult]:
    ranked = sorted(
        ((t, v) for t, v in weighted_avgs.items() if v is not None),
        key=lambda x: (x[1], x[0]),  # primary: weighted avg, tie-break: ticker alphabetisch
    )

    results: list[TotalRankResult] = []
    current_rank = 1
    for i, (ticker, avg) in enumerate(ranked):
        if i > 0 and avg > ranked[i - 1][1]:
            current_rank = i + 1
        results.append(
            TotalRankResult(
                ticker=ticker,
                total_rank=current_rank,
                weighted_avg=avg,
                is_sweet_spot=sweet_spot_counts.get(ticker, 0) >= 3,
            )
        )

    for ticker, wavg in weighted_avgs.items():
        if wavg is None:
            results.append(
                TotalRankResult(
                    ticker=ticker,
                    total_rank=None,
                    weighted_avg=None,
                    is_sweet_spot=False,
                )
            )

    return results
