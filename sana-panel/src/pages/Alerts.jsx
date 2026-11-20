import { useState, useMemo, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Check, CheckCheck, Eye, Bell, RefreshCw, Search } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Input from '../components/Input';
import Tabs from '../components/Tabs';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Select from '../components/Select';
import StatCard from '../components/StatCard';
import EmptyState from '../components/EmptyState';
import { severityMap, statusMap } from '../data/alertsData';
import { useAuth } from '../context/AuthContext';
import { alertsAPI, panelNotificationsAPI, notificationsAPI } from '../api/services/fleet';
import { formatJalaliDateTime } from '../utils/dateUtils';
import LoadingSpinner from '../components/LoadingSpinner';

export default function Alerts() {
  const { isPersonal } = useAuth();
  return isPersonal ? <PersonalAlerts /> : <PanelAlerts />;
}

const personalEventTypes = {
  commandResult: { label: 'نتیجه اجرای فرمان', icon: '🧾', severity: 'info', message: 'نتیجه اجرای فرمان دستگاه دریافت شد' },
  deviceOnline: { label: 'اتصال مجدد دستگاه', icon: '🟢', severity: 'info', message: 'ارتباط دستگاه برقرار شد' },
  deviceUnknown: { label: 'وضعیت ارتباط نامشخص', icon: '❔', severity: 'warning', message: 'وضعیت ارتباط دستگاه نامشخص است' },
  deviceOffline: { label: 'قطع ارتباط دستگاه', icon: '📡', severity: 'warning', message: 'ارتباط دستگاه قطع شد' },
  deviceInactive: { label: 'عدم فعالیت دستگاه', icon: '⚠️', severity: 'warning', message: 'دستگاه برای مدت طولانی موقعیتی ارسال نکرده است' },
  queuedCommandSent: { label: 'ارسال فرمان در صف', icon: '📤', severity: 'info', message: 'فرمان در صف ارسال به دستگاه قرار گرفت' },
  deviceMoving: { label: 'شروع حرکت', icon: '🚗', severity: 'info', message: 'حرکت خودرو آغاز شد' },
  deviceStopped: { label: 'توقف خودرو', icon: '🛑', severity: 'info', message: 'خودرو متوقف شد' },
  deviceOverspeed: { label: 'سرعت غیرمجاز', icon: '⚡', severity: 'critical', message: 'سرعت خودرو از حد مجاز عبور کرد' },
  overspeed: { label: 'سرعت غیرمجاز', icon: '⚡', severity: 'critical', message: 'هشدار سرعت غیرمجاز ثبت شد' },
  deviceFuelDrop: { label: 'کاهش ناگهانی سوخت', icon: '⛽', severity: 'warning', message: 'کاهش ناگهانی سطح سوخت تشخیص داده شد' },
  deviceFuelIncrease: { label: 'افزایش ناگهانی سوخت', icon: '⛽', severity: 'info', message: 'افزایش ناگهانی سطح سوخت تشخیص داده شد' },
  geofenceEnter: { label: 'ورود به محدوده', icon: '📍', severity: 'info', message: 'خودرو وارد محدوده جغرافیایی شد' },
  geofenceExit: { label: 'خروج از محدوده', icon: '📍', severity: 'warning', message: 'خودرو از محدوده جغرافیایی خارج شد' },
  geofenceCrossed: { label: 'عبور از محدوده', icon: '🗺️', severity: 'warning', message: 'خودرو از مرز محدوده جغرافیایی عبور کرد' },
  proximityEnter: { label: 'ورود به محدوده نزدیکی', icon: '↔️', severity: 'info', message: 'دستگاه به دستگاه مرتبط نزدیک شد' },
  proximityExit: { label: 'خروج از محدوده نزدیکی', icon: '↔️', severity: 'warning', message: 'دستگاه از دستگاه مرتبط دور شد' },
  unaccompaniedMotion: { label: 'حرکت بدون همراه', icon: '🚨', severity: 'warning', message: 'حرکت دستگاه بدون حضور دستگاه همراه تشخیص داده شد' },
  alarm: { label: 'هشدار دستگاه', icon: '🆘', severity: 'critical', message: 'هشدار توسط خود دستگاه ارسال شد' },
  ignitionOn: { label: 'روشن شدن سوئیچ', icon: '🔑', severity: 'info', message: 'سوئیچ خودرو روشن شد' },
  ignitionOff: { label: 'خاموش شدن سوئیچ', icon: '🔑', severity: 'info', message: 'سوئیچ خودرو خاموش شد' },
  maintenance: { label: 'یادآوری سرویس', icon: '🛠️', severity: 'warning', message: 'موعد سرویس دوره‌ای فرا رسیده است' },
  driverChanged: { label: 'تغییر راننده', icon: '👤', severity: 'info', message: 'راننده دستگاه تغییر کرد' },
  media: { label: 'رسانه جدید', icon: '📷', severity: 'info', message: 'رسانه‌ای از دستگاه دریافت شد' },
};

