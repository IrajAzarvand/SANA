import { useState, useMemo, useCallback } from 'react';
import { Search, Plus, Building2, Pencil, Trash2, Eye } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Modal from '../components/Modal';
import ActionMenu from '../components/ActionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { useAuth } from '../context/AuthContext';
import { organizationsAPI } from '../api/services/organizations';
import { useApi } from '../hooks/useApi';

export default function Companies() {
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState({
    name: '', code: '', registration_number: '',
    phone: '', email: '', address: '', status: 'active',
  });
  const [saving, setSaving] = useState(false);

  const { isSiteAdmin } = useAuth();

  // دریافت سازمان‌ها از API
  const fetchOrganizations = useCallback(async () => {
    const result = await organizationsAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const { data: organizations, loading, error, refetch } =
    useApi(fetchOrganizations, []);

  // فیلتر
  const filtered = useMemo(() => {
    if (!organizations) return [];
    if (!search) return organizations;
    return organizations.filter((o) =>
      o.name.includes(search) ||
      o.code.includes(search) ||
      (o.phone && o.phone.includes(search))
    );
  }, [organizations, search]);

  // افزودن سازمان
  const handleAdd = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await organizationsAPI.create(form);
      setModalOpen(false);
      setForm({
        name: '', code: '', registration_number: '',
        phone: '', email: '', address: '', status: 'active',
      });
      refetch();
    } catch (err) {
      console.error('Error adding organization:', err);
      alert('خطا در افزودن شرکت: ' + (err.response?.data?.code?.[0] || 'لطفاً دوباره تلاش کنید'));
    } finally {
      setSaving(false);
    }
  };

  // حذف سازمان
  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این شرکت اطمینان دارید؟')) return;
    try {
      await organizationsAPI.delete(id);
      refetch();
    } catch (err) {
      console.error('Error deleting organization:', err);
      alert('خطا در حذف شرکت');
    }
  };

  const getMenuItems = (org) => {
    const items = [];

    if (isSiteAdmin) {
      items.push({
        label: 'ویرایش',
        icon: Pencil,
        onClick: () => console.log('Edit organization:', org.id),
      });
      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => handleDelete(org.id),
      });
    } else {
      items.push({
        label: 'مشاهده جزئیات',
        icon: Eye,
        onClick: () => console.log('View organization:', org.id),
      });
    }

    return items;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="شرکت‌ها" subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="شرکت‌ها" subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader
        title="شرکت‌ها"
        subtitle={`مدیریت شرکت‌های مشتری سامانه سانا — ${filtered.length} شرکت`}
        actions={
          isSiteAdmin ? (
            <Button icon={Plus} onClick={() => setModalOpen(true)}>
              افزودن شرکت
            </Button>
          ) : null
        }
      />

      <Card>
        <Input
          icon={Search}
          placeholder="جستجوی نام، کد یا تلفن شرکت..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Card>

      <Card>
        {filtered.length === 0 ? (
          <div className="py-12 text-center">
            <Building2 size={40} className="text-text-muted mx-auto mb-3" />
            <p className="text-sm text-text-muted">شرکتی یافت نشد</p>
          </div>
        ) : (
          <div className="overflow-x-auto -m-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نام شرکت</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">کد</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">تلفن</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">منابع</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-field bg-brand-900/40 flex items-center justify-center">
                          <Building2 size={16} className="text-brand-400" />
                        </div>
                        <span className="font-medium text-text-primary">{c.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{c.code}</td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{c.phone || '—'}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3 text-[10px] text-text-muted">
                        <span>🏢 {c.branches_count || 0}</span>
                        <span>🚗 {c.vehicles_count || 0}</span>
                        <span>📡 {c.devices_count || 0}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={c.status === 'active' ? 'success' : 'muted'}>
                        {c.status === 'active' ? 'فعال' : 'غیرفعال'}
                      </Badge>
                    </td>
                    <td className="py-3 px-2">
                      <ActionMenu items={getMenuItems(c)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* مودال افزودن */}
      {isSiteAdmin && (
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title="افزودن شرکت"
          size="lg"
          footer={
            <>
              <Button variant="secondary" onClick={() => setModalOpen(false)} disabled={saving}>
                انصراف
              </Button>
              <Button type="submit" form="add-company-form" disabled={saving}>
                {saving ? 'در حال ذخیره...' : 'ذخیره'}
              </Button>
            </>
          }
        >
          <form id="add-company-form" onSubmit={handleAdd} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="نام شرکت"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="نام کامل شرکت"
                required
              />
              <Input
                label="کد شرکت"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="مثلاً SMP-001"
                required
              />
              <Input
                label="شماره ثبت"
                value={form.registration_number}
                onChange={(e) => setForm({ ...form, registration_number: e.target.value })}
              />
              <Input
                label="کد اقتصادی"
                value={form.economy_code}
                onChange={(e) => setForm({ ...form, economy_code: e.target.value })}
              />
              <Input
                label="تلفن"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="۰۲۱-xxxxxxxx"
              />
              <Input
                label="ایمیل"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="info@example.com"
              />
            </div>
            <Input
              label="آدرس"
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="آدرس کامل"
            />
          </form>
        </Modal>
      )}

    </div>
  );
}