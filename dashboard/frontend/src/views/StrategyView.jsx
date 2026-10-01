import React from 'react';
import { Sliders, ShieldCheck, Lock, Activity, CheckCircle2 } from 'lucide-react';

export default function StrategyView({ strategyConfig }) {
  const cfg = strategyConfig || {
    symbol: 'BTCUSDT',
    timeframe: '1m',
    ema_fast: 20,
    ema_mid: 50,
    ema_slow: 200,
    rsi_period: 14,
    rsi_oversold: 30,
    rsi_overbought: 70,
    atr_period: 14,
    risk_per_trade_pct: 0.01,
    max_daily_loss_pct: 0.03,
    max_open_positions: 1,
    paper_trading_only: true,
    leverage: 1.0,
  };

  const sections = [
    {
      title: 'Trend & Moving Averages',
      params: [
        { label: 'Target Symbol', value: cfg.symbol, desc: 'Primary trading pair' },
        { label: 'Primary Timeframe', value: cfg.timeframe, desc: 'Bar interval for indicator calculations' },
        { label: 'EMA Fast Period', value: cfg.ema_fast, desc: 'Short-term momentum tracking' },
        { label: 'EMA Mid Period', value: cfg.ema_mid, desc: 'Intermediate trend filter' },
        { label: 'EMA Slow / Base', value: cfg.ema_slow, desc: 'Long-term baseline regime filter' },
      ],
    },
    {
      title: 'Momentum & Volatility',
      params: [
        { label: 'RSI Period', value: cfg.rsi_period, desc: 'Wilder RSI calculation window' },
        { label: 'RSI Oversold Level', value: cfg.rsi_oversold, desc: 'Dip detection boundary' },
        { label: 'RSI Overbought Level', value: cfg.rsi_overbought, desc: 'Exhaustion warning boundary' },
        { label: 'ATR Period', value: cfg.atr_period, desc: 'True range volatility window' },
        { label: 'Stop Loss ATR Multiplier', value: '1.5x', desc: 'Dynamic volatility trailing buffer' },
        { label: 'Take Profit ATR Multiplier', value: '3.0x', desc: 'Favorable reward:risk 2:1 target' },
      ],
    },
    {
      title: 'Risk & Capital Preservation',
      params: [
        { label: 'Risk Per Trade', value: `${(cfg.risk_per_trade_pct * 100).toFixed(1)}%`, desc: 'Max account equity risked per single setup' },
        { label: 'Max Daily Loss Circuit', value: `${(cfg.max_daily_loss_pct * 100).toFixed(1)}%`, desc: 'Auto-halt engine if intraday loss exceeds limit' },
        { label: 'Max Open Positions', value: cfg.max_open_positions, desc: 'Single position constraint avoids correlation exposure' },
        { label: 'Taker Fee Model', value: '10.0 bps', desc: 'Conservative friction modeled per fill' },
      ],
    },
    {
      title: 'Safety Invariants (Non-Overridable)',
      params: [
        { label: 'PAPER_TRADING_ONLY', value: 'TRUE', desc: 'Hard-coded bypass protection', locked: true },
        { label: 'LEVERAGE', value: '1.0x', desc: 'Unleveraged spot only; margin/futures disabled', locked: true },
        { label: 'LIVE_ORDERS', value: '0', desc: 'No exchange order execution endpoints wired', locked: true },
        { label: 'WALLET_CONNECTIONS', value: '0', desc: 'No external web3 or exchange private keys', locked: true },
      ],
    },
  ];

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Strategy Architecture Header */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-cyan-950/60 text-cyan-400 border border-cyan-800/40">
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">Strategy Architecture</div>
            <h2 className="text-lg font-bold text-slate-100">Multi-Horizon Trend & Volatility Engine</h2>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-400 flex items-center space-x-1.5">
            <Lock className="w-3 h-3 text-amber-400" />
            <span>PROTECTED CONFIGURATION</span>
          </span>
          <span className="px-2.5 py-1 rounded bg-emerald-950/40 text-emerald-400 border border-emerald-800/40 font-semibold flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>ACTIVE</span>
          </span>
        </div>
      </div>

      {/* Rules Breakdown */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-mono space-y-2">
        <div className="text-slate-300 font-semibold uppercase tracking-wide">Execution Logic Summary:</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-slate-400">
          <div className="p-2.5 rounded bg-slate-900/80 border border-slate-800/60">
            <strong className="text-emerald-400 block mb-1">LONG Entry Criteria:</strong>
            1. Fast EMA (20) &gt; Mid EMA (50) &gt; Slow EMA (200)<br />
            2. RSI (14) &lt; 70.0 (Not overbought)<br />
            3. No existing open position
          </div>
          <div className="p-2.5 rounded bg-slate-900/80 border border-slate-800/60">
            <strong className="text-rose-400 block mb-1">Exit Criteria:</strong>
            1. Stop Loss: Entry - (1.5 * ATR)<br />
            2. Take Profit: Entry + (3.0 * ATR)<br />
            3. Trend Breakdown: EMA 20 &lt; EMA 50
          </div>
        </div>
      </div>

      {/* Parameter Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {sections.map((sec, idx) => (
          <div key={idx} className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-3">
            <h3 className="text-sm font-semibold text-slate-200">{sec.title}</h3>
            
            <div className="space-y-2 font-mono text-xs">
              {sec.params.map((p, pIdx) => (
                <div key={pIdx} className="p-2.5 rounded bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
                  <div className="max-w-[70%]">
                    <div className="text-slate-300 font-medium">{p.label}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">{p.desc}</div>
                  </div>
                  <div className="text-right flex items-center space-x-1.5">
                    {p.locked && <Lock className="w-3 h-3 text-amber-400" />}
                    <span className={`font-bold ${p.locked ? 'text-amber-400' : 'text-cyan-300'}`}>
                      {p.value}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}
