"""Model-Agnostic Baseline Benchmark Suite.

Evaluates simple, standard benchmark strategies on identical out-of-sample data:
1. Always HOLD: Zero trades, 0 return, 0 friction.
2. Random Direction: Uniform random choice (Long/Short), testing market efficiency.
3. Simple Momentum: 3-period price momentum sign.
4. Mean Reversion: RSI extreme reversal (Long < 30, Short > 70).
5. Moving Average Crossover: EMA20 vs EMA50 hierarchy.
6. Logistic Regression: Linear probability estimator on normalized features.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd
import numpy as np


@dataclass
class BaselineBenchmarkResult:
    baseline_name: str
    total_trades: int
    win_rate_pct: float
    directional_accuracy_pct: float
    net_return_bps: float
    brier_score: float
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_name": self.baseline_name,
            "total_trades": self.total_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "directional_accuracy_pct": round(self.directional_accuracy_pct, 2),
            "net_return_bps": round(self.net_return_bps, 1),
            "brier_score": round(self.brier_score, 4),
            "status": self.status,
        }


def evaluate_baselines(
    df: pd.DataFrame, horizon_bars: int = 3, friction_bps: float = 30.0, random_seed: int = 42
) -> List[BaselineBenchmarkResult]:
    """Runs all 6 baseline strategies on the out-of-sample partition of the dataset."""
    from reconstruction.market_state import compute_enriched_market_state_df

    enriched = compute_enriched_market_state_df(df)
    close = enriched["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    enriched["fwd_ret"] = fwd_ret

    valid = enriched.dropna(subset=["fwd_ret"]).copy()
    n = len(valid)
    if n < 50:
        return []

    # Out of sample: last 40%
    split_idx = int(n * 0.60)
    test_df = valid.iloc[split_idx:].copy()
    n_test = len(test_df)
    actual_up = (test_df["fwd_ret"] > 0).astype(int)

    results: List[BaselineBenchmarkResult] = []

    # 1. Always HOLD
    results.append(
        BaselineBenchmarkResult(
            baseline_name="Always_HOLD",
            total_trades=0,
            win_rate_pct=0.0,
            directional_accuracy_pct=0.0,
            net_return_bps=0.0,
            brier_score=0.25,
            status="BENCHMARK",
        )
    )

    # 2. Random Direction (Seed=42)
    rng = np.random.RandomState(random_seed)
    rand_choices = rng.choice([1, -1], size=n_test)
    rand_up = (rand_choices == 1).astype(int)
    rand_acc = float((rand_up == actual_up).mean()) * 100.0
    rand_rets = (rand_choices * test_df["fwd_ret"]) - (friction_bps / 100.0)
    rand_wr = float((rand_rets > 0).mean()) * 100.0
    rand_tot_bps = float(rand_rets.sum()) * 100.0
    rand_brier = 0.50  # uniform 0.5 brier

    results.append(
        BaselineBenchmarkResult(
            baseline_name="Random_Direction",
            total_trades=n_test,
            win_rate_pct=rand_wr,
            directional_accuracy_pct=rand_acc,
            net_return_bps=rand_tot_bps,
            brier_score=rand_brier,
            status="NOT_SUPPORTED",
        )
    )

    # 3. Simple Momentum (3-bar return sign)
    mom_3 = (test_df["close"] / test_df["close"].shift(3) - 1.0).fillna(0.0)
    mom_choices = np.where(mom_3 > 0, 1, np.where(mom_3 < 0, -1, 0))
    mom_active = mom_choices != 0
    if mom_active.sum() > 0:
        mom_rets = (mom_choices[mom_active] * test_df.loc[mom_active, "fwd_ret"]) - (friction_bps / 100.0)
        mom_wr = float((mom_rets > 0).mean()) * 100.0
        mom_acc = float(((mom_choices[mom_active] == 1).astype(int) == actual_up[mom_active]).mean()) * 100.0
        mom_tot_bps = float(mom_rets.sum()) * 100.0
    else:
        mom_wr, mom_acc, mom_tot_bps = 0.0, 0.0, 0.0

    results.append(
        BaselineBenchmarkResult(
            baseline_name="Simple_Momentum_3Bar",
            total_trades=int(mom_active.sum()),
            win_rate_pct=mom_wr,
            directional_accuracy_pct=mom_acc,
            net_return_bps=mom_tot_bps,
            brier_score=0.25,
            status="SUPPORTED" if mom_tot_bps > 0 else "NOT_SUPPORTED",
        )
    )

    # 4. Mean Reversion (RSI < 30 Buy, RSI > 70 Sell)
    rsi_col = test_df["rsi14"]
    mr_choices = np.where(rsi_col < 30, 1, np.where(rsi_col > 70, -1, 0))
    mr_active = mr_choices != 0
    if mr_active.sum() > 0:
        mr_rets = (mr_choices[mr_active] * test_df.loc[mr_active, "fwd_ret"]) - (friction_bps / 100.0)
        mr_wr = float((mr_rets > 0).mean()) * 100.0
        mr_acc = float(((mr_choices[mr_active] == 1).astype(int) == actual_up[mr_active]).mean()) * 100.0
        mr_tot_bps = float(mr_rets.sum()) * 100.0
    else:
        mr_wr, mr_acc, mr_tot_bps = 0.0, 0.0, 0.0

    results.append(
        BaselineBenchmarkResult(
            baseline_name="Mean_Reversion_RSI",
            total_trades=int(mr_active.sum()),
            win_rate_pct=mr_wr,
            directional_accuracy_pct=mr_acc,
            net_return_bps=mr_tot_bps,
            brier_score=0.25,
            status="SUPPORTED" if mr_tot_bps > 0 and mr_active.sum() >= 5 else "NOT_SUPPORTED",
        )
    )

    # 5. EMA Crossover (EMA20 vs EMA50)
    ema_choices = np.where(test_df["dist_ema20_pct"] > test_df["dist_ema50_pct"], 1, -1)
    ema_rets = (ema_choices * test_df["fwd_ret"]) - (friction_bps / 100.0)
    ema_wr = float((ema_rets > 0).mean()) * 100.0
    ema_acc = float(((ema_choices == 1).astype(int) == actual_up).mean()) * 100.0
    ema_tot_bps = float(ema_rets.sum()) * 100.0

    results.append(
        BaselineBenchmarkResult(
            baseline_name="EMA_Crossover_20_50",
            total_trades=n_test,
            win_rate_pct=ema_wr,
            directional_accuracy_pct=ema_acc,
            net_return_bps=ema_tot_bps,
            brier_score=0.25,
            status="SUPPORTED" if ema_tot_bps > 0 else "NOT_SUPPORTED",
        )
    )

    # 6. Simple Logistic Regression (Linear Log-Odds Estimator)
    # Train on first 60%
    train_df = valid.iloc[:split_idx].copy()
    y_train = (train_df["fwd_ret"] > 0).astype(float).values
    # Feature matrix X: dist_ema20, rsi14, atr_norm
    def make_X(sub):
        x1 = sub["dist_ema20_pct"].values
        x2 = (sub["rsi14"].values - 50.0) / 10.0
        x3 = sub["atr_norm_pct"].values
        const = np.ones_like(x1)
        return np.column_stack([const, x1, x2, x3])

    X_train = make_X(train_df)
    X_test = make_X(test_df)

    # Simple Ridge / Regularized Normal Equations: w = (X^T X + lambda I)^-1 X^T y
    lam = 1.0
    XtX = X_train.T @ X_train + lam * np.eye(X_train.shape[1])
    Xty = X_train.T @ y_train
    w = np.linalg.solve(XtX, Xty)

    # Predict test probabilities via sigmoid of linear predictor
    linear_pred = X_test @ w
    p_test = 1.0 / (1.0 + np.exp(-np.clip(linear_pred, -5.0, 5.0)))
    lr_pred_up = (p_test >= 0.5).astype(int)
    lr_choices = np.where(lr_pred_up == 1, 1, -1)
    lr_acc = float((lr_pred_up == actual_up).mean()) * 100.0
    lr_rets = (lr_choices * test_df["fwd_ret"]) - (friction_bps / 100.0)
    lr_wr = float((lr_rets > 0).mean()) * 100.0
    lr_tot_bps = float(lr_rets.sum()) * 100.0
    lr_brier = float(np.mean((p_test - actual_up) ** 2))

    results.append(
        BaselineBenchmarkResult(
            baseline_name="Logistic_Regression_Linear",
            total_trades=n_test,
            win_rate_pct=lr_wr,
            directional_accuracy_pct=lr_acc,
            net_return_bps=lr_tot_bps,
            brier_score=lr_brier,
            status="SUPPORTED" if lr_tot_bps > 0 and lr_acc > 52.0 else "NOT_SUPPORTED",
        )
    )

    return results
