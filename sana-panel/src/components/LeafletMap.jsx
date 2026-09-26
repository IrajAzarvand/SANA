import { useEffect, useRef } from 'react';
import { mapStatusColors } from '../data/mapData';
import { getMarkerIcon } from '../data/markerIcons';

const NESHAN_API_KEY = import.meta.env.VITE_NESHAN_API_KEY;

// ساخت آیکون مارکر با PNG + هاله رنگی
function createMarkerIcon(L, status) {
  const color = mapStatusColors[status]?.color || '#64748B';
  const iconUrl = getMarkerIcon(status);

  const html = `
    <div style="position: relative; width: 48px; height: 48px;">
      <div style="
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: ${color}30;
        box-shadow: 0 0 0 2px ${color}50, 0 0 20px ${color}40;
        animation: ${status === 'moving' ? 'marker-pulse 2s ease-in-out infinite' : 'none'};
      "></div>
      <img
        src="${iconUrl}"
        alt="${status}"
        style="
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 36px;
          height: 36px;
          object-fit: contain;
          filter: drop-shadow(0 2px 6px rgba(0,0,0,0.5));
        "
      />
    </div>
  `;

  return L.divIcon({
    html,
    className: 'custom-marker-png',
    iconSize: [48, 48],
    iconAnchor: [24, 24],
    popupAnchor: [0, -24],
  });
}

function createEndpointIcon(L, color, label) {
  const svg = `
    <svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <circle cx="16" cy="16" r="12" fill="${color}" stroke="#0B1220" stroke-width="3"/>
      <text x="16" y="21" text-anchor="middle" font-family="Vazirmatn" font-size="12" font-weight="bold" fill="#0B1220">${label}</text>
    </svg>
  `;
  return L.divIcon({
    html: svg,
    className: 'endpoint-marker',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

export default function LeafletMap({
  vehicles,
  selectedId,
  onSelect,
  center = [35.6892, 51.3890],
  zoom = 11,
  fitAll = false,
  showPath = null,
  onPathClose,
}) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({});
  const pathLayerRef = useRef(null);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const initMap = () => {
      if (!window.L) {
        console.error('Neshan Leaflet SDK لود نشد');
        return;
      }

      const L = window.L;

      const map = new L.Map(mapRef.current, {
        key: NESHAN_API_KEY,
        maptype: 'dreamy',
        center: center,
        zoom: zoom,
        zoomControl: false,
      });

      L.control.zoom({ position: 'topleft' }).addTo(map);
      mapInstanceRef.current = map;

      updateMarkers(L, map, vehicles, selectedId, onSelect, markersRef);
    };

    if (window.L) {
      initMap();
    } else {
      let tries = 0;
      const interval = setInterval(() => {
        tries++;
        if (window.L) {
          clearInterval(interval);
          initMap();
        } else if (tries > 100) {
          clearInterval(interval);
          console.error('Neshan SDK بعد از ۱۰ ثانیه لود نشد');
        }
      }, 100);
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
      markersRef.current = {};
      pathLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;
    if (!fitAll && !showPath) {
      map.setView(center, zoom);
    }
  }, [center, zoom, fitAll, showPath]);

  useEffect(() => {
    const L = window.L;
    const map = mapInstanceRef.current;
    if (!L || !map) return;

    if (fitAll && vehicles.length > 0 && !showPath) {
      const bounds = L.latLngBounds(vehicles.map((v) => [v.lat, v.lng]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 });
    }
  }, [fitAll, vehicles, showPath]);

  useEffect(() => {
    const L = window.L;
    const map = mapInstanceRef.current;
    if (!L || !map) return;
    updateMarkers(L, map, vehicles, selectedId, onSelect, markersRef);
  }, [vehicles, selectedId, onSelect]);

  // رسم یا پاک کردن مسیر
  useEffect(() => {
    const L = window.L;
    const map = mapInstanceRef.current;
    if (!L || !map) return;

    if (pathLayerRef.current) {
      pathLayerRef.current.forEach((layer) => layer.remove());
      pathLayerRef.current = null;
    }

    if (!showPath || !showPath.path || showPath.path.length < 2) return;

    const layers = [];
    const pathCoords = showPath.path.map((p) => [p.lat, p.lng]);
    const color = showPath.color || '#14B8A6';

    const polyline = L.polyline(pathCoords, {
      color: color,
      weight: 4,
      opacity: 0.9,
      lineJoin: 'round',
      lineCap: 'round',
    }).addTo(map);
    layers.push(polyline);

    const haloLine = L.polyline(pathCoords, {
      color: color,
      weight: 10,
      opacity: 0.2,
      lineJoin: 'round',
      lineCap: 'round',
    }).addTo(map);
    layers.push(haloLine);
    haloLine.bringToBack();

    const startPoint = pathCoords[0];
    const startMarker = L.marker(startPoint, {
      icon: createEndpointIcon(L, '#10B981', '▶'),
      zIndexOffset: 500,
    }).addTo(map);
    layers.push(startMarker);

    const endPoint = pathCoords[pathCoords.length - 1];
    const endMarker = L.marker(endPoint, {
      icon: createEndpointIcon(L, '#EF4444', '■'),
      zIndexOffset: 500,
    }).addTo(map);
    layers.push(endMarker);

    const bounds = L.latLngBounds(pathCoords);
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 14 });

    pathLayerRef.current = layers;
  }, [showPath]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !selectedId || showPath) return;
    const vehicle = vehicles.find((v) => v.id === selectedId);
    if (vehicle) {
      map.setView([vehicle.lat, vehicle.lng], 14, { animate: true });
    }
  }, [selectedId, vehicles, showPath]);

  return <div ref={mapRef} className="w-full h-full" />;
}

