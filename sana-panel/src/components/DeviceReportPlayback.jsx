import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, CalendarClock, ChevronLeft, ChevronRight, CircleAlert, Download, Gauge, LoaderCircle, Pause, Play, Route, Search, SkipBack, SkipForward, Clock3, Zap, Fuel, Signal } from 'lucide-react';
import apiClient from '../api/client';
import LiveDeviceMap from '../../../sana-map/src/LiveDeviceMap';
import { MAP_PROVIDER, MAP_PROVIDERS } from '../../../sana-map/src/config';

const dateTimeLocal = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};
const toApiDate = (value) => value ? new Date(value).toISOString() : '';
const formatDate = (value) => value ? new Date(value).toLocaleString('fa-IR') : '—';
const showValue = (value, suffix = '') => value === null || value === undefined || value === '' ? '—' : `${value}${suffix}`;
const pointCoordinates = (point) => [
  Number(point.matched_latitude ?? point.latitude),
  Number(point.matched_longitude ?? point.longitude),
];
const distanceBetween = (a, b) => {
  const [lat1, lon1] = pointCoordinates(a).map((value) => value * Math.PI / 180);
  const [lat2, lon2] = pointCoordinates(b).map((value) => value * Math.PI / 180);
  if (![lat1, lon1, lat2, lon2].every(Number.isFinite)) return 0;
  const dLat = lat2 - lat1;
  const dLon = lon2 - lon1;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
};
const formatDuration = (milliseconds) => {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return '—';
  const totalMinutes = Math.floor(milliseconds / 60000);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  return [days ? `${days} روز` : '', hours ? `${hours} ساعت` : '', `${minutes} دقیقه`].filter(Boolean).join(' و ');
};

function normalizeList(payload) {
  return Array.isArray(payload) ? payload : Array.isArray(payload?.results) ? payload.results : [];
}
async function getAllPages(path) {
  let url = path;
  const items = [];
  while (url) {
    const { data } = await apiClient.get(url);
    items.push(...normalizeList(data));
    url = !Array.isArray(data) ? data?.next || null : null;
  }
  return items;
}

