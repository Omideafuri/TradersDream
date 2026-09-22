"""Unit tests for Phase 10B.2 Academic Research Trial and Data Access Verification."""

import json
from pathlib import Path
import pytest

from bot.config import BotConfig


def test_phase10b2_artifacts_exist():
    """Verify all required Phase 10B.2 documentation, application files, and manifests exist."""
    repo_root = Path(__file__).resolve().parent.parent

    root_report = repo_root / "PHASE10B2_ACADEMIC_ACCESS_AND_DATA_ACQUISITION_REPORT.md"
    metadata_manifest = repo_root / "phase10b2" / "manifests" / "trial_access_metadata.json"
    eligibility_report = repo_root / "phase10b2" / "reports" / "trial_eligibility_and_coverage_assessment.md"
    app_desc = repo_root / "phase10b2" / "application" / "research_project_description.md"
    app_dataset = repo_root / "phase10b2" / "application" / "requested_dataset.md"
    app_usage = repo_root / "phase10b2" / "application" / "data_usage_statement.md"

    artifacts = [
        root_report,
        metadata_manifest,
        eligibility_report,
        app_desc,
        app_dataset,
        app_usage,
    ]

    for artifact in artifacts:
        assert artifact.is_file(), f"Missing required Phase 10B.2 artifact: {artifact}"
        assert artifact.stat().st_size > 100, f"Artifact unexpectedly empty: {artifact.name}"


def test_trial_access_metadata_schema_and_invariants():
    """Verify trial access metadata structure, financial commitments, and readiness state."""
    repo_root = Path(__file__).resolve().parent.parent
    meta_path = repo_root / "phase10b2" / "manifests" / "trial_access_metadata.json"

    data = json.loads(meta_path.read_text(encoding="utf-8"))

    assert data["provider"] == "Tardis.dev"
    assert data["exchange"] == "binance-us"
    assert "BTCUSDT" in data["symbols"]
    assert "ETHUSDT" in data["symbols"]
    assert "SOLUSDT" in data["symbols"]
    assert "trades" in data["datasets"]
    assert "incremental_book_L2" in data["datasets"]

    # Invariant: Zero financial commitment
    assert data["financial_commitments_incurred_usd"] == 0.0
    assert data["payment_credentials_entered"] is False
    assert data["submission_status"] == "NOT_SUBMITTED"
    assert data["application_status"] == "PREPARED_PENDING_USER_AUTHORIZATION"
    assert data["phase10c_readiness"] == "BLOCKED"

    # Safety invariants
    safety = data["safety_invariants"]
    assert safety["paper_trading_only"] is True
    assert safety["use_live_jev"] is False
    assert safety["leverage"] == 1.0
    assert safety["live_orders"] == 0
    assert safety["wallet_connections"] == 0
    assert safety["private_keys"] == 0


def test_application_materials_content():
    """Verify application package components and non-commercial academic commitments."""
    repo_root = Path(__file__).resolve().parent.parent
    app_dir = repo_root / "phase10b2" / "application"

    desc = (app_dir / "research_project_description.md").read_text(encoding="utf-8")
    assert "PAPER_TRADING_ONLY = True" in desc
    assert "USE_LIVE_JEV = False" in desc
    assert "LIVE_ORDERS = 0" in desc
    assert "non-commercial" in desc.lower()
    assert "passive execution" in desc.lower()

    dataset = (app_dir / "requested_dataset.md").read_text(encoding="utf-8")
    assert "BTCUSDT" in dataset
    assert "ETHUSDT" in dataset
    assert "SOLUSDT" in dataset
    assert "incremental_book_L2" in dataset
    assert "trades" in dataset
    assert "30 consecutive" in dataset or "30-day" in dataset

    usage = (app_dir / "data_usage_statement.md").read_text(encoding="utf-8")
    assert "non-redistribution" in usage.lower()
    assert "APPLICATION READY FOR USER REVIEW" in usage


def test_root_report_points_and_queue_classification():
    """Verify master report covers required evaluation criteria and queue classification."""
    repo_root = Path(__file__).resolve().parent.parent
    report = (repo_root / "PHASE10B2_ACADEMIC_ACCESS_AND_DATA_ACQUISITION_REPORT.md").read_text(encoding="utf-8")

    assert "Tardis.dev" in report
    assert "300" in report  # Commercial minimum pricing mention
    assert "QUEUE-AHEAD" in report
    assert "adverse selection" in report.lower()
    assert "BLOCKED" in report
    assert "USER AUTHORIZATION REQUIRED" in report


def test_safety_invariants_and_freeze():
    """Verify platform config constraints and research freeze immutability."""
    import os
    repo_root = Path(__file__).resolve().parent.parent

    config = BotConfig.from_env()
    assert config.paper_trading_only is True
    assert config.leverage == 1.0
    use_live_jev = os.getenv("USE_LIVE_JEV", "false").strip().lower() in ("true", "1")
    assert use_live_jev is False

    # Ensure RESEARCH_FREEZE.md exists and is untouched
    freeze_path = repo_root / "RESEARCH_FREEZE.md"
    assert freeze_path.is_file()
    freeze_text = freeze_path.read_text(encoding="utf-8")
    assert "RESEARCH FREEZE MANIFEST" in freeze_text
    assert "MASTER_CLASSIFICATION:  NOT_SUPPORTED" in freeze_text
