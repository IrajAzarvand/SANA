import apiClient from '../client';

export const authAPI = {
  login: async (username, password) => {
    const response = await apiClient.post('/auth/login/', { username, password });
    return response.data;
  },

  refresh: async (refreshToken) => {
    const response = await apiClient.post('/auth/refresh/', { refresh: refreshToken });
    return response.data;
  },

  me: async () => {
    const response = await apiClient.get('/users/me/');
    return response.data;
  },

  changePassword: async (oldPassword, newPassword) => {
    const response = await apiClient.post('/users/change_password/', {
      old_password: oldPassword,
      new_password: newPassword,
    });
    return response.data;
  },
};
