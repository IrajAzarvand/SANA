import { useCallback, useMemo } from 'react';
import {
  Activity, ArrowLeft, Clock3, Cpu, FileBarChart,
  MapPinned, ShieldAlert, Wifi, WifiOff,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';
import Card from '../components/Card';
import Badge from '../components/Badge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { dashboardAPI } from '../api/services/dashboard';
import { devicesAPI } from '../api/services/fleet';
import { useApi } from '../hooks/useApi';

const managementLabels = {
  warehouse: 'در انبار',
  sold: 'فروخته‌شده',
  installed: 'نصب‌شده',
  active: 'فعال',
  ready: 'آماده تعیین تکلیف',
  faulty: 'خراب',
  lost: 'گمشده',
  stolen: 'سرقت‌شده',
  disconnected: 'قطع سرویس',
  retired: 'بازنشسته',
  disposed: 'امحاءشده',
};

function formatReceivedAt(value) {
  if (!value) return 'هنوز داده‌ای دریافت نشده';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' });
}

function PersonalDashboard() {
  const fetchDevices = useCallback(async () => {
    const result = await devicesAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);
  const fetchStats = useCallback(() => dashboardAPI.getStats(), []);

  const {
    data: devicesData,
    loading: devicesLoading,
    error: devicesError,
    refetch: refetchDevices,
  } = useApi(fetchDevices, []);
  const {
    data: stats,
    loading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useApi(fetchStats, []);

  const devices = Array.isArray(devicesData) ? devicesData : [];
  const activeCount = devices.filter((device) => device.data_active).length;
  const withDataCount = devices.filter((device) => Boolean(device.last_data_received_at)).length;
  const attentionCount = devices.length - activeCount;

  const recentDevices = useMemo(() => (
    [...devices]
      .sort((a, b) => {
        const aTime = a.last_data_received_at ? new Date(a.last_data_received_at).getTime() : 0;
        const bTime = b.last_data_received_at ? new Date(b.last_data_received_at).getTime() : 0;
        return bTime - aTime;
      })
      .slice(0, 5)
  ), [devices]);

  const subscription = stats?.current_subscription;

  return (
    <div className="min-w-0 space-y-5 sm:space-y-6">
      <PageHeader
        title="داشبورد شخصی"
        subtitle="نمای یکپارچه دستگاه‌ها و وضعیت سرویس GPS شما"
        actions={
          <Link
            to="/panel/devices"
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-field border border-border-base px-3 py-2 text-sm text-text-primary transition-colors hover:bg-bg-hover"
          >
            همه دستگاه‌ها <ArrowLeft size={16} />
          </Link>
        }
      />

      {subscription?.is_expiring_soon && (
        <div className="flex min-w-0 items-start gap-3 rounded-card border border-warning/30 bg-warning/10 p-3 sm:p-4">
          <ShieldAlert size={20} className="mt-0.5 shrink-0 text-warning" />
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-warning">قرارداد شما به‌زودی منقضی می‌شود</h2>
            <p className="mt-1 break-words text-xs leading-6 text-text-secondary">
              قرارداد <span className="font-mono">{subscription.contract_number}</span>
              {' '}تا {Number(subscription.days_until_expiry).toLocaleString('fa-IR')} روز دیگر منقضی می‌شود.
              برای تمدید با پشتیبانی سانا تماس بگیرید.
            </p>
          </div>
        </div>
      )}

      {devicesLoading ? (
        <Card><LoadingSpinner /></Card>
      ) : devicesError ? (
        <Card><ErrorState error={devicesError} onRetry={refetchDevices} /></Card>
      ) : (
        <>
          <section aria-label="خلاصه دستگاه‌ها" className="grid min-w-0 grid-cols-2 gap-3 xl:grid-cols-4">
            <StatCard title="دستگاه‌های من" value={devices.length.toLocaleString('fa-IR')} icon={Cpu} color="brand" />
            <StatCard title="دارای مجوز سرویس GPS" value={activeCount.toLocaleString('fa-IR')} icon={Wifi} color="success" />
            <StatCard title="نیازمند بررسی" value={attentionCount.toLocaleString('fa-IR')} icon={ShieldAlert} color={attentionCount ? 'warning' : 'muted'} />
            <StatCard title="دارای سابقه دریافت GPS" value={withDataCount.toLocaleString('fa-IR')} icon={Activity} color="info" />
          </section>

          <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(280px,1fr)]">
            <Card
              title="آخرین وضعیت دستگاه‌ها"
              subtitle="اطلاعات واقعی ثبت‌شده در سانا و زمان آخرین دریافت از Traccar"
              action={
                <Link to="/panel/devices" className="inline-flex min-h-10 items-center gap-1 text-xs text-brand-400 hover:text-brand-300">
                  مشاهده فهرست <ArrowLeft size={14} />
                </Link>
              }
            >
              {recentDevices.length === 0 ? (
                <EmptyState
                  icon={Cpu}
                  title="هنوز دستگاهی به حساب شما اختصاص داده نشده"
                  description="پس از ثبت تخصیص دستگاه به حساب شما، اطلاعات آن در این قسمت نمایش داده می‌شود."
                />
              ) : (
                <div className="space-y-2">
                  {recentDevices.map((device) => (
                    <div key={device.id} className="flex min-w-0 flex-col gap-2 rounded-field border border-border-base bg-bg-base p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm font-semibold text-text-primary">{device.imei}</span>
                          <Badge variant={device.data_active ? 'success' : 'muted'}>
                            {device.data_active ? 'سرویس فعال' : 'سرویس غیرفعال'}
                          </Badge>
                          <span className="text-[11px] text-text-muted">{managementLabels[device.management_status] || 'وضعیت نامشخص'}</span>
                        </div>
                        <p className="mt-1 truncate text-xs text-text-secondary">
                          {device.vehicle_plate ? `خودرو: ${device.vehicle_plate}` : (device.device_model_name || device.traccar_model || 'مدل نامشخص')}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 text-xs text-text-muted sm:max-w-52">
                        {device.last_data_received_at ? <Wifi size={14} className="text-success" /> : <WifiOff size={14} />}
                        <span className="min-w-0">{formatReceivedAt(device.last_data_received_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title="وضعیت کلی سرویس" subtitle="بر اساس اطلاعات فعلی دستگاه‌های قابل‌دسترسی">
              <div className="space-y-4">
                <div>
                  <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                    <span className="text-text-secondary">سرویس GPS فعال</span>
                    <strong className="tabular-nums text-success">{activeCount.toLocaleString('fa-IR')} از {devices.length.toLocaleString('fa-IR')}</strong>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-bg-hover">
                    <div
                      className="h-full rounded-full bg-success transition-all"
                      style={{ width: devices.length ? `${(activeCount / devices.length) * 100}%` : '0%' }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-field bg-bg-base p-3">
                    <div className="text-[11px] text-text-muted">دریافت داده</div>
                    <div className="mt-1 text-xl font-bold tabular-nums text-text-primary">{withDataCount.toLocaleString('fa-IR')}</div>
                  </div>
                  <div className="rounded-field bg-bg-base p-3">
                    <div className="text-[11px] text-text-muted">بدون داده ثبت‌شده</div>
                    <div className="mt-1 text-xl font-bold tabular-nums text-text-primary">{(devices.length - withDataCount).toLocaleString('fa-IR')}</div>
                  </div>
                </div>
                {statsError && (
                  <div role="status" className="rounded-field border border-warning/30 bg-warning/10 p-3 text-xs leading-5 text-text-secondary">
                    اطلاعات قرارداد دریافت نشد.
                    <button type="button" onClick={refetchStats} className="mr-2 text-brand-400 underline">تلاش دوباره</button>
                  </div>
                )}
                {statsLoading && <p className="text-[11px] text-text-muted">در حال بررسی اطلاعات قرارداد…</p>}
                {subscription && !subscription.is_expiring_soon && (
                  <div className="flex items-center gap-2 text-xs text-text-secondary">
                    <Clock3 size={15} className="text-success" />
                    قرارداد فعال: <span className="font-mono">{subscription.contract_number}</span>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </>
      )}

      <section aria-label="دسترسی سریع" className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <QuickLink to="/panel/map" icon={MapPinned} title="نقشه زنده" description="مشاهده آخرین موقعیت دستگاه‌های شما" />
        <QuickLink to="/panel/devices" icon={Cpu} title="دستگاه‌های من" description="مشاهده مشخصات و وضعیت سرویس GPS" />
        <QuickLink to="/panel/reports/trips" icon={FileBarChart} title="گزارش مسیرها" description="بررسی مسیر و سوابق حرکتی دستگاه‌ها" />
      </section>
    </div>
  );
}

function QuickLink({ to, icon: Icon, title, description }) {
  return (
    <Link
      to={to}
      className="group flex min-w-0 items-center gap-3 rounded-card border border-border-base bg-bg-elevated p-4 transition-colors hover:border-brand-500/50 hover:bg-bg-hover"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-field bg-brand-500/10 text-brand-400">
        <Icon size={20} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-text-primary">{title}</span>
        <span className="mt-1 block text-xs leading-5 text-text-muted">{description}</span>
      </span>
      <ArrowLeft size={16} className="shrink-0 text-text-muted transition-transform group-hover:-translate-x-1" />
    </Link>
  );
}

export default PersonalDashboard;
