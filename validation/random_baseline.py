"""Deterministic Random Baseline Framework and Empirical Null Distributions.

Implements:
1. Random Direction Baseline: Randomly chooses LONG or SHORT at identical opportunity timestamps.
2. Randomized Jev Permutation: Preserves the exact distribution of Jev actions but randomly permutes them across timestamps.
3. Compares actual Jev performance against empirical null distributions (calculating empirical p-values).
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from backtest.dataset import HistoricalDecision
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult


@dataclass
class NullDistributionSummary:
    baseline_type: str
    n_iterations: int
    mean_return_pct: float
    median_return_pct: float
    std_return_pct: float
    min_return_pct: float
    max_return_pct: float
    empirical_p_value_return: float  # P(Null Return >= Jev Return)
    empirical_p_value_win_rate: float
    mean_win_rate_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_type": self.baseline_type,
            "n_iterations": self.n_iterations,
            "mean_return_pct": round(self.mean_return_pct, 4),
            "median_return_pct": round(self.median_return_pct, 4),
            "std_return_pct": round(self.std_return_pct, 4),
            "min_return_pct": round(self.min_return_pct, 4),
            "max_return_pct": round(self.max_return_pct, 4),
            "empirical_p_value_return": round(self.empirical_p_value_return, 4),
            "empirical_p_value_win_rate": round(self.empirical_p_value_win_rate, 4),
            "mean_win_rate_pct": round(self.mean_win_rate_pct, 2),
        }


class RandomBaselineEngine:
    """Generates empirical null distributions to test against statistical flukes."""

    def __init__(self, config: BacktestConfig, n_simulations: int = 50, base_seed: int = 42):
        self.config = config
        self.n_simulations = n_simulations
        self.base_seed = base_seed
        self.engine = BacktestEngine(config)

    def generate_random_direction_decisions(
        self,
        template_decisions: List[HistoricalDecision],
        seed: int,
    ) -> List[HistoricalDecision]:
        """Generates random LONG/SHORT decisions at identical timestamps."""
        rng = np.random.default_rng(seed)
        randomized = []

        for d in template_decisions:
            # 50/50 chance of LONG vs SHORT, keeping same confidence level
            action = "LONG" if rng.uniform() > 0.5 else "SHORT"
            randomized.append(
                HistoricalDecision(
                    timestamp=d.timestamp,
                    symbol=d.symbol,
                    timeframe=d.timeframe,
                    price=d.price,
                    action=action,
                    confidence=d.confidence,
                    prob_hold=0.0,
                    prob_long=0.5,
                    prob_short=0.5,
                )
            )
        return randomized

    def generate_permuted_jev_decisions(
        self,
        template_decisions: List[HistoricalDecision],
        seed: int,
    ) -> List[HistoricalDecision]:
        """Permutes Jev decision actions across timestamps, preserving exact class counts."""
        rng = np.random.default_rng(seed)
        actions = [d.action for d in template_decisions]
        confidences = [d.confidence for d in template_decisions]

        shuffled_indices = rng.permutation(len(template_decisions))
        permuted = []

        for i, d in enumerate(template_decisions):
            idx = shuffled_indices[i]
            permuted.append(
                HistoricalDecision(
                    timestamp=d.timestamp,
                    symbol=d.symbol,
                    timeframe=d.timeframe,
                    price=d.price,
                    action=actions[idx],
                    confidence=confidences[idx],
                    prob_hold=d.prob_hold,
                    prob_long=d.prob_long,
                    prob_short=d.prob_short,
                )
            )
        return permuted

    def evaluate_null_distribution(
        self,
        candles_df: pd.DataFrame,
        actual_decisions: List[HistoricalDecision],
        actual_result: BacktestResult,
        baseline_type: str = "random_direction",
    ) -> NullDistributionSummary:
        """Runs Monte Carlo simulations to generate empirical null distribution."""
        returns = []
        win_rates = []

        for i in range(self.n_simulations):
            sim_seed = self.base_seed + i * 17
            if baseline_type == "random_direction":
                sim_decisions = self.generate_random_direction_decisions(actual_decisions, sim_seed)
            else:
                sim_decisions = self.generate_permuted_jev_decisions(actual_decisions, sim_seed)

            res = self.engine.run(candles_df, sim_decisions)
            returns.append(res.metrics.total_return_pct)
            win_rates.append(res.metrics.win_rate_pct)

        arr_ret = np.array(returns)
        arr_wr = np.array(win_rates)

        actual_ret = actual_result.metrics.total_return_pct
        actual_wr = actual_result.metrics.win_rate_pct

        # Empirical p-value: Fraction of random iterations that achieved >= actual return
        p_val_ret = float((arr_ret >= actual_ret).sum() / self.n_simulations)
        p_val_wr = float((arr_wr >= actual_wr).sum() / self.n_simulations)

        return NullDistributionSummary(
            baseline_type=baseline_type,
            n_iterations=self.n_simulations,
            mean_return_pct=float(np.mean(arr_ret)),
            median_return_pct=float(np.median(arr_ret)),
            std_return_pct=float(np.std(arr_ret)),
            min_return_pct=float(np.min(arr_ret)),
            max_return_pct=float(np.max(arr_ret)),
            empirical_p_value_return=p_val_ret,
            empirical_p_value_win_rate=p_val_wr,
            mean_win_rate_pct=float(np.mean(arr_wr)),
        )
