const LOCAL_API_BASE_URL = 'http://localhost:8000';
const PRODUCTION_API_BASE_URL = 'https://evolvingai.flobots.xyz/api';
const STALE_API_HOSTS = [
  'katbot.atlasfoundation.app',
  'ae5460180c1d.ngrok-free.app'
];

function getApiBaseUrl() {
  const configuredUrl = import.meta.env.VITE_API_BASE_URL;

  if (configuredUrl && !STALE_API_HOSTS.some((host) => configuredUrl.includes(host))) {
    return configuredUrl;
  }

  return import.meta.env.DEV ? LOCAL_API_BASE_URL : PRODUCTION_API_BASE_URL;
}

export const API_BASE_URL = getApiBaseUrl();

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
