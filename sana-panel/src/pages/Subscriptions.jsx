import { useState, useMemo, useCallback } from 'react';
import { Search, Plus, FileText, Pencil, Trash2, Eye, RotateCw } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Select from '../components/Select';
import ActionMenu from '../components/ActionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { useAuth } from '../context/AuthContext';
import { subscriptionsAPI } from '../api/services/subscriptions';
import { useApi } from '../hooks/useApi';
import { toJalali } from '../utils/dateUtils';

const statusMap = {
  active:    { label: 'فعال',          variant: 'success' },
  pending:   { label: 'در انتظار شروع', variant: 'info'    },
  suspended: { label: 'تعلیق‌شده',      variant: 'warning' },
  expired:   { label: 'منقضی',         variant: 'muted'   },
  cancelled: { label: 'لغو‌شده',        variant: 'danger'  },
};

export default function Subscriptions() {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterType, setFilterType] = useState('');
  const navigate = useNavigate();
  const { isSiteAdmin } = useAuth();

  const fetchSubscriptions = useCallback(async () => {
    const result = await subscriptionsAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const { data: subscriptions, loading, error, refetch } = useApi(fetchSubscriptions, []);

  const filtered = useMemo(() => {
    if (!subscriptions) return [];
    return subscriptions.filter((s) => {
      if (search && !s.contract_number.includes(search) && !s.customer_name?.includes(search)) return false;
      if (filterStatus && s.status !== filterStatus) return false;
      if (filterType && s.customer_type !== filterType) return false;
      return true;
    });
  }, [subscriptions, search, filterStatus, filterType]);

  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این قرارداد اطمینان دارید؟')) return;
    try {
      await subscriptionsAPI.delete(id);
      refetch();
    } catch (err) {
      console.error('Error deleting subscription:', err);
      alert('خطا در حذف قرارداد');
    }
  };

  const getMenuItems = (sub) => {
    const items = [];

    items.push({
      label: 'مشاهده جزئیات',
      icon: Eye,
      onClick: () => navigate(`/panel/subscriptions/${sub.id}`),
    });

    // اگه لغو نشده، دکمه تمدید رو نشون بده
    if (isSiteAdmin && sub.status !== 'cancelled') {
      items.push({
        label: 'تمدید',
        icon: RotateCw,
        onClick: () => navigate(`/panel/subscriptions/${sub.id}?renew=true`),
      });

      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => handleDelete(sub.id),
      });
    }

    return items;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="قراردادها" subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="قراردادها" subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader
        title="قراردادها"
        subtitle={`${filtered.length} قرارداد`}
        actions={
          isSiteAdmin ? (
            <Button icon={Plus} onClick={() => navigate('/panel/subscriptions/new')}>
              قرارداد جدید
            </Button>
          ) : null
        }
      />

      <Card>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            icon={Search}
            placeholder="جستجوی شماره قرارداد یا مشتری..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Select
            placeholder="همه وضعیت‌ها"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            options={Object.entries(statusMap).map(([value, { label }]) => ({ value, label }))}
          />
          <Select
            placeholder="همه انواع"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            options={[
              { value: 'organization', label: 'سازمانی' },
              { value: 'personal', label: 'شخصی' },
            ]}
          />
        </div>
      </Card>

      <Card>
        {filtered.length === 0 ? (
          <div className="py-12 text-center">
            <FileText size={40} className="text-text-muted mx-auto mb-3" />
            <p className="text-sm text-text-muted mb-3">قراردادی یافت نشد</p>
            {isSiteAdmin && (
              <Button icon={Plus} onClick={() => navigate('/panel/subscriptions/new')}>
                ساخت اولین قرارداد
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto -m-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">شماره قرارداد</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">مشتری</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نوع</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">شروع</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">پایان</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">روز مانده</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">دستگاه‌های فعال</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">پرداخت‌شده</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">پرداخت آینده</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => {
                  const st = statusMap[s.status] || statusMap.expired;
                  const daysLeft = s.days_until_expiry;
                  return (
                    <tr key={s.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                      <td className="py-3 px-4">
                        <button
                          onClick={() => navigate(`/panel/subscriptions/${s.id}`)}
                          className="font-mono text-brand-400 hover:text-brand-500 text-xs"
                        >
                          {s.contract_number}
                        </button>
                      </td>
                      <td className="py-3 px-4 text-text-primary">{s.customer_name}</td>
                      <td className="py-3 px-4">
                        <Badge variant={s.customer_type === 'organization' ? 'brand' : 'info'}>
                          {s.customer_type === 'organization' ? 'سازمانی' : 'شخصی'}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-text-secondary font-mono text-xs">{toJalali(s.start_date)}</td>
                      <td className="py-3 px-4 text-text-secondary font-mono text-xs">{toJalali(s.end_date)}</td>
                      <td className="py-3 px-4">
                        <span className={`font-mono text-xs ${daysLeft < 0 ? 'text-danger' : daysLeft <= 30 ? 'text-warning' : 'text-text-secondary'}`}>
                          {daysLeft < 0 ? `منقضی (${Math.abs(daysLeft)} روز پیش)` : `${daysLeft} روز`}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-text-secondary font-mono text-xs">{s.active_device_count ?? 0}</td>
                      <td className="py-3 px-4 text-text-secondary font-mono text-xs">
                        {Number(s.paid_payment_amount || 0).toLocaleString('fa-IR')} ریال
                      </td>
                      <td className="py-3 px-4 text-text-secondary font-mono text-xs">
                        {Number(s.future_payment_amount || 0).toLocaleString('fa-IR')} ریال
                      </td>
                      <td className="py-3 px-4"><Badge variant={st.variant}>{st.label}</Badge></td>
                      <td className="py-3 px-2">
                        <ActionMenu items={getMenuItems(s)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

    </div>
  );
}