import { createContext, useContext, useState, useCallback } from 'react';
import { jwtDecode } from 'jwt-decode';

const STORAGE_KEY = 'lexi_auth_user';
const AuthContext = createContext(null);

function loadStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(loadStoredUser);

  const persistUser = useCallback((nextUser) => {
    setUser(nextUser);
    try {
      if (nextUser) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(nextUser));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // Ignore storage quota / privacy mode errors
    }
  }, []);

  const signIn = useCallback(
    (credential) => {
      const decoded = jwtDecode(credential);
      persistUser({
        name: decoded.name || 'User',
        email: decoded.email || '',
        picture: decoded.picture || '',
        token: credential,
        guest: false,
      });
    },
    [persistUser]
  );

  const continueAsGuest = useCallback(() => {
    persistUser({
      name: 'Guest',
      email: '',
      picture: '',
      token: null,
      guest: true,
    });
  }, [persistUser]);

  const signOut = useCallback(() => {
    persistUser(null);
  }, [persistUser]);

  return (
    <AuthContext.Provider value={{ user, signIn, continueAsGuest, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return ctx;
}
