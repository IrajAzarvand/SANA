import { useState, useMemo, useEffect, useCallback } from 'react';
import { Search, AlertTriangle, Check, CheckCheck, Eye, Bell, Trash2, RefreshCw } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Input from '../components/Input';
import Select from '../components/Select';
import Tabs from '../components/Tabs';
import StatCard from '../components/StatCard';
import EmptyState from '../components/EmptyState';
import {
  alerts as initialAlerts,
  alertTypes,
  severityMap,
  statusMap,
} from '../data/alertsData';
import { branches } from '../data/vehiclesData';
import { useAuth } from '../context/AuthContext';
import { alertsAPI } from '../api/services/fleet';
import { formatJalaliDateTime } from '../utils/dateUtils';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Alerts() {
  const { isPersonal } = useAuth();
  return isPersonal ? <PersonalAlerts /> : <LegacyAlerts />;
}

function LegacyAlerts() {
  const [search, setSearch] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [activeTab, setActiveTab] = useState('all');

  const { can, isPersonal, isBranchManager, user } = useAuth();

  // فیلتر بر اساس دامنه دید کاربر
  const visibleAlerts = useMemo(() => {
    // مدیر شعبه: فقط هشدارهای شعبه خودش
    if (isBranchManager && user?.branch) {
      const branchMap = {
        'تهران': 'tehran',
        'اصفهان': 'isfahan',
        'شیراز': 'shiraz',
        'تبریز': 'tabriz',
      };
      const bv = branchMap[user.branch.name] || '';
      return initialAlerts.filter((a) => a.branch === bv);
    }

    // مشتری شخصی: فقط هشدارهای خودروهای خودش (mock: فقط 2 خودرو)
    if (isPersonal) {
      const personalVehicles = ['۱۲ب۳۴۵۶۷', '۴۵ج۶۷۸۹۰'];
      return initialAlerts.filter((a) => personalVehicles.includes(a.vehicle));
    }

    return initialAlerts;
  }, [isPersonal, isBranchManager, user]);

  const counts = useMemo(() => ({
    all:          visibleAlerts.length,
    active:       visibleAlerts.filter(a => a.status === 'active').length,
    acknowledged: visibleAlerts.filter(a => a.status === 'acknowledged').length,
    resolved:     visibleAlerts.filter(a => a.status === 'resolved').length,
  }), [visibleAlerts]);

  const filtered = useMemo(() => {
    return visibleAlerts.filter((a) => {
      if (activeTab !== 'all' && a.status !== activeTab) return false;
      if (search && !a.vehicle.includes(search) && !a.message.includes(search) && !(a.driver && a.driver.includes(search))) return false;
      if (filterBranch && a.branch !== filterBranch) return false;
      if (filterSeverity && a.severity !== filterSeverity) return false;
      return true;
    });
  }, [visibleAlerts, search, filterBranch, filterSeverity, activeTab]);

  const severityOptions = Object.entries(severityMap).map(([value, { label }]) => ({
    value, label,
  }));

  return (
    <div className="space-y-6">

      <PageHeader
        title="هشدارها"
        subtitle={
          isPersonal
            ? 'هشدارهای خودروهای من'
            : isBranchManager
              ? `هشدارهای شعبه ${user?.branch?.name || ''}`
              : 'مدیریت هشدارهای فعال و تاریخی ناوگان'
        }
      />

      {/* آمار */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="کل هشدارها"    value={counts.all}          icon={Bell}          color="brand"  />
        <StatCard title="فعال"          value={counts.active}       icon={AlertTriangle} color="danger" />
        <StatCard title="بررسی‌شده"      value={counts.acknowledged} icon={Eye}           color="warning"/>
        <StatCard title="حل‌شده"         value={counts.resolved}     icon={CheckCheck}    color="success"/>
      </div>

      {/* Tabs + فیلترها */}
      <Card>
        <Tabs
          activeTab={activeTab}
          onChange={setActiveTab}
          tabs={[
            { value: 'all',          label: 'همه',       count: counts.all },
            { value: 'active',       label: 'فعال',      count: counts.active },
            { value: 'acknowledged', label: 'بررسی‌شده',  count: counts.acknowledged },
            { value: 'resolved',     label: 'حل‌شده',     count: counts.resolved },
          ]}
        />
        <div className={`grid grid-cols-1 gap-4 mt-5 ${!isPersonal && !isBranchManager ? 'md:grid-cols-2' : ''}`}>
          <Input
            icon={Search}
            placeholder="جستجوی پلاک، راننده یا متن هشدار..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {!isPersonal && !isBranchManager && (
            <div className="grid grid-cols-2 gap-4">
              <Select
                placeholder="همه شعبه‌ها"
                value={filterBranch}
                onChange={(e) => setFilterBranch(e.target.value)}
                options={branches}
              />
              <Select
                placeholder="همه شدت‌ها"
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value)}
                options={severityOptions}
              />
            </div>
          )}
          {(isPersonal || isBranchManager) && (
            <Select
              placeholder="همه شدت‌ها"
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              options={severityOptions}
            />
          )}
        </div>
      </Card>

      {/* لیست هشدارها */}
      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon={AlertTriangle}
            title="هشداری یافت نشد"
            description="هیچ هشداری با فیلترهای فعلی مطابقت ندارد."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((alert) => {
            const type = alertTypes[alert.type];
            const sev = severityMap[alert.severity];
            const st = statusMap[alert.status];
            const branchLabel = branches.find((b) => b.value === alert.branch)?.label || '—';

            return (
              <div
                key={alert.id}
                className={`bg-bg-elevated border border-border-base rounded-card overflow-hidden
                           ${alert.severity === 'critical' && alert.status === 'active' ? 'border-r-4 border-r-danger' : ''}
                           ${alert.severity === 'warning' && alert.status !== 'resolved' ? 'border-r-4 border-r-warning' : ''}
                `}
              >
                <div className="p-4 flex items-start gap-4">

                  <div className={`w-11 h-11 rounded-field flex items-center justify-center text-lg flex-shrink-0
                    ${alert.severity === 'critical' ? 'bg-danger/10' : ''}
                    ${alert.severity === 'warning'  ? 'bg-warning/10' : ''}
                    ${alert.severity === 'info'     ? 'bg-info/10' : ''}
                  `}>
                    {type.icon}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center flex-wrap gap-2 mb-1">
                      <h4 className="text-sm font-semibold text-text-primary">{type.label}</h4>
                      <Badge variant={sev.variant}>{sev.label}</Badge>
                      <Badge variant={st.variant}>{st.label}</Badge>
                    </div>

                    <p className="text-sm text-text-secondary mb-2">{alert.message}</p>

                    {alert.detail && (
                      <p className="text-xs text-text-muted mb-3">{alert.detail}</p>
                    )}

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted">
                      <span className="font-mono">{alert.vehicle}</span>
                      {alert.driver && alert.driver !== '—' && <span>{alert.driver}</span>}
                      {!isPersonal && !isBranchManager && (
                        <>
                          <span>•</span>
                          <span>{branchLabel}</span>
                        </>
                      )}
                      <span>•</span>
                      <span>{alert.relativeTime}</span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-3 flex-shrink-0">
                    <span className="text-[10px] text-text-muted font-mono whitespace-nowrap hidden md:block">
                      {alert.time}
                    </span>

                    {/* اکشن‌ها — فقط برای کسانی که edit دارن */}
                    {can('edit') && (
                      <div className="flex items-center gap-1">
                        {alert.status === 'active' && (
                          <>
                            <button
                              title="بررسی شد"
                              className="p-1.5 rounded-field text-text-muted hover:bg-warning/10 hover:text-warning transition-colors"
                            >
                              <Eye size={15} />
                            </button>
                            <button
                              title="حل شد"
                              className="p-1.5 rounded-field text-text-muted hover:bg-success/10 hover:text-success transition-colors"
                            >
                              <Check size={15} />
                            </button>
                          </>
                        )}
                        {alert.status === 'acknowledged' && (
                          <button
                            title="حل شد"
                            className="p-1.5 rounded-field text-text-muted hover:bg-success/10 hover:text-success transition-colors"
                          >
                            <Check size={15} />
                          </button>
                        )}
                        {alert.status === 'resolved' && (
                          <span className="p-1.5 text-success">
                            <CheckCheck size={15} />
                          </span>
                        )}
                        {can('delete') && (
                          <button
                            title="حذف"
                            className="p-1.5 rounded-field text-text-muted hover:bg-danger/10 hover:text-danger transition-colors"
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    )}

                    {/* اگه فقط مشاهده */}
                    {!can('edit') && (
                      <div className="flex items-center gap-1">
                        {alert.status === 'resolved' ? (
                          <span className="p-1.5 text-success">
                            <CheckCheck size={15} />
                          </span>
                        ) : (
                          <span className="p-1.5 text-text-muted">
                            <Eye size={15} />
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}

const personalEventTypes = {
  deviceOffline: { label: 'قطع ارتباط', icon: '📡', severity: 'warning', message: 'ارتباط دستگاه قطع شد' },
  deviceOnline: { label: 'اتصال مجدد', icon: '🟢', severity: 'info', message: 'ارتباط دستگاه برقرار شد' },
  alarm: { label: 'هشدار دستگاه', icon: '🆘', severity: 'critical', message: 'هشدار توسط دستگاه ثبت شد' },
  overspeed: { label: 'سرعت غیرمجاز', icon: '⚡', severity: 'critical', message: 'هشدار سرعت غیرمجاز ثبت شد' },
  geofenceEnter: { label: 'ورود به محدوده', icon: '📍', severity: 'warning', message: 'خودرو وارد محدوده شد' },
  geofenceExit: { label: 'خروج از محدوده', icon: '📍', severity: 'warning', message: 'خودرو از محدوده خارج شد' },
  ignitionOn: { label: 'روشن شدن خودرو', icon: '🔑', severity: 'info', message: 'سوئیچ خودرو روشن شد' },
  ignitionOff: { label: 'خاموش شدن خودرو', icon: '🔑', severity: 'info', message: 'سوئیچ خودرو خاموش شد' },
  deviceMoving: { label: 'شروع حرکت', icon: '🚗', severity: 'info', message: 'حرکت خودرو آغاز شد' },
  deviceStopped: { label: 'توقف خودرو', icon: '🛑', severity: 'info', message: 'خودرو متوقف شد' },
};

const alarmLabels = {
  sos: 'دکمه اضطراری',
  powerCut: 'قطع برق اصلی',
  lowBattery: 'باتری ضعیف',
  lowPower: 'ولتاژ پایین',
  tampering: 'دست‌کاری دستگاه',
  vibration: 'لرزش',
  accident: 'تصادف',
  tow: 'یدک‌کش شدن',
  jamming: 'اختلال سیگنال',
  door: 'باز شدن در',
  bonnet: 'باز شدن کاپوت',
  fuel: 'هشدار سوخت',
};

function getPersonalEventPresentation(alert) {
  const config = personalEventTypes[alert.type] || {
    label: 'رویداد دستگاه',
    icon: '🔔',
    severity: 'info',
    message: 'رویداد جدیدی توسط دستگاه ثبت شد',
  };
  const attributes = alert.attributes || {};
  const alarm = attributes.alarm;
  const alarmLabel = alarmLabels[alarm] || alarm;

  let message = config.message;
  if (alert.type === 'alarm' && alarmLabel) message = `هشدار دستگاه: ${alarmLabel}`;

  const details = [];
  if (attributes.geofence) details.push(`محدوده: ${attributes.geofence}`);
  if (attributes.speed !== undefined && attributes.speed !== null) {
    details.push(`سرعت: ${attributes.speed}`);
  }
  if (attributes.address) details.push(`موقعیت: ${attributes.address}`);
  if (attributes.result) details.push(`نتیجه: ${attributes.result}`);

  const status = alert.status === 'new' ? 'active' : alert.status;
  return {
    ...alert,
    message,
    detail: details.join(' • '),
    vehicle: alert.vehicle_plate || 'خودرو بدون پلاک',
    time: formatJalaliDateTime(alert.event_time),
    typeLabel: config.label,
    icon: config.icon,
    severity: config.severity,
    status,
  };
}

function PersonalAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [search, setSearch] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [error, setError] = useState('');

  const loadAlerts = useCallback(async () => {
    const response = await alertsAPI.list();
    setAlerts(Array.isArray(response?.results) ? response.results : []);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const poll = async () => {
      if (document.visibilityState === 'visible') {
        try {
          await loadAlerts();
          if (!cancelled) setError('');
        } catch {
          if (!cancelled) setError('دریافت هشدارها از سرور ناموفق بود. دوباره تلاش می‌کنیم.');
        }
      }
      if (!cancelled) timer = window.setTimeout(poll, 30000);
    };

    loadAlerts()
      .then(() => { if (!cancelled) setError(''); })
      .catch(() => { if (!cancelled) setError('دریافت هشدارها از سرور ناموفق بود.'); })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          timer = window.setTimeout(poll, 30000);
        }
      });

    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [loadAlerts]);

  const presentedAlerts = useMemo(
    () => alerts.map(getPersonalEventPresentation),
    [alerts],
  );

  const counts = useMemo(() => ({
    all: presentedAlerts.length,
    active: presentedAlerts.filter((item) => item.status === 'active').length,
    acknowledged: presentedAlerts.filter((item) => item.status === 'acknowledged').length,
    resolved: presentedAlerts.filter((item) => item.status === 'resolved').length,
  }), [presentedAlerts]);

  const filtered = useMemo(() => presentedAlerts.filter((alert) => {
    if (activeTab !== 'all' && alert.status !== activeTab) return false;
    if (filterSeverity && alert.severity !== filterSeverity) return false;
    if (search && !alert.vehicle.includes(search) && !alert.message.includes(search)) return false;
    return true;
  }), [presentedAlerts, activeTab, filterSeverity, search]);

  const severityOptions = Object.entries(severityMap).map(([value, item]) => ({
    value,
    label: item.label,
  }));

  const updateStatus = async (alert, status) => {
    const key = `${alert.device_id}:${alert.id}`;
    setSavingId(key);
    setError('');
    try {
      await alertsAPI.updateStatus({
        deviceId: alert.device_id,
        eventId: alert.id,
        status,
      });
      setAlerts((current) => current.map((item) => (
        item.id === alert.id && item.device_id === alert.device_id
          ? {
              ...item,
              status,
              ...(status === 'acknowledged'
                ? { acknowledged_at: new Date().toISOString() }
                : { resolved_at: new Date().toISOString() }),
            }
          : item
      )));
    } catch {
      setError('ثبت تغییر وضعیت هشدار انجام نشد. لطفاً دوباره تلاش کنید.');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="هشدارها"
        subtitle="رویدادهای واقعی دستگاه‌های شما"
      />

      {error && (
        <div className="rounded-field border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard title="کل رویدادها" value={counts.all} icon={Bell} color="brand" />
        <StatCard title="جدید" value={counts.active} icon={AlertTriangle} color="danger" />
        <StatCard title="بررسی‌شده" value={counts.acknowledged} icon={Eye} color="warning" />
        <StatCard title="رفع‌شده" value={counts.resolved} icon={CheckCheck} color="success" />
      </div>

      <Card>
        <Tabs
          activeTab={activeTab}
          onChange={setActiveTab}
          tabs={[
            { value: 'all', label: 'همه', count: counts.all },
            { value: 'active', label: 'جدید', count: counts.active },
            { value: 'acknowledged', label: 'بررسی‌شده', count: counts.acknowledged },
            { value: 'resolved', label: 'رفع‌شده', count: counts.resolved },
          ]}
        />
        <div className="grid grid-cols-1 gap-4 mt-5 sm:grid-cols-2">
          <Input
            icon={Search}
            placeholder="جستجوی پلاک یا متن هشدار..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Select
            placeholder="همه شدت‌ها"
            value={filterSeverity}
            onChange={(event) => setFilterSeverity(event.target.value)}
            options={severityOptions}
          />
        </div>
      </Card>

      {loading ? (
        <Card>
          <div className="flex justify-center py-10"><LoadingSpinner /></div>
        </Card>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon={AlertTriangle}
            title={alerts.length === 0 ? 'هنوز رویدادی ثبت نشده است' : 'هشداری یافت نشد'}
            description={alerts.length === 0
              ? 'با ثبت رویداد جدید در دستگاه‌های شما، اینجا نمایش داده می‌شود.'
              : 'هیچ رویدادی با فیلترهای فعلی مطابقت ندارد.'}
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((alert) => {
            const severity = severityMap[alert.severity] || severityMap.info;
            const status = statusMap[alert.status] || statusMap.active;
            const key = `${alert.device_id}:${alert.id}`;
            const saving = savingId === key;

            return (
              <div
                key={key}
                className={`bg-bg-elevated border border-border-base rounded-card overflow-hidden
                  ${alert.severity === 'critical' && alert.status === 'active' ? 'border-r-4 border-r-danger' : ''}
                  ${alert.severity === 'warning' && alert.status !== 'resolved' ? 'border-r-4 border-r-warning' : ''}`}
              >
                <div className="p-4 flex items-start gap-4">
                  <div className={`w-11 h-11 rounded-field flex items-center justify-center text-lg flex-shrink-0
                    ${alert.severity === 'critical' ? 'bg-danger/10' : ''}
                    ${alert.severity === 'warning' ? 'bg-warning/10' : ''}
                    ${alert.severity === 'info' ? 'bg-info/10' : ''}`}>
                    {alert.icon}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center flex-wrap gap-2 mb-1">
                      <h4 className="text-sm font-semibold text-text-primary">{alert.typeLabel}</h4>
                      <Badge variant={severity.variant}>{severity.label}</Badge>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </div>
                    <p className="text-sm text-text-secondary mb-2">{alert.message}</p>
                    {alert.detail && (
                      <p className="text-xs text-text-muted mb-3">{alert.detail}</p>
                    )}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-muted">
                      <span className="font-mono">{alert.vehicle}</span>
                      <span>•</span>
                      <span>{alert.time || 'زمان نامشخص'}</span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-3 flex-shrink-0">
                    <div className="flex items-center gap-1">
                      {alert.status === 'active' && (
                        <>
                          <button
                            type="button"
                            title="بررسی شد"
                            aria-label="بررسی شد"
                            disabled={saving}
                            onClick={() => updateStatus(alert, 'acknowledged')}
                            className="p-1.5 rounded-field text-text-muted hover:bg-warning/10 hover:text-warning transition-colors disabled:opacity-40"
                          >
                            <Eye size={15} />
                          </button>
                          <button
                            type="button"
                            title="رفع شد"
                            aria-label="رفع شد"
                            disabled={saving}
                            onClick={() => updateStatus(alert, 'resolved')}
                            className="p-1.5 rounded-field text-text-muted hover:bg-success/10 hover:text-success transition-colors disabled:opacity-40"
                          >
                            <Check size={15} />
                          </button>
                        </>
                      )}
                      {alert.status === 'acknowledged' && (
                        <button
                          type="button"
                          title="رفع شد"
                          aria-label="رفع شد"
                          disabled={saving}
                          onClick={() => updateStatus(alert, 'resolved')}
                          className="p-1.5 rounded-field text-text-muted hover:bg-success/10 hover:text-success transition-colors disabled:opacity-40"
                        >
                          <Check size={15} />
                        </button>
                      )}
                      {alert.status === 'resolved' && (
                        <span className="p-1.5 text-success"><CheckCheck size={15} /></span>
                      )}
                      {saving && <RefreshCw size={13} className="animate-spin text-text-muted" />}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
