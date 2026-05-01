import { useEffect, useState } from 'react';

// Возвращает значение через delay мс после последнего обновления.
// Использовать для поисковых инпутов: не дёргаем API на каждый символ.
export function useDebounce(value, delay = 350) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
