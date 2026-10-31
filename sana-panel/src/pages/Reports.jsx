import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileBarChart, Calendar, Terminal, Radio, Pause, Play, Trash2, ShieldCheck } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import Select from '../components/Select';
import Modal from '../components/Modal';
import Badge from '../components/Badge';
import EmptyState from '../components/EmptyState';
import ReportCard from '../components/ReportCard';
import apiClient from '../api/client';
import {
  reportTypes,
  reportCategories,
  dateRanges,
  sampleTripsReport,
} from '../data/reportsData';
import { useAuth } from '../context/AuthContext';

// گزارش‌های مخصوص ادمین
const adminReports = [
  {
    id: 'companies-overview',
    title: 'گزارش کلی شرکت‌ها',
    description: 'خلاصه عملکرد همه شرکت‌های مشتری سامانه',
    icon: 'truck',
    color: 'brand',
    format: ['PDF', 'Excel'],
    category: 'مدیریتی',
  },
  {
    id: 'revenue',
    title: 'گزارش درآمد و قرارداد',
    description: 'درآمد ماهانه، قراردادهای فعال و اشتراک‌ها',
    icon: 'fuel',
    color: 'success',
    format: ['PDF', 'Excel'],
    category: 'مالی',
  },
  {
    id: 'system-usage',
    title: 'گزارش استفاده از سامانه',
    description: 'آمار کاربران، دستگاه‌ها و ترافیک سراسری',
    icon: 'cpu',
    color: 'info',
    format: ['PDF'],
    category: 'فنی',
  },
];

// گزارش‌های مخصوص مشتری شخصی
const personalReports = [
  {
    id: 'my-trips',
    title: 'گزارش سفرهای من',
    description: 'لیست کامل سفرهای خودروهای من',
    icon: 'route',
    color: 'brand',
    format: ['PDF', 'Excel'],
    category: 'شخصی',
  },
  {
    id: 'my-vehicle-usage',
    title: 'استفاده از خودروی من',
    description: 'میزان استفاده و مسافت طي‌شده خودروهای من',
    icon: 'truck',
    color: 'info',
    format: ['PDF'],
    category: 'شخصی',
  },
];


