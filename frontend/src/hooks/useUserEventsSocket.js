import { useEffect, useRef, useState } from 'react';
import { WS_BASE } from '../utils/config';

const RECONNECT_BASE_MS = 1500;
const RECONNECT_MAX_MS = 15000;

export function useUserEventsSocket(enabled, onEvent) {
  const [socketReady, setSocketReady] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(0);
  const reconnectTRef = useRef(null);
  const closedRef = useRef(false);
  const cbRef = useRef(onEvent);

  useEffect(() => { cbRef.current = onEvent; }, [onEvent]);

  useEffect(() => {
    if (!enabled) return undefined;
    closedRef.current = false;

    function connect() {
      const token = localStorage.getItem('access_token') || '';
      const qs = token ? `?token=${encodeURIComponent(token)}` : '';
      const ws = new WebSocket(`${WS_BASE}/ws/notifications/${qs}`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectRef.current = 0;
        setSocketReady(true);
      };

      ws.onmessage = (event) => {
        try {
          cbRef.current?.(JSON.parse(event.data));
        } catch {}
      };

      ws.onerror = () => {};

      ws.onclose = () => {
        setSocketReady(false);
        if (closedRef.current) return;
        reconnectRef.current += 1;
        const delay = Math.min(
          RECONNECT_BASE_MS * Math.pow(2, reconnectRef.current - 1),
          RECONNECT_MAX_MS,
        );
        reconnectTRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      closedRef.current = true;
      if (reconnectTRef.current) clearTimeout(reconnectTRef.current);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch {}
      }
    };
  }, [enabled]);

  return { socketReady };
}
