import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Search, Plus, Cpu, Pencil, Trash2 , Hash, Phone, Eye, History, Activity,
} from 'lucide-react';
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
import AddDeviceModal from '../components/AddDeviceModal';
import DeviceHistoryModal from '../components/DeviceHistoryModal';
import { useAuth } from '../context/AuthContext';
import { useSearchParams } from 'react-router-dom';
import { devicesAPI } from '../api/services/fleet';
import { useApi } from '../hooks/useApi';

const managementStatusMap = {
  warehouse:    { label: 'در انبار',      variant: 'info'    },
  sold:         { label: 'فروخته شده',    variant: 'brand'   },
  installed:    { label: 'نصب شده',       variant: 'brand'   },
  active:       { label: 'فعال',          variant: 'success' },
  ready:        { label: 'آماده تعیین تکلیف', variant: 'info' },
  faulty:       { label: 'خراب',          variant: 'danger'  },
  lost:         { label: 'گمشده',         variant: 'warning' },
  stolen:       { label: 'سرقت شده',      variant: 'danger'  },
  disconnected: { label: 'قطع سرویس',     variant: 'muted'   },
  retired:      { label: 'بازنشسته',       variant: 'muted'   },
  disposed:     { label: 'امحاء شده',      variant: 'danger'  },
};

export default function Devices() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="دستگاه‌ها"
        subtitle="ثبت و مدیریت دستگاه‌ها با IMEI؛ شناسایی پروتکل به‌صورت خودکار"
      />
      <DevicesTab />
    </div>
  );
}

/* ═══════════════════════════════════════════════
   تب ۱ — دستگاه‌ها
   ═══════════════════════════════════════════════ */

