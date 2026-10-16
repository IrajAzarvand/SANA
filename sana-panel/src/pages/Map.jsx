import { useEffect, useState } from 'react';
import { Activity, MapPin } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import apiClient from '../api/client';
import LiveDeviceMap from '../../../sana-map/src/LiveDeviceMap';

const REFRESH_INTERVAL_MS = 10_000;

export default function Map() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);

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
    const intervalId = window.setInterval(refreshPositions, REFRESH_INTERVAL_MS);
    return () => { active = false; window.clearInterval(intervalId); };
  }, []);

  const moving = positions.filter((item) => item.status === 'moving').length;
  const stopped = positions.filter((item) => item.status === 'stopped').length;
  const offline = positions.filter((item) => item.status === 'offline').length;

  return (
    <div className="space-y-5">
      <PageHeader title="نقشه زنده" subtitle="موقعیت فعلی و آخرین موقعیت معتبر دستگاه‌های GPS" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Summary label="دستگاه‌های دارای موقعیت" value={positions.length} icon={<MapPin size={17} />} />
        <Summary label="در حرکت" value={moving} tone="text-brand-400" />
        <Summary label="متوقف" value={stopped} tone="text-warning" />
        <Summary label="آفلاین" value={offline} tone="text-text-muted" />
      </div>
      {error && <div role="alert" className="rounded-card border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-text-primary">{error}{positions.length > 0 && <span className="mr-2 text-text-muted">موقعیت‌های قبلی تا دریافت داده جدید نمایش داده می‌شوند.</span>}</div>}
      <section className="overflow-hidden rounded-card border border-border-base bg-bg-elevated">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-base px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-medium text-text-primary"><Activity size={17} className="text-brand-400" />موقعیت دستگاه‌ها</div>
          <div className="flex items-center gap-3 text-xs text-text-muted">
            <span>{loading ? 'در حال دریافت اطلاعات…' : lastUpdated ? 'آخرین به‌روزرسانی: ' + lastUpdated.toLocaleTimeString('fa-IR') : 'در انتظار اطلاعات'}</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-brand-500" />به‌روزرسانی خودکار هر ۱۰ ثانیه</span>
          </div>
        </div>
        <div className="h-[min(72vh,760px)] min-h-[420px]"><LiveDeviceMap positions={positions} /></div>
        {!loading && !error && positions.length === 0 && <div className="flex items-center gap-2 border-t border-border-base px-4 py-3 text-sm text-text-muted"><MapPin size={16} />هنوز موقعیت معتبری برای دستگاه‌های قابل‌دسترسی ثبت نشده است.</div>}
      </section>
    </div>
  );
}

function Summary({ label, value, tone = 'text-text-primary', icon = null }) {
  return <div className="flex items-center gap-3 rounded-card border border-border-base bg-bg-elevated px-4 py-3">{icon && <span className="text-brand-400">{icon}</span>}<div className="min-w-0"><div className="text-xs text-text-muted">{label}</div><div className={'mt-1 text-xl font-semibold tabular-nums ' + tone}>{value}</div></div></div>;
}