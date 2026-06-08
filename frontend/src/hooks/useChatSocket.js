/**
 * WebSocket-подписка на чат. Заменяет HTTP polling 3с.
 *
 * Бэкенд: chats/consumers.py + chats/routing.py
 *   ws(s)://host/ws/chats/<chatId>/
 * Auth: httpOnly cookie access_token.
 *
 * Возвращает:
 *   - socketReady: boolean (есть открытое соединение)
 *   - sendMessage(text): отправить через WS (fallback на HTTP — в вызывающем коде)
 *
 * События приходят в onMessage:
 *   { type: 'message.created', message: {...} }
 *   { type: 'chat.updated', chat: {...} }
 */
import { useEffect, useRef, useState } from 'react';
import { WS_BASE } from '../utils/config';

const RECONNECT_BASE_MS = 1500;
const RECONNECT_MAX_MS  = 15000;

export function useChatSocket(chatId, onMessage) {
  const [socketReady, setSocketReady] = useState(false);
  const wsRef         = useRef(null);
  const reconnectRef  = useRef(0);    // количество последовательных reconnect-ов
  const reconnectTRef = useRef(null); // setTimeout id
  const closedRef     = useRef(false);
  const cbRef         = useRef(onMessage);

  // Сохраняем последний колбэк, чтобы не пересоздавать сокет при смене onMessage.
  useEffect(() => { cbRef.current = onMessage; }, [onMessage]);

  useEffect(() => {
    if (!chatId) return undefined;
    closedRef.current = false;

    function connect() {
      const url = `${WS_BASE}/ws/chats/${chatId}/`;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectRef.current = 0;
        setSocketReady(true);
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          cbRef.current?.(data);
        } catch {}
      };

      ws.onerror = () => { /* swallow — onclose всё равно сработает */ };

      ws.onclose = () => {
        setSocketReady(false);
        if (closedRef.current) return;
        // Экспоненциальный backoff с верхним порогом.
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
  }, [chatId]);

  function sendMessage(text) {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    try {
      ws.send(JSON.stringify({ type: 'message', text }));
      return true;
    } catch {
      return false;
    }
  }

  function markRead() {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    try {
      ws.send(JSON.stringify({ type: 'read' }));
      return true;
    } catch {
      return false;
    }
  }

  return { socketReady, sendMessage, markRead };
}
