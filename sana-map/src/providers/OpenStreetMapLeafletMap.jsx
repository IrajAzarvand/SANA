import { useEffect, useRef } from 'react';
import { Marker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

const DEFAULT_CENTER = [32.4279, 53.688];
const DEFAULT_ZOOM = 5;

function markerColor(position) {
  if (position.status === 'offline') return '#64748B';
  if (position.status === 'moving') return '#14B8A6';
  return '#F59E0B';
}


function headingDegrees(position) {
  const value = Number(position.heading);
  return Number.isFinite(value) && value >= 0 && value <= 360 ? value % 360 : 0;
}

function createDeviceIcon(position) {
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

function formatLastSeen(value) {
  if (!value) return 'نامشخص';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'نامشخص';
  return new Intl.DateTimeFormat('fa-IR', { dateStyle: 'short', timeStyle: 'medium' }).format(date);
}

function FitInitialBounds({ positions, followPosition = false }) {
  const map = useMap();
  const fitted = useRef(false);

  useEffect(() => {
    if (!positions.length) return;
    const points = positions
      .filter((item) => Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude)))
      .map((item) => [Number(item.latitude), Number(item.longitude)]);
    if (!points.length) return;
    if (followPosition && points.length === 1) {
      map.setView(points[0], Math.max(map.getZoom(), 14), { animate: false });
      return;
    }
    if (fitted.current) return;
    if (points.length === 1) {
      map.setView(points[0], 14);
    } else {
      map.fitBounds(points, { padding: [36, 36], maxZoom: 14 });
    }
    fitted.current = true;
  }, [map, positions, followPosition]);

  return null;
}

export default function OpenStreetMapLeafletMap({ positions = [], onSelectDevice, followPosition = false }) {
  const validPositions = positions.filter((item) => (
    Number.isFinite(Number(item.latitude))
    && Number.isFinite(Number(item.longitude))
    && Number(item.latitude) >= -90
    && Number(item.latitude) <= 90
    && Number(item.longitude) >= -180
    && Number(item.longitude) <= 180
  ));

  return (
    <div className="relative h-full min-h-80 w-full">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        scrollWheelZoom
        zoomControl
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <FitInitialBounds positions={validPositions} followPosition={followPosition} />
        {validPositions.map((position) => {
          const status = position.status === 'moving'
            ? 'در حرکت'
            : position.status === 'offline' ? 'آفلاین' : 'متوقف';
          const title = position.vehicle_plate || position.imei || `دستگاه ${position.device_id}`;
          return (
            <Marker
              key={String(position.device_id)}
              position={[Number(position.latitude), Number(position.longitude)]}
              icon={createDeviceIcon(position)}
              eventHandlers={{ click: () => onSelectDevice?.(position.device_id) }}
            >
              <Popup>
                <div dir="rtl" style={{ minWidth: 180, fontFamily: 'Tahoma, sans-serif', lineHeight: 1.9 }}>
                  <strong>{title}</strong>
                  <div>شناسه دستگاه: {position.imei || '—'}</div>
                  <div>وضعیت: {status}</div>
                  <div>سرعت: {position.speed == null ? '—' : position.speed} km/h</div>
                  <div>آخرین ارتباط: {formatLastSeen(position.last_seen)}</div>
                  {!position.position_is_current && (
                    <div style={{ color: '#B45309' }}>آخرین مختصات معتبر (GPS فعلی فاقد Fix است)</div>
                  )}
                  {position.position_is_matched && (
                    <div style={{ color: '#0F766E' }}>موقعیت منطبق‌شده با مسیر جاده</div>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
