const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchAPI(endpoint: string, options?: RequestInit) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options?.headers as Record<string, string>) || {}),
  };

  // Add auth token for bot endpoints
  if (typeof window !== 'undefined' && endpoint.startsWith('/api/bot')) {
    const token = sessionStorage.getItem('bot_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && endpoint.startsWith('/api/bot') && endpoint !== '/api/bot/login') {
    // Token expired or invalid — clear and redirect
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('bot_token');
      sessionStorage.removeItem('bot_user');
    }
    throw new Error('AUTH_REQUIRED');
  }

  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export function createWebSocket(path: string): WebSocket {
  const wsBase = API_BASE.replace('http', 'ws');
  return new WebSocket(`${wsBase}${path}`);
}

export function isAuthenticated(): boolean {
  if (typeof window === 'undefined') return false;
  return !!sessionStorage.getItem('bot_token');
}

export function getUsername(): string {
  if (typeof window === 'undefined') return '';
  return sessionStorage.getItem('bot_user') || '';
}

export function logout(): void {
  if (typeof window !== 'undefined') {
    sessionStorage.removeItem('bot_token');
    sessionStorage.removeItem('bot_user');
  }
}
