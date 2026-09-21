"""Unit tests for Phase 10A Passive Execution research specification, hypothesis registry, and safety invariants."""

import json
import os
from pathlib import Path
import pytest

from bot.config import BotConfig
from phase10a.hypothesis_registry import Phase10AHypothesisRegistry, Phase10AStatus


def test_phase10a_artifacts_exist():
    """Verify that all mandatory Phase 10A research specification artifacts exist and are populated."""
    repo_root = Path(__file__).resolve().parent.parent
    spec_path = repo_root / "PHASE10A_PASSIVE_EXECUTION_RESEARCH_SPEC.md"
    data_req_path = repo_root / "PHASE10A_DATA_REQUIREMENTS.md"
    registry_code_path = repo_root / "phase10a" / "hypothesis_registry.py"

    assert spec_path.is_file(), "PHASE10A_PASSIVE_EXECUTION_RESEARCH_SPEC.md missing"
    assert data_req_path.is_file(), "PHASE10A_DATA_REQUIREMENTS.md missing"
    assert registry_code_path.is_file(), "phase10a/hypothesis_registry.py missing"

    assert spec_path.stat().st_size > 5000, "Research specification file unexpectedly short"
    assert data_req_path.stat().st_size > 2000, "Data requirements file unexpectedly short"


def test_phase10a_hypotheses_exist_and_have_required_metadata(tmp_path):
    """Verify all 7 pre-registered hypotheses exist and contain complete, non-empty metadata."""
    registry = Phase10AHypothesisRegistry(storage_path=tmp_path / "test_hyp.json")
    hypotheses = registry.list_all()

    assert len(hypotheses) == 7, f"Expected 7 pre-registered hypotheses, found {len(hypotheses)}"

    expected_ids = [
        "P10A-H01",
        "P10A-H02",
        "P10A-H03",
        "P10A-H04",
        "P10A-H05",
        "P10A-H06",
        "P10A-H07",
    ]

    for hyp_id in expected_ids:
        hyp = registry.get(hyp_id)
        assert hyp.hypothesis_id == hyp_id
        assert len(hyp.name.strip()) > 0
        assert len(hyp.rationale.strip()) > 20, f"Rationale too brief for {hyp_id}"
        assert len(hyp.measurable_prediction.strip()) > 10, f"Measurable prediction too brief for {hyp_id}"
        assert len(hyp.metric.strip()) > 5, f"Metric missing for {hyp_id}"
        assert len(hyp.statistical_test.strip()) > 5, f"Statistical test missing for {hyp_id}"
        assert len(hyp.economic_gate.strip()) > 5, f"Economic gate missing for {hyp_id}"
        assert len(hyp.rejection_criterion.strip()) > 10, f"Rejection criterion missing for {hyp_id}"
        assert hyp.status == Phase10AStatus.REGISTERED


def test_phase10a_data_sufficiency_audit_decision():
    """Verify that data requirements audit correctly declares DATA INSUFFICIENT for realistic queue modeling."""
    repo_root = Path(__file__).resolve().parent.parent
    data_req_path = repo_root / "PHASE10A_DATA_REQUIREMENTS.md"
    content = data_req_path.read_text(encoding="utf-8")

    assert "DATA INSUFFICIENT FOR REALISTIC QUEUE MODELING" in content
    assert "BTCUSDT" in content
    assert "ETHUSDT" in content
    assert "SOLUSDT" in content
    assert "Level-2" in content or "L2" in content


def test_safety_invariants_and_no_live_trading():
    """Verify strict adherence to paper-trading-only and zero-leverage safety invariants."""
    cfg = BotConfig.from_env()
    assert cfg.paper_trading_only is True, "paper_trading_only must remain True"
    assert cfg.leverage == 1.0, "Leverage must remain 1.0"
    use_live_jev = os.getenv("USE_LIVE_JEV", "false").strip().lower() in ("true", "1")
    assert use_live_jev is False, "USE_LIVE_JEV must remain False"

    # Verify no live execution orders in phase10a
    for p in Path("phase10a").glob("**/*.py"):
        code = p.read_text(encoding="utf-8")
        assert "private_key" not in code.lower(), f"Forbidden private_key found in {p}"
        assert "place_order" not in code.lower(), f"Forbidden place_order found in {p}"
        assert "execute_trade" not in code.lower(), f"Forbidden execute_trade found in {p}"


def test_phase9_integrity_preserved():
    """Verify that Phase 9 synthesis, closure documents, and freeze manifests are preserved."""
    repo_root = Path(__file__).resolve().parent.parent

    # Check RESEARCH_FREEZE.md
    freeze = repo_root / "RESEARCH_FREEZE.md"
    assert freeze.is_file()
    freeze_content = freeze.read_text(encoding="utf-8")
    assert "MASTER_CLASSIFICATION:  NOT_SUPPORTED" in freeze_content

    # Check Phase 9E closure artifacts
    closure = repo_root / "PHASE9E_RESEARCH_CLOSURE.md"
    synthesis = repo_root / "PHASE9E_RESEARCH_SYNTHESIS_AND_CLOSURE.md"
    summary = repo_root / "PHASE9E_CLOSURE_SUMMARY.json"

    assert closure.is_file()
    assert synthesis.is_file()
    assert summary.is_file()

    closure_data = json.loads(summary.read_text(encoding="utf-8"))
    assert closure_data["final_classification"] == "NOT_SUPPORTED"
    assert closure_data["hypothesis_statuses"]["P9D-H05"] == "REJECTED"


def test_holdout_remains_sealed():
    """Verify that the holdout manifest remains sealed and untampered."""
    repo_root = Path(__file__).resolve().parent.parent
    holdout_manifest = repo_root / "PHASE9B_HOLDOUT_MANIFEST.md"
    assert holdout_manifest.is_file()
    content = holdout_manifest.read_text(encoding="utf-8")
    assert "SEALED & IMMUTABLE" in content
