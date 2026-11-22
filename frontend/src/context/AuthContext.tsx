import React, { createContext, useContext, useState, useEffect } from 'react';
import type { UserRole } from '../types';
import { api } from '../api/client';

export interface CurrentUser {
  actor_id: string;
  role: string;
  organization_id?: string;
  name: string;
}

interface AuthContextType {
  activeActor: UserRole;
  setActiveActor: (role: UserRole) => void;
  token: string | null;
  isAuthenticated: boolean;
  currentUser: CurrentUser | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  language: 'bn-IN' | 'hi-IN' | 'en-IN';
  setLanguage: (lang: 'bn-IN' | 'hi-IN' | 'en-IN') => void;
  devMode: boolean;
  setDevMode: (enabled: boolean) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem('gramsetu_token');
  });

  const [activeActor, setActiveActorState] = useState<UserRole>(() => {
    return (localStorage.getItem('gramsetu_active_actor') as UserRole) || 'fpo_admin';
  });

  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(() => {
    const cached = localStorage.getItem('gramsetu_user_info');
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch {
        return null;
      }
    }
    return null;
  });

  const [language, setLanguageState] = useState<'bn-IN' | 'hi-IN' | 'en-IN'>(() => {
    return (localStorage.getItem('gramsetu_language') as 'bn-IN' | 'hi-IN' | 'en-IN') || 'en-IN';
  });

  const [devMode, setDevModeState] = useState<boolean>(() => {
    return localStorage.getItem('gramsetu_dev_mode') !== 'false';
  });

  const setActiveActor = (role: UserRole) => {
    setActiveActorState(role);
    localStorage.setItem('gramsetu_active_actor', role);
  };

  const setLanguage = (lang: 'bn-IN' | 'hi-IN' | 'en-IN') => {
    setLanguageState(lang);
    localStorage.setItem('gramsetu_language', lang);
  };

  const setDevMode = (enabled: boolean) => {
    setDevModeState(enabled);
    localStorage.setItem('gramsetu_dev_mode', enabled ? 'true' : 'false');
  };

  const login = async (username: string, password: string) => {
    const data = await api.login({ username, password });
    if (data.access_token) {
      setToken(data.access_token);
      localStorage.setItem('gramsetu_token', data.access_token);

      const role = (data.role ? data.role.toLowerCase() : 'fpo_admin') as UserRole;
      setActiveActor(role);

      const userInfo: CurrentUser = {
        actor_id: data.actor_id,
        role: data.role,
        organization_id: data.organization_id,
        name: data.name || username,
      };
      setCurrentUser(userInfo);
      localStorage.setItem('gramsetu_user_info', JSON.stringify(userInfo));
    }
  };

  const logout = () => {
    setToken(null);
    setCurrentUser(null);
    localStorage.removeItem('gramsetu_token');
    localStorage.removeItem('gramsetu_user_info');
  };

  // Check current profile on mount if token exists
  useEffect(() => {
    if (token && !currentUser) {
      api.getMe()
        .then((res) => {
          setCurrentUser(res);
          localStorage.setItem('gramsetu_user_info', JSON.stringify(res));
        })
        .catch(() => {
          // Token expired or invalid
          logout();
        });
    }
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        activeActor,
        setActiveActor,
        token,
        isAuthenticated: !!token || devMode,
        currentUser,
        login,
        logout,
        language,
        setLanguage,
        devMode,
        setDevMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
