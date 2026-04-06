'use client';

import { useState, useEffect } from 'react';
import { fetchAPI } from '@/lib/api';

interface QualityData {
  nb_assets: number;
  total_points: number;
  density_pct: number;
  date_range: { start: string; end: string };
  tokens: Array<{
    token: string;
    exchanges: string[];
    first_date: string;
    last_date: string;
    missing_pct: number;
  }>;
}

interface ScanResult {
  token: string;
  long_exchange: string;
  short_exchange: string;
  hourly_pct: number;
  apr_pct: number;
}

export default function HistoricalPage() {
  const [quality, setQuality] = useState<QualityData | null>(null);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [tab, setTab] = useState<'quality' | 'scanner'>('scanner');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadQuality();
  }, []);

  async function loadQuality() {
    setLoading(true);
    try {
      const res = await fetchAPI(`/api/historical/data-quality`);
      setQuality(res);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  async function runScan() {
    setLoading(true);
    try {
      const res = await fetchAPI(`/api/historical/scanner`);
      setScanResults(res.opportunities || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>
          📊 Historical Analysis
        </h1>
        <p style={{ fontSize: 14, color: '#8888aa', marginTop: 6 }}>
          Data quality audit and opportunity scanner
        </p>
      </div>

      <div style={{
        display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center',
        background: '#1a1a2e', borderRadius: 12, padding: '12px 20px',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 3 }}>
          {(['scanner', 'quality'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '8px 18px', borderRadius: 6, border: 'none', fontSize: 13,
              fontWeight: 600, cursor: 'pointer',
              background: tab === t ? 'linear-gradient(135deg, #4488ff, #3366cc)' : 'transparent',
              color: tab === t ? '#fff' : '#8888aa',
            }}>
              {t === 'scanner' ? '🚀 Scanner' : '🔍 Data Quality'}
            </button>
          ))}
        </div>

        {tab === 'scanner' && (
          <button onClick={runScan} style={{
            background: 'linear-gradient(135deg, #00ff88, #00cc66)', border: 'none',
            borderRadius: 8, padding: '10px 24px', color: '#000', fontSize: 13,
            fontWeight: 700, cursor: 'pointer',
          }}>
            ▶ Run Scan
          </button>
        )}
      </div>

      {/* KPIs */}
      {quality && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
          {[
            { label: 'Assets', value: quality.nb_assets, color: '#4488ff' },
            { label: 'Data Points', value: quality.total_points.toLocaleString(), color: '#8855ff' },
            { label: 'Density', value: `${quality.density_pct}%`, color: '#00ff88' },
            { label: 'Range', value: `${quality.date_range.start?.slice(0, 10)} → ${quality.date_range.end?.slice(0, 10)}`, color: '#ffcc00' },
          ].map((m, i) => (
            <div key={i} style={{
              background: '#1a1a2e', borderRadius: 10, padding: '16px 20px',
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div style={{ fontSize: 11, color: '#666', fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>{m.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: m.color }}>{m.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Content */}
      <div style={{
        background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>Loading...</div>
        ) : tab === 'scanner' ? (
          scanResults.length === 0 ? (
            <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>
              <p>Click "Run Scan" to find historical arbitrage opportunities</p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  {['#', 'Token', 'Long On', 'Short On', 'Hourly %', 'APR %'].map(h => (
                    <th key={h} style={{
                      padding: '12px 14px', textAlign: 'left', fontSize: 11,
                      color: '#666', fontWeight: 600, textTransform: 'uppercase',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scanResults.slice(0, 50).map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    <td style={{ padding: '12px 14px', color: '#666', fontSize: 12 }}>{i + 1}</td>
                    <td style={{ padding: '12px 14px', fontWeight: 600 }}>{r.token}</td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{
                        padding: '3px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                        background: 'rgba(0,255,136,0.1)', color: '#00ff88',
                      }}>{r.long_exchange}</span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{
                        padding: '3px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                        background: 'rgba(255,51,102,0.1)', color: '#ff3366',
                      }}>{r.short_exchange}</span>
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: "'JetBrains Mono'", fontSize: 12 }}>
                      {r.hourly_pct.toFixed(6)}
                    </td>
                    <td style={{
                      padding: '12px 14px', fontFamily: "'JetBrains Mono'", fontWeight: 700,
                      color: r.apr_pct > 0 ? '#00ff88' : '#ff3366',
                    }}>
                      {r.apr_pct.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          quality?.tokens && quality.tokens.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  {['Token', 'Exchanges', 'First Date', 'Last Date', 'Missing %'].map(h => (
                    <th key={h} style={{
                      padding: '12px 14px', textAlign: 'left', fontSize: 11,
                      color: '#666', fontWeight: 600, textTransform: 'uppercase',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {quality.tokens.map((t, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                    <td style={{ padding: '12px 14px', fontWeight: 600 }}>{t.token}</td>
                    <td style={{ padding: '12px 14px', fontSize: 12, color: '#8888aa' }}>{t.exchanges.join(', ')}</td>
                    <td style={{ padding: '12px 14px', fontSize: 12, color: '#8888aa' }}>{t.first_date?.slice(0, 10)}</td>
                    <td style={{ padding: '12px 14px', fontSize: 12, color: '#8888aa' }}>{t.last_date?.slice(0, 10)}</td>
                    <td style={{
                      padding: '12px 14px', fontFamily: "'JetBrains Mono'", fontSize: 12,
                      color: t.missing_pct > 20 ? '#ff3366' : t.missing_pct > 5 ? '#ffcc00' : '#00ff88',
                    }}>
                      {t.missing_pct}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>No quality data available</div>
          )
        )}
      </div>
    </div>
  );
}
