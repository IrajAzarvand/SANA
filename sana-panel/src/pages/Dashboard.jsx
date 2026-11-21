import { useCallback } from 'react';
import { formatJalaliDate } from '../utils/dateUtils';
import {
  Truck, Navigation, WifiOff, AlertTriangle, Building2, Cpu, Car, Bell, Users,
  Activity, Radio, Signal, FileText, ArrowUpLeft,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import StatCard from '../components/StatCard';
import Card from '../components/Card';
import Badge from '../components/Badge';
import MovementChart from '../components/MovementChart';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { useAuth } from '../context/AuthContext';
import { dashboardAPI } from '../api/services/dashboard';
import { useApi } from '../hooks/useApi';
import AdminDashboard from './AdminDashboard';

// داده‌ی Mock نمودار (تا وقتی Ingestion Server راه بیفته)
import { movementData, recentAlerts, recentTrips, movingVehicles } from '../data/mockData';

function CustomerDashboard() {
  const { isSiteAdmin, isPersonal, isBranchManager, user } = useAuth();

  const fetchStats = useCallback(async () => {
    return await dashboardAPI.getStats();
  }, []);

  const { data: stats, loading, error, refetch } = useApi(fetchStats, []);

  const severityMap = {
    danger:  { variant: 'danger',  icon: '⚠️' },
    warning: { variant: 'warning', icon: '⚡' },
    info:    { variant: 'info',    icon: 'ℹ️' },
  };

  const getTitle = () => {
    if (isSiteAdmin) return 'داشبورد مدیریت سامانه';
    if (isPersonal) return 'داشبورد شخصی';
    if (isBranchManager) return `داشبورد شعبه ${user?.branch_name || ''}`;
    return 'داشبورد سازمان';
  };

  const getSubtitle = () => {
    if (isSiteAdmin) return 'نمای کلی سامانه سانا — امروز';
    if (isPersonal) return 'خلاصه وضعیت خودروهای شما — امروز';
    if (isBranchManager) return 'خلاصه وضعیت ناوگان شعبه — امروز';
    return 'خلاصه وضعیت ناوگان — امروز';
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title={getTitle()} subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title={getTitle()} subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  // محاسبه آمار
  const gpsStatus = stats?.gps_status;
  const gpsAvailable = gpsStatus?.available === true;
  const isDevicesActive = gpsAvailable ? Number(gpsStatus.online || 0) : '—';
  const isDevicesOffline = gpsAvailable ? Number(gpsStatus.offline || 0) : '—';

  if (isPersonal) {
    const gpsTotal = Number(gpsStatus?.total ?? stats?.devices ?? 0);
    const gpsValue = (key) => gpsAvailable ? Number(gpsStatus?.[key] ?? 0) : '—';
    const onlineCount = gpsAvailable ? Number(gpsStatus?.online ?? 0) : 0;
    const offlineCount = gpsAvailable ? Number(gpsStatus?.offline ?? 0) : 0;
    const onlinePercent = gpsAvailable && gpsTotal > 0
      ? Math.min(100, Math.round((onlineCount / gpsTotal) * 100))
      : 0;
    const daysLeft = stats?.current_subscription?.days_until_expiry;
    const subscriptionExpiring = stats?.current_subscription?.is_expiring_soon;

    const quickLinks = [
      {
        to: '/panel/map',
        icon: Navigation,
        title: 'نقشه زنده',
        description: 'مشاهده موقعیت خودروها',
        tone: 'text-brand-400 bg-brand-500/10',
      },
      {
        to: '/panel/devices',
        icon: Cpu,
        title: 'دستگاه‌های من',
        description: 'مشاهده مشخصات و وضعیت',
        tone: 'text-info bg-info/10',
      },
      {
        to: '/panel/reports/trips',
        icon: Truck,
        title: 'گزارش مسیرها',
        description: 'بررسی سفرها و مسیرها',
        tone: 'text-success bg-success/10',
      },
    ];

    return (
      <div className="space-y-6 pb-8">
        <PageHeader
          title="داشبورد شخصی"
          subtitle="نمای یکپارچه وضعیت خودروها، دستگاه‌ها و خدمات شما"
        />

        <section className="relative isolate overflow-hidden rounded-3xl border border-border-base bg-bg-elevated">
          <div className="pointer-events-none absolute -left-16 -top-24 h-64 w-64 rounded-full bg-brand-500/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-28 right-1/3 h-56 w-56 rounded-full bg-info/10 blur-3xl" />
          <div className="relative flex flex-col gap-6 p-5 sm:p-7 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl">
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-brand-500/20 bg-brand-500/10 px-3 py-1.5 text-xs font-medium text-brand-300">
                <Activity size={14} />
                مرکز کنترل خودروی شما
              </div>
              <h2 className="text-xl font-bold leading-9 text-text-primary sm:text-2xl">
                همه‌چیز درباره خودروی شما، یک‌جا
              </h2>
              <p className="mt-2 max-w-xl text-sm leading-7 text-text-secondary">
                وضعیت اتصال دستگاه‌ها را بررسی کنید، موقعیت خودرو را ببینید و به گزارش مسیرها و اطلاعات قرارداد دسترسی داشته باشید.
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-4 rounded-2xl border border-border-base bg-bg-base/80 px-5 py-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-500/10 text-brand-400">
                <Car size={25} />
              </div>
              <div>
                <div className="text-xs text-text-muted">خودروهای ثبت‌شده</div>
                <div className="mt-1 text-3xl font-bold tabular-nums text-text-primary">
                  {Number(stats?.vehicles || 0).toLocaleString('fa-IR')}
                </div>
              </div>
              <div className="mx-1 h-10 w-px bg-border-base" />
              <div>
                <div className="text-xs text-text-muted">دستگاه‌های تحت دسترسی</div>
                <div className="mt-1 text-3xl font-bold tabular-nums text-text-primary">
                  {gpsTotal.toLocaleString('fa-IR')}
                </div>
              </div>
            </div>
          </div>
        </section>

        {subscriptionExpiring && (
          <section className="flex items-start gap-3 rounded-2xl border border-warning/30 bg-warning/10 p-4">
            <AlertTriangle size={20} className="mt-0.5 shrink-0 text-warning" />
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-warning">زمان تمدید قرارداد نزدیک است</h3>
              <p className="mt-1 text-xs leading-6 text-text-secondary">
                قرارداد شما {daysLeft} روز دیگر به پایان می‌رسد. برای پیگیری تمدید با پشتیبانی سانا در ارتباط باشید.
              </p>
            </div>
          </section>
        )}

        <section>
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 className="text-base font-bold text-text-primary">وضعیت زنده دستگاه‌ها</h2>
              <p className="mt-1 text-xs text-text-muted">اطلاعات اتصال و حرکت دریافت‌شده از سامانه GPS</p>
            </div>
            {gpsAvailable && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-success/20 bg-success/10 px-2.5 py-1 text-[11px] font-medium text-success">
                <span className="h-1.5 w-1.5 rounded-full bg-success" />
                اطلاعات به‌روز
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { key: 'online', title: 'آنلاین', detail: 'دارای ارتباط با سرور', icon: Radio, tone: 'success' },
              { key: 'offline', title: 'آفلاین', detail: 'بدون ارتباط اخیر', icon: WifiOff, tone: 'muted' },
              { key: 'moving', title: 'در حال حرکت', detail: 'از دستگاه‌های آنلاین', icon: Navigation, tone: 'brand' },
              { key: 'stopped', title: 'متوقف', detail: 'از دستگاه‌های آنلاین', icon: Car, tone: 'warning' },
            ].map((item) => {
              const Icon = item.icon;
              const tones = {
                success: 'bg-success/10 text-success border-success/20',
                muted: 'bg-bg-hover text-text-secondary border-border-base',
                brand: 'bg-brand-500/10 text-brand-400 border-brand-500/20',
                warning: 'bg-warning/10 text-warning border-warning/20',
              };
              return (
                <div key={item.key} className="group rounded-2xl border border-border-base bg-bg-elevated p-4 transition-colors hover:border-border-strong">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-text-secondary">{item.title}</span>
                    <span className={`flex h-10 w-10 items-center justify-center rounded-xl border ${tones[item.tone]}`}>
                      <Icon size={19} />
                    </span>
                  </div>
                  <div className="mt-3 text-3xl font-bold tabular-nums tracking-tight text-text-primary">
                    {gpsValue(item.key) === '—' ? '—' : Number(gpsValue(item.key)).toLocaleString('fa-IR')}
                  </div>
                  <p className="mt-1 text-[11px] text-text-muted">{item.detail}</p>
                </div>
              );
            })}
          </div>
          {!gpsAvailable && (
            <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-warning/25 bg-warning/5 px-4 py-3 text-xs leading-6 text-text-secondary">
              <AlertTriangle size={16} className="mt-1 shrink-0 text-warning" />
              <span>
                در حال حاضر دریافت وضعیت زنده GPS ممکن نیست. به همین دلیل وضعیت آنلاین و آفلاین نمایش داده نمی‌شود؛ این موضوع به معنی قطع بودن دستگاه‌ها نیست.
              </span>
            </div>
          )}
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-5">
          <div className="rounded-2xl border border-border-base bg-bg-elevated p-5 xl:col-span-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-text-primary">کیفیت اتصال دستگاه‌ها</h2>
                <p className="mt-1 text-xs text-text-muted">نمای کلی دسترسی دستگاه‌ها به شبکه GPS</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/10 text-brand-400">
                <Signal size={20} />
              </div>
            </div>
            {gpsAvailable ? (
              gpsTotal > 0 ? (
                <>
                  <div className="mt-6 flex items-end justify-between gap-3">
                    <div>
                      <div className="text-3xl font-bold tabular-nums text-text-primary">{onlinePercent.toLocaleString('fa-IR')}٪</div>
                      <div className="mt-1 text-xs text-text-muted">دستگاه‌های آنلاین</div>
                    </div>
                    <div className="text-left text-xs leading-6 text-text-secondary">
                      <div><span className="font-semibold text-success">{onlineCount.toLocaleString('fa-IR')}</span> آنلاین</div>
                      <div><span className="font-semibold text-text-primary">{offlineCount.toLocaleString('fa-IR')}</span> آفلاین</div>
                    </div>
                  </div>
                  <div className="mt-4 h-3 overflow-hidden rounded-full bg-bg-hover">
                    <div
                      className="h-full rounded-full bg-gradient-to-l from-success to-brand-400 transition-all"
                      style={{ width: `${onlinePercent}%` }}
                    />
                  </div>
                  <p className="mt-3 text-[11px] leading-5 text-text-muted">
                    مبنای محاسبه، وضعیت ارتباط و آخرین زمان دریافت‌شده در سرور است؛ نه وضعیت انبار یا چرخه مدیریتی دستگاه.
                  </p>
                </>
              ) : (
                <div className="mt-6 rounded-xl bg-bg-base px-4 py-6 text-center">
                  <Cpu size={24} className="mx-auto text-text-muted" />
                  <p className="mt-2 text-sm text-text-secondary">در حال حاضر دستگاهی برای این حساب ثبت نشده است.</p>
                </div>
              )
            ) : (
              <div className="mt-6 rounded-xl bg-bg-base px-4 py-6 text-center">
                <WifiOff size={24} className="mx-auto text-text-muted" />
                <p className="mt-2 text-sm text-text-secondary">اطلاعات اتصال فعلاً در دسترس نیست.</p>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-border-base bg-bg-elevated p-5 xl:col-span-2">
            <h2 className="text-base font-bold text-text-primary">دسترسی سریع</h2>
            <p className="mt-1 text-xs text-text-muted">بخش موردنظر را انتخاب کنید</p>
            <div className="mt-4 space-y-2">
              {quickLinks.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className="group flex items-center gap-3 rounded-xl border border-border-base bg-bg-base p-3 transition-all hover:border-border-strong hover:bg-bg-hover"
                  >
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${item.tone}`}>
                      <Icon size={19} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold text-text-primary">{item.title}</span>
                      <span className="mt-0.5 block text-[11px] text-text-muted">{item.description}</span>
                    </span>
                    <span className="text-text-muted transition-transform group-hover:-translate-x-1" aria-hidden="true">←</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>

        <section className="overflow-hidden rounded-2xl border border-border-base bg-bg-elevated">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-base px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/10 text-brand-400">
                <FileText size={20} />
              </span>
              <div>
                <h2 className="text-base font-bold text-text-primary">قرارداد و اشتراک</h2>
                <p className="mt-1 text-xs text-text-muted">اطلاعات اعتبار خدمات شما</p>
              </div>
            </div>
            {stats?.current_subscription && (
              <Badge variant={subscriptionExpiring ? 'warning' : 'success'}>
                {subscriptionExpiring ? 'نزدیک به پایان' : 'فعال'}
              </Badge>
            )}
          </div>
          {stats?.current_subscription ? (
            <div className="grid grid-cols-1 gap-5 p-5 sm:grid-cols-3 sm:items-center">
              <div>
                <div className="text-xs text-text-muted">شماره قرارداد</div>
                <Link
                  to={`/panel/subscriptions/${stats.current_subscription.id}`}
                  className="mt-1 inline-flex items-center gap-2 font-mono text-base font-bold text-brand-400 transition-colors hover:text-brand-300 hover:underline underline-offset-4"
                  aria-label={`مشاهده جزئیات قرارداد ${stats.current_subscription.contract_number}`}
                >
                  {stats.current_subscription.contract_number}
                  <ArrowUpLeft size={14} />
                </Link>
              </div>
              <div>
                <div className="text-xs text-text-muted">تاریخ پایان اعتبار</div>
                <div className="mt-1 text-sm font-semibold text-text-primary">
                  {stats.current_subscription.end_date ? formatJalaliDate(stats.current_subscription.end_date) : '—'}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-muted">زمان باقی‌مانده</div>
                <div className={`mt-1 text-sm font-semibold ${subscriptionExpiring ? 'text-warning' : 'text-text-primary'}`}>
                  {daysLeft == null ? '—' : daysLeft < 0 ? 'پایان‌یافته' : daysLeft === 0 ? 'آخرین روز اعتبار' : `${Number(daysLeft).toLocaleString('fa-IR')} روز`}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-5 text-sm text-text-secondary">
              در حال حاضر قرارداد فعال برای این حساب ثبت نشده است.
            </div>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader title={getTitle()} subtitle={getSubtitle()} />
      {/* هشدار قرارداد نزدیک به انقضا — فقط برای کاربران سازمانی و شخصی */}
      {!isSiteAdmin && stats?.current_subscription?.is_expiring_soon && (
        <div className="bg-warning/10 border border-warning/30 rounded-card p-4 flex items-start gap-3">
          <AlertTriangle size={20} className="text-warning flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-warning mb-1">
              قرارداد شما به‌زودی منقضی می‌شود
            </h4>
            <p className="text-xs text-text-secondary leading-relaxed">
              قرارداد
              <span className="font-mono mx-1">{stats.current_subscription.contract_number}</span>
              تا
              <span className="font-bold text-warning mx-1">
                {stats.current_subscription.days_until_expiry} روز دیگر
              </span>
              منقضی می‌شود. لطفاً برای تمدید با پشتیبانی سانا تماس بگیرید.
            </p>
          </div>
        </div>
      )}

      {/* KPIهای ادمین کل */}
      {isSiteAdmin && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="کل شرکت‌ها"
            value={stats.companies || 0}
            icon={Building2}
            color="brand"
          />
          <StatCard
            title="کل دستگاه‌ها"
            value={stats.devices || 0}
            icon={Cpu}
            color="info"
          />
          <StatCard
            title="کل کاربران"
            value={stats.users || 0}
            icon={Users}
            color="success"
          />
          <StatCard
            title="نزدیک به انقضا"
            value={stats.subscriptions_expiring_soon || 0}
            icon={AlertTriangle}
            color={stats.subscriptions_expiring_soon > 0 ? 'warning' : 'muted'}
          />
        </div>
      )}

      {/* KPIهای مدیر شرکت / شعبه */}
      {!isSiteAdmin && !isPersonal && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="خودروها"        value={stats.vehicles || 0}  icon={Truck}         color="brand" />
          <StatCard title="دستگاه‌های آنلاین" value={isDevicesActive} icon={Cpu} color="success" />
          <StatCard title="دستگاه‌های آفلاین" value={isDevicesOffline} icon={WifiOff} color="muted" />
          <StatCard title="کل دستگاه‌ها" value={stats.devices || 0} icon={Activity} color="info" />
        </div>
      )}

      {/* KPIهای مشتری شخصی */}
      {isPersonal && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="خودروهای من"     value={stats.vehicles || 0}   icon={Car}    color="brand" />
          <StatCard title="دستگاه‌های من"    value={stats.devices || 0}    icon={Cpu}    color="info" />
          <StatCard title="دستگاه‌های آنلاین" value={isDevicesActive} icon={Cpu} color="success" />
          <StatCard title="هشدارهای امروز"  value={3}                       icon={Bell}   color="warning" />
        </div>
      )}

      {/* نمودار */}
      {!isPersonal && (
        <Card
          title="حرکت خودروها در ۲۴ ساعت گذشته"
          subtitle="تعداد خودروها به تفکیک وضعیت (داده‌ی نمونه تا فعال‌سازی Ingestion)"
          action={
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-brand-500"></span>
                <span className="text-text-secondary">در حال حرکت</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-warning"></span>
                <span className="text-text-secondary">متوقف</span>
              </div>
            </div>
          }
        >
          <MovementChart data={movementData} />
        </Card>
      )}

      {isPersonal && (
        <Card title="مسافت خودروهای من در ۲۴ ساعت گذشته" subtitle="کیلومتر طي‌شده (داده‌ی نمونه)">
          <MovementChart data={movementData} />
        </Card>
      )}

      {/* آخرین هشدارها + خودروهای در حال حرکت */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <Card
          title={isPersonal ? 'آخرین هشدارهای من' : 'آخرین هشدارها'}
          subtitle="۵ هشدار اخیر (داده‌ی نمونه)"
          className="lg:col-span-2"
          action={
            <Link to="/panel/alerts" className="text-xs text-brand-400 hover:text-brand-500 transition-colors">
              مشاهده همه ←
            </Link>
          }
        >
          <div className="space-y-3">
            {recentAlerts.slice(0, isPersonal ? 3 : 5).map((alert) => {
              const sev = severityMap[alert.severity] || severityMap.info;
              return (
                <div
                  key={alert.id}
                  className="flex items-start gap-3 p-3 rounded-field bg-bg-base border border-border-base hover:border-border-strong transition-colors"
                >
                  <div className={`w-9 h-9 rounded-field flex items-center justify-center text-base flex-shrink-0
                    ${alert.severity === 'danger'  ? 'bg-danger/10'  : ''}
                    ${alert.severity === 'warning' ? 'bg-warning/10' : ''}
                    ${alert.severity === 'info'    ? 'bg-info/10'    : ''}
                  `}>
                    {sev.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-text-primary font-mono">{alert.vehicle}</span>
                      <Badge variant={sev.variant}>
                        {alert.severity === 'danger'  ? 'بحرانی' : ''}
                        {alert.severity === 'warning' ? 'هشدار'  : ''}
                        {alert.severity === 'info'    ? 'اطلاع'  : ''}
                      </Badge>
                    </div>
                    <p className="text-xs text-text-secondary truncate">{alert.message}</p>
                    <div className="flex items-center gap-3 mt-1.5 text-[10px] text-text-muted">
                      <span>{alert.driver}</span>
                      <span>•</span>
                      <span>{alert.time}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card
          title={isPersonal ? 'خودروهای من' : 'خودروهای در حال حرکت'}
          subtitle={`${isPersonal ? 2 : movingVehicles.length} خودرو (داده‌ی نمونه)`}
          action={
            <Link to="/panel/map" className="text-xs text-brand-400 hover:text-brand-500 transition-colors">
              نقشه ←
            </Link>
          }
        >
          <div className="space-y-3">
            {(isPersonal ? movingVehicles.slice(0, 2) : movingVehicles).map((v) => (
              <div
                key={v.id}
                className="flex items-center gap-3 p-3 rounded-field bg-bg-base border border-border-base"
              >
                <div className={`w-9 h-9 rounded-field flex items-center justify-center flex-shrink-0
                  ${v.status === 'moving' ? 'bg-brand-900/40' : 'bg-warning/10'}`}>
                  <Navigation size={16} className={v.status === 'moving' ? 'text-brand-400' : 'text-warning'} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-text-primary font-mono">{v.plate}</div>
                  <div className="text-[10px] text-text-muted truncate">{v.driver}</div>
                </div>
                <div className="text-left">
                  <div className={`text-sm font-bold font-mono ${v.status === 'moving' ? 'text-brand-400' : 'text-warning'}`}>
                    {v.speed}
                  </div>
                  <div className="text-[10px] text-text-muted">km/h</div>
                </div>
              </div>
            ))}
          </div>
        </Card>

      </div>

      {/* آخرین سفرها */}
      {!isPersonal && (
        
        <Card
          title="آخرین سفرها"
          subtitle="۵ سفر اخیر (داده‌ی نمونه)"
          action={
            <Link to="/panel/reports" className="text-xs text-brand-400 hover:text-brand-500 transition-colors">
              گزارش کامل ←
            </Link>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">شناسه</th>
                  <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">خودرو</th>
                  <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">راننده</th>
                  <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">شروع</th>
                  <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">پایان</th>
                  <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">مسافت</th>
                  <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">وضعیت</th>
                </tr>
              </thead>
              <tbody>
                {recentTrips.map((trip) => (
                  <tr key={trip.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                    <td className="py-3 px-3 text-text-secondary font-mono text-xs">#{trip.id}</td>
                    <td className="py-3 px-3 text-text-primary font-mono text-xs">{trip.vehicle}</td>
                    <td className="py-3 px-3 text-text-secondary text-xs">{trip.driver}</td>
                    <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.start}</td>
                    <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.end}</td>
                    <td className="py-3 px-3 text-text-primary font-mono text-xs">{trip.distance} km</td>
                    <td className="py-3 px-3">
                      <Badge variant={trip.status === 'active' ? 'success' : 'neutral'}>
                        {trip.status === 'active' ? 'در جریان' : 'تکمیل شده'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

    </div>
  );
}

export default function Dashboard() {
  const { isSiteAdmin } = useAuth();
  return isSiteAdmin ? <AdminDashboard /> : <CustomerDashboard />;
}
