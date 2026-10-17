import { useEffect, useRef, useState } from 'react';
import { NESHAN_LEAFLET_CONFIG } from '../config';
import { animateLeafletMarker } from '../markerAnimation';

const SDK_SCRIPT_ID = 'sana-neshan-leaflet-sdk';
const SDK_STYLE_ID = 'sana-neshan-leaflet-style';
const SDK_BASE = 'https://static.neshan.org/sdk/leaflet/v1.9.4/neshan-sdk/v1.0.8';
const SDK_LOADED_FLAG = '__SANA_NESHAN_LEAFLET_SDK_LOADED__';

function loadNeshanSdk() {
  if (window[SDK_LOADED_FLAG] && window.L?.Map) return Promise.resolve(window.L);

  const existing = document.getElementById(SDK_SCRIPT_ID);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', () => {
        if (window.L?.Map) {
          window[SDK_LOADED_FLAG] = true;
          resolve(window.L);
        } else {
          reject(new Error('SDK نشان بارگذاری شد اما Leaflet در دسترس نیست.'));
        }
      }, { once: true });
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
    script.onload = () => {
      if (window.L?.Map) {
        window[SDK_LOADED_FLAG] = true;
        resolve(window.L);
      } else {
        reject(new Error('SDK نشان بارگذاری شد اما Leaflet در دسترس نیست.'));
      }
    };
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

function headingDegrees(position) {
  const value = Number(position.heading);
  return Number.isFinite(value) && value >= 0 && value <= 360 ? value % 360 : 0;
}

function createDeviceIcon(L, position) {
  const color = markerColor(position);
  const angle = headingDegrees(position);
  return L.divIcon({
    className: 'sana-map-device-icon',
    iconSize: [36, 42],
    iconAnchor: [18, 21],
    popupAnchor: [0, -20],
    html: `<div style="width:36px;height:42px;display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 2px 3px #0006)"><svg width="32" height="40" viewBox="0 0 32 40" aria-hidden="true"><path d="M16 2 L29 35 L16 28 L3 35 Z" fill="${color}" stroke="#ffffff" stroke-width="2" stroke-linejoin="round" transform="rotate(${angle} 16 20)"/></svg></div>`,
  });
}

function popupHtml(position) {
  const title = position.vehicle_plate || position.imei || `دستگاه ${position.device_id}`;
  const status = position.status === 'moving' ? 'در حرکت' : position.status === 'offline' ? 'آفلاین' : 'متوقف';
  const positionNote = position.position_is_current ? '' : '<div style="color:#F59E0B;margin-top:6px">آخرین مختصات معتبر (GPS فعلی فاقد Fix است)</div>';
  const matchingNote = position.position_is_matched ? '<div style="color:#0F766E;margin-top:6px">موقعیت منطبق‌شده با مسیر جاده</div>' : '';
  return `<div dir="rtl" style="font-family:Tahoma,sans-serif;min-width:190px;color:#111">
    <div style="font-weight:700;margin-bottom:8px">${escapeHtml(title)}</div>
    <div>شناسه دستگاه: ${escapeHtml(position.imei)}</div>
    <div>وضعیت: ${status}</div>
    <div>سرعت: ${position.speed == null ? '—' : escapeHtml(position.speed)} km/h</div>
    <div>آخرین ارتباط: ${escapeHtml(formatLastSeen(position.last_seen))}</div>
    ${positionNote}
    ${matchingNote}
  </div>`;
}

export default function NeshanLeafletMap({ positions, onSelectDevice, followPosition = false, animationDuration = 10000 }) {
  const elementRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(new Map());
  const positionsRef = useRef(positions);
  const hasFitBoundsRef = useRef(false);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    positionsRef.current = positions;
  }, [positions]);

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
        syncMarkers(L, map, positionsRef.current, markersRef, onSelectDevice, animationDuration);
        if (!hasFitBoundsRef.current && positionsRef.current.length) {
          const bounds = L.latLngBounds(positionsRef.current.map((item) => [item.latitude, item.longitude]));
          map.fitBounds(bounds, { padding: [36, 36], maxZoom: 14 });
          hasFitBoundsRef.current = true;
        }
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
    syncMarkers(L, map, positions, markersRef, onSelectDevice, animationDuration);

    if (followPosition && positions.length === 1) {
      map.setView([Number(positions[0].latitude), Number(positions[0].longitude)], Math.max(map.getZoom(), 14), { animate: true, duration: Math.max(0.15, animationDuration / 1000) });
    } else if (!hasFitBoundsRef.current && positions.length) {
      const bounds = L.latLngBounds(positions.map((item) => [item.latitude, item.longitude]));
      map.fitBounds(bounds, { padding: [36, 36], maxZoom: 14 });
      hasFitBoundsRef.current = true;
    }
  }, [positions, onSelectDevice, followPosition, animationDuration]);

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

function syncMarkers(L, map, positions, markersRef, onSelectDevice, animationDuration = 10000) {
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
      animateLeafletMarker(marker, [Number(position.latitude), Number(position.longitude)], Number(position.animation_duration_ms) || animationDuration);
      marker.setIcon(createDeviceIcon(L, position));
      marker.setPopupContent(content);
    }
  });
}
