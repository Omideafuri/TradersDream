import React, { useState } from 'react';
import { Settings, Key, Link2, RefreshCw, CheckCircle, ShieldAlert, AlertCircle } from 'lucide-react';
import { getStoredToken, setStoredToken } from '../utils/api';

export default function SettingsView({ wsStatus, onReconnectWs }) {
  const [token, setToken] = useState(getStoredToken());
  const [saved, setSaved] = useState(false);

  const handleSaveToken = (e) => {
    e.preventDefault();
    setStoredToken(token.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-4 animate-fade-in max-w-4xl">
      
      {/* Settings Header */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-cyan-950/60 text-cyan-400 border border-cyan-800/40">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100">Cockpit Settings & Security</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Configure dashboard authentication credentials and connection endpoints.
            </p>
          </div>
        </div>
      </div>

      {/* Operator Authentication Form */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4">
        <div className="flex items-center space-x-2">
          <Key className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-200">Operator Authentication Token (X-API-Key)</h3>
        </div>

        <p className="text-xs text-slate-400 leading-relaxed font-mono">
          All state-modifying actions (Start, Pause, Resume, Stop, and Emergency Stop) require an authorized operator token sent in the <code className="text-cyan-300">X-API-Key</code> request header.
        </p>

        <form onSubmit={handleSaveToken} className="space-y-3">
          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1">
              Active Operator Secret Token:
            </label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full max-w-xl px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/60"
              placeholder="Enter operator token..."
            />
          </div>

          <div className="flex items-center space-x-3 pt-1">
            <button
              type="submit"
              className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold font-mono transition"
            >
              Save Credentials
            </button>
            {saved && (
              <span className="flex items-center space-x-1.5 text-xs text-emerald-400 font-mono">
                <CheckCircle className="w-4 h-4" />
                <span>Token saved successfully</span>
              </span>
            )}
          </div>
        </form>
      </div>

      {/* WebSocket Connection Management */}
      <div className="p-5 rounded-xl bg-[#0f172a] border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Link2 className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200">WebSocket Live Channel</h3>
          </div>
          <span className={`px-2.5 py-1 rounded text-xs font-mono font-semibold ${
            wsStatus === 'CONNECTED' 
              ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/40' 
              : 'bg-rose-950/40 text-rose-400 border border-rose-800/40'
          }`}>
            {wsStatus}
          </span>
        </div>

        <div className="space-y-2 text-xs font-mono text-slate-400">
          <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
            <span>WebSocket Target URL:</span>
            <span className="text-slate-200">/ws (Auto-proxied to :8000)</span>
          </div>
          <div className="flex justify-between p-2.5 rounded bg-slate-900/60 border border-slate-800">
            <span>Broadcasting Frequency:</span>
            <span className="text-slate-200">1.0 second heartbeat</span>
          </div>
        </div>

        <button
          onClick={onReconnectWs}
          className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-mono transition border border-slate-700"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Force Reconnect WebSocket</span>
        </button>
      </div>

      {/* Safety Notice */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 space-y-2">
        <div className="flex items-center space-x-2 text-amber-400 font-semibold">
          <ShieldAlert className="w-4 h-4" />
          <span>Permanent Research Invariants Notice</span>
        </div>
        <p className="leading-relaxed font-mono text-[11px]">
          Even with valid administrator credentials, the bot remains strictly locked to paper trading mode (`PAPER_TRADING_ONLY=true`). No endpoint or user setting can switch the bot to live trading or introduce exchange order endpoints without a separately engineered and audited release.
        </p>
      </div>

    </div>
  );
}
