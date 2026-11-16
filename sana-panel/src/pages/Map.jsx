import { useEffect, useMemo, useState } from 'react';
import {
  CarFront, Clock3, MapPin, Navigation, PauseCircle,
  RefreshCw, Search, WifiOff, X, CircleHelp,
} from 'lucide-react';
import apiClient from '../api/client';
import { useAuth } from '../context/AuthContext';
import { formatJalaliDateTime } from '../utils/dateUtils';
import { TRACCAR_ATTRIBUTE_LABELS as ATTRIBUTE_LABELS } from '../utils/traccarAttributes';
import LiveDeviceMap from '../../../sana-map/src/LiveDeviceMap';
import { MAP_PROVIDER, MAP_PROVIDERS } from '../../../sana-map/src/config';

const STATUS_META = {
  moving: { label: 'در حرکت', tone: 'text-success', dot: 'bg-success' },
  stopped: { label: 'متوقف', tone: 'text-warning', dot: 'bg-warning' },
  offline: { label: 'آفلاین', tone: 'text-text-muted', dot: 'bg-text-muted' },
  unknown: { label: 'نامشخص', tone: 'text-text-secondary', dot: 'bg-text-secondary' },
};

const STATUS_FILTERS = [
  { value: 'all', label: 'همه' },
  { value: 'moving', label: 'در حرکت' },
  { value: 'stopped', label: 'متوقف' },
  { value: 'offline', label: 'آفلاین' },
  { value: 'unknown', label: 'نامشخص' },
];

const COMMON_ATTRIBUTES = [
  'ignition', 'motion', 'sat', 'rssi', 'power',
  'battery', 'fuel', 'odometer', 'hours', 'event',
  'priority', 'gpsStatus', 'hdop', 'pdop',
];

function formatTime(value) {
  return value ? formatJalaliDateTime(value) : 'نامشخص';
}

