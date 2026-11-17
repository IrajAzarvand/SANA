import axios from 'axios';

// API URL is configured per environment.
// Development defaults to the local backend; production defaults to same-origin.
const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://192.168.1.132:8000/api' : '/api');

const AUTH_KEYS = ['sana_access_token', 'sana_refresh_token', 'sana_user'];

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// نشست موقت در sessionStorage و نشست ماندگار در localStorage نگهداری می‌شود.
export function getAuthStorage() {
  if (
    sessionStorage.getItem('sana_access_token') ||
    sessionStorage.getItem('sana_refresh_token')
  ) {
    return sessionStorage;
  }
  return localStorage;
}

export function getAuthToken() {
  return getAuthStorage().getItem('sana_access_token');
}

export function setAuthItem(key, value) {
  getAuthStorage().setItem(key, value);
}

export function clearAuthData() {
  for (const storage of [localStorage, sessionStorage]) {
    AUTH_KEYS.forEach((key) => storage.removeItem(key));
  }
}

export function saveAuthSession(data, remember) {
  clearAuthData();
  const storage = remember ? localStorage : sessionStorage;
  storage.setItem('sana_access_token', data.access);
  storage.setItem('sana_refresh_token', data.refresh);
  storage.setItem('sana_user', JSON.stringify(data.user));
}

// درخواست‌های هم‌زمان فقط یک بار توکن را تمدید می‌کنند.
let refreshInFlight = null;

export function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const storage = getAuthStorage();
      const refreshToken = storage.getItem('sana_refresh_token');
      if (!refreshToken) {
        throw new Error('No refresh token');
      }

      const response = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
        refresh: refreshToken,
      });
      const access = response.data?.access;
      if (!access) {
        throw new Error('Refresh response did not contain an access token');
      }

      storage.setItem('sana_access_token', access);
      if (response.data?.refresh) {
        storage.setItem('sana_refresh_token', response.data.refresh);
      }
      return access;
    })().finally(() => {
      refreshInFlight = null;
    });
  }

  return refreshInFlight;
}

export function clearAuthSession() {
  clearAuthData();
  window.location.href = '/login';
}

// Interceptor برای افزودن توکن به همه درخواست‌ها
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor برای مدیریت خطای 401 (توکن منقضی)
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      originalRequest.url?.includes('/auth/refresh/')
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;
    try {
      const access = await refreshAccessToken();
      originalRequest.headers = originalRequest.headers || {};
      originalRequest.headers.Authorization = `Bearer ${access}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      // فقط رد شدن قطعی Refresh Token به معنی پایان نشست است؛
      // خطای شبکه نباید کاربر را به‌اشتباه از پنل خارج کند.
      if ([401, 403].includes(refreshError.response?.status) || refreshError.message === 'No refresh token') {
        clearAuthSession();
      }
      return Promise.reject(refreshError);
    }
  }
);

export default apiClient;
