import { useEffect, useState } from 'react';
import { Activity, MapPin, Navigation, PauseCircle, WifiOff } from 'lucide-react';
import PageHeader from '../components/PageHeader';
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
    if (!positions.length) {
      setFollowedDeviceId(null);
      return;
    }
    setFollowedDeviceId((current) => {
      if (current && positions.some((item) => String(item.device_id) === String(current))) return current;
      return positions[0].device_id;
    });
  }, [positions]);

  const moving = positions.filter((item) => item.status === 'moving').length;
  const stopped = positions.filter((item) => item.status === 'stopped').length;
  const offline = positions.filter((item) => item.status === 'offline').length;

  return (
    <div className="flex min-h-[560px] flex-col gap-3 lg:h-full lg:min-h-[560px]">
      <PageHeader
        title="نقشه زنده"
        subtitle="نمای لحظه‌ای موقعیت و وضعیت دستگاه‌های GPS"
      />

      <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4">
        <Summary label="دارای موقعیت" value={positions.length} icon={<MapPin size={17} />} tone="text-brand-400" />
        <Summary label="در حرکت" value={moving} icon={<Navigation size={17} />} tone="text-success" />
        <Summary label="متوقف" value={stopped} icon={<PauseCircle size={17} />} tone="text-warning" />
        <Summary label="آفلاین" value={offline} icon={<WifiOff size={17} />} tone="text-text-muted" />
      </div>

      {error && (
        <div role="alert" className="shrink-0 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs leading-6 text-text-primary">
          {error}
          {positions.length > 0 && <span className="mr-2 text-text-muted">موقعیت‌های قبلی تا دریافت داده جدید نمایش داده می‌شوند.</span>}
        </div>
      )}

      <section className="flex min-h-[360px] flex-1 flex-col overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm">
        <div className="flex shrink-0 flex-col gap-2 border-b border-border-base bg-bg-elevated px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:px-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/10 text-brand-400">
                <Activity size={17} />
              </span>
              موقعیت دستگاه‌ها
            </div>
            <label className="flex items-center gap-2 text-xs text-text-secondary">
              <span>نوع نقشه</span>
              <select
                aria-label="انتخاب ارائه‌دهنده نقشه"
                value={mapProvider}
                onChange={(event) => setMapProvider(event.target.value)}
                className="min-w-36 rounded-lg border border-border-base bg-bg-base px-3 py-2 text-xs text-text-primary outline-none transition focus:border-brand-400"
              >
                <option value={MAP_PROVIDERS.LEAFLET_OSM}>OpenStreetMap</option>
                <option value={MAP_PROVIDERS.NESHAN_LEAFLET}>نشان</option>
              </select>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted">
            <span className="inline-flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${loading ? 'bg-warning animate-pulse' : error ? 'bg-danger' : 'bg-success'}`} />
              {loading ? 'در حال دریافت' : error ? 'اختلال در ارتباط' : 'اتصال فعال'}
            </span>
            <span>به‌روزرسانی هر {refreshIntervalSeconds.toLocaleString('fa-IR')} ثانیه</span>
            <span>{lastUpdated ? `آخرین دریافت: ${lastUpdated.toLocaleTimeString('fa-IR')}` : 'هنوز به‌روزرسانی نشده'}</span>
            {followedDeviceId && <span className="hidden text-text-secondary md:inline">دستگاه انتخاب‌شده در مرکز نقشه</span>}
          </div>
        </div>

        <div className="relative min-h-[300px] flex-1">
          <LiveDeviceMap
            positions={positions}
            provider={mapProvider}
            followPosition={followedDeviceId || false}
            onSelectDevice={setFollowedDeviceId}
            animationDuration={refreshIntervalSeconds * 1000}
          />
        </div>

        {!loading && !error && positions.length === 0 && (
          <div className="flex shrink-0 items-center justify-center gap-2 border-t border-border-base bg-bg-base/40 px-4 py-3 text-xs text-text-muted">
            <MapPin size={15} />
            هنوز موقعیت معتبری برای دستگاه‌های قابل‌دسترسی ثبت نشده است.
          </div>
        )}
      </section>
    </div>
  );
}

function Summary({ label, value, tone = 'text-text-primary', icon }) {
  return (
    <div className="flex min-h-[62px] items-center gap-2.5 rounded-xl border border-border-base bg-bg-elevated px-3 py-2 sm:gap-3 sm:px-3.5">
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-bg-base ${tone}`}>
        {icon}
      </span>
      <div className="min-w-0">
        <div className="truncate text-[11px] text-text-muted sm:text-xs">{label}</div>
        <div className={`mt-0.5 text-lg font-bold leading-6 tabular-nums ${tone}`}>{value.toLocaleString('fa-IR')}</div>
      </div>
    </div>
  );
}