function LiveTerminal({ streamName, title, description, icon: Icon, accent }) {
  const [running, setRunning] = useState(true);
  const [status, setStatus] = useState('connecting');
  const [lines, setLines] = useState([]);
  const [error, setError] = useState('');
  const bodyRef = useRef(null);

  useEffect(() => {
    if (!running) return undefined;
    const controller = new AbortController();
    let cancelled = false;
    const connect = async () => {
      try {
        const token = localStorage.getItem('sana_access_token');
        const response = await fetch(`${apiClient.defaults.baseURL}/gps-monitor/logs/${streamName}/`, {
          headers: token ? { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' } : { Accept: 'text/event-stream' },
          signal: controller.signal,
        });
        if (!response.ok) {
          const detail = response.status === 403
            ? 'دسترسی فقط برای ادمین کل سایت مجاز است.'
            : response.status === 401
              ? 'نشست شما منقضی شده است؛ دوباره وارد شوید.'
              : `خطای سرور: ${response.status}`;
          throw new Error(detail);
        }
        if (!response.body) throw new Error('مرورگر از دریافت زنده پشتیبانی نمی‌کند.');
        setStatus('live');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const event of events) {
            const dataLine = event.split('\n').find((line) => line.startsWith('data: '));
            if (!dataLine) continue;
            try {
              const payload = JSON.parse(dataLine.slice(6));
              if (payload.line) {
                setLines((previous) => [...previous, { id: `${Date.now()}-${Math.random()}`, text: payload.line }].slice(-250));
              }
            } catch {
              // Ignore incomplete or malformed server-sent events.
            }
          }
        }
        if (!cancelled) setStatus('disconnected');
      } catch (err) {
        if (err.name !== 'AbortError' && !cancelled) {
          setError(err.message || 'اتصال برقرار نشد.');
          setStatus('error');
        }
      }
    };
    connect();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [running, streamName]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [lines]);

  const displayStatus = running ? status : 'paused';
  const statusLabel = displayStatus === 'live' ? 'زنده' : displayStatus === 'connecting' ? 'در حال اتصال' : displayStatus === 'paused' ? 'متوقف' : displayStatus === 'error' ? 'خطا' : 'قطع اتصال';

  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border-base p-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${accent}`}>
            <Icon size={19} />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-text-primary">{title}</h3>
            <p className="mt-1 text-xs leading-5 text-text-muted">{description}</p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${displayStatus === 'live' ? 'bg-emerald-500/10 text-emerald-600' : displayStatus === 'error' ? 'bg-danger/10 text-danger' : 'bg-bg-base text-text-muted'}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${displayStatus === 'live' ? 'animate-pulse bg-emerald-500' : displayStatus === 'error' ? 'bg-danger' : 'bg-text-muted'}`} />
          {statusLabel}
        </span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 bg-[#111827] px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400/90" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/90" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/90" />
          <span className="mr-2 font-mono">sana@server:~</span>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setLines([])} title="پاک کردن نمایش" className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white"><Trash2 size={15} /></button>
          <button type="button" onClick={() => {
            if (running) {
              setRunning(false);
            } else {
              setStatus('connecting');
              setError('');
              setRunning(true);
            }
          }} title={running ? 'توقف نمایش زنده' : 'ادامه نمایش زنده'} className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-2.5 py-1.5 text-xs text-slate-100 hover:bg-white/15">
            {running ? <Pause size={13} /> : <Play size={13} />}
            {running ? 'توقف' : 'ادامه'}
          </button>
        </div>
      </div>
      <div ref={bodyRef} aria-live="polite" className="h-72 overflow-auto bg-[#0b1220] p-4 font-mono text-[11px] leading-5 text-emerald-300 sm:h-80 sm:text-xs">
        {lines.length === 0 && !error && (
          <div className="text-slate-500">
            <p>{running ? 'در انتظار دریافت لاگ...' : 'نمایش متوقف شده است.'}</p>
            <p className="mt-1 text-slate-600">$ {streamName === 'service' ? 'journalctl -u sana-gps -f' : 'sudo /usr/local/sbin/sana-gps-network-capture'}</p>
          </div>
        )}
        {error && <p className="mb-2 whitespace-pre-wrap text-rose-300">خطا: {error}</p>}
        {lines.map((line) => (
          <div key={line.id} className="grid grid-cols-[auto_1fr] gap-2 break-words">
            <span className="select-none text-slate-600">$</span>
            <span className="whitespace-pre-wrap">{line.text}</span>
          </div>
        ))}
        {displayStatus === 'live' && <span className="inline-block h-3.5 w-1.5 animate-pulse bg-emerald-400 align-middle" />}
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-border-base px-4 py-2 text-[11px] text-text-muted">
        <span>{lines.length} خط اخیر در نمایش</span>
        <span className="inline-flex items-center gap-1"><ShieldCheck size={12} /> فقط خواندنی</span>
      </div>
    </section>
  );
}

function AdminGPSMonitor() {
  return (
    <section className="space-y-5 border-t border-border-base pt-7">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-brand-500/20 bg-brand-500/5 px-3 py-1 text-xs font-medium text-brand-600">
            <ShieldCheck size={14} /> ویژه ادمین کل سایت
          </div>
          <h2 className="text-xl font-bold text-text-primary sm:text-2xl">مانیتورینگ زنده GPS</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">لاگ سرویس و ترافیک شبکه را از یک صفحه بررسی کن. این بخش فقط خواندنی است و هیچ دستوری برای تغییر تنظیمات یا وضعیت دستگاه اجرا نمی‌کند.</p>
        </div>
        
      </div>
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <LiveTerminal streamName="service" title="لاگ زنده سرویس sana-gps" description="رویدادهای systemd، همگام‌سازی Traccar و خطاهای سرویس" icon={Terminal} accent="bg-sky-500/10 text-sky-500" />
        <LiveTerminal streamName="network" title="ترافیک زنده شبکه" description="نمایش ترافیک شبکه از طریق ابزار تشخیصی محدودشده سرور" icon={Radio} accent="bg-emerald-500/10 text-emerald-500" />
      </div>
    </section>
  );
}

