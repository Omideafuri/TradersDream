# Crypto Trading Bot — Phase 1 (Paper Trading Foundation)

A local, deterministic, paper-trading-only cryptocurrency trading bot built in Python 3.12. Designed as a safe, testable foundation for future AI-assisted trading systems.

---

## Safety Invariants & Guardrails

- **Paper Trading Only**: Real trading execution paths are strictly forbidden. The system refuses to boot if `PAPER_TRADING_ONLY` is not set to `true`.
- **Zero Real Money**: Operates exclusively against a simulated virtual portfolio (default: $10,000).
- **Zero Real Exchange Orders**: All order fills, position sizing, fees, and P&L tracking occur entirely in memory.
- **No Leverage**: Leverage is locked at 1.0x.
- **No API Secrets in Code**: Configuration is loaded strictly from environment variables (`.env`). Public market data endpoints require no API keys.

---

## Architecture

```
crypto-trading-bot/
├── bot/
│   ├── __init__.py           # Package marker & version
│   ├── config.py             # Configuration dataclass, env loading, safety check
│   ├── market_data.py        # Public exchange Kline fetcher (BTC/USDT 5m)
│   ├── indicators.py         # Deterministic indicators (EMA, RSI, ATR, Vol MA) & MarketState
│   ├── decision.py           # Jev decision layer (LONG/SHORT/HOLD), validation & timeouts
│   ├── risk.py               # Deterministic risk engine (0.5% risk, 2% daily loss, 10% max pos)
│   ├── paper_trader.py       # Paper trading engine (balance, positions, fees, P&L, drawdown)
│   └── main.py               # Async bot orchestration loop & structured decision logging
│
├── tests/
│   ├── __init__.py
│   ├── test_indicators.py    # RSI, EMA, ATR, Volume MA, MarketState tests
│   ├── test_risk.py          # Risk limits, daily loss, max position size, trade rejection tests
│   ├── test_paper_trader.py  # Paper buy, paper sell, P&L, fees, drawdown tests
│   ├── test_decision.py      # Jev validation, fallback to HOLD, timeout tests
│   └── test_safety.py        # Safety tripwire tests (refuses real execution / leverage)
│
├── data/                     # Local data directory
├── .env.example              # Sample environment template
├── .gitignore                # Git ignore rules
├── requirements.txt          # Pinned minimal dependencies
└── README.md                 # System documentation
```

---

## Modules Overview

### 1. Market Data (`bot/market_data.py`)
- Collects public 5-minute OHLCV candles for `BTCUSDT` without API credentials.
- Parses candles into standardized pandas DataFrames with timestamps, open, high, low, close, and volume.
- Includes synthetic candle generator for offline simulation and isolated testing.

### 2. Indicators (`bot/indicators.py`)
Deterministic technical indicators computed via `pandas` and `numpy`:
- **EMA 20, 50, 200**: Exponential moving averages.
- **RSI 14**: Wilder's smoothed Relative Strength Index bounded in `[0.0, 100.0]`.
- **ATR 14**: Average True Range for volatility-based sizing.
- **Volume Moving Average**: SMA 20 of volume and volume ratio calculation.
- **MarketState**: Immutable, JSON-serializable structured state object.

### 3. Jev Decision Layer (`bot/decision.py`)
- Completely isolated from order execution and risk controls.
- Connects directly to TypeSafe AI's Jev "System One" decision model endpoint (`https://api.typesafe.ai/v1/systemone`) via `JevApiProvider`.
- Strictly accepts structured `MarketState` input and formulates deterministic choice-based questions.
- Decision output constrained to `LONG`, `SHORT`, or `HOLD`.
- **Confidence Threshold**: Implements gating where decisions below threshold (e.g. 0.60) default safely to `HOLD` with `LOW_CONFIDENCE`.
- **Failsafe**: If Jev is unavailable, times out, returns malformed JSON, auth fails, or outputs unexpected commands, the action defaults strictly to `HOLD` with confidence `0.0`. Never trades on error.
- **RuleBasedJev**: Deterministic baseline mock preserved for isolated unit testing.

