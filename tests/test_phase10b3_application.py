"""Unit tests for Phase 10B.3 Academic Data Access Application and Approval Gate."""

import json
import os
from pathlib import Path
import pytest

from bot.config import BotConfig


def test_phase10b3_package_files_exist():
    """Verify all required Phase 10B.3 application documents, reports, and manifests exist."""
    repo_root = Path(__file__).resolve().parent.parent

    p10b3 = repo_root / "phase10b3"
    app_dir = p10b3 / "application"
    reports_dir = p10b3 / "reports"
    manifests_dir = p10b3 / "manifests"

    expected_files = [
        app_dir / "final_research_project_description.md",
        app_dir / "final_requested_dataset.md",
        app_dir / "final_data_usage_statement.md",
        app_dir / "submission_checklist.md",
        reports_dir / "provider_verification.md",
        reports_dir / "application_audit.md",
        reports_dir / "approval_gate_report.md",
        manifests_dir / "phase10b3_manifest.json",
    ]

    for file_path in expected_files:
        assert file_path.is_file(), f"Missing required Phase 10B.3 file: {file_path}"
        assert file_path.stat().st_size > 100, f"File unexpectedly empty: {file_path.name}"


def test_required_instruments_and_streams_present():
    """Verify target instruments and minimal event streams are specified without extraneous feeds."""
    repo_root = Path(__file__).resolve().parent.parent
    dataset_file = repo_root / "phase10b3" / "application" / "final_requested_dataset.md"
    content = dataset_file.read_text(encoding="utf-8")

    assert "BTCUSDT" in content
    assert "ETHUSDT" in content
    assert "SOLUSDT" in content
    assert "incremental_book_L2" in content
    assert "trades" in content
    assert "binance-us" in content.lower()

    # Minimum data principle check: no extraneous derivative or ticker feeds requested for spot
    assert "options_chain" not in content.lower() or "omitted" in content.lower()


def test_continuous_30_day_requirement_explicit():
    """Verify that the 30-day continuous requirement is mandatory and not weakened."""
    repo_root = Path(__file__).resolve().parent.parent
    dataset_file = repo_root / "phase10b3" / "application" / "final_requested_dataset.md"
    content = dataset_file.read_text(encoding="utf-8")

    assert "30 consecutive calendar days" in content
    assert "7–14 day evaluation window is insufficient" in content or "insufficient" in content.lower()


def test_no_unsupported_claims_or_fake_affiliations():
    """Verify that no fabricated affiliations exist and required fields use [USER INPUT REQUIRED]."""
    repo_root = Path(__file__).resolve().parent.parent
    app_dir = repo_root / "phase10b3" / "application"

    desc = (app_dir / "final_research_project_description.md").read_text(encoding="utf-8")
    usage = (app_dir / "final_data_usage_statement.md").read_text(encoding="utf-8")

    # Check for placeholder presence
    assert "[USER INPUT REQUIRED" in desc
    assert "[USER INPUT REQUIRED" in usage

    # Verify no claims of guaranteed alpha or profitability
    clean_desc = desc.replace("*", "").lower()
    assert "does not assume, guarantee, or claim expected profitability or alpha" in clean_desc

    # Verify queue model is strictly queue-ahead estimation, NOT exact FIFO
    assert "queue-ahead estimation" in desc.lower()
    assert "not exact order-level fifo" in desc.lower() or "not exact fifo" in desc.lower()


def test_no_payment_credentials_and_no_external_submission():
    """Verify zero financial commitments, zero payment credentials, and no external submission."""
    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = repo_root / "phase10b3" / "manifests" / "phase10b3_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["financial_commitments_incurred_usd"] == 0.0
    assert manifest["payment_credentials_entered"] is False
    assert manifest["external_submission"] == "NOT_PERFORMED"
    assert manifest["application_status"] == "READY_FOR_USER_REVIEW"


def test_provenance_hash_audit_documented():
    """Verify that the empty-string SHA-256 hash in Phase 10B.1 manifest was audited and recorded."""
    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = repo_root / "phase10b3" / "manifests" / "phase10b3_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    hash_audit = manifest["provenance_hash_audit"]
    assert hash_audit["sample_manifest_hash_investigated"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert "empty byte string" in hash_audit["hash_type"]
    assert hash_audit["physical_file_present"] is False


def test_safety_invariants_freeze_and_phase10c_blocked():
    """Verify safety invariants, untouched research freeze, and blocked Phase 10C status."""
    repo_root = Path(__file__).resolve().parent.parent

    config = BotConfig.from_env()
    assert config.paper_trading_only is True
    assert config.leverage == 1.0
    use_live_jev = os.getenv("USE_LIVE_JEV", "false").strip().lower() in ("true", "1")
    assert use_live_jev is False

    # Freeze integrity
    freeze_path = repo_root / "RESEARCH_FREEZE.md"
    assert freeze_path.is_file()
    freeze_content = freeze_path.read_text(encoding="utf-8")
    assert "RESEARCH FREEZE MANIFEST" in freeze_content
    assert "MASTER_CLASSIFICATION:  NOT_SUPPORTED" in freeze_content

    # Phase 10C blocked
    manifest_path = repo_root / "phase10b3" / "manifests" / "phase10b3_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["phase10c_readiness"] == "BLOCKED"
    assert manifest["phase10b_validation_state"] == "BLOCKED_UNTIL_ACTUAL_DATA_PASSES"
