import { useEffect, useRef, useState } from 'react';
import { NESHAN_LEAFLET_CONFIG } from '../config';

const SDK_SCRIPT_ID = 'sana-neshan-leaflet-sdk';
const SDK_STYLE_ID = 'sana-neshan-leaflet-style';
const SDK_BASE = 'https://static.neshan.org/sdk/leaflet/v1.9.4/neshan-sdk/v1.0.8';

function loadNeshanSdk() {
  if (window.L?.Map) return Promise.resolve(window.L);

  const existing = document.getElementById(SDK_SCRIPT_ID);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', () => resolve(window.L), { once: true });
      existing.addEventListener('error', () => reject(new Error('بارگذاری SDK نقشه نشان ناموفق بود.')), { once: true });
    });
  }

  if (!document.getElementById(SDK_STYLE_ID)) {
    const link = document.createElement('link');
    link.id = SDK_STYLE_ID;
    link.rel = 'stylesheet';
    link.href = `${SDK_BASE}/index.css`;
    document.head.appendChild(link);
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.id = SDK_SCRIPT_ID;
    script.src = `${SDK_BASE}/index.js`;
    script.async = true;
    script.onload = () => window.L
      ? resolve(window.L)
      : reject(new Error('SDK نشان بارگذاری شد اما Leaflet در دسترس نیست.'));
    script.onerror = () => reject(new Error('بارگذاری SDK نقشه نشان ناموفق بود.'));
    document.head.appendChild(script);
  });
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

function formatLastSeen(value) {
  if (!value) return 'نامشخص';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'نامشخص';
  return new Intl.DateTimeFormat('fa-IR', {
    dateStyle: 'short',
    timeStyle: 'medium',
  }).format(date);
}

function markerColor(position) {
  if (position.status === 'offline') return '#64748B';
  if (position.status === 'moving') return '#14B8A6';
  return '#F59E0B';
}

function createDeviceIcon(L, position) {
  const color = markerColor(position);
  const pulse = position.status === 'moving' ? 'animation: sana-map-pulse 1.8s ease-in-out infinite;' : '';
  return L.divIcon({
    className: 'sana-map-device-icon',
    iconSize: [42, 42],
    iconAnchor: [21, 21],
    popupAnchor: [0, -18],
    html: `<div style="width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:${color}22;border:2px solid ${color};box-shadow:0 2px 10px #0005;${pulse}"><span style="font-size:19px;line-height:1">🚘</span></div>`,
  });
}

function popupHtml(position) {
  const title = position.vehicle_plate || position.imei || `دستگاه ${position.device_id}`;
  const status = position.status === 'moving' ? 'در حرکت' : position.status === 'offline' ? 'آفلاین' : 'متوقف';
  const positionNote = position.position_is_current ? '' : '<div style="color:#F59E0B;margin-top:6px">آخرین مختصات معتبر (GPS فعلی فاقد Fix است)</div>';
  return `<div dir="rtl" style="font-family:Tahoma,sans-serif;min-width:190px;color:#111">
    <div style="font-weight:700;margin-bottom:8px">${escapeHtml(title)}</div>
    <div>شناسه دستگاه: ${escapeHtml(position.imei)}</div>
    <div>وضعیت: ${status}</div>
    <div>سرعت: ${position.speed == null ? '—' : escapeHtml(position.speed)} km/h</div>
    <div>آخرین ارتباط: ${escapeHtml(formatLastSeen(position.last_seen))}</div>
    ${positionNote}
  </div>`;
}

export default function NeshanLeafletMap({ positions, onSelectDevice }) {
  const elementRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(new Map());
  const positionsRef = useRef(positions);
  const hasFitBoundsRef = useRef(false);
  const [loadError, setLoadError] = useState('');

  positionsRef.current = positions;

  useEffect(() => {
    let cancelled = false;

    if (!NESHAN_LEAFLET_CONFIG.apiKey) {
      setLoadError('کلید نقشه نشان تنظیم نشده است. مقدار VITE_NESHAN_API_KEY را در sana-panel/.env قرار دهید و پنل را دوباره اجرا کنید.');
      return undefined;
    }

    loadNeshanSdk()
      .then((L) => {
        if (cancelled || !elementRef.current) return;
        const map = new L.Map(elementRef.current, {
          key: NESHAN_LEAFLET_CONFIG.apiKey,
          maptype: NESHAN_LEAFLET_CONFIG.mapType,
          center: NESHAN_LEAFLET_CONFIG.center,
          zoom: NESHAN_LEAFLET_CONFIG.zoom,
          zoomControl: false,
        });
        L.control.zoom({ position: 'topleft' }).addTo(map);
        mapRef.current = map;
        setLoadError('');
        syncMarkers(L, map, positionsRef.current, markersRef, onSelectDevice);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message || 'نقشه بارگذاری نشد.');
      });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      markersRef.current.clear();
      hasFitBoundsRef.current = false;
    };
  }, [onSelectDevice]);

  useEffect(() => {
    const map = mapRef.current;
    const L = window.L;
    if (!map || !L) return;
    syncMarkers(L, map, positions, markersRef, onSelectDevice);

    if (!hasFitBoundsRef.current && positions.length) {
      const bounds = L.latLngBounds(positions.map((item) => [item.latitude, item.longitude]));
      map.fitBounds(bounds, { padding: [36, 36], maxZoom: 14 });
      hasFitBoundsRef.current = true;
    }
  }, [positions, onSelectDevice]);

  return (
    <div className="relative h-full min-h-80 w-full">
      <style>{`@keyframes sana-map-pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.08); } }`}</style>
      <div ref={elementRef} className="absolute inset-0 h-full w-full" />
      {loadError && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-bg-elevated/95 p-6 text-center">
          <div className="max-w-lg">
            <div className="mb-2 text-sm font-semibold text-text-primary">نقشه در دسترس نیست</div>
            <p className="text-sm text-text-secondary">{loadError}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function syncMarkers(L, map, positions, markersRef, onSelectDevice) {
  const visibleIds = new Set(positions.map((item) => String(item.device_id)));

  for (const [id, marker] of markersRef.current.entries()) {
    if (!visibleIds.has(id)) {
      marker.remove();
      markersRef.current.delete(id);
    }
  }

  positions.forEach((position) => {
    if (!Number.isFinite(Number(position.latitude)) || !Number.isFinite(Number(position.longitude))) return;
    const id = String(position.device_id);
    let marker = markersRef.current.get(id);
    const content = popupHtml(position);

    if (!marker) {
      marker = L.marker([Number(position.latitude), Number(position.longitude)], {
        icon: createDeviceIcon(L, position),
      }).addTo(map);
      marker.bindPopup(content);
      marker.on('click', () => onSelectDevice?.(position.device_id));
      markersRef.current.set(id, marker);
    } else {
      marker.setLatLng([Number(position.latitude), Number(position.longitude)]);
      marker.setIcon(createDeviceIcon(L, position));
      marker.setPopupContent(content);
    }
  });
}
