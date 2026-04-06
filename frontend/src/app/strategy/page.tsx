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

  // Config
  const [zscoreEntry, setZscoreEntry] = useState(2.0);
  const [zscoreExit, setZscoreExit] = useState(0.5);
  const [lookback, setLookback] = useState(168);

  // Results
  const [analysis, setAnalysis] = useState<any>(null);
  const [backtest, setBacktest] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [optResults, setOptResults] = useState<any[]>([]);
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
    setOptResults([]);
    try {
      const res = await fetchAPI('/api/strategy/backtest', {
        method: 'POST',
        body: JSON.stringify({
          token: selectedToken,
          long_exchange: longEx,
          short_exchange: shortEx,
          config: {
            zscore_entry: zscoreEntry,
            zscore_exit: zscoreExit,
            lookback_hours: lookback
          }
        })
      });
      setBacktest(res);
      setActiveTab('backtest');
    } catch (e: any) {
      console.error(e);
      setBacktest({ error: 'Failed to run backtest' });
    }
    setLoading(false);
  };

  const handleOptimize = async () => {
    setOptimizing(true);
    setOptResults([]);
    try {
      const res = await fetchAPI('/api/strategy/optimize', {
        method: 'POST',
        body: JSON.stringify({
          token: selectedToken,
          long_exchange: longEx,
          short_exchange: shortEx,
          config: {
            zscore_entry: zscoreEntry,
            zscore_exit: zscoreExit,
            lookback_hours: lookback
          }
        })
      });
      setOptResults(res.results || []);
    } catch (e: any) {
      console.error(e);
    }
    setOptimizing(false);
  };

  const applyParams = (params: any) => {
    setZscoreEntry(params.zscore_entry);
    setZscoreExit(params.zscore_exit);
    setLookback(params.lookback_hours);
    setOptResults([]);
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

          <button onClick={runAnalysis} disabled={!selectedToken || loading} style={{
            background: 'linear-gradient(135deg, #8855ff, #6633cc)', border: 'none',
            borderRadius: 8, padding: '10px 20px', color: '#fff', fontSize: 13,
            fontWeight: 700, cursor: 'pointer', opacity: !selectedToken ? 0.5 : 1,
          }}>
            🔬 Analyze Risk
          </button>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={handleBacktest}
            disabled={loading || optimizing || !selectedToken}
            style={{
              flex: 1, padding: '14px', borderRadius: 10, border: 'none',
              background: 'linear-gradient(135deg, #4488ff, #8855ff)',
              color: 'white', fontWeight: 700, cursor: (loading || optimizing) ? 'not-allowed' : 'pointer',
              opacity: (loading || optimizing) ? 0.7 : 1, transition: '0.2s'
            }}
          >
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
          <button
            onClick={handleOptimize}
            disabled={loading || optimizing || !selectedToken}
            style={{
              flex: 1, padding: '14px', borderRadius: 10, border: '1px solid #4488ff',
              background: 'transparent',
              color: '#4488ff', fontWeight: 700, cursor: (loading || optimizing) ? 'not-allowed' : 'pointer',
              opacity: (loading || optimizing) ? 0.7 : 1, transition: '0.2s'
            }}
          >
            {optimizing ? 'Optimizing...' : 'Optimize Params'}
          </button>
        </div>

        {/* Optimizer Results */}
        {optResults.length > 0 && (
          <div style={{ 
            background: 'rgba(68,136,255,0.05)', borderRadius: 12, padding: 20, 
            marginTop: 20, border: '1px solid rgba(68,136,255,0.1)' 
          }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, color: '#4488ff' }}>🚀 Best Optimized Parameters</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {optResults.map((res: any, idx: number) => (
                <div key={idx} style={{ 
                  background: 'rgba(255,255,255,0.02)', padding: 12, borderRadius: 8, 
                  border: '1px solid rgba(255,255,255,0.04)', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                }}>
                  <div>
                    <div style={{ fontSize: 10, color: '#666' }}>Ent: {res.params.zscore_entry} | Ext: {res.params.zscore_exit} | Lbk: {res.params.lookback_hours}h</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#00ff88' }}>Sharpe: {res.sharpe.toFixed(2)} | PnL: {res.pnl.toFixed(2)}%</div>
                  </div>
                  <button 
                    onClick={() => applyParams(res.params)}
                    style={{ background: '#4488ff', border: 'none', borderRadius: 4, padding: '4px 8px', color: 'white', fontSize: 10, cursor: 'pointer' }}
                  >
                    Apply
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
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
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Risk Analysis Results</h2>
          
          {analysis.error ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#ff3366', fontSize: 14 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
              {analysis.error}
              <br/><br/>
              <span style={{ fontSize: 12, color: '#ff3366aa' }}>Check if the selected exchanges have historical data for this token in the current dataset.</span>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24, marginTop: -8 }}>
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
            </>
          )}
        </div>
      )}

      {!loading && backtest && activeTab === 'backtest' && (
        <div style={{
          background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 14, padding: '24px',
        }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 20 }}>Backtest Results</h2>

          {backtest.error ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#ff3366', fontSize: 14 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
              {backtest.error}
              <br/><br/>
              <span style={{ fontSize: 12, color: '#ff3366aa' }}>Check your exchange selection. Binance often lacks hourly funding data in this dataset. Try paradex or extended!</span>
            </div>
          ) : backtest.metrics && backtest.metrics.total_trades > 0 ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
                {[
                  { label: 'Strategy PnL', value: `${backtest.metrics.total_pnl_pct}%`, color: backtest.metrics.total_pnl_pct > 0 ? '#00ff88' : '#ff3366' },
                  { label: 'Passive PnL', value: `${backtest.equity_curve?.[backtest.equity_curve.length - 1]?.passive_pnl || 0}%`, color: '#8888aa' },
                  { label: 'Sharpe', value: backtest.metrics.sharpe_ratio, color: '#4488ff' },
                  { label: 'Win Rate', value: `${backtest.metrics.win_rate}%`, color: '#ffcc00' },
                  { label: 'Max DD', value: `${backtest.metrics.max_drawdown_pct}%`, color: '#ff3366' },
                  { label: 'Trades', value: backtest.metrics.total_trades, color: '#8855ff' },
                  { label: 'Avg Duration', value: `${backtest.metrics.avg_duration_hours}h`, color: '#8888aa' },
                  { label: 'Profit Factor', value: backtest.metrics.profit_factor, color: '#00ff88' },
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

              {/* Chart Section */}
              <div style={{ 
                height: 350, 
                width: '100%', 
                background: 'rgba(0,0,0,0.2)', 
                borderRadius: 12, 
                padding: '24px 16px 16px 0',
                marginBottom: 24,
                border: '1px solid rgba(255,255,255,0.03)'
              }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={backtest.equity_curve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis 
                      dataKey="time" 
                      hide={true}
                    />
                    <YAxis 
                      stroke="#666" 
                      fontSize={11} 
                      tickFormatter={(v) => `${v}%`}
                      domain={([dataMin, dataMax]) => {
                        const min = Math.min(0, dataMin);
                        const max = Math.max(0, dataMax);
                        return [min * 1.1, max * 1.1];
                      }}
                    />
                    <Tooltip 
                      contentStyle={{ background: '#1a1a2e', border: '1px solid #333', borderRadius: 8, fontSize: 12 }}
                      itemStyle={{ padding: '0 4px' }}
                      labelFormatter={(l) => new Date(l).toLocaleString()}
                    />
                    <Legend verticalAlign="top" height={36}/>
                    <ReferenceLine y={0} stroke="#444" strokeDasharray="3 3" />
                    <Line 
                      name="Active Strategy"
                      type="monotone" 
                      dataKey="cumulative_pnl" 
                      stroke="#8855ff" 
                      strokeWidth={2}
                      dot={false} 
                      activeDot={{ r: 4 }}
                    />
                    <Line 
                      name="Passive (Hold)"
                      type="monotone" 
                      dataKey="passive_pnl" 
                      stroke="#00ff88" 
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false} 
                      activeDot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
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
          ) : (
            <div style={{ padding: 40, textAlign: 'center', color: '#8888aa', fontSize: 14 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🤷‍♂️</div>
              {backtest.metrics?.message || "No trades triggered for this pair with the current configuration."}
              <br/><br/>
              <span style={{ fontSize: 12, color: '#666' }}>Try picking a pair with more funding spread divergence.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
