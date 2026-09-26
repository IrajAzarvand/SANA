import apiClient from '../client';

export const subscriptionsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/subscriptions/', { params });
    return response.data;
  },

  get: async (id) => {
    const response = await apiClient.get(`/subscriptions/${id}/`);
    return response.data;
  },

  create: async (data) => {
    const response = await apiClient.post('/subscriptions/', data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await apiClient.patch(`/subscriptions/${id}/`, data);
    return response.data;
  },

  delete: async (id) => {
    await apiClient.delete(`/subscriptions/${id}/`);
  },

  renew: async (id, data) => {
    const response = await apiClient.post(`/subscriptions/${id}/renew/`, data);
    return response.data;
  },

  suspend: async (id) => {
    const response = await apiClient.post(`/subscriptions/${id}/suspend/`);
    return response.data;
  },

  activate: async (id) => {
    const response = await apiClient.post(`/subscriptions/${id}/activate/`);
    return response.data;
  },

  cancel: async (id) => {
    const response = await apiClient.post(`/subscriptions/${id}/cancel/`);
    return response.data;
  },

  getNextNumber: async (customerType = 'organization') => {
    const response = await apiClient.get('/subscriptions/next_number/', {
      params: { type: customerType },
    });
    return response.data;
  },
};

export const subscriptionDevicesAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/subscription-devices/', { params });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/subscription-devices/${id}/`);
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/subscription-devices/', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.patch(`/subscription-devices/${id}/`, data);
    return response.data;
  },
  delete: async (id) => {
    await apiClient.delete(`/subscription-devices/${id}/`);
  },
};

export const subscriptionPaymentsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/subscription-payments/', { params });
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/subscription-payments/', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.patch(`/subscription-payments/${id}/`, data);
    return response.data;
  },
  delete: async (id) => {
    await apiClient.delete(`/subscription-payments/${id}/`);
  },
};