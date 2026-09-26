import { useState, useMemo, useCallback, useEffect } from 'react';
import { Search, Plus, Building2, Pencil, Trash2, Eye, Phone, MapPin } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Select from '../components/Select';
import Modal from '../components/Modal';
import ActionMenu from '../components/ActionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { useAuth } from '../context/AuthContext';
import { organizationsAPI, branchesAPI } from '../api/services/organizations';
import { useApi } from '../hooks/useApi';

export default function Branches() {
  const [search, setSearch] = useState('');
  const [filterOrg, setFilterOrg] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBranch, setEditingBranch] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    organization: '', name: '', code: '', phone: '', address: '', status: 'active',
  });

  const { isSiteAdmin, isMainUser } = useAuth();

  // دریافت شعبه‌ها
  const fetchBranches = useCallback(async () => {
    const result = await branchesAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  // دریافت سازمان‌ها (برای فیلتر و فرم)
  const fetchOrgs = useCallback(async () => {
    try {
      const result = await organizationsAPI.list();
      return Array.isArray(result) ? result : result.results || [];
    } catch {
      return [];
    }
  }, []);

  const { data: branches, loading, error, refetch } = useApi(fetchBranches, []);
  const { data: organizations } = useApi(fetchOrgs, []);

  // اگه Main User بود، توی فرم، سازمانش رو پیش‌فرض انتخاب کن
  useEffect(() => {
    if (isMainUser && organizations?.length === 1 && !form.organization) {
      setForm((f) => ({ ...f, organization: organizations[0].id }));
    }
  }, [isMainUser, organizations]); // eslint-disable-line react-hooks/exhaustive-deps

  // فیلتر
  const filtered = useMemo(() => {
    if (!branches) return [];
    return branches.filter((b) => {
      if (search && !b.name.includes(search) && !b.code.includes(search)) return false;
      if (filterOrg && b.organization !== Number(filterOrg)) return false;
      return true;
    });
  }, [branches, search, filterOrg]);

  const orgOptions = useMemo(() => {
    return (organizations || []).map((o) => ({ value: o.id, label: o.name }));
  }, [organizations]);

  // افزودن/ویرایش
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editingBranch) {
        await branchesAPI.update(editingBranch.id, form);
      } else {
        await branchesAPI.create(form);
      }
      setModalOpen(false);
      setEditingBranch(null);
      setForm({
        organization: isMainUser && organizations?.[0]?.id || '',
        name: '', code: '', phone: '', address: '', status: 'active',
      });
      refetch();
    } catch (err) {
      console.error('Error saving branch:', err);
      const errData = err.response?.data;
      const errMsg = errData
        ? Object.entries(errData).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'لطفاً دوباره تلاش کنید';
      alert('خطا در ذخیره شعبه:\n' + errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (branch) => {
    setEditingBranch(branch);
    setForm({
      organization: branch.organization,
      name: branch.name,
      code: branch.code,
      phone: branch.phone || '',
      address: branch.address || '',
      status: branch.status,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این شعبه اطمینان دارید؟')) return;
    try {
      await branchesAPI.delete(id);
      refetch();
    } catch (err) {
      console.error('Error deleting branch:', err);
      alert('خطا در حذف شعبه');
    }
  };

  const getMenuItems = (branch) => {
    const items = [];

    if (isSiteAdmin || isMainUser) {
      items.push({
        label: 'ویرایش',
        icon: Pencil,
        onClick: () => handleEdit(branch),
      });
    }

    if (isSiteAdmin) {
      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => handleDelete(branch.id),
      });
    }

    if (!isSiteAdmin && !isMainUser) {
      items.push({
        label: 'مشاهده جزئیات',
        icon: Eye,
        onClick: () => console.log('View branch:', branch.id),
      });
    }

    return items;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="شعبه‌ها" subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="شعبه‌ها" subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader
        title="شعبه‌ها"
        subtitle={`${filtered.length} شعبه ثبت شده`}
        actions={
          (isSiteAdmin || isMainUser) ? (
            <Button icon={Plus} onClick={() => {
              setEditingBranch(null);
              setForm({
                organization: isMainUser && organizations?.[0]?.id || '',
                name: '', code: '', phone: '', address: '', status: 'active',
              });
              setModalOpen(true);
            }}>
              افزودن شعبه
            </Button>
          ) : null
        }
      />

      {/* فیلترها */}
      <Card>
        <div className={`grid grid-cols-1 gap-4 ${isSiteAdmin ? 'md:grid-cols-2' : ''}`}>
          <Input
            icon={Search}
            placeholder="جستجوی نام یا کد شعبه..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {isSiteAdmin && (
            <Select
              placeholder="همه شرکت‌ها"
              value={filterOrg}
              onChange={(e) => setFilterOrg(e.target.value)}
              options={orgOptions}
            />
          )}
        </div>
      </Card>

      {/* جدول */}
      <Card>
        {filtered.length === 0 ? (
          <div className="py-12 text-center">
            <Building2 size={40} className="text-text-muted mx-auto mb-3" />
            <p className="text-sm text-text-muted">شعبه‌ای یافت نشد</p>
          </div>
        ) : (
          <div className="overflow-x-auto -m-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نام شعبه</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">کد</th>
                  {isSiteAdmin && (
                    <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">شرکت</th>
                  )}
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">تلفن</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">منابع</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((b) => (
                  <tr key={b.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-field bg-brand-900/40 flex items-center justify-center">
                          <Building2 size={16} className="text-brand-400" />
                        </div>
                        <span className="font-medium text-text-primary">{b.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{b.code}</td>
                    {isSiteAdmin && (
                      <td className="py-3 px-4 text-text-secondary text-xs">{b.organization_name || '—'}</td>
                    )}
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{b.phone || '—'}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3 text-[10px] text-text-muted">
                        <span>🚗 {b.vehicles_count || 0}</span>
                        <span>📡 {b.devices_count || 0}</span>
                        <span>👤 {b.drivers_count || 0}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={b.status === 'active' ? 'success' : 'muted'}>
                        {b.status === 'active' ? 'فعال' : 'غیرفعال'}
                      </Badge>
                    </td>
                    <td className="py-3 px-2">
                      <ActionMenu items={getMenuItems(b)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* مودال افزودن/ویرایش */}
      {(isSiteAdmin || isMainUser) && (
        <Modal
          open={modalOpen}
          onClose={() => {
            setModalOpen(false);
            setEditingBranch(null);
          }}
          title={editingBranch ? 'ویرایش شعبه' : 'افزودن شعبه'}
          size="lg"
          footer={
            <>
              <Button variant="secondary" onClick={() => {
                setModalOpen(false);
                setEditingBranch(null);
              }} disabled={saving}>
                انصراف
              </Button>
              <Button type="submit" form="add-branch-form" disabled={saving}>
                {saving ? 'در حال ذخیره...' : 'ذخیره'}
              </Button>
            </>
          }
        >
          <form id="add-branch-form" onSubmit={handleSubmit} className="space-y-4">

            {isSiteAdmin && (
              <Select
                label="شرکت"
                placeholder="انتخاب کنید..."
                value={form.organization}
                onChange={(e) => setForm({ ...form, organization: e.target.value })}
                options={orgOptions}
                required
              />
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="نام شعبه"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="مثلاً تهران"
                required
              />
              <Input
                label="کد شعبه"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="مثلاً THR-01"
                required
              />
              <Input
                label="تلفن"
                icon={Phone}
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="۰۲۱-xxxxxxxx"
              />
              <div>
                <label className="block text-sm text-text-secondary mb-2">وضعیت</label>
                <select
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-brand-500"
                >
                  <option value="active">فعال</option>
                  <option value="inactive">غیرفعال</option>
                </select>
              </div>
            </div>

            <Input
              label="آدرس"
              icon={MapPin}
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="آدرس کامل شعبه"
            />

          </form>
        </Modal>
      )}

    </div>
  );
}