const alarmLabels = {
  general: 'هشدار عمومی',
  sos: 'دکمه اضطراری',
  vibration: 'لرزش',
  movement: 'حرکت غیرمجاز',
  lowspeed: 'سرعت پایین',
  overspeed: 'سرعت غیرمجاز',
  fallDown: 'سقوط',
  lowPower: 'ولتاژ برق پایین',
  lowBattery: 'باتری ضعیف',
  fault: 'خطای دستگاه',
  powerOff: 'خاموشی برق',
  powerOn: 'وصل شدن برق',
  door: 'باز شدن در',
  lock: 'قفل شدن',
  unlock: 'باز شدن قفل',
  geofence: 'هشدار محدوده جغرافیایی',
  geofenceEnter: 'ورود به محدوده',
  geofenceExit: 'خروج از محدوده',
  gpsAntennaCut: 'قطع آنتن GPS',
  accident: 'تصادف',
  tow: 'یدک‌کش شدن',
  idle: 'درجا کار کردن موتور',
  highRpm: 'دور موتور بالا',
  hardAcceleration: 'شتاب‌گیری شدید',
  hardBraking: 'ترمز شدید',
  hardCornering: 'پیچیدن شدید',
  laneChange: 'تغییر ناگهانی خط',
  fatigueDriving: 'خستگی راننده',
  powerCut: 'قطع برق اصلی',
  powerRestored: 'برقراری مجدد برق',
  jamming: 'اختلال یا مسدودسازی سیگنال',
  temperature: 'دمای غیرعادی',
  parking: 'هشدار پارک',
  bonnet: 'باز شدن کاپوت',
  footBrake: 'فشار پدال ترمز',
  fuelLeak: 'نشت سوخت',
  tampering: 'دست‌کاری دستگاه',
  removing: 'جدا شدن دستگاه',
};

function getPersonalEventPresentation(alert) {
  const config = personalEventTypes[alert.type];
  const attributes = alert.attributes || {};
  const rawAlarm = attributes.alarm;
  const alarmNames = typeof rawAlarm === 'string'
    ? rawAlarm.split(',').map((item) => item.trim()).filter(Boolean)
    : [];
  const alarmLabelsText = alarmNames
    .map((alarm) => alarmLabels[alarm] || `هشدار دستگاه (${alarm})`)
    .join('، ');

  const fallback = {
    label: alert.type
      ? `رویداد Traccar: ${alert.type}`
      : 'رویداد ناشناخته',
    icon: '🔔',
    severity: 'info',
    message: alert.type
      ? `رویداد ${alert.type} از Traccar دریافت شد`
      : 'یک رویداد با نوع نامشخص دریافت شد',
  };
  const presentation = config || fallback;
  let message = presentation.message;
  if (alert.type === 'alarm' && alarmLabelsText) {
    message = `هشدار دستگاه: ${alarmLabelsText}`;
  }

  const details = [];
  if (attributes.geofence) details.push(`محدوده: ${attributes.geofence}`);
  if (attributes.speed !== undefined && attributes.speed !== null) {
    details.push(`سرعت: ${attributes.speed}`);
  }
  if (attributes.speedLimit !== undefined && attributes.speedLimit !== null) {
    details.push(`حد مجاز سرعت: ${attributes.speedLimit}`);
  }
  if (attributes.fuel !== undefined && attributes.fuel !== null) {
    details.push(`سوخت: ${attributes.fuel}`);
  }
  if (attributes.result) details.push(`نتیجه: ${attributes.result}`);
  if (attributes.command) details.push(`فرمان: ${attributes.command}`);
  if (attributes.driverName) details.push(`راننده: ${attributes.driverName}`);
  if (attributes.address) details.push(`موقعیت: ${attributes.address}`);

  const status = alert.status === 'unread' ? 'active' : alert.status;
  return {
    ...alert,
    message,
    detail: details.join(' • '),
    vehicle: alert.vehicle_plate || 'خودرو بدون پلاک',
    time: formatJalaliDateTime(alert.event_time),
    typeLabel: presentation.label,
    icon: presentation.icon,
    severity: presentation.severity,
    status,
  };
}

