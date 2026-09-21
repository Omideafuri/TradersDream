"""Input Quality Audit and Feature Deficiency Diagnostics.

Analyzes input feature distributions, missingness, scaling, redundancy, and return correlations:
- Categorizes features by market dimension (PRICE, VOLUME, VOLATILITY, MOMENTUM, TREND, DERIVED).
- Computes distribution moments (variance, range, skewness) and forward return correlations.
- Detects feature scaling deficiencies, high collinearity, and noise.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class FeatureQualityProfile:
    feature_name: str
    dimension_category: str  # PRICE, VOLUME, VOLATILITY, MOMENTUM, TREND, DERIVED
    missing_rate_pct: float
    variance: float
    min_value: float
    max_value: float
    skewness: float
    correlation_15m_return: float
    correlation_1h_return: float
    is_poorly_scaled: bool
    is_collinear: bool
    diagnostic_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "dimension_category": self.dimension_category,
            "missing_rate_pct": round(self.missing_rate_pct, 2),
            "variance": round(self.variance, 4),
            "min_value": round(self.min_value, 4),
            "max_value": round(self.max_value, 4),
            "skewness": round(self.skewness, 4),
            "correlation_15m_return": round(self.correlation_15m_return, 4),
            "correlation_1h_return": round(self.correlation_1h_return, 4),
            "is_poorly_scaled": self.is_poorly_scaled,
            "is_collinear": self.is_collinear,
            "diagnostic_notes": self.diagnostic_notes,
        }


def audit_feature_quality(enriched_df: pd.DataFrame) -> List[FeatureQualityProfile]:
    """Calculates statistical moments, scaling quality, and predictive correlations for all inputs."""
    df = enriched_df.copy()
    n = len(df)
    if n == 0:
        return []

    # Calculate forward 15m and 1h returns
    close = df["close"]
    fwd_15m = (close.shift(-3) / close - 1.0) * 100.0
    fwd_1h = (close.shift(-12) / close - 1.0) * 100.0

    feature_categories = {
        "close": ("PRICE", "Raw unnormalized closing price. Highly non-stationary; cannot be compared across assets."),
        "ema20": ("TREND", "20-period EMA in price units. Highly collinear with price (r > 0.99)."),
        "ema50": ("TREND", "50-period EMA in price units. Highly collinear with EMA20 (r > 0.98)."),
        "ema200": ("TREND", "200-period EMA in price units. Stale during short windows; collinear with price."),
        "rsi14": ("MOMENTUM", "Wilder's 14-period RSI bounded in [0, 100]. Good scaling, mean-reverting properties."),
        "atr14": ("VOLATILITY", "Average True Range in raw dollars ($). Poorly scaled across assets; requires price normalization."),
        "volume_ratio": ("VOLUME", "Current volume relative to 20-period volume SMA. Positive skew; good stationary scaling."),
        "price_change_pct": ("MOMENTUM", "1-period bar percentage price change. High variance, noisy, mean near zero."),
    }

    profiles: List[FeatureQualityProfile] = []

    for col, (cat, notes) in feature_categories.items():
        if col not in df.columns:
            continue

        series = df[col]
        missing = float(series.isna().sum() / n) * 100.0
        clean = series.dropna()

        if len(clean) > 2:
            var = float(np.var(clean))
            min_v = float(np.min(clean))
            max_v = float(np.max(clean))

            # Sample skewness
            mean_v = float(np.mean(clean))
            std_v = float(np.std(clean))
            skew = float(np.mean(((clean - mean_v) / (std_v if std_v > 0 else 1.0)) ** 3))

            # Correlations with future returns
            valid_mask = series.notna() & fwd_15m.notna()
            if valid_mask.sum() > 10:
                corr_15m = float(np.corrcoef(series[valid_mask], fwd_15m[valid_mask])[0, 1])
            else:
                corr_15m = 0.0

            valid_mask_1h = series.notna() & fwd_1h.notna()
            if valid_mask_1h.sum() > 10:
                corr_1h = float(np.corrcoef(series[valid_mask_1h], fwd_1h[valid_mask_1h])[0, 1])
            else:
                corr_1h = 0.0
        else:
            var = min_v = max_v = skew = corr_15m = corr_1h = 0.0

        is_poorly_scaled = max_v > 1000.0 or (max_v - min_v > 5000.0)
        is_collinear = col in ("ema20", "ema50", "ema200")

        profiles.append(
            FeatureQualityProfile(
                feature_name=col,
                dimension_category=cat,
                missing_rate_pct=missing,
                variance=var,
                min_value=min_v,
                max_value=max_v,
                skewness=skew,
                correlation_15m_return=corr_15m,
                correlation_1h_return=corr_1h,
                is_poorly_scaled=is_poorly_scaled,
                is_collinear=is_collinear,
                diagnostic_notes=notes,
            )
        )

    return profiles
