import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL;

if (!API_BASE_URL) {
  throw new Error('VITE_API_URL is not configured. Create sana-panel/.env before starting the frontend.');
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// درخواست‌های هم‌زمان فقط یک بار توکن را تمدید می‌کنند.
let refreshInFlight = null;

export function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refreshToken = localStorage.getItem('sana_refresh_token');
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

      localStorage.setItem('sana_access_token', access);
      return access;
    })().finally(() => {
      refreshInFlight = null;
    });
  }

  return refreshInFlight;
}

export function clearAuthSession() {
  localStorage.removeItem('sana_access_token');
  localStorage.removeItem('sana_refresh_token');
  localStorage.removeItem('sana_user');
  window.location.href = '/login';
}

// Interceptor برای افزودن توکن به همه درخواست‌ها
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('sana_access_token');
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
      if ([401, 403].includes(refreshError.response?.status)) {
        clearAuthSession();
      }
      return Promise.reject(refreshError);
    }
  }
);

export default apiClient;
