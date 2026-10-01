import React, { useState } from 'react';
import { History, TrendingUp, TrendingDown, Filter, Download } from 'lucide-react';

export default function TradesView({ tradeData }) {
  const [filter, setFilter] = useState('ALL'); // ALL, WIN, LOSS

  const trades = tradeData?.trades || [];
  
  const filteredTrades = trades.filter(t => {
    if (filter === 'WIN') return (t.pnl || 0) > 0;
    if (filter === 'LOSS') return (t.pnl || 0) < 0;
    return true;
  });

  const totalTrades = trades.length;
  const wins = trades.filter(t => (t.pnl || 0) > 0);
  const losses = trades.filter(t => (t.pnl || 0) < 0);
  const winRate = totalTrades > 0 ? (wins.length / totalTrades) * 100 : 0;
  
  const totalPnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const totalWinAmount = wins.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const totalLossAmount = Math.abs(losses.reduce((sum, t) => sum + (t.pnl || 0), 0));
  const profitFactor = totalLossAmount > 0 ? (totalWinAmount / totalLossAmount) : (totalWinAmount > 0 ? 99.9 : 1.0);

  const exportCsv = () => {
    if (trades.length === 0) return;
    const headers = ['id', 'timestamp', 'symbol', 'side', 'size', 'entry_price', 'exit_price', 'pnl', 'fee', 'exit_reason'];
    const rows = trades.map(t => [
      t.id,
      t.exit_time || t.timestamp,
      t.symbol,
      t.side,
      t.size,
      t.entry_price,
      t.exit_price,
      t.pnl,
      t.fee,
      t.exit_reason || 'NORMAL'
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `jevo_paper_trades_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Top Trade Statistics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Total Closed Trades</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">{totalTrades}</div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">{wins.length}W / {losses.length}L</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Win Rate</div>
          <div className="text-xl font-bold font-mono text-cyan-300 mt-1">{winRate.toFixed(1)}%</div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">Target: &gt; 52.0%</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Realized Net PnL</div>
          <div className={`text-xl font-bold font-mono mt-1 ${totalPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {totalPnl >= 0 ? `+$${totalPnl.toFixed(2)}` : `-$${Math.abs(totalPnl).toFixed(2)}`}
          </div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">Net of fees & slippage</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="text-slate-400 text-xs">Profit Factor</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-1">{profitFactor.toFixed(2)}</div>
          <div className="text-[11px] font-mono text-slate-500 mt-0.5">Gross Wins / Gross Losses</div>
        </div>
      </div>

      {/* Main Ledger Table */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center space-x-2">
            <History className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-slate-100">Trade Ledger</h2>
          </div>

          <div className="flex items-center space-x-2">
            {/* Filter Pills */}
            <div className="flex items-center space-x-1 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs font-mono">
              {['ALL', 'WIN', 'LOSS'].map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-2.5 py-1 rounded transition ${
                    filter === f 
                      ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40' 
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>

            <button
              onClick={exportCsv}
              disabled={trades.length === 0}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg border border-slate-700 text-xs font-mono transition disabled:opacity-40"
              title="Export trades as CSV"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>
          </div>
        </div>

        {filteredTrades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono text-left">
              <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="p-3">Trade ID / Time</th>
                  <th className="p-3">Asset</th>
                  <th className="p-3">Side</th>
                  <th className="p-3">Size (BTC)</th>
                  <th className="p-3">Entry Price</th>
                  <th className="p-3">Exit Price</th>
                  <th className="p-3">Realized PnL</th>
                  <th className="p-3">Fee Paid</th>
                  <th className="p-3">Exit Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {filteredTrades.slice().reverse().map((t, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30">
                    <td className="p-3 text-slate-400">
                      <div className="font-semibold text-slate-200">{t.id || `#${idx + 1}`}</div>
                      <div className="text-[10px] text-slate-500">{new Date(t.exit_time || Date.now()).toLocaleString()}</div>
                    </td>
                    <td className="p-3 font-semibold text-slate-100">{t.symbol}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        t.side === 'BUY' || t.side === 'LONG'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      }`}>
                        {t.side}
                      </span>
                    </td>
                    <td className="p-3">{t.size?.toFixed(4)} BTC</td>
                    <td className="p-3">${t.entry_price?.toFixed(2)}</td>
                    <td className="p-3">${t.exit_price?.toFixed(2)}</td>
                    <td className="p-3">
                      <span className={`font-bold ${(t.pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {(t.pnl || 0) >= 0 ? `+$${t.pnl.toFixed(2)}` : `-$${Math.abs(t.pnl).toFixed(2)}`}
                      </span>
                    </td>
                    <td className="p-3 text-slate-400">${t.fee ? t.fee.toFixed(2) : '0.00'}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-300">
                        {t.exit_reason || 'TAKE_PROFIT'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 text-center text-slate-500 font-mono text-xs">
            No trades match the selected filter.
          </div>
        )}
      </div>

    </div>
  );
}
