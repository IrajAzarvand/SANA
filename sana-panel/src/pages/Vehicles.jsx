import { useState, useMemo, useCallback, useEffect } from 'react';
import { Search, Plus, Truck, Pencil, Trash2, Eye } from 'lucide-react';
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
import { vehiclesAPI, vehicleTypesAPI } from '../api/services/fleet';
import { branchesAPI } from '../api/services/organizations';
import { useApi } from '../hooks/useApi';

const deviceStatusMap = {
  active:       { label: 'آنلاین',      variant: 'success' },
  offline:      { label: 'آفلاین',      variant: 'muted'   },
  faulty:       { label: 'خراب',        variant: 'danger'  },
  sold:         { label: 'فروخته شده',  variant: 'info'    },
  installed:    { label: 'نصب شده',     variant: 'brand'   },
  lost:         { label: 'گمشده',       variant: 'warning' },
  stolen:       { label: 'سرقت شده',    variant: 'danger'  },
  disconnected: { label: 'قطع سرویس',   variant: 'muted'   },
  none:         { label: 'بدون دستگاه', variant: 'neutral' },
};

export default function Vehicles() {
  const [search, setSearch] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [filterType, setFilterType] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    plate: '', vehicle_type: '', branch: '',
  });

  const { isPersonal, isSiteAdmin, isMainUser, isBranchManager } = useAuth();

  // Fetch
  const fetchVehicles = useCallback(async () => {
    const result = await vehiclesAPI.list();
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

  const fetchVehicleTypes = useCallback(async () => {
    try {
      const result = await vehicleTypesAPI.list();
      return Array.isArray(result) ? result : result.results || [];
    } catch {
      return [];
    }
  }, []);

  const { data: vehicles, loading, error, refetch } = useApi(fetchVehicles, []);
  const { data: branches } = useApi(fetchBranches, []);
  const { data: vehicleTypes } = useApi(fetchVehicleTypes, []);

  // فیلتر
  const filtered = useMemo(() => {
    if (!vehicles) return [];
    return vehicles.filter((v) => {
      if (search && !v.plate.includes(search)) return false;
      if (filterBranch && v.branch !== Number(filterBranch)) return false;
      if (filterType && v.vehicle_type !== Number(filterType)) return false;
      return true;
    });
  }, [vehicles, search, filterBranch, filterType]);

  // آپشن‌ها
  const branchOptions = useMemo(() => {
    return (branches || []).map((b) => ({ value: b.id, label: b.name }));
  }, [branches]);

  const typeOptions = useMemo(() => {
    return (vehicleTypes || []).map((t) => ({ value: t.id, label: t.name }));
  }, [vehicleTypes]);

  // اگه Branch Manager بود، شعبه‌اش رو پیش‌فرض کن
  useEffect(() => {
    if (isBranchManager && branches?.length === 1 && !form.branch) {
      setForm((f) => ({ ...f, branch: branches[0].id }));
    }
  }, [isBranchManager, branches]); // eslint-disable-line react-hooks/exhaustive-deps

  const canCreate = isMainUser || isBranchManager;
  const showBranchColumn = isMainUser;

  // ذخیره
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        plate: form.plate,
        vehicle_type: form.vehicle_type || null,
        branch: form.branch || null,
      };

      if (editingVehicle) {
        await vehiclesAPI.update(editingVehicle.id, payload);
      } else {
        await vehiclesAPI.create(payload);
      }

      setModalOpen(false);
      setEditingVehicle(null);
      setForm({
        plate: '',
        vehicle_type: '',
        branch: isBranchManager && branches?.[0]?.id || '',
      });
      refetch();
    } catch (err) {
      console.error('Error saving vehicle:', err);
      const errData = err.response?.data;
      const errMsg = errData
        ? Object.entries(errData).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'لطفاً دوباره تلاش کنید';
      alert('خطا در ذخیره خودرو:\n' + errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (vehicle) => {
    setEditingVehicle(vehicle);
    setForm({
      plate: vehicle.plate,
      vehicle_type: vehicle.vehicle_type || '',
      branch: vehicle.branch || '',
    });
    setModalOpen(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این خودرو اطمینان دارید؟')) return;
    try {
      await vehiclesAPI.delete(id);
      refetch();
    } catch (err) {
      console.error('Error deleting vehicle:', err);
      alert('خطا در حذف خودرو');
    }
  };

  const getMenuItems = (vehicle) => {
    const items = [];

    if (isMainUser || isBranchManager) {
      items.push({
        label: 'ویرایش',
        icon: Pencil,
        onClick: () => handleEdit(vehicle),
      });
    }

    // حذف برای شرکت و شعبه هم مجاز (چون خودشون خودرو رو خریدن)
    if (isMainUser || isBranchManager) {
      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => handleDelete(vehicle.id),
      });
    }

    if (isPersonal) {
      items.push({
        label: 'مشاهده جزئیات',
        icon: Eye,
        onClick: () => console.log('View vehicle:', vehicle.id),
      });
    }

    return items;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="خودروها" subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="خودروها" subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader
        title={isPersonal ? 'خودروهای من' : 'خودروها'}
        subtitle={
          isPersonal
            ? `مشاهده خودروهای شخصی — ${filtered.length} خودرو`
            : `مدیریت خودروهای ناوگان — ${filtered.length} خودرو`
        }
        actions={
          canCreate ? (
            <Button icon={Plus} onClick={() => {
              setEditingVehicle(null);
              setForm({
                plate: '',
                vehicle_type: '',
                branch: isBranchManager && branches?.[0]?.id || '',
              });
              setModalOpen(true);
            }}>
              افزودن خودرو
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
            placeholder="جستجوی پلاک..."
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
            placeholder="همه انواع"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            options={typeOptions}
          />
        </div>
      </Card>

      <Card>
        {filtered.length === 0 ? (
          <EmptyState
            icon={Truck}
            title="خودرویی یافت نشد"
            description="هنوز خودرویی ثبت نشده یا با فیلترهای فعلی مطابقت ندارد."
          />
        ) : (
          <div className="overflow-x-auto -m-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">پلاک</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نوع</th>
                  {showBranchColumn && (
                    <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">شعبه</th>
                  )}
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">دستگاه</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((v) => {
                  const devStatus = deviceStatusMap[v.device_status] || deviceStatusMap.none;
                  return (
                    <tr
                      key={v.id}
                      className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors"
                    >
                      <td className="py-3 px-4">
                        <span className="font-mono font-medium text-text-primary">{v.plate}</span>
                      </td>
                      <td className="py-3 px-4 text-text-secondary">{v.vehicle_type_name || '—'}</td>
                      {showBranchColumn && (
                        <td className="py-3 px-4 text-text-secondary">{v.branch_name || '—'}</td>
                      )}
                      <td className="py-3 px-4">
                        <Badge variant={devStatus.variant}>{devStatus.label}</Badge>
                      </td>
                      <td className="py-3 px-2">
                        <ActionMenu items={getMenuItems(v)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* مودال */}
      {canCreate && (
        <Modal
          open={modalOpen}
          onClose={() => {
            setModalOpen(false);
            setEditingVehicle(null);
          }}
          title={editingVehicle ? 'ویرایش خودرو' : 'افزودن خودرو'}
          footer={
            <>
              <Button variant="secondary" onClick={() => {
                setModalOpen(false);
                setEditingVehicle(null);
              }} disabled={saving}>
                انصراف
              </Button>
              <Button type="submit" form="add-vehicle-form" disabled={saving}>
                {saving ? 'در حال ذخیره...' : 'ذخیره'}
              </Button>
            </>
          }
        >
          <form id="add-vehicle-form" onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="پلاک خودرو"
              placeholder="مثلاً ۱۲ب۳۴۵۶۷"
              value={form.plate}
              onChange={(e) => setForm({ ...form, plate: e.target.value })}
              required
            />
            <Select
              label="نوع خودرو"
              placeholder="انتخاب کنید..."
              value={form.vehicle_type}
              onChange={(e) => setForm({ ...form, vehicle_type: e.target.value })}
              options={typeOptions}
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
          </form>
        </Modal>
      )}

    </div>
  );
}