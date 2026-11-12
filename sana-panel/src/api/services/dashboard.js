import apiClient from '../client';

export const dashboardAPI = {
  getAdminOverview: async () => {\n    const response = await apiClient.get('/dashboard/admin-overview/');\n    return response.data;\n  },\n  getStats: async () => {
    const response = await apiClient.get('/dashboard/stats/');
    return response.data;
  },
};
