import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI } from '../api/services/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // بارگذاری اولیه از localStorage
  useEffect(() => {
    const init = async () => {
      const accessToken = localStorage.getItem('sana_access_token');
      const savedUser = localStorage.getItem('sana_user');

      if (accessToken && savedUser) {
        try {
          setUser(JSON.parse(savedUser));

          // اعتبارسنجی توکن با API
          const freshUser = await authAPI.me();
          setUser(freshUser);
          localStorage.setItem('sana_user', JSON.stringify(freshUser));
        } catch (e) {
          // توکن منقضی یا خطا
          localStorage.removeItem('sana_access_token');
          localStorage.removeItem('sana_refresh_token');
          localStorage.removeItem('sana_user');
          setUser(null);
        }
      }
      setLoading(false);
    };

    init();
  }, []);

  const login = async (username, password) => {
    const data = await authAPI.login(username, password);
    localStorage.setItem('sana_access_token', data.access);
    localStorage.setItem('sana_refresh_token', data.refresh);
    localStorage.setItem('sana_user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = useCallback(() => {
    localStorage.removeItem('sana_access_token');
    localStorage.removeItem('sana_refresh_token');
    localStorage.removeItem('sana_user');
    setUser(null);
    window.location.href = '/login';
  }, []);

  // helperها
  const isSiteAdmin     = user?.role === 'site_admin';
  const isMainUser      = user?.role === 'main_user';
  const isBranchManager = user?.role === 'branch_manager';
  const isPersonal      = user?.role === 'personal_user';
  const isOrganization  = user?.account_type === 'organization';

  // Permissions بر اساس نقش
  const getPermissions = (role) => {
    switch (role) {
      case 'site_admin':
        return ['view', 'create', 'edit', 'delete', 'manage_branches', 'manage_users', 'manage_devices', 'manage_companies'];
      case 'main_user':
        return ['view', 'edit', 'manage_branches', 'manage_branch_users'];
      case 'branch_manager':
        return ['view', 'edit'];
      case 'personal_user':
        return ['view'];
      default:
        return [];
    }
  };

  const can = (permission) => {
    if (!user) return false;
    return getPermissions(user.role).includes(permission);
  };

  return (
    <AuthContext.Provider value={{
      user, loading, login, logout,
      isSiteAdmin, isMainUser, isBranchManager, isPersonal, isOrganization,
      can,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}