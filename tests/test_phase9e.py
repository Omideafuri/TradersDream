"""Unit tests for Phase 9E research synthesis, closure artifacts, and safety invariants."""

import json
from pathlib import Path
import pytest
from bot.config import BotConfig


def test_phase9e_artifacts_exist():
    """Verify that all mandatory Phase 9E artifacts exist and are non-empty."""
    repo_root = Path(__file__).resolve().parent.parent
    synthesis_path = repo_root / "PHASE9E_RESEARCH_SYNTHESIS_AND_CLOSURE.md"
    closure_path = repo_root / "PHASE9E_RESEARCH_CLOSURE.md"
    summary_path = repo_root / "PHASE9E_CLOSURE_SUMMARY.json"

    assert synthesis_path.is_file(), "PHASE9E_RESEARCH_SYNTHESIS_AND_CLOSURE.md missing"
    assert closure_path.is_file(), "PHASE9E_RESEARCH_CLOSURE.md missing"
    assert summary_path.is_file(), "PHASE9E_CLOSURE_SUMMARY.json missing"

    assert synthesis_path.stat().st_size > 5000, "Synthesis document unexpectedly brief"
    assert closure_path.stat().st_size > 1000, "Closure document unexpectedly brief"
    assert summary_path.stat().st_size > 200, "Summary JSON unexpectedly brief"


def test_phase9e_closure_summary_schema_and_values():
    """Verify schema, keys, and empirical metrics in PHASE9E_CLOSURE_SUMMARY.json."""
    repo_root = Path(__file__).resolve().parent.parent
    summary_path = repo_root / "PHASE9E_CLOSURE_SUMMARY.json"

    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_keys = [
        "research_scope",
        "datasets",
        "assets",
        "sampling_frequency",
        "hypotheses",
        "hypothesis_statuses",
        "best_gross_edge_bps",
        "best_net_edge_bps",
        "average_dynamic_hurdle_bps",
        "holdout_gross_edge_bps",
        "holdout_net_edge_bps",
        "incremental_auc",
        "incremental_auc_ci",
        "incremental_auc_p_value",
        "abstention_net_edge_bps",
        "reproducibility_status",
        "test_status",
        "safety_status",
        "final_classification",
        "next_permitted_research_direction",
    ]

    for key in required_keys:
        assert key in data, f"Missing required key '{key}' in closure summary"

    # Empirical values checks
    assert data["final_classification"] == "NOT_SUPPORTED"
    assert data["hypothesis_statuses"]["P9D-H05"] == "REJECTED"
    assert data["hypothesis_statuses"]["P9D-H02"] == "REJECTED"
    assert data["best_net_edge_bps"] < 0.0, "Net edge must reflect negative post-cost performance"
    assert data["holdout_net_edge_bps"] < 0.0, "Holdout net edge must reflect negative post-cost performance"
    assert data["incremental_auc_p_value"] > 0.05, "Incremental AUC must not be statistically significant"
    assert data["reproducibility_status"] == "FULLY_REPRODUCIBLE"
    assert data["safety_status"] == "VERIFIED"


def test_phase9e_safety_invariants():
    """Verify safety configuration invariants are strictly maintained."""
    import os
    cfg = BotConfig.from_env()
    assert cfg.paper_trading_only is True, "paper_trading_only must remain True"
    assert cfg.leverage == 1.0, "Leverage must remain 1.0"
    use_live_jev = os.getenv("USE_LIVE_JEV", "false").strip().lower() in ("true", "1")
    assert use_live_jev is False, "USE_LIVE_JEV must remain False"


def test_research_freeze_integrity():
    """Ensure RESEARCH_FREEZE.md has not been altered or tampered with."""
    repo_root = Path(__file__).resolve().parent.parent
    freeze_path = repo_root / "RESEARCH_FREEZE.md"
    assert freeze_path.is_file(), "RESEARCH_FREEZE.md missing"
    content = freeze_path.read_text(encoding="utf-8")
    assert "NOT_SUPPORTED" in content
    assert "MASTER_CLASSIFICATION:  NOT_SUPPORTED" in content
    assert "PERMANENT RESEARCH CONCLUSION" in content or "permanently closed and frozen" in content

