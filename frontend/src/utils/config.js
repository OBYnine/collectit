// Единые константы API. Использовать вместо дубликатов API_BASE по страницам.

// Полный URL API (с /api на конце), например: http://127.0.0.1:8000/api.
// В Docker/nginx используется относительный /api, чтобы cookie и WebSocket были same-origin.
export const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000/api';

// Корень сервера (без /api) — для построения ссылок на /media/... файлы.
export const API_BASE = API_URL.replace(/\/api\/?$/, '');

// WebSocket-корень. Для относительного API берём текущий origin браузера.
function getWsBase() {
  if (/^https?:\/\//.test(API_BASE)) {
    return API_BASE.replace(/^http/, 'ws');
  }
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}${API_BASE}`;
  }
  return API_BASE;
}

export const WS_BASE = getWsBase();

// Построить абсолютный URL к файлу. Возвращает null для пустых значений,
// не трогает уже абсолютные ссылки (http/https/data).
export function mediaUrl(path) {
  if (!path) return null;
  if (/^(https?:|data:)/.test(path)) return path;
  return `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
}
