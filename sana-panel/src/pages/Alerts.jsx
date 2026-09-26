import { useState, useMemo } from 'react';
import { Search, AlertTriangle, Check, CheckCheck, Eye, Bell, Trash2 } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
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

export default function Alerts() {
  const [search, setSearch] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [activeTab, setActiveTab] = useState('all');

  const { can, isPersonal, isBranchManager, isSiteAdmin, user } = useAuth();

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