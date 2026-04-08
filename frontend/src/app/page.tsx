'use client';

import { useState, useEffect } from 'react';
import { fetchAPI } from '@/lib/api';

interface Opportunity {
  token: string;
  best_long?: { exchange: string; rate: number };
  best_short?: { exchange: string; rate: number };
  spread_hourly: number;
  apr: number;
  nb_exchanges: number;
  exchanges: Record<string, number>;
}

interface BotStatus {
  is_running: boolean;
  mode: string;
  open_positions: number;
}

function MetricCard({ title, value, subtitle, color }: { title: string; value: string; subtitle?: string; color?: string }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16162a 100%)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 14,
      padding: '22px 24px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: 0, right: 0, width: 80, height: 80,
        background: `radial-gradient(circle, ${color || 'rgba(0,255,136,0.08)'} 0%, transparent 70%)`,
      }} />
      <div style={{ fontSize: 12, color: '#8888aa', fontWeight: 500, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {title}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: color || '#e8e8f0', letterSpacing: '-0.02em' }}>
        {value}
      </div>
      {subtitle && <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{subtitle}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [liveData, setLiveData] = useState<Opportunity[]>([]);
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [liveRes, botRes] = await Promise.allSettled([
          fetchAPI('/api/live?min_exchanges=2'),
          fetchAPI('/api/bot/status'),
        ]);

        if (liveRes.status === 'fulfilled') setLiveData(liveRes.value.data || []);
        if (botRes.status === 'fulfilled') setBotStatus(botRes.value);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const topOpps = liveData.slice(0, 5);
  const avgApr = liveData.length > 0
    ? liveData.reduce((s, d) => s + d.apr, 0) / liveData.length
    : 0;

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', margin: 0 }}>
          Dashboard
        </h1>
        <p style={{ fontSize: 14, color: '#8888aa', marginTop: 6 }}>
          Cross-exchange funding rate arbitrage overview
        </p>
      </div>

      {/* KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <MetricCard
          title="Active Pairs"
          value={String(liveData.length)}
          subtitle="With ≥2 exchanges"
          color="#4488ff"
        />
        <MetricCard
          title="Best APR"
          value={topOpps[0] ? `${topOpps[0].apr.toFixed(0)}%` : '—'}
          subtitle={topOpps[0] ? `${topOpps[0].token}` : 'No data'}
          color="#00ff88"
        />
        <MetricCard
          title="Avg APR"
          value={`${avgApr.toFixed(0)}%`}
          subtitle="Across all pairs"
          color="#ffcc00"
        />
        <MetricCard
          title="Bot Status"
          value={botStatus?.is_running ? 'Running' : 'Stopped'}
          subtitle={botStatus ? `Mode: ${botStatus.mode}` : 'Not connected'}
          color={botStatus?.is_running ? '#00ff88' : '#ff3366'}
        />
      </div>

      {/* Top Opportunities */}
      <div style={{
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16162a 100%)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 14,
        overflow: 'hidden',
      }}>
        <div style={{ padding: '18px 24px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
            Top Opportunities
            <span style={{ fontSize: 12, color: '#8888aa', fontWeight: 400 }}>
              (Live data)
            </span>
          </h2>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#666' }}>Loading...</div>
        ) : liveData.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#666' }}>
            No live data. Start the live feed scripts and Redis.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                {['Token', 'APR %', 'Spread/H', 'Long On', 'Short On', 'Exchanges'].map(h => (
                  <th key={h} style={{
                    padding: '12px 16px', textAlign: 'left', fontSize: 11,
                    color: '#666', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {liveData.slice(0, 20).map((item, i) => (
                <tr key={i} style={{
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                  transition: 'background 0.15s',
                }} onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                   onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <td style={{ padding: '14px 16px', fontWeight: 600, fontSize: 14 }}>
                    {item.token}
                  </td>
                  <td style={{
                    padding: '14px 16px', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                    color: item.apr > 0 ? '#00ff88' : '#ff3366',
                  }}>
                    {item.apr.toFixed(1)}%
                  </td>
                  <td style={{ padding: '14px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: '#8888aa' }}>
                    {item.spread_hourly.toFixed(4)}%
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <span style={{
                      padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                      background: 'rgba(0,255,136,0.1)', color: '#00ff88', border: '1px solid rgba(0,255,136,0.2)',
                    }}>
                      {item.best_long?.exchange || '—'}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <span style={{
                      padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                      background: 'rgba(255,51,102,0.1)', color: '#ff3366', border: '1px solid rgba(255,51,102,0.2)',
                    }}>
                      {item.best_short?.exchange || '—'}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px', color: '#8888aa', fontSize: 13 }}>
                    {item.nb_exchanges}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