function formatAttribute(value) {
  if (value === null || value === undefined || value === '') return 'مقدار ارسال نشده';
  if (typeof value === 'boolean') return value ? 'بله / فعال' : 'خیر / غیرفعال';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function hasCoordinates(position) {
  return position?.latitude !== null && position?.latitude !== undefined
    && position?.longitude !== null && position?.longitude !== undefined
    && Number.isFinite(Number(position.latitude))
    && Number.isFinite(Number(position.longitude))
    && Number(position.latitude) >= -90 && Number(position.latitude) <= 90
    && Number(position.longitude) >= -180 && Number(position.longitude) <= 180;
}

export default function Map() {
  const { isPersonal } = useAuth();
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [mapProvider, setMapProvider] = useState(MAP_PROVIDER);
  const [refreshIntervalSeconds, setRefreshIntervalSeconds] = useState(10);
  const [followedDeviceId, setFollowedDeviceId] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [mobileListOpen, setMobileListOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

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
      .catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const sessionId = window.crypto?.randomUUID
      ? window.crypto.randomUUID()
      : `map-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const heartbeat = () => {
      apiClient.post('/devices/map-matching-activity/', {
        session_id: sessionId,
        active: true,
      }).catch(() => {});
    };
    heartbeat();
    const timer = window.setInterval(heartbeat, 15000);
    return () => {
      window.clearInterval(timer);
      apiClient.post('/devices/map-matching-activity/', {
        session_id: sessionId,
        active: false,
      }).catch(() => {});
    };
  }, []);

  useEffect(() => {
    let active = true;
    let timer = null;
    let inFlight = false;

    const refreshPositions = async () => {
      if (inFlight) return;
      inFlight = true;
      setRefreshing(true);
      try {
        const response = await apiClient.get('/devices/map-positions/');
        const data = response.data;
        const items = Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : [];
        if (active) {
          setPositions(items);
          setLastUpdated(new Date());
          setError('');
        }
      } catch (requestError) {
        if (active) {
          setError(requestError.response?.data?.detail
            || 'دریافت اطلاعات زنده از سرور سانا انجام نشد. اطلاعات قبلی تا برقراری ارتباط حفظ می‌شود.');
        }
      } finally {
        inFlight = false;
        if (active) {
          setLoading(false);
          setRefreshing(false);
          timer = window.setTimeout(refreshPositions, refreshIntervalSeconds * 1000);
        }
      }
    };

    refreshPositions();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [refreshIntervalSeconds, refreshKey]);

  useEffect(() => {
    if (!followedDeviceId) return;
    if (!positions.some((item) => String(item.device_id) === String(followedDeviceId))) {
      setFollowedDeviceId(null);
    }
  }, [positions, followedDeviceId]);

  const counts = useMemo(() => positions.reduce((result, item) => {
    result.total += 1;
    if (Object.prototype.hasOwnProperty.call(result, item.status)) result[item.status] += 1;
    else result.unknown += 1;
    if (hasCoordinates(item)) result.withPosition += 1;
    return result;
  }, { total: 0, moving: 0, stopped: 0, offline: 0, unknown: 0, withPosition: 0 }), [positions]);

  const filteredDevices = useMemo(() => {
    const query = search.trim().toLowerCase();
    return positions.filter((item) => {
      if (statusFilter !== 'all' && item.status !== statusFilter) return false;
      if (!query) return true;
      return [item.vehicle_plate, item.imei, item.phone]
        .some((value) => String(value || '').toLowerCase().includes(query));
    });
  }, [positions, search, statusFilter]);

  const selectedDevice = positions.find(
    (item) => String(item.device_id) === String(followedDeviceId),
  );

  const selectDevice = (id) => {
    setFollowedDeviceId(id);
    setMobileListOpen(false);
  };

  return (
    <div className="flex min-h-[calc(100dvh-6.5rem)] flex-col gap-3 lg:h-full lg:min-h-[600px]">
      <header className="flex shrink-0 items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-base font-semibold text-text-primary sm:text-lg">نقشه زنده</h1>
          <p className="mt-0.5 text-[11px] text-text-muted sm:text-xs">
            {isPersonal
              ? 'موقعیت و وضعیت لحظه‌ای دستگاه‌های شما'
              : 'نمای لحظه‌ای موقعیت و وضعیت دستگاه‌های GPS'}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-[10px] text-text-muted">
          <span className={`h-2 w-2 rounded-full ${error ? 'bg-danger' : refreshing ? 'bg-warning animate-pulse' : 'bg-success'}`} />
          <span className="hidden sm:inline">
            {error ? 'اختلال ارتباط' : refreshing ? 'در حال بروزرسانی' : 'اتصال برقرار'}
          </span>
          <button
            type="button"
            onClick={() => setRefreshKey((value) => value + 1)}
            disabled={refreshing}
            title="بروزرسانی موقعیت‌ها"
            aria-label="بروزرسانی موقعیت‌ها"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-base bg-bg-elevated text-text-secondary transition hover:text-text-primary disabled:opacity-50"
          >
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
          </button>
        </div>
      </header>

      {error && (
        <div role="alert" className="shrink-0 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs leading-6 text-text-primary">
          {error}
          {positions.length > 0 && <span className="mr-2 text-text-muted">آخرین اطلاعات موفق همچنان نمایش داده می‌شود.</span>}
        </div>
      )}

      <section className="relative isolate z-0 flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm sm:min-h-[580px]">
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
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-5 sm:gap-2">
            <Summary label="کل دستگاه‌ها" value={counts.total} icon={<CarFront size={15} />} />
            <Summary label="در حرکت" value={counts.moving} icon={<Navigation size={15} />} tone="text-success" />
            <Summary label="متوقف" value={counts.stopped} icon={<PauseCircle size={15} />} tone="text-warning" />
            <Summary label="آفلاین" value={counts.offline} icon={<WifiOff size={15} />} tone="text-text-muted" />
            <Summary label="نامشخص" value={counts.unknown} icon={<CircleHelp size={15} />} tone="text-text-secondary" />
          </div>
        </div>

        {isPersonal && (
          <>
            <div className="absolute right-2 top-[126px] z-[1000] hidden w-[276px] bottom-[72px] flex-col overflow-hidden rounded-xl border border-white/10 bg-bg-elevated/95 shadow-xl backdrop-blur-md lg:flex">
              <DeviceList
                devices={filteredDevices}
                selectedId={followedDeviceId}
                search={search}
                setSearch={setSearch}
                statusFilter={statusFilter}
                setStatusFilter={setStatusFilter}
                onSelect={selectDevice}
                total={positions.length}
              />
            </div>

            <button
              type="button"
              onClick={() => setMobileListOpen((value) => !value)}
              className="absolute right-2 top-[126px] z-[1000] flex items-center gap-2 rounded-lg border border-white/10 bg-bg-elevated/95 px-3 py-2 text-xs font-semibold text-text-primary shadow-lg backdrop-blur-md lg:hidden"
            >
              <CarFront size={15} />
              دستگاه‌ها ({positions.length.toLocaleString('fa-IR')})
              {mobileListOpen ? <X size={14} /> : <Search size={14} />}
            </button>

            {mobileListOpen && (
              <div className="absolute inset-x-2 bottom-[68px] top-[172px] z-[1000] flex flex-col overflow-hidden rounded-xl border border-white/10 bg-bg-elevated/95 shadow-xl backdrop-blur-md lg:hidden">
                <DeviceList
                  devices={filteredDevices}
                  selectedId={followedDeviceId}
                  search={search}
                  setSearch={setSearch}
                  statusFilter={statusFilter}
                  setStatusFilter={setStatusFilter}
                  onSelect={selectDevice}
                  total={positions.length}
                />
              </div>
            )}
          </>
        )}

        {selectedDevice && (
          <div className="absolute bottom-[68px] left-2 z-[1000] w-[min(320px,calc(100%-16px))] sm:left-3">
            <DeviceDetails position={selectedDevice} onClose={() => setFollowedDeviceId(null)} />
          </div>
        )}

        <div className="absolute inset-x-2 bottom-2 z-[1000] flex flex-wrap items-center justify-between gap-2 sm:inset-x-3 sm:bottom-3">
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
              <span className={`h-2 w-2 rounded-full ${error ? 'bg-danger' : refreshing ? 'bg-warning animate-pulse' : 'bg-success'}`} />
              {refreshing ? 'در حال دریافت' : error ? 'اختلال ارتباط' : 'دریافت زنده'}
            </span>
            <span>هر {refreshIntervalSeconds.toLocaleString('fa-IR')} ثانیه</span>
          </div>
          <div className="rounded-lg border border-white/10 bg-bg-elevated/95 px-2.5 py-2 text-[10px] text-text-muted shadow-lg backdrop-blur-md">
            <Clock3 size={12} className="ml-1 inline" />
            {lastUpdated ? formatTime(lastUpdated.toISOString()) : loading ? 'در انتظار اولین دریافت' : 'زمان دریافت نامشخص'}
          </div>
        </div>

        {!loading && !error && counts.total === 0 && (
          <div className="pointer-events-none absolute left-1/2 top-1/2 z-[1000] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border-base bg-bg-elevated/95 px-4 py-3 text-center text-xs text-text-primary shadow-lg backdrop-blur-md">
            <MapPin size={17} className="mx-auto mb-1 text-text-muted" />
            هنوز دستگاهی برای این حساب ثبت نشده است.
          </div>
        )}
        {!loading && !error && counts.total > 0 && counts.withPosition === 0 && (
          <div className="pointer-events-none absolute left-1/2 top-1/2 z-[900] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border-base bg-bg-elevated/95 px-4 py-3 text-center text-xs text-text-primary shadow-lg backdrop-blur-md">
            <MapPin size={17} className="mx-auto mb-1 text-text-muted" />
            هنوز هیچ‌یک از دستگاه‌ها مختصات قابل‌نمایش ارسال نکرده‌اند.
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
        <div className={`text-sm font-bold leading-5 tabular-nums sm:text-base ${tone}`}>{Number(value).toLocaleString('fa-IR')}</div>
      </div>
    </div>
  );
}

function DeviceList({ devices, selectedId, search, setSearch, statusFilter, setStatusFilter, onSelect, total }) {
  return (
    <>
      <div className="shrink-0 border-b border-border-base p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-xs font-bold text-text-primary">دستگاه‌های من</div>
          <span className="text-[10px] text-text-muted">{devices.length.toLocaleString('fa-IR')} از {total.toLocaleString('fa-IR')}</span>
        </div>
        <div className="relative">
          <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="جست‌وجوی پلاک یا IMEI"
            aria-label="جست‌وجوی دستگاه"
            className="w-full rounded-lg border border-border-base bg-bg-base py-2 pr-8 pl-3 text-xs text-text-primary outline-none placeholder:text-text-muted focus:border-brand-400"
          />
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {STATUS_FILTERS.map((item) => (
            <button
              type="button"
              key={item.value}
              onClick={() => setStatusFilter(item.value)}
              className={`rounded-md px-2 py-1 text-[10px] transition ${statusFilter === item.value ? 'bg-brand-500/15 text-brand-400' : 'bg-bg-base text-text-muted hover:text-text-primary'}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2">
        {devices.length === 0 ? (
          <div className="px-3 py-8 text-center text-xs leading-6 text-text-muted">دستگاهی با این مشخصات پیدا نشد.</div>
        ) : devices.map((device) => {
          const meta = STATUS_META[device.status] || STATUS_META.unknown;
          const active = String(selectedId) === String(device.device_id);
          return (
            <button
              type="button"
              key={device.device_id}
              onClick={() => onSelect(device.device_id)}
              className={`mb-1.5 flex w-full items-start gap-2 rounded-lg border px-2.5 py-2.5 text-right transition ${active ? 'border-brand-400/50 bg-brand-500/10' : 'border-transparent bg-bg-base/70 hover:border-border-base'}`}
            >
              <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${meta.dot}`} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-semibold text-text-primary">{device.vehicle_plate || device.imei || `دستگاه ${device.device_id}`}</span>
                <span className="mt-1 block truncate text-[10px] text-text-muted" dir="ltr">{device.imei || 'IMEI ثبت نشده'}</span>
                <span className={`mt-1 block text-[10px] ${meta.tone}`}>{meta.label} · {device.speed == null ? 'سرعت نامشخص' : `${Number(device.speed).toLocaleString('fa-IR')} km/h`}</span>
                <span className="mt-0.5 block truncate text-[9px] text-text-muted">آخرین دریافت: {formatTime(device.last_seen)}</span>
              </span>
            </button>
          );
        })}
      </div>
    </>
  );
}

function DeviceDetails({ position, onClose }) {
  const title = position.vehicle_plate || position.imei || `دستگاه ${position.device_id}`;
  const meta = STATUS_META[position.status] || STATUS_META.unknown;
  const attributes = position.attributes && typeof position.attributes === 'object' && !Array.isArray(position.attributes)
    ? position.attributes : {};
  const keys = [...new Set([...COMMON_ATTRIBUTES, ...Object.keys(attributes)])];

  return (
    <div dir="rtl" className="max-h-[42vh] overflow-hidden rounded-xl border border-white/10 bg-bg-elevated/95 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
        <div className="min-w-0">
          <div className="truncate text-xs font-bold text-text-primary">{title}</div>
          <div className={`mt-0.5 text-[10px] ${meta.tone}`}>{meta.label}</div>
        </div>
        <button type="button" onClick={onClose} aria-label="بستن جزئیات دستگاه" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-text-muted hover:bg-bg-base hover:text-text-primary">
          <X size={14} />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 px-3 py-2 text-[10px]">
        <Info label="سرعت" value={position.speed == null ? '—' : `${Number(position.speed).toLocaleString('fa-IR')} km/h`} />
        <Info label="شماره سیم‌کارت" value={position.phone || 'ثبت نشده'} />
        <Info label="آخرین دریافت Traccar" value={formatTime(position.last_seen)} />
        <Info label="زمان پیام دستگاه" value={formatTime(position.device_time)} />
        <Info label="موقعیت" value={hasCoordinates(position) ? (position.position_is_current ? 'Fix معتبر' : 'آخرین مختصات معتبر') : 'مختصات موجود نیست'} />
        <Info label="تطبیق جاده‌ای" value={position.position_is_matched ? 'انجام شده' : 'انجام نشده'} />
      </div>
      {!position.position_is_current && hasCoordinates(position) && (
        <div className="px-3 pb-2 text-[10px] text-warning">GPS فعلی فاقد Fix معتبر است؛ آخرین مختصات معتبر نمایش داده می‌شود.</div>
      )}
      <details className="border-t border-white/10">
        <summary className="cursor-pointer px-3 py-2 text-[10px] font-semibold text-text-secondary">اطلاعات فنی و Attributeهای Traccar</summary>
        <div className="max-h-36 overflow-y-auto px-3 pb-2">
          {keys.map((key) => (
            <div key={key} className="flex items-start justify-between gap-3 border-b border-white/5 py-1 text-[10px]">
              <span className="text-text-muted">{ATTRIBUTE_LABELS[key] || key} <span className="opacity-60">({key})</span></span>
              <strong className="break-all text-left font-medium text-text-primary">{Object.prototype.hasOwnProperty.call(attributes, key) ? formatAttribute(attributes[key]) : 'فاقد اطلاعات'}</strong>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="min-w-0">
      <div className="text-text-muted">{label}</div>
      <div className="mt-0.5 break-words font-medium text-text-primary">{value}</div>
    </div>
  );
}
