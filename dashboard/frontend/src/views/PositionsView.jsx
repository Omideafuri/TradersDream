import React, { useState } from 'react';
import { Layers, ShieldCheck, AlertTriangle, TrendingUp, TrendingDown, DollarSign } from 'lucide-react';
import Modal from '../components/Modal';
import { api } from '../utils/api';

export default function PositionsView({ positionData, marketData, onRefresh }) {
  const [closeModalOpen, setCloseModalOpen] = useState(false);
  const [closing, setClosing] = useState(false);

  const openPos = positionData?.open_position;
  const currentPrice = marketData?.latest_candle?.close || 64000;
  const equity = positionData?.account_equity || 10000;
  const dailyPnl = positionData?.daily_pnl || 0;

  const handleClose = async () => {
    setClosing(true);
    try {
      await api.closePosition(openPos?.symbol || 'BTCUSDT');
      setCloseModalOpen(false);
      onRefresh();
    } catch (e) {
      alert(`Close position error: ${e.message}`);
    } finally {
      setClosing(false);
    }
  };

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Active Position Section */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-slate-100">Open Paper Position</h2>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-400">
            Engine Capacity: 1 Max Position
          </span>
        </div>

        {openPos ? (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono text-left">
                <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="p-3">Asset</th>
                    <th className="p-3">Side</th>
                    <th className="p-3">Size (BTC)</th>
                    <th className="p-3">Entry Price</th>
                    <th className="p-3">Mark Price</th>
                    <th className="p-3">Market Value</th>
                    <th className="p-3">Unrealized PnL</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  <tr className="hover:bg-slate-800/30">
                    <td className="p-3 font-bold text-slate-100">{openPos.symbol}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                        {openPos.side}
                      </span>
                    </td>
                    <td className="p-3">{openPos.size?.toFixed(4)} BTC</td>
                    <td className="p-3">${openPos.entry_price?.toFixed(2)}</td>
                    <td className="p-3">${currentPrice.toFixed(2)}</td>
                    <td className="p-3">${(openPos.size * currentPrice).toFixed(2)}</td>
                    <td className="p-3">
                      <span className={`font-bold ${openPos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {openPos.unrealized_pnl >= 0 ? `+$${openPos.unrealized_pnl.toFixed(2)}` : `-$${Math.abs(openPos.unrealized_pnl).toFixed(2)}`}
                        <span className="text-[11px] ml-1">
                          ({openPos.unrealized_pnl_pct >= 0 ? `+${openPos.unrealized_pnl_pct.toFixed(2)}%` : `${openPos.unrealized_pnl_pct.toFixed(2)}%`})
                        </span>
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setCloseModalOpen(true)}
                        className="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded transition text-xs"
                      >
                        Close Market
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-lg bg-slate-900/50 border border-slate-800/80 text-xs font-mono">
              <div>
                <span className="text-slate-500">Stop Loss:</span>
                <span className="text-rose-400 font-semibold ml-2">
                  {openPos.stop_loss ? `$${openPos.stop_loss.toFixed(2)}` : 'None'}
                </span>
              </div>
              <div>
                <span className="text-slate-500">Take Profit:</span>
                <span className="text-emerald-400 font-semibold ml-2">
                  {openPos.take_profit ? `$${openPos.take_profit.toFixed(2)}` : 'None'}
                </span>
              </div>
              <div>
                <span className="text-slate-500">Leverage:</span>
                <span className="text-cyan-400 font-semibold ml-2">1.0x (Spot Only)</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-10 rounded-lg bg-slate-900/30 border border-slate-800 text-center space-y-2">
            <div className="w-12 h-12 rounded-full bg-slate-800/50 flex items-center justify-center mx-auto text-slate-500">
              <Layers className="w-6 h-6" />
            </div>
            <div className="text-sm font-semibold text-slate-300">No Open Positions</div>
            <p className="text-xs text-slate-500 font-mono max-w-sm mx-auto">
              Paper portfolio is currently 100% in cash (USDT). The bot will enter long positions when trend alignment and risk filters pass.
            </p>
          </div>
        )}
      </div>

      {/* Risk Limits & Safety Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        
        {/* Risk Limits */}
        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-3">
          <h3 className="text-sm font-semibold text-slate-200">Active Risk Constraints</h3>
          
          <div className="space-y-2.5 text-xs font-mono">
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Total Portfolio Value:</span>
              <span className="text-slate-100 font-semibold">${equity.toFixed(2)} USDT</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Daily Loss Used / Limit (3.0%):</span>
              <span className="text-slate-200 font-semibold">
                ${Math.abs(Math.min(0, dailyPnl)).toFixed(2)} / ${(equity * 0.03).toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Max Position Size Allowed (30% equity):</span>
              <span className="text-slate-200 font-semibold">${(equity * 0.30).toFixed(2)}</span>
            </div>
            <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">Risk per Individual Trade:</span>
              <span className="text-cyan-300 font-semibold">1.0% ($100.00 max risk)</span>
            </div>
          </div>
        </div>

        {/* Safety Invariants Checklist */}
        <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-3">
          <h3 className="text-sm font-semibold text-slate-200">Execution Safety Audit</h3>

          <div className="space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">PAPER_TRADING_ONLY:</span>
              <span className="flex items-center space-x-1 text-emerald-400 font-bold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>TRUE (HARD-LOCKED)</span>
              </span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">LIVE_ORDERS:</span>
              <span className="text-emerald-400 font-bold">0 (NO ORDER ENDPOINTS)</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">WALLET_CONNECTIONS:</span>
              <span className="text-emerald-400 font-bold">0 (UNCONNECTED)</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800">
              <span className="text-slate-400">LEVERAGE:</span>
              <span className="text-emerald-400 font-bold">1.0x (SPOT NO-BORROW)</span>
            </div>
          </div>
        </div>

      </div>

      {/* Close Position Modal */}
      <Modal
        isOpen={closeModalOpen}
        onClose={() => setCloseModalOpen(false)}
        onConfirm={handleClose}
        title="Confirm Position Closure"
        confirmText="Confirm Close"
        confirmVariant="danger"
        isProcessing={closing}
      >
        <p className="mb-2">Are you sure you want to close this position at current mark price?</p>
        <div className="p-3 bg-slate-900 rounded border border-slate-800 font-mono text-xs">
          <div>Symbol: {openPos?.symbol}</div>
          <div>Size: {openPos?.size} BTC</div>
          <div>Mark Price: ${currentPrice.toFixed(2)}</div>
        </div>
      </Modal>

    </div>
  );
}
