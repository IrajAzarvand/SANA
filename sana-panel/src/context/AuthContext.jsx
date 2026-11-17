import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI } from '../api/services/auth';
import { getAuthStorage, setAuthItem, saveAuthSession, clearAuthData } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // بازیابی نشست از محل ذخیره‌سازی انتخاب‌شده هنگام ورود
  useEffect(() => {
    const init = async () => {
      try {
        const storage = getAuthStorage();
        const accessToken = storage.getItem('sana_access_token');
        const savedUser = storage.getItem('sana_user');

        if (!accessToken || !savedUser) return;

        let cachedUser;
        try {
          cachedUser = JSON.parse(savedUser);
        } catch {
          clearAuthData();
          return;
        }

        // اطلاعات ذخیره‌شده تا زمان پاسخ سرور، هویت کاربر را حفظ می‌کند.
        setUser(cachedUser);

        try {
          const freshUser = await authAPI.me();
          setUser(freshUser);
          setAuthItem('sana_user', JSON.stringify(freshUser));
        } catch (error) {
          // فقط پاسخ قطعیِ رد شدن اعتبارنامه، نشست محلی را باطل می‌کند.
          // خطای شبکه یا اختلال موقت سرور نباید کاربر را از حساب خارج کند.
          if ([400, 401, 403].includes(error.response?.status)) {
            clearAuthData();
            setUser(null);
          }
        }
      } finally {
        setLoading(false);
      }
    };

    init();
  }, []);

  const login = async (username, password, remember = false) => {
    const data = await authAPI.login(username, password);
    saveAuthSession(data, remember);
    setUser(data.user);
    return data.user;
  };

  const updateUser = useCallback((updatedUser) => {
    setUser(updatedUser);
    setAuthItem('sana_user', JSON.stringify(updatedUser));
  }, []);

  const logout = useCallback(async ({ revokeServer = true } = {}) => {
    try {
      if (revokeServer) {
        await authAPI.logout();
      }
    } catch {
      // Local credentials must be cleared even if the server is unreachable.
    } finally {
      clearAuthData();
      setUser(null);
      window.location.href = '/login';
    }
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
      user, loading, login, logout, updateUser,
      isSiteAdmin, isMainUser, isBranchManager, isPersonal, isOrganization,
      can,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

// The context hook is exported alongside its provider by design.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}