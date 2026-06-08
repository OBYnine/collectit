import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getMe, isAuthenticated } from '../api/client';

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);

  const refreshUser = useCallback(async () => {
    if (!isAuthenticated()) {
      setUser(null);
      return null;
    }

    try {
      const data = await getMe();
      if (data && data.id) {
        setUser(data);
        return data;
      }
    } catch {}

    return null;
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

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
