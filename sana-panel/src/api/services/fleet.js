import apiClient from '../client';

export const vehiclesAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/vehicles/', { params });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/vehicles/${id}/`);
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/vehicles/', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.put(`/vehicles/${id}/`, data);
    return response.data;
  },
  delete: async (id) => {
    await apiClient.delete(`/vehicles/${id}/`);
  },
};

export const deviceLifecycleAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/device-lifecycle-events/', { params });
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/device-lifecycle-events/', data);
    return response.data;
  },
};

export const devicesAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/devices/', { params });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/devices/${id}/`);
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/devices/', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.put(`/devices/${id}/`, data);
    return response.data;
  },
  delete: async (id) => {
    await apiClient.delete(`/devices/${id}/`);
  },
};

export const deviceModelsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/device-models/', { params });
    return response.data;
  },
};

export const driversAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/drivers/', { params });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/drivers/${id}/`);
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/drivers/', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.put(`/drivers/${id}/`, data);
    return response.data;
  },
  delete: async (id) => {
    await apiClient.delete(`/drivers/${id}/`);
  },
};

export const vehicleTypesAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/vehicle-types/', { params });
    return response.data;
  },
};

export const usersAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/users/', { params });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/users/${id}/`);
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/users/', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.patch(`/users/${id}/`, data);
    return response.data;
  },
  delete: async (id) => {
    await apiClient.delete(`/users/${id}/`);
  },
};


export const deviceReplacementAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/device-replacement-relations/', { params });
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/device-replacement-relations/', data);
    return response.data;
  },
};


export const deviceOperationsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/device-operations/', { params });
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/device-operations/', data);
    return response.data;
  },
};