### 4. Risk Engine (`bot/risk.py`)
Deterministic safety layer operating independently of Jev:
- **Maximum Risk Per Trade**: 0.5% of paper portfolio.
- **Maximum Daily Loss**: 2.0% (trading halts if cumulative daily loss reaches limit).
- **Maximum Position Size**: 10.0% of portfolio equity.
- **Maximum Open Positions**: Exactly 1 position at any time.
- **No Leverage**: Strictly 1.0x.
- **No Averaging Down**: Rejects increasing size when a position is in loss.
- **No Martingale / Revenge Trading**: Position sizing cannot scale up following a losing trade.
- **Rejection Authority**: Can reject any Jev decision, forcing final action to `HOLD`.

### 5. Paper Trading Engine (`bot/paper_trader.py`)
- Starting virtual balance: **$10,000.00**.
- Virtual order execution (entry and exit).
- Realistic exchange fees (e.g. 0.075% taker fee).
- Computes gross/net realized P&L, live unrealized P&L, portfolio equity, and peak-to-trough drawdown.

---

## Setup & Running

### 1. Prerequisites
- Python 3.12+ (managed via `uv` or standard Python)

### 2. Installation
Create and activate virtual environment, then install dependencies:
```bash
uv venv --python 3.12 .venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the example configuration:
```bash
copy .env.example .env
```

### 4. Run Automated Tests
```bash
.venv\Scripts\pytest -v
```

### 5. Run Paper Trading Bot
To run a single verification cycle:
```bash
.venv\Scripts\python -m bot.main --once
```

To start the continuous paper trading loop:
```bash
.venv\Scripts\python -m bot.main
```

### 6. Run Historical Backtester (Phase 2)
To run historical backtesting with offline Jev decision replay, forward-return analysis, and benchmark comparisons:
```bash
.venv\Scripts\python -m backtest.run --symbol BTCUSDT --timeframe 5m
```

Options:
- `--fee <rate>`: Execution fee per trade (default `0.001` / 0.1%)
- `--slippage <rate>`: Execution slippage per fill (default `0.0005` / 0.05%)
- `--threshold <value>`: Jev confidence threshold (default `0.60`)
- `--stop-loss <pct>`: Stop loss percent (default `0.015` / 1.5%)
- `--take-profit <pct>`: Take profit percent (default `0.030` / 3.0%)
- `--max-holding <periods>`: Max holding period (default `24` bars)

### 7. Run Statistical Edge Validation Framework (Phase 3)
To run the full statistical edge validation and robustness testing suite:
```bash
.venv\Scripts\python -m validation.run --symbol BTCUSDT --timeframe 5m
```

Options:
- `--symbol <pair>`: Asset pair (default `BTCUSDT`, supports `ETHUSDT`, `SOLUSDT`)
- `--timeframe <tf>`: Candle interval (default `5m`)
- `--confidence-threshold <val>`: Jev threshold (default `0.60`)
- `--fee <rate>`: Fee per trade (default `0.0010` / 0.10%)
- `--slippage <rate>`: Slippage per fill (default `0.0005` / 0.05%)
- `--seed <int>`: Deterministic seed (default `42`)
- `--bootstrap-samples <int>`: Number of bootstrap iterations (default `500`)
- `--null-simulations <int>`: Monte Carlo null iterations (default `50`)

Generates JSON, CSV, and comprehensive 13-section Markdown audit artifacts in `data/validation_results/`.

### 8. Run Signal Diagnosis & Strategy Reconstruction (Phase 4)
To run the full signal diagnosis, decay analysis, MFE/MAE excursions, exit ablation, timing delays, and candidate architecture evaluations:
```bash
.venv\Scripts\python -m diagnosis.run --symbol BTCUSDT --timeframe 5m
```

Options:
- `--symbol <pair>`: Asset pair (default `BTCUSDT`, supports `ETHUSDT`, `SOLUSDT`)
- `--timeframe <tf>`: Candle interval (default `5m`)
- `--fee <rate>`: Fee per trade (default `0.0010` / 0.10%)
- `--slippage <rate>`: Slippage per fill (default `0.0005` / 0.05%)
- `--seed <int>`: Deterministic seed (default `42`)
- `--bootstrap-samples <int>`: Number of bootstrap iterations (default `500`)

Generates JSON, CSV, and comprehensive 21-section Markdown audit artifacts in `data/phase4_results/`.

---

## Phase 4: Signal Diagnosis & Strategy Reconstruction Findings

### Overall Evidence Verdict: NOT SUPPORTED (NO USABLE TRADING SIGNAL)
Phase 4 decomposed decisions independently of the trading engine to diagnose whether underlying information exists and whether alternative architectures can capture it.

- **Raw Signal Information**:
  - Small raw predictive drift exists over uncosted horizons (4h peak at `+0.193%`), but at 5m/15m/30m, mean directional returns remain near-zero (`-0.002%` to `-0.012%`).
- **Signal Decay**:
  - Decay curve classification: `INCONCLUSIVE`. At short horizons (5m–1h), accuracy hovers around 50%.
- **MFE / MAE Excursions**:
  - Mean MFE is `1.419%`, Mean MAE is `1.337%` (Gain-to-Pain Ratio: `1.06`).
  - Premature stop-out rate is `2.8%`, while clean losses constitute `32.2%`. Stops do not kill good trades; adverse moves predominate.
- **Exit Ablation**:
  - Disabling SL/TP entirely yields `-2.09%` (worse than baseline `-1.85%`). Stop-loss only yields `-1.81%`. Short time exits (6 bars) severely degrade performance (`-5.23%`).
- **Confidence Information Content**:
  - Confidence has **negative** rank correlation with 15m return ($\rho = -0.0547, p = 0.077$) and accuracy ($\rho = -0.0724, p = 0.019$). Confidence does NOT provide useful ordinal ranking.
- **Out-of-Sample Calibration Reconstruction**:
  - Platt logistic scaling fitted on Development improves Brier score from `0.3196` to `0.2470` on Dev, but only `0.2589` on Sealed Holdout.
- **Candidate Architectures (Dev 60% / Val 20% / Sealed Holdout 20%)**:
  - **Arch A (Raw Signal)**: Dev `-2.69%`, Val `+0.77%`, Holdout `-0.02%` (`NOT_SUPPORTED`)
  - **Arch B (High Confidence >=0.70)**: Dev `-2.90%`, Val `+0.85%`, Holdout `+0.08%`, 13 trades (`INCONCLUSIVE` due to low $N$)
  - **Arch C (Regime Filter)**: Dev `-2.69%`, Val `+0.77%`, Holdout `-0.02%` (`NOT_SUPPORTED`)
  - **Arch D (Composite Filter)**: Dev `-2.90%`, Val `+0.85%`, Holdout `+0.08%`, 13 trades (`INCONCLUSIVE`)
  - **Arch E (Directional Margin >=0.40)**: Dev `-2.69%`, Val `+0.77%`, Holdout `-0.02%` (`NOT_SUPPORTED`)
- **Safety Invariant Maintained**: `PAPER_TRADING_ONLY = true` and `USE_LIVE_JEV = false` remain strictly enforced. Zero real execution.

---

## Phase 3: Statistical Edge Validation & Robustness Findings

### Empirical Verdict: REJECTED (NO STATISTICAL TRADING EDGE)
Phase 3 evaluated whether Jev decisions possess defensible trading edge after execution costs across expanded statistical frameworks.

- **Primary Metrics**: Return `-1.85%`, Win Rate `35.94%`, Profit Factor `0.62`, Expectancy `-$2.95/trade`.
- **Hypothesis Testing**: t-statistic `-1.645` ($p = 0.9500$). Null hypothesis of zero/negative return CANNOT be rejected.
- **Predictive vs Trading Edge**:
  - Small positive raw forward returns exist at 15m in certain slices (SHORT: `+0.024%`, 4h SHORT: `+0.569%`).
  - However, exchange fees (`0.10%`) and slippage (`0.05%`) exceed raw predictive signal, yielding negative net expectancy.
- **Confidence Calibration**: Brier Score `0.2974` (exceeds 0.25 random coin-flip), Expected Calibration Error `17.85%`.
- **Execution Cost Sensitivity**:
  - Scenario A (0.00% fee / 0.00% slip): `-0.01%`
  - Scenario B (0.05% fee / 0.02% slip): `-0.93%`
  - Scenario C (0.10% fee / 0.05% slip): `-1.85%`
  - Scenario D (0.15% fee / 0.10% slip): `-3.46%`
  - Scenario E (0.20% fee / 0.15% slip): `-4.83%`
- **Sealed Holdout Isolation**:
  - Development (60%): `-2.69%` return, PF `0.26`
  - Validation (20%): `+0.77%` return, PF `2.30`
  - Final Sealed Holdout (20%): `-0.02%` return, PF `0.97` (Generalization Decay: `99.27%`)
- **Safety Invariant Maintained**: `PAPER_TRADING_ONLY = true` strictly enforced. Zero real execution.

---

## Phase 4: Signal Diagnosis & Strategy Reconstruction Findings

### Empirical Verdict: NOT_SUPPORTED
Phase 4 decomposed Jev's decisions across multiple horizons, tested exit ablation, entry delays, regime conditioning, and candidate architectures.

- **Horizon Matrix**: 15m combined return `-0.012%`, 1h return `-0.019%`, 4h return `+0.193%`.
- **Exit Ablation**: Disproved the exit-problem hypothesis. Wide stops/no-stop configurations still lost money; premature stop-out was only 2.8%.
- **Confidence Calibration**: Correlation between Jev confidence and forward return was negative ($\rho = -0.0547$).
- **Candidate Architectures**: Trend-filtered, mean-reversion, and dynamic time-stop architectures all failed on sealed holdouts.

To run Phase 4 diagnostics:
```bash
.venv\Scripts\python -m diagnosis.run --symbol BTCUSDT --timeframe 5m
```

---

## Phase 5: Signal Reconstruction & Predictive Model Improvement

### Empirical Verdict: NOT_SUPPORTED (Edge < Friction Barrier)
Phase 5 moved upstream into the decision pipeline (`MARKET DATA -> FEATURES -> MARKET STATE -> JEV REASONING -> DIRECTION -> CONFIDENCE`):

- **Architecture Package**: `reconstruction/`
  - `audit.py`: Full audit of Jev API integration, schema, prompts, fallbacks, and sanitized trace.
  - `input_quality.py`: Feature distributions, missingness, variance, skew, collinearity, and 15m/1h return correlations.
  - `market_state.py`: Causal market structure (swing highs/lows, Break of Structure [BOS], range compression/expansion) and normalized indicators.
  - `regimes.py`: Causal regime classification (`TRENDING_UP`, `TRENDING_DOWN`, `RANGE_BOUND`, `HIGH_VOLATILITY`, `LOW_VOLATILITY`, `TRANSITION`).
  - `horizons.py`: Explicit prediction horizons (5m, 15m, 30m, 1h, 4h) disentangling noise from trend.
  - `magnitude.py`: Move magnitude estimation (basis points) and friction hurdle alignment.
  - `uncertainty.py`: Decoupling directional probability $P(up)$, magnitude, and epistemic uncertainty $U$.
  - `abstention.py`: Explicit `NO_EDGE` decision abstention vs `HOLD` (consolidation) vs active trading.
  - `asymmetry.py`: Directional asymmetry and class imbalance diagnosis.
  - `prompt_experiments.py`: Controlled prompt variants (Variants A through E).
  - `information_gain.py`: Feature group ablation and out-of-sample information gain.
  - `baselines.py`: Model-agnostic benchmarks (Always HOLD, Random, Momentum, Mean Reversion, EMA Cross, Logistic Regression).
  - `gate.py`: Economic signal gate requiring $\text{Edge} > 40\text{ bps}$ (fee + slippage + margin).
  - `walk_forward.py`: Chronological 4-fold walk-forward validation.
  - `registry.py`: Structured hypotheses and experiment registry.
  - `report.py`: JSON, CSV, and 18-section Markdown audit generator.

### Key Empirical Findings
1. **Input Enrichment**: Computing causal swing highs/lows, BOS, and normalized indicator distances removes collinearity and improves classification consistency, but 5m crypto noise prevents positive out-of-sample expectancy.
2. **Abstention Filtering**: The `NO_EDGE` abstention rule successfully eliminated over 80% of low-conviction/choppy bars, preventing unnecessary capital degradation from churn.
3. **Friction Barrier**: All active trading variants and model-agnostic benchmarks (Momentum, Mean Reversion, Logistic Regression) produced net negative returns once the realistic 0.30% round-trip fee and slippage were applied.
4. **Safety Status**: Live trading remains **STRICTLY PROHIBITED** (`PAPER_TRADING_ONLY = true`, `USE_LIVE_JEV = false`).

To run Phase 5 reconstruction pipeline:
```bash
.venv\Scripts\python -m reconstruction.run --symbol BTCUSDT --timeframe 5m
```

---

## Phase 6: Dataset Expansion, Cross-Regime Generalization & Signal Qualification

### Master Empirical Classification: NOT_SUPPORTED (No Statistically Significant OOS Edge)
Phase 6 evaluated Jev's reconstructed decision process across expanded historical samples, independent market regimes, macro market episodes, and independent assets (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`):

