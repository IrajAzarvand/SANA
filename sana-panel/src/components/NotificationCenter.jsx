import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, Check, ExternalLink, LoaderCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { notificationsAPI } from '../api/services/fleet';

const alertKey = (alert) => `${alert.device_id}:${alert.id}`;

const gpsEventLabels = {
  commandResult: 'نتیجه اجرای فرمان',
  deviceOnline: 'اتصال مجدد دستگاه',
  deviceUnknown: 'وضعیت ارتباط نامشخص',
  deviceOffline: 'قطع ارتباط دستگاه',
  deviceInactive: 'عدم فعالیت دستگاه',
  queuedCommandSent: 'ارسال فرمان در صف',
  deviceMoving: 'شروع حرکت',
  deviceStopped: 'توقف خودرو',
  deviceOverspeed: 'سرعت غیرمجاز',
  overspeed: 'سرعت غیرمجاز',
  deviceFuelDrop: 'کاهش ناگهانی سوخت',
  deviceFuelIncrease: 'افزایش ناگهانی سوخت',
  geofenceEnter: 'ورود به محدوده جغرافیایی',
  geofenceExit: 'خروج از محدوده جغرافیایی',
  geofenceCrossed: 'عبور از محدوده جغرافیایی',
  proximityEnter: 'ورود به محدوده نزدیکی',
  proximityExit: 'خروج از محدوده نزدیکی',
  unaccompaniedMotion: 'حرکت بدون همراه',
  alarm: 'هشدار دستگاه',
  ignitionOn: 'روشن شدن سوئیچ',
  ignitionOff: 'خاموش شدن سوئیچ',
  maintenance: 'یادآوری سرویس',
  driverChanged: 'تغییر راننده',
  media: 'رسانه جدید',
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

const localizeGpsAlert = (item) => {
  const attributes = item.attributes || {};
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

  const title = gpsEventLabels[item.type] || (item.type ? 'رویداد دستگاه' : 'رویداد ناشناخته');
  const message = item.type === 'alarm' && alarms.length
    ? `هشدار دستگاه: ${alarms.map((value) => alarmLabels[value] || 'هشدار دستگاه').join('، ')}`
    : ({
      deviceMoving: 'حرکت خودرو آغاز شد',
      deviceStopped: 'خودرو متوقف شد',
      deviceOverspeed: 'سرعت خودرو از حد مجاز عبور کرد',
      overspeed: 'هشدار سرعت غیرمجاز ثبت شد',
      deviceOffline: 'ارتباط دستگاه قطع شد',
      deviceOnline: 'ارتباط دستگاه برقرار شد',
      ignitionOn: 'سوئیچ خودرو روشن شد',
      ignitionOff: 'سوئیچ خودرو خاموش شد',
      geofenceEnter: 'خودرو وارد محدوده جغرافیایی شد',
      geofenceExit: 'خودرو از محدوده جغرافیایی خارج شد',
    }[item.type] || 'یک رویداد از دستگاه دریافت شد');

  return {
    ...item,
    title,
    message: [message, item.vehicle_plate || ''].filter(Boolean).join(' · '),
    detail: details.join(' · '),
  };
};

export default function NotificationCenter() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async ({ showError = false } = {}) => {
    try {
      const { businessResult, gpsResult } = await notificationsAPI.list();

    if (businessResult.status === 'rejected' && gpsResult.status === 'rejected') {
      if (showError) setError('دریافت اعلان‌ها ناموفق بود. دوباره تلاش کنید.');
      return;
    }

    const businessItems = businessResult.status === 'fulfilled'
      ? (Array.isArray(businessResult.value?.results) ? businessResult.value.results : []).map((item) => ({
        ...item,
        notification_key: item.id,
        is_gps_alert: false,
        message: item.message || item.detail || '',
        is_read: Boolean(item.is_read),
      }))
      : null;
    const gpsItems = gpsResult.status === 'fulfilled'
      ? (Array.isArray(gpsResult.value?.results) ? gpsResult.value.results : []).map((item) => ({
        ...item,
        notification_key: alertKey(item),
        ...localizeGpsAlert(item),
        message: [localizeGpsAlert(item).message, item.device_imei ? `شناسه دستگاه: ${item.device_imei}` : ''].filter(Boolean).join(' · '),
        created_at: item.event_time,
        is_read: item.status !== 'unread',
        path: '/panel/alerts',
        is_gps_alert: true,
      }))
      : null;

    setItems((current) => {
      const currentBusiness = businessItems ?? current.filter((item) => !item.is_gps_alert);
      const currentGps = gpsItems ?? current.filter((item) => item.is_gps_alert);
      return [...currentBusiness, ...currentGps].sort(
        (a, b) => new Date(b.created_at || b.event_time) - new Date(a.created_at || a.event_time),
      );
    });
      if (showError) {
        setError(
          businessResult.status === 'rejected' || gpsResult.status === 'rejected'
            ? 'بخشی از اعلان‌ها موقتاً در دسترس نیست؛ دوباره تلاش کنید.'
            : '',
        );
      } else if (businessResult.status === 'fulfilled' && gpsResult.status === 'fulfilled') {
        setError('');
      }
    } catch {
      if (showError) setError('دریافت اعلان‌ها ناموفق بود. دوباره تلاش کنید.');
    }
  }, []);

  useEffect(() => {
    let alive = true;
    let timer;
    let running = false;

    const refresh = async () => {
      if (running) return;
      running = true;
      if (document.visibilityState === 'visible') {
        await load();
      }
      running = false;
      if (alive) {
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
    document.addEventListener('visibilitychange', refreshNow);

    return () => {
      alive = false;
      window.clearTimeout(timer);
      window.removeEventListener('sana:notifications-updated', refreshNow);
      window.removeEventListener('sana:personal-alerts-updated', refreshNow);
      document.removeEventListener('visibilitychange', refreshNow);
    };
  }, [load]);

  const unread = useMemo(() => items.filter((item) => !item.is_read), [items]);

  useEffect(() => {
    const publishCount = () => {
      window.dispatchEvent(new CustomEvent('sana:notification-count-updated', {
        detail: { count: unread.length },
      }));
    };
    window.addEventListener('sana:notification-count-request', publishCount);
    publishCount();
    return () => window.removeEventListener('sana:notification-count-request', publishCount);
  }, [unread.length]);

  const markRead = async (item) => {
    if (item.is_read) return true;
    const key = item.notification_key;
    setUpdating(key);
    try {
      if (item.is_gps_alert) {
        await notificationsAPI.markRead({ isGps: true, deviceId: item.device_id, eventId: item.id });
      } else {
        await notificationsAPI.markRead({ isGps: false, eventKey: item.id });
      }
      setItems((current) => current.map((entry) => entry.notification_key === key
        ? { ...entry, is_read: true, status: entry.status === 'unread' ? 'read' : entry.status }
        : entry));
      window.dispatchEvent(new Event(item.is_gps_alert ? 'sana:traccar-alert-state-changed' : 'sana:panel-notification-state-changed'));
      window.dispatchEvent(new Event(item.is_gps_alert ? 'sana:personal-alerts-updated' : 'sana:notifications-updated'));
      return true;
    } catch {
      setError('وضعیت خواندن اعلان ثبت نشد. دوباره تلاش کنید.');
      return false;
    } finally {
      setUpdating('');
    }
  };

  const markAllRead = async () => {
    setUpdating('all');
    try {
      const [businessResult, gpsResult] = await notificationsAPI.markAllRead();
      setItems((current) => current.map((item) => {
        if (item.is_gps_alert && gpsResult.status === 'fulfilled') {
          return { ...item, is_read: true, status: item.status === 'unread' ? 'read' : item.status };
        }
        if (!item.is_gps_alert && businessResult.status === 'fulfilled') {
          return { ...item, is_read: true };
        }
        return item;
      }));
      if (businessResult.status === 'fulfilled') {
        window.dispatchEvent(new Event('sana:panel-notification-state-changed'));
        window.dispatchEvent(new Event('sana:notifications-updated'));
      }
      if (gpsResult.status === 'fulfilled') {
        window.dispatchEvent(new Event('sana:traccar-alert-state-changed'));
        window.dispatchEvent(new Event('sana:personal-alerts-updated'));
      }
      if (businessResult.status === 'rejected' || gpsResult.status === 'rejected') {
        setError('خواندن همه اعلان‌ها به‌طور کامل انجام نشد.');
      }
    } catch {
      setError('خواندن همه اعلان‌ها ناموفق بود. دوباره تلاش کنید.');
    } finally {
      setUpdating('');
    }
  };

  const openNotification = async (item) => {
    const success = await markRead(item);
    if (!success) return;
    setOpen(false);
    navigate(item.path || '/panel/alerts');
  };

  const openAll = () => {
    setOpen(false);
    navigate('/panel/alerts');
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((value) => !value);
          if (!open) {
            setError('');
            setLoading(true);
            load({ showError: true }).finally(() => setLoading(false));
          }
        }}
        className="relative rounded-field p-2 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        aria-label={unread.length ? `اعلان‌ها، ${unread.length} خوانده‌نشده` : 'اعلان‌ها'}
        aria-expanded={open}
      >
        <Bell size={20} />
        {unread.length > 0 && <span className="absolute -right-0.5 -top-0.5 min-w-[17px] rounded-full bg-danger px-1 text-center text-[10px] leading-[17px] text-white">{unread.length > 99 ? '99+' : unread.length}</span>}
      </button>
      {open && <>
        <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
        <section className="absolute left-0 top-full z-50 mt-2 w-[min(22rem,calc(100vw-1.5rem))] overflow-hidden rounded-xl border border-border-base bg-bg-overlay shadow-xl" aria-label="مرکز اعلان‌ها">
          <header className="flex items-center justify-between border-b border-border-base px-4 py-3">
            <div>
              <h3 className="text-sm font-semibold text-text-primary">اعلان‌ها</h3>
              <p className="mt-0.5 text-xs text-text-muted">{unread.length} خوانده‌نشده</p>
            </div>
            {unread.length > 0 && <button type="button" onClick={markAllRead} disabled={!!updating} className="text-xs text-brand-500 hover:underline disabled:opacity-50">خواندن همه</button>}
          </header>
          {loading ? <div className="flex justify-center py-8"><LoaderCircle size={20} className="animate-spin text-text-muted" /></div>
            : error ? <p className="px-4 py-5 text-xs text-danger">{error}</p>
            : items.length === 0 ? <p className="px-4 py-8 text-center text-sm text-text-muted">اعلانی برای نمایش وجود ندارد.</p>
            : <div className="max-h-[60vh] overflow-y-auto divide-y divide-border-base">
              {items.slice(0, 10).map((item) => (
                <button
                  type="button"
                  key={item.notification_key}
                  onClick={() => openNotification(item)}
                  className={`flex w-full gap-3 px-4 py-3 text-right transition-colors hover:bg-bg-hover ${!item.is_read ? 'bg-brand-500/5' : ''}`}
                >
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${!item.is_read ? 'bg-brand-500' : 'bg-transparent'}`} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-medium text-text-primary">{item.title}</span>
                    <span className="mt-1 block text-[11px] text-text-muted">{item.message}</span>
                    <span className="mt-1 block text-[10px] text-text-muted">{item.created_at ? new Date(item.created_at).toLocaleString('fa-IR') : 'زمان نامشخص'}</span>
                  </span>
                  {updating === item.notification_key ? <LoaderCircle size={14} className="animate-spin text-text-muted" /> : !item.is_read ? <Check size={14} className="text-text-muted" /> : null}
                </button>
              ))}
            </div>}
          <footer className="border-t border-border-base">
            <button type="button" onClick={openAll} className="flex w-full items-center justify-center gap-2 px-4 py-3 text-xs text-brand-500 hover:bg-bg-hover">
              مشاهده همه هشدارها <ExternalLink size={13} />
            </button>
          </footer>
        </section>
      </>}
    </div>
  );
}