function DevicesTab() {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterWarehouse, setFilterWarehouse] = useState('');
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editForm, setEditForm] = useState({ imei: '', sim_number: '' });
  const [deviceHistoryId, setDeviceHistoryId] = useState(null);

  const { isSiteAdmin, isPersonal } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const fetchDevices = useCallback(async () => {
    const result = await devicesAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const { data: devices, loading, error, refetch } = useApi(fetchDevices, []);
  const filtered = useMemo(() => {
    if (!devices) return [];
    return devices.filter((d) => {
      if (search && !d.imei.includes(search) &&
          !(d.sim_number && d.sim_number.includes(search)) &&
          !(d.vehicle_plate && d.vehicle_plate.includes(search))) return false;
      if (filterStatus && d.management_status !== filterStatus) return false;
      if (filterWarehouse === 'yes' && !d.is_in_warehouse) return false;
      if (filterWarehouse === 'no' && d.is_in_warehouse) return false;
      return true;
    });
  }, [devices, search, filterStatus, filterWarehouse]);

  const statusOptions = useMemo(() => {
    return Object.entries(managementStatusMap).map(([value, { label }]) => ({
      value, label,
    }));
  }, []);

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await devicesAPI.update(editingDevice.id, { imei: editForm.imei, sim_number: editForm.sim_number });
      setEditModalOpen(false);
      setEditingDevice(null);
      refetch();
    } catch (err) {
      console.error('Error updating device:', err);
      alert('خطا در ویرایش دستگاه');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (device) => {
    setEditingDevice(device);
    setEditForm({ imei: device.imei, sim_number: device.sim_number || '' });
    setEditModalOpen(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این دستگاه اطمینان دارید؟')) return;
    try {
      await devicesAPI.delete(id);
      refetch();
    } catch (err) {
      console.error('Error deleting device:', err);
      alert('خطا در حذف دستگاه');
    }
  };

  const focusRelatedDevice = (imei) => {
    if (!imei) return;
    setFilterStatus('');
    setFilterWarehouse('');
    setSearch(imei);
  };

  const getMenuItems = (device) => {
    const items = [
      {
        label: 'تاریخچه و رویدادها',
        icon: History,
        onClick: () => setDeviceHistoryId(device.id),
      },
    ];

    if (isSiteAdmin) {
      items.push({
        label: 'ویرایش',
        icon: Pencil,
        onClick: () => handleEdit(device),
      });
      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => handleDelete(device.id),
      });
    } else if (!isPersonal) {
      items.push({
        label: 'مشاهده جزئیات',
        icon: Eye,
        onClick: () => console.log('View device:', device.id),
      });
    }

    return items;
  };

  useEffect(() => {
    const deviceId = Number(searchParams.get('device'));
    const action = searchParams.get('action');
    if (!deviceId || !action || !devices?.length) return;

    const device = devices.find((item) => Number(item.id) === deviceId);
    if (!device) return;

    setSearchParams({}, { replace: true });
    if (action === 'history') {
      setDeviceHistoryId(device.id);
    } else if (action === 'edit') {
      handleEdit(device);
    }
  }, [devices, searchParams, setSearchParams]);

  if (loading) return <Card><LoadingSpinner /></Card>;
  if (error) return <Card><ErrorState error={error} onRetry={refetch} /></Card>;

  return (
    <div className="space-y-6">
      <Card>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            icon={Search}
            placeholder="جستجوی IMEI، شماره SIM یا پلاک..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Select
            placeholder="همه وضعیت‌ها"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            options={statusOptions}
          />
          <Select
            placeholder="همه دستگاه‌ها"
            value={filterWarehouse}
            onChange={(e) => setFilterWarehouse(e.target.value)}
            options={[
              { value: '', label: 'همه دستگاه‌ها' },
              { value: 'yes', label: 'فقط انبار' },
              { value: 'no', label: 'فقط تخصیص‌یافته' },
            ]}
          />
        </div>
      </Card>

      {isSiteAdmin && (
        <div className="flex justify-end">
          <Button icon={Plus} onClick={() => setAddModalOpen(true)}>
            افزودن دستگاه به انبار
          </Button>
        </div>
      )}

      <Card>
        {filtered.length === 0 ? (
          <EmptyState
            icon={Cpu}
            title="دستگاهی یافت نشد"
            description="هنوز دستگاهی ثبت نشده یا با فیلترهای فعلی مطابقت ندارد."
          />
        ) : (
          <div className="overflow-x-auto -m-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">IMEI</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">SIM</th>
                  {isSiteAdmin && (
                    <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">مشتری</th>
                  )}
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">قرارداد</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نوع ارتباط</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">خودرو</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت مدیریتی</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت دریافت داده</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((d) => {
                  const mgmt = managementStatusMap[d.management_status] || managementStatusMap.warehouse;
                  return (
                    <tr id={`device-row-${d.id}`} key={d.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 font-mono text-xs text-text-primary">
                          <Hash size={12} className="text-text-muted" />
                          {d.imei}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 font-mono text-xs text-text-secondary">
                          <Phone size={12} className="text-text-muted" />
                          {d.sim_number || '—'}
                        </div>
                      </td>
                      {isSiteAdmin && (
                        <td className="py-3 px-4 text-text-secondary text-xs">
                          {d.customer_name || (
                            <span className="text-text-muted">در انبار</span>
                          )}
                        </td>
                      )}
                      <td className="py-3 px-4">
                        {d.subscription_number ? (
                          <span className="font-mono text-text-primary text-xs">{d.subscription_number}</span>
                        ) : (
                          <span className="text-text-muted text-xs">—</span>
                        )}
                      </td>
                       <td className="py-3 px-4">
                         {d.replacement_device_imei ? (
                           <button type="button" onClick={() => focusRelatedDevice(d.replacement_device_imei)} title={d.replacement_relation_direction === 'replaced_by' ? `این دستگاه با IMEI ${d.replacement_device_imei} جایگزین شده است` : `این دستگاه جایگزین IMEI ${d.replacement_device_imei} است`} className="inline-flex items-center rounded-full border border-border-base px-2.5 py-1 text-xs text-text-primary hover:bg-bg-hover hover:border-brand/40 transition-colors cursor-pointer">
                             {d.subscription_device_type_display || 'جایگزین شده'}
                           </button>
                         ) : d.subscription_device_type_display ? (
                           <Badge variant={d.subscription_device_type === 'primary' ? 'muted' : 'brand'}>
                             {d.subscription_device_type_display}
                           </Badge>
                         ) : (
                           <span className="text-text-muted text-xs">—</span>
                         )}
                       </td>
                       <td className="py-3 px-4">
                         {d.vehicle_plate ? (
                           <span className="font-mono text-text-primary text-xs">{d.vehicle_plate}</span>
                         ) : (
                           <span className="text-text-muted text-xs">—</span>
                         )}
                       </td>
                      <td className="py-3 px-4">
                        <Badge variant={mgmt.variant}>{mgmt.label}</Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={d.data_active ? 'success' : 'muted'}>
                          <span className="inline-flex items-center gap-1.5">
                            <Activity size={12} />
                            {d.data_active ? 'دریافت داده فعال' : 'دریافت داده غیرفعال'}
                          </span>
                        </Badge>
                      </td>
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

      <DeviceHistoryModal
        open={Boolean(deviceHistoryId)}
        deviceId={deviceHistoryId}
        onClose={() => setDeviceHistoryId(null)}
        onOperationSaved={refetch}
      />

      {/* مودال افزودن */}
      <AddDeviceModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onSuccess={() => refetch()}
      />

      {/* مودال ویرایش */}
      {isSiteAdmin && (
        <Modal
          open={editModalOpen}
          onClose={() => {
            setEditModalOpen(false);
            setEditingDevice(null);
          }}
          title="ویرایش دستگاه"
          footer={
            <>
              <Button variant="secondary" onClick={() => {
                setEditModalOpen(false);
                setEditingDevice(null);
              }} disabled={saving}>
                انصراف
              </Button>
              <Button type="submit" form="edit-device-form" disabled={saving}>
                {saving ? 'در حال ذخیره...' : 'ذخیره'}
              </Button>
            </>
          }
        >
          <form id="edit-device-form" onSubmit={handleEditSubmit} className="space-y-4">
            <Input
              label="IMEI"
              value={editForm.imei}
              onChange={(e) => setEditForm({ ...editForm, imei: e.target.value })}
              placeholder="۱۵ رقم"
              required
            />
            <Input
              label="شماره SIM"
              value={editForm.sim_number}
              onChange={(e) => setEditForm({ ...editForm, sim_number: e.target.value })}
              placeholder="۰۹xxxxxxxxx"
            />
            <Input
              label="شماره SIM"
              value={editForm.sim_number}
              onChange={(e) => setEditForm({ ...editForm, sim_number: e.target.value })}
              placeholder="۰۹xxxxxxxxx"
            />
          </form>
        </Modal>
      )}
    </div>
  );
}
