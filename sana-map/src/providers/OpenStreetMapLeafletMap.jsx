import { useEffect, useRef } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const DEFAULT_CENTER = [32.4279, 53.688];
const DEFAULT_ZOOM = 5;

function markerColor(position) {
  if (position.status === 'offline') return '#64748B';
  if (position.status === 'moving') return '#14B8A6';
  return '#F59E0B';
}

function formatLastSeen(value) {
  if (!value) return 'نامشخص';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'نامشخص';
  return new Intl.DateTimeFormat('fa-IR', { dateStyle: 'short', timeStyle: 'medium' }).format(date);
}

function FitInitialBounds({ positions }) {
  const map = useMap();
  const fitted = useRef(false);

  useEffect(() => {
    if (fitted.current || !positions.length) return;
    const points = positions
      .filter((item) => Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude)))
      .map((item) => [Number(item.latitude), Number(item.longitude)]);
    if (!points.length) return;
    if (points.length === 1) {
      map.setView(points[0], 14);
    } else {
      map.fitBounds(points, { padding: [36, 36], maxZoom: 14 });
    }
    fitted.current = true;
  }, [map, positions]);

  return null;
}

export default function OpenStreetMapLeafletMap({ positions = [], onSelectDevice }) {
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
        <FitInitialBounds positions={validPositions} />
        {validPositions.map((position) => {
          const status = position.status === 'moving'
            ? 'در حرکت'
            : position.status === 'offline' ? 'آفلاین' : 'متوقف';
          const title = position.vehicle_plate || position.imei || `دستگاه ${position.device_id}`;
          return (
            <CircleMarker
              key={String(position.device_id)}
              center={[Number(position.latitude), Number(position.longitude)]}
              radius={9}
              pathOptions={{
                color: markerColor(position),
                fillColor: markerColor(position),
                fillOpacity: 0.85,
                weight: 3,
              }}
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
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
