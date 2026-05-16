const LOCAL_API_BASE_URL = 'http://localhost:8000';

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? LOCAL_API_BASE_URL : '/api');

export function getWebSocketUrl(path = '/ws/status') {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  if (API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://')) {
    const url = new URL(API_BASE_URL);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = `${url.pathname.replace(/\/$/, '')}${normalizedPath}`;
    url.search = '';
    url.hash = '';
    return url.toString();
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${wsProtocol}//${window.location.host}${normalizedPath}`;
}
