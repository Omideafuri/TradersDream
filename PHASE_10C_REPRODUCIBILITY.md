# PHASE 10C.X — REPRODUCIBILITY & VERIFICATION GUIDE

## 1. EXECUTION ENVIRONMENT

- Python Version: 3.10+
- Dependencies: `numpy`, `pandas`, `pytest`
- Execution Working Directory: Repository root

---

## 2. REPRODUCTION STEPS

To reproduce the exact audit and backtesting numbers reported in Phase 10C.X:

```bash
# 1. Verify frozen git commit
git rev-parse HEAD
# Expected: 9e720c54bf856976e001c3d3257a20cc9514f754

# 2. Run adversarial future-data leakage audit
python -m phase10cx.leakage_audit

# 3. Run complete evaluation and artifact generation
python -m phase10cx.run_experiment
```

---

## 3. CRYPTOGRAPHIC VERIFICATION TABLE

| Artifact File | Expected SHA-256 Checksum |
|:---|:---|
| `phase10b4/data/sample_binance-us_incremental_book_L2_2024-03-01_BTCUSDT.csv` | `f15a7d14691d85c62b496b1b57598c791fe18b1ebc0cc4bb05d8fd962fbc79df` |
| `phase10b4/data/sample_binance-us_trades_2024-03-01_BTCUSDT.csv` | `bd02cb034ef0baf027ce9040d8ab465af3c8283fe31b3fc1dbc87fad0c953fcc` |
| `data/phase9_data/BINANCE_US_BTCUSDT_5m.csv` | `f72be9be809e599481909d12126f47c6569faaa85717a3dc9109c4800250b515` |

All calculations are 100% deterministic with zero stochastic variance.
