import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Search, Plus, Cpu, Pencil, Trash2, Hash, Phone, Eye, History, Activity, Package,
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
import AddDeviceModal, { SearchablePicker } from '../components/AddDeviceModal';
import DeviceHistoryModal from '../components/DeviceHistoryModal';
import { useAuth } from '../context/AuthContext';
import { useSearchParams } from 'react-router-dom';
import { devicesAPI, deviceModelsAPI } from '../api/services/fleet';
import { useApi } from '../hooks/useApi';

const protocolLabelMap = {
  teltonika: 'Teltonika',
  gt06: 'GT06',
  'hq*': 'HQ',
};

const formatReceivedAt = (value) => {
  if (!value) return 'هنوز داده‌ای دریافت نشده';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'medium' });
};

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
  const [editForm, setEditForm] = useState({ imei: '', sim_number: '', manufacturer: '', device_model: '' });
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [editError, setEditError] = useState('');
  const [deviceHistoryId, setDeviceHistoryId] = useState(null);

  const { isSiteAdmin, isPersonal } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const fetchDevices = useCallback(async () => {
    const result = await devicesAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const { data: devices, loading, error, refetch } = useApi(
    fetchDevices,
    [],
    { keepDataOnRefetch: true },
  );

  // Keep the device table current while it is open; pause background polling
  // when the browser tab is hidden to avoid unnecessary API traffic.
  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const poll = async () => {
      if (!cancelled && document.visibilityState === 'visible') {
        try {
          await refetch();
        } catch {
          // useApi stores the error; the next poll will retry automatically.
        }
      }
      if (!cancelled) timer = window.setTimeout(poll, 5000);
    };

    timer = window.setTimeout(poll, 5000);
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [refetch]);
  const filtered = useMemo(() => {
    if (!devices) return [];
    return devices.filter((d) => {
      if (search && !d.imei.includes(search) &&
          !(d.sim_number && d.sim_number.includes(search)) &&
          !(d.device_model_manufacturer && d.device_model_manufacturer.toLowerCase().includes(search.toLowerCase())) &&
          !(d.device_model_name && d.device_model_name.toLowerCase().includes(search.toLowerCase())) &&
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

  useEffect(() => {
    if (!editModalOpen) return;
    let cancelled = false;
    setLoadingModels(true);
    deviceModelsAPI.list()
      .then((data) => {
        if (!cancelled) setModels(Array.isArray(data) ? data : (data.results || []));
      })
      .catch(() => {
        if (!cancelled) setEditError('دریافت فهرست برندها و مدل‌های Traccar ناموفق بود.');
      })
      .finally(() => {
        if (!cancelled) setLoadingModels(false);
      });
    return () => { cancelled = true; };
  }, [editModalOpen]);

  const brandOptions = useMemo(() => {
    return [...new Set(models.map((model) => model.manufacturer))]
      .sort((a, b) => a.localeCompare(b))
      .map((manufacturer) => ({ value: manufacturer, label: manufacturer }));
  }, [models]);

  const filteredModels = useMemo(() => {
    return models
      .filter((model) => model.manufacturer === editForm.manufacturer)
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((model) => ({ value: String(model.id), label: model.name }));
  }, [models, editForm.manufacturer]);

  const selectedModel = models.find((model) => String(model.id) === editForm.device_model);

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setEditError('');
    setSaving(true);
    try {
      await devicesAPI.update(editingDevice.id, {
        imei: editForm.imei.trim(),
        sim_number: editForm.sim_number.trim(),
        device_model: editForm.device_model ? Number(editForm.device_model) : null,
      });
      setEditModalOpen(false);
      setEditingDevice(null);
      await refetch();
    } catch (err) {
      console.error('Error updating device:', err);
      const errData = err.response?.data;
      if (errData) {
        const messages = Object.entries(errData)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value[0] : value}`)
          .join('\\n');
        setEditError(messages);
      } else {
        setEditError('خطا در ویرایش دستگاه. لطفاً دوباره تلاش کنید.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = async (device) => {
    setEditError('');
    setEditingDevice(device);
    setEditForm({
      imei: device.imei || '',
      sim_number: device.sim_number || '',
      manufacturer: device.device_model_manufacturer || '',
      device_model: '',
    });
    try {
      // The list serializer does not expose the related model ID; fetch detail
      // so models filled automatically from Traccar remain editable here.
      const detail = await devicesAPI.get(device.id);
      setEditingDevice(detail);
      setEditForm({
        imei: detail.imei || '',
        sim_number: detail.sim_number || '',
        manufacturer: detail.device_model_manufacturer || device.device_model_manufacturer || '',
        device_model: detail.device_model ? String(detail.device_model) : '',
      });
    } catch (err) {
      console.error('Error loading device details for editing:', err);
      // Keep the list values available if detail retrieval temporarily fails.
    }
    setEditModalOpen(true);
  };

  const handleDelete = async (device) => {
    if (!window.confirm(
      `هشدار: حذف دائمی دستگاه با IMEI ${device.imei} تمام سوابق و رویدادهای مرتبط را از دیتابیس حذف می‌کند. این کار قابل بازگشت نیست. ادامه می‌دهید؟`
    )) return;

    const confirmedImei = window.prompt(
      `برای تأیید نهایی، IMEI دستگاه را دقیقاً وارد کنید:\n${device.imei}`
    );
    if (confirmedImei === null || confirmedImei.trim() !== device.imei) {
      alert('IMEI واردشده مطابقت ندارد؛ حذف انجام نشد.');
      return;
    }

    try {
      await devicesAPI.delete(device.id, confirmedImei.trim());
      await refetch();
    } catch (err) {
      console.error('Error deleting device:', err);
      const detail = err.response?.data?.detail;
      alert(detail || 'خطا در حذف دستگاه؛ برای تشخیص، پاسخ درخواست DELETE را در Network بررسی کنید.');
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
        onClick: () => handleDelete(device),
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
      // The URL action intentionally opens a modal after the device list loads.
      // eslint-disable-next-line react-hooks/set-state-in-effect
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
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">برند / مدل دستگاه</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">SIM</th>
                  {isSiteAdmin && (
                    <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">مشتری</th>
                  )}
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">قرارداد</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نوع ارتباط</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">خودرو</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت مدیریتی</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">آخرین دریافت GPS</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت قرارداد داده</th>
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
                        <Badge variant={d.protocol ? 'brand' : 'muted'}>
                          {[
                            d.device_model_manufacturer,
                            d.device_model_name,
                          ].filter(Boolean).join(' - ') || protocolLabelMap[(d.protocol || '').toLowerCase()] || d.protocol || 'در انتظار شناسایی'}
                        </Badge>
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
                      <td className="py-3 px-4 text-xs text-text-secondary whitespace-nowrap" title={d.last_data_received_at || ''}>
                        <span className={d.last_data_received_at ? 'text-text-primary' : 'text-text-muted'}>
                          {formatReceivedAt(d.last_data_received_at)}
                        </span>
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
            {editError && (
              <div className="bg-danger/10 border border-danger/30 rounded-field p-3">
                <p className="text-xs text-danger whitespace-pre-line">{editError}</p>
              </div>
            )}

            <Input
              label="شناسه دستگاه (IMEI)"
              value={editForm.imei}
              onChange={(e) => setEditForm({ ...editForm, imei: e.target.value })}
              placeholder="IMEI دستگاه"
              icon={Hash}
              required
            />

            <SearchablePicker
              label="برند"
              value={editForm.manufacturer}
              onChange={(manufacturer) => setEditForm({ ...editForm, manufacturer, device_model: '' })}
              options={brandOptions}
              placeholder={loadingModels ? 'در حال دریافت فهرست...' : 'برای جستجو، نام برند را بنویسید یا از فهرست انتخاب کنید'}
              disabled={loadingModels || !brandOptions.length}
            />

            <SearchablePicker
              label="مدل دستگاه"
              value={editForm.device_model}
              onChange={(device_model) => setEditForm({ ...editForm, device_model })}
              options={filteredModels}
              placeholder={!editForm.manufacturer ? 'ابتدا برند را انتخاب کنید' : 'برای جستجو، نام مدل را بنویسید یا از فهرست انتخاب کنید'}
              disabled={!editForm.manufacturer || loadingModels || !filteredModels.length}
            />

            {selectedModel && (
              <div className="rounded-field border border-border-base bg-bg-subtle p-3 space-y-1">
                <p className="text-sm text-text-primary">پورت پیش‌فرض Traccar: <strong>{selectedModel.port ?? 'نامشخص'}</strong></p>
                <p className="text-xs text-text-secondary">پروتکل کاتالوگ: {selectedModel.protocol} · منبع: فهرست رسمی Traccar</p>
                <p className="text-xs text-text-secondary">این پورت، مقدار پیش‌فرض مستندشده است و ممکن است با تنظیمات سرور متفاوت باشد.</p>
              </div>
            )}

            <Input
              label="شماره سیم‌کارت (اختیاری)"
              value={editForm.sim_number}
              onChange={(e) => setEditForm({ ...editForm, sim_number: e.target.value })}
              placeholder="شماره سیم‌کارت را وارد کنید"
              icon={Phone}
              inputMode="tel"
            />

            <div className="bg-info/10 border border-info/30 rounded-field p-3 flex items-start gap-2">
              <Package size={16} className="text-info flex-shrink-0 mt-0.5" />
              <p className="text-xs text-text-secondary leading-relaxed">
                فقط شناسه دستگاه (IMEI) برای ثبت اجباری است. برند و مدل اختیاری‌اند؛ اگر Traccar مدل معتبر و قابل تطبیقی گزارش کند، سانا می‌تواند اطلاعات مدل را تکمیل کند. اگر Traccar مدل را گزارش نکند یا تطبیق مطمئن نباشد، اطلاعات خالی می‌ماند و حدس زده نمی‌شود. مدل انتخاب‌شده نیز قابل تغییر یا پاک کردن است.
              </p>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
