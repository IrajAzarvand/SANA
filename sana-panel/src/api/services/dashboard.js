import apiClient from '../client';

export const dashboardAPI = {
  getAdminOverview: async () => {
    const response = await apiClient.get('/dashboard/admin-overview/');
    return response.data;
  },
  getStats: async () => {
    const response = await apiClient.get('/dashboard/stats/');
    return response.data;
  },
};
