import React from 'react';
import { Microscope, AlertTriangle, ShieldCheck, XCircle, CheckCircle2, FileText } from 'lucide-react';

export default function ResearchView({ researchData }) {
  const summary = researchData?.summary || {};
  const status = researchData?.status || 'FROZEN';
  const hypotheses = researchData?.hypotheses || [];

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Research Freeze Banner */}
      <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-800/40">
        <div className="flex items-start space-x-3">
          <div className="p-2 rounded-lg bg-amber-900/40 text-amber-400 border border-amber-700/50 mt-0.5">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-bold text-amber-200 uppercase tracking-wide">
                Scientific Freeze Active — Phase 10C Blocked
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-900/60 text-amber-300 font-bold border border-amber-700">
                STATUS: {status}
              </span>
            </div>
            <p className="text-xs text-amber-300/80 mt-1 leading-relaxed">
              Phase 9E empirical research proved that after accounting for realistic exchange friction (38–44 bps taker fees and slippage),
              naive quantitative signals yield negative net returns (-36.1 bps on sealed holdout). Live execution is blocked by design until genuine passive L2 edge is validated.
            </p>
          </div>
        </div>
      </div>

      {/* Key Research Empirical Findings */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Holdout Out-of-Sample AUC</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">
            {summary.auc_oos ? summary.auc_oos.toFixed(4) : '0.5025'}
          </div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">
            Edge: +0.0025 above coin flip (p=0.690)
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Gross Holdout Return</div>
          <div className="text-xl font-bold font-mono text-rose-400 mt-1">
            {summary.holdout_return_bps ? `${summary.holdout_return_bps.toFixed(1)} bps` : '-36.1 bps'}
          </div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">
            Statistical Significance: None
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Taker Execution Friction</div>
          <div className="text-xl font-bold font-mono text-amber-400 mt-1">38.0 – 44.0 bps</div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">
            Exchange fees + half-spread + market impact
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Passive Queue Edge</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">BLOCKED</div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">
            Requires continuous L2 orderbook data
          </div>
        </div>

      </div>

      {/* Edge vs Friction Visual Comparison */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4">
        <div className="flex items-center space-x-2">
          <Microscope className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">The Edge vs Friction Reality</h3>
        </div>

        <div className="p-4 rounded-lg bg-slate-900/80 border border-slate-800 space-y-3 font-mono text-xs">
          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span>Gross Strategy Theoretical Edge (Taker):</span>
              <span className="text-emerald-400 font-bold">+2.4 bps</span>
            </div>
            <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500" style={{ width: '6%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span>Exchange Friction (Taker Fee + Slippage + Spread):</span>
              <span className="text-rose-400 font-bold">-40.0 bps</span>
            </div>
            <div className="w-full h-3 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-rose-500" style={{ width: '100%' }} />
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800 flex justify-between items-center text-sm font-bold">
            <span className="text-slate-300">Net Realized Taker Edge:</span>
            <span className="text-rose-400">-37.6 bps (Guaranteed Loss if Live)</span>
          </div>
        </div>

        <div className="text-xs text-slate-400 leading-relaxed font-mono">
          <strong className="text-slate-200">Why this matters:</strong> Quantitative retail bots often fail because they backtest with zero-fee assumptions. Jevo strictly enforces realistic friction modeling and keeps paper execution active to preserve capital until a scientifically sound passive market-making edge can be proven.
        </div>
      </div>

      {/* Phase 9D Hypotheses Verification Matrix */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800">
        <h3 className="text-sm font-semibold text-slate-200 mb-3">
          Phase 9D Microstructure Hypotheses (Empirical Verification)
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono text-left">
            <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="p-3">Hypothesis ID</th>
                <th className="p-3">Description</th>
                <th className="p-3">Target Metric</th>
                <th className="p-3">Observed Result</th>
                <th className="p-3">Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {[
                {
                  id: 'P9D-H01',
                  desc: 'Order flow imbalance predicts 1s-10s directional mid-price change with AUC > 0.55',
                  target: 'AUC > 0.55',
                  observed: 'AUC 0.5025 (p=0.690)',
                  verdict: 'REJECTED'
                },
                {
                  id: 'P9D-H02',
                  desc: 'Trade volume acceleration predicts volatility regime transition with accuracy > 65%',
                  target: 'Acc > 65%',
                  observed: 'Acc 51.2% (No signal)',
                  verdict: 'REJECTED'
                },
                {
                  id: 'P9D-H03',
                  desc: 'Micro-price deviation provides profitable taker entry after 38 bps fees',
                  target: 'Net Return > 0 bps',
                  observed: '-36.1 bps (Negative)',
                  verdict: 'REJECTED'
                },
                {
                  id: 'P9D-H04',
                  desc: 'Multi-horizon book depth imbalance yields monotonic alpha decay curve',
                  target: 'Monotonic Alpha',
                  observed: 'Decay noisy / non-stat-sig',
                  verdict: 'REJECTED'
                },
                {
                  id: 'P9D-H05',
                  desc: 'Passive queue join priority yields positive maker edge on 1-second fills',
                  target: 'Positive Fill Margin',
                  observed: 'Unverifiable without L2 MBP',
                  verdict: 'BLOCKED'
                },
              ].map((h, idx) => (
                <tr key={idx} className="hover:bg-slate-800/30">
                  <td className="p-3 font-bold text-slate-200">{h.id}</td>
                  <td className="p-3 text-slate-300 max-w-xs">{h.desc}</td>
                  <td className="p-3 text-slate-400">{h.target}</td>
                  <td className="p-3 text-cyan-300">{h.observed}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      h.verdict === 'REJECTED'
                        ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                        : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                    }`}>
                      {h.verdict}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
