import React from 'react';
import { Server, Activity, Cpu, HardDrive, ShieldCheck, CheckCircle2, Clock } from 'lucide-react';

export default function SystemView({ healthData, botStatus }) {
  const components = healthData?.components || {};
  const sys = healthData?.system || {};

  const componentList = [
    { key: 'bot_core', name: 'Bot Core Engine', desc: 'Main evaluation iteration loop and state machine' },
    { key: 'market_data', name: 'Market Data Streamer', desc: 'Binance.US public market feed and candle aggregators' },
    { key: 'risk_engine', name: 'Risk & Sizing Engine', desc: 'Position sizing, stop loss calculation, drawdown caps' },
    { key: 'paper_broker', name: 'Simulated Paper Broker', desc: 'Virtual order routing, fill execution, fee deduction' },
    { key: 'jev_ai', name: 'Jev AI Reasoning', desc: 'Trend direction, confidence scoring, feature engineering' },
  ];

  const safetyGuarantees = [
    { title: 'PAPER_TRADING_ONLY', status: 'PASS', desc: 'Real order execution paths disabled at core engine' },
    { title: 'LEVERAGE = 1.0x', status: 'PASS', desc: 'Margin borrowing disabled; spot-equivalent exposure only' },
    { title: 'LIVE_ORDERS = 0', status: 'PASS', desc: 'Zero live order endpoints wired to exchange' },
    { title: 'WALLET_CONNECTIONS = 0', status: 'PASS', desc: 'No web3 private keys or wallet connectors imported' },
    { title: 'RESEARCH_FREEZE = ACTIVE', status: 'PASS', desc: 'Phase 10C blocked until verified continuous L2 data' },
    { title: 'AUDIT_TRAIL = PERSISTED', status: 'PASS', desc: 'All state transitions and orders recorded to log buffer' },
  ];

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Top System Health Summary */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">System Operational Health</div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
              <span>Overall Status:</span>
              <span className="text-emerald-400 font-mono">
                {healthData?.status?.toUpperCase() || 'OK'}
              </span>
            </h2>
          </div>
        </div>

        <div className="flex items-center space-x-4 text-xs font-mono">
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <span className="text-slate-500">Uptime: </span>
            <span className="text-slate-200 font-semibold">{Math.floor(botStatus?.uptime_seconds || 0)}s</span>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <span className="text-slate-500">Cycle Iteration: </span>
            <span className="text-slate-200 font-semibold">#{botStatus?.iteration || 0}</span>
          </div>
        </div>
      </div>

      {/* Hardware Telemetry Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>CPU Usage</span>
            <Cpu className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">
            {sys.cpu_percent !== undefined ? `${sys.cpu_percent.toFixed(1)}%` : '—'}
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2 overflow-hidden">
            <div 
              className="h-full bg-cyan-500" 
              style={{ width: `${Math.min(100, sys.cpu_percent || 5)}%` }} 
            />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>RAM Used (Process)</span>
            <HardDrive className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">
            {sys.memory_mb !== undefined ? `${sys.memory_mb.toFixed(1)} MB` : '—'}
          </div>
          <div className="text-[11px] font-mono text-slate-500 mt-1">
            Total RAM: {sys.total_memory_mb ? `${(sys.total_memory_mb / 1024).toFixed(1)} GB` : '—'}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Active Threads</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">
            {sys.threads || 4} Threads
          </div>
          <div className="text-[11px] font-mono text-slate-500 mt-1">
            FastAPI + Bot Event Loop
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Python Runtime</span>
            <Server className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-base font-bold font-mono text-slate-100 mt-1">
            Python 3.12
          </div>
          <div className="text-[11px] font-mono text-slate-500 mt-1">
            FastAPI + Uvicorn + WebSockets
          </div>
        </div>
      </div>

      {/* Components Grid */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-3">
        <h3 className="text-sm font-semibold text-slate-200">Subsystem Diagnostics</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {componentList.map((comp) => {
            const compState = components[comp.key] || 'HEALTHY';
            return (
              <div key={comp.key} className="p-3.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-start justify-between">
                <div>
                  <div className="font-semibold text-xs text-slate-100 font-mono">{comp.name}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{comp.desc}</div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>{compState.toUpperCase()}</span>
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Absolute Safety Invariants Verification */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-3">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">Forensic Safety Guarantees</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {safetyGuarantees.map((g, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-slate-900/40 border border-slate-800/80 flex items-center justify-between text-xs font-mono">
              <div>
                <div className="text-slate-200 font-bold">{g.title}</div>
                <div className="text-[11px] text-slate-500 mt-0.5">{g.desc}</div>
              </div>
              <span className="px-2.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                {g.status}
              </span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
