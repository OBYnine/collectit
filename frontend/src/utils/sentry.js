/**
 * Опциональная инициализация Sentry на фронте.
 * Без REACT_APP_SENTRY_DSN — модуль ничего не делает (no-op).
 */
import * as Sentry from '@sentry/react';

export function initSentry() {
  const dsn = process.env.REACT_APP_SENTRY_DSN;
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: process.env.REACT_APP_SENTRY_ENV || process.env.NODE_ENV,
    tracesSampleRate: Number(process.env.REACT_APP_SENTRY_TRACES_RATE || 0.1),
    // Не пишем PII по умолчанию.
    sendDefaultPii: false,
  });
}

export { Sentry };
