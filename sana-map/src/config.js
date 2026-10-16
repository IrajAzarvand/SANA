export const MAP_PROVIDER = import.meta.env.VITE_MAP_PROVIDER || 'leaflet-osm';

export const NESHAN_LEAFLET_CONFIG = {
  apiKey: import.meta.env.VITE_NESHAN_API_KEY || '',
  mapType: import.meta.env.VITE_NESHAN_MAP_TYPE || 'dreamy',
  center: [32.4279, 53.688],
  zoom: 5,
};

export const MAP_PROVIDERS = {
  LEAFLET_OSM: 'leaflet-osm',
  NESHAN_LEAFLET: 'neshan-leaflet',
};
