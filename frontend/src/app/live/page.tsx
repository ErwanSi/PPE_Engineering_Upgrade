'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchAPI } from '@/lib/api';

interface LiveRate {
  token: string;
  exchanges: Record<string, number>;
  nb_exchanges: number;
  best_long?: { exchange: string; rate: number };
  best_short?: { exchange: string; rate: number };
  spread_hourly: number;
  apr: number;
}

export default function LivePage() {
  const [data, setData] = useState<LiveRate[]>([]);
  const [search, setSearch] = useState('');
  const [minExchanges, setMinExchanges] = useState(2);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await fetchAPI(`/api/live?search=${search}&min_exchanges=${minExchanges}`);
      setData(res.data || []);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [search, minExchanges]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const exchanges = ['binance', 'hyperliquid', 'paradex', 'extended'];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>
          Live Monitor
        </h1>
        <p style={{ fontSize: 14, color: '#8888aa', marginTop: 6 }}>
          Real-time funding rates from Redis — Auto-refresh every 15s
        </p>
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex', gap: 16, marginBottom: 20, alignItems: 'center',
        background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: '12px 20px',
      }}>
        <input
          type="text"
          placeholder="Search token (BTC, ETH, SOL...)"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8, padding: '10px 16px', color: '#e8e8f0', fontSize: 14,
            outline: 'none',
          }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#8888aa', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={minExchanges === 1}
            onChange={e => setMinExchanges(e.target.checked ? 1 : 2)}
            style={{ accentColor: '#4488ff' }}
          />
          Show orphan tokens
        </label>
        <button onClick={load} style={{
          background: 'linear-gradient(135deg, #4488ff, #3366cc)', border: 'none',
          borderRadius: 8, padding: '10px 20px', color: '#fff', fontSize: 13,
          fontWeight: 600, cursor: 'pointer',
        }}>
          ⟳ Refresh
        </button>
        <span style={{ fontSize: 12, color: '#666' }}>Updated: {lastUpdate}</span>
      </div>

      {/* Table */}
      <div style={{
        background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>Loading live data...</div>
        ) : data.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>
            <p style={{ fontSize: 16, marginBottom: 8 }}>No live data available</p>
            <p style={{ fontSize: 13 }}>Start Redis and the live feed scripts (*Live.py)</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  {['Token', 'APR %', 'Spread/H', 'Long', 'Short', ...exchanges, '# Exch'].map(h => (
                    <th key={h} style={{
                      padding: '12px 14px', textAlign: 'left', fontSize: 11,
                      color: '#666', fontWeight: 600, textTransform: 'uppercase',
                      letterSpacing: '0.05em', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((item, i) => (
                  <tr key={i} style={{
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td style={{ padding: '12px 14px', fontWeight: 600, fontSize: 14 }}>{item.token}</td>
                    <td style={{
                      padding: '12px 14px', fontFamily: "'JetBrains Mono', monospace", fontWeight: 700,
                      color: item.apr > 0 ? '#00ff88' : '#ff3366',
                    }}>
                      {item.apr.toFixed(1)}%
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#8888aa' }}>
                      {item.spread_hourly.toFixed(4)}%
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{
                        padding: '3px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                        background: 'rgba(0,255,136,0.1)', color: '#00ff88',
                      }}>
                        {item.best_long?.exchange || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{
                        padding: '3px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                        background: 'rgba(255,51,102,0.1)', color: '#ff3366',
                      }}>
                        {item.best_short?.exchange || '—'}
                      </span>
                    </td>
                    {exchanges.map(ex => (
                      <td key={ex} style={{
                        padding: '12px 14px', fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 12, color: item.exchanges[ex] !== undefined ? '#e8e8f0' : '#333',
                      }}>
                        {item.exchanges[ex] !== undefined ? `${item.exchanges[ex].toFixed(6)}%` : '—'}
                      </td>
                    ))}
                    <td style={{ padding: '12px 14px', color: '#8888aa', textAlign: 'center' }}>
                      {item.nb_exchanges}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
