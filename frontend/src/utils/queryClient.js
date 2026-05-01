/**
 * Единый QueryClient на всё приложение.
 * Настройки кэша подобраны под наш UX:
 *   - staleTime: 30с — короткие запросы (счётчики, списки) не дёргают API без нужды
 *   - cacheTime (gcTime): 5мин — оставляем данные в памяти при переходах между страницами
 *   - retry: 1 — на 401/мистике перезапросов не делаем агрессивно
 */
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      gcTime:    5 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});
