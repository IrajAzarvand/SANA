import apiClient from '../client';

export const deviceModelsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/device-models/', { params });
    return response.data;
  },

  get: async (id) => {
    const response = await apiClient.get(`/device-models/${id}/`);
    return response.data;
  },

  create: async (data) => {
    const response = await apiClient.post('/device-models/', data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await apiClient.patch(`/device-models/${id}/`, data);
    return response.data;
  },

  delete: async (id) => {
    await apiClient.delete(`/device-models/${id}/`);
  },
};