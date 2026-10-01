import React from 'react';
import { 
  LayoutDashboard, 
  CandlestickChart, 
  Cpu, 
  Layers, 
  History, 
  Microscope, 
  Sliders, 
  Terminal, 
  Server, 
  Settings as SettingsIcon,
  ShieldAlert
} from 'lucide-react';

export default function Sidebar({ currentTab, onSelectTab, openPositionsCount = 0 }) {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'markets', label: 'Markets & Chart', icon: CandlestickChart },
    { id: 'signals', label: 'Signals & AI', icon: Cpu },
    { id: 'positions', label: 'Positions', icon: Layers, badge: openPositionsCount > 0 ? openPositionsCount : null },
    { id: 'trades', label: 'Trade History', icon: History },
    { id: 'research', label: 'Research & Edge', icon: Microscope },
    { id: 'strategy', label: 'Strategy Config', icon: Sliders },
    { id: 'logs', label: 'System Logs', icon: Terminal },
    { id: 'system', label: 'Health & System', icon: Server },
    { id: 'settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <aside className="w-64 bg-[#0a0e1a] border-r border-slate-800/80 flex flex-col h-[calc(100vh-57px)] select-none">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800/60">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-blue-700 flex items-center justify-center shadow-lg shadow-cyan-900/30">
            <span className="font-mono font-bold text-white text-base">J</span>
          </div>
          <div>
            <div className="text-sm font-bold text-slate-100 tracking-wider font-mono">JEVO COCKPIT</div>
            <div className="text-[10px] text-cyan-400 font-mono tracking-tight flex items-center space-x-1">
              <span>RESEARCH PAPER BOT</span>
              <span>•</span>
              <span>v10B.6</span>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shadow-sm shadow-cyan-950 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
              }`}
            >
              <div className="flex items-center space-x-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== null && item.badge !== undefined && (
                <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Invariants Reminder */}
      <div className="p-3 border-t border-slate-800/60 bg-[#080c14]">
        <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px] text-slate-400">
          <div className="flex items-center space-x-1.5 text-amber-400 font-medium mb-1">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span className="font-mono text-[10px] uppercase">Safety Guarantee</span>
          </div>
          <div className="text-[10px] text-slate-400 leading-tight space-y-0.5">
            <div>• Real Execution: <span className="text-slate-200 font-semibold">BLOCKED</span></div>
            <div>• Real Leverage: <span className="text-slate-200 font-semibold">1.0x (Spot only)</span></div>
            <div>• External Wallets: <span className="text-slate-200 font-semibold">0</span></div>
          </div>
        </div>
      </div>
    </aside>
  );
}
