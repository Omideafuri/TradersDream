import React, { useState, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  Square, 
  AlertOctagon, 
  ShieldCheck, 
  Activity, 
  Wifi, 
  WifiOff,
  Clock
} from 'lucide-react';
import Modal from './Modal';
import { api } from '../utils/api';

export default function TopBar({ botStatus, marketData, wsStatus, onRefresh }) {
  const [currentTime, setCurrentTime] = useState('');
  const [stopModalOpen, setStopModalOpen] = useState(false);
  const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toUTCString().replace('GMT', 'UTC'));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await api.startBot();
      onRefresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handlePause = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await api.pauseBot();
      onRefresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await api.resumeBot();
      onRefresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmStop = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await api.stopBot();
      setStopModalOpen(false);
      onRefresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmEmergency = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await api.emergencyStop();
      setEmergencyModalOpen(false);
      onRefresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const statusState = botStatus?.state || 'UNKNOWN';

  const stateColors = {
    RUNNING: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    PAUSED: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    STOPPED: 'bg-slate-500/10 text-slate-400 border-slate-600/30',
    ERROR: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  }[statusState] || 'bg-slate-500/10 text-slate-400 border-slate-600/30';

  const btcPrice = marketData?.latest_candle?.close || 0;
  const priceChange = marketData?.metrics_summary?.price_change_24h || 0;

  return (
    <>
      <header className="sticky top-0 z-40 bg-[#0b101b]/95 backdrop-blur-md border-b border-slate-800/80 px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          
          {/* Left section: Safety Invariants & Status Badges */}
          <div className="flex items-center space-x-2.5">
            {/* Paper Trading Invariant Badge */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-cyan-950/40 text-cyan-300 border border-cyan-700/50 rounded-md text-xs font-semibold tracking-wide shadow-sm shadow-cyan-950">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
              <span>PAPER TRADING ONLY</span>
            </div>

            {/* Bot State Badge */}
            <div className={`flex items-center space-x-1.5 px-2.5 py-1 border rounded-md text-xs font-semibold font-mono tracking-wider ${stateColors}`}>
              <span className={`w-2 h-2 rounded-full ${statusState === 'RUNNING' ? 'bg-emerald-400 animate-pulse' : statusState === 'PAUSED' ? 'bg-amber-400' : 'bg-slate-400'}`} />
              <span>{statusState}</span>
            </div>

            {/* WebSocket Stream Badge */}
            <div className="flex items-center space-x-1 px-2 py-1 text-[11px] font-mono rounded bg-slate-900/60 border border-slate-800 text-slate-400">
              {wsStatus === 'CONNECTED' ? (
                <>
                  <Wifi className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400">LIVE</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3 h-3 text-rose-400" />
                  <span className="text-rose-400">{wsStatus}</span>
                </>
              )}
            </div>
          </div>

          {/* Center section: Live Price Ticker */}
          <div className="hidden lg:flex items-center space-x-4 px-3 py-1 rounded-md bg-slate-900/70 border border-slate-800/70">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-slate-400">BTC/USDT</span>
              <span className="text-sm font-bold font-mono-numbers text-slate-100">
                ${btcPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className={`text-xs font-mono font-medium ${priceChange >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {priceChange >= 0 ? `+${priceChange.toFixed(2)}%` : `${priceChange.toFixed(2)}%`}
            </div>
          </div>

          {/* Right section: UTC Clock & Controls */}
          <div className="flex items-center space-x-3">
            <div className="hidden sm:flex items-center space-x-1.5 text-xs font-mono text-slate-400 px-2 py-1 bg-slate-900/40 rounded border border-slate-800/50">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              <span>{currentTime}</span>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center space-x-2">
              {statusState === 'STOPPED' || statusState === 'ERROR' ? (
                <button
                  onClick={handleStart}
                  disabled={actionLoading}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-md shadow-md shadow-emerald-950/50 transition disabled:opacity-50"
                  title="Start paper trading cycle"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>START</span>
                </button>
              ) : null}

              {statusState === 'RUNNING' ? (
                <button
                  onClick={handlePause}
                  disabled={actionLoading}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-md shadow-md shadow-amber-950/50 transition disabled:opacity-50"
                  title="Pause signal evaluations and paper trade execution"
                >
                  <Pause className="w-3.5 h-3.5 fill-current" />
                  <span>PAUSE</span>
                </button>
              ) : null}

              {statusState === 'PAUSED' ? (
                <button
                  onClick={handleResume}
                  disabled={actionLoading}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold rounded-md shadow-md shadow-cyan-950/50 transition disabled:opacity-50"
                  title="Resume paper trading cycle"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>RESUME</span>
                </button>
              ) : null}

              {statusState === 'RUNNING' || statusState === 'PAUSED' ? (
                <button
                  onClick={() => setStopModalOpen(true)}
                  disabled={actionLoading}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-semibold rounded-md border border-slate-600 transition disabled:opacity-50"
                  title="Gracefully stop bot loop (preserves open paper position)"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>STOP</span>
                </button>
              ) : null}

              {/* Emergency Stop Button (Always visible when active) */}
              {(statusState === 'RUNNING' || statusState === 'PAUSED') && (
                <button
                  onClick={() => setEmergencyModalOpen(true)}
                  disabled={actionLoading}
                  className="flex items-center space-x-1.5 px-3 py-1.5 bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold rounded-md shadow-md shadow-rose-950/80 border border-rose-500 transition animate-pulse"
                  title="Emergency Stop: Liquidates open paper positions immediately and halts bot"
                >
                  <AlertOctagon className="w-3.5 h-3.5" />
                  <span>EMERGENCY STOP</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {actionError && (
          <div className="mt-2 text-xs text-rose-400 bg-rose-950/50 border border-rose-800/50 px-3 py-1 rounded">
            Action failed: {actionError}
          </div>
        )}
      </header>

      {/* Stop Confirmation Modal */}
      <Modal
        isOpen={stopModalOpen}
        onClose={() => setStopModalOpen(false)}
        onConfirm={handleConfirmStop}
        title="Stop Paper Trading Bot?"
        confirmText="Confirm Stop"
        confirmVariant="warning"
        isProcessing={actionLoading}
      >
        <p className="mb-2">Are you sure you want to stop the bot?</p>
        <ul className="list-disc pl-5 space-y-1 text-slate-400 text-xs">
          <li>The live iteration loop will terminate gracefully.</li>
          <li>Any existing open paper position will remain active in the paper broker.</li>
          <li>You can restart the bot at any time.</li>
        </ul>
      </Modal>

      {/* Emergency Stop Confirmation Modal */}
      <Modal
        isOpen={emergencyModalOpen}
        onClose={() => setEmergencyModalOpen(false)}
        onConfirm={handleConfirmEmergency}
        title="EMERGENCY STOP CONFIRMATION"
        confirmText="LIQUIDATE & HALT BOT"
        confirmVariant="danger"
        isProcessing={actionLoading}
      >
        <div className="space-y-2">
          <p className="font-semibold text-rose-300">
            WARNING: This triggers an immediate, unhedged paper position liquidation!
          </p>
          <ul className="list-disc pl-5 space-y-1 text-slate-400 text-xs">
            <li>Any open BTC paper position will be liquidated at the current market price.</li>
            <li>The bot execution loop will be terminated immediately.</li>
            <li>This action is logged as a critical audit event with operator timestamp.</li>
          </ul>
        </div>
      </Modal>
    </>
  );
}
