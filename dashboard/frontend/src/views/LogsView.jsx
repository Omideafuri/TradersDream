import React, { useState, useRef, useEffect } from 'react';
import { Terminal, Search, Trash2, Download, ArrowDownCircle } from 'lucide-react';
import { api } from '../utils/api';

export default function LogsView({ logs, onRefreshLogs }) {
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const filteredLogs = (logs || []).filter(l => {
    if (levelFilter !== 'ALL' && l.level?.toUpperCase() !== levelFilter) return false;
    if (search && !l.message?.toLowerCase().includes(search.toLowerCase()) && !l.module?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const getLevelColor = (level) => {
    switch (level?.toUpperCase()) {
      case 'CRITICAL':
        return 'text-rose-400 font-bold bg-rose-950/50 border border-rose-800/60 px-1.5 py-0.5 rounded';
      case 'ERROR':
        return 'text-red-400 font-semibold bg-red-950/40 border border-red-800/40 px-1.5 py-0.5 rounded';
      case 'WARNING':
        return 'text-amber-400 bg-amber-950/40 border border-amber-800/40 px-1.5 py-0.5 rounded';
      case 'INFO':
      default:
        return 'text-cyan-400 bg-cyan-950/30 border border-cyan-800/30 px-1.5 py-0.5 rounded';
    }
  };

  const handleDownload = () => {
    if (!logs || logs.length === 0) return;
    const text = logs.map(l => `[${l.timestamp}] [${l.level}] [${l.module}] ${l.message}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jevo_terminal_logs_${Date.now()}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 animate-fade-in flex flex-col h-[calc(100vh-120px)]">
      
      {/* Top Filter and Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[#0f172a] border border-slate-800">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <Terminal className="w-5 h-5 text-cyan-400" />
            <h2 className="text-sm font-bold text-slate-100 font-mono">System Console</h2>
          </div>

          {/* Level Filter Pills */}
          <div className="hidden sm:flex items-center space-x-1 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs font-mono">
            {['ALL', 'INFO', 'WARNING', 'ERROR'].map(lvl => (
              <button
                key={lvl}
                onClick={() => setLevelFilter(lvl)}
                className={`px-2.5 py-0.5 rounded transition ${
                  levelFilter === lvl
                    ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>

        {/* Search & Actions */}
        <div className="flex items-center space-x-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search logs..."
              className="pl-8 pr-3 py-1 bg-slate-900 text-xs font-mono text-slate-200 placeholder-slate-500 rounded-lg border border-slate-800 focus:outline-none focus:border-cyan-500/60 w-44"
            />
          </div>

          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded-lg border text-xs font-mono flex items-center space-x-1 transition ${
              autoScroll 
                ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30' 
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
            title="Toggle autoscroll"
          >
            <ArrowDownCircle className="w-4 h-4" />
          </button>

          <button
            onClick={handleDownload}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Download log file"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Terminal Output Window */}
      <div className="flex-1 bg-[#06090e] border border-slate-800/90 rounded-xl p-4 overflow-y-auto font-mono text-xs select-text shadow-inner">
        {filteredLogs.length > 0 ? (
          <div className="space-y-1.5">
            {filteredLogs.map((log, idx) => (
              <div key={idx} className="flex items-start space-x-2.5 hover:bg-slate-900/60 p-0.5 rounded leading-relaxed">
                <span className="text-slate-500 select-none text-[11px] whitespace-nowrap">
                  {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
                </span>
                <span className={`text-[10px] select-none ${getLevelColor(log.level)}`}>
                  {log.level?.padEnd(7)}
                </span>
                <span className="text-slate-500 text-[11px] select-none whitespace-nowrap">
                  [{log.module || 'bot'}]
                </span>
                <span className="text-slate-200 flex-1 break-all">
                  {log.message}
                </span>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-slate-500 font-mono text-xs">
            No log entries match the current filter.
          </div>
        )}
      </div>

    </div>
  );
}
