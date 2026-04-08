'use client';

import { useState, useEffect, useRef } from 'react';
import { fetchAPI, isAuthenticated, getUsername, logout } from '@/lib/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend
} from 'recharts';

interface BotStatus {
  is_running: boolean;
  mode: string;
  tracked_pairs: number;
  open_positions: number;
  cumulative_pnl: number;
  positions: any[];
  recent_signals: any[];
}

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export default function BotPage() {
  const [authed, setAuthed] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [activeSection, setActiveSection] = useState<'control' | 'credentials' | 'history'>('control');

  const [status, setStatus] = useState<BotStatus | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [performance, setPerformance] = useState<any>(null);
  const [pairs, setPairs] = useState([{ token: 'BTC', long: 'extended', short: 'binance' }]);
  const [loading, setLoading] = useState(false);
  const [tokens, setTokens] = useState<string[]>([]);
  const [botMode, setBotMode] = useState<'manual' | 'auto'>('manual');
  const [autoPairs, setAutoPairs] = useState<any[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Credentials state
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [savedCreds, setSavedCreds] = useState<any>(null);
  const [credsSaving, setCredsSaving] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setAuthed(isAuthenticated());
    }
  }, []);

  useEffect(() => {
    if (authed) {
      fetchAPI('/api/historical/tokens')
        .then(res => setTokens(res.tokens || []))
        .catch(() => {});
      loadStatus();
      loadCredentials();
      const interval = setInterval(loadStatus, 8000);
      return () => clearInterval(interval);
    }
  }, [authed]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetchAPI('/api/bot/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      sessionStorage.setItem('bot_token', res.token);
      sessionStorage.setItem('bot_user', res.username);
      setAuthed(true);
      setPassword('');
    } catch (err: any) {
      setAuthError('Invalid credentials');
    }
  }

  function handleLogout() {
    logout();
    setAuthed(false);
    setStatus(null);
    setPerformance(null);
  }

  async function loadStatus() {
    try {
      const [statusRes, logsRes, histRes] = await Promise.allSettled([
        fetchAPI('/api/bot/command', { method: 'POST', body: JSON.stringify({ action: 'status' }) }),
        fetchAPI('/api/bot/logs?limit=80'),
        fetchAPI('/api/bot/history'),
      ]);
      if (statusRes.status === 'fulfilled') {
        setStatus(statusRes.value);
        if (statusRes.value.mode) setBotMode(statusRes.value.mode);
      }
      if (logsRes.status === 'fulfilled') setLogs(logsRes.value.logs || []);
      if (histRes.status === 'fulfilled') setPerformance(histRes.value.performance || null);
    } catch (e: any) {
      if (e.message === 'AUTH_REQUIRED') handleLogout();
    }
  }

  async function loadCredentials() {
    try {
      const res = await fetchAPI('/api/bot/credentials');
      setSavedCreds(res.credentials || {});
    } catch (e) {}
  }

  async function saveCredentials() {
    setCredsSaving(true);
    try {
      const filtered = Object.fromEntries(Object.entries(credentials).filter(([, v]) => v && v.trim()));
      await fetchAPI('/api/bot/credentials', {
        method: 'POST',
        body: JSON.stringify(filtered),
      });
      await loadCredentials();
      setCredentials({});
      alert('Credentials saved');
    } catch (e: any) { alert(e.message); }
    setCredsSaving(false);
  }

  async function toggleMode(newMode: 'manual' | 'auto') {
    try {
      await fetchAPI('/api/bot/mode', {
        method: 'POST',
        body: JSON.stringify({ mode: newMode }),
      });
      setBotMode(newMode);

      if (newMode === 'auto') {
        // Fetch recommended pairs
        const res = await fetchAPI('/api/bot/auto-pairs');
        if (res.pairs && res.pairs.length > 0) {
          setAutoPairs(res.pairs);
          setPairs(res.pairs.map((p: any) => ({ token: p.token, long: p.long, short: p.short })));
        }
      }
    } catch (e: any) { console.error(e); }
  }

  async function startBot() {
    setLoading(true);
    try {
      await fetchAPI('/api/bot/command', {
        method: 'POST',
        body: JSON.stringify({ action: 'start', pairs, config: {} }),
      });
      // Delay reload to let simulation generate
      setTimeout(() => loadStatus(), 1000);
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
      // Reload — server keeps history, positions are closed
      setTimeout(() => loadStatus(), 500);
    } catch (e: any) { alert(e.message); }
    setLoading(false);
  }

  function addPair() { setPairs([...pairs, { token: '', long: '', short: '' }]); }
  function removePair(index: number) { setPairs(pairs.filter((_, i) => i !== index)); }
  function updatePair(index: number, field: string, value: string) {
    const updated = [...pairs];
    (updated[index] as any)[field] = value;
    setPairs(updated);
  }

  const inputStyle = {
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8, padding: '8px 12px', color: '#e8e8f0', fontSize: 13, width: 120,
  };

  // --- LOGIN SCREEN ---
  if (!authed) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '80vh' }}>
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 16, padding: '40px 48px', width: 400,
          boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
        }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 14, margin: '0 auto 16px',
              background: 'linear-gradient(135deg, #00ff88, #4488ff)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
            }}></div>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0 }}>Bot Access</h1>
            <p style={{ fontSize: 13, color: '#666', marginTop: 6 }}>Private access — Contact admin for credentials</p>
          </div>
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 6, textTransform: 'uppercase', fontWeight: 600 }}>Username</label>
              <input type="text" value={username} onChange={e => setUsername(e.target.value)} placeholder="Enter username"
                style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, padding: '12px 16px', color: '#e8e8f0', fontSize: 14, outline: 'none' }} />
            </div>
            <div style={{ marginBottom: 24 }}>
              <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 6, textTransform: 'uppercase', fontWeight: 600 }}>Password</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter password"
                style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, padding: '12px 16px', color: '#e8e8f0', fontSize: 14, outline: 'none' }} />
            </div>
            {authError && <div style={{ color: '#ff3366', fontSize: 13, marginBottom: 16, textAlign: 'center' }}>{authError}</div>}
            <button type="submit" style={{
              width: '100%', background: 'linear-gradient(135deg, #00ff88, #00cc66)', border: 'none',
              borderRadius: 10, padding: '14px', color: '#000', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            }}>Sign In</button>
          </form>
        </div>
      </div>
    );
  }

  // --- MAIN BOT INTERFACE ---
  const isRunning = status?.is_running || false;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>Bot Control</h1>
          <p style={{ fontSize: 14, color: '#8888aa', marginTop: 6 }}>
            {getUsername() && <span>Connected as <strong style={{ color: '#00ff88' }}>{getUsername()}</strong> — </span>}
            Manage trading, positions, and supervision
          </p>
        </div>
        <button onClick={handleLogout} style={{
          background: 'rgba(255,51,102,0.1)', border: '1px solid rgba(255,51,102,0.2)',
          borderRadius: 8, padding: '8px 16px', color: '#ff3366', fontSize: 12, fontWeight: 600, cursor: 'pointer',
        }}>Logout</button>
      </div>

      {/* Section Tabs */}
      <div style={{
        display: 'flex', gap: 4, marginBottom: 20, background: '#1a1a2e',
        borderRadius: 12, padding: 4, border: '1px solid rgba(255,255,255,0.06)', width: 'fit-content',
      }}>
        {(['control', 'credentials', 'history'] as const).map(t => (
          <button key={t} onClick={() => setActiveSection(t)} style={{
            padding: '10px 20px', borderRadius: 8, border: 'none', fontSize: 13,
            fontWeight: 600, cursor: 'pointer',
            background: activeSection === t ? 'linear-gradient(135deg, #4488ff, #3366cc)' : 'transparent',
            color: activeSection === t ? '#fff' : '#8888aa',
          }}>
            {t === 'control' ? 'Control' : t === 'credentials' ? 'API Keys' : 'History'}
          </button>
        ))}
      </div>

      {/* === CONTROL SECTION === */}
      {activeSection === 'control' && (
        <>
          {/* Status Bar + Mode Toggle */}
          <div style={{
            display: 'flex', gap: 16, marginBottom: 20, alignItems: 'center',
            background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 12, padding: '14px 24px', flexWrap: 'wrap',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 12, height: 12, borderRadius: '50%',
                background: isRunning ? '#00ff88' : '#ff3366',
                boxShadow: `0 0 12px ${isRunning ? 'rgba(0,255,136,0.5)' : 'rgba(255,51,102,0.3)'}`,
                animation: isRunning ? 'pulse 2s infinite' : 'none',
              }} />
              <span style={{ fontSize: 14, fontWeight: 600 }}>{isRunning ? 'Running' : 'Stopped'}</span>
            </div>

            {/* Manual / Auto Toggle */}
            <div style={{
              display: 'flex', borderRadius: 8, overflow: 'hidden',
              border: '1px solid rgba(255,255,255,0.1)',
            }}>
              <button onClick={() => toggleMode('manual')} style={{
                padding: '8px 16px', border: 'none', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                background: botMode === 'manual' ? '#4488ff' : 'rgba(255,255,255,0.03)',
                color: botMode === 'manual' ? '#fff' : '#666',
              }}>Manual</button>
              <button onClick={() => toggleMode('auto')} style={{
                padding: '8px 16px', border: 'none', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                background: botMode === 'auto' ? '#00ff88' : 'rgba(255,255,255,0.03)',
                color: botMode === 'auto' ? '#000' : '#666',
              }}>Auto</button>
            </div>

            <span style={{ color: '#666', fontSize: 13 }}>
              Positions: <strong style={{ color: '#e8e8f0' }}>{status?.open_positions || 0}</strong>
            </span>
            {isRunning && (
              <span style={{ color: '#666', fontSize: 13 }}>
                PnL: <strong style={{ color: (status?.cumulative_pnl || 0) >= 0 ? '#00ff88' : '#ff3366', fontFamily: "'JetBrains Mono'" }}>
                  ${(status?.cumulative_pnl || 0).toLocaleString()}
                </strong>
              </span>
            )}

            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              {!isRunning ? (
                <button onClick={startBot} disabled={loading} style={{
                  background: 'linear-gradient(135deg, #00ff88, #00cc66)', border: 'none',
                  borderRadius: 8, padding: '10px 24px', color: '#000', fontSize: 13,
                  fontWeight: 700, cursor: 'pointer', opacity: loading ? 0.7 : 1,
                }}>Start Bot</button>
              ) : (
                <button onClick={stopBot} disabled={loading} style={{
                  background: 'linear-gradient(135deg, #ff3366, #cc2244)', border: 'none',
                  borderRadius: 8, padding: '10px 24px', color: '#fff', fontSize: 13,
                  fontWeight: 700, cursor: 'pointer', opacity: loading ? 0.7 : 1,
                }}>Stop Bot</button>
              )}
            </div>
          </div>

          {/* Auto Mode Banner */}
          {botMode === 'auto' && autoPairs.length > 0 && (
            <div style={{
              marginBottom: 16, padding: '12px 20px', borderRadius: 10,
              background: 'rgba(0,255,136,0.06)', border: '1px solid rgba(0,255,136,0.15)',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div>
                <div style={{ fontSize: 13, color: '#00ff88', fontWeight: 600 }}>Auto Mode — Top 3 pairs selected by APR</div>
                <div style={{ fontSize: 12, color: '#8888aa', marginTop: 2 }}>
                  {autoPairs.map(p => `${p.token} (${p.apr?.toFixed(0) || '—'}% APR)`).join(' • ')}
                </div>
              </div>
            </div>
          )}

          {/* Mini Equity Curve (visible when running) */}
          {isRunning && performance?.equity_curve && performance.equity_curve.length > 5 && (
            <div style={{
              background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 14, marginBottom: 20, padding: '16px 16px 8px 0', overflow: 'hidden',
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#8888aa', marginBottom: 8, paddingLeft: 20 }}>
                Equity Curve — 60 days
              </div>
              <div style={{ height: 180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={performance.equity_curve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="timestamp" hide />
                    <YAxis stroke="#555" fontSize={10} tickFormatter={(v) => `$${v}`} width={55} />
                    <Tooltip
                      contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: 8, fontSize: 11 }}
                      labelFormatter={(l) => { try { return new Date(l).toLocaleDateString(); } catch { return ''; } }}
                      formatter={(value: any) => [`$${Number(value).toFixed(2)}`, 'PnL']}
                    />
                    <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
                    <Line type="monotone" dataKey="cumulative_pnl" stroke="#00ff88" strokeWidth={1.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {/* Pair Configuration */}
            <div style={{
              background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 14, padding: '20px 24px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>
                  {botMode === 'auto' ? 'Auto-Selected Pairs' : 'Tracked Pairs'}
                </h3>
                {botMode === 'manual' && (
                  <button onClick={addPair} style={{
                    background: 'rgba(68,136,255,0.1)', border: '1px solid rgba(68,136,255,0.2)',
                    borderRadius: 6, padding: '6px 14px', color: '#4488ff', fontSize: 12,
                    fontWeight: 600, cursor: 'pointer',
                  }}>+ Add Pair</button>
                )}
              </div>

              {pairs.map((pair, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8,
                  padding: '10px 12px', background: 'rgba(255,255,255,0.02)',
                  borderRadius: 8, border: '1px solid rgba(255,255,255,0.04)',
                }}>
                  <select disabled={botMode === 'auto'} value={pair.token} onChange={e => updatePair(i, 'token', e.target.value)} style={{ ...inputStyle, opacity: botMode === 'auto' ? 0.7 : 1 }}>
                    <option value="">Token</option>
                    {tokens.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <span style={{ color: '#666', fontSize: 12 }}>L:</span>
                  <select disabled={botMode === 'auto'} value={pair.long} onChange={e => updatePair(i, 'long', e.target.value)} style={{ ...inputStyle, width: 100, opacity: botMode === 'auto' ? 0.7 : 1 }}>
                    {['binance', 'hyperliquid', 'extended', 'paradex'].map(ex => (
                      <option key={ex} value={ex}>{ex}</option>
                    ))}
                  </select>
                  <span style={{ color: '#666', fontSize: 12 }}>S:</span>
                  <select disabled={botMode === 'auto'} value={pair.short} onChange={e => updatePair(i, 'short', e.target.value)} style={{ ...inputStyle, width: 100, opacity: botMode === 'auto' ? 0.7 : 1 }}>
                    {['binance', 'hyperliquid', 'extended', 'paradex'].map(ex => (
                      <option key={ex} value={ex}>{ex}</option>
                    ))}
                  </select>
                  {botMode === 'manual' && (
                    <button onClick={() => removePair(i)} style={{
                      background: 'rgba(255,51,102,0.1)', border: 'none', borderRadius: 6,
                      padding: '6px 10px', color: '#ff3366', cursor: 'pointer', fontSize: 14,
                    }}>×</button>
                  )}
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
                        background: 'rgba(0,255,136,0.1)', color: '#00ff88',
                      }}>{pos.signal === 'ENTER_POS' ? 'LONG' : 'SHORT'}</span>
                    </div>
                    <div style={{ fontSize: 12, color: '#8888aa' }}>
                      {pos.long_exchange} ↔ {pos.short_exchange} | ${pos.size_usd?.toLocaleString()}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#666', marginTop: 6 }}>
                      <span>Since: {pos.opened_at?.slice(0, 16)?.replace('T', ' ')}</span>
                      <span>Z: {pos.entry_zscore || '—'}</span>
                      <span style={{ color: (pos.funding_collected || 0) >= 0 ? '#00ff88' : '#ff3366', fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>
                        ${(pos.funding_collected || 0).toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ padding: 30, textAlign: 'center', color: '#666', fontSize: 13 }}>
                  {isRunning ? 'Loading positions...' : 'Start the bot to see positions'}
                </div>
              )}
            </div>
          </div>

          {/* Activity Log */}
          <div style={{
            background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 14, marginTop: 20, overflow: 'hidden',
          }}>
            <div style={{ padding: '14px 24px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Activity Log</h3>
              <span style={{ fontSize: 11, color: '#555' }}>{logs.length} entries</span>
            </div>
            <div style={{
              maxHeight: 280, overflowY: 'auto', padding: '12px 16px',
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11.5,
            }}>
              {logs.length === 0 ? (
                <div style={{ color: '#666', textAlign: 'center', padding: 20 }}>
                  {isRunning ? 'Loading logs...' : 'No logs — start the bot'}
                </div>
              ) : (
                logs.slice(-60).map((log, i) => (
                  <div key={i} style={{
                    padding: '3px 8px', borderRadius: 4, marginBottom: 1,
                    color: log.level === 'error' ? '#ff3366' : log.level === 'warning' ? '#ffcc00' : '#8888aa',
                    lineHeight: 1.5,
                  }}>
                    <span style={{ color: '#444' }}>{log.timestamp?.slice(5, 16)?.replace('T', ' ')}</span>{' '}
                    {log.message}
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </>
      )}

      {/* === CREDENTIALS SECTION === */}
      {activeSection === 'credentials' && (
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '24px 32px',
        }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>API Keys & Wallets</h2>
          <p style={{ fontSize: 13, color: '#666', marginBottom: 24 }}>Configure your exchange API keys and wallet addresses for live trading.</p>

          {savedCreds && Object.keys(savedCreds).length > 0 && (
            <div style={{ marginBottom: 24, padding: 16, background: 'rgba(0,255,136,0.05)', borderRadius: 10, border: '1px solid rgba(0,255,136,0.1)' }}>
              <div style={{ fontSize: 12, color: '#00ff88', fontWeight: 600, marginBottom: 8 }}>Saved Credentials</div>
              {Object.entries(savedCreds).filter(([k]) => k !== 'updated_at').map(([key, val]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#888', padding: '2px 0' }}>
                  <span>{key}</span>
                  <span style={{ fontFamily: "'JetBrains Mono'", color: '#666' }}>{String(val)}</span>
                </div>
              ))}
              {savedCreds.updated_at && (
                <div style={{ fontSize: 11, color: '#444', marginTop: 8 }}>Last updated: {savedCreds.updated_at?.slice(0, 16)}</div>
              )}
            </div>
          )}

          {[
            { title: 'Binance', fields: [['binance_api_key', 'API Key'], ['binance_api_secret', 'API Secret']] },
            { title: 'Hyperliquid', fields: [['hyperliquid_api_key', 'API Key'], ['hyperliquid_api_secret', 'API Secret'], ['hyperliquid_wallet', 'Wallet Address']] },
            { title: 'Extended (Starknet)', fields: [['extended_api_key', 'API Key'], ['extended_api_secret', 'API Secret'], ['extended_wallet', 'Wallet'], ['extended_private_key', 'Private Key']] },
            { title: 'Paradex', fields: [['paradex_api_key', 'API Key'], ['paradex_api_secret', 'API Secret'], ['paradex_wallet', 'Wallet']] },
          ].map(exchange => (
            <div key={exchange.title} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, color: '#4488ff' }}>{exchange.title}</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
                {exchange.fields.map(([key, label]) => (
                  <div key={key}>
                    <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>{label}</label>
                    <input type="password" value={credentials[key] || ''} onChange={e => setCredentials({ ...credentials, [key]: e.target.value })} placeholder={`Enter ${label}`}
                      style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '10px 14px', color: '#e8e8f0', fontSize: 13 }} />
                  </div>
                ))}
              </div>
            </div>
          ))}

          <button onClick={saveCredentials} disabled={credsSaving} style={{
            background: 'linear-gradient(135deg, #00ff88, #00cc66)', border: 'none',
            borderRadius: 10, padding: '14px 32px', color: '#000', fontSize: 14,
            fontWeight: 700, cursor: 'pointer', opacity: credsSaving ? 0.7 : 1,
          }}>{credsSaving ? 'Saving...' : 'Save Credentials'}</button>
        </div>
      )}

      {/* === HISTORY SECTION === */}
      {activeSection === 'history' && (
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '24px',
        }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Bot Historical Performance</h2>

          {!isRunning && (!performance || !performance.equity_curve || performance.equity_curve.length === 0) ? (
            <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>
              <div style={{ fontSize: 40, marginBottom: 16 }}></div>
              <div style={{ fontSize: 15 }}>No performance data</div>
              <div style={{ fontSize: 13, marginTop: 8, color: '#555' }}>Start the bot to generate historical simulation and track live performance.</div>
            </div>
          ) : (
            <>
              {/* KPIs */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
                {(() => {
                  const trades = performance?.recent_trades || [];
                  const winners = trades.filter((t: any) => (t.funding_collected || 0) > 0);
                  const winRate = trades.length > 0 ? Math.round(winners.length / trades.length * 100) : 0;
                  const avgPnl = trades.length > 0 ? trades.reduce((s: number, t: any) => s + (t.funding_collected || 0), 0) / trades.length : 0;
                  return [
                    { label: 'Realized PnL', value: `$${(performance?.realized_pnl || 0).toLocaleString()}`, color: (performance?.realized_pnl || 0) >= 0 ? '#00ff88' : '#ff3366' },
                    { label: 'Closed Trades', value: performance?.total_closed_trades || 0, color: '#4488ff' },
                    { label: 'Win Rate', value: `${winRate}%`, color: winRate >= 50 ? '#00ff88' : '#ff3366' },
                    { label: 'Avg PnL/Trade', value: `$${avgPnl.toFixed(1)}`, color: avgPnl >= 0 ? '#00ff88' : '#ff3366' },
                    { label: 'Status', value: isRunning ? 'Active' : 'Inactive', color: isRunning ? '#00ff88' : '#ff3366' },
                  ].map((m, i) => (
                    <div key={i} style={{ background: 'rgba(255,255,255,0.02)', padding: 14, borderRadius: 10, border: '1px solid rgba(255,255,255,0.04)' }}>
                      <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', fontWeight: 600 }}>{m.label}</div>
                      <div style={{ fontSize: 20, fontWeight: 800, color: m.color, fontFamily: "'JetBrains Mono'", marginTop: 4 }}>{m.value}</div>
                    </div>
                  ));
                })()}
              </div>

              {/* Equity Curve */}
              {performance?.equity_curve && performance.equity_curve.length > 0 && (
                <div style={{ height: 340, background: 'rgba(0,0,0,0.2)', borderRadius: 12, padding: '20px 16px 16px 0', marginBottom: 24, border: '1px solid rgba(255,255,255,0.03)' }}>
                  <div style={{ fontSize: 12, color: '#666', marginBottom: 8, paddingLeft: 16 }}>
                    60-day equity curve — {performance.equity_curve.length} data points
                  </div>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={performance.equity_curve}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="timestamp" tick={{ fill: '#555', fontSize: 10 }}
                        tickFormatter={(v) => { try { return new Date(v).toLocaleDateString('en', { month: 'short', day: 'numeric' }); } catch { return ''; } }}
                        interval={Math.floor((performance.equity_curve.length || 1) / 8)} />
                      <YAxis stroke="#666" fontSize={11} tickFormatter={(v) => `$${v}`} />
                      <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: 8, fontSize: 12 }}
                        labelFormatter={(l) => { try { return new Date(l).toLocaleString(); } catch { return ''; } }}
                        formatter={(value: any) => [`$${Number(value).toFixed(2)}`, 'Cumulative PnL']} />
                      <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="cumulative_pnl" stroke="#00ff88" strokeWidth={2} dot={false} name="Cumulative PnL" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Recent Trades */}
              {performance?.recent_trades && performance.recent_trades.length > 0 && (
                <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                  <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>Recent Closed Trades ({performance.total_closed_trades})</h3>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        {['Token', 'Exchanges', 'Slot', 'Signal', 'Opened', 'Closed', 'Duration', 'Net PnL'].map(h => (
                          <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 10, color: '#666', fontWeight: 600, textTransform: 'uppercase' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {performance.recent_trades.map((t: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 700, fontSize: 12 }}>{t.token}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#888' }}>{t.long_exchange} / {t.short_exchange}</td>
                          <td style={{ padding: '8px 12px' }}>
                            {t.slot && (
                              <span style={{
                                padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, textTransform: 'capitalize',
                                background: t.slot === 'aggressive' ? 'rgba(255,51,102,0.1)' : t.slot === 'conservative' ? 'rgba(0,255,136,0.1)' : 'rgba(68,136,255,0.1)',
                                color: t.slot === 'aggressive' ? '#ff3366' : t.slot === 'conservative' ? '#00ff88' : '#4488ff',
                              }}>{t.slot}</span>
                            )}
                          </td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700, color: t.signal === 'ENTER_POS' ? '#00ff88' : '#ff3366' }}>{t.signal === 'ENTER_POS' ? 'POS' : 'NEG'}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#666' }}>{t.opened_at?.slice(0, 10)}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#666' }}>{t.closed_at?.slice(0, 10)}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#888' }}>{t.duration_hours ? `${t.duration_hours}h` : '—'}</td>
                          <td style={{ padding: '8px 12px', fontSize: 12, fontFamily: "'JetBrains Mono'", fontWeight: 700, color: (t.funding_collected || 0) >= 0 ? '#00ff88' : '#ff3366' }}>
                            ${(t.funding_collected || 0).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
