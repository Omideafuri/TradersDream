// API Client and WebSocket Manager for Jevo Trading Dashboard

const API_BASE = '/api';
const TOKEN_KEY = 'jevo_admin_token';
const DEFAULT_TOKEN = 'jevo-admin-insecure-dev-token-change-in-production';

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY) || DEFAULT_TOKEN;
}

export function setStoredToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export async function fetchJson(endpoint, options = {}) {
  const token = getStoredToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'X-API-Key': token } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const data = await response.json();
      errorDetail = data.detail || JSON.stringify(data);
    } catch (_) {}
    throw new Error(`${response.status}: ${errorDetail}`);
  }

  return response.json();
}

export const api = {
  getStatus: () => fetchJson('/status'),
  getMarket: () => fetchJson('/market'),
  getSignals: () => fetchJson('/signals'),
  getPositions: () => fetchJson('/positions'),
  getTrades: () => fetchJson('/trades'),
  getStrategy: () => fetchJson('/strategy'),
  getResearch: () => fetchJson('/research'),
  getLogs: (limit = 100, level) => {
    const q = new URLSearchParams({ limit });
    if (level) q.append('level', level);
    return fetchJson(`/logs?${q.toString()}`);
  },
  getHealth: () => fetchJson('/health'),
  
  // Bot control actions (require X-API-Key)
  startBot: () => fetchJson('/bot/start', { method: 'POST' }),
  pauseBot: () => fetchJson('/bot/pause', { method: 'POST' }),
  resumeBot: () => fetchJson('/bot/resume', { method: 'POST' }),
  stopBot: () => fetchJson('/bot/stop', {
    method: 'POST',
    body: JSON.stringify({ action: 'stop', confirmed: true }),
  }),
  emergencyStop: () => fetchJson('/bot/emergency-stop', {
    method: 'POST',
    body: JSON.stringify({ action: 'emergency_stop', confirmed: true, reason: 'Operator triggered via Dashboard UI' }),
  }),
  closePosition: (symbol = 'BTCUSDT') => fetchJson('/bot/close-position', {
    method: 'POST',
    body: JSON.stringify({ symbol }),
  }),
};

export class WSClient {
  constructor(onMessage, onStatusChange) {
    this.onMessage = onMessage;
    this.onStatusChange = onStatusChange;
    this.ws = null;
    this.reconnectTimer = null;
    this.shouldReconnect = true;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    this.onStatusChange('CONNECTING');

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.onStatusChange('CONNECTED');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this.onMessage(payload);
        } catch (e) {
          console.error('Failed to parse WS message', e);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('WebSocket error:', err);
      };

      this.ws.onclose = () => {
        this.onStatusChange('DISCONNECTED');
        if (this.shouldReconnect) {
          this.reconnectTimer = setTimeout(() => this.connect(), 2500);
        }
      };
    } catch (e) {
      this.onStatusChange('DISCONNECTED');
      if (this.shouldReconnect) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2500);
      }
    }
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) this.ws.close();
  }
}
