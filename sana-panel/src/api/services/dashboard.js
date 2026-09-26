import apiClient from '../client';

export const dashboardAPI = {
  getStats: async () => {
    const response = await apiClient.get('/dashboard/stats/');
    return response.data;
  },
};
