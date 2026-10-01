import React, { useState, useEffect, useRef, useCallback } from 'react';
import TopBar from './components/TopBar';
import Sidebar from './components/Sidebar';
import OverviewView from './views/OverviewView';
import MarketsView from './views/MarketsView';
import SignalsView from './views/SignalsView';
import PositionsView from './views/PositionsView';
import TradesView from './views/TradesView';
import ResearchView from './views/ResearchView';
import StrategyView from './views/StrategyView';
import LogsView from './views/LogsView';
import SystemView from './views/SystemView';
import SettingsView from './views/SettingsView';
import { api, WSClient } from './utils/api';

export default function App() {
  const [currentTab, setCurrentTab] = useState('overview');
  const [wsStatus, setWsStatus] = useState('CONNECTING');

  // Core Data States
  const [botStatus, setBotStatus] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [signalData, setSignalData] = useState(null);
  const [positionData, setPositionData] = useState(null);
  const [tradeData, setTradeData] = useState(null);
  const [strategyConfig, setStrategyConfig] = useState(null);
  const [researchData, setResearchData] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [logs, setLogs] = useState([]);

  const wsClientRef = useRef(null);

  // Initial Data Fetch
  const fetchAllData = useCallback(async () => {
    try {
      const [
        statusRes,
        marketRes,
        signalRes,
        posRes,
        tradeRes,
        stratRes,
        resRes,
        healthRes,
        logsRes
      ] = await Promise.allSettled([
        api.getStatus(),
        api.getMarket(),
        api.getSignals(),
        api.getPositions(),
        api.getTrades(),
        api.getStrategy(),
        api.getResearch(),
        api.getHealth(),
        api.getLogs(100),
      ]);

      if (statusRes.status === 'fulfilled') setBotStatus(statusRes.value);
      if (marketRes.status === 'fulfilled') setMarketData(marketRes.value);
      if (signalRes.status === 'fulfilled') setSignalData(signalRes.value);
      if (posRes.status === 'fulfilled') setPositionData(posRes.value);
      if (tradeRes.status === 'fulfilled') setTradeData(tradeRes.value);
      if (stratRes.status === 'fulfilled') setStrategyConfig(stratRes.value);
      if (resRes.status === 'fulfilled') setResearchData(resRes.value);
      if (healthRes.status === 'fulfilled') setHealthData(healthRes.value);
      if (logsRes.status === 'fulfilled') setLogs(logsRes.value);
    } catch (err) {
      console.error('Error fetching initial data:', err);
    }
  }, []);

  // WebSocket Message Handler
  const handleWsMessage = useCallback((msg) => {
    if (!msg || !msg.type) return;

    switch (msg.type) {
      case 'initial':
        if (msg.status) setBotStatus(msg.status);
        if (msg.market) setMarketData(msg.market);
        if (msg.signals) setSignalData(msg.signals);
        if (msg.positions) setPositionData(msg.positions);
        if (msg.trades) setTradeData(msg.trades);
        break;

      case 'tick':
        if (msg.status) setBotStatus(msg.status);
        if (msg.market) setMarketData(msg.market);
        if (msg.signal) setSignalData(prev => ({ ...prev, latest_signal: msg.signal }));
        if (msg.position) setPositionData(prev => ({ ...prev, open_position: msg.position }));
        break;

      case 'signal':
        if (msg.data) {
          setSignalData(prev => ({
            ...prev,
            latest_signal: msg.data,
            history: [...(prev?.history || []), msg.data].slice(-50),
          }));
        }
        break;

      case 'trade':
        if (msg.data) {
          setTradeData(prev => ({
            ...prev,
            trades: [...(prev?.trades || []), msg.data],
          }));
        }
        break;

      case 'log':
        if (msg.data) {
          setLogs(prev => [...prev, msg.data].slice(-300));
        }
        break;

      default:
        break;
    }
  }, []);

  // Connect WebSocket
  useEffect(() => {
    fetchAllData();

    const client = new WSClient(handleWsMessage, (status) => setWsStatus(status));
    client.connect();
    wsClientRef.current = client;

    // Fallback polling every 5s if WS is down
    const pollInterval = setInterval(() => {
      if (wsStatus !== 'CONNECTED') {
        fetchAllData();
      }
    }, 5000);

    return () => {
      clearInterval(pollInterval);
      client.disconnect();
    };
  }, [fetchAllData, handleWsMessage]);

  const handleReconnectWs = () => {
    if (wsClientRef.current) {
      wsClientRef.current.disconnect();
      wsClientRef.current.connect();
    }
  };

  const openPositionsCount = positionData?.open_position ? 1 : 0;

  return (
    <div className="min-h-screen bg-[#080c14] text-slate-200 flex flex-col font-sans">
      {/* Top Header Bar */}
      <TopBar
        botStatus={botStatus}
        marketData={marketData}
        wsStatus={wsStatus}
        onRefresh={fetchAllData}
      />

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          openPositionsCount={openPositionsCount}
        />

        {/* Center Content View Area */}
        <main className="flex-1 p-6 overflow-y-auto bg-gradient-to-b from-[#0a0e1a] to-[#080c14]">
          {currentTab === 'overview' && (
            <OverviewView
              botStatus={botStatus}
              marketData={marketData}
              signalData={signalData}
              positionData={positionData}
              tradeData={tradeData}
              onRefresh={fetchAllData}
              onSelectTab={setCurrentTab}
            />
          )}

          {currentTab === 'markets' && (
            <MarketsView
              marketData={marketData}
              onRefresh={fetchAllData}
            />
          )}

          {currentTab === 'signals' && (
            <SignalsView
              signalData={signalData}
              positionData={positionData}
              marketData={marketData}
            />
          )}

          {currentTab === 'positions' && (
            <PositionsView
              positionData={positionData}
              marketData={marketData}
              onRefresh={fetchAllData}
            />
          )}

          {currentTab === 'trades' && (
            <TradesView
              tradeData={tradeData}
            />
          )}

          {currentTab === 'research' && (
            <ResearchView
              researchData={researchData}
            />
          )}

          {currentTab === 'strategy' && (
            <StrategyView
              strategyConfig={strategyConfig}
            />
          )}

          {currentTab === 'logs' && (
            <LogsView
              logs={logs}
              onRefreshLogs={fetchAllData}
            />
          )}

          {currentTab === 'system' && (
            <SystemView
              healthData={healthData}
              botStatus={botStatus}
            />
          )}

          {currentTab === 'settings' && (
            <SettingsView
              wsStatus={wsStatus}
              onReconnectWs={handleReconnectWs}
            />
          )}
        </main>
      </div>
    </div>
  );
}