export default function Reports() {
  const [category, setCategory] = useState('all');
  const [dateRange, setDateRange] = useState('last7');
  const [preview, setPreview] = useState(null);

  const { isSiteAdmin, isPersonal, isBranchManager, user } = useAuth();
  const navigate = useNavigate();

  // لیست گزارش‌ها بر اساس نقش
  const availableReports = useMemo(() => {
    if (isSiteAdmin) {
      return [...adminReports, ...reportTypes];
    }
    if (isPersonal) {
      return personalReports;
    }
    return reportTypes;
  }, [isSiteAdmin, isPersonal]);

  // دسته‌بندی‌ها
  const availableCategories = useMemo(() => {
    if (isSiteAdmin) {
      return [
        { value: 'all', label: 'همه' },
        { value: 'مدیریتی', label: 'مدیریتی' },
        { value: 'مالی', label: 'مالی' },
        { value: 'فنی', label: 'فنی' },
        { value: 'عملیاتی', label: 'عملیاتی' },
        { value: 'عملکردی', label: 'عملکردی' },
        { value: 'امنیتی', label: 'امنیتی' },
      ];
    }
    if (isPersonal) {
      return [
        { value: 'all', label: 'همه' },
        { value: 'شخصی', label: 'شخصی' },
      ];
    }
    return reportCategories;
  }, [isSiteAdmin, isPersonal]);

  const filtered = useMemo(() => {
    if (category === 'all') return availableReports;
    return availableReports.filter((r) => r.category === category);
  }, [availableReports, category]);

  // عنوان
  const getTitle = () => {
    if (isSiteAdmin) return 'گزارش‌های سامانه';
    if (isPersonal) return 'گزارش‌های من';
    if (isBranchManager) return `گزارش‌های شعبه ${user?.branch?.name || ''}`;
    return 'گزارش‌های سازمان';
  };

  return (
    <div className="space-y-6">

      <PageHeader
        title={getTitle()}
        subtitle={
          isSiteAdmin
            ? 'گزارش‌های مدیریتی و تحلیلی سراسر سامانه'
            : isPersonal
              ? 'گزارش‌های خودروهای شما'
              : 'گزارش‌های عملکردی و تحلیلی ناوگان'
        }
      />

      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Select
            label="دسته‌بندی"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={availableCategories}
          />
          <Select
            label="بازه زمانی"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            options={dateRanges}
          />
        </div>
      </Card>

      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon={FileBarChart}
            title="گزارشی یافت نشد"
            description="هیچ گزارشی در این دسته‌بندی وجود ندارد."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              onPreview={(report) => {
                if (report.id === 'trips' || report.id === 'my-trips') {
                  navigate('/panel/reports/trips');
                  return;
                }
                setPreview(report);
              }}
            />
          ))}
        </div>
      )}

      {isSiteAdmin && <AdminGPSMonitor />}

      <Modal
        open={!!preview}
        onClose={() => setPreview(null)}
        title={preview ? `پیش‌نمایش — ${preview.title}` : ''}
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPreview(null)}>بستن</Button>
            <Button>دانلود گزارش</Button>
          </>
        }
      >
        {preview && (
          <div className="space-y-4">

            <div className="flex flex-wrap items-center gap-3 p-3 bg-bg-base border border-border-base rounded-field">
              <Calendar size={16} className="text-text-muted" />
              <span className="text-sm text-text-secondary">
                بازه: {dateRanges.find((d) => d.value === dateRange)?.label}
              </span>
              <Badge variant="brand">{filtered.length} گزارش موجود</Badge>
            </div>

            {preview.id === 'trips' || preview.id === 'my-trips' ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-base">
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">#</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">خودرو</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">راننده</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">تاریخ</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">مسافت</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">مدت</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">حداکثر سرعت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sampleTripsReport.map((trip) => (
                      <tr key={trip.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                        <td className="py-3 px-3 text-text-muted font-mono text-xs">#{trip.id}</td>
                        <td className="py-3 px-3 text-text-primary font-mono text-xs">{trip.vehicle}</td>
                        <td className="py-3 px-3 text-text-secondary text-xs">{trip.driver}</td>
                        <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.date}</td>
                        <td className="py-3 px-3 text-text-primary font-mono text-xs">{trip.distance} km</td>
                        <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.duration}</td>
                        <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.maxSpeed} km/h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-12 text-center">
                <FileBarChart size={48} className="text-text-muted mx-auto mb-4" />
                <p className="text-sm text-text-secondary mb-1">
                  پیش‌نمایش این گزارش آماده نیست
                </p>
                <p className="text-xs text-text-muted">
                  این گزارش در فاز پیاده‌سازی تکمیل خواهد شد
                </p>
              </div>
            )}

          </div>
        )}
      </Modal>

    </div>
  );
}