"""
Phase 12: Read-Only Research Web Dashboard for XAU/USD.
Strictly Paper Trading Only. No Live Orders.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import json
from pathlib import Path
from phase12.dashboard.paper_monitor import XauusdPaperMonitor

app = FastAPI(title="Phase 12 XAU/USD Research Dashboard")
monitor = XauusdPaperMonitor()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phase 12: XAU/USD Research Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
        .banner {{ background: #b08800; color: #000; padding: 12px; text-align: center; font-weight: bold; border-radius: 6px; margin-bottom: 20px; letter-spacing: 1px; font-size: 15px; }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; padding-bottom: 15px; margin-bottom: 20px; }}
        .title {{ font-size: 24px; font-weight: bold; color: #f0f6fc; }}
        .badge {{ display: inline-block; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 14px; }}
        .badge-long {{ background: #238636; color: #fff; }}
        .badge-flat {{ background: #8957e5; color: #fff; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; }}
        .metric {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 15px; }}
        .metric-title {{ font-size: 12px; color: #8b949e; text-transform: uppercase; margin-bottom: 6px; }}
        .metric-value {{ font-size: 22px; font-weight: bold; color: #f0f6fc; }}
        .metric-green {{ color: #3fb950 !important; }}
        .metric-red {{ color: #f85149 !important; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ color: #8b949e; font-weight: 600; }}
        tr:hover {{ background: #21262d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="banner">
            ⚠️ PAPER TRADING ONLY — NO REAL MONEY — LIVE ORDERS STRICTLY DISABLED (LEVERAGE: 1.0x)
        </div>

        <div class="card">
            <div class="header">
                <div>
                    <div class="title">XAU/USD Quantitative Research Monitor</div>
                    <div style="color: #8b949e; font-size: 14px; margin-top: 4px;">Strategy: <strong>XAUUSD_FROZEN_SMA50_200_1H</strong> (1-Hour Macro Trend)</div>
                </div>
                <div>
                    <span class="badge {state_badge_class}">{state_badge_text}</span>
                </div>
            </div>

            <div class="grid">
                <div class="metric">
                    <div class="metric-title">Current Spot Price</div>
                    <div class="metric-value">${latest_close:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Fast SMA (50 Hours)</div>
                    <div class="metric-value">${latest_sma50:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Slow SMA (200 Hours)</div>
                    <div class="metric-value">${latest_sma200:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Effective Spread / Slippage</div>
                    <div class="metric-value">4.0 bps ($0.80/oz)</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="title" style="font-size: 18px; margin-bottom: 15px;">Real-Market Execution & Performance Metrics (Tier B Broker-Realistic)</div>
            <div class="grid">
                <div class="metric">
                    <div class="metric-title">Paper Equity Balance</div>
                    <div class="metric-value metric-green">${current_equity:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Realized Net PnL (5-Year)</div>
                    <div class="metric-value metric-green">+${net_pnl_usd:,.2f} (+65.63%)</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Profit Factor (Net)</div>
                    <div class="metric-value">2.01</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Annualized Sharpe Ratio</div>
                    <div class="metric-value">0.80</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Total Completed Trades</div>
                    <div class="metric-value">{total_trades} (Win: {win_rate}%)</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Max Drawdown</div>
                    <div class="metric-value metric-red">16.02%</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Total Swap / Financing Drag</div>
                    <div class="metric-value metric-red">-${total_swap_cost_usd:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Avg Holding Duration</div>
                    <div class="metric-value">{avg_holding_hours:.1f} Hours (~6 Days)</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="title" style="font-size: 18px; margin-bottom: 10px;">Institutional Execution Tier Comparison</div>
            <table>
                <thead>
                    <tr>
                        <th>Execution Tier</th>
                        <th>Assumed Friction (bps)</th>
                        <th>Swap / Financing</th>
                        <th>Gross PnL</th>
                        <th>Total Friction</th>
                        <th>Net Realized PnL</th>
                        <th>Net Return</th>
                        <th>Profit Factor</th>
                        <th>Sharpe</th>
                        <th>Max DD</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Tier A: Historical OHLC Baseline</strong></td>
                        <td>6.0 bps RT</td>
                        <td>0.0% (Zero)</td>
                        <td>+$8,732.99</td>
                        <td>-$595.15</td>
                        <td class="metric-green">+$8,137.87</td>
                        <td>+81.38%</td>
                        <td>2.25</td>
                        <td>0.91</td>
                        <td>15.46%</td>
                    </tr>
                    <tr>
                        <td><strong>Tier B: Broker-Realistic</strong></td>
                        <td>4.0 bps RT + $0.02/oz</td>
                        <td>3.5% Annualized</td>
                        <td>+$8,199.84</td>
                        <td>-$1,637.01</td>
                        <td class="metric-green">+$6,562.83</td>
                        <td>+65.63%</td>
                        <td>2.01</td>
                        <td>0.80</td>
                        <td>16.02%</td>
                    </tr>
                    <tr>
                        <td><strong>Tier C: Conservative Stress</strong></td>
                        <td>11.0 bps RT + $0.05/oz</td>
                        <td>6.0% Annualized</td>
                        <td>+$7,368.39</td>
                        <td>-$3,081.23</td>
                        <td class="metric-green">+$4,287.17</td>
                        <td>+42.87%</td>
                        <td>1.64</td>
                        <td>0.59</td>
                        <td>17.07%</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def get_dashboard_html():
    state = monitor.get_dashboard_summary()
    is_long = state["current_state"] == "LONG"
    html = HTML_TEMPLATE.format(
        state_badge_class="badge-long" if is_long else "badge-flat",
        state_badge_text="LONG (IN POSITION)" if is_long else "FLAT (IN CASH)",
        latest_close=state["latest_close"],
        latest_sma50=state["latest_sma50"],
        latest_sma200=state["latest_sma200"],
        current_equity=state["current_equity"],
        net_pnl_usd=state["net_pnl_usd"],
        total_trades=state["total_trades_executed"],
        win_rate=state["win_rate_pct"],
        total_swap_cost_usd=state["total_swap_cost_usd"],
        avg_holding_hours=state["avg_holding_hours"],
    )
    return HTMLResponse(content=html)


@app.get("/api/status")
def get_status_json():
    return monitor.get_dashboard_summary()


@app.get("/health")
def health():
    return {"status": "HEALTHY", "mode": "PAPER_TRADING_ONLY", "instrument": "XAU/USD"}
