import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, Check, ExternalLink, LoaderCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { alertsAPI } from '../api/services/fleet';
import { useAuth } from '../context/AuthContext';

const alertKey = (alert) => `${alert.device_id}:${alert.id}`;

export default function NotificationCenter() {
  const { isPersonal } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!isPersonal) return;
    try {
      const response = await alertsAPI.list();
      setAlerts(Array.isArray(response?.results) ? response.results : []);
      setError('');
    } catch {
      setError('دریافت اعلان‌ها ناموفق بود.');
    }
  }, [isPersonal]);

  useEffect(() => {
    if (!isPersonal) return undefined;
    let alive = true;
    let timer;
    const poll = async () => {
      if (document.visibilityState === 'visible') {
        try {
          const response = await alertsAPI.list();
          if (alive) {
            setAlerts(Array.isArray(response?.results) ? response.results : []);
            setError('');
          }
        } catch {
          if (alive) setError('دریافت اعلان‌ها ناموفق بود.');
        }
      }
      if (alive) timer = window.setTimeout(poll, 30000);
    };
    poll();
    window.addEventListener('sana:personal-alerts-updated', poll);
    return () => {
      alive = false;
      window.clearTimeout(timer);
      window.removeEventListener('sana:personal-alerts-updated', poll);
    };
  }, [isPersonal]);

  const unread = useMemo(() => alerts.filter((item) => item.status === 'new'), [alerts]);

  const markRead = async (alert) => {
    if (alert.status !== 'new') return;
    const key = alertKey(alert);
    setUpdating(key);
    try {
      await alertsAPI.updateStatus({ deviceId: alert.device_id, eventId: alert.id, status: 'acknowledged' });
      setAlerts((current) => current.map((item) => alertKey(item) === key ? { ...item, status: 'acknowledged' } : item));
      window.dispatchEvent(new Event('sana:personal-alerts-updated'));
    } catch {
      setError('خواندن اعلان ثبت نشد. دوباره تلاش کنید.');
    } finally {
      setUpdating('');
    }
  };

  const markAllRead = async () => {
    for (const item of unread) await markRead(item);
  };
  const openAlerts = () => { setOpen(false); navigate('/panel/alerts'); };

  return (
    <div className="relative">
      <button type="button" onClick={() => { setOpen((value) => !value); if (!open && isPersonal) { setLoading(true); load().finally(() => setLoading(false)); } }} className="relative rounded-field p-2 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary" aria-label={unread.length ? `اعلان‌ها، ${unread.length} خوانده‌نشده` : 'اعلان‌ها'} aria-expanded={open}>
        <Bell size={20} />
        {unread.length > 0 && <span className="absolute -right-0.5 -top-0.5 min-w-[17px] rounded-full bg-danger px-1 text-center text-[10px] leading-[17px] text-white">{unread.length > 99 ? '99+' : unread.length}</span>}
      </button>
      {open && <>
        <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
        <section className="absolute left-0 top-full z-50 mt-2 w-[min(22rem,calc(100vw-1.5rem))] overflow-hidden rounded-xl border border-border-base bg-bg-overlay shadow-xl" aria-label="مرکز اعلان‌ها">
          <header className="flex items-center justify-between border-b border-border-base px-4 py-3">
            <div><h3 className="text-sm font-semibold text-text-primary">اعلان‌ها</h3><p className="mt-0.5 text-xs text-text-muted">{isPersonal ? `${unread.length} خوانده‌نشده` : 'مشاهده هشدارهای پنل'}</p></div>
            {isPersonal && unread.length > 0 && <button type="button" onClick={markAllRead} disabled={!!updating} className="text-xs text-brand-500 hover:underline disabled:opacity-50">خواندن همه</button>}
          </header>
          {!isPersonal ? <p className="px-4 py-5 text-center text-sm text-text-muted">برای مشاهده هشدارهای پنل، فهرست هشدارها را باز کنید.</p>
            : loading ? <div className="flex justify-center py-8"><LoaderCircle size={20} className="animate-spin text-text-muted" /></div>
            : error ? <p className="px-4 py-5 text-xs text-danger">{error}</p>
            : alerts.length === 0 ? <p className="px-4 py-8 text-center text-sm text-text-muted">اعلانی برای نمایش وجود ندارد.</p>
            : <div className="max-h-[60vh] overflow-y-auto divide-y divide-border-base">
              {alerts.slice(0, 8).map((item) => {
                const key = alertKey(item);
                const isUnread = item.status === 'new';
                return <button type="button" key={key} onClick={async () => { await markRead(item); openAlerts(); }} className={`flex w-full gap-3 px-4 py-3 text-right transition-colors hover:bg-bg-hover ${isUnread ? 'bg-brand-500/5' : ''}`}>
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${isUnread ? 'bg-brand-500' : 'bg-transparent'}`} />
                  <span className="min-w-0 flex-1"><span className="block text-xs font-medium text-text-primary">{item.type || 'رویداد دستگاه'}</span><span className="mt-1 block text-[11px] text-text-muted">{item.vehicle_plate || 'دستگاه'} · {item.event_time ? new Date(item.event_time).toLocaleString('fa-IR') : 'زمان نامشخص'}</span></span>
                  {updating === key ? <LoaderCircle size={14} className="animate-spin text-text-muted" /> : isUnread ? <Check size={14} className="text-text-muted" /> : null}
                </button>;
              })}
            </div>}
          <footer className="border-t border-border-base"><button type="button" onClick={openAlerts} className="flex w-full items-center justify-center gap-2 px-4 py-3 text-xs text-brand-500 hover:bg-bg-hover">مشاهده همه هشدارها <ExternalLink size={13} /></button></footer>
        </section>
      </>}
    </div>
  );
}
