import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CalendarClock, ChevronLeft, ChevronRight, CircleAlert, Download, Play, Search, SkipBack, SkipForward } from 'lucide-react';
import apiClient from '../api/client';
import JalaliDatePicker from './JalaliDatePicker';
import LiveDeviceMap from '../../../sana-map/src/LiveDeviceMap';
import { MAP_PROVIDER, MAP_PROVIDERS } from '../../../sana-map/src/config';

const dateTimeLocal = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};
const datePart = (value) => value ? value.slice(0, 10) : '';
const timePart = (value) => value ? value.slice(11, 16) : '';
const composeDateTime = (date, time) => date && time ? `${date}T${time}` : '';
const parseLocalDateTime = (value) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value || '');
  if (!match) return null;
  const [, year, month, day, hour, minute] = match.map((part, index) => index ? Number(part) : part);
  const date = new Date(year, month - 1, day, hour, minute, 0, 0);
  if (
    date.getFullYear() !== year || date.getMonth() !== month - 1 ||
    date.getDate() !== day || date.getHours() !== hour || date.getMinutes() !== minute
  ) return null;
  return date;
};
const toApiDate = (value) => {
  const date = parseLocalDateTime(value);
  return date ? date.toISOString() : ''; 
};
const formatDate = (value) => value ? new Date(value).toLocaleString('fa-IR') : '—';
const formatNumeric = (value, maximumFractionDigits = 2) => {
  if (value === null || value === undefined || value === '') return '—';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  return new Intl.NumberFormat('fa-IR', {
    useGrouping: false,
    maximumFractionDigits,
  }).format(numeric);
};
const showValue = (value, suffix = '', maximumFractionDigits = 2) =>
  value === null || value === undefined || value === '' ? '—' : `${formatNumeric(value, maximumFractionDigits)}${suffix}`;
