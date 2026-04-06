'use client';

import { useState, useEffect, useRef } from 'react';
import { fetchAPI } from '@/lib/api';

interface BotStatus {
  is_running: boolean;
  mode: string;
  tracked_pairs: number;
  open_positions: number;
  positions: any[];
  recent_signals: any[];
}

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export default function BotPage() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [pairs, setPairs] = useState([{ token: 'BTC', long: 'extended', short: 'binance' }]);
  const [mode, setMode] = useState('manual');
  const [loading, setLoading] = useState(false);
  const [tokens, setTokens] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchAPI('/api/historical/tokens')
      .then(res => setTokens(res.tokens || []))
      .catch(() => { });
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  async function loadStatus() {
    try {
      const [statusRes, logsRes] = await Promise.allSettled([
        fetchAPI('/api/bot/command', { method: 'POST', body: JSON.stringify({ action: 'status' }) }),
        fetchAPI('/api/bot/logs?limit=50'),
      ]);
      if (statusRes.status === 'fulfilled') setStatus(statusRes.value);
      if (logsRes.status === 'fulfilled') setLogs(logsRes.value.logs || []);
    } catch (e) { console.error(e); }
  }

  async function startBot() {
    setLoading(true);
    try {
      await fetchAPI('/api/bot/command', {
        method: 'POST',
        body: JSON.stringify({ action: 'start', pairs, config: {} }),
      });
      await loadStatus();
    } catch (e: any) { alert(e.message); }
    setLoading(false);
  }

  async function stopBot() {
    setLoading(true);
    try {
      await fetchAPI('/api/bot/command', {
        method: 'POST',
        body: JSON.stringify({ action: 'stop' }),
      });
      await loadStatus();
    } catch (e: any) { alert(e.message); }
    setLoading(false);
  }

  function addPair() {
    setPairs([...pairs, { token: '', long: '', short: '' }]);
  }

  function removePair(index: number) {
    setPairs(pairs.filter((_, i) => i !== index));
  }

  function updatePair(index: number, field: string, value: string) {
    const updated = [...pairs];
    (updated[index] as any)[field] = value;
    setPairs(updated);
  }

  const inputStyle = {
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8, padding: '8px 12px', color: '#e8e8f0', fontSize: 13, width: 120,
  };

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>🤖 Bot Control</h1>
        <p style={{ fontSize: 14, color: '#8888aa', marginTop: 6 }}>
          Manage automated trading, positions, and rebalancing
        </p>
      </div>

      {/* Status Bar */}
      <div style={{
        display: 'flex', gap: 16, marginBottom: 20, alignItems: 'center',
        background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: '14px 24px',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <div style={{
            width: 12, height: 12, borderRadius: '50%',
            background: status?.is_running ? '#00ff88' : '#ff3366',
            boxShadow: `0 0 12px ${status?.is_running ? 'rgba(0,255,136,0.5)' : 'rgba(255,51,102,0.3)'}`,
            animation: status?.is_running ? 'pulse 2s infinite' : 'none',
          }} />
          <span style={{ fontSize: 14, fontWeight: 600 }}>
            {status?.is_running ? 'Running' : 'Stopped'}
          </span>
        </div>

        <span style={{ color: '#666', fontSize: 13 }}>
          Mode: <strong style={{ color: '#4488ff' }}>{status?.mode || mode}</strong>
        </span>
        <span style={{ color: '#666', fontSize: 13 }}>
          Positions: <strong style={{ color: '#e8e8f0' }}>{status?.open_positions || 0}</strong>
        </span>
        <span style={{ color: '#666', fontSize: 13 }}>
          Pairs: <strong style={{ color: '#e8e8f0' }}>{status?.tracked_pairs || pairs.length}</strong>
        </span>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {!status?.is_running ? (
            <button onClick={startBot} disabled={loading} style={{
              background: 'linear-gradient(135deg, #00ff88, #00cc66)', border: 'none',
              borderRadius: 8, padding: '10px 24px', color: '#000', fontSize: 13,
              fontWeight: 700, cursor: 'pointer',
            }}>
              ▶ Start Bot
            </button>
          ) : (
            <button onClick={stopBot} disabled={loading} style={{
              background: 'linear-gradient(135deg, #ff3366, #cc2244)', border: 'none',
              borderRadius: 8, padding: '10px 24px', color: '#fff', fontSize: 13,
              fontWeight: 700, cursor: 'pointer',
            }}>
              ■ Stop Bot
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Pair Configuration */}
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '20px 24px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Tracked Pairs</h3>
            <button onClick={addPair} style={{
              background: 'rgba(68,136,255,0.1)', border: '1px solid rgba(68,136,255,0.2)',
              borderRadius: 6, padding: '6px 14px', color: '#4488ff', fontSize: 12,
              fontWeight: 600, cursor: 'pointer',
            }}>
              + Add Pair
            </button>
          </div>

          {pairs.map((pair, i) => (
            <div key={i} style={{
              display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8,
              padding: '10px 12px', background: 'rgba(255,255,255,0.02)',
              borderRadius: 8, border: '1px solid rgba(255,255,255,0.04)',
            }}>
              <select
                value={pair.token}
                onChange={e => updatePair(i, 'token', e.target.value)}
                style={inputStyle}
              >
                <option value="">Select Token</option>
                {tokens.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <span style={{ color: '#666', fontSize: 12 }}>Long:</span>
              <select value={pair.long} onChange={e => updatePair(i, 'long', e.target.value)} style={{ ...inputStyle, width: 110 }}>
                {['binance', 'hyperliquid', 'extended', 'paradex'].map(ex => (
                  <option key={ex} value={ex}>{ex}</option>
                ))}
              </select>
              <span style={{ color: '#666', fontSize: 12 }}>Short:</span>
              <select value={pair.short} onChange={e => updatePair(i, 'short', e.target.value)} style={{ ...inputStyle, width: 110 }}>
                {['binance', 'hyperliquid', 'extended', 'paradex'].map(ex => (
                  <option key={ex} value={ex}>{ex}</option>
                ))}
              </select>
              <button onClick={() => removePair(i)} style={{
                background: 'rgba(255,51,102,0.1)', border: 'none', borderRadius: 6,
                padding: '6px 10px', color: '#ff3366', cursor: 'pointer', fontSize: 14,
              }}>×</button>
            </div>
          ))}
        </div>

        {/* Open Positions */}
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '20px 24px',
        }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16, margin: '0 0 16px' }}>Open Positions</h3>
          {status?.positions && status.positions.length > 0 ? (
            status.positions.map((pos: any, i: number) => (
              <div key={i} style={{
                padding: '12px 16px', background: 'rgba(255,255,255,0.02)',
                borderRadius: 8, marginBottom: 8, border: '1px solid rgba(255,255,255,0.04)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{pos.token}</span>
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                    background: pos.status === 'live' ? 'rgba(0,255,136,0.1)' : 'rgba(68,136,255,0.1)',
                    color: pos.status === 'live' ? '#00ff88' : '#4488ff',
                  }}>{pos.status}</span>
                </div>
                <div style={{ fontSize: 12, color: '#8888aa' }}>
                  {pos.long_exchange} ↔ {pos.short_exchange} | ${pos.size_usd?.toLocaleString()} | Signal: {pos.signal}
                </div>
              </div>
            ))
          ) : (
            <div style={{ padding: 30, textAlign: 'center', color: '#666', fontSize: 13 }}>
              No open positions
            </div>
          )}
        </div>
      </div>

      {/* Activity Log */}
      <div style={{
        background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14, marginTop: 20, overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 24px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Activity Log</h3>
        </div>
        <div style={{
          maxHeight: 300, overflowY: 'auto', padding: '12px 16px',
          fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
        }}>
          {logs.length === 0 ? (
            <div style={{ color: '#666', textAlign: 'center', padding: 20 }}>No logs yet</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} style={{
                padding: '4px 8px', borderRadius: 4, marginBottom: 2,
                color: log.level === 'error' ? '#ff3366' : log.level === 'warning' ? '#ffcc00' : '#8888aa',
              }}>
                <span style={{ color: '#444' }}>{log.timestamp?.slice(11, 19)}</span>{' '}
                <span style={{ fontWeight: 600 }}>[{log.level.toUpperCase()}]</span>{' '}
                {log.message}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
