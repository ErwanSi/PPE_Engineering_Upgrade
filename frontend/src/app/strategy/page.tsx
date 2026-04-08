'use client';

import { useState, useEffect } from 'react';
import { fetchAPI } from '@/lib/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

export default function StrategyPage() {
  const [tokens, setTokens] = useState<string[]>([]);
  const [selectedToken, setSelectedToken] = useState('');
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [longEx, setLongEx] = useState('');
  const [shortEx, setShortEx] = useState('');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const [zscoreEntry, setZscoreEntry] = useState(2.0);
  const [zscoreExit, setZscoreExit] = useState(0.5);
  const [lookback, setLookback] = useState(168);

  const [analysis, setAnalysis] = useState<any>(null);
  const [backtest, setBacktest] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [autoTune, setAutoTune] = useState(true);
  const [activeTab, setActiveTab] = useState<'analysis' | 'backtest'>('analysis');

  useEffect(() => {
    fetchAPI(`/api/historical/tokens`)
      .then(res => setTokens(res.tokens || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedToken) {
      fetchAPI(`/api/historical/exchanges?token=${selectedToken}`)
        .then(res => {
          setExchanges(res.exchanges || []);
          if (res.exchanges?.length >= 2) {
            setLongEx(res.exchanges[0]);
            setShortEx(res.exchanges[1]);
          }
        })
        .catch(() => {});
    }
  }, [selectedToken]);

  async function runAnalysis() {
    setLoading(true);
    try {
      const res = await fetchAPI('/api/strategy/analyze', {
        method: 'POST',
        body: JSON.stringify({
          token: selectedToken,
          long_exchange: longEx,
          short_exchange: shortEx,
          config: { zscore_entry: zscoreEntry, zscore_exit: zscoreExit, lookback_hours: lookback }
        }),
      });
      setAnalysis(res);
      setActiveTab('analysis');
    } catch (e: any) { alert(e.message); }
    setLoading(false);
  }

  const handleBacktest = async () => {
    setLoading(true);
    setBacktest(null);
    try {
      const res = await fetchAPI('/api/strategy/backtest', {
        method: 'POST',
        body: JSON.stringify({
          token: selectedToken,
          long_exchange: longEx,
          short_exchange: shortEx,
          auto_tune: autoTune,
          config: {
            zscore_entry: zscoreEntry,
            zscore_exit: zscoreExit,
            lookback_hours: lookback
          }
        })
      });
      setBacktest(res);
      if (res.optimized_params && autoTune) {
        setZscoreEntry(res.optimized_params.zscore_entry);
        setZscoreExit(res.optimized_params.zscore_exit);
        setLookback(res.optimized_params.lookback_hours);
      }
      setActiveTab('backtest');
    } catch (e: any) {
      console.error(e);
      setBacktest({ error: 'Failed to run backtest' });
    }
    setLoading(false);
  };

  const selectStyle = {
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8, padding: '10px 14px', color: '#e8e8f0', fontSize: 14, minWidth: 140,
  };

  function RiskBadge({ level }: { level: string }) {
    const colors: Record<string, string> = { LOW: '#00ff88', MEDIUM: '#ffcc00', HIGH: '#ff3366' };
    return (
      <span style={{
        padding: '6px 14px', borderRadius: 8, fontSize: 13, fontWeight: 700,
        background: `${colors[level] || '#666'}22`, color: colors[level] || '#666',
        border: `1px solid ${colors[level] || '#666'}44`,
      }}>
        Risk: {level}
      </span>
    );
  }

  if (!mounted) return null;

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>Strategy Lab</h1>
        <p style={{ fontSize: 14, color: '#8888aa', marginTop: 6 }}>
          Statistical Arbitrage — Strategy vs Funding Hold
        </p>
      </div>

      <div style={{
        background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14, padding: '20px 24px', marginBottom: 20,
      }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'end', marginBottom: 20 }}>
          <div>
            <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>Token</label>
            <select value={selectedToken} onChange={e => setSelectedToken(e.target.value)} style={selectStyle}>
              <option value="">Select...</option>
              {tokens.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>Long On</label>
            <select value={longEx} onChange={e => setLongEx(e.target.value)} style={selectStyle}>
              {exchanges.map(e => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>Short On</label>
            <select value={shortEx} onChange={e => setShortEx(e.target.value)} style={selectStyle}>
              {exchanges.map(e => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>

        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(255,255,255,0.03)', padding: '8px 16px', borderRadius: 8 }}>
            <label style={{ fontSize: 13, color: '#e8e8f0', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
              <input type="checkbox" checked={autoTune} onChange={e => setAutoTune(e.target.checked)} style={{ marginRight: 8 }} />
              Auto-Tune
            </label>
          </div>
          <button
            onClick={handleBacktest}
            disabled={loading || !selectedToken}
            style={{
              flex: 1, padding: '14px', borderRadius: 10, border: 'none',
              background: 'linear-gradient(135deg, #4488ff, #8855ff)',
              color: 'white', fontWeight: 700, cursor: 'pointer'
            }}
          >
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {loading && <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>Processing...</div>}

      {!loading && analysis && activeTab === 'analysis' && (
        <div style={{ background: '#1a1a2e', borderRadius: 14, padding: '24px', border: '1px solid rgba(255,255,255,0.06)' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Analysis Results</h2>
          {analysis.error ? (
            <div style={{ color: '#ff3366' }}>{analysis.error}</div>
          ) : (
            <>
              <RiskBadge level={analysis.risk_level} />
              <p style={{ marginTop: 16, color: '#e8e8f0' }}>{analysis.verdict}</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginTop: 20 }}>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: 16, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: '#888' }}>Stationarity</div>
                  <div style={{ color: analysis.adf_spread?.is_stationary ? '#00ff88' : '#ff3366' }}>{analysis.adf_spread?.interpretation}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: 16, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: '#888' }}>Cointegration</div>
                  <div style={{ color: analysis.cointegration?.is_cointegrated ? '#00ff88' : '#ff3366' }}>{analysis.cointegration?.interpretation}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: 16, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: '#888' }}>Hedge Ratio</div>
                  <div style={{ color: '#4488ff', fontSize: 20 }}>{analysis.hedge_ratio?.beta}</div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {!loading && backtest && activeTab === 'backtest' && (
        <div style={{ background: '#1a1a2e', borderRadius: 14, padding: '24px', border: '1px solid rgba(255,255,255,0.06)' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Backtest Results</h2>
          {backtest.error ? (
            <div style={{ color: '#ff3366' }}>{backtest.error}</div>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
                <Panel label="Strategy PnL" value={`${backtest.metrics?.total_pnl_pct ?? 0}%`} color={(backtest.metrics?.total_pnl_pct ?? 0) > 0 ? '#00ff88' : '#ff3366'} />
                <Panel label="Funding Hold" value={`${backtest.metrics?.hold_pnl_pct ?? 0}%`} color={(backtest.metrics?.hold_pnl_pct ?? 0) > 0 ? '#4488ff' : '#ff3366'} />
                <Panel label="Alpha" value={`${backtest.metrics?.alpha_pct ?? 0}%`} color={(backtest.metrics?.alpha_pct ?? 0) > 0 ? '#00ff88' : '#ff3366'} />
                <Panel label="Sharpe" value={backtest.metrics?.sharpe_ratio ?? 0} color="#8855ff" />
                <Panel label="Trades" value={backtest.metrics?.total_trades ?? 0} color="#ffcc00" />
              </div>

              {/* Additional metrics */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
                <Panel label="Win Rate" value={`${backtest.metrics?.win_rate ?? 0}%`} color="#00ff88" />
                <Panel label="Max Drawdown" value={`${backtest.metrics?.max_drawdown_pct ?? 0}%`} color="#ff3366" />
                <Panel label="Avg Duration" value={`${backtest.metrics?.avg_duration_hours ?? 0}h`} color="#4488ff" />
                <Panel label="Profit Factor" value={backtest.metrics?.profit_factor === Infinity ? '∞' : backtest.metrics?.profit_factor ?? 0} color="#8855ff" />
              </div>

              <div style={{ height: 380, background: 'rgba(0,0,0,0.2)', borderRadius: 12, padding: '24px 16px 16px 0', marginBottom: 24, border: '1px solid rgba(255,255,255,0.03)' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={backtest.equity_curve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false}  />
                    <XAxis dataKey="time" hide />
                    <YAxis stroke="#666" fontSize={11} tickFormatter={(v) => `${v}%`} />
                    <Tooltip
                      contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: 8, fontSize: 12 }}
                      labelFormatter={(l) => new Date(l).toLocaleString()}
                      formatter={(value: any, name: any) => {
                        const labels: Record<string, string> = {
                          'cumulative_pnl': 'Strategy',
                          'hold_pnl': 'Funding Hold',
                        };
                        return [`${Number(value).toFixed(4)}%`, labels[name] || name];
                      }}
                    />
                    <Legend verticalAlign="top" height={36} />
                    <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
                    <Line name="Strategy" type="monotone" dataKey="cumulative_pnl" stroke="#8855ff" strokeWidth={2} dot={false} />
                    <Line name="Funding Hold" type="monotone" dataKey="hold_pnl" stroke="#00ff88" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Trade History */}
              {backtest.trades && backtest.trades.length > 0 && (
                <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                  <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12 }}>Trade History</h3>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        {['Entry', 'Exit', 'Direction', 'Duration', 'Funding PnL', 'Costs', 'Net PnL'].map(h => (
                          <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 10, color: '#666', fontWeight: 600, textTransform: 'uppercase' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {backtest.trades.slice(0, 50).map((t: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#888' }}>{t.entry_time?.slice(0, 16)}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#888' }}>{t.exit_time?.slice(0, 16)}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontWeight: 700, color: t.direction === 'ENTER_POS' ? '#00ff88' : '#ff3366' }}>{t.direction === 'ENTER_POS' ? 'POS' : 'NEG'}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#888' }}>{t.duration_hours}h</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontFamily: "'JetBrains Mono'", color: t.funding_pnl_pct > 0 ? '#00ff88' : '#ff3366' }}>{t.funding_pnl_pct}%</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontFamily: "'JetBrains Mono'", color: '#ff3366' }}>-{t.cost_pct}%</td>
                          <td style={{ padding: '8px 12px', fontSize: 12, fontFamily: "'JetBrains Mono'", fontWeight: 700, color: t.net_pnl_pct > 0 ? '#00ff88' : '#ff3366' }}>{t.net_pnl_pct}%</td>
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
    </div>
  );
}

function Panel({ label, value, color }: { label: string, value: any, color: string }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.02)', padding: 14, borderRadius: 10, border: '1px solid rgba(255,255,255,0.04)' }}>
      <div style={{ fontSize: 11, color: '#666', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color, marginTop: 4, fontFamily: "'JetBrains Mono'" }}>{value}</div>
    </div>
  );
}
