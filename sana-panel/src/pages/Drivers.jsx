import { useState, useMemo, useCallback, useEffect } from 'react';
import { Search, Plus, Users, Pencil, Trash2, Phone, CreditCard, Eye } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Select from '../components/Select';
import Modal from '../components/Modal';
import EmptyState from '../components/EmptyState';
import ActionMenu from '../components/ActionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { useAuth } from '../context/AuthContext';
import { driversAPI } from '../api/services/fleet';
import { branchesAPI } from '../api/services/organizations';
import { useApi } from '../hooks/useApi';
import { toJalali } from '../utils/dateUtils';

const positions = [
  { value: 'driver',     label: 'راننده' },
  { value: 'senior',     label: 'راننده ارشد' },
  { value: 'supervisor', label: 'سرپرست رانندگان' },
];

const licenseTypes = [
  { value: 'base2',   label: 'پایه دوم' },
  { value: 'base1',   label: 'پایه اول' },
  { value: 'special', label: 'ویژه' },
  { value: 'heavy',   label: 'تخصصی سنگین' },
];

export default function Drivers() {
  const [search, setSearch] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [filterPosition, setFilterPosition] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingDriver, setEditingDriver] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    first_name: '', last_name: '', national_id: '', mobile: '',
    personnel_code: '', position: 'driver',
    license_number: '', license_type: '', license_expiry: '',
    branch: '',
  });

  const { isBranchManager, isMainUser } = useAuth();

  const fetchDrivers = useCallback(async () => {
    const result = await driversAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const fetchBranches = useCallback(async () => {
    try {
      const result = await branchesAPI.list();
      return Array.isArray(result) ? result : result.results || [];
    } catch {
      return [];
    }
  }, []);

  const { data: drivers, loading, error, refetch } = useApi(fetchDrivers, []);
  const { data: branches } = useApi(fetchBranches, []);

  const filtered = useMemo(() => {
    if (!drivers) return [];
    return drivers.filter((d) => {
      const fullName = `${d.first_name} ${d.last_name}`;
      if (search && !fullName.includes(search) &&
          !(d.mobile && d.mobile.includes(search)) &&
          !(d.personnel_code && d.personnel_code.includes(search))) return false;
      if (filterBranch && d.branch !== Number(filterBranch)) return false;
      if (filterPosition && d.position !== filterPosition) return false;
      return true;
    });
  }, [drivers, search, filterBranch, filterPosition]);

  const branchOptions = useMemo(() => {
    return (branches || []).map((b) => ({ value: b.id, label: b.name }));
  }, [branches]);

  // اگه Branch Manager بود، شعبه‌اش رو پیش‌فرض کن
  useEffect(() => {
    if (isBranchManager && branches?.length === 1 && !form.branch) {
      setForm((f) => ({ ...f, branch: branches[0].id }));
    }
  }, [isBranchManager, branches]); // eslint-disable-line react-hooks/exhaustive-deps

  const canEdit = isMainUser || isBranchManager;
  const showBranchColumn = isMainUser;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        first_name: form.first_name,
        last_name: form.last_name,
        national_id: form.national_id,
        mobile: form.mobile,
        personnel_code: form.personnel_code,
        position: form.position,
        license_number: form.license_number,
        license_type: form.license_type,
        license_expiry: form.license_expiry || null,
        branch: form.branch || null,
      };

      if (editingDriver) {
        await driversAPI.update(editingDriver.id, payload);
      } else {
        await driversAPI.create(payload);
      }

      setModalOpen(false);
      setEditingDriver(null);
      resetForm();
      refetch();
    } catch (err) {
      console.error('Error saving driver:', err);
      const errData = err.response?.data;
      const errMsg = errData
        ? Object.entries(errData).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'لطفاً دوباره تلاش کنید';
      alert('خطا در ذخیره راننده:\n' + errMsg);
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setForm({
      first_name: '', last_name: '', national_id: '', mobile: '',
      personnel_code: '', position: 'driver',
      license_number: '', license_type: '', license_expiry: '',
      branch: isBranchManager && branches?.[0]?.id || '',
    });
  };

  const handleEdit = (driver) => {
    setEditingDriver(driver);
    setForm({
      first_name: driver.first_name,
      last_name: driver.last_name,
      national_id: driver.national_id || '',
      mobile: driver.mobile,
      personnel_code: driver.personnel_code || '',
      position: driver.position,
      license_number: driver.license_number || '',
      license_type: driver.license_type || '',
      license_expiry: driver.license_expiry || '',
      branch: driver.branch || '',
    });
    setModalOpen(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این راننده اطمینان دارید؟')) return;
    try {
      await driversAPI.delete(id);
      refetch();
    } catch (err) {
      console.error('Error deleting driver:', err);
      alert('خطا در حذف راننده');
    }
  };

  const getMenuItems = (driver) => {
    const items = [];

    if (canEdit) {
      items.push({
        label: 'ویرایش',
        icon: Pencil,
        onClick: () => handleEdit(driver),
      });
      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => handleDelete(driver.id),
      });
    } else {
      items.push({
        label: 'مشاهده',
        icon: Eye,
        onClick: () => console.log('View driver:', driver.id),
      });
    }

    return items;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="رانندگان" subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="رانندگان" subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader
        title="رانندگان"
        subtitle={`${filtered.length} راننده ثبت شده`}
        actions={
          canEdit ? (
            <Button icon={Plus} onClick={() => {
              setEditingDriver(null);
              resetForm();
              setModalOpen(true);
            }}>
              افزودن راننده
            </Button>
          ) : null
        }
      />

      <Card>
        <div className={`grid grid-cols-1 gap-4 ${
          showBranchColumn ? 'md:grid-cols-3' : 'md:grid-cols-2'
        }`}>
          <Input
            icon={Search}
            placeholder="جستجوی نام، موبایل یا کد پرسنلی..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {showBranchColumn && (
            <Select
              placeholder="همه شعبه‌ها"
              value={filterBranch}
              onChange={(e) => setFilterBranch(e.target.value)}
              options={branchOptions}
            />
          )}
          <Select
            placeholder="همه سمت‌ها"
            value={filterPosition}
            onChange={(e) => setFilterPosition(e.target.value)}
            options={positions}
          />
        </div>
      </Card>

      <Card>
        {filtered.length === 0 ? (
          <EmptyState
            icon={Users}
            title="راننده‌ای یافت نشد"
            description="هنوز راننده‌ای ثبت نشده یا با فیلترهای فعلی مطابقت ندارد."
          />
        ) : (
          <div className="overflow-x-auto -m-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نام</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">تماس</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">سمت</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">گواهینامه</th>
                  {showBranchColumn && (
                    <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">شعبه</th>
                  )}
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((d) => {
                  const positionLabel = positions.find((p) => p.value === d.position)?.label || d.position;

                  return (
                    <tr
                      key={d.id}
                      className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-brand-900/40 flex items-center justify-center text-brand-400 font-bold text-xs flex-shrink-0">
                            {d.first_name?.[0] || 'ر'}
                          </div>
                          <div>
                            <div className="font-medium text-text-primary">
                              {d.full_name || `${d.first_name} ${d.last_name}`}
                            </div>
                            <div className="text-[10px] text-text-muted font-mono">
                              {d.personnel_code || '—'}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 text-text-secondary font-mono text-xs">
                          <Phone size={12} className="text-text-muted" />
                          {d.mobile}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-text-secondary text-xs">{positionLabel}</td>
                      <td className="py-3 px-4">
                        {d.license_number ? (
                          <>
                            <div className="flex items-center gap-1.5 text-text-secondary font-mono text-xs">
                              <CreditCard size={12} className="text-text-muted" />
                              {d.license_number}
                            </div>
                            {d.license_expiry && (
                              <div className="text-[10px] text-text-muted mt-0.5">
                                انقضا: {toJalali(d.license_expiry)}
                              </div>
                            )}
                          </>
                        ) : (
                          <span className="text-text-muted text-xs">—</span>
                        )}
                      </td>
                      {showBranchColumn && (
                        <td className="py-3 px-4 text-text-secondary text-xs">
                          {d.branch_name || '—'}
                        </td>
                      )}
                      <td className="py-3 px-2">
                        <ActionMenu items={getMenuItems(d)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {canEdit && (
        <Modal
          open={modalOpen}
          onClose={() => {
            setModalOpen(false);
            setEditingDriver(null);
          }}
          title={editingDriver ? 'ویرایش راننده' : 'افزودن راننده'}
          size="lg"
          footer={
            <>
              <Button variant="secondary" onClick={() => {
                setModalOpen(false);
                setEditingDriver(null);
              }} disabled={saving}>
                انصراف
              </Button>
              <Button type="submit" form="add-driver-form" disabled={saving}>
                {saving ? 'در حال ذخیره...' : 'ذخیره'}
              </Button>
            </>
          }
        >
          <form id="add-driver-form" onSubmit={handleSubmit} className="space-y-5">

            <div>
              <h4 className="text-xs font-medium text-text-muted mb-3">اطلاعات هویتی</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="نام"
                  value={form.first_name}
                  onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                  required
                />
                <Input
                  label="نام خانوادگی"
                  value={form.last_name}
                  onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  required
                />
                <Input
                  label="کد ملی"
                  value={form.national_id}
                  onChange={(e) => setForm({ ...form, national_id: e.target.value })}
                  placeholder="۱۰ رقم"
                />
                <Input
                  label="موبایل"
                  value={form.mobile}
                  onChange={(e) => setForm({ ...form, mobile: e.target.value })}
                  placeholder="۰۹xxxxxxxxx"
                  required
                />
              </div>
            </div>

            <div className="border-t border-border-base" />

            <div>
              <h4 className="text-xs font-medium text-text-muted mb-3">اطلاعات استخدامی</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="کد پرسنلی"
                  value={form.personnel_code}
                  onChange={(e) => setForm({ ...form, personnel_code: e.target.value })}
                />
                <Select
                  label="سمت"
                  placeholder="انتخاب کنید..."
                  value={form.position}
                  onChange={(e) => setForm({ ...form, position: e.target.value })}
                  options={positions}
                />
                {isMainUser && (
                  <Select
                    label="شعبه (اختیاری)"
                    placeholder="انتخاب کنید..."
                    value={form.branch}
                    onChange={(e) => setForm({ ...form, branch: e.target.value })}
                    options={branchOptions}
                  />
                )}
              </div>
            </div>

            <div className="border-t border-border-base" />

            <div>
              <h4 className="text-xs font-medium text-text-muted mb-3">اطلاعات گواهینامه</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  label="شماره گواهینامه"
                  value={form.license_number}
                  onChange={(e) => setForm({ ...form, license_number: e.target.value })}
                />
                <Select
                  label="نوع گواهینامه"
                  placeholder="انتخاب کنید..."
                  value={form.license_type}
                  onChange={(e) => setForm({ ...form, license_type: e.target.value })}
                  options={licenseTypes}
                />
                <JalaliDatePicker
                  label="تاریخ انقضا"
                  value={form.license_expiry}
                  onChange={(val) => setForm({ ...form, license_expiry: val })}
                />
              </div>
            </div>

          </form>
        </Modal>
      )}

    </div>
  );
}