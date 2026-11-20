import { useState, useMemo, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, CheckCheck, CircleAlert, FileText, CarFront, ClipboardList,
  Search, Check, Eye, ArrowUpRight, RefreshCw, Inbox,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { useAuth } from '../context/AuthContext';
import { alertsAPI, panelNotificationsAPI, notificationsAPI } from '../api/services/fleet';
import { formatJalaliDateTime } from '../utils/dateUtils';
import LoadingSpinner from '../components/LoadingSpinner';

const eventTypes = {
  commandResult: { label: 'نتیجه اجرای فرمان', severity: 'info', message: 'نتیجه اجرای فرمان دستگاه دریافت شد' },
  deviceOnline: { label: 'اتصال مجدد دستگاه', severity: 'info', message: 'ارتباط دستگاه برقرار شد' },
  deviceUnknown: { label: 'وضعیت ارتباط نامشخص', severity: 'warning', message: 'وضعیت ارتباط دستگاه نامشخص است' },
  deviceOffline: { label: 'قطع ارتباط دستگاه', severity: 'warning', message: 'ارتباط دستگاه قطع شد' },
  deviceInactive: { label: 'عدم فعالیت دستگاه', severity: 'warning', message: 'دستگاه برای مدت طولانی موقعیتی ارسال نکرده است' },
  queuedCommandSent: { label: 'ارسال فرمان در صف', severity: 'info', message: 'فرمان در صف ارسال به دستگاه قرار گرفت' },
  deviceMoving: { label: 'شروع حرکت', severity: 'info', message: 'حرکت خودرو آغاز شد' },
  deviceStopped: { label: 'توقف خودرو', severity: 'info', message: 'خودرو متوقف شد' },
  deviceOverspeed: { label: 'سرعت غیرمجاز', severity: 'critical', message: 'سرعت خودرو از حد مجاز عبور کرد' },
  overspeed: { label: 'سرعت غیرمجاز', severity: 'critical', message: 'هشدار سرعت غیرمجاز ثبت شد' },
  deviceFuelDrop: { label: 'کاهش ناگهانی سوخت', severity: 'warning', message: 'کاهش ناگهانی سطح سوخت تشخیص داده شد' },
  deviceFuelIncrease: { label: 'افزایش ناگهانی سوخت', severity: 'info', message: 'افزایش ناگهانی سطح سوخت تشخیص داده شد' },
  geofenceEnter: { label: 'ورود به محدوده', severity: 'info', message: 'خودرو وارد محدوده جغرافیایی شد' },
  geofenceExit: { label: 'خروج از محدوده', severity: 'warning', message: 'خودرو از محدوده جغرافیایی خارج شد' },
  geofenceCrossed: { label: 'عبور از محدوده', severity: 'warning', message: 'خودرو از مرز محدوده جغرافیایی عبور کرد' },
  proximityEnter: { label: 'ورود به محدوده نزدیکی', severity: 'info', message: 'دستگاه به دستگاه مرتبط نزدیک شد' },
  proximityExit: { label: 'خروج از محدوده نزدیکی', severity: 'warning', message: 'دستگاه از دستگاه مرتبط دور شد' },
  unaccompaniedMotion: { label: 'حرکت بدون همراه', severity: 'warning', message: 'حرکت دستگاه بدون حضور دستگاه همراه تشخیص داده شد' },
  alarm: { label: 'هشدار دستگاه', severity: 'critical', message: 'هشدار توسط خود دستگاه ارسال شد' },
  ignitionOn: { label: 'روشن شدن سوئیچ', severity: 'info', message: 'سوئیچ خودرو روشن شد' },
  ignitionOff: { label: 'خاموش شدن سوئیچ', severity: 'info', message: 'سوئیچ خودرو خاموش شد' },
  maintenance: { label: 'یادآوری سرویس', severity: 'warning', message: 'موعد سرویس دوره‌ای فرا رسیده است' },
  driverChanged: { label: 'تغییر راننده', severity: 'info', message: 'راننده دستگاه تغییر کرد' },
  media: { label: 'رسانه جدید', severity: 'info', message: 'رسانه‌ای از دستگاه دریافت شد' },
};

const alarmLabels = {
  general: 'هشدار عمومی', sos: 'دکمه اضطراری', vibration: 'لرزش',
  movement: 'حرکت غیرمجاز', overspeed: 'سرعت غیرمجاز', fallDown: 'سقوط',
  lowPower: 'ولتاژ برق پایین', lowBattery: 'باتری ضعیف', fault: 'خطای دستگاه',
  powerOff: 'خاموشی برق', powerOn: 'وصل شدن برق', door: 'باز شدن در',
  geofence: 'هشدار محدوده جغرافیایی', gpsAntennaCut: 'قطع آنتن GPS',
  accident: 'تصادف', tow: 'یدک‌کش شدن', idle: 'درجا کار کردن موتور',
  fuelLeak: 'نشت سوخت', tampering: 'دست‌کاری دستگاه', removing: 'جدا شدن دستگاه',
};

function presentGpsEvent(alert) {
  const config = eventTypes[alert.type] || {
    label: alert.type ? `رویداد Traccar: ${alert.type}` : 'رویداد ناشناخته',
    severity: 'info',
    message: alert.type ? `رویداد ${alert.type} از Traccar دریافت شد` : 'یک رویداد با نوع نامشخص دریافت شد',
  };
  const attributes = alert.attributes || {};
  const rawAlarm = attributes.alarm;
  const alarms = typeof rawAlarm === 'string'
    ? rawAlarm.split(',').map((value) => value.trim()).filter(Boolean)
    : [];
  const details = [];
  if (attributes.geofence) details.push(`محدوده: ${attributes.geofence}`);
  if (attributes.speed != null) details.push(`سرعت: ${attributes.speed}`);
  if (attributes.speedLimit != null) details.push(`حد مجاز سرعت: ${attributes.speedLimit}`);
  if (attributes.fuel != null) details.push(`سوخت: ${attributes.fuel}`);
  if (attributes.result) details.push(`نتیجه: ${attributes.result}`);
  if (attributes.command) details.push(`فرمان: ${attributes.command}`);
  if (attributes.driverName) details.push(`راننده: ${attributes.driverName}`);
  if (attributes.address) details.push(`موقعیت: ${attributes.address}`);
  const message = alert.type === 'alarm' && alarms.length
    ? `هشدار دستگاه: ${alarms.map((value) => alarmLabels[value] || `هشدار دستگاه (${value})`).join('، ')}`
    : config.message;
  return {
    ...alert,
    notification_key: `gps:${alert.device_id}:${alert.id}`,
    source: 'gps',
    category: 'gps',
    title: config.label,
    message,
    detail: details.join(' • '),
    vehicle: alert.vehicle_plate || 'خودرو بدون پلاک',
    created_at: alert.event_time,
    is_read: alert.status !== 'unread',
    status: alert.status,
    severity: config.severity,
  };
}

function presentBusinessItem(item, personal) {
  return {
    ...item,
    notification_key: `business:${item.id}`,
    source: 'business',
    category: personal ? 'contract' : 'management',
    title: item.title || (personal ? 'اعلان قرارداد و امور مالی' : 'اعلان مدیریتی'),
    message: item.message || '',
    created_at: item.created_at,
    is_read: !!item.is_read,
    severity: 'info',
  };
}

const dateValue = (item) => {
  const value = new Date(item.created_at || item.event_time || 0).getTime();
  return Number.isFinite(value) ? value : 0;
};

function Metric({ icon: Icon, label, value, tone = 'default' }) {
  const tones = {
    default: 'bg-bg-hover text-text-secondary',
    warning: 'bg-warning/10 text-warning',
    success: 'bg-success/10 text-success',
    brand: 'bg-brand-500/10 text-brand-500',
  };
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-xl border border-border-base bg-bg-elevated px-4 py-3">
      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${tones[tone]}`}>
        <Icon size={19} />
      </span>
      <div className="min-w-0">
        <div className="text-xl font-bold tabular-nums text-text-primary">{value}</div>
        <div className="truncate text-xs text-text-muted">{label}</div>
      </div>
    </div>
  );
}

function NotificationCard({ item, personal, busy, onRead, onReview, onResolve, onNavigate }) {
  const isGps = item.category === 'gps';
  const tone = item.severity === 'critical'
    ? 'border-r-danger bg-danger/5'
    : item.severity === 'warning'
      ? 'border-r-warning'
      : 'border-r-transparent';
  return (
    <article className={`group rounded-xl border border-border-base border-r-[3px] ${tone} bg-bg-elevated p-4 transition-colors hover:bg-bg-hover/50`}>
      <div className="flex items-start gap-3">
        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${isGps ? 'bg-info/10 text-info' : item.category === 'contract' ? 'bg-brand-500/10 text-brand-500' : 'bg-bg-hover text-text-secondary'}`}>
          {isGps ? <CarFront size={21} /> : item.category === 'contract' ? <FileText size={21} /> : <ClipboardList size={21} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-text-primary">{item.title}</h3>
            <span className={`rounded-md px-2 py-1 text-[10px] font-medium ${isGps ? 'bg-info/10 text-info' : item.category === 'contract' ? 'bg-brand-500/10 text-brand-500' : 'bg-bg-hover text-text-secondary'}`}>
              {isGps ? 'خودرو و GPS' : item.category === 'contract' ? 'قرارداد و مالی' : 'مدیریتی'}
            </span>
            {!item.is_read && <span className="h-2 w-2 rounded-full bg-brand-500" title="خوانده‌نشده" />}
          </div>
          <p className="mt-2 whitespace-pre-line text-sm leading-6 text-text-secondary">{item.message}</p>
          {item.detail && <p className="mt-1 text-xs leading-5 text-text-muted">{item.detail}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-muted">
            {item.vehicle && <span className="font-medium text-text-secondary">{item.vehicle}</span>}
            {item.vehicle && <span className="text-border-base">•</span>}
            <span>{formatJalaliDateTime(item.created_at || item.event_time) || 'زمان نامشخص'}</span>
            <span className={item.is_read ? 'text-success' : 'text-warning'}>{item.is_read ? 'خوانده‌شده' : 'جدید'}</span>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
          {!item.is_read && (
            <button type="button" onClick={() => onRead(item)} disabled={busy} title="علامت‌گذاری به‌عنوان خوانده‌شده" aria-label="خوانده شد" className="rounded-lg p-2 text-text-muted transition-colors hover:bg-brand-500/10 hover:text-brand-500 disabled:opacity-40">
              {busy ? <RefreshCw size={16} className="animate-spin" /> : <Check size={17} />}
            </button>
          )}
          {personal && isGps && item.status === 'unread' && (
            <button type="button" onClick={() => onReview(item)} disabled={busy} title="بررسی شد" aria-label="بررسی شد" className="rounded-lg p-2 text-text-muted hover:bg-warning/10 hover:text-warning disabled:opacity-40"><Eye size={16} /></button>
          )}
          {personal && isGps && ['unread', 'read', 'reviewed'].includes(item.status) && (
            <button type="button" onClick={() => onResolve(item)} disabled={busy} title="رفع شد" aria-label="رفع شد" className="rounded-lg p-2 text-text-muted hover:bg-success/10 hover:text-success disabled:opacity-40"><CheckCheck size={16} /></button>
          )}
          {item.path && (
            <button type="button" onClick={() => onNavigate(item)} title="مشاهده جزئیات" aria-label="مشاهده جزئیات" className="rounded-lg p-2 text-text-muted hover:bg-bg-hover hover:text-text-primary"><ArrowUpRight size={17} /></button>
          )}
        </div>
      </div>
    </article>
  );
}

export default function Alerts() {
  const navigate = useNavigate();
  const { isPersonal, isSiteAdmin, isMainUser } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [readFilter, setReadFilter] = useState('all');
  const [updating, setUpdating] = useState('');

  const loadNotifications = useCallback(async () => {
    if (isPersonal) {
      const [businessResult, gpsResult] = await Promise.allSettled([
        panelNotificationsAPI.list(),
        alertsAPI.list(),
      ]);
      if (businessResult.status === 'rejected' && gpsResult.status === 'rejected') {
        throw new Error('notification feeds unavailable');
      }
      const business = businessResult.status === 'fulfilled'
        ? (businessResult.value?.results || []).map((item) => presentBusinessItem(item, true))
        : null;
      const gps = gpsResult.status === 'fulfilled'
        ? (gpsResult.value?.results || []).map(presentGpsEvent)
        : null;
      setItems((current) => {
        const merged = [...(business ?? current.filter((item) => item.category === 'contract')), ...(gps ?? current.filter((item) => item.category === 'gps'))];
        return merged.sort((a, b) => dateValue(b) - dateValue(a));
      });
      setError(businessResult.status === 'rejected' || gpsResult.status === 'rejected' ? 'بخشی از اعلان‌ها موقتاً در دسترس نیست.' : '');
      return;
    }

    const { businessResult, gpsResult } = await notificationsAPI.list();
    if (businessResult.status === 'rejected' && gpsResult.status === 'rejected') {
      throw new Error('notification feeds unavailable');
    }
    const business = businessResult.status === 'fulfilled'
      ? (businessResult.value?.results || []).map((item) => presentBusinessItem(item, false))
      : null;
    const gps = gpsResult.status === 'fulfilled'
      ? (gpsResult.value?.results || []).map((item) => ({
          ...presentGpsEvent(item),
          is_read: item.status !== 'unread',
          path: '/panel/alerts',
        }))
      : null;
    setItems((current) => {
      const merged = [...(business ?? current.filter((item) => item.category !== 'gps')), ...(gps ?? current.filter((item) => item.category === 'gps'))];
      return merged.sort((a, b) => dateValue(b) - dateValue(a));
    });
    setError(businessResult.status === 'rejected' || gpsResult.status === 'rejected' ? 'بخشی از اعلان‌ها موقتاً در دسترس نیست.' : '');
  }, [isPersonal]);

  useEffect(() => {
    let active = true;
    let timer = null;
    let running = false;
    const refresh = async () => {
      if (running) return;
      running = true;
      if (document.visibilityState === 'visible') {
        try {
          await loadNotifications();
        } catch {
          if (active) setError('دریافت اعلان‌ها ناموفق بود. دوباره تلاش کنید.');
        }
      }
      running = false;
      if (active) {
        setLoading(false);
        timer = window.setTimeout(refresh, 30000);
      }
    };
    const refreshNow = () => {
      window.clearTimeout(timer);
      refresh();
    };
    refresh();
    window.addEventListener('sana:notifications-updated', refreshNow);
    window.addEventListener('sana:personal-alerts-updated', refreshNow);
    window.addEventListener('sana:panel-notification-state-changed', refreshNow);
    window.addEventListener('sana:traccar-alert-state-changed', refreshNow);
    document.addEventListener('visibilitychange', refreshNow);
    return () => {
      active = false;
      window.clearTimeout(timer);
      window.removeEventListener('sana:notifications-updated', refreshNow);
      window.removeEventListener('sana:personal-alerts-updated', refreshNow);
      window.removeEventListener('sana:panel-notification-state-changed', refreshNow);
      window.removeEventListener('sana:traccar-alert-state-changed', refreshNow);
      document.removeEventListener('visibilitychange', refreshNow);
    };
  }, [loadNotifications]);

  const unreadCount = useMemo(() => items.filter((item) => !item.is_read).length, [items]);
  const gpsCount = useMemo(() => items.filter((item) => item.category === 'gps').length, [items]);
  const businessCount = items.length - gpsCount;
  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('fa');
    return items.filter((item) => {
      if (category !== 'all' && item.category !== category) return false;
      if (readFilter === 'unread' && item.is_read) return false;
      if (readFilter === 'read' && !item.is_read) return false;
      if (query && ![item.title, item.message, item.detail, item.vehicle]
        .filter(Boolean).some((value) => String(value).toLocaleLowerCase('fa').includes(query))) return false;
      return true;
    });
  }, [items, category, readFilter, search]);

  const markRead = async (item) => {
    if (item.is_read) return;
    setUpdating(item.notification_key);
    setError('');
    try {
      if (isPersonal && item.category === 'contract') {
        await panelNotificationsAPI.markRead(item.id);
      } else if (isPersonal && item.category === 'gps') {
        await alertsAPI.updateStatus({ deviceId: item.device_id, eventId: item.id, status: 'read' });
      } else {
        await notificationsAPI.markRead({
          isGps: item.category === 'gps',
          eventKey: item.id,
          deviceId: item.device_id,
          eventId: item.id,
        });
      }
      setItems((current) => current.map((entry) => entry.notification_key === item.notification_key
        ? { ...entry, is_read: true, status: 'read' }
        : entry));
      window.dispatchEvent(new Event('sana:notifications-updated'));
    } catch {
      setError('ثبت وضعیت خواندن اعلان ناموفق بود.');
    } finally {
      setUpdating('');
    }
  };

  const updateGpsStatus = async (item, status) => {
    setUpdating(item.notification_key);
    setError('');
    try {
      await alertsAPI.updateStatus({ deviceId: item.device_id, eventId: item.id, status });
      setItems((current) => current.map((entry) => entry.notification_key === item.notification_key
        ? { ...entry, status, is_read: true }
        : entry));
      window.dispatchEvent(new Event('sana:personal-alerts-updated'));
    } catch {
      setError('ثبت وضعیت هشدار انجام نشد. لطفاً دوباره تلاش کنید.');
    } finally {
      setUpdating('');
    }
  };

  const markAllRead = async () => {
    if (!unreadCount) return;
    setUpdating('all');
    setError('');
    try {
      if (isPersonal) {
        const unreadItems = items.filter((item) => !item.is_read);
        const results = await Promise.allSettled(unreadItems.map((item) => (
          item.category === 'contract'
            ? panelNotificationsAPI.markRead(item.id)
            : alertsAPI.updateStatus({ deviceId: item.device_id, eventId: item.id, status: 'read' })
        )));
        const failed = results.some((result) => result.status === 'rejected');
        await loadNotifications();
        if (failed) setError('بعضی اعلان‌ها خوانده شدند، اما ثبت وضعیت همه آن‌ها انجام نشد.');
      } else {
        const [businessResult, gpsResult] = await notificationsAPI.markAllRead();
        setItems((current) => current.map((item) => {
          if (item.category === 'gps' && gpsResult.status === 'fulfilled') return { ...item, is_read: true, status: 'read' };
          if (item.category !== 'gps' && businessResult.status === 'fulfilled') return { ...item, is_read: true, status: 'read' };
          return item;
        }));
        if (businessResult.status === 'rejected' || gpsResult.status === 'rejected') {
          setError('خواندن همه اعلان‌ها به‌طور کامل انجام نشد.');
        }
      }
      window.dispatchEvent(new Event('sana:notifications-updated'));
    } catch {
      setError('خواندن همه اعلان‌ها ناموفق بود.');
    } finally {
      setUpdating('');
    }
  };

  const roleTitle = isSiteAdmin ? 'مرکز اعلان‌های سامانه' : isMainUser ? 'مرکز اعلان‌های سازمان' : 'مرکز اعلان‌ها';
  const categoryTabs = [
    { value: 'all', label: 'همه', count: items.length },
    { value: isPersonal ? 'contract' : 'management', label: isPersonal ? 'قرارداد و مالی' : 'مدیریتی', count: businessCount },
    { value: 'gps', label: 'خودرو و GPS', count: gpsCount },
  ];

  return (
    <div className="space-y-5 pb-8">
      <PageHeader title={roleTitle} subtitle="همه رویدادها و پیام‌های مهم شما، در یک نمای یکپارچه و به‌ترتیب زمان" />

      <section className="overflow-hidden rounded-2xl border border-border-base bg-bg-elevated">
        <div className="flex flex-col justify-between gap-4 border-b border-border-base bg-gradient-to-l from-brand-500/10 via-bg-elevated to-bg-elevated px-5 py-5 sm:flex-row sm:items-center sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-500/10 text-brand-500"><Bell size={24} /></div>
            <div>
              <h2 className="text-base font-bold text-text-primary">صندوق اعلان‌ها</h2>
              <p className="mt-1 text-xs text-text-muted">نمایش یکپارچه، بدون تفکیک صفحه‌ای منابع اعلان</p>
            </div>
          </div>
          {unreadCount > 0 && (
            <button type="button" onClick={markAllRead} disabled={!!updating} className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50">
              <CheckCheck size={15} /> خواندن همه اعلان‌ها
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-3 sm:p-5">
          <Metric icon={Inbox} label="مجموع اعلان‌ها" value={items.length} tone="brand" />
          <Metric icon={CircleAlert} label="خوانده‌نشده" value={unreadCount} tone="warning" />
          <Metric icon={CheckCheck} label="خوانده‌شده" value={items.length - unreadCount} tone="success" />
        </div>
      </section>

      {error && <div className="rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger">{error}</div>}

      <section className="rounded-2xl border border-border-base bg-bg-elevated p-4 sm:p-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1 rounded-xl bg-bg-hover p-1">
              {categoryTabs.map((tab) => (
                <button key={tab.value} type="button" onClick={() => setCategory(tab.value)} className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${category === tab.value ? 'bg-bg-elevated text-text-primary shadow-sm' : 'text-text-muted hover:text-text-primary'}`}>
                  {tab.label}<span className="mr-1.5 text-[10px] opacity-70">{tab.count}</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 rounded-lg border border-border-base p-1">
              {[{ value: 'all', label: 'وضعیت: همه' }, { value: 'unread', label: 'جدید' }, { value: 'read', label: 'خوانده‌شده' }].map((tab) => (
                <button key={tab.value} type="button" onClick={() => setReadFilter(tab.value)} className={`rounded-md px-2.5 py-1.5 text-[11px] transition-colors ${readFilter === tab.value ? 'bg-brand-500/10 text-brand-500' : 'text-text-muted hover:text-text-primary'}`}>{tab.label}</button>
              ))}
            </div>
          </div>
          <div className="relative">
            <Search size={17} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="جستجو در عنوان، متن، پلاک یا جزئیات اعلان..." className="w-full rounded-xl border border-border-base bg-bg-base py-3 pr-10 pl-4 text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-brand-500" />
          </div>
        </div>
      </section>

      <div className="flex items-center justify-between gap-3 px-1">
        <div>
          <h2 className="text-sm font-bold text-text-primary">فهرست اعلان‌ها</h2>
          <p className="mt-1 text-[11px] text-text-muted">{filtered.length} مورد از {items.length} اعلان</p>
        </div>
        <span className="text-[11px] text-text-muted">مرتب‌سازی: جدیدترین</span>
      </div>

      {loading ? (
        <div className="flex justify-center rounded-2xl border border-border-base bg-bg-elevated py-14"><LoadingSpinner /></div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border-base bg-bg-elevated px-5 py-14 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-bg-hover text-text-muted"><Bell size={25} /></div>
          <h3 className="mt-4 text-sm font-semibold text-text-primary">{items.length ? 'اعلانی مطابق فیلترها پیدا نشد' : 'صندوق اعلان‌ها خالی است'}</h3>
          <p className="mx-auto mt-2 max-w-md text-xs leading-6 text-text-muted">{items.length ? 'فیلتر نوع، وضعیت یا عبارت جستجو را تغییر دهید.' : 'به‌محض ثبت رویداد جدید در سامانه، قرارداد یا دستگاه‌های شما، اعلان آن در اینجا نمایش داده می‌شود.'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <NotificationCard
              key={item.notification_key}
              item={item}
              personal={isPersonal}
              busy={updating === item.notification_key || updating === 'all'}
              onRead={markRead}
              onReview={(entry) => updateGpsStatus(entry, 'reviewed')}
              onResolve={(entry) => updateGpsStatus(entry, 'resolved')}
              onNavigate={(entry) => {
                if (!entry.is_read) markRead(entry);
                if (entry.path && entry.path !== '/panel/alerts') navigate(entry.path);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
