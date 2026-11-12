import { useCallback } from 'react';
import {
  Activity, AlertTriangle, Building2, Car, CheckCircle2, Clock3, Cpu,
  Database, HardDrive, RefreshCw, Server, Users, Wifi, WifiOff, XCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import StatCard from '../components/StatCard';
import Badge from '../components/Badge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { dashboardAPI } from '../api/services/dashboard';
import { useApi } from '../hooks/useApi';

const number = (value) => value == null ? '—' : new Intl.NumberFormat('fa-IR').format(value);
const bytes = (value) => {
  if (value == null) return '—';
  const units = ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت', 'ترابایت'];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 1 }).format(size)} ${units[unit]}`;
};
const percent = (value) => value == null ? '—' : `${number(value)}٪`;
const serviceNames = {
  'sana-backend-production.service': 'بک‌اند سانا',
  'sana-gps.service': 'دریافت GPS',
  'traccar.service': 'Traccar',
  'postgresql.service': 'پایگاه داده',
};
const serviceState = {
  active: { label: 'فعال', variant: 'success', icon: CheckCircle2 },
  failed: { label: 'خطا', variant: 'danger', icon: XCircle },
  inactive: { label: 'متوقف', variant: 'warning', icon: AlertTriangle },
  activating: { label: 'در حال راه‌اندازی', variant: 'info', icon: Clock3 },
  deactivating: { label: 'در حال توقف', variant: 'warning', icon: Clock3 },
  unknown: { label: 'نامشخص', variant: 'neutral', icon: AlertTriangle },
};
const managementLabels = {
  warehouse: 'انبار',
  sold: 'فروخته‌شده',
  installed: 'نصب‌شده',
  active: 'فعال',
  ready: 'آماده تعیین تکلیف',
  faulty: 'خراب',
  lost: 'گمشده',
  stolen: 'سرقت‌شده',
  disconnected: 'قطع سرویس',
  retired: 'بازنشسته',
  disposed: 'امحاء‌شده',
};

function ProgressRow({ label, value, total, color = 'bg-brand-500' }) {
  const ratio = total > 0 ? Math.min(100, (value / total) * 100) : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between gap-3 text-xs">
        <span className="text-text-secondary">{label}</span>
        <span className="font-mono text-text-primary">{number(value)}</span>
      </div>
      <div className="h-2 rounded-full bg-bg-hover overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${ratio}%` }} />
      </div>
    </div>
  );
}

function Metric({ label, value, hint }) {
  return (
    <div className="rounded-field border border-border-base bg-bg-base p-3 min-w-0">
      <div className="text-[11px] text-text-muted mb-1">{label}</div>
      <div className="text-lg font-bold text-text-primary font-mono break-words">{value}</div>
      {hint && <div className="text-[10px] text-text-muted mt-1">{hint}</div>}
    </div>
  );
}

function ServiceTile({ unit, state }) {
  const status = serviceState[state] || serviceState.unknown;
  const Icon = status.icon;
  return (
    <div className="flex items-center justify-between gap-3 rounded-field border border-border-base bg-bg-base p-3">
      <div className="flex items-center gap-2 min-w-0">
        <Icon size={17} className={status.variant === 'success' ? 'text-success' : status.variant === 'danger' ? 'text-danger' : 'text-warning'} />
        <span className="text-sm text-text-primary truncate">{serviceNames[unit] || unit}</span>
      </div>
      <Badge variant={status.variant}>{status.label}</Badge>
    </div>
  );
}

