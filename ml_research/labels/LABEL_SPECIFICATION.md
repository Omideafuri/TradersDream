# XAU/USD ML RESEARCH TRACK — LABEL SPECIFICATION

**Document Version:** 1.0.0  
**Research Track:** `ml_research/` (Strictly Isolated from `phase13/`)  
**Target Instrument:** `XAU/USD` (Spot Gold / US Dollar)  

---

## 1. Objective & Label Generation Philosophy

Labels must **NEVER** be imported from discretionary trading ideas, hindsight-selected profitable patterns, or external signal services. All labels are generated mechanically from future price trajectories following the causal prediction point $t_{\text{close}}$.

Execution occurs causally at $Open(t+1)$, eliminating same-bar execution bias.

---

## 2. Horizons Evaluated

Three prediction horizons are evaluated:
1. **Target A (Short Horizon):** $H = 4\text{ hours}$ (Entry at $t+1$ Open, Exit at $t+5$ Open).
2. **Target B (Medium Horizon):** $H = 12\text{ hours}$ (Entry at $t+1$ Open, Exit at $t+13$ Open).
3. **Target C (Long Horizon):** $H = 24\text{ hours}$ (Entry at $t+1$ Open, Exit at $t+25$ Open).

---

## 3. Mathematical Return Formulations

### Gross Forward Return
For bar $t$ and horizon $H$:
$$R_{\text{gross}, H}(t) = \frac{Open(t + 1 + H) - Open(t + 1)}{Open(t + 1)}$$

### Modeled Cost Friction Model
The cost model adheres strictly to the frozen Phase 12 / Phase 13 execution model:
* **Bid/Ask Spread:** $4.0\text{ bps round-trip}$ ($2.0\text{ bps entry} + 2.0\text{ bps exit} = 0.0004$)
* **Adverse Slippage:** $4.0\text{ bps round-trip}$ ($2.0\text{ bps entry} + 2.0\text{ bps exit} = 0.0004$)
* **Total Spread & Slippage Friction:** $8.0\text{ bps round-trip}$ ($0.0008$)
* **Broker Commission:** $\$0.02 / \text{oz}$ flat fee per fill. For a round-trip of 2 fills:
  $$\text{CommCost}(t) = \frac{2 \times \$0.02}{Open(t+1)}$$
* **Overnight Financing (Swap):** $3.5\%$ annualized interest cut daily at 22:00 UTC (with Wednesday triple rollover):
  $$\text{SwapCost}(t, H) = \frac{0.035}{365} \times N_{\text{swap\_days}}(t+1, t+1+H)$$

### Total Cost Friction:
$$\text{Friction}_H(t) = 0.0008 + \frac{0.04}{Open(t+1)} + \text{SwapCost}(t, H)$$

### Net Forward Return:
$$R_{\text{net}, H}(t) = R_{\text{gross}, H}(t) - \text{Friction}_H(t)$$

---

## 4. Binary Classification Targets

For each horizon $H$:
$$Y_H(t) = \begin{cases} 1 & \text{if } R_{\text{net}, H}(t) > 0 \\ 0 & \text{otherwise} \end{cases}$$

A positive label ($Y = 1$) indicates that a long position entered at $t+1$ Open and closed at $t+1+H$ Open achieves positive economic return **after full round-trip friction, broker commission, and overnight swap**.
