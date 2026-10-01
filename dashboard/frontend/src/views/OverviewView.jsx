import React, { useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Percent, 
  Activity, 
  ShieldCheck, 
  Cpu, 
  AlertCircle,
  ExternalLink,
  ArrowRight
} from 'lucide-react';
import { api } from '../utils/api';
import Modal from '../components/Modal';

export default function OverviewView({ 
  botStatus, 
  marketData, 
  signalData, 
  positionData, 
  tradeData,
  onRefresh,
  onSelectTab
}) {
  const [closeModalOpen, setCloseModalOpen] = useState(false);
  const [closing, setClosing] = useState(false);

  const equity = positionData?.account_equity || 10000.0;
  const dailyPnl = positionData?.daily_pnl || 0.0;
  const dailyPnlPct = (dailyPnl / (equity - dailyPnl || 1)) * 100;
  
  const openPos = positionData?.open_position;
  const hasPosition = !!openPos;
  
  const trades = tradeData?.trades || [];
  const closedCount = trades.length;
  const wins = trades.filter(t => (t.pnl || 0) > 0).length;
  const winRate = closedCount > 0 ? (wins / closedCount) * 100 : 0;

  const currentPrice = marketData?.latest_candle?.close || 0;
  const signal = signalData?.latest_signal;

  const handleClosePosition = async () => {
    setClosing(true);
    try {
      await api.closePosition(openPos?.symbol || 'BTCUSDT');
      setCloseModalOpen(false);
      onRefresh();
    } catch (e) {
      alert(`Failed to close position: ${e.message}`);
    } finally {
      setClosing(false);
    }
  };

  return (
    <div className="space-y-5 animate-fade-in">
      
      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        
        {/* Equity Card */}
        <div className="p-4 rounded-xl bg-[#0f172a]/90 border border-slate-800 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Portfolio Equity</span>
            <DollarSign className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="text-xl font-bold font-mono-numbers text-slate-100">
            ${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-1">Paper Account (Spot)</div>
        </div>

        {/* Daily PnL Card */}
        <div className="p-4 rounded-xl bg-[#0f172a]/90 border border-slate-800 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Daily PnL</span>
            {dailyPnl >= 0 ? (
              <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
            )}
          </div>
          <div className={`text-xl font-bold font-mono-numbers ${dailyPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {dailyPnl >= 0 ? `+$${dailyPnl.toFixed(2)}` : `-$${Math.abs(dailyPnl).toFixed(2)}`}
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1">
            {dailyPnlPct >= 0 ? `+${dailyPnlPct.toFixed(2)}%` : `${dailyPnlPct.toFixed(2)}%`} today
          </div>
        </div>

        {/* Open Exposure Card */}
        <div className="p-4 rounded-xl bg-[#0f172a]/90 border border-slate-800 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Exposure</span>
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="text-xl font-bold font-mono-numbers text-slate-100">
            {hasPosition ? `${openPos.size.toFixed(4)} BTC` : '0.0000 BTC'}
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1">
            {hasPosition 
              ? `$${(openPos.size * currentPrice).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (1.0x Spot)`
              : 'Flat (100% Cash)'
            }
          </div>
        </div>

        {/* Trades & Win Rate */}
        <div className="p-4 rounded-xl bg-[#0f172a]/90 border border-slate-800 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Trades & Win Rate</span>
            <Percent className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="text-xl font-bold font-mono-numbers text-slate-100">
            {winRate.toFixed(1)}%
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1">
            {wins}W / {closedCount - wins}L ({closedCount} total)
          </div>
        </div>

        {/* Safety Mode Card */}
        <div className="p-4 rounded-xl bg-[#0f172a]/90 border border-slate-800 shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>Execution Mode</span>
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-sm font-bold font-mono text-emerald-400">
            PAPER ONLY
          </div>
          <div className="text-[11px] font-mono text-slate-400 mt-1">
            Live Orders: 0 | Lev: 1.0x
          </div>
        </div>
      </div>

      {/* Middle Row: Active Signal + Active Position */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        
        {/* Active Signal & Decision Card */}
        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Cpu className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-200">Latest Jev AI Signal</h3>
              </div>
              <button 
                onClick={() => onSelectTab('signals')}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
              >
                <span>Full Analysis</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {signal ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div className="flex items-center space-x-3">
                    <span className={`px-3 py-1 rounded text-xs font-bold font-mono tracking-wider ${
                      signal.action === 'BUY' 
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' 
                        : signal.action === 'SELL' 
                        ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40' 
                        : 'bg-slate-700/50 text-slate-300 border border-slate-600'
                    }`}>
                      {signal.action}
                    </span>
                    <span className="text-xs text-slate-300 font-mono">
                      Target: <span className="font-semibold text-slate-100">{signal.symbol || 'BTCUSDT'}</span>
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-slate-400">Confidence</div>
                    <div className="text-sm font-bold font-mono text-cyan-300">
                      {((signal.confidence || 0) * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                <div className="text-xs text-slate-400 bg-slate-900/50 p-3 rounded-lg border border-slate-800/80">
                  <div className="text-slate-500 font-mono text-[10px] uppercase mb-1">Reasoning Breakdown</div>
                  <div className="text-slate-300 leading-relaxed font-mono">
                    {signal.reason || 'Awaiting signal calculation...'}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                    <div className="text-slate-500 text-[10px]">RSI (14)</div>
                    <div className="font-mono font-semibold text-slate-200">
                      {signalData?.features?.rsi !== undefined ? signalData.features.rsi.toFixed(1) : '—'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                    <div className="text-slate-500 text-[10px]">ATR Volatility</div>
                    <div className="font-mono font-semibold text-slate-200">
                      {signalData?.features?.atr !== undefined ? `$${signalData.features.atr.toFixed(1)}` : '—'}
                    </div>
                  </div>
                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                    <div className="text-slate-500 text-[10px]">Regime</div>
                    <div className="font-mono font-semibold text-slate-200">
                      {signalData?.features?.trend || 'TRENDING'}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 py-6 text-center font-mono">
                No signal evaluated yet. Start the bot to evaluate market conditions.
              </div>
            )}
          </div>

          <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>Cycle Iteration: #{botStatus?.iteration || 0}</span>
            <span>Uptime: {Math.floor(botStatus?.uptime_seconds || 0)}s</span>
          </div>
        </div>

        {/* Active Paper Position Card */}
        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-200">Active Paper Position</h3>
              </div>
              <button 
                onClick={() => onSelectTab('positions')}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
              >
                <span>Risk & Details</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {hasPosition ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                        {openPos.side}
                      </span>
                      <span className="text-sm font-bold text-slate-100 font-mono">{openPos.symbol}</span>
                    </div>
                    <div className="text-xs text-slate-400 mt-1 font-mono">
                      Entry: <span className="text-slate-200 font-semibold">${openPos.entry_price?.toFixed(2)}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-slate-400">Unrealized PnL</div>
                    <div className={`text-base font-bold font-mono ${openPos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {openPos.unrealized_pnl >= 0 ? `+$${openPos.unrealized_pnl.toFixed(2)}` : `-$${Math.abs(openPos.unrealized_pnl).toFixed(2)}`}
                      <span className="text-xs ml-1 font-medium">
                        ({openPos.unrealized_pnl_pct >= 0 ? `+${openPos.unrealized_pnl_pct.toFixed(2)}%` : `${openPos.unrealized_pnl_pct.toFixed(2)}%`})
                      </span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded bg-slate-900/50 border border-slate-800">
                    <span className="text-slate-500">Position Size:</span>
                    <div className="font-mono font-semibold text-slate-200 mt-0.5">
                      {openPos.size?.toFixed(4)} BTC (${(openPos.size * currentPrice).toFixed(2)})
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-slate-900/50 border border-slate-800">
                    <span className="text-slate-500">Mark Price:</span>
                    <div className="font-mono font-semibold text-slate-200 mt-0.5">
                      ${currentPrice.toFixed(2)}
                    </div>
                  </div>
                </div>

                <div className="pt-1">
                  <button
                    onClick={() => setCloseModalOpen(true)}
                    className="w-full py-2 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 text-xs font-semibold rounded-lg transition"
                  >
                    Close Position at Market (Paper)
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-8 rounded-lg bg-slate-900/40 border border-slate-800/80 text-center space-y-2">
                <div className="w-10 h-10 rounded-full bg-slate-800/60 flex items-center justify-center mx-auto text-slate-500">
                  <Activity className="w-5 h-5" />
                </div>
                <div className="text-xs text-slate-300 font-medium">No Open Paper Position</div>
                <div className="text-[11px] text-slate-500 font-mono">
                  Engine is monitoring market. Capital is 100% USDT cash.
                </div>
              </div>
            )}
          </div>

          <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>Stop Loss: {openPos?.stop_loss ? `$${openPos.stop_loss.toFixed(2)}` : 'None'}</span>
            <span>Take Profit: {openPos?.take_profit ? `$${openPos.take_profit.toFixed(2)}` : 'None'}</span>
          </div>
        </div>
      </div>

      {/* Bottom Row: Market Indicators Quick Glance + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* Market Indicators */}
        <div className="lg:col-span-1 p-5 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-200">Market Telemetry</h3>
            <button 
              onClick={() => onSelectTab('markets')}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
            >
              <span>Chart</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between p-2 rounded bg-slate-900/60 border border-slate-800/80">
              <span className="text-slate-400">BTC/USDT Spot:</span>
              <span className="font-mono font-semibold text-slate-100">${currentPrice.toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-900/60 border border-slate-800/80">
              <span className="text-slate-400">EMA Fast (20):</span>
              <span className="font-mono font-semibold text-cyan-400">
                ${marketData?.indicators?.ema_20 ? marketData.indicators.ema_20.toFixed(2) : '—'}
              </span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-900/60 border border-slate-800/80">
              <span className="text-slate-400">EMA Mid (50):</span>
              <span className="font-mono font-semibold text-amber-400">
                ${marketData?.indicators?.ema_50 ? marketData.indicators.ema_50.toFixed(2) : '—'}
              </span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-900/60 border border-slate-800/80">
              <span className="text-slate-400">EMA Trend (200):</span>
              <span className="font-mono font-semibold text-purple-400">
                ${marketData?.indicators?.ema_200 ? marketData.indicators.ema_200.toFixed(2) : '—'}
              </span>
            </div>
            <div className="flex justify-between p-2 rounded bg-slate-900/60 border border-slate-800/80">
              <span className="text-slate-400">RSI (14):</span>
              <span className="font-mono font-semibold text-slate-200">
                {marketData?.indicators?.rsi ? marketData.indicators.rsi.toFixed(2) : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Live Activity / Events */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-[#0f172a] border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-200">Recent Trading Activity</h3>
              <button 
                onClick={() => onSelectTab('trades')}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
              >
                <span>Full Ledger</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {trades.length > 0 ? (
              <div className="space-y-2">
                {trades.slice(-4).reverse().map((t, idx) => (
                  <div 
                    key={idx} 
                    className="flex items-center justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/80 text-xs"
                  >
                    <div className="flex items-center space-x-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                        (t.pnl || 0) >= 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                      }`}>
                        {t.side}
                      </span>
                      <span className="font-mono text-slate-200 font-semibold">{t.symbol}</span>
                      <span className="text-slate-500 text-[11px] font-mono">
                        ${t.entry_price?.toFixed(2)} → ${t.exit_price?.toFixed(2)}
                      </span>
                    </div>
                    <div className="text-right font-mono">
                      <span className={`font-bold ${(t.pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {(t.pnl || 0) >= 0 ? `+$${t.pnl.toFixed(2)}` : `-$${Math.abs(t.pnl).toFixed(2)}`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-xs text-slate-500 font-mono">
                No closed trades yet in current session.
              </div>
            )}
          </div>

          <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500 font-mono">
            <span>Trading Engine: CryptoTradingBot</span>
            <span>Fee Model: 0.10% Taker / 0.10% Maker</span>
          </div>
        </div>

      </div>

      {/* Close Position Modal */}
      <Modal
        isOpen={closeModalOpen}
        onClose={() => setCloseModalOpen(false)}
        onConfirm={handleClosePosition}
        title="Close Open Paper Position?"
        confirmText="Close Position"
        confirmVariant="danger"
        isProcessing={closing}
      >
        <p className="mb-2">Are you sure you want to close the current open paper position at market?</p>
        <div className="p-3 bg-slate-900/70 rounded border border-slate-800 font-mono text-xs space-y-1">
          <div>Symbol: <span className="text-white font-semibold">{openPos?.symbol}</span></div>
          <div>Size: <span className="text-white font-semibold">{openPos?.size} BTC</span></div>
          <div>Estimated Exit: <span className="text-white font-semibold">${currentPrice.toFixed(2)}</span></div>
        </div>
      </Modal>
    </div>
  );
}
