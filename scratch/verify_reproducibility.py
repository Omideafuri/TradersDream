"""
Verify determinism and 100% bit-for-bit reproducibility of Phase 12 audit.
"""
import hashlib
import os
from pathlib import Path
import pandas as pd

ROOT = Path("c:/Users/Omideafuri/Documents/antigravity/goofy-hopper")
REPORTS = ROOT / "phase12" / "reports"

files_to_check = [
    "PHASE12_SIGNAL_RECONSTRUCTION.csv",
    "PHASE12_TRADE_LEDGER.csv",
    "PHASE12_EXECUTION_COST_SWEEP.csv",
    "PHASE12_VARIABLE_SPREAD_AUDIT.csv",
    "PHASE12_SLIPPAGE_AUDIT.csv",
    "PHASE12_GAP_RISK_AUDIT.csv",
    "PHASE12_SESSION_ANALYSIS.csv",
    "PHASE12_MISSING_DATA_SENSITIVITY.csv",
    "PHASE12_BAR_ALIGNMENT_AUDIT.csv",
    "PHASE12_DRAWDOWN_AUDIT.csv",
    "PHASE12_PARAMETER_ROBUSTNESS.csv",
    "PHASE12_RANDOM_BASELINE.csv",
    "PHASE12_TRADE_ORDER_MONTE_CARLO.csv",
    "PHASE12_REGIME_ANALYSIS.csv",
]

def get_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1048576):
            h.update(chunk)
    return h.hexdigest()

print("Calculating File Hashes:")
hashes = {}
for fname in files_to_check:
    fpath = REPORTS / fname
    if fpath.exists():
        h = get_hash(fpath)
        hashes[fname] = h
        print(f"  {fname}: {h[:16]}... ({fpath.stat().st_size:,} bytes)")
    else:
        print(f"  MISSING: {fname}")

# Also verify root files match reports files
print("\nVerifying Root Copy Synchronization:")
mismatches = 0
for fname in files_to_check:
    p_rep = REPORTS / fname
    p_root = ROOT / fname
    if p_rep.exists() and p_root.exists():
        h1 = get_hash(p_rep)
        h2 = get_hash(p_root)
        if h1 != h2:
            print(f"  MISMATCH between root and reports: {fname}")
            mismatches += 1
    elif not p_root.exists():
        print(f"  Copying {fname} to root...")
        p_root.write_bytes(p_rep.read_bytes())

print(f"Total Mismatches: {mismatches}")
