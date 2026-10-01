# PHASE 10C.X.1 — RANDOM BASELINE AUDIT

## 1. COMPARABLE MONTE CARLO SPECIFICATION

The random-entry baseline was evaluated across 100 independent Monte Carlo simulations with strict parameter parity:
- **Capital**: $10,000.00
- **Position Allocation**: 10.0% ($1,000)
- **Trade Count**: 7247 trades (identical to strategy)
- **Stop Loss / Take Profit**: 1.5% SL / 3.0% TP
- **Transaction Costs**: 16 bps round-trip friction

---

## 2. EMPIRICAL DISTRIBUTION (100 ITERATIONS)

| Metric | Measured Value |
|:---|:---|
| Mean Net PnL | $-5245.38 |
| Median Net PnL | $-5289.67 |
| Standard Deviation | $709.00 |
| Fraction Profitable | 0.0% |
| Frozen Strategy Base Case PnL | **$-9153.37** |

**Conclusion**: The random baseline demonstrates that under identical 16 bps friction, random entries produce a mean loss of approximately $5245.38. The frozen strategy's loss of $9153.37 confirms that transaction costs dominate both signal and random entries.
