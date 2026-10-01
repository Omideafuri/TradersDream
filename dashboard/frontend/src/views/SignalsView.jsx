import React from 'react';
import { Cpu, ShieldAlert, CheckCircle, Crosshair, HelpCircle, ArrowRight } from 'lucide-react';

export default function SignalsView({ signalData, positionData, marketData }) {
  const signal = signalData?.latest_signal;
  const history = signalData?.history || [];
  const features = signalData?.features || {};
  const currentPrice = marketData?.latest_candle?.close || 64000;
  const equity = positionData?.account_equity || 10000;

  const atr = features.atr || 350;
  const riskPerTradePct = 0.01; // 1%
  const riskUsd = equity * riskPerTradePct;
  const stopLossDist = atr * 1.5;
  const stopLossPrice = currentPrice - stopLossDist;
  const takeProfitPrice = currentPrice + (atr * 3.0);
  const targetSizeBtc = riskUsd / stopLossDist;

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Top Banner / Decision Header */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 rounded-lg bg-cyan-950/60 text-cyan-400 border border-cyan-800/40">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <div className="text-xs text-slate-400 font-mono uppercase tracking-wider">Jev AI Signal Engine</div>
              <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
                <span>Decision:</span>
                <span className={`px-3 py-0.5 rounded text-sm font-mono font-bold ${
                  signal?.action === 'BUY'
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                    : signal?.action === 'SELL'
                    ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                    : 'bg-slate-700/40 text-slate-300 border border-slate-600'
                }`}>
                  {signal?.action || 'HOLD'}
                </span>
              </h2>
            </div>
          </div>

          <div className="flex items-center space-x-6 text-sm font-mono">
            <div>
              <div className="text-xs text-slate-500">Confidence Metric</div>
              <div className="text-lg font-bold text-cyan-300">
                {((signal?.confidence || 0) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Evaluation Mode</div>
              <div className="text-xs font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-1 rounded border border-emerald-800/40">
                STRICT PAPER
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 p-3.5 rounded-lg bg-slate-900/80 border border-slate-800/80">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide font-mono mb-1">
            Reasoning Summary
          </div>
          <p className="text-sm font-mono text-slate-200 leading-relaxed">
            {signal?.reason || 'No signal evaluated yet. The bot evaluates trend alignment and RSI bounds each cycle.'}
          </p>
        </div>
      </div>

      {/* Sizing & Features Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        
        {/* Risk Management & Sizing Calculation */}
        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Crosshair className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200">Risk Engine Position Sizing</h3>
          </div>

          <div className="space-y-2.5 text-xs font-mono">
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Account Equity:</span>
              <span className="text-slate-100 font-semibold">${equity.toFixed(2)} USDT</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Risk per Trade (1.0%):</span>
              <span className="text-cyan-300 font-semibold">${riskUsd.toFixed(2)} USDT</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Stop Loss Distance (1.5x ATR):</span>
              <span className="text-rose-400 font-semibold">${stopLossDist.toFixed(2)} (${stopLossPrice.toFixed(2)})</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Take Profit Target (3.0x ATR):</span>
              <span className="text-emerald-400 font-semibold">+${(atr * 3.0).toFixed(2)} (${takeProfitPrice.toFixed(2)})</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-cyan-950/30 border border-cyan-800/40">
              <span className="text-cyan-300 font-semibold">Calculated Size (BTC):</span>
              <span className="text-cyan-200 font-bold">{targetSizeBtc.toFixed(4)} BTC (~${(targetSizeBtc * currentPrice).toFixed(2)})</span>
            </div>
          </div>

          <div className="p-3 rounded bg-slate-900/40 border border-slate-800/60 text-[11px] text-slate-400">
            <div className="font-semibold text-slate-300 mb-0.5">Sizing Invariant Check:</div>
            Size is strictly bounded by max account risk (1%) divided by ATR stop distance. Leverage is locked at 1.0x spot.
          </div>
        </div>

        {/* Feature Vectors & Indicator Inputs */}
        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200">Indicator Vectors</h3>
          </div>

          <div className="space-y-2.5 text-xs font-mono">
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">EMA Fast (20) vs Mid (50):</span>
              <span className="text-slate-200 font-semibold">
                {features.ema_fast !== undefined && features.ema_mid !== undefined
                  ? features.ema_fast > features.ema_mid ? 'Bullish (Fast > Mid)' : 'Bearish (Fast < Mid)'
                  : 'Bullish (20 > 50)'}
              </span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">RSI Oscillator (14):</span>
              <span className="text-slate-200 font-semibold">
                {features.rsi !== undefined ? features.rsi.toFixed(2) : '48.50'} (Neutral)
              </span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">ATR Volatility (14):</span>
              <span className="text-slate-200 font-semibold">${atr.toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Trend Alignment:</span>
              <span className="text-emerald-400 font-semibold">{features.trend || 'ALIGNED'}</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Max Open Positions Permitted:</span>
              <span className="text-slate-200 font-semibold">1 (Strict Single-Asset)</span>
            </div>
          </div>
        </div>

      </div>

      {/* Signal History Table */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800">
        <h3 className="text-sm font-semibold text-slate-200 mb-3">Signal Evaluation Log</h3>
        
        {history.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono text-left">
              <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="p-2.5">Time</th>
                  <th className="p-2.5">Symbol</th>
                  <th className="p-2.5">Action</th>
                  <th className="p-2.5">Confidence</th>
                  <th className="p-2.5">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {history.slice(-10).reverse().map((sig, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="p-2.5 text-slate-400">{new Date(sig.timestamp || Date.now()).toLocaleTimeString()}</td>
                    <td className="p-2.5 font-semibold text-slate-100">{sig.symbol || 'BTCUSDT'}</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        sig.action === 'BUY'
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : sig.action === 'SELL'
                          ? 'bg-rose-500/20 text-rose-400'
                          : 'bg-slate-700/30 text-slate-400'
                      }`}>
                        {sig.action}
                      </span>
                    </td>
                    <td className="p-2.5 text-cyan-300">{((sig.confidence || 0) * 100).toFixed(1)}%</td>
                    <td className="p-2.5 text-slate-400 max-w-xs truncate">{sig.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 text-center text-xs text-slate-500 font-mono">
            No past signals in buffer. Signals will populate as bot cycles run.
          </div>
        )}
      </div>

    </div>
  );
}
