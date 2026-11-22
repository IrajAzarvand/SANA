import apiClient, { getAuthToken } from '../client';

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

export const deviceModelsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/device-models/', { params });
    return response.data;
  },
};

export const alertsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/devices/alerts/', { params });
    return response.data;
  },
  preferences: async () => {
    const response = await apiClient.get('/devices/alert-preferences/');
    return response.data;
  },
  updatePreferences: async (data) => {
    const response = await apiClient.put('/devices/alert-preferences/', data);
    return response.data;
  },
  updateStatus: async ({ deviceId, eventId, status }) => {
    const response = await apiClient.post('/devices/alerts/', {
      device_id: deviceId,
      event_id: eventId,
      status,
    });
    return response.data;
  },
  markAllRead: async () => {
    const response = await apiClient.post('/devices/alerts/', { mark_all: true });
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
  delete: async (id, confirmImei) => {
    await apiClient.delete(`/devices/${id}/`, {
      data: { confirm_imei: confirmImei },
    });
  },
  mapPositions: async () => {
    const response = await apiClient.get('/devices/map-positions/');
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

export const driverVehicleAssignmentsAPI = {
  list: async (params = {}) => {
    const response = await apiClient.get('/driver-vehicle-assignments/', { params });
    return response.data;
  },
  get: async (id) => {
    const response = await apiClient.get(`/driver-vehicle-assignments/${id}/`);
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/driver-vehicle-assignments/', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.patch(`/driver-vehicle-assignments/${id}/`, data);
    return response.data;
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
  checkUsername: async (username) => {
    const response = await apiClient.get('/users/username-availability/', {
      params: { username },
    });
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
  archive: async (id) => {
    const response = await apiClient.post(`/users/${id}/archive/`);
    return response.data;
  },
  restore: async (id) => {
    const response = await apiClient.post(`/users/${id}/restore/`);
    return response.data;
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

export const panelNotificationsAPI = {
  list: async () => {
    const response = await apiClient.get('/users/notifications/');
    return response.data;
  },
  markRead: async (eventKey) => {
    const response = await apiClient.post('/users/notifications/', { event_key: eventKey });
    return response.data;
  },
  markAllRead: async () => {
    const response = await apiClient.post('/users/notifications/', { mark_all: true });
    return response.data;
  },
};

// All notification surfaces share one request/cache so the bell and inbox
// cannot independently exhaust the per-user alert throttle.
const NOTIFICATION_CACHE_TTL_MS = 11000;
let notificationCache = null;
let notificationCacheAt = 0;
let notificationCacheToken = null;
let notificationRequest = null;

function updateCachedNotificationFeed(feedName, updater) {
  if (!notificationCache || notificationCache[feedName]?.status !== 'fulfilled') return;
  const feed = notificationCache[feedName];
  const value = feed.value || {};
  const results = Array.isArray(value.results) ? value.results : [];
  notificationCache = {
    ...notificationCache,
    [feedName]: {
      ...feed,
      value: { ...value, results: updater(results) },
    },
  };
}

function setCachedFeedRead(feedName, predicate) {
  updateCachedNotificationFeed(feedName, (results) => results.map((item) => (
    predicate(item) ? { ...item, is_read: true, status: item.status === 'unread' ? 'read' : item.status } : item
  )));
}

// Shared notification client: source feeds remain separate, workflow actions are centralized.
export const notificationsAPI = {
  list: async () => {
    const token = getAuthToken();
    if (token !== notificationCacheToken) {
      notificationCache = null;
      notificationRequest = null;
      notificationCacheAt = 0;
      notificationCacheToken = token;
    }

    if (notificationRequest) return notificationRequest;
    if (notificationCache && Date.now() - notificationCacheAt < NOTIFICATION_CACHE_TTL_MS) {
      if (notificationCache.businessResult.status === 'rejected' && notificationCache.gpsResult.status === 'rejected') {
        throw new Error('notification feeds unavailable');
      }
      return notificationCache;
    }

    notificationCacheAt = Date.now();
    notificationRequest = (async () => {
      const [businessResult, gpsResult] = await Promise.allSettled([
        panelNotificationsAPI.list(),
        alertsAPI.list(),
      ]);
      const result = { businessResult, gpsResult };
      if (getAuthToken() === token) {
        notificationCache = result;
        notificationCacheAt = Date.now();
      }
      if (businessResult.status === 'rejected' && gpsResult.status === 'rejected') {
        throw new Error('notification feeds unavailable');
      }
      return result;
    })().finally(() => {
      if (notificationCacheToken === token) notificationRequest = null;
    });
    return notificationRequest;
  },
  markRead: async ({ isGps, eventKey, deviceId, eventId }) => {
    const result = isGps
      ? await alertsAPI.updateStatus({ deviceId, eventId, status: 'read' })
      : await panelNotificationsAPI.markRead(eventKey);
    if (isGps) {
      setCachedFeedRead('gpsResult', (item) => String(item.device_id) === String(deviceId) && String(item.id) === String(eventId));
    } else {
      setCachedFeedRead('businessResult', (item) => String(item.id) === String(eventKey));
    }
    return result;
  },
  updateGpsStatus: async ({ deviceId, eventId, status }) => {
    const result = await alertsAPI.updateStatus({ deviceId, eventId, status });
    updateCachedNotificationFeed('gpsResult', (results) => results.map((item) => (
      String(item.device_id) === String(deviceId) && String(item.id) === String(eventId)
        ? { ...item, status, is_read: true }
        : item
    )));
    return result;
  },
  markAllRead: async () => {
    const results = await Promise.allSettled([
      panelNotificationsAPI.markAllRead(),
      alertsAPI.markAllRead(),
    ]);
    if (results[0].status === 'fulfilled') {
      setCachedFeedRead('businessResult', () => true);
    }
    if (results[1].status === 'fulfilled') {
      setCachedFeedRead('gpsResult', () => true);
    }
    return results;
  },
};
