# PHASE 10C.X.1 — EXECUTION MODEL AUDIT

## 1. EXECUTION RULES & PRICE FORMATION

- **Entry Execution**: Fills execute against the prevailing bar Close price, adjusted for the scenario's slippage and latency penalty:
  $$\text{Fill}_{\text{entry, long}} = \text{Close} \cdot (1 + \text{friction})$$
  $$\text{Fill}_{\text{entry, short}} = \text{Close} \cdot (1 - \text{friction})$$
- **Exit Execution**: Exits trigger on bar High, Low, or Holding Period expiration:
  - Stop Loss: executed at Stop price $\pm$ friction.
  - Take Profit: executed at Take Profit price $\pm$ friction.
  - Max Holding Time: executed at Close price $\pm$ friction.

---

## 2. INTRABAR AMBIGUITY RESOLUTION

In historical 5-minute candle backtesting, when both `High >= Take Profit` and `Low <= Stop Loss` occur within the exact same 5-minute bar, the true chronological arrival sequence is unknown without tick-level data.

**Audited Resolution Policy**:
- The backtester implements the **conservative worst-case convention**: `low <= stop_loss` is evaluated first.
- If both conditions trigger in the same bar, the trade is recorded as a **STOP LOSS**.
- No optimistic intrabar assumptions were permitted.
