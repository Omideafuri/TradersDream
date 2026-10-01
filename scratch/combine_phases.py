from pathlib import Path

root = Path(__file__).resolve().parent.parent

p11_order = [
    'PHASE11_XAUUSD_DATA_PROVENANCE.md',
    'PHASE11_DATA_QUALITY_AUDIT.md',
    'PHASE11_STRATEGY_FREEZE.md',
    'PHASE11_PNL_RECONCILIATION.md',
    'PHASE11_COST_ACCOUNTING_AUDIT.md',
    'PHASE11_WALK_FORWARD.md',
    'PHASE11_DRAWDOWN_AUDIT.md',
    'PHASE11_STATISTICS_AUDIT.md',
    'PHASE11_PARAMETER_ROBUSTNESS.md',
    'PHASE11_RANDOM_BASELINE.md',
    'PHASE11_REGIME_ANALYSIS.md',
    'PHASE11_LEAKAGE_AUDIT.md',
    'PHASE11_CLAIM_AUDIT.md',
    'PHASE11_FINAL_REPORT.md',
]

p12_order = [
    'PHASE12_DATA_PROVENANCE_AUDIT.md',
    'PHASE12_DATA_AUDIT.md',
    'PHASE12_DATA_CROSS_VALIDATION.md',
    'PHASE12_BROKER_SPECIFICATION.md',
    'PHASE12_BID_ASK_AUDIT.md',
    'PHASE12_EXECUTION_AUDIT.md',
    'PHASE12_PNL_RECONCILIATION.md',
    'PHASE12_GAP_RISK_REPORT.md',
    'PHASE12_RETURN_AUDIT.md',
    'PHASE12_STATISTICAL_AUDIT.md',
    'PHASE12_STATISTICS_AUDIT.md',
    'PHASE12_MULTIPLE_TESTING_AUDIT.md',
    'PHASE12_HOLDOUT_INTEGRITY.md',
    'PHASE12_HOLDOUT_INTEGRITY_AUDIT.md',
    'PHASE12_LEAKAGE_AUDIT.md',
    'PHASE12_CODE_FORENSIC_AUDIT.md',
    'PHASE12_FORWARD_CAPTURE.md',
    'PHASE12_REPRODUCIBILITY.md',
    'PHASE12_FINAL_REPORT.md',
]

out = []
out.append('# MASTER COMPILATION: PHASE 11 & PHASE 12 QUANTITATIVE AUDIT & RESEARCH COMPENDIUM\n\n')
out.append('**Instrument:** XAU/USD (Spot Gold vs US Dollar)  \n')
out.append('**Strategy ID:** `XAUUSD_FROZEN_SMA50_200_1H`  \n')
out.append('**Evaluation Period:** 2021-01-03 to 2025-12-31 (5 Years Historical)  \n')
out.append('**Compilation Timestamp:** 2026-10-01T02:42:00+03:30  \n')
out.append('**Safety Standard:** STRICTLY PAPER TRADING ONLY — ZERO LIVE ORDERS — NO WALLET CONNECTION  \n\n')
out.append('---\n\n')
out.append('## MASTER TABLE OF CONTENTS\n\n')

out.append('### PART I: PHASE 11 — QUANTITATIVE DISCOVERY, RESEARCH FREEZE & PRE-HOLDOUT VERIFICATION\n\n')
for i, f in enumerate(p11_order, 1):
    slug = f"phase-11-{f.lower().replace('_', '-').replace('.', '')}"
    out.append(f"{i}. [{f}](#{slug})\n")

out.append('\n### PART II: PHASE 12 — INDEPENDENT EXECUTION, MICROSTRUCTURE & FORENSIC AUDIT\n\n')
for j, f in enumerate(p12_order, 1):
    slug = f"phase-12-{f.lower().replace('_', '-').replace('.', '')}"
    out.append(f"{j}. [{f}](#{slug})\n")

out.append('\n\n' + '='*80 + '\n\n')
out.append('# PART I: PHASE 11 RESEARCH & VERIFICATION REPORTS\n\n')

for f in p11_order:
    p = root / f
    if not p.exists():
        p = root / 'phase11' / 'reports' / f
    content = p.read_text(encoding='utf-8')
    slug = f"phase-11-{f.lower().replace('_', '-').replace('.', '')}"
    out.append(f'<a id="{slug}"></a>\n\n')
    out.append(f'---\n\n# DOCUMENT: {f}\n\n')
    out.append(content)
    out.append('\n\n' + '-'*60 + '\n\n')

out.append('\n\n' + '='*80 + '\n\n')
out.append('# PART II: PHASE 12 INDEPENDENT FORENSIC AUDIT & EXECUTION REPORTS\n\n')

for f in p12_order:
    p = root / f
    if not p.exists():
        p = root / 'phase12' / 'reports' / f
    content = p.read_text(encoding='utf-8')
    slug = f"phase-12-{f.lower().replace('_', '-').replace('.', '')}"
    out.append(f'<a id="{slug}"></a>\n\n')
    out.append(f'---\n\n# DOCUMENT: {f}\n\n')
    out.append(content)
    out.append('\n\n' + '-'*60 + '\n\n')

target = root / 'PHASE11_AND_PHASE12_MASTER_AUDIT_REPORT.md'
target.write_text(''.join(out), encoding='utf-8')
print(f'Successfully wrote master document to {target} (Size: {target.stat().st_size:,} bytes)')
