import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Search, Plus, Cpu, Pencil, Trash2 , Hash, Phone, Eye, Boxes, History,
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
import Tabs from '../components/Tabs';
import AddDeviceModal from '../components/AddDeviceModal';
import DeviceHistoryModal from '../components/DeviceHistoryModal';
import { useAuth } from '../context/AuthContext';
import { useSearchParams } from 'react-router-dom';
import { devicesAPI } from '../api/services/fleet';
import { deviceModelsAPI } from '../api/services/deviceModels';
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
  const [activeTab, setActiveTab] = useState('devices');
  const { isSiteAdmin } = useAuth();

  return (
    <div className="space-y-6">
      <PageHeader
        title="دستگاه‌ها"
        subtitle="مدیریت دستگاه‌های GPS و مدل‌های آن‌ها"
      />

      <Card>
        <Tabs
          activeTab={activeTab}
          onChange={setActiveTab}
          tabs={[
            { value: 'devices', label: 'دستگاه‌ها' },
            ...(isSiteAdmin
              ? [{ value: 'models', label: 'مدل‌های دستگاه' }]
              : []),
          ]}
        />
      </Card>

      {activeTab === 'devices' && <DevicesTab />}
      {activeTab === 'models' && isSiteAdmin && <DeviceModelsTab />}
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
  const [editForm, setEditForm] = useState({
    imei: '', device_model: '', sim_number: '',
  });
  const [deviceHistoryId, setDeviceHistoryId] = useState(null);

  const { isSiteAdmin, isPersonal } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const fetchDevices = useCallback(async () => {
    const result = await devicesAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const fetchModels = useCallback(async () => {
    try {
      const result = await deviceModelsAPI.list();
      return Array.isArray(result) ? result : result.results || [];
    } catch {
      return [];
    }
  }, []);

  const { data: devices, loading, error, refetch } = useApi(fetchDevices, []);
  const { data: deviceModels } = useApi(fetchModels, []);

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

  const modelOptions = useMemo(() => {
    return (deviceModels || []).map((m) => ({
      value: m.id,
      label: `${m.manufacturer} ${m.name}`,
    }));
  }, [deviceModels]);

  const statusOptions = useMemo(() => {
    return Object.entries(managementStatusMap).map(([value, { label }]) => ({
      value, label,
    }));
  }, []);

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await devicesAPI.update(editingDevice.id, editForm);
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
    setEditForm({
      imei: device.imei,
      device_model: device.device_model || '',
      sim_number: device.sim_number || '',
    });
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
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">مدل</th>
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
                  const modelLabel = d.device_model_manufacturer && d.device_model_name
                    ? `${d.device_model_manufacturer} ${d.device_model_name}`
                    : '—';

                  return (
                    <tr id={`device-row-${d.id}`} key={d.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5 font-mono text-xs text-text-primary">
                          <Hash size={12} className="text-text-muted" />
                          {d.imei}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-text-secondary text-xs">{modelLabel}</td>
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
            <Select
              label="مدل دستگاه"
              placeholder="انتخاب کنید..."
              value={editForm.device_model}
              onChange={(e) => setEditForm({ ...editForm, device_model: e.target.value })}
              options={modelOptions}
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

/* ═══════════════════════════════════════════════
   تب ۲ — مدل‌های دستگاه
   ═══════════════════════════════════════════════ */

function DeviceModelsTab() {
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    manufacturer: '', name: '', code: '', protocol: '',
  });

  const { isSiteAdmin } = useAuth();

  const fetchModels = useCallback(async () => {
    const result = await deviceModelsAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const { data: models, loading, error, refetch } = useApi(fetchModels, []);

  const filtered = useMemo(() => {
    if (!models) return [];
    if (!search) return models;
    return models.filter((m) =>
      m.name.includes(search) ||
      m.manufacturer.includes(search) ||
      m.code.includes(search) ||
      m.protocol.includes(search)
    );
  }, [models, search]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editingModel) {
        await deviceModelsAPI.update(editingModel.id, form);
      } else {
        await deviceModelsAPI.create(form);
      }
      setModalOpen(false);
      setEditingModel(null);
      setForm({ manufacturer: '', name: '', code: '', protocol: '' });
      refetch();
    } catch (err) {
      console.error('Error saving model:', err);
      const errData = err.response?.data;
      const errMsg = errData
        ? Object.entries(errData).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'لطفاً دوباره تلاش کنید';
      alert('خطا در ذخیره مدل:\n' + errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (model) => {
    setEditingModel(model);
    setForm({
      manufacturer: model.manufacturer,
      name: model.name,
      code: model.code,
      protocol: model.protocol,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('آیا از حذف این مدل اطمینان دارید؟')) return;
    try {
      await deviceModelsAPI.delete(id);
      refetch();
    } catch (err) {
      console.error('Error deleting model:', err);
      const errMsg = err.response?.data?.detail || 'خطا در حذف مدل. ممکنه دستگاه‌هایی از این مدل استفاده کنن.';
      alert(errMsg);
    }
  };

  const getMenuItems = (model) => [
    {
      label: 'ویرایش',
      icon: Pencil,
      onClick: () => handleEdit(model),
    },
    {
      label: 'حذف',
      icon: Trash2,
      variant: 'danger',
      onClick: () => handleDelete(model.id),
    },
  ];

  if (loading) return <Card><LoadingSpinner /></Card>;
  if (error) return <Card><ErrorState error={error} onRetry={refetch} /></Card>;

  return (
    <div className="space-y-6">
      <Card>
        <Input
          icon={Search}
          placeholder="جستجوی نام، سازنده، کد یا پروتکل..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Card>

      {isSiteAdmin && (
        <div className="flex justify-end">
          <Button icon={Plus} onClick={() => {
            setEditingModel(null);
            setForm({ manufacturer: '', name: '', code: '', protocol: '' });
            setModalOpen(true);
          }}>
            افزودن مدل جدید
          </Button>
        </div>
      )}

      <Card>
        {filtered.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="مدلی یافت نشد"
            description="هنوز مدلی ثبت نشده یا با فیلترهای فعلی مطابقت ندارد."
          />
        ) : (
          <div className="overflow-x-auto -m-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">سازنده</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نام</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">کد</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">پروتکل</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">تعداد دستگاه</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((m) => (
                  <tr key={m.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                    <td className="py-3 px-4 text-text-primary">{m.manufacturer}</td>
                    <td className="py-3 px-4 text-text-primary">{m.name}</td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{m.code}</td>
                    <td className="py-3 px-4">
                      <Badge variant="brand">{m.protocol}</Badge>
                    </td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">
                      {m.devices_count || 0}
                    </td>
                    <td className="py-3 px-2">
                      {isSiteAdmin && <ActionMenu items={getMenuItems(m)} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {isSiteAdmin && (
        <Modal
          open={modalOpen}
          onClose={() => {
            setModalOpen(false);
            setEditingModel(null);
          }}
          title={editingModel ? 'ویرایش مدل' : 'افزودن مدل جدید'}
          footer={
            <>
              <Button variant="secondary" onClick={() => {
                setModalOpen(false);
                setEditingModel(null);
              }} disabled={saving}>
                انصراف
              </Button>
              <Button type="submit" form="add-model-form" disabled={saving}>
                {saving ? 'در حال ذخیره...' : 'ذخیره'}
              </Button>
            </>
          }
        >
          <form id="add-model-form" onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="سازنده"
              value={form.manufacturer}
              onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
              placeholder="مثلاً Teltonika"
              required
            />
            <Input
              label="نام مدل"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="مثلاً FMB920"
              required
            />
            <Input
              label="کد مدل"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
              placeholder="مثلاً FMB920"
            />
            <Input
              label="پروتکل"
              value={form.protocol}
              onChange={(e) => setForm({ ...form, protocol: e.target.value })}
              placeholder="مثلاً teltonika"
            />
          </form>
        </Modal>
      )}
    </div>
  );
}