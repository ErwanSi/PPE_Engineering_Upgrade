'use client';

import { useState, useEffect } from 'react';
import { fetchAPI } from '@/lib/api';

export default function StrategyPage() {
  const [tokens, setTokens] = useState<string[]>([]);
  const [selectedToken, setSelectedToken] = useState('');
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [longEx, setLongEx] = useState('');
  const [shortEx, setShortEx] = useState('');
  const [dataset, setDataset] = useState('ARBITRAGE');

  // Config
  const [zscoreEntry, setZscoreEntry] = useState(2.0);
  const [zscoreExit, setZscoreExit] = useState(0.5);
  const [lookback, setLookback] = useState(168);

  // Results
  const [analysis, setAnalysis] = useState<any>(null);
  const [backtest, setBacktest] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'analysis' | 'backtest'>('analysis');

  useEffect(() => {
    fetchAPI(`/api/historical/tokens?dataset=${dataset}`)
      .then(res => setTokens(res.tokens || []))
      .catch(() => {});
  }, [dataset]);

  useEffect(() => {
    if (selectedToken) {
      fetchAPI(`/api/historical/exchanges?token=${selectedToken}&dataset=${dataset}`)
        .then(res => {
          setExchanges(res.exchanges || []);
          if (res.exchanges?.length >= 2) {
            setLongEx(res.exchanges[0]);
            setShortEx(res.exchanges[1]);
          }
        })
        .catch(() => {});
    }
  }, [selectedToken, dataset]);

  async function runAnalysis() {
    setLoading(true);
    try {
      const res = await fetchAPI('/api/strategy/analyze', {
        method: 'POST',
        body: JSON.stringify({
          token: selectedToken,
          long_exchange: longEx,
          short_exchange: shortEx,
          dataset,
          config: { zscore_entry: zscoreEntry, zscore_exit: zscoreExit, lookback_hours: lookback }
        }),
      });
      setAnalysis(res);
      setActiveTab('analysis');
    } catch (e: any) { alert(e.message); }
    setLoading(false);
  }

  async function runBacktest() {
    setLoading(true);
    try {
      const res = await fetchAPI('/api/strategy/backtest', {
        method: 'POST',
        body: JSON.stringify({
          token: selectedToken,
          long_exchange: longEx,
          short_exchange: shortEx,
          dataset,
          config: { zscore_entry: zscoreEntry, zscore_exit: zscoreExit, lookback_hours: lookback }
        }),
      });
      setBacktest(res);
      setActiveTab('backtest');
    } catch (e: any) { alert(e.message); }
    setLoading(false);
  }

  const selectStyle = {
    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8, padding: '10px 14px', color: '#e8e8f0', fontSize: 14, minWidth: 140,
  };

  const inputStyle = {
    ...selectStyle, width: 80, textAlign: 'center' as const,
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

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>🧠 Strategy Lab</h1>
        <p style={{ fontSize: 14, color: '#8888aa', marginTop: 6 }}>
          Risk Analysis (ADF, Cointegration) + Event-Driven Backtest
        </p>
      </div>

      {/* Config Panel */}
      <div style={{
        background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14, padding: '20px 24px', marginBottom: 20,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#8888aa', marginBottom: 14, textTransform: 'uppercase' }}>
          Configuration
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'end' }}>
          <div>
            <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>Dataset</label>
            <select value={dataset} onChange={e => setDataset(e.target.value)} style={selectStyle}>
              <option value="ARBITRAGE">Arbitrage</option>
              <option value="STRICT">Strict</option>
              <option value="ALL">All</option>
            </select>
          </div>
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
          <div>
            <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>Z Entry</label>
            <input type="number" step="0.1" value={zscoreEntry} onChange={e => setZscoreEntry(+e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>Z Exit</label>
            <input type="number" step="0.1" value={zscoreExit} onChange={e => setZscoreExit(+e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 4 }}>Lookback (h)</label>
            <input type="number" value={lookback} onChange={e => setLookback(+e.target.value)} style={inputStyle} />
          </div>

          <button onClick={runAnalysis} disabled={!selectedToken || loading} style={{
            background: 'linear-gradient(135deg, #8855ff, #6633cc)', border: 'none',
            borderRadius: 8, padding: '10px 20px', color: '#fff', fontSize: 13,
            fontWeight: 700, cursor: 'pointer', opacity: !selectedToken ? 0.5 : 1,
          }}>
            🔬 Analyze Risk
          </button>
          <button onClick={runBacktest} disabled={!selectedToken || loading} style={{
            background: 'linear-gradient(135deg, #00ff88, #00cc66)', border: 'none',
            borderRadius: 8, padding: '10px 20px', color: '#000', fontSize: 13,
            fontWeight: 700, cursor: 'pointer', opacity: !selectedToken ? 0.5 : 1,
          }}>
            ▶ Backtest
          </button>
        </div>
      </div>

      {/* Results */}
      {loading && (
        <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>
          Computing... This may take a moment for large datasets.
        </div>
      )}

      {!loading && analysis && activeTab === 'analysis' && (
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '24px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Risk Analysis Results</h2>
            <RiskBadge level={analysis.risk_level} />
          </div>

          <p style={{ fontSize: 14, marginBottom: 24, color: '#e8e8f0' }}>{analysis.verdict}</p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            {/* ADF Spread */}
            <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 10, padding: 16, border: '1px solid rgba(255,255,255,0.04)' }}>
              <div style={{ fontSize: 12, color: '#8888aa', fontWeight: 600, marginBottom: 10 }}>ADF TEST (Spread)</div>
              <div style={{ fontSize: 14, color: analysis.adf_spread?.is_stationary ? '#00ff88' : '#ff3366', fontWeight: 600 }}>
                {analysis.adf_spread?.interpretation}
              </div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
                p-value: {analysis.adf_spread?.p_value} | Stat: {analysis.adf_spread?.test_statistic}
              </div>
            </div>

            {/* Cointegration */}
            <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 10, padding: 16, border: '1px solid rgba(255,255,255,0.04)' }}>
              <div style={{ fontSize: 12, color: '#8888aa', fontWeight: 600, marginBottom: 10 }}>COINTEGRATION</div>
              <div style={{ fontSize: 14, color: analysis.cointegration?.is_cointegrated ? '#00ff88' : '#ff3366', fontWeight: 600 }}>
                {analysis.cointegration?.interpretation}
              </div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
                p-value: {analysis.cointegration?.p_value}
              </div>
            </div>

            {/* Hedge Ratio */}
            <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: 10, padding: 16, border: '1px solid rgba(255,255,255,0.04)' }}>
              <div style={{ fontSize: 12, color: '#8888aa', fontWeight: 600, marginBottom: 10 }}>HEDGE RATIO (β)</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#4488ff', fontFamily: "'JetBrains Mono'" }}>
                {analysis.hedge_ratio?.beta}
              </div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 8 }}>
                R² = {analysis.hedge_ratio?.r_squared} | Spread σ = {analysis.hedge_ratio?.spread_std}
              </div>
            </div>
          </div>
        </div>
      )}

      {!loading && backtest && activeTab === 'backtest' && (
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '24px',
        }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Backtest Results</h2>

          {backtest.metrics && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
                {[
                  { label: 'Total PnL', value: `${backtest.metrics.total_pnl_pct}%`, color: backtest.metrics.total_pnl_pct > 0 ? '#00ff88' : '#ff3366' },
                  { label: 'Sharpe', value: backtest.metrics.sharpe_ratio, color: '#4488ff' },
                  { label: 'Win Rate', value: `${backtest.metrics.win_rate}%`, color: '#ffcc00' },
                  { label: 'Max DD', value: `${backtest.metrics.max_drawdown_pct}%`, color: '#ff3366' },
                  { label: 'Trades', value: backtest.metrics.total_trades, color: '#8855ff' },
                  { label: 'Avg Duration', value: `${backtest.metrics.avg_duration_hours}h`, color: '#8888aa' },
                  { label: 'Profit Factor', value: backtest.metrics.profit_factor, color: '#00ff88' },
                  { label: 'Avg PnL/Trade', value: `${backtest.metrics.avg_pnl_per_trade_pct}%`, color: '#4488ff' },
                ].map((m, i) => (
                  <div key={i} style={{
                    background: 'rgba(255,255,255,0.02)', borderRadius: 10, padding: '14px 16px',
                    border: '1px solid rgba(255,255,255,0.04)',
                  }}>
                    <div style={{ fontSize: 11, color: '#666', fontWeight: 600, textTransform: 'uppercase' }}>{m.label}</div>
                    <div style={{ fontSize: 20, fontWeight: 800, color: m.color, marginTop: 4, fontFamily: "'JetBrains Mono'" }}>
                      {m.value}
                    </div>
                  </div>
                ))}
              </div>

              {/* Trade List */}
              {backtest.trades && backtest.trades.length > 0 && (
                <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                        {['Entry', 'Exit', 'Direction', 'Z In', 'Z Out', 'Funding PnL', 'Cost', 'Net PnL', 'Duration'].map(h => (
                          <th key={h} style={{
                            padding: '10px 12px', textAlign: 'left', fontSize: 10,
                            color: '#666', fontWeight: 600, textTransform: 'uppercase',
                          }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {backtest.trades.map((t: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#8888aa' }}>{t.entry_time?.slice(0, 16)}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#8888aa' }}>{t.exit_time?.slice(0, 16)}</td>
                          <td style={{ padding: '8px 12px' }}>
                            <span style={{
                              padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700,
                              background: t.direction === 'LONG' ? 'rgba(0,255,136,0.1)' : 'rgba(255,51,102,0.1)',
                              color: t.direction === 'LONG' ? '#00ff88' : '#ff3366',
                            }}>{t.direction}</span>
                          </td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontFamily: "'JetBrains Mono'" }}>{t.entry_zscore}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontFamily: "'JetBrains Mono'" }}>{t.exit_zscore}</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontFamily: "'JetBrains Mono'" }}>{t.funding_pnl_pct}%</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, fontFamily: "'JetBrains Mono'", color: '#ff3366' }}>{t.cost_pct}%</td>
                          <td style={{
                            padding: '8px 12px', fontSize: 11, fontFamily: "'JetBrains Mono'", fontWeight: 700,
                            color: t.net_pnl_pct > 0 ? '#00ff88' : '#ff3366',
                          }}>{t.net_pnl_pct}%</td>
                          <td style={{ padding: '8px 12px', fontSize: 11, color: '#8888aa' }}>{t.duration_hours}h</td>
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
