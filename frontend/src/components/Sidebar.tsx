'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { href: '/', label: 'Dashboard', icon: '' },
  { href: '/live', label: 'Live Monitor', icon: '' },
  { href: '/historical', label: 'Historical', icon: '' },
  { href: '/strategy', label: 'Strategy', icon: '' },
  { href: '/bot', label: 'Bot Control', icon: '' },
  { href: '/bot-portfolio', label: 'Bot Portfolio', icon: '' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside style={{
      position: 'fixed',
      left: 0,
      top: 0,
      width: 260,
      height: '100vh',
      background: 'linear-gradient(180deg, #0d0d15 0%, #12121a 100%)',
      borderRight: '1px solid rgba(255,255,255,0.06)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{
        padding: '28px 24px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg, #00ff88, #4488ff)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, fontWeight: 800,
          }}>₿</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#e8e8f0', letterSpacing: '-0.02em' }}>
              Funding Arb
            </div>
            <div style={{ fontSize: 11, color: '#666', fontWeight: 500 }}>Engine v1.0</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ padding: '16px 12px', flex: 1 }}>
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 16px',
              borderRadius: 10,
              marginBottom: 4,
              textDecoration: 'none',
              fontSize: 14,
              fontWeight: isActive ? 600 : 400,
              color: isActive ? '#fff' : '#8888aa',
              background: isActive
                ? 'linear-gradient(135deg, rgba(0,255,136,0.12), rgba(68,136,255,0.08))'
                : 'transparent',
              border: isActive ? '1px solid rgba(0,255,136,0.15)' : '1px solid transparent',
              transition: 'all 0.2s ease',
            }}>
              <span style={{ fontSize: 18 }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Status */}
      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 12, color: '#666',
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: '#00ff88',
            boxShadow: '0 0 8px rgba(0,255,136,0.5)',
          }} />
          System Online
        </div>
      </div>
    </aside>
  );
}
