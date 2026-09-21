"""Model-Agnostic Baseline Benchmark Suite for Phase 6.

Evaluates benchmark trading models on identical out-of-sample data without parameter tuning:
1. Always HOLD: Zero trades, 0 net return, 0 friction.
2. Random Direction: Random coin-flip choice testing market efficiency.
3. Simple Momentum (3-bar): Trend continuation based on 3-bar price return.
4. Mean Reversion (RSI): Contrarian bounds (RSI < 30 Buy, RSI > 70 Sell).
5. Moving Average Crossover: EMA20 vs EMA50 hierarchy.
6. Logistic Regression: Out-of-sample linear probability estimator on normalized features.
7. Donchian Breakout: 20-bar channel breakout non-Jev predictive baseline.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from reconstruction.market_state import compute_enriched_market_state_df


@dataclass
class Phase6BaselineResult:
    symbol: str
    baseline_name: str
    total_trades: int
    win_rate_pct: float
    directional_accuracy_pct: float
    gross_return_bps: float
    net_return_bps: float
    brier_score: float
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_phase6_baselines(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    horizon_bars: int = 3,
    friction_bps: float = 30.0,
    random_seed: int = 42,
) -> List[Phase6BaselineResult]:
    """Runs all 7 baseline strategies on the out-of-sample partition of the dataset."""
    enriched = compute_enriched_market_state_df(df)
    close = enriched["close"]
    fwd_ret = (close.shift(-horizon_bars) / close - 1.0) * 100.0
    enriched["fwd_ret"] = fwd_ret

    valid = enriched.dropna(subset=["fwd_ret"]).copy()
    n = len(valid)
    if n < 50:
        return []

    # Out of sample: last 40% (Validation + Sealed Holdout)
    split_idx = int(n * 0.60)
    test_df = valid.iloc[split_idx:].copy()
    n_test = len(test_df)
    actual_up = (test_df["fwd_ret"] > 0).astype(int).values

    results: List[Phase6BaselineResult] = []

    # 1. Always HOLD
    results.append(
        Phase6BaselineResult(
            symbol=symbol,
            baseline_name="Always_HOLD",
            total_trades=0,
            win_rate_pct=0.0,
            directional_accuracy_pct=0.0,
            gross_return_bps=0.0,
            net_return_bps=0.0,
            brier_score=0.25,
            status="BENCHMARK",
        )
    )

    # 2. Random Direction
    rng = np.random.RandomState(random_seed)
    rand_choices = rng.choice([1, -1], size=n_test)
    rand_up = (rand_choices == 1).astype(int)
    rand_acc = float((rand_up == actual_up).mean()) * 100.0
    rand_gross = (rand_choices * test_df["fwd_ret"].values)
    rand_net = rand_gross - (friction_bps / 100.0)
    results.append(
        Phase6BaselineResult(
            symbol=symbol,
            baseline_name="Random_Direction",
            total_trades=n_test,
            win_rate_pct=round(float((rand_net > 0).mean()) * 100.0, 2),
            directional_accuracy_pct=round(rand_acc, 2),
            gross_return_bps=round(float(rand_gross.sum()) * 100.0, 1),
            net_return_bps=round(float(rand_net.sum()) * 100.0, 1),
            brier_score=0.50,
            status="NOT_SUPPORTED",
        )
    )

    # 3. Simple Momentum (3-bar)
    mom_3 = (test_df["close"] / test_df["close"].shift(3) - 1.0).fillna(0.0).values
    mom_choices = np.where(mom_3 > 0, 1, np.where(mom_3 < 0, -1, 0))
    mom_active = mom_choices != 0
    if mom_active.sum() > 0:
        mom_gross = mom_choices[mom_active] * test_df.loc[mom_active, "fwd_ret"].values
        mom_net = mom_gross - (friction_bps / 100.0)
        mom_wr = float((mom_net > 0).mean()) * 100.0
        mom_acc = float(((mom_choices[mom_active] == 1).astype(int) == actual_up[mom_active]).mean()) * 100.0
        mom_gross_bps = float(mom_gross.sum()) * 100.0
        mom_net_bps = float(mom_net.sum()) * 100.0
    else:
        mom_wr, mom_acc, mom_gross_bps, mom_net_bps = 0.0, 0.0, 0.0, 0.0

    results.append(
        Phase6BaselineResult(
            symbol=symbol,
            baseline_name="Simple_Momentum_3Bar",
            total_trades=int(mom_active.sum()),
            win_rate_pct=round(mom_wr, 2),
            directional_accuracy_pct=round(mom_acc, 2),
            gross_return_bps=round(mom_gross_bps, 1),
            net_return_bps=round(mom_net_bps, 1),
            brier_score=0.25,
            status="SUPPORTED" if mom_net_bps > 0 else "NOT_SUPPORTED",
        )
    )

    # 4. Mean Reversion (RSI)
    rsi_vals = test_df["rsi14"].values
    mr_choices = np.where(rsi_vals < 30, 1, np.where(rsi_vals > 70, -1, 0))
    mr_active = mr_choices != 0
    if mr_active.sum() > 0:
        mr_gross = mr_choices[mr_active] * test_df.loc[mr_active, "fwd_ret"].values
        mr_net = mr_gross - (friction_bps / 100.0)
        mr_wr = float((mr_net > 0).mean()) * 100.0
        mr_acc = float(((mr_choices[mr_active] == 1).astype(int) == actual_up[mr_active]).mean()) * 100.0
        mr_gross_bps = float(mr_gross.sum()) * 100.0
        mr_net_bps = float(mr_net.sum()) * 100.0
    else:
        mr_wr, mr_acc, mr_gross_bps, mr_net_bps = 0.0, 0.0, 0.0, 0.0

    results.append(
        Phase6BaselineResult(
            symbol=symbol,
            baseline_name="Mean_Reversion_RSI",
            total_trades=int(mr_active.sum()),
            win_rate_pct=round(mr_wr, 2),
            directional_accuracy_pct=round(mr_acc, 2),
            gross_return_bps=round(mr_gross_bps, 1),
            net_return_bps=round(mr_net_bps, 1),
            brier_score=0.25,
            status="SUPPORTED" if mr_net_bps > 0 and mr_active.sum() >= 5 else "NOT_SUPPORTED",
        )
    )

    # 5. EMA Crossover (20 vs 50)
    ema_choices = np.where(test_df["dist_ema20_pct"].values > test_df["dist_ema50_pct"].values, 1, -1)
    ema_gross = ema_choices * test_df["fwd_ret"].values
    ema_net = ema_gross - (friction_bps / 100.0)
    results.append(
        Phase6BaselineResult(
            symbol=symbol,
            baseline_name="EMA_Crossover_20_50",
            total_trades=n_test,
            win_rate_pct=round(float((ema_net > 0).mean()) * 100.0, 2),
            directional_accuracy_pct=round(float(((ema_choices == 1).astype(int) == actual_up).mean()) * 100.0, 2),
            gross_return_bps=round(float(ema_gross.sum()) * 100.0, 1),
            net_return_bps=round(float(ema_net.sum()) * 100.0, 1),
            brier_score=0.25,
            status="SUPPORTED" if ema_net.sum() > 0 else "NOT_SUPPORTED",
        )
    )

    # 6. Logistic Regression
    train_df = valid.iloc[:split_idx].copy()
    y_train = (train_df["fwd_ret"].values > 0).astype(float)
    def make_X(sub):
        x1 = sub["dist_ema20_pct"].values
        x2 = (sub["rsi14"].values - 50.0) / 10.0
        x3 = sub["atr_norm_pct"].values
        const = np.ones_like(x1)
        return np.column_stack([const, x1, x2, x3])

    X_train = make_X(train_df)
    X_test = make_X(test_df)
    lam = 1.0
    XtX = X_train.T @ X_train + lam * np.eye(X_train.shape[1])
    Xty = X_train.T @ y_train
    w = np.linalg.solve(XtX, Xty)

    p_test = 1.0 / (1.0 + np.exp(-np.clip(X_test @ w, -5.0, 5.0)))
    lr_pred_up = (p_test >= 0.5).astype(int)
    lr_choices = np.where(lr_pred_up == 1, 1, -1)
    lr_gross = lr_choices * test_df["fwd_ret"].values
    lr_net = lr_gross - (friction_bps / 100.0)
    results.append(
        Phase6BaselineResult(
            symbol=symbol,
            baseline_name="Logistic_Regression_Linear",
            total_trades=n_test,
            win_rate_pct=round(float((lr_net > 0).mean()) * 100.0, 2),
            directional_accuracy_pct=round(float((lr_pred_up == actual_up).mean()) * 100.0, 2),
            gross_return_bps=round(float(lr_gross.sum()) * 100.0, 1),
            net_return_bps=round(float(lr_net.sum()) * 100.0, 1),
            brier_score=round(float(np.mean((p_test - actual_up) ** 2)), 4),
            status="SUPPORTED" if lr_net.sum() > 0 else "NOT_SUPPORTED",
        )
    )

    # 7. Donchian Channel Breakout (20-bar rolling high/low)
    roll_high = test_df["high"].shift(1).rolling(window=20).max().values
    roll_low = test_df["low"].shift(1).rolling(window=20).min().values
    close_vals = test_df["close"].values

    donch_choices = np.where(close_vals > roll_high, 1, np.where(close_vals < roll_low, -1, 0))
    donch_active = donch_choices != 0
    if donch_active.sum() > 0:
        donch_gross = donch_choices[donch_active] * test_df.loc[donch_active, "fwd_ret"].values
        donch_net = donch_gross - (friction_bps / 100.0)
        donch_wr = float((donch_net > 0).mean()) * 100.0
        donch_acc = float(((donch_choices[donch_active] == 1).astype(int) == actual_up[donch_active]).mean()) * 100.0
        donch_gross_bps = float(donch_gross.sum()) * 100.0
        donch_net_bps = float(donch_net.sum()) * 100.0
    else:
        donch_wr, donch_acc, donch_gross_bps, donch_net_bps = 0.0, 0.0, 0.0, 0.0

    results.append(
        Phase6BaselineResult(
            symbol=symbol,
            baseline_name="Donchian_Channel_Breakout",
            total_trades=int(donch_active.sum()),
            win_rate_pct=round(donch_wr, 2),
            directional_accuracy_pct=round(donch_acc, 2),
            gross_return_bps=round(donch_gross_bps, 1),
            net_return_bps=round(donch_net_bps, 1),
            brier_score=0.25,
            status="SUPPORTED" if donch_net_bps > 0 and donch_active.sum() >= 5 else "NOT_SUPPORTED",
        )
    )

    return results
