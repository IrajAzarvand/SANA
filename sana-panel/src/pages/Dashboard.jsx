import { useCallback } from 'react';
import {
  Truck, Navigation, WifiOff, AlertTriangle, Building2, Cpu, Car, Route, Bell, Users,
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

// داده‌ی Mock نمودار (تا وقتی Ingestion Server راه بیفته)
import { movementData, recentAlerts, recentTrips, movingVehicles } from '../data/mockData';

export default function Dashboard() {
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
  const deviceStatus = stats?.devices_by_status || {};
  const isDevicesActive = (deviceStatus.active || 0) + (deviceStatus.installed || 0);
  const isDevicesOffline = (deviceStatus.disconnected || 0) + (deviceStatus.lost || 0) + (deviceStatus.stolen || 0);
  const isDevicesFaulty = deviceStatus.faulty || 0;

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
          <StatCard title="دستگاه‌های فعال" value={isDevicesActive}     icon={Cpu}           color="success" />
          <StatCard title="دستگاه‌های آفلاین" value={isDevicesOffline}  icon={WifiOff}       color="muted" />
          <StatCard title="دستگاه‌های خراب"  value={isDevicesFaulty}    icon={AlertTriangle} color="danger" />
        </div>
      )}

      {/* KPIهای مشتری شخصی */}
      {isPersonal && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="خودروهای من"     value={stats.vehicles || 0}   icon={Car}    color="brand" />
          <StatCard title="دستگاه‌های من"    value={stats.devices || 0}    icon={Cpu}    color="info" />
          <StatCard title="دستگاه‌های فعال"  value={isDevicesActive}       icon={Cpu}    color="success" />
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