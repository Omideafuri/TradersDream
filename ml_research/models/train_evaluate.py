"""
XAU/USD ML Research Track — Model Training & Forensic Walk-Forward Evaluation
Evaluates whether lightweight ML can extract predictive edge on XAU/USD after realistic transaction costs.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
from sklearn.preprocessing import StandardScaler

from ml_research.features.feature_pipeline import (
    FEATURE_NAMES,
    WARMUP_BARS,
    compute_features,
)
from ml_research.labels.label_generator import HORIZONS, compute_labels

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR.parent / "phase11" / "data" / "processed" / "XAUUSD_1H_2021_2025.csv"
ARTIFACTS_DIR = BASE_DIR / "artifacts"


def load_dataset() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads raw 1H data, computes causal features and forward labels.
    Returns: (raw_df, features_df, labels_df)
    """
    logging.info(f"Loading authoritative raw dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    df["dt_utc"] = pd.to_datetime(df["dt_utc"], utc=True)
    df = df.sort_values("dt_utc").reset_index(drop=True)

    logging.info("Computing 24 causal features...")
    df_feat = compute_features(df)

    logging.info("Computing forward labels (4H, 12H, 24H) with realistic friction...")
    df_labels = compute_labels(df)

    return df, df_feat, df_labels


def calculate_trading_metrics(
    returns: np.ndarray, positions: np.ndarray, horizon: int
) -> Dict[str, float]:
    """
    Calculates trading performance metrics for active positions.
    Annualization factor uses ~5,900 hourly bars per trading year:
    bars_per_year = 5900 / horizon
    """
    if len(positions) == 0 or positions.sum() == 0:
        return {
            "trade_count": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "cumulative_return_pct": 0.0,
            "annualized_sharpe": 0.0,
            "max_drawdown_pct": 0.0,
            "mean_net_return_bps": 0.0,
        }

    active_rets = returns[positions == 1]
    trade_count = len(active_rets)

    wins = active_rets[active_rets > 0]
    losses = active_rets[active_rets < 0]
    win_rate = len(wins) / trade_count if trade_count > 0 else 0.0

    sum_wins = wins.sum() if len(wins) > 0 else 0.0
    sum_losses = np.abs(losses.sum()) if len(losses) > 0 else 0.0
    profit_factor = float(sum_wins / sum_losses) if sum_losses > 0 else (999.0 if sum_wins > 0 else 0.0)

    # Cumulative equity curve (uncompounded net return sum)
    equity = np.cumsum(active_rets)
    cum_ret_pct = float(equity[-1] * 100.0) if len(equity) > 0 else 0.0

    # Drawdown
    peaks = np.maximum.accumulate(equity)
    drawdowns = peaks - equity
    max_dd_pct = float(np.max(drawdowns) * 100.0) if len(drawdowns) > 0 else 0.0

    # Annualized Sharpe
    # In rolling evaluations, positions taken sequentially at interval horizon
    bars_per_year = 5900.0 / horizon
    std_ret = np.std(active_rets)
    if std_ret > 1e-12:
        sharpe = float((np.mean(active_rets) / std_ret) * np.sqrt(bars_per_year))
    else:
        sharpe = 0.0

    mean_bps = float(np.mean(active_rets) * 10000.0)

    return {
        "trade_count": int(trade_count),
        "win_rate": round(win_rate * 100.0, 2),
        "profit_factor": round(profit_factor, 2),
        "cumulative_return_pct": round(cum_ret_pct, 2),
        "annualized_sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "mean_net_return_bps": round(mean_bps, 2),
    }


def evaluate_classifier(
    y_true: np.ndarray, y_prob: np.ndarray, y_pred: np.ndarray
) -> Dict[str, float]:
    """
    Computes standard statistical and probabilistic classification metrics.
    """
    # Safe metrics when y_true or y_pred has single class
    try:
        roc_auc = float(roc_auc_score(y_true, y_prob))
    except Exception:
        roc_auc = 0.5

    try:
        pr_auc = float(average_precision_score(y_true, y_prob))
    except Exception:
        pr_auc = float(np.mean(y_true))

    brier = float(brier_score_loss(y_true, y_prob))
    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    return {
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "accuracy": round(acc * 100.0, 2),
        "precision": round(prec * 100.0, 2),
        "recall": round(rec * 100.0, 2),
        "f1": round(f1, 4),
    }


def run_experiment() -> Dict[str, Any]:
    """
    Executes full forensic research experiment across all models, horizons, and walk-forward folds.
    """
    df, df_feat, df_labels = load_dataset()
    dt = df["dt_utc"]

    results: Dict[str, Any] = {
        "metadata": {
            "dataset_rows": len(df),
            "feature_count": len(FEATURE_NAMES),
            "features": FEATURE_NAMES,
            "warmup_bars": WARMUP_BARS,
        },
        "horizons": {},
        "walk_forward_folds": {},
        "threshold_sweeps": {},
        "feature_importances": {},
        "monotonicity": {},
    }

    # Evaluate each horizon
    for h in HORIZONS:
        logging.info(f"\n=======================================================")
        logging.info(f"EVALUATING HORIZON: {h} HOURS (Target: target_{h}h)")
        logging.info(f"=======================================================")

        target_col = f"target_{h}h"
        ret_net_col = f"ret_net_{h}h"

        # Split indices
        # Train: 2021-2023 (dt < 2024-01-01), drop warmup & drop last h+1 bars of 2023
        train_mask = (dt < "2024-01-01 00:00:00+00:00") & (df.index >= WARMUP_BARS)
        # Purge / Embargo: drop last h+1 bars before 2024
        train_indices = df[train_mask].index[:- (h + 1)]

        # Val: 2024 (2024-01-01 <= dt < 2025-01-01), drop last h+1 bars of 2024
        val_mask = (dt >= "2024-01-01 00:00:00+00:00") & (dt < "2025-01-01 00:00:00+00:00")
        val_indices = df[val_mask].index[:- (h + 1)]

        # Holdout: 2025 (dt >= 2025-01-01), drop last h+1 bars of dataset
        holdout_mask = (dt >= "2025-01-01 00:00:00+00:00")
        holdout_indices = df[holdout_mask].index[:- (h + 1)]

        logging.info(f"  Train bars (2021-2023 purged): {len(train_indices):,}")
        logging.info(f"  Val bars (2024 purged):         {len(val_indices):,}")
        logging.info(f"  Holdout bars (2025 purged):     {len(holdout_indices):,}")

        X_train_raw = df_feat.loc[train_indices, FEATURE_NAMES].to_numpy()
        y_train = df_labels.loc[train_indices, target_col].to_numpy().astype(int)
        r_train = df_labels.loc[train_indices, ret_net_col].to_numpy()

        X_val_raw = df_feat.loc[val_indices, FEATURE_NAMES].to_numpy()
        y_val = df_labels.loc[val_indices, target_col].to_numpy().astype(int)
        r_val = df_labels.loc[val_indices, ret_net_col].to_numpy()

        X_holdout_raw = df_feat.loc[holdout_indices, FEATURE_NAMES].to_numpy()
        y_holdout = df_labels.loc[holdout_indices, target_col].to_numpy().astype(int)
        r_holdout = df_labels.loc[holdout_indices, ret_net_col].to_numpy()

        # Strict Causal Scaler: Fit on Train ONLY
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train_raw)
        X_val = scaler.transform(X_val_raw)
        X_holdout = scaler.transform(X_holdout_raw)

        # Baselines on Validation & Holdout
        # Baseline 1: Majority Class
        train_prior = float(np.mean(y_train))
        maj_prob_val = np.full(len(y_val), train_prior)
        maj_pred_val = (maj_prob_val >= 0.5).astype(int)
        maj_prob_holdout = np.full(len(y_holdout), train_prior)
        maj_pred_holdout = (maj_prob_holdout >= 0.5).astype(int)

        # Baseline 2: Always Long
        always_long_prob_val = np.ones(len(y_val))
        always_long_pred_val = np.ones(len(y_val), dtype=int)
        always_long_prob_holdout = np.ones(len(y_holdout))
        always_long_pred_holdout = np.ones(len(y_holdout), dtype=int)

        # Baseline 3: Frozen SMA50/200
        sma_val_sig = df_feat.loc[val_indices, "sma_trend_regime"].to_numpy().astype(int)
        sma_holdout_sig = df_feat.loc[holdout_indices, "sma_trend_regime"].to_numpy().astype(int)

        # Models
        models = {
            "logistic_regression": LogisticRegression(C=1.0, max_iter=1000, random_state=42),
            "random_forest": RandomForestClassifier(
                n_estimators=100, max_depth=5, min_samples_leaf=50, random_state=42, n_jobs=-1
            ),
            "hist_gradient_boosting": HistGradientBoostingClassifier(
                max_iter=100, max_depth=4, min_samples_leaf=50, random_state=42
            ),
        }

        horizon_summary: Dict[str, Any] = {
            "class_distribution": {
                "train_pos_pct": round(train_prior * 100.0, 2),
                "val_pos_pct": round(float(np.mean(y_val)) * 100.0, 2),
                "holdout_pos_pct": round(float(np.mean(y_holdout)) * 100.0, 2),
            },
            "baselines": {
                "majority_class": {
                    "val_metrics": evaluate_classifier(y_val, maj_prob_val, maj_pred_val),
                    "holdout_metrics": evaluate_classifier(y_holdout, maj_prob_holdout, maj_pred_holdout),
                },
                "always_long": {
                    "val_trading": calculate_trading_metrics(r_val, always_long_pred_val, h),
                    "holdout_trading": calculate_trading_metrics(r_holdout, always_long_pred_holdout, h),
                },
                "frozen_sma50_200": {
                    "val_trading": calculate_trading_metrics(r_val, sma_val_sig, h),
                    "holdout_trading": calculate_trading_metrics(r_holdout, sma_holdout_sig, h),
                },
            },
            "models": {},
        }

        # Train and evaluate models
        for m_name, model in models.items():
            logging.info(f"  Training {m_name} on Train (2021-2023)...")
            model.fit(X_train, y_train)

            # Probabilities
            p_val = model.predict_proba(X_val)[:, 1]
            p_holdout = model.predict_proba(X_holdout)[:, 1]

            # Default threshold 0.50
            pred_val_def = (p_val >= 0.5).astype(int)
            pred_holdout_def = (p_holdout >= 0.5).astype(int)

            val_clf_metrics = evaluate_classifier(y_val, p_val, pred_val_def)
            holdout_clf_metrics = evaluate_classifier(y_holdout, p_holdout, pred_holdout_def)

            val_trading_def = calculate_trading_metrics(r_val, pred_val_def, h)
            holdout_trading_def = calculate_trading_metrics(r_holdout, pred_holdout_def, h)

            # Threshold search on Validation set [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
            threshold_grid = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
            best_thresh = 0.50
            best_val_sharpe = -999.0
            val_sweep = []

            for tau in threshold_grid:
                sig_tau = (p_val >= tau).astype(int)
                t_metrics = calculate_trading_metrics(r_val, sig_tau, h)
                val_sweep.append({"threshold": tau, **t_metrics})

                # Optimization constraint: min 30 trades on validation
                if t_metrics["trade_count"] >= 30 and t_metrics["annualized_sharpe"] > best_val_sharpe:
                    best_val_sharpe = t_metrics["annualized_sharpe"]
                    best_thresh = tau

            # Freeze best threshold and evaluate on Holdout ONCE
            sig_holdout_frozen = (p_holdout >= best_thresh).astype(int)
            holdout_trading_frozen = calculate_trading_metrics(r_holdout, sig_holdout_frozen, h)

            # Hybrid strategy: Frozen SMA50/200 AND ML >= best_thresh
            sig_hybrid_val = (sma_val_sig == 1) & (p_val >= best_thresh)
            hybrid_val_trading = calculate_trading_metrics(r_val, sig_hybrid_val.astype(int), h)

            sig_hybrid_holdout = (sma_holdout_sig == 1) & (p_holdout >= best_thresh)
            hybrid_holdout_trading = calculate_trading_metrics(r_holdout, sig_hybrid_holdout.astype(int), h)

            horizon_summary["models"][m_name] = {
                "val_classification_default": val_clf_metrics,
                "holdout_classification_default": holdout_clf_metrics,
                "val_trading_default": val_trading_def,
                "holdout_trading_default": holdout_trading_def,
                "threshold_sweep_val": val_sweep,
                "frozen_threshold": best_thresh,
                "holdout_trading_frozen_threshold": holdout_trading_frozen,
                "hybrid_strategy": {
                    "val_trading": hybrid_val_trading,
                    "holdout_trading": hybrid_holdout_trading,
                },
            }

            logging.info(
                f"    [{m_name}] Val AUC: {val_clf_metrics['roc_auc']:.4f} | "
                f"Holdout AUC: {holdout_clf_metrics['roc_auc']:.4f} | "
                f"Frozen Thresh: {best_thresh:.2f} | "
                f"Holdout Sharpe: {holdout_trading_frozen['annualized_sharpe']:.2f} | "
                f"Hybrid Holdout Sharpe: {hybrid_holdout_trading['annualized_sharpe']:.2f}"
            )

        results["horizons"][f"{h}h"] = horizon_summary

    # --- Feature Importance Analysis (Primary Horizon = 24H) ---
    logging.info("\nExtracting feature importances for Horizon 24H...")
    # Re-train models on 2021-2023 for 24H to extract weights
    y_24h_train = df_labels.loc[train_indices, "target_24h"].to_numpy().astype(int)
    scaler_24 = StandardScaler()
    X_train_24 = scaler_24.fit_transform(df_feat.loc[train_indices, FEATURE_NAMES].to_numpy())

    lr_24 = LogisticRegression(C=1.0, max_iter=1000, random_state=42).fit(X_train_24, y_24h_train)
    rf_24 = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_leaf=50, random_state=42).fit(
        X_train_24, y_24h_train
    )

    feat_imp = []
    for i, fname in enumerate(FEATURE_NAMES):
        feat_imp.append({
            "feature": fname,
            "lr_coefficient": round(float(lr_24.coef_[0][i]), 5),
            "rf_importance": round(float(rf_24.feature_importances_[i]), 5),
        })
    df_feat_imp = pd.DataFrame(feat_imp).sort_values("rf_importance", ascending=False)
    results["feature_importances"] = df_feat_imp.to_dict(orient="records")

    # --- Monotonicity Analysis (Horizon 24H, HistGradientBoosting on Holdout) ---
    logging.info("Conducting economic calibration / monotonicity analysis...")
    hgb_24 = HistGradientBoostingClassifier(max_iter=100, max_depth=4, min_samples_leaf=50, random_state=42)
    hgb_24.fit(X_train_24, y_24h_train)
    X_holdout_24 = scaler_24.transform(df_feat.loc[holdout_indices, FEATURE_NAMES].to_numpy())
    p_holdout_24 = hgb_24.predict_proba(X_holdout_24)[:, 1]
    r_holdout_24 = df_labels.loc[holdout_indices, "ret_net_24h"].to_numpy()

    bins = [0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 1.0]
    bin_labels = ["<0.40", "0.40-0.45", "0.45-0.50", "0.50-0.55", "0.55-0.60", ">=0.60"]
    binned = pd.cut(p_holdout_24, bins=bins, labels=bin_labels, include_lowest=True)

    df_mono = pd.DataFrame({"bin": binned, "ret_net": r_holdout_24})
    mono_stats = []
    for bl in bin_labels:
        subset = df_mono[df_mono["bin"] == bl]
        count = len(subset)
        mean_bps = float(subset["ret_net"].mean() * 10000.0) if count > 0 else 0.0
        win_rate = float((subset["ret_net"] > 0).mean() * 100.0) if count > 0 else 0.0
        mono_stats.append({
            "probability_bin": bl,
            "observations": int(count),
            "win_rate_pct": round(win_rate, 2),
            "mean_net_return_bps": round(mean_bps, 2),
        })
    results["monotonicity"]["24h_holdout"] = mono_stats

    # --- Walk-Forward Rolling Folds (Horizon 24H, HistGradientBoosting) ---
    logging.info("\n=======================================================")
    logging.info("EXECUTING 4-FOLD WALK-FORWARD ROLLING EVALUATION (24H)")
    logging.info("=======================================================")

    folds = [
        {"fold": 1, "train_years": [2021], "test_year": 2022},
        {"fold": 2, "train_years": [2021, 2022], "test_year": 2023},
        {"fold": 3, "train_years": [2021, 2022, 2023], "test_year": 2024},
        {"fold": 4, "train_years": [2021, 2022, 2023, 2024], "test_year": 2025},
    ]

    h_wf = 24
    wf_results = []
    for f in folds:
        fold_id = f["fold"]
        tr_years = f["train_years"]
        te_year = f["test_year"]

        dt_year = dt.dt.year
        tr_mask = dt_year.isin(tr_years) & (df.index >= WARMUP_BARS)
        # Purge last h+1 bars of train period
        tr_idx = df[tr_mask].index[:- (h_wf + 1)]

        te_mask = (dt_year == te_year)
        te_idx = df[te_mask].index[:- (h_wf + 1)]

        X_tr = df_feat.loc[tr_idx, FEATURE_NAMES].to_numpy()
        y_tr = df_labels.loc[tr_idx, f"target_{h_wf}h"].to_numpy().astype(int)

        X_te = df_feat.loc[te_idx, FEATURE_NAMES].to_numpy()
        y_te = df_labels.loc[te_idx, f"target_{h_wf}h"].to_numpy().astype(int)
        r_te = df_labels.loc[te_idx, f"ret_net_{h_wf}h"].to_numpy()

        scaler_f = StandardScaler()
        X_tr_sc = scaler_f.fit_transform(X_tr)
        X_te_sc = scaler_f.transform(X_te)

        # Train HGB
        clf = HistGradientBoostingClassifier(max_iter=100, max_depth=4, min_samples_leaf=50, random_state=42)
        clf.fit(X_tr_sc, y_tr)

        p_te = clf.predict_proba(X_te_sc)[:, 1]
        pred_te = (p_te >= 0.5).astype(int)

        # Baselines on test fold
        prior_tr = float(np.mean(y_tr))
        maj_prob = np.full(len(y_te), prior_tr)
        maj_pred = (maj_prob >= 0.5).astype(int)

        clf_metrics = evaluate_classifier(y_te, p_te, pred_te)
        maj_metrics = evaluate_classifier(y_te, maj_prob, maj_pred)

        trading_metrics = calculate_trading_metrics(r_te, pred_te, h_wf)
        always_long_metrics = calculate_trading_metrics(r_te, np.ones(len(y_te), dtype=int), h_wf)

        sma_sig = df_feat.loc[te_idx, "sma_trend_regime"].to_numpy().astype(int)
        sma_metrics = calculate_trading_metrics(r_te, sma_sig, h_wf)

        fold_record = {
            "fold": fold_id,
            "train_years": tr_years,
            "test_year": te_year,
            "train_bars": len(tr_idx),
            "test_bars": len(te_idx),
            "test_pos_rate_pct": round(float(np.mean(y_te)) * 100.0, 2),
            "ml_roc_auc": clf_metrics["roc_auc"],
            "ml_pr_auc": clf_metrics["pr_auc"],
            "ml_brier": clf_metrics["brier_score"],
            "ml_accuracy": clf_metrics["accuracy"],
            "ml_sharpe": trading_metrics["annualized_sharpe"],
            "ml_win_rate_pct": trading_metrics["win_rate"],
            "ml_profit_factor": trading_metrics["profit_factor"],
            "ml_cum_ret_pct": trading_metrics["cumulative_return_pct"],
            "always_long_sharpe": always_long_metrics["annualized_sharpe"],
            "frozen_sma_sharpe": sma_metrics["annualized_sharpe"],
        }
        wf_results.append(fold_record)

        logging.info(
            f"  Fold {fold_id} ({tr_years} -> {te_year}): AUC={clf_metrics['roc_auc']:.4f} | "
            f"ML Sharpe={trading_metrics['annualized_sharpe']:.2f} | "
            f"Always Long Sharpe={always_long_metrics['annualized_sharpe']:.2f} | "
            f"SMA Sharpe={sma_metrics['annualized_sharpe']:.2f}"
        )

    results["walk_forward_folds"] = wf_results

    # Save artifact
    output_path = ARTIFACTS_DIR / "ml_experiment_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logging.info(f"\n[+] Successfully exported ML experiment results to {output_path}")

    # Export Feature Importance CSV
    df_feat_imp.to_csv(ARTIFACTS_DIR / "feature_importances.csv", index=False)
    # Export Walk Forward CSV
    pd.DataFrame(wf_results).to_csv(ARTIFACTS_DIR / "walk_forward_results.csv", index=False)

    return results


if __name__ == "__main__":
    run_experiment()