function PersonalAlerts() {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState([]);
  const [businessNotifications, setBusinessNotifications] = useState([]);
  const [businessError, setBusinessError] = useState('');
  const [businessUpdating, setBusinessUpdating] = useState('');
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

  const loadBusinessNotifications = useCallback(async () => {
    try {
      const response = await panelNotificationsAPI.list();
      setBusinessNotifications(Array.isArray(response?.results) ? response.results : []);
      setBusinessError('');
    } catch {
      setBusinessError('دریافت اعلان‌های قرارداد و مالی ناموفق بود.');
    }
  }, []);

  const markBusinessRead = async (item, shouldNavigate = false) => {
    if (!item.is_read) {
      setBusinessUpdating(item.id);
      try {
        await panelNotificationsAPI.markRead(item.id);
        setBusinessNotifications((current) => current.map((entry) => (
          entry.id === item.id ? { ...entry, is_read: true } : entry
        )));
        window.dispatchEvent(new Event('sana:notifications-updated'));
      } catch {
        setBusinessError('ثبت وضعیت خواندن اعلان ناموفق بود.');
        setBusinessUpdating('');
        return;
      }
      setBusinessUpdating('');
    }
    if (shouldNavigate && item.path) navigate(item.path);
  };

  const markAllBusinessRead = async () => {
    setBusinessUpdating('all');
    try {
      await panelNotificationsAPI.markAllRead();
      setBusinessNotifications((current) => current.map((item) => ({ ...item, is_read: true })));
      window.dispatchEvent(new Event('sana:notifications-updated'));
      setBusinessError('');
    } catch {
      setBusinessError('خواندن همه اعلان‌های مالی ناموفق بود.');
    } finally {
      setBusinessUpdating('');
    }
  };

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
      if (!cancelled) {
        await loadBusinessNotifications();
        timer = window.setTimeout(poll, 30000);
      }
    };

    const refreshFromHeader = () => {
      loadAlerts().catch(() => {
        if (!cancelled) setError('دریافت هشدارها از سرور ناموفق بود.');
      });
    };
    window.addEventListener('sana:traccar-alert-state-changed', refreshFromHeader);
    window.addEventListener('sana:panel-notification-state-changed', loadBusinessNotifications);
    window.addEventListener('sana:notifications-updated', loadBusinessNotifications);

    loadBusinessNotifications();
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
      window.removeEventListener('sana:traccar-alert-state-changed', refreshFromHeader);
      window.removeEventListener('sana:panel-notification-state-changed', loadBusinessNotifications);
      window.removeEventListener('sana:notifications-updated', loadBusinessNotifications);
    };
  }, [loadAlerts, loadBusinessNotifications]);

  const presentedAlerts = useMemo(
    () => alerts.map(getPersonalEventPresentation),
    [alerts],
  );

  const counts = useMemo(() => ({
    all: presentedAlerts.length,
    active: presentedAlerts.filter((item) => item.status === 'active').length,
    read: presentedAlerts.filter((item) => item.status === 'read').length,
    reviewed: presentedAlerts.filter((item) => item.status === 'reviewed').length,
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
              ...(status === 'reviewed'
                ? { reviewed_at: new Date().toISOString() }
                : { resolved_at: new Date().toISOString() }),
            }
          : item
      )));
      window.dispatchEvent(new Event('sana:personal-alerts-updated'));
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

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">قرارداد و امور مالی</h2>
            <p className="mt-1 text-xs text-text-muted">سررسید اقساط، مانده‌های پرداخت‌نشده، دریافت وجه و وضعیت قرارداد</p>
          </div>
          {businessNotifications.some((item) => !item.is_read) && (
            <button
              type="button"
              onClick={markAllBusinessRead}
              disabled={!!businessUpdating}
              className="rounded-field px-3 py-2 text-xs text-brand-500 hover:bg-bg-hover disabled:opacity-50"
            >
              خواندن همه
            </button>
          )}
        </div>
        {businessError && <p className="text-xs text-danger">{businessError}</p>}
        {businessNotifications.length === 0 ? (
          <Card><p className="py-3 text-center text-xs text-text-muted">اعلان قراردادی یا مالی جدیدی وجود ندارد.</p></Card>
        ) : (
          <div className="space-y-2">
            {businessNotifications.map((item) => (
              <Card key={item.id}>
                <div className="flex flex-wrap items-start gap-3">
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brand-500" style={{ opacity: item.is_read ? 0.2 : 1 }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-text-primary">{item.title}</h3>
                      <Badge variant={item.is_read ? 'success' : 'warning'}>{item.is_read ? 'خوانده‌شده' : 'خوانده‌نشده'}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-text-secondary">{item.message}</p>
                    <p className="mt-1 text-[11px] text-text-muted">{formatJalaliDateTime(item.created_at)}</p>
                  </div>
                  <div className="flex gap-2">
                    {!item.is_read && (
                      <button
                        type="button"
                        onClick={() => markBusinessRead(item)}
                        disabled={!!businessUpdating}
                        className="rounded-field px-3 py-2 text-xs text-brand-500 hover:bg-bg-hover disabled:opacity-50"
                      >
                        {businessUpdating === item.id ? 'در حال ثبت…' : 'خوانده شد'}
                      </button>
                    )}
                    {item.path && (
                      <button
                        type="button"
                        onClick={() => markBusinessRead(item, true)}
                        disabled={!!businessUpdating}
                        className="rounded-field px-3 py-2 text-xs text-text-secondary hover:bg-bg-hover disabled:opacity-50"
                      >
                        جزئیات قرارداد
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {error && (
        <div className="rounded-field border border-danger/30 bg-danger/5 px-4 py-3 text-xs text-danger">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard title="کل رویدادها" value={counts.all} icon={Bell} color="brand" />
        <StatCard title="جدید" value={counts.active} icon={AlertTriangle} color="danger" />
        <StatCard title="خوانده‌شده" value={counts.read} icon={Check} color="info" />
        <StatCard title="بررسی‌شده" value={counts.reviewed} icon={Eye} color="warning" />
        <StatCard title="رفع‌شده" value={counts.resolved} icon={CheckCheck} color="success" />
      </div>

      <Card>
        <Tabs
          activeTab={activeTab}
          onChange={setActiveTab}
          tabs={[
            { value: 'all', label: 'همه', count: counts.all },
            { value: 'active', label: 'جدید', count: counts.active },
            { value: 'read', label: 'خوانده‌شده', count: counts.read },
            { value: 'reviewed', label: 'بررسی‌شده', count: counts.reviewed },
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
                            onClick={() => updateStatus(alert, 'reviewed')}
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
                      {alert.status === 'reviewed' && (
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


function PanelAlerts() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [updating, setUpdating] = useState('');

  const loadAlerts = useCallback(async () => {
    const { businessResult, gpsResult } = await notificationsAPI.list();
    if (businessResult.status === 'rejected' && gpsResult.status === 'rejected') {
      throw new Error('notification feeds unavailable');
    }

    const businessItems = businessResult.status === 'fulfilled'
      ? (Array.isArray(businessResult.value?.results) ? businessResult.value.results : []).map((item) => ({
        ...item,
        notification_key: item.id,
        is_gps_alert: false,
        typeLabel: 'رویداد مدیریتی',
        icon: '📋',
        severity: 'info',
        vehicle: item.message,
        time: formatJalaliDateTime(item.created_at),
        status: item.is_read ? 'read' : 'unread',
      }))
      : null;
    const gpsItems = gpsResult.status === 'fulfilled'
      ? (Array.isArray(gpsResult.value?.results) ? gpsResult.value.results : []).map((item) => ({
        ...getPersonalEventPresentation(item),
        notification_key: `gps:${item.device_id}:${item.id}`,
        is_gps_alert: true,
        is_read: item.status !== 'unread',
        title: getPersonalEventPresentation(item).typeLabel,
        path: '/panel/alerts',
      }))
      : null;

    setItems((current) => {
      const currentBusiness = businessItems ?? current.filter((item) => !item.is_gps_alert);
      const currentGps = gpsItems ?? current.filter((item) => item.is_gps_alert);
      return [...currentBusiness, ...currentGps].sort(
        (a, b) => new Date(b.created_at || b.event_time) - new Date(a.created_at || a.event_time),
      );
    });
    setError(
      businessResult.status === 'rejected' || gpsResult.status === 'rejected'
        ? 'بخشی از اعلان‌ها موقتاً در دسترس نیست.'
        : '',
    );
  }, []);

  useEffect(() => {
    let active = true;
    let timer;
    let running = false;

    const refresh = async () => {
      if (running) return;
      running = true;
      if (document.visibilityState === 'visible') {
        try {
          await loadAlerts();
        } catch {
          if (active) setError('دریافت اعلان‌ها ناموفق بود. دوباره تلاش کنید.');
        }
      }
      running = false;
      if (active) {
        setLoading(false);
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
    window.addEventListener('sana:panel-notification-state-changed', refreshNow);
    window.addEventListener('sana:traccar-alert-state-changed', refreshNow);
    document.addEventListener('visibilitychange', refreshNow);
    return () => {
      active = false;
      window.clearTimeout(timer);
      window.removeEventListener('sana:notifications-updated', refreshNow);
      window.removeEventListener('sana:personal-alerts-updated', refreshNow);
      window.removeEventListener('sana:panel-notification-state-changed', refreshNow);
      window.removeEventListener('sana:traccar-alert-state-changed', refreshNow);
      document.removeEventListener('visibilitychange', refreshNow);
    };
  }, [loadAlerts]);

  const unread = useMemo(() => items.filter((item) => !item.is_read), [items]);
  const counts = useMemo(() => ({
    all: items.length,
    unread: unread.length,
    read: items.length - unread.length,
  }), [items.length, unread.length]);

  const filtered = useMemo(() => items.filter((item) => {
    if (activeTab === 'unread' && item.is_read) return false;
    if (activeTab === 'read' && !item.is_read) return false;
    const query = search.trim().toLocaleLowerCase('fa');
    if (query && ![item.title, item.message, item.vehicle, item.typeLabel]
      .filter(Boolean).some((value) => String(value).toLocaleLowerCase('fa').includes(query))) return false;
    return true;
  }), [items, activeTab, search]);

  const markRead = async (item) => {
    if (item.is_read) return true;
    setUpdating(item.notification_key);
    try {
      await notificationsAPI.markRead({
        isGps: item.is_gps_alert,
        eventKey: item.id,
        deviceId: item.device_id,
        eventId: item.id,
      });
      setItems((current) => current.map((entry) => entry.notification_key === item.notification_key
        ? { ...entry, is_read: true, status: 'read' }
        : entry));
      window.dispatchEvent(new Event(item.is_gps_alert ? 'sana:personal-alerts-updated' : 'sana:notifications-updated'));
      return true;
    } catch {
      setError('ثبت وضعیت خواندن اعلان ناموفق بود.');
      return false;
    } finally {
      setUpdating('');
    }
  };

  const markAllRead = async () => {
    setUpdating('all');
    const [businessResult, gpsResult] = await notificationsAPI.markAllRead();
    setItems((current) => current.map((item) => {
      if (item.is_gps_alert && gpsResult.status === 'fulfilled') {
        return { ...item, is_read: true, status: 'read' };
      }
      if (!item.is_gps_alert && businessResult.status === 'fulfilled') {
        return { ...item, is_read: true, status: 'read' };
      }
      return item;
    }));
    if (businessResult.status === 'fulfilled') {
      window.dispatchEvent(new Event('sana:notifications-updated'));
    }
    if (gpsResult.status === 'fulfilled') {
      window.dispatchEvent(new Event('sana:personal-alerts-updated'));
    }
    setError(
      businessResult.status === 'rejected' || gpsResult.status === 'rejected'
        ? 'خواندن همه اعلان‌ها به‌طور کامل انجام نشد.'
        : '',
    );
    setUpdating('');
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="مرکز اعلان‌ها"
        subtitle="رویدادهای مدیریتی، تغییرات سازمانی و هشدارهای خودرو و GPS"
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard title="کل اعلان‌ها" value={counts.all} icon={Bell} color="brand" />
        <StatCard title="خوانده‌نشده" value={counts.unread} icon={AlertTriangle} color="warning" />
        <StatCard title="خوانده‌شده" value={counts.read} icon={CheckCheck} color="success" />
      </div>

      <Card>
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs
              activeTab={activeTab}
              onChange={setActiveTab}
              tabs={[
                { value: 'all', label: 'همه', count: counts.all },
                { value: 'unread', label: 'خوانده‌نشده', count: counts.unread },
                { value: 'read', label: 'خوانده‌شده', count: counts.read },
              ]}
            />
            {unread.length > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                disabled={!!updating}
                className="rounded-field px-3 py-2 text-xs text-brand-500 hover:bg-bg-hover disabled:opacity-50"
              >
                خواندن همه
              </button>
            )}
          </div>
          <Input
            icon={Search}
            placeholder="جستجوی نوع رویداد، دستگاه، پلاک یا متن اعلان..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </Card>

      {loading ? (
        <LoadingSpinner />
      ) : error && items.length === 0 ? (
        <Card><EmptyState icon={Bell} title="دریافت اعلان‌ها ممکن نشد" description={error} /></Card>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState icon={Bell} title="اعلانی یافت نشد" description="برای این فیلتر موردی وجود ندارد." />
        </Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <Card key={item.notification_key}>
              <div className="flex flex-wrap items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-field bg-bg-hover text-lg">
                  {item.icon || '🔔'}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-text-primary">{item.title || item.typeLabel}</h3>
                    <Badge variant={item.is_read ? 'success' : 'warning'}>
                      {item.is_read ? 'خوانده‌شده' : 'خوانده‌نشده'}
                    </Badge>
                    {item.is_gps_alert && <Badge variant="info">هشدار خودرو</Badge>}
                  </div>
                  <p className="text-sm text-text-secondary">{item.message}</p>
                  {item.detail && <p className="mt-1 text-xs text-text-muted">{item.detail}</p>}
                  <p className="mt-2 text-[11px] text-text-muted">
                    {item.vehicle && <span>{item.vehicle} · </span>}
                    {formatJalaliDateTime(item.created_at || item.event_time)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {!item.is_read && (
                    <button
                      type="button"
                      onClick={() => markRead(item)}
                      disabled={!!updating}
                      className="rounded-field px-3 py-2 text-xs text-brand-500 hover:bg-bg-hover disabled:opacity-50"
                    >
                      {updating === item.notification_key ? 'در حال ثبت…' : 'خوانده شد'}
                    </button>
                  )}
                  {item.path && item.path !== '/panel/alerts' && (
                    <button
                      type="button"
                      onClick={() => navigate(item.path)}
                      className="rounded-field px-3 py-2 text-xs text-text-secondary hover:bg-bg-hover"
                    >
                      مشاهده مرتبط
                    </button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
