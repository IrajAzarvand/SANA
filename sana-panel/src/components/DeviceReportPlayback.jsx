import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, CalendarClock, ChevronLeft, ChevronRight, CircleAlert, LoaderCircle, Pause, Play, Search, SkipBack, SkipForward } from 'lucide-react';
import apiClient from '../api/client';
import LiveDeviceMap from '../../../sana-map/src/LiveDeviceMap';
import { MAP_PROVIDER, MAP_PROVIDERS } from '../../../sana-map/src/config';
import { driverVehicleAssignmentsAPI, vehiclesAPI } from '../api/services/fleet';

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
  const [drivers, setDrivers] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [loadingDevices, setLoadingDevices] = useState(true);
  const [search, setSearch] = useState('');
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
      getAllPages('/drivers/?page_size=1000'),
      getAllPages('/driver-vehicle-assignments/?page_size=1000'),
      getAllPages('/vehicles/?page_size=1000'),
    ]).then(([deviceRows, driverRows, assignmentRows, vehicleRows]) => {
      if (!active) return;
      setDevices(deviceRows);
      setDrivers(driverRows);
      setAssignments(assignmentRows);
      setVehicles(vehicleRows);
    }).catch((err) => {
      if (active) setError(err.response?.data?.detail || 'دریافت فهرست دستگاه‌های مجاز ناموفق بود.');
    }).finally(() => { if (active) setLoadingDevices(false); });
    return () => { active = false; };
  }, []);

  const driverById = useMemo(() => new Map(drivers.map((item) => [String(item.id), item])), [drivers]);
  const vehicleById = useMemo(() => new Map(vehicles.map((item) => [String(item.id), item])), [vehicles]);
  const searchableDevices = useMemo(() => devices.map((device) => {
    const plate = device.vehicle_plate || '';
    const matchingAssignments = assignments.filter((assignment) => {
      const vehicleId = assignment.vehicle_id ?? assignment.vehicle;
      const assignedVehicle = vehicleById.get(String(vehicleId));
      return assignedVehicle?.plate === plate && plate;
    });
    const driverNames = matchingAssignments.map((assignment) => {
      const driverId = assignment.driver_id ?? assignment.driver;
      const driver = driverById.get(String(driverId));
      return assignment.driver_name || driver?.full_name || driver?.name || driver?.driver_name || '';
    }).filter(Boolean);
    return { ...device, driverNames, searchText: [device.imei, device.sim_number, plate, device.customer_name, ...driverNames].join(' ').toLocaleLowerCase() };
  }), [devices, assignments, vehicleById, driverById]);

  const filteredDevices = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    if (!query) return searchableDevices;
    return searchableDevices.filter((device) => device.searchText.includes(query));
  }, [search, searchableDevices]);

  const selectedDevice = devices.find((item) => String(item.id) === String(deviceId));

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
            <label htmlFor="device-report-search" className="mb-2 block text-sm font-medium text-text-primary">جست‌وجوی دستگاه، سیم‌کارت یا راننده</label>
            <div className="relative">
              <Search size={17} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input ref={searchInputRef} id="device-report-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="IMEI، شماره سیم‌کارت، پلاک یا نام راننده" className="w-full rounded-xl border border-border-base bg-bg-base py-2.5 pr-10 pl-3 text-sm text-text-primary outline-none focus:border-brand-400" />
            </div>
            <label htmlFor="device-report-device" className="mb-2 mt-3 block text-sm font-medium text-text-primary">دستگاه</label>
            <select id="device-report-device" value={deviceId} onChange={(event) => setDeviceId(event.target.value)} disabled={loadingDevices} className="w-full rounded-xl border border-border-base bg-bg-base px-3 py-2.5 text-sm text-text-primary outline-none focus:border-brand-400 disabled:opacity-60">
              <option value="">{loadingDevices ? 'در حال دریافت دستگاه‌ها…' : 'انتخاب دستگاه مجاز'}</option>
              {filteredDevices.map((device) => (
                <option key={device.id} value={device.id}>{device.imei}{device.sim_number ? ` · SIM ${device.sim_number}` : ''}{device.vehicle_plate ? ` · ${device.vehicle_plate}` : ''}</option>
              ))}
            </select>
            {!loadingDevices && filteredDevices.length === 0 && <p className="mt-2 text-xs text-text-muted">دستگاهی با این عبارت پیدا نشد.</p>}
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

      <div className="overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-base px-4 py-3">
          <div className="text-sm font-semibold text-text-primary">{metadata?.device?.imei || selectedDevice?.imei || 'دستگاه انتخاب نشده'}</div>
          <div className="text-xs text-text-muted">{points.length.toLocaleString('fa-IR')} نقطه {loadingHistory ? '· در حال بارگذاری' : ''}</div>
        </div>
        <div className="h-[min(62vh,680px)] min-h-[360px]">
          {mapPosition.length ? <LiveDeviceMap positions={mapPosition} provider={provider} /> : <div className="flex h-full items-center justify-center text-sm text-text-muted">پس از انتخاب دستگاه و بازه زمانی، مسیر در این نقشه نمایش داده می‌شود.</div>}
        </div>
        <div className="space-y-3 border-t border-border-base p-4">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => { setPointIndex(0); setPlaying(false); }} disabled={!points.length} title="ابتدای مسیر" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><SkipBack size={17} /></button>
            <button type="button" onClick={() => setPlaying((value) => !value)} disabled={points.length < 2} className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{playing ? <Pause size={16} /> : <Play size={16} />}{playing ? 'توقف' : 'پخش'}</button>
            <button type="button" onClick={() => moveBy(-1)} disabled={!points.length || pointIndex === 0} title="نقطه قبلی" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><ChevronRight size={17} /></button>
            <button type="button" onClick={() => moveBy(1)} disabled={!points.length || pointIndex >= points.length - 1} title="نقطه بعدی" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><ChevronLeft size={17} /></button>
            <button type="button" onClick={() => { setPointIndex(Math.max(0, points.length - 1)); setPlaying(false); }} disabled={!points.length} title="انتهای مسیر" className="rounded-lg border border-border-base p-2 text-text-secondary disabled:opacity-40"><SkipForward size={17} /></button>
            <label className="mr-auto flex items-center gap-2 text-xs text-text-muted">سرعت
              <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))} className="rounded-lg border border-border-base bg-bg-base px-2 py-1.5 text-text-primary"><option value={0.5}>۰٫۵×</option><option value={1}>۱×</option><option value={2}>۲×</option><option value={4}>۴×</option></select>
            </label>
            <span className="text-xs text-text-muted">{points.length ? `${(pointIndex + 1).toLocaleString('fa-IR')} از ${points.length.toLocaleString('fa-IR')}` : 'بدون نقطه'}</span>
          </div>
          <input aria-label="موقعیت در مسیر" type="range" min="0" max={Math.max(0, points.length - 1)} value={pointIndex} onChange={(event) => { setPlaying(false); setPointIndex(Number(event.target.value)); }} disabled={!points.length} className="w-full accent-brand-500" style={{ backgroundSize: `${progress}% 100%` }} />
          <div className="flex flex-wrap justify-between gap-2 text-xs text-text-muted"><span>زمان نقطه: {formatDate(currentPoint?.device_time)}</span><span>{currentPoint?.position_is_matched ? 'مختصات تطبیق‌یافته با جاده' : currentPoint ? 'مختصات خام GPS' : '—'}</span></div>
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