- **Architecture Package**: `generalization/`
  - `data_loader.py`: Dataset loader supporting public Binance pagination, caching, and SHA256 integrity verification.
  - `data_quality.py`: Automated data quality auditor checking timestamp monotonicity, zero gaps, zero duplicates, and valid OHLC bounds.
  - `temporal.py`: Strict chronological partitioning: Development (60%), Validation (20%), and Sealed Frozen Holdout (20%).
  - `regimes.py`: Causal regime classification across micro regimes and macro market episodes (Sustained Bull, Sustained Bear, Sideways Chop, Sharp Selloff).
  - `signal_eval.py`: Horizon-specific evaluations (5m, 15m, 30m, 1h, 4h), rank correlation ($\rho$), directional accuracy, and calibration error.
  - `statistics.py`: Stationary block bootstrapping, empirical statistical power, and Benjamini-Hochberg FDR multiple testing control.
  - `abstention.py`: Explicit `NO_EDGE` abstention auditing (abstention rate, active win rate, capital protection ratio).
  - `gate.py`: Economic signal gate requiring $\text{Edge} > 40\text{ bps}$ (30 bps friction + 10 bps margin).
  - `baselines.py`: Model-agnostic benchmarks across all assets (Always HOLD, Random, Momentum, Mean Reversion, EMA Cross, Logistic Regression, Donchian Breakout).
  - `walk_forward.py`: Chronological 4-fold rolling walk-forward validation per asset.
  - `cross_asset.py`: Cross-asset transferability experiments ($\text{BTC} \to \text{ETH/SOL}$, $\text{ETH} \to \text{BTC/SOL}$).
  - `registry.py`: Pre-registered hypotheses with configuration hashing and FDR adjustments.
  - `report.py`: Comprehensive 26-section Markdown scientific report, JSON, and CSV artifact generator.
  - `run.py`: Multi-asset pipeline orchestrator CLI.

