import apiClient from '../client';

export const organizationsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/organizations/', { params });
    return response.data;
  },

  get: async (id) => {
    const response = await apiClient.get(`/organizations/${id}/`);
    return response.data;
  },

  create: async (data) => {
    const response = await apiClient.post('/organizations/', data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await apiClient.put(`/organizations/${id}/`, data);
    return response.data;
  },

  delete: async (id) => {
    await apiClient.delete(`/organizations/${id}/`);
  },
};

export const branchesAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/branches/', { params });
    return response.data;
  },

  get: async (id) => {
    const response = await apiClient.get(`/branches/${id}/`);
    return response.data;
  },

  create: async (data) => {
    const response = await apiClient.post('/branches/', data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await apiClient.put(`/branches/${id}/`, data);
    return response.data;
  },

  delete: async (id) => {
    await apiClient.delete(`/branches/${id}/`);
  },
};
