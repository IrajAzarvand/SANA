import { useEffect, useRef, useState } from 'react';
import { NESHAN_LEAFLET_CONFIG } from '../config';
import { animateLeafletMarker, getFollowedPosition } from '../markerAnimation';
import { getDeviceClusters, createClusterIcon } from '../deviceClusters';

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

function formatSpeed(value) {
  const speed = Number(value);
  return value == null || !Number.isFinite(speed) ? '—' : speed.toFixed(1);
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
    iconSize: [32, 38],
    iconAnchor: [16, 19],
    popupAnchor: [0, -20],
    html: `<div style="width:36px;height:42px;display:flex;align-items:center;justify-content:center;filter:drop-shadow(0 2px 3px #0006)"><svg width="32" height="40" viewBox="0 0 32 40" aria-hidden="true"><path d="M16 2 L29 35 L16 28 L3 35 Z" fill="${color}" stroke="#ffffff" stroke-width="2" stroke-linejoin="round" transform="rotate(${angle} 16 20)"/></svg></div>`,
  });
}

const ATTRIBUTE_LABELS = {
  priority: 'اولویت پیام', sat: 'تعداد ماهواره', event: 'کد رویداد', ignition: 'سوئیچ', motion: 'حرکت',
  rssi: 'قدرت سیگنال GSM', gpsStatus: 'وضعیت GPS', pdop: 'PDOP', hdop: 'HDOP',
  power: 'ولتاژ خارجی', battery: 'ولتاژ باتری', fuel: 'سوخت', fuelLevel: 'سطح سوخت',
  odometer: 'کیلومترشمار', totalDistance: 'مسافت کل', distance: 'مسافت پیام',
  hours: 'ساعت موتور', adc1: 'ورودی آنالوگ ۱', adc2: 'ورودی آنالوگ ۲',
  operator: 'شناسه اپراتور', ip: 'IP دستگاه', alarm: 'هشدار', charge: 'شارژ',
  door: 'وضعیت درب', temp1: 'دمای ۱', temp2: 'دمای ۲', deviceTemp: 'دمای دستگاه',
};
const COMMON_ATTRIBUTES = ['ignition','motion','sat','rssi','power','battery','fuel','odometer','hours','event','priority','gpsStatus','hdop','pdop'];
function attributeRows(attributes = {}) {
  const values = attributes && typeof attributes === 'object' && !Array.isArray(attributes) ? attributes : {};
  const keys = [...new Set([...COMMON_ATTRIBUTES, ...Object.keys(values)])];
  return keys.map((key) => {
    const value = Object.prototype.hasOwnProperty.call(values, key) ? values[key] : undefined;
    const display = value === undefined || value === null || value === '' ? 'در این نقطه از دستگاه دریافت نشده' : typeof value === 'boolean' ? (value ? 'بله / فعال' : 'خیر / غیرفعال') : typeof value === 'object' ? JSON.stringify(value) : String(value);
    return '<div style="display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #ddd;padding:2px 0"><span>' + escapeHtml(ATTRIBUTE_LABELS[key] || key) + ' <small style="color:#777">(' + escapeHtml(key) + ')</small></span><strong style="overflow-wrap:anywhere">' + escapeHtml(display) + '</strong></div>';
  }).join('');
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
    <div>سرعت: ${escapeHtml(formatSpeed(position.speed))} km/h</div>
    <div>زمان پیام دستگاه: ${escapeHtml(formatLastSeen(position.device_time))}</div>
    <div>زمان دریافت Traccar: ${escapeHtml(formatLastSeen(position.last_seen))}</div>
    <div style="font-weight:700;margin-top:8px">Attributeهای Traccar</div>
    <div style="max-height:240px;overflow-y:auto;margin-top:4px">${attributeRows(position.attributes)}</div>
    ${positionNote}
    ${matchingNote}
  </div>`;
}

export default function NeshanLeafletMap({ positions, onSelectDevice, followPosition = false, animationDuration = 10000, routeSegments = [] }) {
  const elementRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(new Map());
  const clusterMarkersRef = useRef(new Map());
  const routeLayersRef = useRef([]);
  const positionsRef = useRef(positions);
  const hasFitBoundsRef = useRef(false);
  const lastFollowKeyRef = useRef(null);
  const [loadError, setLoadError] = useState('');
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    positionsRef.current = positions;
  }, [positions]);

  useEffect(() => {
    const L = window.L;
    const map = mapRef.current;
    if (!L || !map) return;
    routeLayersRef.current.forEach((layer) => layer.remove());
    routeLayersRef.current = [];
    const points = routeSegments.flatMap((segment) => segment.coordinates || []);
    routeSegments.forEach((segment) => {
      if (!segment.coordinates || segment.coordinates.length < 2) return;
      const line = L.polyline(segment.coordinates, { color: segment.color, weight: 5, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }).addTo(map);
      routeLayersRef.current.push(line);
    });
    if (!followPosition && points.length >= 2) map.fitBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 15 });
    return () => { routeLayersRef.current.forEach((layer) => layer.remove()); routeLayersRef.current = []; };
  }, [routeSegments, loadError, mapReady, followPosition]);

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
        map.on('click', () => onSelectDevice?.(null));
        setMapReady(true);
        setLoadError('');
        syncMarkers(L, map, positionsRef.current, markersRef, clusterMarkersRef, onSelectDevice, animationDuration, followPosition);
        const followed = getFollowedPosition(positionsRef.current, followPosition);
        if (followed) {
          map.setView([Number(followed.latitude), Number(followed.longitude)], Math.max(map.getZoom(), 14), { animate: false });
          lastFollowKeyRef.current = String(followed.device_id);
          hasFitBoundsRef.current = true;
        } else if (!hasFitBoundsRef.current && positionsRef.current.length) {
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
      clusterMarkersRef.current.forEach((marker) => marker.remove());
      clusterMarkersRef.current.clear();
      markersRef.current.clear();
      hasFitBoundsRef.current = false;
      lastFollowKeyRef.current = null;
    };
  }, [onSelectDevice]);

  useEffect(() => {
    const map = mapRef.current;
    const L = window.L;
    if (!map || !L) return;
    syncMarkers(L, map, positions, markersRef, clusterMarkersRef, onSelectDevice, animationDuration, followPosition);

    const refreshMarkers = () => {
      syncMarkers(
        L,
        map,
        positionsRef.current,
        markersRef,
        clusterMarkersRef,
        onSelectDevice,
        animationDuration,
        followPosition,
      );
    };
    map.on('zoomend', refreshMarkers);

    const followed = getFollowedPosition(positions, followPosition);
    if (followed) {
      const key = String(followed.device_id);
      if (lastFollowKeyRef.current !== key) {
        map.setView(
          [Number(followed.latitude), Number(followed.longitude)],
          Math.max(map.getZoom(), 14),
          { animate: false },
        );
        lastFollowKeyRef.current = key;
        hasFitBoundsRef.current = true;
      }
    } else {
      lastFollowKeyRef.current = null;
      if (!hasFitBoundsRef.current && positions.length) {
        const bounds = L.latLngBounds(positions.map((item) => [item.latitude, item.longitude]));
        map.fitBounds(bounds, { padding: [36, 36], maxZoom: 14 });
        hasFitBoundsRef.current = true;
      }
    }

    return () => {
      map.off('zoomend', refreshMarkers);
    };
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

function syncMarkers(
  L,
  map,
  positions,
  markersRef,
  clusterMarkersRef,
  onSelectDevice,
  animationDuration = 10000,
  followPosition = false,
) {
  const validPositions = positions.filter((position) =>
    Number.isFinite(Number(position.latitude)) &&
    Number.isFinite(Number(position.longitude))
  );
  const visibleIds = new Set(validPositions.map((item) => String(item.device_id)));
  const clusters = getDeviceClusters(map, validPositions, followPosition);
  const individualIds = new Set(
    clusters
      .filter((item) => item.type === 'device')
      .map((item) => String(item.position.device_id))
  );
  const clusterIds = new Set(
    clusters.filter((item) => item.type === 'cluster').map((item) => item.id)
  );

  for (const [id, marker] of markersRef.current.entries()) {
    if (!visibleIds.has(id)) {
      marker.remove();
      markersRef.current.delete(id);
    }
  }

  for (const [id, marker] of clusterMarkersRef.current.entries()) {
    if (!clusterIds.has(id)) {
      marker.remove();
      clusterMarkersRef.current.delete(id);
    }
  }

  const followed = getFollowedPosition(validPositions, followPosition);

  validPositions.forEach((position) => {
    const id = String(position.device_id);
    const target = [Number(position.latitude), Number(position.longitude)];
    const shouldShow = individualIds.has(id);
    let marker = markersRef.current.get(id);

    if (!marker && !shouldShow) return;

    const content = popupHtml(position);
    const keepCentered = Boolean(followed && String(followed.device_id) === id);

    if (!marker) {
      marker = L.marker(target, {
        icon: createDeviceIcon(L, position),
      }).addTo(map);
      marker.bindPopup(content);
      marker.on('click', () => onSelectDevice?.(position.device_id));
      markersRef.current.set(id, marker);

      if (keepCentered) {
        animateLeafletMarker(marker, target, 0, {
          map,
          keepCentered: true,
        });
      }
    } else if (!shouldShow) {
      marker.setLatLng(target);
      if (map.hasLayer(marker)) marker.remove();
      marker.setIcon(createDeviceIcon(L, position));
      marker.setPopupContent(content);
    } else {
      if (!map.hasLayer(marker)) marker.addTo(map);

      animateLeafletMarker(
        marker,
        target,
        Number(position.animation_duration_ms) || animationDuration,
        { map, keepCentered },
      );
      marker.setIcon(createDeviceIcon(L, position));
      marker.setPopupContent(content);
    }
  });

  clusters.forEach((cluster) => {
    if (cluster.type !== 'cluster') return;

    const content = `
      <div dir="rtl" style="min-width:150px;padding:5px 8px;font-family:Tahoma,sans-serif;font-size:12px;line-height:2;color:#1f2937">
        <strong>${cluster.total} دستگاه در این محدوده</strong>
        <div><span style="color:#14B8A6">●</span> در حرکت: ${cluster.counts.moving}</div>
        <div><span style="color:#F59E0B">●</span> متوقف: ${cluster.counts.stopped}</div>
        <div><span style="color:#64748B">●</span> آفلاین: ${cluster.counts.offline}</div>
      </div>`;

    let marker = clusterMarkersRef.current.get(cluster.id);

    if (!marker) {
      marker = L.marker(
        [cluster.latitude, cluster.longitude],
        {
          icon: createClusterIcon(L, cluster),
          bubblingMouseEvents: false,
        },
      ).addTo(map);

      marker.bindPopup(content, {
        closeButton: false,
        closeOnClick: true,
        autoClose: true,
        autoPan: false,
        className: 'sana-cluster-popup',
      });

      marker.on('mouseover', () => marker.openPopup());
      marker.on('mouseout', () => marker.closePopup());
      marker.on('click', (event) => {
        event.originalEvent?.stopPropagation();
        marker.openPopup();
      });

      clusterMarkersRef.current.set(cluster.id, marker);
    } else {
      marker.setLatLng([cluster.latitude, cluster.longitude]);
      marker.setIcon(createClusterIcon(L, cluster));
      marker.setPopupContent(content);
    }
  });
}