### Key Empirical Findings
1. **Directional Accuracy**: Out-of-sample directional accuracy remains between 47% and 51% across BTC, ETH, and SOL on 5m candles (statistically indistinguishable from a random coin flip, $p > 0.05$ after Benjamini-Hochberg FDR correction).
2. **Abstention Discipline**: Explicit `NO_EDGE` abstention reliably flags and filters ~83% of low-conviction/choppy bars across all assets, preventing churning losses.
3. **Friction Hurdle**: When realistic execution friction (0.10% taker fee + 0.05% slippage per fill = 0.30% round-trip) is applied, all active decision paths and all benchmark strategies yield negative net returns.
4. **Cross-Asset Transferability**: Parameters fitted on BTC fail when transferred to ETH and SOL, and vice versa, confirming the lack of a universal or persistent alpha signal on 5m candles.
5. **Safety Invariants Maintained**: `PAPER_TRADING_ONLY = true` and `USE_LIVE_JEV = false` remain strictly enforced. Zero real execution, zero financial risk.

To run the Phase 6 generalization and cross-asset pipeline:
```bash
.venv\Scripts\python -m generalization.run --symbols BTCUSDT,ETHUSDT,SOLUSDT --timeframe 5m
```

---

## Phase 7: Horizon Reassessment & Temporal Resolution Study

