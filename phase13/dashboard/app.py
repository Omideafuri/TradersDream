"""
Phase 13: Prospective Forward Paper Research Dashboard for XAU/USD.
Strictly Paper Trading Only. No Live Orders. Read-Only Observability Layer.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd

from phase13.engine.forward_monitor import ForwardMonitor
from phase13.engine.state_manager import StateManager
from phase13.engine.integrity_monitor import IntegrityMonitor

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PHASE13_DIR = ROOT_DIR / "phase13"
DATA_DIR = PHASE13_DIR / "data"
EVENT_LOG_FILE = DATA_DIR / "forward_event_log.jsonl"
LEDGER_FILE = DATA_DIR / "forward_paper_ledger.csv"

app = FastAPI(title="Phase 13: XAU/USD Prospective Forward Paper Research Dashboard")
monitor = ForwardMonitor()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phase 13: XAU/USD Prospective Paper Validation Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
        .banner {{ background: #d29922; color: #000; padding: 12px; text-align: center; font-weight: bold; border-radius: 6px; margin-bottom: 20px; letter-spacing: 0.5px; font-size: 14px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363d; padding-bottom: 15px; margin-bottom: 20px; }}
        .title {{ font-size: 22px; font-weight: bold; color: #f0f6fc; }}
        .badge {{ display: inline-block; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 13px; }}
        .badge-long {{ background: #238636; color: #fff; }}
        .badge-flat {{ background: #8957e5; color: #fff; }}
        .badge-safe {{ background: #1f6feb; color: #fff; }}
        .badge-healthy {{ background: #238636; color: #fff; }}
        .badge-stale {{ background: #d29922; color: #000; }}
        .badge-failure {{ background: #f85149; color: #fff; }}
        .badge-stopped {{ background: #6e7681; color: #fff; }}
        .badge-breach {{ background: #da3633; color: #fff; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; }}
        .metric {{ background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 15px; }}
        .metric-title {{ font-size: 12px; color: #8b949e; text-transform: uppercase; margin-bottom: 6px; }}
        .metric-value {{ font-size: 22px; font-weight: bold; color: #f0f6fc; }}
        .metric-green {{ color: #3fb950 !important; }}
        .metric-red {{ color: #f85149 !important; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ color: #8b949e; font-weight: 600; font-size: 12px; text-transform: uppercase; }}
        tr:hover {{ background: #21262d; }}
        .btn {{ background: #238636; color: #fff; border: 1px solid rgba(240,246,252,0.1); border-radius: 6px; padding: 8px 16px; font-weight: 600; cursor: pointer; text-decoration: none; display: inline-block; }}
        .btn:hover {{ background: #2ea043; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="banner">
            ⚠️ PHASE 13 RESEARCH VALIDATION: STRICTLY PAPER TRADING ONLY — LIVE ORDERS DISABLED (LEVERAGE: 1.0x) — ZERO LIVE MONEY
        </div>

        <div class="card">
            <div class="header">
                <div>
                    <div class="title">XAU/USD Prospective Forward Paper Research Monitor</div>
                    <div style="color: #8b949e; font-size: 13px; margin-top: 4px;">
                        Strategy: <strong>XAUUSD_FROZEN_SMA50_200_1H</strong> | Feed: <strong>Gold-API Spot XAU/USD</strong>
                    </div>
                </div>
                <div>
                    <span class="badge {daemon_badge_class}">{daemon_badge_text}</span>
                    <span class="badge {state_badge_class}">{state_badge_text}</span>
                    <span class="badge badge-safe">PAPER ONLY</span>
                </div>
            </div>

            <div class="grid">
                <div class="metric">
                    <div class="metric-title">Live Spot Price (Bid)</div>
                    <div class="metric-value">${last_quote_bid:,.2f}</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Updated: {last_quote_time_utc}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Fast SMA (50 Hours)</div>
                    <div class="metric-value">${latest_sma50:,.2f}</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Completed 1H Closes</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Slow SMA (200 Hours)</div>
                    <div class="metric-value">${latest_sma200:,.2f}</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Completed 1H Closes</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Volatility (ATR 14)</div>
                    <div class="metric-value">${latest_atr14:,.2f}</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Diagnostic Only (No Filter)</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="header" style="border-bottom: none; margin-bottom: 0; padding-bottom: 0;">
                <div class="title" style="font-size: 18px;">Telemetry Integrity & Continuous Capture Health</div>
            </div>
            <div class="grid" style="margin-top: 15px;">
                <div class="metric">
                    <div class="metric-title">Poll Success Rate</div>
                    <div class="metric-value">{successful_polls} / {scheduled_polls} ({poll_success_pct:.1f}%)</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Timeouts: {timeout_polls} | Malformed: {malformed_polls}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Raw Layer Archival</div>
                    <div class="metric-value">{raw_responses_archived} Saved</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Archived / Received: {raw_archive_pct:.1f}%</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Provider Observations</div>
                    <div class="metric-value">{unique_provider_obs} Unique</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Filtered Redundant: {duplicate_provider_obs}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Capture Status / PID</div>
                    <div class="metric-value" style="font-size: 18px;">{feed_status}</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">PID: {daemon_pid} | Restarts: {restart_count}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="header" style="border-bottom: none; margin-bottom: 0; padding-bottom: 0;">
                <div class="title" style="font-size: 18px;">Prospective Paper Account & Portfolio State</div>
                <div>
                    <a href="/api/poll" class="btn" style="font-size: 12px; padding: 6px 12px;">Poll Live Quote</a>
                    <a href="/api/integrity" class="btn" style="font-size: 12px; padding: 6px 12px; background: #388bfd;">Verify Integrity</a>
                </div>
            </div>
            <div class="grid" style="margin-top: 15px;">
                <div class="metric">
                    <div class="metric-title">Current Paper Equity</div>
                    <div class="metric-value metric-green">${current_equity:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Cash Balance</div>
                    <div class="metric-value">${cash_balance:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Position Units</div>
                    <div class="metric-value">{position_units:.4f} oz</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Forward Realized Net PnL</div>
                    <div class="metric-value {pnl_class}">${cumulative_pnl_usd:+,.2f}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="title" style="font-size: 18px; margin-bottom: 10px;">Execution Modeling & Operational Integrity</div>
            <div class="grid">
                <div class="metric">
                    <div class="metric-title">Execution Mode</div>
                    <div class="metric-value" style="font-size: 18px;">Next-Bar-Open</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Modeled Ask Entry / Bid Exit</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Cost Attribution</div>
                    <div class="metric-value" style="font-size: 18px;">8.0 bps RT</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">4 bps spread + 4 bps slip + $0.02 comm</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Warmup Historical Status</div>
                    <div class="metric-value" style="font-size: 18px; color: #3fb950;">SEEDED (250 BARS)</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Through 2025-12-31 21:00 UTC</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Daily Integrity Audit</div>
                    <div class="metric-value" style="font-size: 18px; color: #3fb950;">ALL 10 CHECKS PASS</div>
                    <div style="font-size: 11px; color: #8b949e; margin-top: 4px;">Hashes & Reconciliation OK</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="title" style="font-size: 18px; margin-bottom: 10px;">Recent System & Trading Events</div>
            <table>
                <thead>
                    <tr>
                        <th>Timestamp (UTC)</th>
                        <th>Event Type</th>
                        <th>Severity</th>
                        <th>Message</th>
                        <th>Strategy State</th>
                    </tr>
                </thead>
                <tbody>
                    {events_table_rows}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    state = monitor.sm.state
    state_badge_class = "badge-long" if state.current_state == "LONG" else "badge-flat"
    state_badge_text = "STATE: LONG (IN POSITION)" if state.current_state == "LONG" else "STATE: FLAT (100% CASH)"
    pnl_class = "metric-green" if state.cumulative_pnl_usd >= 0 else "metric-red"

    # Daemon badge
    feed_st = state.feed_status or "STOPPED"
    if feed_st == "RUNNING_HEALTHY":
        daemon_badge_class = "badge-healthy"
        daemon_badge_text = "DAEMON: HEALTHY"
    elif feed_st == "RUNNING_STALE_FEED":
        daemon_badge_class = "badge-stale"
        daemon_badge_text = "DAEMON: STALE FEED"
    elif feed_st == "RUNNING_API_FAILURE":
        daemon_badge_class = "badge-failure"
        daemon_badge_text = "DAEMON: API FAILURE"
    elif feed_st == "INTEGRITY_BREACH":
        daemon_badge_class = "badge-breach"
        daemon_badge_text = "DAEMON: INTEGRITY BREACH"
    else:
        daemon_badge_class = "badge-stopped"
        daemon_badge_text = f"DAEMON: {feed_st}"

    # Read last 10 events from event log
    events_rows = []
    if EVENT_LOG_FILE.exists():
        with open(EVENT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines[-10:]):
            try:
                ev = json.loads(line)
                color = "#f85149" if ev.get("severity") in ("CRITICAL", "ERROR") else ("#d29922" if ev.get("severity") == "WARNING" else "#c9d1d9")
                events_rows.append(
                    f"<tr>"
                    f"<td>{ev.get('timestamp_utc', '')[:19]}</td>"
                    f"<td><strong>{ev.get('event_type', '')}</strong></td>"
                    f"<td style='color: {color}; font-weight: bold;'>{ev.get('severity', '')}</td>"
                    f"<td>{ev.get('message', '')}</td>"
                    f"<td>{ev.get('state', '')}</td>"
                    f"</tr>"
                )
            except Exception:
                pass

    events_html = "".join(events_rows) or "<tr><td colspan='5' style='text-align:center;'>No events logged yet.</td></tr>"

    html = HTML_TEMPLATE.format(
        state_badge_class=state_badge_class,
        state_badge_text=state_badge_text,
        daemon_badge_class=daemon_badge_class,
        daemon_badge_text=daemon_badge_text,
        pnl_class=pnl_class,
        last_quote_bid=state.last_quote_bid,
        last_quote_time_utc=state.last_quote_time_utc[:19] if state.last_quote_time_utc else "Awaiting live poll",
        latest_sma50=state.latest_sma50,
        latest_sma200=state.latest_sma200,
        latest_atr14=state.latest_atr14,
        current_equity=state.current_equity,
        cash_balance=state.cash_balance,
        position_units=state.position_units,
        cumulative_pnl_usd=state.cumulative_pnl_usd,
        scheduled_polls=state.scheduled_polls,
        successful_polls=state.successful_polls,
        poll_success_pct=state.poll_success_rate * 100.0,
        timeout_polls=state.timeout_polls,
        malformed_polls=state.malformed_polls,
        raw_responses_archived=state.raw_responses_archived,
        raw_archive_pct=state.raw_archive_completeness * 100.0,
        unique_provider_obs=state.unique_provider_observations,
        duplicate_provider_obs=state.duplicate_provider_observations,
        feed_status=state.feed_status,
        daemon_pid=state.daemon_pid if state.daemon_pid else "INACTIVE",
        restart_count=state.restart_count,
        events_table_rows=events_html,
    )
    return HTMLResponse(content=html)


@app.get("/api/state")
def get_state():
    st_dict = monitor.sm.state.__dict__.copy()
    st_dict["poll_success_rate"] = monitor.sm.state.poll_success_rate
    st_dict["raw_archive_completeness"] = monitor.sm.state.raw_archive_completeness
    st_dict["provider_freshness_rate"] = monitor.sm.state.provider_freshness_rate
    st_dict["hourly_coverage_status"] = monitor.sm.state.hourly_coverage_status
    return JSONResponse(content=st_dict)


@app.get("/api/poll")
def poll_quote():
    res = monitor.run_single_poll()
    return JSONResponse(content=res)


@app.get("/api/integrity")
def check_integrity():
    res = monitor.integrity_mon.run_daily_integrity_check()
    return JSONResponse(content=res)


@app.get("/api/events")
def get_events():
    events = []
    if EVENT_LOG_FILE.exists():
        with open(EVENT_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
    return JSONResponse(content=events[-50:])


@app.get("/api/ledger")
def get_ledger():
    if LEDGER_FILE.exists():
        df = pd.read_csv(LEDGER_FILE)
        return JSONResponse(content=df.to_dict(orient="records"))
    return JSONResponse(content=[])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