export default function AdminDashboard() {
  const fetchOverview = useCallback(() => dashboardAPI.getAdminOverview(), []);
  const { data, loading, error, refetch } = useApi(fetchOverview, [], { keepDataOnRefetch: true });

  if (loading && !data) {
    return <div className="space-y-5"><PageHeader title="مرکز مدیریت سانا" subtitle="نمای یکپارچه وضعیت سامانه و کسب‌وکار" /><Card><LoadingSpinner /></Card></div>;
  }
  if (error && !data) {
    return <div className="space-y-5"><PageHeader title="مرکز مدیریت سانا" subtitle="دریافت اطلاعات داشبورد ناموفق بود" /><Card><ErrorState error={error} onRetry={refetch} /></Card></div>;
  }

  const server = data?.server || {};
  const customers = data?.customers || {};
  const fleet = data?.fleet || {};
  const traccar = data?.traccar || {};
  const contracts = data?.contracts || {};
  const services = server.services || {};
  const serviceValues = Object.values(services);
  const healthyServices = serviceValues.filter((value) => value === 'active').length;
  const failedServices = serviceValues.filter((value) => value === 'failed').length;
  const loadOne = server.cpu?.load_average?.[0];
  const memory = server.memory || {};
  const disk = server.disk || {};
  const db = server.database || {};

  return (
    <div className="space-y-5">
      <PageHeader
        title="مرکز مدیریت سانا"
        subtitle="نمای یکپارچه زیرساخت، ناوگان، مشتریان و قراردادها"
        action={
          <button onClick={() => refetch().catch(() => {})} disabled={loading}
            className="inline-flex items-center gap-2 rounded-field border border-border-base px-3 py-2 text-xs text-text-secondary hover:bg-bg-hover disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            بروزرسانی
          </button>
        }
      />

      {error && data && <div className="rounded-field border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">بروزرسانی انجام نشد؛ اطلاعات نمایش‌داده‌شده مربوط به آخرین دریافت موفق است.</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard title="شرکت‌های مشتری" value={number(customers.organizations)} icon={Building2} color="brand" />
        <StatCard title="مشتریان شخصی" value={number(customers.personal_customers)} icon={Users} color="info" />
        <StatCard title="کل دستگاه‌های GPS" value={number(fleet.devices)} icon={Cpu} color="success" />
        <StatCard title="قراردادهای فعال" value={number(contracts.active)} icon={CheckCircle2} color="success" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card title="سلامت زیرساخت سرور" subtitle="اطلاعات خواندنی از سیستم‌عامل و سرویس‌های اصلی" className="xl:col-span-2">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
            <Metric label="بار سیستم (۱ دقیقه)" value={loadOne == null ? '—' : number(loadOne)} hint={server.cpu?.load_average?.length ? `۵ دقیقه: ${number(server.cpu.load_average[1])} · ۱۵ دقیقه: ${number(server.cpu.load_average[2])}` : 'Load Average؛ نه درصد CPU'} />
            <Metric label="مصرف حافظه RAM" value={percent(memory.used_percent)} hint={`${bytes(memory.used_bytes)} از ${bytes(memory.total_bytes)}`} />
            <Metric label="فضای دیسک ریشه" value={percent(disk.used_percent)} hint={`${bytes(disk.used_bytes)} مصرف‌شده · ${bytes(disk.free_bytes)} آزاد`} />
          </div>
          <div className="space-y-3">
            <ProgressRow label="حافظه RAM" value={memory.used_bytes || 0} total={memory.total_bytes || 0} color="bg-info" />
            <ProgressRow label="فضای دیسک" value={disk.used_bytes || 0} total={disk.total_bytes || 0} color="bg-brand-500" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
            <div className="flex items-center gap-3 rounded-field border border-border-base p-3">
              <Database size={18} className={db.status === 'connected' ? 'text-success' : 'text-danger'} />
              <div className="min-w-0 flex-1">
                <div className="text-xs text-text-secondary">اتصال PostgreSQL</div>
                <div className="text-sm font-semibold text-text-primary">{db.status === 'connected' ? 'متصل' : 'در دسترس نیست'}</div>
              </div>
              <span className="text-xs text-text-muted">{bytes(db.size_bytes)}</span>
            </div>
            <div className="flex items-center gap-3 rounded-field border border-border-base p-3">
              <Server size={18} className="text-text-muted" />
              <div className="min-w-0 flex-1">
                <div className="text-xs text-text-secondary">زمان روشن بودن سرور</div>
                <div className="text-sm font-semibold text-text-primary">{server.uptime_seconds == null ? '—' : `${number(Math.floor(server.uptime_seconds / 86400))} روز و ${number(Math.floor((server.uptime_seconds % 86400) / 3600))} ساعت`}</div>
              </div>
            </div>
          </div>
        </Card>

        <Card title="وضعیت سرویس‌ها" subtitle={`${number(healthyServices)} از ${number(serviceValues.length)} سرویس فعال`}>
          <div className="space-y-2">
            {Object.entries(services).map(([unit, state]) => <ServiceTile key={unit} unit={unit} state={state} />)}
          </div>
          {failedServices > 0 && <div className="mt-3 text-xs text-danger flex items-center gap-2"><AlertTriangle size={14} /> {number(failedServices)} سرویس دارای خطاست</div>}
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card title="وضعیت ارتباط Traccar" subtitle="وضعیت ارتباطی گزارش‌شده توسط خود Traccar">
          <div className="flex items-center gap-2 mb-4">
            {traccar.status === 'connected' ? <Wifi size={18} className="text-success" /> : <WifiOff size={18} className="text-warning" />}
            <span className="text-sm font-medium text-text-primary">{traccar.status === 'connected' ? 'API ترکار در دسترس است' : 'وضعیت API ترکار نامشخص است'}</span>
            <spacer />
            <Badge variant={traccar.status === 'connected' ? 'success' : 'warning'}>{traccar.status === 'connected' ? 'متصل' : 'نامشخص'}</Badge>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="ثبت‌شده در Traccar" value={number(traccar.registered)} />
            <Metric label="آنلاین" value={number(traccar.online)} />
            <Metric label="آفلاین" value={number(traccar.offline)} />
            <Metric label="وضعیت نامشخص" value={number(traccar.unknown)} />
          </div>
          <p className="text-[10px] text-text-muted mt-3">آفلاین بودن ارتباطی با وضعیت مدیریتی دستگاه در انبار یا چرخه فروش ندارد.</p>
        </Card>

        <Card title="موجودی ناوگان و دستگاه‌ها" subtitle={`${number(fleet.vehicles)} خودرو در سامانه ثبت شده`}>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <Metric label="کل دستگاه‌ها" value={number(fleet.devices)} />
            <Metric label="دارای خودرو" value={number(fleet.with_vehicle)} />
            <Metric label="انبار" value={number(fleet.warehouse)} />
            <Metric label="نصب‌شده / فعال مدیریتی" value={number(fleet.installed)} />
          </div>
          <div className="space-y-2">
            <ProgressRow label="دارای خودرو" value={fleet.with_vehicle || 0} total={fleet.devices || 0} color="bg-success" />
            <ProgressRow label="بدون خودرو" value={fleet.without_vehicle || 0} total={fleet.devices || 0} color="bg-warning" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant="danger">خراب: {number(fleet.faulty)}</Badge>
            <Badge variant="warning">گمشده: {number(fleet.lost)}</Badge>
            <Badge variant="warning">سرقت‌شده: {number(fleet.stolen)}</Badge>
          </div>
        </Card>

        <Card title="مشتریان و کاربران" subtitle="تفکیک حساب‌های سازمانی و شخصی">
          <div className="grid grid-cols-2 gap-3 mb-4">
            <Metric label="شرکت فعال" value={number(customers.active_organizations)} />
            <Metric label="شرکت تعلیق‌شده" value={number(customers.suspended_organizations)} />
            <Metric label="شعبه‌ها" value={number(customers.branches)} />
            <Metric label="مشتری شخصی فعال" value={number(customers.active_personal_customers)} />
          </div>
          <div className="flex items-center justify-between text-xs text-text-secondary border-t border-border-base pt-3">
            <span>کاربران فعال / غیرفعال</span>
            <span className="font-mono text-text-primary">{number(customers.active_users)} / {number(customers.inactive_users)}</span>
          </div>
          <div className="flex items-center justify-between text-xs text-text-secondary mt-2">
            <span>مشتریان جدید در ۳۰ روز</span>
            <span className="font-mono text-success">{number(customers.new_customers_30d)}</span>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Card title="وضعیت قراردادها" subtitle="وضعیت محاسبه‌شده با توجه به تاریخ و وضعیت ثبت‌شده">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
            <Metric label="کل قراردادها" value={number(contracts.total)} />
            <Metric label="فعال" value={number(contracts.active)} />
            <Metric label="در انتظار شروع" value={number(contracts.pending)} />
            <Metric label="منقضی" value={number(contracts.expired)} />
            <Metric label="تعلیق‌شده" value={number(contracts.suspended)} />
            <Metric label="لغوشده" value={number(contracts.cancelled)} />
          </div>
          <div className="rounded-field bg-warning/10 border border-warning/20 p-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-warning"><Clock3 size={17} /><span className="text-sm">قراردادهای فعال با سررسید ۳۰ روز آینده</span></div>
            <span className="text-lg font-bold font-mono text-warning">{number(contracts.expiring_soon)}</span>
          </div>
          <div className="flex flex-wrap gap-2 mt-3 text-xs">
            <Badge variant="info">سازمانی: {number(contracts.organization)}</Badge>
            <Badge variant="neutral">شخصی: {number(contracts.personal)}</Badge>
            <Badge variant="success">دستگاه‌های متصل به قرارداد فعال: {number(contracts.active_devices)}</Badge>
          </div>
        </Card>

        <Card title="وضعیت مدیریتی دستگاه‌ها" subtitle="طبقه‌بندی موجودی مستقل از آنلاین یا آفلاین بودن">
          <div className="space-y-3">
            {Object.entries(fleet.devices_by_management_status || {}).map(([key, value]) => (
              <ProgressRow key={key} label={managementLabels[key] || key} value={value} total={fleet.devices || 0}
                color={key === 'faulty' || key === 'lost' || key === 'stolen' ? 'bg-danger' : key === 'warehouse' ? 'bg-warning' : 'bg-brand-500'} />
            ))}
            {!Object.keys(fleet.devices_by_management_status || {}).length && <p className="text-sm text-text-muted">هنوز دستگاهی ثبت نشده است.</p>}
          </div>
        </Card>
      </div>

      <Card title="دسترسی سریع به مدیریت" subtitle="ورود به صفحات جزئیات برای پیگیری و انجام عملیات">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Link to="/panel/companies" className="rounded-field border border-border-base p-3 hover:bg-bg-hover transition-colors">
            <Building2 size={18} className="text-brand-400 mb-2" /><div className="text-sm font-medium text-text-primary">مدیریت شرکت‌ها</div><div className="text-[10px] text-text-muted mt-1">اطلاعات و وضعیت مشتریان</div>
          </Link>
          <Link to="/panel/users" className="rounded-field border border-border-base p-3 hover:bg-bg-hover transition-colors">
            <Users size={18} className="text-info mb-2" /><div className="text-sm font-medium text-text-primary">مدیریت کاربران</div><div className="text-[10px] text-text-muted mt-1">حساب‌های سازمانی و شخصی</div>
          </Link>
          <Link to="/panel/devices" className="rounded-field border border-border-base p-3 hover:bg-bg-hover transition-colors">
            <Cpu size={18} className="text-success mb-2" /><div className="text-sm font-medium text-text-primary">مدیریت دستگاه‌ها</div><div className="text-[10px] text-text-muted mt-1">موجودی و وضعیت دستگاه‌ها</div>
          </Link>
          <Link to="/panel/subscriptions" className="rounded-field border border-border-base p-3 hover:bg-bg-hover transition-colors">
            <Activity size={18} className="text-warning mb-2" /><div className="text-sm font-medium text-text-primary">مدیریت قراردادها</div><div className="text-[10px] text-text-muted mt-1">تمدید و سررسید قراردادها</div>
          </Link>
        </div>
      </Card>
      <div className="text-[10px] text-text-muted text-left">آخرین دریافت: {data?.generated_at ? new Date(data.generated_at).toLocaleString('fa-IR') : '—'}</div>
    </div>
  );
}