### Master Empirical Classification: NOT_SUPPORTED (No Slower-Horizon Edge Exists)
Phase 7 investigated whether Jev contains predictive information at a slower temporal resolution ($5\text{m}, 15\text{m}, 30\text{m}, 1\text{h}, 4\text{h}$) that is obscured or economically destroyed by 5-minute execution:

- **Architecture Package**: `temporal/`
  - `data_aggregator.py`: Strictly causal multi-timeframe OHLCV resampling from 5m base into 15m, 30m, 1h, and 4h.
  - `targets.py`: Strictly causal forward return targets, absolute return, MFE, and MAE over explicit horizon bars.
  - `methodology.py`: Formal separation of Primary Methodology ($\text{horizon} = \text{execution frequency}$) and Secondary Methodology (5m execution, multi-horizon forward hold).
  - `signal_eval.py`: Directional accuracy, balanced accuracy, Brier score, ECE, Spearman rank correlations, and uncertainty relationship.
  - `cost_model.py`: Frozen cost parameters (10 bps fee + 5 bps slippage per fill = 30 bps round-trip friction + 10 bps margin = 40 bps economic hurdle).
  - `frequency_effect.py`: De-biasing engine distinguishing true signal improvements from turnover-reduction fee savings.
  - `monotonicity.py`: Formal monotonicity testing of gross edge and accuracy across horizon durations ($5\text{m} \to 4\text{h}$).
  - `power_audit.py`: Formal statistical power audit and hypothesis testing ($H_0: \mu \le 0$ vs $H_1: \mu = +40\text{ bps}$).
  - `cross_regime.py`: Performance characterization across all 6 causal market regimes per horizon.
  - `walk_forward.py`: Chronological 4-fold rolling walk-forward validation with printed exact boundaries.
  - `baselines.py`: Evaluation of 7 model-agnostic reference benchmarks across all horizons.
  - `registry.py`: Pre-registered hypotheses and Benjamini-Hochberg FDR adjustments.
  - `report.py`: Comprehensive 23-section Markdown scientific audit report, JSON, and CSV generator.
  - `run.py`: Multi-horizon pipeline CLI runner.

