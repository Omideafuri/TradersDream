"""Automated unit and integration tests for Dashboard FastAPI Backend and Controller."""

import os
import pytest
from starlette.testclient import TestClient

from dashboard.backend.api import app
from dashboard.backend.service import BotService
from dashboard.backend.auth import get_current_token


@pytest.fixture(autouse=True)
def reset_service():
    """Resets bot service singleton state before each test."""
    service = BotService.get_instance()
    service.status = "STOPPED"
    if service._loop_task and not service._loop_task.done():
        service._loop_task.cancel()
        service._loop_task = None
    yield service
    service.status = "STOPPED"
    if service._loop_task and not service._loop_task.done():
        service._loop_task.cancel()
        service._loop_task = None


@pytest.fixture
def client():
    return TestClient(app)


def test_status_endpoint(client: TestClient):
    """Verify /api/status returns valid bot state, paper invariant, and portfolio data."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("STOPPED", "RUNNING", "PAUSED")
    assert data["paper_trading_only"] is True
    assert data["symbol"] == "BTCUSDT"
    assert data["portfolio_value"] == 10000.0
    assert data["cash_balance"] == 10000.0
    assert "win_rate" in data
    assert "exposure_pct" in data


def test_market_endpoint(client: TestClient):
    """Verify /api/market returns symbol, interval, and candle list."""
    response = client.get("/api/market")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["interval"] == "5m"
    assert isinstance(data["candles"], list)


def test_signals_endpoint(client: TestClient):
    """Verify /api/signals returns structured signal info."""
    response = client.get("/api/signals")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["action"] in ("LONG", "SHORT", "HOLD")
    assert isinstance(data["confidence"], (int, float))


def test_positions_endpoint(client: TestClient):
    """Verify /api/positions returns current open positions list."""
    response = client.get("/api/positions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_trades_endpoint(client: TestClient):
    """Verify /api/trades returns historical closed paper trades."""
    response = client.get("/api/trades")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_strategy_endpoint(client: TestClient):
    """Verify /api/strategy returns read-only parameters and invariants."""
    response = client.get("/api/strategy")
    assert response.status_code == 200
    data = response.json()
    assert data["paper_trading_only"] is True
    assert data["leverage"] == 1.0
    assert data["symbol"] == "BTCUSDT"
    assert "maker_fee_bps" in data
    assert "taker_fee_bps" in data


def test_research_endpoint(client: TestClient):
    """Verify /api/research loads authoritative empirical research artifact."""
    response = client.get("/api/research")
    assert response.status_code == 200
    data = response.json()
    assert data["final_classification"] == "NOT_SUPPORTED"
    assert data["best_net_edge_bps"] == -35.79
    assert data["holdout_net_edge_bps"] == -36.10
    assert "P9D-H01" in data["hypothesis_statuses"]


def test_logs_endpoint(client: TestClient):
    """Verify /api/logs returns activity logs ring buffer."""
    response = client.get("/api/logs")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert logs[0]["level"] in ("INFO", "WARNING", "ERROR", "CRITICAL")


def test_health_endpoint(client: TestClient):
    """Verify /api/health returns component status and resource metrics."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["api_status"] == "HEALTHY"
    assert data["paper_trading_invariant"] is True
    assert "cpu_percent" in data
    assert "memory_mb" in data


def test_control_auth_required(client: TestClient):
    """Verify that bot mutation endpoints require valid X-API-Key."""
    # Attempt start without auth header
    res = client.post("/api/bot/start")
    assert res.status_code == 401
    assert "Invalid or missing X-API-Key" in res.json()["detail"]

    # Attempt with invalid key
    res = client.post("/api/bot/start", headers={"X-API-Key": "invalid_wrong_key"})
    assert res.status_code == 401


def test_control_lifecycle(client: TestClient):
    """Verify full start -> pause -> resume -> stop lifecycle with auth."""
    token = get_current_token()
    headers = {"X-API-Key": token}

    # 1. Start bot
    res = client.post("/api/bot/start", headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["new_status"] == "RUNNING"

    # 2. Pause bot
    res = client.post("/api/bot/pause", headers=headers)
    assert res.status_code == 200
    assert res.json()["new_status"] == "PAUSED"

    # 3. Resume bot
    res = client.post("/api/bot/resume", headers=headers)
    assert res.status_code == 200
    assert res.json()["new_status"] == "RUNNING"

    # 4. Stop bot without confirmation -> rejected (400)
    res = client.post("/api/bot/stop", json={"command": "stop", "confirmed": False}, headers=headers)
    assert res.status_code == 400

    # 5. Stop bot with confirmation -> succeeded (200)
    res = client.post("/api/bot/stop", json={"command": "stop", "confirmed": True}, headers=headers)
    assert res.status_code == 200
    assert res.json()["new_status"] == "STOPPED"


def test_emergency_stop(client: TestClient):
    """Verify emergency stop requires confirmation and sets status to STOPPED."""
    token = get_current_token()
    headers = {"X-API-Key": token}

    # Unconfirmed -> rejected
    res = client.post("/api/bot/emergency-stop", json={"command": "emergency-stop", "confirmed": False}, headers=headers)
    assert res.status_code == 400

    # Confirmed -> executed
    res = client.post("/api/bot/emergency-stop", json={"command": "emergency-stop", "confirmed": True}, headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["new_status"] == "STOPPED"


def test_websocket_streaming(client: TestClient):
    """Verify WebSocket connects and receives initial state message."""
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "INITIAL_STATE"
        assert "status" in data
        assert data["status"]["paper_trading_only"] is True
        
        # Ping-pong test
        websocket.send_text("ping")
        pong = websocket.receive_json()
        assert pong["type"] == "pong"


def test_frontend_static_serving(client: TestClient):
    """Verify that the compiled frontend SPA is served directly at GET /."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "JEVO // Quantitative Paper Trading Cockpit" in res.text