function updateMarkers(L, map, vehicles, selectedId, onSelect, markersRef) {
  const currentIds = new Set(vehicles.map((v) => v.id));

  Object.keys(markersRef.current).forEach((id) => {
    if (!currentIds.has(Number(id))) {
      markersRef.current[id].remove();
      delete markersRef.current[id];
    }
  });

  vehicles.forEach((v) => {
    const isSelected = v.id === selectedId;
    const existing = markersRef.current[v.id];

    const popupContent = `
      <div dir="rtl" style="font-family: 'Vazirmatn', sans-serif; min-width: 240px;">
        <div style="display: flex; align-items: center; justify-content: space-between; padding-bottom: 10px; border-bottom: 1px solid #1F2D4D; margin-bottom: 10px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 36px; height: 36px; border-radius: 10px; background: ${mapStatusColors[v.status].color}20; display: flex; align-items: center; justify-content: center;">
              <img src="${getMarkerIcon(v.status)}" style="width: 24px; height: 24px; object-fit: contain;" />
            </div>
            <div>
              <div style="font-weight: 700; color: #E8EDF7; font-size: 14px; font-family: 'JetBrains Mono', monospace;">${v.plate}</div>
              <div style="font-size: 10px; color: #5F6E8F; margin-top: 2px;">${v.driver}</div>
            </div>
          </div>
          <div style="background: ${mapStatusColors[v.status].color}20; color: ${mapStatusColors[v.status].color}; font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 6px;">
            ${mapStatusColors[v.status].label}
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
          <div style="background: #0B1220; border: 1px solid #1F2D4D; border-radius: 8px; padding: 6px 8px;">
            <div style="font-size: 9px; color: #5F6E8F; margin-bottom: 2px;">سرعت</div>
            <div style="font-size: 13px; font-weight: 700; color: #E8EDF7; font-family: 'JetBrains Mono', monospace;">
              ${v.speed} <span style="font-size: 9px; color: #5F6E8F; font-weight: 400;">km/h</span>
            </div>
          </div>
          <div style="background: #0B1220; border: 1px solid #1F2D4D; border-radius: 8px; padding: 6px 8px;">
            <div style="font-size: 9px; color: #5F6E8F; margin-bottom: 2px;">مسافت امروز</div>
            <div style="font-size: 13px; font-weight: 700; color: #E8EDF7; font-family: 'JetBrains Mono', monospace;">
              ${v.todayDistance} <span style="font-size: 9px; color: #5F6E8F; font-weight: 400;">km</span>
            </div>
          </div>
        </div>

        <div style="display: flex; align-items: flex-start; gap: 6px; margin-bottom: 10px; padding: 8px; background: #0B1220; border-radius: 8px; border: 1px solid #1F2D4D;">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#5F6E8F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-top: 2px; flex-shrink: 0;">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
            <circle cx="12" cy="10" r="3"></circle>
          </svg>
          <div style="font-size: 10px; color: #9BA8C4; line-height: 1.5;">${v.address}</div>
        </div>

        <div style="display: flex; align-items: center; justify-content: space-between; padding-top: 8px; border-top: 1px solid #1F2D4D;">
          <div style="font-size: 9px; color: #5F6E8F;">${v.lastUpdate}</div>
          <div style="display: flex; gap: 6px;">
            <button
              onclick="event.stopPropagation(); window.dispatchEvent(new CustomEvent('sana:view-trip', { detail: { id: ${v.id} } }))"
              style="font-size: 10px; color: #9BA8C4; background: transparent; border: 1px solid #1F2D4D; padding: 4px 8px; border-radius: 6px; cursor: pointer; font-family: 'Vazirmatn', sans-serif;"
            >
              مسیر
            </button>
            <button
              onclick="event.stopPropagation(); window.dispatchEvent(new CustomEvent('sana:view-detail', { detail: { id: ${v.id} } }))"
              style="font-size: 10px; color: #14B8A6; background: #14B8A620; border: 1px solid #14B8A640; padding: 4px 8px; border-radius: 6px; cursor: pointer; font-family: 'Vazirmatn', sans-serif;"
            >
              جزئیات
            </button>
          </div>
        </div>
      </div>
    `;

    if (existing) {
      existing.setLatLng([v.lat, v.lng]);
      existing.setIcon(createMarkerIcon(L, v.status));
      existing.setPopupContent(popupContent);
      existing.setZIndexOffset(isSelected ? 1000 : 0);
    } else {
      const marker = L.marker([v.lat, v.lng], {
        icon: createMarkerIcon(L, v.status),
        zIndexOffset: isSelected ? 1000 : 0,
      })
        .addTo(map)
        .bindPopup(popupContent, { className: 'sana-popup', closeButton: false });

      marker.on('click', () => {
        if (onSelect) onSelect(v.id);
      });

      markersRef.current[v.id] = marker;
    }
  });
}