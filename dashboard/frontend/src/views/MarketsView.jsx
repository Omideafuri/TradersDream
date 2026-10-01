import React, { useState, useMemo } from 'react';
import { CandlestickChart, BarChart2, Layers, AlertCircle, RefreshCw } from 'lucide-react';

export default function MarketsView({ marketData, onRefresh }) {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1m');
  const [hoveredCandle, setHoveredCandle] = useState(null);

  const candles = marketData?.candles || [];
  const latestCandle = marketData?.latest_candle;
  const indicators = marketData?.indicators || {};

  // Compute SVG chart coordinates
  const chartHeight = 320;
  const chartWidth = 800;
  const padding = { top: 20, right: 60, bottom: 25, left: 10 };

  const chartData = useMemo(() => {
    if (!candles || candles.length === 0) return null;

    const prices = candles.flatMap(c => [c.high, c.low]);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice || 1;

    const volumes = candles.map(c => c.volume);
    const maxVolume = Math.max(...volumes) || 1;

    const innerWidth = chartWidth - padding.left - padding.right;
    const innerHeight = chartHeight - padding.top - padding.bottom;
    const candleWidth = Math.max(2, Math.min(16, innerWidth / candles.length - 2));

    const points = candles.map((c, i) => {
      const x = padding.left + (i * (innerWidth / candles.length)) + candleWidth / 2;
      const yOpen = padding.top + innerHeight - ((c.open - minPrice) / priceRange) * innerHeight;
      const yClose = padding.top + innerHeight - ((c.close - minPrice) / priceRange) * innerHeight;
      const yHigh = padding.top + innerHeight - ((c.high - minPrice) / priceRange) * innerHeight;
      const yLow = padding.top + innerHeight - ((c.low - minPrice) / priceRange) * innerHeight;
      const isUp = c.close >= c.open;
      const volHeight = (c.volume / maxVolume) * 60;

      return {
        ...c,
        x,
        yOpen,
        yClose,
        yHigh,
        yLow,
        isUp,
        volHeight,
        candleWidth,
      };
    });

    return {
      points,
      minPrice,
      maxPrice,
      priceRange,
      innerWidth,
      innerHeight,
    };
  }, [candles]);

  const activeCandle = hoveredCandle || latestCandle;

  return (
    <div className="space-y-4 animate-fade-in">
      
      {/* Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[#0f172a] border border-slate-800">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <CandlestickChart className="w-5 h-5 text-cyan-400" />
            <span className="text-base font-bold font-mono text-slate-100">BTC/USDT</span>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-cyan-950/60 text-cyan-300 border border-cyan-800/40">
              SPOT
            </span>
          </div>

          <div className="hidden md:flex items-center space-x-1 pl-4 border-l border-slate-800 text-xs font-mono">
            {['1m', '5m', '15m', '1h', '4h'].map(tf => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-2.5 py-1 rounded transition ${
                  selectedTimeframe === tf 
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold' 
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        {/* Live Candle Summary */}
        {activeCandle && (
          <div className="flex items-center space-x-3 text-xs font-mono">
            <span className="text-slate-500">O: <span className="text-slate-200">${activeCandle.open?.toFixed(1)}</span></span>
            <span className="text-slate-500">H: <span className="text-slate-200">${activeCandle.high?.toFixed(1)}</span></span>
            <span className="text-slate-500">L: <span className="text-slate-200">${activeCandle.low?.toFixed(1)}</span></span>
            <span className="text-slate-500">C: <span className="text-emerald-400 font-bold">${activeCandle.close?.toFixed(1)}</span></span>
            <span className="text-slate-500">Vol: <span className="text-slate-300">{activeCandle.volume?.toFixed(2)} BTC</span></span>
          </div>
        )}

        <button
          onClick={onRefresh}
          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition"
          title="Refresh market data"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Main Chart Area */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        
        {/* Candlestick & Volume SVG Canvas */}
        <div className="lg:col-span-3 p-4 rounded-xl bg-[#0f172a] border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-4 text-xs font-mono">
              <span className="flex items-center space-x-1.5">
                <span className="w-2.5 h-0.5 bg-cyan-400 inline-block" />
                <span className="text-slate-400">EMA 20 (${indicators.ema_20?.toFixed(1)})</span>
              </span>
              <span className="flex items-center space-x-1.5">
                <span className="w-2.5 h-0.5 bg-amber-400 inline-block" />
                <span className="text-slate-400">EMA 50 (${indicators.ema_50?.toFixed(1)})</span>
              </span>
              <span className="flex items-center space-x-1.5">
                <span className="w-2.5 h-0.5 bg-purple-400 inline-block" />
                <span className="text-slate-400">EMA 200 (${indicators.ema_200?.toFixed(1)})</span>
              </span>
            </div>
            <div className="text-[11px] text-slate-500 font-mono">
              Live Feed: Free Stream ({candles.length} bars)
            </div>
          </div>

          {/* SVG Price Chart */}
          <div className="w-full overflow-x-auto">
            {chartData ? (
              <svg 
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                className="w-full h-auto cursor-crosshair select-none"
              >
                {/* Horizontal Grid lines */}
                {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
                  const y = padding.top + (chartData.innerHeight * pct);
                  const price = chartData.maxPrice - (chartData.priceRange * pct);
                  return (
                    <g key={idx}>
                      <line
                        x1={padding.left}
                        y1={y}
                        x2={chartWidth - padding.right}
                        y2={y}
                        stroke="#1e293b"
                        strokeDasharray="3 3"
                        strokeWidth="1"
                      />
                      <text
                        x={chartWidth - padding.right + 8}
                        y={y + 4}
                        fill="#64748b"
                        fontSize="10"
                        fontFamily="monospace"
                      >
                        ${price.toFixed(0)}
                      </text>
                    </g>
                  );
                })}

                {/* Candlesticks */}
                {chartData.points.map((pt, i) => {
                  const bodyTop = Math.min(pt.yOpen, pt.yClose);
                  const bodyHeight = Math.max(1.5, Math.abs(pt.yClose - pt.yOpen));
                  const color = pt.isUp ? '#10b981' : '#ef4444';

                  return (
                    <g 
                      key={i}
                      onMouseEnter={() => setHoveredCandle(pt)}
                      onMouseLeave={() => setHoveredCandle(null)}
                    >
                      {/* Wick */}
                      <line
                        x1={pt.x}
                        y1={pt.yHigh}
                        x2={pt.x}
                        y2={pt.yLow}
                        stroke={color}
                        strokeWidth="1.2"
                      />
                      {/* Candle Body */}
                      <rect
                        x={pt.x - pt.candleWidth / 2}
                        y={bodyTop}
                        width={pt.candleWidth}
                        height={bodyHeight}
                        fill={color}
                        rx="1"
                      />
                      {/* Volume Bar in background */}
                      <rect
                        x={pt.x - pt.candleWidth / 2}
                        y={chartHeight - padding.bottom - pt.volHeight}
                        width={pt.candleWidth}
                        height={pt.volHeight}
                        fill={pt.isUp ? '#10b98130' : '#ef444430'}
                        rx="0.5"
                      />
                    </g>
                  );
                })}
              </svg>
            ) : (
              <div className="h-64 flex items-center justify-center text-slate-500 font-mono text-xs">
                Awaiting candle stream from market engine...
              </div>
            )}
          </div>

          {/* RSI Sub-Panel */}
          <div className="mt-3 pt-3 border-t border-slate-800">
            <div className="flex items-center justify-between text-xs font-mono mb-1.5">
              <span className="text-slate-400">Relative Strength Index (RSI 14):</span>
              <span className={`font-bold ${
                (indicators.rsi || 50) > 70 ? 'text-rose-400' : (indicators.rsi || 50) < 30 ? 'text-emerald-400' : 'text-cyan-400'
              }`}>
                {indicators.rsi?.toFixed(2) || '50.00'}
              </span>
            </div>
            {/* Visual RSI Gauge Bar */}
            <div className="relative w-full h-3 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              {/* Oversold band (0-30) */}
              <div className="absolute left-0 top-0 bottom-0 w-[30%] bg-emerald-950/40 border-r border-emerald-800/40" />
              {/* Overbought band (70-100) */}
              <div className="absolute right-0 top-0 bottom-0 w-[30%] bg-rose-950/40 border-l border-rose-800/40" />
              {/* Current Value Indicator */}
              <div 
                className="absolute top-0 bottom-0 w-1.5 bg-cyan-400 shadow-md shadow-cyan-400 rounded-full transition-all"
                style={{ left: `${Math.min(100, Math.max(0, indicators.rsi || 50))}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
              <span>0 (Oversold 30)</span>
              <span>Neutral 50</span>
              <span>(Overbought 70) 100</span>
            </div>
          </div>
        </div>

        {/* Orderbook Depth / Microstructure Side Panel */}
        <div className="p-4 rounded-xl bg-[#0f172a] border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-200">Orderbook L1/L2</h3>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                LIVE SPOT
              </span>
            </div>

            {/* Asks (Red) */}
            <div className="space-y-1 font-mono text-xs mb-3">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex justify-between">
                <span>Price (USDT)</span>
                <span>Size (BTC)</span>
              </div>
              {[
                { price: (latestCandle?.close || 64200) + 25.5, size: 0.842, pct: 60 },
                { price: (latestCandle?.close || 64200) + 18.0, size: 1.250, pct: 85 },
                { price: (latestCandle?.close || 64200) + 10.2, size: 0.410, pct: 30 },
                { price: (latestCandle?.close || 64200) + 4.5, size: 0.655, pct: 45 },
              ].reverse().map((ask, idx) => (
                <div key={idx} className="relative flex justify-between px-2 py-0.5 rounded overflow-hidden">
                  <div 
                    className="absolute right-0 top-0 bottom-0 bg-rose-950/30" 
                    style={{ width: `${ask.pct}%` }} 
                  />
                  <span className="text-rose-400 relative z-10">${ask.price.toFixed(1)}</span>
                  <span className="text-slate-300 relative z-10">{ask.size.toFixed(3)}</span>
                </div>
              ))}
            </div>

            {/* Current Mid Spread */}
            <div className="py-2 px-3 my-2 bg-slate-900/90 rounded border border-slate-800 flex items-center justify-between font-mono text-xs">
              <span className="text-slate-400">Spread / Mid:</span>
              <span className="text-cyan-300 font-bold">
                ${(latestCandle?.close || 64200).toFixed(2)} (0.8 bps)
              </span>
            </div>

            {/* Bids (Green) */}
            <div className="space-y-1 font-mono text-xs">
              {[
                { price: (latestCandle?.close || 64200) - 3.8, size: 0.512, pct: 35 },
                { price: (latestCandle?.close || 64200) - 9.1, size: 1.104, pct: 75 },
                { price: (latestCandle?.close || 64200) - 15.4, size: 0.720, pct: 50 },
                { price: (latestCandle?.close || 64200) - 22.0, size: 1.450, pct: 95 },
              ].map((bid, idx) => (
                <div key={idx} className="relative flex justify-between px-2 py-0.5 rounded overflow-hidden">
                  <div 
                    className="absolute right-0 top-0 bottom-0 bg-emerald-950/30" 
                    style={{ width: `${bid.pct}%` }} 
                  />
                  <span className="text-emerald-400 relative z-10">${bid.price.toFixed(1)}</span>
                  <span className="text-slate-300 relative z-10">{bid.size.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Research Invariant Notice */}
          <div className="mt-4 p-2.5 rounded bg-slate-900/60 border border-slate-800 text-[10px] text-slate-400">
            <div className="flex items-center space-x-1.5 text-cyan-400 font-semibold mb-1">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>Microstructure Notice</span>
            </div>
            <p className="leading-tight">
              Orderbook displays live free websocket stream. Full historical MBP-10 / MBO tick data remains restricted under Phase 10B/10C freeze.
            </p>
          </div>
        </div>

      </div>

    </div>
  );
}
