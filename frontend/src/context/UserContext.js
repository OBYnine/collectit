import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getMe, isAuthenticated } from '../api/client';

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);

  const refreshUser = useCallback(async () => {
    if (!isAuthenticated()) return;
    try {
      const data = await getMe();
      // getMe() возвращает либо объект профиля, либо ошибку. Если бэкенд вернул
      // что-то странное (например, {detail: '...'}) — не подменяем user.
      if (data && data.id) setUser(data);
    } catch {}
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  // Обновляем баланс после оплаты из чата
  useEffect(() => {
    window.addEventListener('balance-updated', refreshUser);
    return () => window.removeEventListener('balance-updated', refreshUser);
  }, [refreshUser]);

  return (
    <UserContext.Provider value={{ user, setUser, refreshUser }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