export default function DeviceReportPlayback({ isSiteAdmin }) {
  const [devices, setDevices] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [search, setSearch] = useState('');
  const [devicePickerOpen, setDevicePickerOpen] = useState(false);
  const [deviceId, setDeviceId] = useState('');
  const [metadata, setMetadata] = useState(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [provider, setProvider] = useState(MAP_PROVIDER);
  const [points, setPoints] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [pointIndex, setPointIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const timerRef = useRef(null);
  const searchInputRef = useRef(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      getAllPages('/devices/?page_size=1000'),
      getAllPages('/driver-vehicle-assignments/?page_size=1000'),
    ]).then(([deviceRows, assignmentRows]) => {
      if (!active) return;
      setDevices(deviceRows);
      setAssignments(assignmentRows);
    }).catch((err) => {
      if (active) setError(err.response?.data?.detail || 'دریافت فهرست دستگاه‌های مجاز ناموفق بود.');
    }).finally(() => { if (active) setLoadingDevices(false); });
    return () => { active = false; };
  }, []);

  const searchableDevices = useMemo(() => devices.map((device) => {
    const plate = device.vehicle_plate || '';
    const matchingAssignments = assignments.filter((assignment) => assignment.vehicle_plate === plate && plate);
    const driverNames = matchingAssignments.map((assignment) => assignment.driver_name || '').filter(Boolean);
    return { ...device, driverNames, searchText: [device.imei, device.sim_number, plate, device.customer_name, ...driverNames].join(' ').toLocaleLowerCase() };
  }), [devices, assignments]);

  const filteredDevices = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    if (!query) return searchableDevices;
    return searchableDevices.filter((device) => device.searchText.includes(query));
  }, [search, searchableDevices]);

  const selectedDevice = devices.find((item) => String(item.id) === String(deviceId));
  const deviceLabel = (device) => [
    device.imei,
    device.sim_number ? `SIM ${device.sim_number}` : '',
    device.vehicle_plate || '',
    ...(device.driverNames || []),
  ].filter(Boolean).join(' · ');

  useEffect(() => {
    setMetadata(null);
    setPoints([]);
    setPointIndex(0);
    setProgress(0);
    setPlaying(false);
    setNotice('');
    setError('');
    if (!deviceId) return undefined;
    let active = true;
    apiClient.get('/devices/report-history/', { params: { device_id: deviceId, metadata: 'true' } })
      .then(({ data }) => {
        if (!active) return;
        setMetadata(data);
        if (!isSiteAdmin && data.range_start && data.range_end) {
          setFrom(dateTimeLocal(data.range_start));
          setTo(dateTimeLocal(data.range_end));
        }
      })
      .catch((err) => { if (active) setError(err.response?.data?.detail || 'دریافت محدوده مجاز دستگاه ناموفق بود.'); });
    return () => { active = false; };
  }, [deviceId, isSiteAdmin]);

  const loadHistory = useCallback(async () => {
    if (!deviceId || !from || !to) {
      setError('دستگاه، زمان شروع و زمان پایان را انتخاب کنید.');
      return;
    }
    if (new Date(from) > new Date(to)) {
      setError('زمان شروع باید قبل از زمان پایان باشد.');
      return;
    }
    setLoadingHistory(true);
    setPlaying(false);
    setError('');
    setNotice('');
    setPoints([]);
    setPointIndex(0);
    setProgress(0);
    try {
      const allPoints = [];
      let cursor = null;
      let page = 0;
      do {
        const params = {
          device_id: deviceId,
          from: toApiDate(from),
          to: toApiDate(to),
        };
        if (cursor) Object.assign(params, cursor);
        const { data } = await apiClient.get('/devices/report-history/', { params });
        allPoints.push(...(data.points || []));
        cursor = data.next_cursor || null;
        page += 1;
        if (page > 200) throw new Error('بازه انتخابی بیش از حد بزرگ است؛ بازه کوتاه‌تری انتخاب کنید.');
      } while (cursor);
      const validPoints = allPoints.filter((point) =>
        (point.matched_latitude !== null && point.matched_latitude !== undefined && point.matched_longitude !== null && point.matched_longitude !== undefined) ||
        (point.latitude !== null && point.latitude !== undefined && point.longitude !== null && point.longitude !== undefined)
      );
      setPoints(validPoints);
      if (validPoints.length === 0) setNotice('در این بازه نقطه مکانی معتبر ثبت نشده است.');
      else if (validPoints.some((point) => point.matched_latitude == null || point.matched_longitude == null)) {
        setNotice('برخی نقاط هنوز مختصات تطبیق‌یافته ندارند؛ برای آن نقاط از مختصات خام GPS استفاده می‌شود.');
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'دریافت تاریخچه دستگاه ناموفق بود.');
    } finally {
      setLoadingHistory(false);
    }
  }, [deviceId, from, to]);

  useEffect(() => {
    if (!playing || points.length < 2) return undefined;
    timerRef.current = window.setInterval(() => {
      setPointIndex((current) => {
        const next = current + 1;
        return Math.min(next, points.length - 1);
      });
    }, Math.max(150, 900 / speed));
    return () => { if (timerRef.current) window.clearInterval(timerRef.current); };
  }, [playing, points.length, speed]);

  useEffect(() => {
    setProgress(points.length > 1 ? (pointIndex / (points.length - 1)) * 100 : 0);
  }, [pointIndex, points.length]);

  useEffect(() => {
    if (playing && points.length > 0 && pointIndex >= points.length - 1) setPlaying(false);
  }, [playing, pointIndex, points.length]);

  const routeSegments = useMemo(() => {
    const colorForSpeed = (value) => {
      const speedValue = Number(value);
      if (!Number.isFinite(speedValue) || speedValue < 20) return { color: '#2563EB', speedBand: '0-20' };
      if (speedValue < 40) return { color: '#16A34A', speedBand: '20-40' };
      if (speedValue < 60) return { color: '#EAB308', speedBand: '40-60' };
      if (speedValue < 80) return { color: '#F97316', speedBand: '60-80' };
      return { color: '#DC2626', speedBand: '80+' };
    };
    const segments = [];
    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const current = points[index];
      const previousLat = previous.matched_latitude ?? previous.latitude;
      const previousLng = previous.matched_longitude ?? previous.longitude;
      const currentLat = current.matched_latitude ?? current.latitude;
      const currentLng = current.matched_longitude ?? current.longitude;
      if ([previousLat, previousLng, currentLat, currentLng].some((value) => value == null || !Number.isFinite(Number(value)))) continue;
      const band = colorForSpeed(current.speed ?? previous.speed ?? 0);
      const coordinates = [[Number(previousLat), Number(previousLng)], [Number(currentLat), Number(currentLng)]];
      const last = segments[segments.length - 1];
      if (last && last.speedBand === band.speedBand && last.coordinates[last.coordinates.length - 1][0] === coordinates[0][0] && last.coordinates[last.coordinates.length - 1][1] === coordinates[0][1]) {
        last.coordinates.push(coordinates[1]);
      } else {
        segments.push({ ...band, coordinates });
      }
    }
    return segments;
  }, [points]);

  const reportStats = useMemo(() => {
    if (!points.length) return null;
    let distanceKm = 0;
    for (let index = 1; index < points.length; index += 1) {
      const previousTime = new Date(points[index - 1].device_time).getTime();
      const currentTime = new Date(points[index].device_time).getTime();
      const elapsedHours = (currentTime - previousTime) / 3600000;
      if (elapsedHours <= 0 || elapsedHours > (10 / 60)) continue;
      const segmentKm = distanceBetween(points[index - 1], points[index]);
      if (segmentKm / elapsedHours <= 180) distanceKm += segmentKm;
    }
    const speeds = points.filter((point) => point.speed != null && point.speed !== '').map((point) => Number(point.speed)).filter(Number.isFinite);
    const movingPoints = points.filter((point) => point.motion === true || Number(point.speed) >= 3).length;
    const start = new Date(points[0].device_time).getTime();
    const end = new Date(points[points.length - 1].device_time).getTime();
    return {
      distanceKm,
      maxSpeed: speeds.reduce((maximum, value) => Math.max(maximum, value), 0),
      averageSpeed: speeds.length ? speeds.reduce((sum, value) => sum + value, 0) / speeds.length : 0,
      duration: end - start,
      movingPoints,
      stoppedPoints: points.length - movingPoints,
    };
  }, [points]);

  const advancedStats = useMemo(() => {
    if (!points.length) return null;
    const isMoving = (point) => point.motion === true || (point.motion == null && Number(point.speed || 0) >= 3);
    const ignitionState = (point) => typeof point.ignition === 'boolean' ? point.ignition : null;
    let movingMs = 0;
    let ignitionOnMs = 0;
    let ignitionOffMs = 0;
    let unknownIgnitionMs = 0;
    let trips = 0;
    let wasMoving = false;
    const stops = [];
    let activeStop = null;
    const speedSamples = points.filter((point) => point.speed != null && point.speed !== '' && Number.isFinite(Number(point.speed)));
    for (let index = 0; index < points.length; index += 1) {
      const point = points[index];
      const moving = isMoving(point);
      if (moving && !wasMoving) trips += 1;
      wasMoving = moving;
      if (!moving) {
        if (!activeStop) activeStop = { start: point.device_time, end: point.device_time, points: 0 };
        activeStop.end = point.device_time;
        activeStop.points += 1;
      } else if (activeStop) {
        const duration = new Date(activeStop.end).getTime() - new Date(activeStop.start).getTime();
        if (duration >= 180000) stops.push({ ...activeStop, duration });
        activeStop = null;
      }
      if (index === points.length - 1) continue;
      const currentTime = new Date(point.device_time).getTime();
      const next = points[index + 1];
      const nextTime = new Date(next.device_time).getTime();
      const delta = nextTime - currentTime;
      // فاصله‌های طولانی بین دو پیام را به‌عنوان حرکت/روشن بودن قطعی حساب نمی‌کنیم.
      const trustedDelta = Number.isFinite(delta) && delta > 0 ? Math.min(delta, 600000) : 0;
      if (moving) movingMs += trustedDelta;
      const ignition = ignitionState(point);
      if (ignition === true) ignitionOnMs += trustedDelta;
      else if (ignition === false) ignitionOffMs += trustedDelta;
      else unknownIgnitionMs += trustedDelta;
    }
    if (activeStop) {
      const duration = new Date(activeStop.end).getTime() - new Date(activeStop.start).getTime();
      if (duration >= 180000) stops.push({ ...activeStop, duration });
    }
    const sampleCount = 36;
    const sampledSpeeds = speedSamples.length <= sampleCount
      ? speedSamples.map((point) => Number(point.speed))
      : Array.from({ length: sampleCount }, (_, index) => Number(speedSamples[Math.round(index * (speedSamples.length - 1) / (sampleCount - 1))].speed));
    const maxSample = Math.max(1, ...sampledSpeeds);
    return {
      tripCount: trips,
      movingMs,
      ignitionOnMs,
      ignitionOffMs,
      unknownIgnitionMs,
      stops: stops.sort((a, b) => b.duration - a.duration),
      sampledSpeeds,
      maxSample,
      minSpeed: speedSamples.length ? Math.min(...speedSamples.map((point) => Number(point.speed))) : 0,
    };
  }, [points]);

  const exportCsv = () => {
    if (!points.length) return;
    const columns = ['device_time', 'server_received_at', 'latitude', 'longitude', 'matched_latitude', 'matched_longitude', 'speed', 'heading', 'altitude', 'accuracy', 'gps_valid', 'motion', 'ignition', 'satellites', 'battery_voltage', 'external_voltage', 'gsm_signal', 'odometer', 'engine_hours', 'fuel_level', 'attributes'];
    const escapeCsv = (value) => {
      const raw = value && typeof value === 'object' ? JSON.stringify(value) : String(value ?? '');
      return `"${raw.replace(/"/g, '""')}"`;
    };
    const rows = [columns.join(','), ...points.map((point) => columns.map((key) => escapeCsv(point[key])).join(','))];
    const blob = new Blob(['\uFEFF', rows.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `sana-device-${deviceId}-report.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const currentPoint = points[pointIndex] || null;
  const mapPosition = useMemo(() => {
    if (!currentPoint) return [];
    const latitude = currentPoint.matched_latitude ?? currentPoint.latitude;
    const longitude = currentPoint.matched_longitude ?? currentPoint.longitude;
    if (latitude === null || longitude === null || latitude === undefined || longitude === undefined) return [];
    return [{
      device_id: Number(deviceId),
      imei: selectedDevice?.imei || metadata?.device?.imei || '',
      vehicle_plate: selectedDevice?.vehicle_plate || metadata?.device?.vehicle_plate || null,
      latitude: Number(latitude),
      longitude: Number(longitude),
      speed: Number(currentPoint.speed || 0),
      heading: currentPoint.heading === null ? null : Number(currentPoint.heading),
      device_time: currentPoint.device_time,
      position_is_current: Boolean(currentPoint.gps_valid),
      position_is_matched: currentPoint.matched_latitude != null && currentPoint.matched_longitude != null,
      status: currentPoint.motion || Number(currentPoint.speed || 0) >= 3 ? 'moving' : 'stopped',
    }];
  }, [currentPoint, deviceId, selectedDevice, metadata]);

  const moveBy = (delta) => {
    setPlaying(false);
    setPointIndex((index) => Math.min(Math.max(0, index + delta), Math.max(0, points.length - 1)));
  };

  const attributes = currentPoint?.attributes && typeof currentPoint.attributes === 'object' ? currentPoint.attributes : {};

  return (
    <section className="space-y-4 border-t border-border-base pt-7">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-brand-500/20 bg-brand-500/5 px-3 py-1 text-xs font-medium text-brand-600">
            <Activity size={14} /> گزارش مسیر و بازپخش دستگاه
          </div>
          <h2 className="text-xl font-bold text-text-primary sm:text-2xl">تاریخچه موقعیت GPS</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">داده‌های واقعی ذخیره‌شده در تاریخچه GPS؛ مختصات تطبیق‌یافته با جاده در اولویت است.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <span>نقشه:</span>
          <select aria-label="انتخاب ارائه‌دهنده نقشه" value={provider} onChange={(event) => setProvider(event.target.value)} className="rounded-lg border border-border-base bg-bg-elevated px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-400">
            <option value={MAP_PROVIDERS.LEAFLET_OSM}>OpenStreetMap</option>
            <option value={MAP_PROVIDERS.NESHAN_LEAFLET}>نشان</option>
          </select>
        </label>
      </div>

      <div className="rounded-2xl border border-border-base bg-bg-elevated p-4 shadow-sm">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(240px,1.3fr)_minmax(180px,1fr)_minmax(180px,1fr)]">
          <div className="relative">
            <label htmlFor="device-report-search" className="mb-2 block text-sm font-medium text-text-primary">جست‌وجو و انتخاب دستگاه</label>
            <div className="relative">
              <Search size={17} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                ref={searchInputRef}
                id="device-report-search"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={devicePickerOpen}
                aria-controls="device-report-options"
                autoComplete="off"
                value={search}
                onFocus={() => setDevicePickerOpen(true)}
                onBlur={() => setDevicePickerOpen(false)}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setDeviceId('');
                  setDevicePickerOpen(true);
                }}
                placeholder={loadingDevices ? 'در حال دریافت دستگاه‌ها…' : 'شناسه، سیم‌کارت، پلاک یا نام راننده را بنویسید'}
                disabled={loadingDevices}
                className="w-full rounded-xl border border-border-base bg-bg-base py-2.5 pr-10 pl-3 text-sm text-text-primary outline-none focus:border-brand-400 disabled:opacity-60"
              />
              {devicePickerOpen && (
                <div id="device-report-options" role="listbox" className="absolute inset-x-0 top-full z-[1200] mt-1 max-h-64 overflow-y-auto rounded-xl border border-border-base bg-bg-elevated p-1 shadow-xl">
                  {filteredDevices.length > 0 ? filteredDevices.slice(0, 100).map((device) => (
                    <button
                      key={device.id}
                      type="button"
                      role="option"
                      aria-selected={String(device.id) === String(deviceId)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        setDeviceId(String(device.id));
                        setSearch(deviceLabel(device));
                        setDevicePickerOpen(false);
                      }}
                      className={`block w-full rounded-lg px-3 py-2 text-right text-sm transition hover:bg-brand-500/10 ${String(device.id) === String(deviceId) ? 'bg-brand-500/10 text-brand-600' : 'text-text-primary'}`}
                    >
                      <span className="block font-medium">{device.imei || `دستگاه ${device.id}`}</span>
                      <span className="mt-0.5 block text-xs text-text-muted">
                        {[device.sim_number ? `سیم‌کارت: ${device.sim_number}` : '', device.vehicle_plate ? `پلاک: ${device.vehicle_plate}` : '', ...(device.driverNames || [])].filter(Boolean).join(' · ') || 'اطلاعات تکمیلی ثبت نشده'}
                      </span>
                    </button>
                  )) : (
                    <p className="px-3 py-3 text-sm text-text-muted">{loadingDevices ? 'در حال دریافت دستگاه‌ها…' : 'دستگاهی با این عبارت پیدا نشد.'}</p>
                  )}
                </div>
              )}
            </div>
            {selectedDevice && !devicePickerOpen && <p className="mt-2 text-xs text-text-muted">دستگاه انتخاب‌شده: {deviceLabel(selectedDevice)}</p>}
          </div>
                    <div>
            <label htmlFor="device-report-from" className="mb-2 block text-sm font-medium text-text-primary">از تاریخ و ساعت</label>
            <input id="device-report-from" type="datetime-local" value={from} min={!isSiteAdmin && metadata?.range_start ? dateTimeLocal(metadata.range_start) : undefined} max={!isSiteAdmin && metadata?.range_end ? dateTimeLocal(metadata.range_end) : undefined} onChange={(event) => setFrom(event.target.value)} className="w-full rounded-xl border border-border-base bg-bg-base px-3 py-2.5 text-sm text-text-primary outline-none focus:border-brand-400" />
            <p className="mt-2 text-xs text-text-muted">{isSiteAdmin ? 'ادمین: بدون محدودیت قراردادی' : metadata?.range_start ? `محدوده قرارداد: ${formatDate(metadata.range_start)} تا ${formatDate(metadata.range_end)}` : 'ابتدا دستگاه مجاز را انتخاب کنید.'}</p>
          </div>
          <div>
            <label htmlFor="device-report-to" className="mb-2 block text-sm font-medium text-text-primary">تا تاریخ و ساعت</label>
            <input id="device-report-to" type="datetime-local" value={to} min={!isSiteAdmin && metadata?.range_start ? dateTimeLocal(metadata.range_start) : undefined} max={!isSiteAdmin && metadata?.range_end ? dateTimeLocal(metadata.range_end) : undefined} onChange={(event) => setTo(event.target.value)} className="w-full rounded-xl border border-border-base bg-bg-base px-3 py-2.5 text-sm text-text-primary outline-none focus:border-brand-400" />
            <button type="button" onClick={loadHistory} disabled={loadingHistory || !deviceId} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60">
              {loadingHistory ? <LoaderCircle size={16} className="animate-spin" /> : <CalendarClock size={16} />}
              {loadingHistory ? 'در حال دریافت مسیر…' : 'نمایش مسیر و گزارش'}
            </button>
          </div>
        </div>
      </div>

      {error && <div role="alert" className="flex items-start gap-2 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger"><CircleAlert size={17} className="mt-0.5 shrink-0" />{error}</div>}
      {notice && <div className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-text-primary">{notice}</div>}

      {reportStats && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-text-primary">خلاصه عملکرد در بازه انتخابی</h3>
              <p className="mt-1 text-xs text-text-muted">محاسبات بر اساس نقاط دریافت‌شده از Traccar انجام شده‌اند.</p>
            </div>
            <button type="button" onClick={exportCsv} className="inline-flex items-center gap-2 rounded-lg border border-border-base px-3 py-2 text-sm font-medium text-text-secondary transition hover:bg-bg-hover">
              <Download size={16} /> خروجی CSV
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {[
              { label: 'مسافت تقریبی', value: `${reportStats.distanceKm.toFixed(2)} km`, icon: Route },
              { label: 'حداکثر سرعت', value: `${reportStats.maxSpeed.toFixed(1)} km/h`, icon: Gauge },
              { label: 'میانگین سرعت نقاط', value: `${reportStats.averageSpeed.toFixed(1)} km/h`, icon: Activity },
              { label: 'مدت بازه ثبت‌شده', value: formatDuration(reportStats.duration), icon: CalendarClock },
              { label: 'نقاط حرکت / توقف', value: `${reportStats.movingPoints.toLocaleString('fa-IR')} / ${reportStats.stoppedPoints.toLocaleString('fa-IR')}`, icon: Activity },
            ].map((item) => {
              const Icon = item.icon;
              return <div key={item.label} className="rounded-xl border border-border-base bg-bg-elevated p-3"><div className="flex items-center gap-2 text-xs text-text-muted"><Icon size={15} />{item.label}</div><div className="mt-2 text-base font-semibold text-text-primary">{item.value}</div></div>;
            })}
          </div>
        </section>
      )}

      {advancedStats && (
        <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div className="rounded-2xl border border-border-base bg-bg-elevated p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2"><Gauge size={17} className="text-brand-500" /><h3 className="font-semibold text-text-primary">نمودار سرعت در طول زمان</h3></div>
            <div className="flex h-32 items-end gap-1 rounded-xl bg-bg-base px-3 pb-3 pt-4" role="img" aria-label="نمودار نمونه‌برداری‌شده سرعت">
              {advancedStats.sampledSpeeds.map((value, index) => <div key={index} title={`سرعت: ${value.toFixed(1)} کیلومتر بر ساعت`} className="min-w-0 flex-1 rounded-t-sm bg-brand-500/80 hover:bg-brand-500" style={{ height: `${Math.max(3, (value / advancedStats.maxSample) * 100)}%` }} />)}
            </div>
            <div className="mt-2 flex justify-between text-xs text-text-muted"><span>کمینه: {advancedStats.minSpeed.toFixed(1)} km/h</span><span>بیشینه: {reportStats.maxSpeed.toFixed(1)} km/h</span></div>
            <p className="mt-2 text-[11px] text-text-muted">برای خوانایی، حداکثر ۳۶ نقطه از داده‌های سرعت نمونه‌برداری شده است.</p>
          </div>
          <div className="rounded-2xl border border-border-base bg-bg-elevated p-4 shadow-sm">
            <div className="mb-3 flex items-center gap-2"><Zap size={17} className="text-brand-500" /><h3 className="font-semibold text-text-primary">تحلیل وضعیت سوئیچ و حرکت</h3></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-bg-base p-3"><div className="flex items-center gap-2 text-xs text-text-muted"><Activity size={14} /> تعداد سفرهای تشخیص‌داده‌شده</div><div className="mt-2 text-xl font-bold text-text-primary">{advancedStats.tripCount.toLocaleString('fa-IR')}</div></div>
              <div className="rounded-xl bg-bg-base p-3"><div className="flex items-center gap-2 text-xs text-text-muted"><Clock3 size={14} /> زمان حرکت تخمینی</div><div className="mt-2 text-base font-bold text-text-primary">{formatDuration(advancedStats.movingMs)}</div></div>
              <div className="rounded-xl bg-bg-base p-3"><div className="flex items-center gap-2 text-xs text-text-muted"><Zap size={14} /> سوئیچ روشن</div><div className="mt-2 text-base font-bold text-text-primary">{formatDuration(advancedStats.ignitionOnMs)}</div></div>
              <div className="rounded-xl bg-bg-base p-3"><div className="flex items-center gap-2 text-xs text-text-muted"><Fuel size={14} /> سوئیچ خاموش</div><div className="mt-2 text-base font-bold text-text-primary">{formatDuration(advancedStats.ignitionOffMs)}</div></div>
            </div>
            <p className="mt-3 text-[11px] leading-5 text-text-muted">مدت‌ها از فاصله زمانی بین پیام‌های متوالی برآورد شده‌اند؛ فاصله‌های بیش از ۱۰ دقیقه برای جلوگیری از محاسبه اشتباه محدود شده‌اند. زمان با وضعیت سوئیچ نامشخص: {formatDuration(advancedStats.unknownIgnitionMs)}.</p>
          </div>
          <div className="rounded-2xl border border-border-base bg-bg-elevated p-4 shadow-sm xl:col-span-2">
            <div className="mb-3 flex items-center justify-between gap-2"><h3 className="font-semibold text-text-primary">توقف‌های مهم (حداقل ۳ دقیقه)</h3><span className="text-xs text-text-muted">{advancedStats.stops.length.toLocaleString('fa-IR')} توقف</span></div>
            {advancedStats.stops.length ? <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-sm"><thead><tr className="border-b border-border-base text-right text-xs text-text-muted"><th className="px-3 py-2 font-medium">شروع توقف</th><th className="px-3 py-2 font-medium">پایان توقف</th><th className="px-3 py-2 font-medium">مدت</th><th className="px-3 py-2 font-medium">تعداد نقاط</th></tr></thead><tbody>{advancedStats.stops.map((stop, index) => <tr key={`${stop.start}-${index}`} className="border-b border-border-base/60 last:border-0"><td className="px-3 py-2 text-text-primary">{formatDate(stop.start)}</td><td className="px-3 py-2 text-text-primary">{formatDate(stop.end)}</td><td className="px-3 py-2 font-medium text-text-primary">{formatDuration(stop.duration)}</td><td className="px-3 py-2 text-text-secondary">{stop.points.toLocaleString('fa-IR')}</td></tr>)}</tbody></table></div> : <p className="py-5 text-center text-sm text-text-muted">توقف طولانی در این بازه تشخیص داده نشد.</p>}
          </div>
        </section>
      )}

      <div className="overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-base px-4 py-3">
          <div className="text-sm font-semibold text-text-primary">{metadata?.device?.imei || selectedDevice?.imei || 'دستگاه انتخاب نشده'}</div>
          <div className="text-xs text-text-muted">{points.length.toLocaleString('fa-IR')} نقطه {loadingHistory ? '· در حال بارگذاری' : ''}</div>
        </div>
        <div className="h-[min(62vh,680px)] min-h-[360px]">
          {mapPosition.length ? <LiveDeviceMap positions={mapPosition} provider={provider} followPosition animationDuration={Math.max(150, 900 / speed)} routeSegments={routeSegments} /> : <div className="flex h-full items-center justify-center text-sm text-text-muted">پس از انتخاب دستگاه و بازه زمانی، مسیر در این نقشه نمایش داده می‌شود.</div>}
        </div>
        <div className="space-y-3 border-t border-border-base p-4">
          <div className="flex flex-wrap gap-3 text-xs text-text-secondary" aria-label="راهنمای رنگ مسیر بر اساس سرعت">
            {[['#2563EB','۰ تا ۲۰'],['#16A34A','۲۰ تا ۴۰'],['#EAB308','۴۰ تا ۶۰'],['#F97316','۶۰ تا ۸۰'],['#DC2626','۸۰ به بالا']].map(([color,label]) => <span key={label} className="inline-flex items-center gap-1.5"><span className="inline-block h-1 w-5 rounded-full" style={{ backgroundColor: color }} />{label} km/h</span>)}
          </div>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3" dir="ltr">
            <div className="flex items-center justify-start gap-2">
              <button type="button" onClick={() => { setPointIndex(0); setPlaying(false); }} disabled={!points.length} title="ابتدای مسیر" aria-label="ابتدای مسیر" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><SkipBack size={17} /></button>
              <button type="button" onClick={() => moveBy(-1)} disabled={!points.length || pointIndex === 0} title="فریم قبلی" aria-label="فریم قبلی" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><ChevronLeft size={17} /></button>
            </div>
            <button type="button" onClick={() => setPlaying((value) => !value)} disabled={points.length < 2} className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{playing ? <Pause size={16} /> : <Play size={16} />}{playing ? 'توقف' : 'پخش'}</button>
            <div className="flex items-center justify-end gap-2">
              <button type="button" onClick={() => moveBy(1)} disabled={!points.length || pointIndex >= points.length - 1} title="فریم بعدی" aria-label="فریم بعدی" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><ChevronRight size={17} /></button>
              <button type="button" onClick={() => { setPointIndex(Math.max(0, points.length - 1)); setPlaying(false); }} disabled={!points.length} title="انتهای مسیر" aria-label="انتهای مسیر" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><SkipForward size={17} /></button>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-xs text-text-muted">سرعت
              <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))} className="rounded-lg border border-border-base bg-bg-base px-2 py-1.5 text-text-primary"><option value={0.5}>۰٫۵×</option><option value={1}>۱×</option><option value={2}>۲×</option><option value={4}>۴×</option></select>
            </label>
            <span className="text-xs text-text-muted" dir="rtl">{points.length ? `${(pointIndex + 1).toLocaleString('fa-IR')} از ${points.length.toLocaleString('fa-IR')}` : 'بدون نقطه'}</span>
          </div>
          <input aria-label="موقعیت در مسیر" type="range" min="0" max={Math.max(0, points.length - 1)} value={pointIndex} onChange={(event) => { setPlaying(false); setPointIndex(Number(event.target.value)); }} disabled={!points.length} className="w-full accent-brand-500" style={{ backgroundSize: `${progress}% 100%` }} />
          <div className="flex flex-wrap justify-between gap-2 text-xs text-text-muted"><span>زمان نقطه: {formatDate(currentPoint?.device_time)}</span><span>{currentPoint && currentPoint.matched_latitude != null && currentPoint.matched_longitude != null ? 'مختصات تطبیق‌یافته با جاده' : currentPoint ? 'مختصات خام GPS' : '—'}</span></div>
        </div>
      </div>

      <section className="rounded-2xl border border-border-base bg-bg-elevated p-4 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-2"><h3 className="font-semibold text-text-primary">ویژگی‌های دستگاه در نقطه انتخاب‌شده</h3><span className="text-xs text-text-muted">{currentPoint ? formatDate(currentPoint.device_time) : '—'}</span></div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {[
            ['سرعت', showValue(currentPoint?.speed, ' km/h')],
            ['مختصات عرض خام', showValue(currentPoint?.latitude)],
            ['مختصات طول خام', showValue(currentPoint?.longitude)],
            ['عرض تطبیق‌یافته', showValue(currentPoint?.matched_latitude)],
            ['طول تطبیق‌یافته', showValue(currentPoint?.matched_longitude)],
            ['دقت GPS', showValue(currentPoint?.accuracy, ' m')],
            ['جهت حرکت', showValue(currentPoint?.heading, '°')],
            ['ارتفاع', showValue(currentPoint?.altitude, ' m')],
            ['ماهواره‌ها', showValue(currentPoint?.satellites)],
            ['وضعیت GPS', currentPoint ? (currentPoint.gps_valid ? 'معتبر' : 'نامعتبر') : '—'],
            ['حرکت', currentPoint?.motion === true ? 'در حرکت' : currentPoint?.motion === false ? 'متوقف' : '—'],
            ['سوئیچ', currentPoint?.ignition === true ? 'روشن' : currentPoint?.ignition === false ? 'خاموش' : '—'],
            ['ولتاژ باتری', showValue(currentPoint?.battery_voltage, ' V')],
            ['ولتاژ خارجی', showValue(currentPoint?.external_voltage, ' V')],
            ['قدرت GSM', showValue(currentPoint?.gsm_signal)],
            ['کیلومترشمار', showValue(currentPoint?.odometer)],
            ['ساعت موتور', showValue(currentPoint?.engine_hours)],
            ['سطح سوخت', showValue(currentPoint?.fuel_level)],
            ['زمان دریافت سرور', formatDate(currentPoint?.server_received_at)],
            ['منبع تطبیق', currentPoint?.match_provider || '—'],
            ['زمان تطبیق', formatDate(currentPoint?.matched_at)],
          ].map(([label, value]) => <div key={label} className="rounded-xl border border-border-base bg-bg-base p-3"><div className="text-xs text-text-muted">{label}</div><div className="mt-1 break-words text-sm font-medium text-text-primary">{value}</div></div>)}
        </div>
        {Object.keys(attributes).length > 0 && <div className="mt-4"><h4 className="mb-2 text-sm font-semibold text-text-primary">ویژگی‌های اضافی ثبت‌شده</h4><pre dir="ltr" className="max-h-64 overflow-auto rounded-xl bg-bg-base p-3 text-xs leading-5 text-text-secondary">{JSON.stringify(attributes, null, 2)}</pre></div>}
      </section>
    </section>
  );
}
