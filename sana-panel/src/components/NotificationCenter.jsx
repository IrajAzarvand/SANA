import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, Check, ExternalLink, LoaderCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { alertsAPI, panelNotificationsAPI } from '../api/services/fleet';
import { useAuth } from '../context/AuthContext';

const alertKey = (alert) => `${alert.device_id}:${alert.id}`;

export default function NotificationCenter() {
  const { isPersonal } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      if (isPersonal) {
        const response = await alertsAPI.list();
        setItems((Array.isArray(response?.results) ? response.results : []).map((item) => ({
          ...item,
          notification_key: alertKey(item),
          title: item.type || 'رویداد دستگاه',
          message: [item.vehicle_plate || 'دستگاه', item.device_imei ? `IMEI ${item.device_imei}` : ''].filter(Boolean).join(' · '),
          created_at: item.event_time,
          is_read: item.status !== 'new',
          path: '/panel/alerts',
        })));
      } else {
        const response = await panelNotificationsAPI.list();
        setItems(Array.isArray(response?.results) ? response.results.map((item) => ({
          ...item,
          notification_key: item.id,
        })) : []);
      }
      setError('');
    } catch {
      setError('دریافت اعلان‌ها ناموفق بود. دوباره تلاش کنید.');
    }
  }, [isPersonal]);

  useEffect(() => {
    let alive = true;
    let timer;
    const poll = async () => {
      if (document.visibilityState === 'visible') {
        try {
          if (isPersonal) {
            const response = await alertsAPI.list();
            if (alive) setItems((Array.isArray(response?.results) ? response.results : []).map((item) => ({
              ...item,
              notification_key: alertKey(item),
              title: item.type || 'رویداد دستگاه',
              message: [item.vehicle_plate || 'دستگاه', item.device_imei ? `IMEI ${item.device_imei}` : ''].filter(Boolean).join(' · '),
              created_at: item.event_time,
              is_read: item.status !== 'new',
              path: '/panel/alerts',
            })));
          } else {
            const response = await panelNotificationsAPI.list();
            if (alive) setItems(Array.isArray(response?.results) ? response.results.map((item) => ({
              ...item,
              notification_key: item.id,
            })) : []);
          }
          if (alive) setError('');
        } catch {
          if (alive) setError('دریافت اعلان‌ها ناموفق بود. دوباره تلاش کنید.');
        }
      }
      if (alive) timer = window.setTimeout(poll, 30000);
    };
    poll();
    const refresh = () => { if (alive) poll(); };
    window.addEventListener('sana:notifications-updated', refresh);
    window.addEventListener('sana:personal-alerts-updated', refresh);
    return () => {
      alive = false;
      window.clearTimeout(timer);
      window.removeEventListener('sana:notifications-updated', refresh);
      window.removeEventListener('sana:personal-alerts-updated', refresh);
    };
  }, [isPersonal]);

  const unread = useMemo(() => items.filter((item) => !item.is_read), [items]);

  const markRead = async (item) => {
    if (item.is_read) return true;
    const key = item.notification_key;
    setUpdating(key);
    try {
      if (isPersonal) {
        await alertsAPI.updateStatus({
          deviceId: item.device_id,
          eventId: item.id,
          status: 'acknowledged',
        });
      } else {
        await panelNotificationsAPI.markRead(item.id);
      }
      setItems((current) => current.map((entry) => entry.notification_key === key
        ? { ...entry, is_read: true, status: entry.status === 'new' ? 'acknowledged' : entry.status }
        : entry));
      window.dispatchEvent(new Event(isPersonal ? 'sana:personal-alerts-updated' : 'sana:notifications-updated'));
      return true;
    } catch {
      setError('وضعیت خواندن اعلان ثبت نشد. دوباره تلاش کنید.');
      return false;
    } finally {
      setUpdating('');
    }
  };

  const markAllRead = async () => {
    for (const item of unread) {
      const success = await markRead(item);
      if (!success) break;
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
            setLoading(true);
            load().finally(() => setLoading(false));
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
