import { useEffect, useState } from 'react';
import { Activity, MapPin, Navigation, PauseCircle, WifiOff } from 'lucide-react';
import apiClient from '../api/client';
import LiveDeviceMap from '../../../sana-map/src/LiveDeviceMap';
import { MAP_PROVIDER, MAP_PROVIDERS } from '../../../sana-map/src/config';

export default function Map() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [mapProvider, setMapProvider] = useState(MAP_PROVIDER);
  const [refreshIntervalSeconds, setRefreshIntervalSeconds] = useState(10);
  const [followedDeviceId, setFollowedDeviceId] = useState(null);

  useEffect(() => {
    let active = true;
    apiClient.get('/site-settings/')
      .then(({ data }) => {
        if (!active) return;
        if ([MAP_PROVIDERS.LEAFLET_OSM, MAP_PROVIDERS.NESHAN_LEAFLET].includes(data?.map_provider)) {
          setMapProvider(data.map_provider);
        }
        const interval = Number(data?.map_refresh_interval_seconds);
        if (Number.isInteger(interval) && interval >= 5 && interval <= 300) {
          setRefreshIntervalSeconds(interval);
        }
      })
      .catch(() => {
        // در صورت در دسترس نبودن تنظیمات، مقادیر پیش‌فرض محلی استفاده می‌شوند.
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    // A short-lived heartbeat tells the GPS worker that somebody is viewing the map.
    // The server expires the session automatically if the tab/browser disappears.
    const sessionId = window.crypto?.randomUUID
      ? window.crypto.randomUUID()
      : `map-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const heartbeat = () => {
      apiClient.post('/devices/map-matching-activity/', {
        session_id: sessionId,
        active: true,
      }).catch(() => {
        // Matching stays disabled if the activity endpoint is unavailable.
      });
    };
    heartbeat();
    const timer = window.setInterval(heartbeat, 15000);
    return () => {
      window.clearInterval(timer);
      apiClient.post('/devices/map-matching-activity/', {
        session_id: sessionId,
        active: false,
      }).catch(() => {
        // The server-side expiry is the fallback cleanup.
      });
    };
  }, []);

  useEffect(() => {
    let active = true;
    let inFlight = false;
    const refreshPositions = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await apiClient.get('/devices/map-positions/');
        const data = response.data;
        const items = Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : [];
        if (active) { setPositions(items); setLastUpdated(new Date()); setError(''); }
      } catch (requestError) {
        if (active) setError(requestError.response?.data?.detail || 'دریافت موقعیت دستگاه‌ها از سرور سانا ناموفق بود. اتصال سرور و دسترسی حساب را بررسی کنید.');
      } finally {
        inFlight = false;
        if (active) setLoading(false);
      }
    };
    refreshPositions();
    const intervalId = window.setInterval(refreshPositions, refreshIntervalSeconds * 1000);
    return () => { active = false; window.clearInterval(intervalId); };
  }, [refreshIntervalSeconds]);

  useEffect(() => {
    setFollowedDeviceId((current) => {
      if (!current) return null;
      return positions.some((item) => String(item.device_id) === String(current))
        ? current
        : null;
    });
  }, [positions]);

  const moving = positions.filter((item) => item.status === 'moving').length;
  const stopped = positions.filter((item) => item.status === 'stopped').length;
  const offline = positions.filter((item) => item.status === 'offline').length;
  const selectedDevice = positions.find(
  (item) => String(item.device_id) === String(followedDeviceId)
  );

  return (
    <div className="flex min-h-[calc(100dvh-6.5rem)] flex-col gap-3 lg:h-full lg:min-h-[560px]">
      <header className="flex shrink-0 items-center gap-3">
        <div className="min-w-0">
          <h1 className="text-base font-semibold text-text-primary sm:text-lg">نقشه زنده</h1>
          <p className="mt-0.5 text-[11px] text-text-muted sm:text-xs">نمای لحظه‌ای موقعیت و وضعیت دستگاه‌های GPS</p>
        </div>
      </header>

      {error && (
        <div role="alert" className="shrink-0 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs leading-6 text-text-primary">
          {error}
          {positions.length > 0 && <span className="mr-2 text-text-muted">موقعیت‌های قبلی تا دریافت داده جدید نمایش داده می‌شوند.</span>}
        </div>
      )}

      <section className="relative flex min-h-[480px] flex-1 flex-col overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm sm:min-h-[540px]">
        <div className="absolute inset-0">
          <LiveDeviceMap
            positions={positions}
            provider={mapProvider}
            followPosition={followedDeviceId || false}
            onSelectDevice={setFollowedDeviceId}
            animationDuration={refreshIntervalSeconds * 1000}
          />
        </div>

        <div className="pointer-events-none absolute inset-x-2 top-2 z-[1000] sm:inset-x-3 sm:top-3">
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 sm:gap-2.5">
            <Summary label="دارای موقعیت" value={positions.length} icon={<MapPin size={15} />} tone="text-brand-400" />
            <Summary label="در حرکت" value={moving} icon={<Navigation size={15} />} tone="text-success" />
            <Summary label="متوقف" value={stopped} icon={<PauseCircle size={15} />} tone="text-warning" />
            <div className="relative min-w-0">
              <Summary label="آفلاین" value={offline} icon={<WifiOff size={15} />} tone="text-text-muted" />
              {selectedDevice && <DeviceDetails position={selectedDevice} />}
            </div>
          </div>
        </div>

        <div className="absolute inset-x-2 bottom-2 z-[1000] flex flex-col gap-2 sm:inset-x-3 sm:bottom-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-bg-elevated/95 px-2.5 py-2 text-[11px] text-text-secondary shadow-lg backdrop-blur-md sm:gap-3 sm:px-3">
            <label className="flex items-center gap-2">
              <span>نقشه</span>
              <select
                aria-label="انتخاب ارائه‌دهنده نقشه"
                value={mapProvider}
                onChange={(event) => setMapProvider(event.target.value)}
                className="min-w-28 rounded-lg border border-border-base bg-bg-base px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-brand-400"
              >
                <option value={MAP_PROVIDERS.LEAFLET_OSM}>OpenStreetMap</option>
                <option value={MAP_PROVIDERS.NESHAN_LEAFLET}>نشان</option>
              </select>
            </label>
            <span className="hidden h-4 w-px bg-border-strong sm:block" />
            <span className="inline-flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${loading ? 'bg-warning animate-pulse' : error ? 'bg-danger' : 'bg-success'}`} />
              {loading ? 'در حال دریافت' : error ? 'اختلال ارتباط' : 'آنلاین'}
            </span>
            <span>هر {refreshIntervalSeconds.toLocaleString('fa-IR')} ثانیه</span>
          </div>

        </div>

        {!loading && !error && positions.length === 0 && (
          <div className="pointer-events-none absolute left-1/2 top-1/2 z-[1000] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border-base bg-bg-elevated/95 px-4 py-3 text-center text-xs text-text-primary shadow-lg backdrop-blur-md">
            <MapPin size={17} className="mx-auto mb-1 text-text-muted" />
            هنوز موقعیت معتبری برای دستگاه‌های قابل‌دسترسی ثبت نشده است.
          </div>
        )}
      </section>
    </div>
  );
}

function Summary({ label, value, tone = 'text-text-primary', icon }) {
  return (
    <div className="pointer-events-auto flex min-h-[48px] min-w-0 items-center gap-1.5 rounded-lg border border-white/10 bg-bg-elevated/95 px-2 py-1.5 shadow-lg backdrop-blur-md sm:min-h-[54px] sm:gap-2 sm:rounded-xl sm:px-2.5">
      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-bg-base/90 sm:h-8 sm:w-8 ${tone}`}>
        {icon}
      </span>
      <div className="min-w-0">
        <div className="truncate text-[10px] leading-4 text-text-muted sm:text-[11px]">{label}</div>
        <div className={`text-sm font-bold leading-5 tabular-nums sm:text-base ${tone}`}>{value.toLocaleString('fa-IR')}</div>
      </div>
    </div>
  );
}


const ATTRIBUTE_LABELS = {
  priority: 'اولویت پیام',
  sat: 'تعداد ماهواره',
  event: 'کد رویداد',
  ignition: 'سوئیچ',
  motion: 'حرکت',
  rssi: 'قدرت سیگنال GSM',
  gpsStatus: 'وضعیت GPS',
  pdop: 'PDOP',
  hdop: 'HDOP',
  power: 'ولتاژ خارجی',
  battery: 'ولتاژ باتری',
  fuel: 'سوخت',
  fuelLevel: 'سطح سوخت',
  odometer: 'کیلومترشمار',
  totalDistance: 'مسافت کل',
  distance: 'مسافت پیام',
  hours: 'ساعت موتور',
  adc1: 'ورودی آنالوگ ۱',
  adc2: 'ورودی آنالوگ ۲',
  operator: 'شناسه اپراتور',
  ip: 'IP دستگاه',
  alarm: 'هشدار',
  charge: 'شارژ',
  door: 'وضعیت درب',
  temp1: 'دمای ۱',
  temp2: 'دمای ۲',
  deviceTemp: 'دمای دستگاه',
};

const COMMON_ATTRIBUTES = [
  'ignition', 'motion', 'sat', 'rssi', 'power',
  'battery', 'fuel', 'odometer', 'hours', 'event',
  'priority', 'gpsStatus', 'hdop', 'pdop',
];

function formatDeviceTime(value) {
  if (!value) return 'نامشخص';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return 'نامشخص';

  return new Intl.DateTimeFormat('fa-IR', {
    dateStyle: 'short',
    timeStyle: 'medium',
  }).format(date);
}

function formatDeviceAttribute(value) {
  if (value === null || value === undefined || value === '') {
    return 'مقدار ارسال نشده';
  }

  if (typeof value === 'boolean') {
    return value ? 'بله / فعال' : 'خیر / غیرفعال';
  }

  if (typeof value === 'object') {
    return JSON.stringify(value);
  }

  return String(value);
}

function DeviceDetails({ position }) {
  const title = position.vehicle_plate
    || position.imei
    || `دستگاه ${position.device_id}`;

  const status = position.status === 'moving'
    ? 'در حرکت'
    : position.status === 'offline'
      ? 'آفلاین'
      : 'متوقف';

  const attributes = position.attributes
    && typeof position.attributes === 'object'
    && !Array.isArray(position.attributes)
      ? position.attributes
      : {};

  const keys = [
    ...new Set([...COMMON_ATTRIBUTES, ...Object.keys(attributes)]),
  ];

  return (
    <div
      dir="rtl"
      className="pointer-events-auto absolute right-0 top-full z-20 mt-2 w-full min-w-0 overflow-hidden rounded-xl border border-white/10 bg-bg-elevated/95 shadow-lg backdrop-blur-md"
    >
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
        <div className="min-w-0">
          <div className="truncate text-xs font-bold text-text-primary">
            {title}
          </div>
          <div className="mt-0.5 text-[10px] text-text-muted">
            شناسه دستگاه: {position.imei || '—'}
          </div>
        </div>

        <span className={`shrink-0 rounded-md bg-bg-base px-2 py-1 text-[10px] font-semibold ${
          position.status === 'moving'
            ? 'text-success'
            : position.status === 'offline'
              ? 'text-text-muted'
              : 'text-warning'
        }`}>
          {status}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-y-1 px-2.5 py-2 text-[10px]">
        <div>
          <div className="text-text-muted">سرعت</div>
          <div className="font-semibold text-text-primary">
            {position.speed == null || !Number.isFinite(Number(position.speed))
              ? '—'
              : Number(position.speed).toFixed(1)} km/h
          </div>
        </div>

        <div>
          <div className="text-text-muted">زمان پیام دستگاه</div>
          <div className="font-medium text-text-primary">
            {formatDeviceTime(position.device_time)}
          </div>
        </div>

        <div>
          <div className="text-text-muted">زمان دریافت Traccar</div>
          <div className="font-medium text-text-primary">
            {formatDeviceTime(position.last_seen)}
          </div>
        </div>

        <div>
          <div className="text-text-muted">وضعیت موقعیت</div>
          <div className="font-medium text-text-primary">
            {position.position_is_current
              ? 'مختصات فعلی'
              : 'آخرین مختصات معتبر'}
          </div>
        </div>
      </div>

      {!position.position_is_current && (
        <div className="px-3 pb-1 text-[10px] text-warning">
          GPS فعلی فاقد Fix است؛ آخرین مختصات معتبر نمایش داده شده.
        </div>
      )}

      {position.position_is_matched && (
        <div className="px-3 pb-1 text-[10px] text-success">
          موقعیت منطبق‌شده با مسیر جاده
        </div>
      )}

      <div className="border-t border-white/10 px-3 py-1.5">
        <div className="mb-1 text-[10px] font-bold text-text-secondary">
          Attributeهای Traccar
        </div>

        <div className="max-h-36 overflow-y-auto overscroll-contain">
          <div className="grid grid-cols-1">
            {keys.map((key) => {
              const received = Object.prototype.hasOwnProperty.call(attributes, key);

              const value = received
                ? formatDeviceAttribute(attributes[key])
                : 'فاقد اطلاعات';

              return (
                <div
                  key={key}
                  className="flex min-w-0 items-start justify-between gap-2 border-b border-white/5 py-1 text-[10px]"
                >
                  <span className="min-w-0 text-text-muted">
                    {ATTRIBUTE_LABELS[key] || key}
                    <span className="mr-1 opacity-60">({key})</span>
                  </span>

                  <strong className="min-w-0 break-all text-left font-medium text-text-primary">
                    {value}
                  </strong>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