### Key Empirical Findings
1. **Directional Accuracy**: Out-of-sample directional accuracy remains between $45.8\%$ and $53.6\%$ across all horizons and assets (statistically indistinguishable from a random coin flip, $p > 0.30$ across all tests).
2. **Gross Return vs Edge**: While uncosted return dispersion scales with $\sqrt{t}$ as expected under diffusion, net expectancy remains negative across all tested horizons after accounting for 30 bps round-trip friction.
3. **Turnover De-biasing**: Performance improvement at 1h and 4h is driven primarily by reduced transaction frequency rather than genuine alpha generation (`FRICTION_REDUCTION_ONLY` / `MARGINAL_SIGNAL_IMPROVEMENT_INSUFFICIENT_FOR_FEES`).
4. **Statistical Power Audit**: Clarified that with $N_{eff} \approx 200 - 1500$, the system has $\ge 95\%$ statistical power to detect an economic alpha of $+40\text{ bps}$. The observed negative returns cannot be attributed to a type II sample-size error.
5. **Multiple Testing**: 0 of the pre-registered horizon hypotheses reject $H_0$ or survive Benjamini-Hochberg FDR ($q < 0.05$).
6. **Safety Invariants Maintained**: `PAPER_TRADING_ONLY = true` and `USE_LIVE_JEV = false` remain strictly enforced. Zero real execution.

To run the Phase 7 temporal resolution evaluation:
```bash
.venv\Scripts\python -m temporal.run --symbols BTCUSDT,ETHUSDT,SOLUSDT --horizons 5m,15m,30m,1h,4h
```

---

## Structured Logging Format

Every decision cycle emits a structured log entry:
```json
{
  "timestamp": "2026-09-21T11:15:00.000000+00:00",
  "symbol": "BTCUSDT",
  "price": 63450.0,
  "indicators": {
    "ema20": 63200.0,
    "ema50": 62800.0,
    "ema200": 61500.0,
    "rsi14": 58.4,
    "atr14": 420.0,
    "volume_ratio": 1.25,
    "price_change_pct": 0.45
  },
  "jev_action": "LONG",
  "jev_confidence": 0.75,
  "jev_reason_code": "TREND_CONFIRMATION",
  "risk_approved": true,
  "risk_rejection_reason": null,
  "final_action": "LONG",
  "executed_action": "BUY_OPEN",
  "position": {
    "symbol": "BTCUSDT",
    "side": "LONG",
    "entry_price": 63450.0,
    "quantity": 0.01576,
    "entry_fee": 0.75,
    "unrealized_pnl": 0.0
  },
  "realized_pnl": 0.0,
  "unrealized_pnl": 0.0,
  "portfolio_value": 10000.0,
  "max_drawdown_pct": 0.0
}
```

---

## Known Limitations
- **Paper Trading Only**: No actual exchange connectivity or live execution.
- **Microstructure Friction Dominance**: On 5-minute candle horizons, microstructure noise dominates cryptocurrency price movements. Bid-ask spreads and exchange taker fees systematically exceed directional edge.
- **Empirical Verdict Across All Phases**: Rigorous empirical testing across Phases 1 through 6 confirms that neither raw Jev decisions, threshold-filtered decisions, regime-conditioned models, nor reconstructed signals achieve statistically significant positive expectancy out-of-sample after realistic transaction friction.
- **Safety Invariant**: Live trading remains strictly prohibited.