const attributeLabels = {
  ignition: 'سوئیچ', motion: 'حرکت', satellites: 'ماهواره‌ها', sat: 'ماهواره‌ها',
  rssi: 'قدرت سیگنال', gsm: 'قدرت GSM', battery: 'باتری', batteryVoltage: 'ولتاژ باتری',
  power: 'ولتاژ خارجی', voltage: 'ولتاژ', odometer: 'کیلومترشمار', totalDistance: 'مسافت کل',
  hours: 'ساعت کارکرد', engineHours: 'ساعت موتور', fuel: 'سوخت', fuelLevel: 'سطح سوخت',
  alarm: 'هشدار', status: 'وضعیت', event: 'رویداد', hdop: 'دقت افقی',
};
const attributePrecision = (key = '') => {
  const normalized = String(key).replace(/([A-Z])/g, '_$1').toLowerCase();
  if (/(^|_)(latitude|longitude|lat|lon|lng)(_|$)/.test(normalized)) return 6;
  if (/(^|_)(speed|velocity)(_|$)/.test(normalized)) return 1;
  if (/(^|_)(heading|course|satellites|sat|rssi|gsm|signal|event|status|count|index)(_|$)/.test(normalized)) return 0;
  if (/(voltage|battery|power|fuel|hdop|accuracy|altitude|odometer|distance|hours|temperature|rpm|frequency)/.test(normalized)) return 2;
  return 2;
};
const formatAttributeValue = (value, key = '') => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'بله' : 'خیر';
  if (typeof value === 'number') return formatNumeric(value, attributePrecision(key));
  if (Array.isArray(value)) return JSON.stringify(value.map((item) => (
    typeof item === 'number' ? formatNumeric(item, attributePrecision(key)) :
      item && typeof item === 'object' ? JSON.parse(formatAttributeValue(item, key)) : item
  )));
  if (typeof value === 'object') {
    return JSON.stringify(Object.fromEntries(Object.entries(value).map(([childKey, childValue]) => [
      childKey,
      typeof childValue === 'number' ? formatNumeric(childValue, attributePrecision(childKey)) :
        childValue && typeof childValue === 'object' ? JSON.parse(formatAttributeValue(childValue, childKey)) : childValue,
    ])));
  }
  return String(value);
};
const formatAttributeLabel = (key) => attributeLabels[key] || key.replace(/([A-Z])/g, ' $1').replace(/[_-]+/g, ' ').trim();
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
  // Keep time drafts independently so choosing a time before its date does not discard it.
  const [fromTime, setFromTime] = useState('00:00');
  const [toTime, setToTime] = useState('23:59');
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
  const dateSelectionTouchedRef = useRef(false);

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
    dateSelectionTouchedRef.current = false;
    setMetadata(null);
    setFrom('');
    setTo('');
    setFromTime('00:00');
    setToTime('23:59');
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
        if (!isSiteAdmin && data.range_start && data.range_end && !dateSelectionTouchedRef.current) {
          const rangeStart = dateTimeLocal(data.range_start);
          const rangeEnd = dateTimeLocal(data.range_end);
          setFrom(rangeStart);
          setTo(rangeEnd);
          setFromTime(timePart(rangeStart) || '00:00');
          setToTime(timePart(rangeEnd) || '23:59');
        }
      })
      .catch((err) => { if (active) setError(err.response?.data?.detail || 'دریافت محدوده مجاز دستگاه ناموفق بود.'); });
    return () => { active = false; };
  }, [deviceId, isSiteAdmin]);

  const loadHistory = useCallback(async () => {
    if (!deviceId) {
      setError('ابتدا یک دستگاه را از فهرست انتخاب کنید.');
      return;
    }
    const startDate = parseLocalDateTime(from);
    const endDate = parseLocalDateTime(to);
    if (!startDate || !endDate) {
      setError('تاریخ و ساعت شروع و پایان را کامل انتخاب کنید.');
      return;
    }
    if (startDate.getTime() > endDate.getTime()) {
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
      distanceKm += distanceBetween(points[index - 1], points[index]);
    }
    const speeds = points.map((point) => Number(point.speed)).filter(Number.isFinite);
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
    <section className="min-w-0 space-y-3">
      <div className="rounded-xl border border-border-base bg-bg-elevated p-3">
        <div className="grid min-w-0 grid-cols-1 gap-2 lg:grid-cols-[minmax(220px,1.15fr)_minmax(180px,1fr)_minmax(180px,1fr)_auto] lg:items-end">
          <div className="relative min-w-0">
            <label htmlFor="device-report-search" className="mb-1 block text-[11px] font-medium text-text-muted">دستگاه</label>
            <div className="relative">
              <Search size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
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
                placeholder={loadingDevices ? 'در حال دریافت دستگاه‌ها…' : 'جست‌وجوی شناسه، پلاک یا راننده'}
                disabled={loadingDevices}
                className="w-full rounded-lg border border-border-base bg-bg-base py-2.5 pr-9 pl-3 text-sm text-text-primary outline-none focus:border-brand-400 disabled:opacity-60"
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
                  )) : <p className="px-3 py-3 text-sm text-text-muted">دستگاهی با این عبارت پیدا نشد.</p>}
                </div>
              )}
            </div>
          </div>

          <div className="min-w-0">
            <label className="mb-1 block text-[11px] font-medium text-text-muted">شروع بازه</label>
            <JalaliDatePicker
              value={from ? `${datePart(from)}T12:00:00` : ''}
              onChange={(value) => {
                dateSelectionTouchedRef.current = true;
                setError('');
                setFrom(composeDateTime(value, fromTime));
              }}
              showTime
              timeValue={fromTime}
              onTimeChange={(value) => {
                dateSelectionTouchedRef.current = true;
                setError('');
                setFromTime(value);
                setFrom((current) => datePart(current) ? composeDateTime(datePart(current), value) : current);
              }}
              minTime={!isSiteAdmin && metadata?.range_start && datePart(from) === datePart(dateTimeLocal(metadata.range_start)) ? timePart(dateTimeLocal(metadata.range_start)) : null}
              maxTime={!isSiteAdmin && metadata?.range_end && datePart(from) === datePart(dateTimeLocal(metadata.range_end)) ? timePart(dateTimeLocal(metadata.range_end)) : null}
              minDate={!isSiteAdmin && metadata?.range_start ? datePart(dateTimeLocal(metadata.range_start)) : null}
              maxDate={!isSiteAdmin && metadata?.range_end ? datePart(dateTimeLocal(metadata.range_end)) : null}
              placeholder="انتخاب تاریخ و ساعت شروع"
              className="[&>div>input]:!py-2"
            />
          </div>

          <div className="min-w-0">
            <label className="mb-1 block text-[11px] font-medium text-text-muted">پایان بازه</label>
            <JalaliDatePicker
              value={to ? `${datePart(to)}T12:00:00` : ''}
              onChange={(value) => {
                dateSelectionTouchedRef.current = true;
                setError('');
                setTo(composeDateTime(value, toTime));
              }}
              showTime
              timeValue={toTime}
              onTimeChange={(value) => {
                dateSelectionTouchedRef.current = true;
                setError('');
                setToTime(value);
                setTo((current) => datePart(current) ? composeDateTime(datePart(current), value) : current);
              }}
              minTime={!isSiteAdmin && metadata?.range_start && datePart(to) === datePart(dateTimeLocal(metadata.range_start)) ? timePart(dateTimeLocal(metadata.range_start)) : null}
              maxTime={!isSiteAdmin && metadata?.range_end && datePart(to) === datePart(dateTimeLocal(metadata.range_end)) ? timePart(dateTimeLocal(metadata.range_end)) : null}
              minDate={!isSiteAdmin && metadata?.range_start ? datePart(dateTimeLocal(metadata.range_start)) : null}
              maxDate={!isSiteAdmin && metadata?.range_end ? datePart(dateTimeLocal(metadata.range_end)) : null}
              placeholder="انتخاب تاریخ و ساعت پایان"
              className="[&>div>input]:!py-2"
            />
          </div>

          <div className="flex min-w-0 gap-2">
            <button type="button" onClick={loadHistory} disabled={loadingHistory || !deviceId} className="inline-flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60 lg:flex-none">
              <CalendarClock size={16} className={loadingHistory ? 'animate-pulse' : ''} />
              {loadingHistory ? 'در حال دریافت…' : 'نمایش گزارش'}
            </button>
            <label className="flex items-center gap-1.5 rounded-lg border border-border-base bg-bg-base px-2 text-xs text-text-secondary">
              <span className="sr-only">نقشه</span>
              <select aria-label="انتخاب ارائه‌دهنده نقشه" value={provider} onChange={(event) => setProvider(event.target.value)} className="max-w-[112px] bg-transparent py-2 text-xs text-text-primary outline-none">
                <option value={MAP_PROVIDERS.LEAFLET_OSM}>OpenStreetMap</option>
                <option value={MAP_PROVIDERS.NESHAN_LEAFLET}>نشان</option>
              </select>
            </label>
          </div>
        </div>
        {!isSiteAdmin && metadata?.range_start && (
          <p className="mt-2 text-[10px] text-text-muted">محدوده مجاز دستگاه: {formatDate(metadata.range_start)} تا {formatDate(metadata.range_end)}</p>
        )}
      </div>

      {error && <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/20 bg-danger/5 px-3 py-2 text-xs text-danger"><CircleAlert size={15} className="shrink-0" />{error}</div>}
      {notice && <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-text-primary"><CircleAlert size={15} className="shrink-0" />{notice}</div>}

      <div className="relative isolate h-[min(76vh,820px)] min-h-[520px] overflow-hidden rounded-2xl border border-border-base bg-bg-base shadow-sm">
        <LiveDeviceMap positions={mapPosition} provider={provider} followPosition animationDuration={Math.max(150, 900 / speed)} routeSegments={routeSegments} />

        {!mapPosition.length && (
          <div className="pointer-events-none absolute inset-0 z-[900] flex items-center justify-center bg-bg-elevated/75 px-4 text-center text-sm text-text-muted">
            {loadingHistory ? 'در حال آماده‌سازی مسیر دستگاه…' : 'برای مشاهده مسیر، دستگاه و بازه زمانی را انتخاب و گزارش را اجرا کنید.'}
          </div>
        )}

        <div className="pointer-events-none absolute inset-x-0 top-0 z-[1001] flex items-start justify-between gap-2 p-2 sm:p-3">
          <div className="pointer-events-auto min-w-0 max-w-[70%] rounded-xl border border-white/30 bg-bg-elevated/95 px-3 py-2 shadow-lg backdrop-blur-md">
            <div className="truncate text-xs font-bold text-text-primary">{selectedDevice?.vehicle_plate || selectedDevice?.imei || metadata?.device?.imei || 'گزارش مسیر دستگاه'}</div>
            <div className="mt-0.5 truncate text-[10px] text-text-muted">{selectedDevice ? deviceLabel(selectedDevice) : 'دستگاهی انتخاب نشده'}{points.length ? ` · ${points.length.toLocaleString('fa-IR')} نقطه` : ''}</div>
          </div>
          <div className="pointer-events-auto flex shrink-0 gap-1.5">
            {points.length > 0 && (
              <button type="button" onClick={exportCsv} title="دریافت فایل CSV" aria-label="دریافت فایل CSV" className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/30 bg-bg-elevated/95 text-text-secondary shadow-lg backdrop-blur-md hover:text-brand-500">
                <Download size={16} />
              </button>
            )}
          </div>
        </div>

        {reportStats && (
          <div className="pointer-events-none absolute right-2 top-[4.6rem] z-[1001] flex max-w-[calc(100%-1rem)] flex-wrap gap-1.5 sm:right-3 sm:top-[4.8rem]">
            {[
              ['مسافت', `${formatNumeric(reportStats.distanceKm, 2)} km`],
              ['بیشترین سرعت', `${formatNumeric(reportStats.maxSpeed, 1)} km/h`],
              ['میانگین', `${formatNumeric(reportStats.averageSpeed, 1)} km/h`],
              ['مدت', formatDuration(reportStats.duration)],
              ['حرکت / توقف', `${reportStats.movingPoints.toLocaleString('fa-IR')} / ${reportStats.stoppedPoints.toLocaleString('fa-IR')}`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-white/30 bg-bg-elevated/95 px-2.5 py-1.5 shadow-md backdrop-blur-md">
                <div className="text-[9px] text-text-muted">{label}</div>
                <div className="whitespace-nowrap text-[11px] font-bold tabular-nums text-text-primary">{value}</div>
              </div>
            ))}
          </div>
        )}

        {currentPoint && (
          <div className="pointer-events-none absolute bottom-[6.4rem] left-2 z-[1001] max-w-[calc(100%-1rem)] rounded-xl border border-white/30 bg-bg-elevated/95 px-2.5 py-1.5 shadow-lg backdrop-blur-md sm:bottom-3 sm:left-3 sm:max-w-[min(42%,420px)]">
            <div className="mb-1 text-[10px] font-semibold text-text-muted">اطلاعات نقطه انتخاب‌شده</div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-primary">
              <span>سرعت: <b>{showValue(currentPoint.speed, ' km/h', 1)}</b></span>
              <span>زمان: <b>{formatDate(currentPoint.device_time)}</b></span>
              <span>سوئیچ: <b>{currentPoint.ignition === true ? 'روشن' : currentPoint.ignition === false ? 'خاموش' : '—'}</b></span>
              <span>GPS: <b>{currentPoint.gps_valid ? 'معتبر' : 'نامعتبر'}</b></span>
              <span>ماهواره: <b>{showValue(currentPoint.satellites, '', 0)}</b></span>
              <span>باتری: <b>{showValue(currentPoint.battery_voltage, ' V')}</b></span>
            </div>
          </div>
        )}

        <div className="absolute inset-x-2 bottom-2 z-[1002] rounded-xl border border-white/30 bg-bg-elevated/95 p-2 shadow-xl backdrop-blur-md sm:inset-x-auto sm:bottom-3 sm:right-3 sm:w-[min(56%,520px)] sm:p-2.5">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-1.5 text-[9px] text-text-muted">
              <span className="shrink-0 font-semibold text-text-primary">{points.length ? `${(pointIndex + 1).toLocaleString('fa-IR')} از ${points.length.toLocaleString('fa-IR')}` : 'بدون نقطه'}</span>
              <span className="truncate">{currentPoint ? formatDate(currentPoint.device_time) : loadingHistory ? 'در حال دریافت…' : 'آماده بازپخش'}</span>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <label className="flex items-center gap-1 text-[9px] text-text-muted">سرعت
                <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))} className="rounded-md border border-border-base bg-bg-base px-1 py-1 text-[9px] text-text-primary">
                  <option value={0.5}>۰٫۵×</option><option value={1}>۱×</option><option value={2}>۲×</option><option value={4}>۴×</option>
                </select>
              </label>
              <button type="button" onClick={() => { setPointIndex(0); setPlaying(false); }} disabled={!points.length} title="ابتدای مسیر" aria-label="ابتدای مسیر" className="flex h-7 w-7 items-center justify-center rounded-md border border-border-base text-text-secondary disabled:opacity-40"><SkipBack size={13} /></button>
              <button type="button" onClick={() => moveBy(-1)} disabled={!points.length || pointIndex === 0} title="نقطه قبلی" aria-label="نقطه قبلی" className="flex h-7 w-7 items-center justify-center rounded-md border border-border-base text-text-secondary disabled:opacity-40"><ChevronLeft size={13} /></button>
              <button type="button" onClick={() => setPlaying((value) => !value)} disabled={points.length < 2} aria-label={playing ? 'توقف بازپخش' : 'شروع بازپخش'} title={playing ? 'توقف بازپخش' : 'شروع بازپخش'} className="flex h-7 min-w-9 items-center justify-center gap-1 rounded-md bg-brand-500 px-1.5 text-[10px] font-semibold text-white disabled:opacity-40">
                {playing ? <span>توقف</span> : <><Play size={12} /><span>پخش</span></>}
              </button>
              <button type="button" onClick={() => moveBy(1)} disabled={!points.length || pointIndex >= points.length - 1} title="نقطه بعدی" aria-label="نقطه بعدی" className="flex h-7 w-7 items-center justify-center rounded-md border border-border-base text-text-secondary disabled:opacity-40"><ChevronRight size={13} /></button>
              <button type="button" onClick={() => { setPointIndex(Math.max(0, points.length - 1)); setPlaying(false); }} disabled={!points.length} title="انتهای مسیر" aria-label="انتهای مسیر" className="flex h-7 w-7 items-center justify-center rounded-md border border-border-base text-text-secondary disabled:opacity-40"><SkipForward size={13} /></button>
            </div>
          </div>
          <input aria-label="موقعیت در مسیر" type="range" min="0" max={Math.max(0, points.length - 1)} value={pointIndex} onChange={(event) => { setPlaying(false); setPointIndex(Number(event.target.value)); }} disabled={!points.length} className="block w-full accent-brand-500" style={{ backgroundSize: `${progress}% 100%` }} />
          <div className="mt-1 flex items-center justify-between gap-2 text-[8px] text-text-muted">
            <div className="flex flex-wrap gap-x-2 gap-y-0.5" aria-label="راهنمای رنگ مسیر بر اساس سرعت">
              {[['#2563EB','۰–۲۰'],['#16A34A','۲۰–۴۰'],['#EAB308','۴۰–۶۰'],['#F97316','۶۰–۸۰'],['#DC2626','۸۰+']].map(([color,label]) => <span key={label} className="inline-flex items-center gap-1"><span className="h-1 w-2.5 rounded-full" style={{ backgroundColor: color }} />{label}</span>)}
              <span>km/h</span>
            </div>
            <span className="hidden truncate sm:inline">{currentPoint?.matched_latitude != null && currentPoint?.matched_longitude != null ? 'مسیر منطبق با جاده' : currentPoint ? 'مختصات خام GPS' : 'رنگ مسیر بر اساس سرعت'}</span>
          </div>
        </div>
      </div>

      {currentPoint && (
        <details className="group rounded-xl border border-border-base bg-bg-elevated">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 text-xs">
            <span className="font-semibold text-text-primary">جزئیات نقطه و تمام Attributes دریافتی</span>
            <span className="text-[10px] text-text-muted">{(21 + Object.keys(attributes).length).toLocaleString('fa-IR')} مقدار · مشاهده / بستن</span>
          </summary>
          <div className="border-t border-border-base px-3 py-3">
            <div className="grid grid-cols-2 gap-x-5 gap-y-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
              {[
                ['عرض جغرافیایی خام', showValue(currentPoint.latitude, '', 6)],
                ['طول جغرافیایی خام', showValue(currentPoint.longitude, '', 6)],
                ['عرض تطبیق‌یافته', showValue(currentPoint.matched_latitude, '', 6)],
                ['طول تطبیق‌یافته', showValue(currentPoint.matched_longitude, '', 6)],
                ['دقت GPS', showValue(currentPoint.accuracy, ' m', 1)],
                ['جهت حرکت', showValue(currentPoint.heading, '°', 0)],
                ['ارتفاع', showValue(currentPoint.altitude, ' m', 1)],
                ['ماهواره‌ها', showValue(currentPoint.satellites, '', 0)],
                ['وضعیت GPS', currentPoint.gps_valid ? 'معتبر' : 'نامعتبر'],
                ['حرکت', currentPoint.motion === true ? 'در حرکت' : currentPoint.motion === false ? 'متوقف' : '—'],
                ['سوئیچ', currentPoint.ignition === true ? 'روشن' : currentPoint.ignition === false ? 'خاموش' : '—'],
                ['ولتاژ باتری', showValue(currentPoint.battery_voltage, ' V')],
                ['ولتاژ خارجی', showValue(currentPoint.external_voltage, ' V')],
                ['قدرت GSM', showValue(currentPoint.gsm_signal, '', 0)],
                ['کیلومترشمار', showValue(currentPoint.odometer)],
                ['ساعت موتور', showValue(currentPoint.engine_hours)],
                ['سطح سوخت', showValue(currentPoint.fuel_level)],
                ['زمان دریافت سرور', formatDate(currentPoint.server_received_at)],
                ['منبع تطبیق', currentPoint.match_provider || '—'],
                ['زمان تطبیق', formatDate(currentPoint.matched_at)],
                ['زمان دستگاه', formatDate(currentPoint.device_time)],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0 border-b border-border-base/70 pb-1.5">
                  <div className="text-[10px] text-text-muted">{label}</div>
                  <div className="mt-0.5 break-words text-xs font-medium text-text-primary">{value}</div>
                </div>
              ))}
              {Object.entries(attributes).map(([key, value]) => (
                <div key={`attribute-${key}`} className="min-w-0 border-b border-border-base/70 pb-1.5">
                  <div className="text-[10px] text-text-muted">{formatAttributeLabel(key)}</div>
                  <div className="mt-0.5 break-words text-xs font-medium text-text-primary">{formatAttributeValue(value, key)}</div>
                </div>
              ))}
            </div>
          </div>
        </details>
      )}
    </section>
  );
}
