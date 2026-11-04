import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Search, Plus, Cpu, Pencil, Trash2, Hash, Phone, Eye, History, Activity, Package, Truck,
} from 'lucide-react';
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
    <div className="space-y-4">
      <header className="flex shrink-0 items-center gap-3">
        <div className="min-w-0">
          <h1 className="text-base font-semibold text-text-primary sm:text-lg">دستگاه‌ها</h1>
          <p className="mt-0.5 text-[11px] text-text-muted sm:text-xs">
            ثبت، جستجو و مدیریت دستگاه‌های GPS
          </p>
        </div>
      </header>
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
  const [editModelLoaded, setEditModelLoaded] = useState(false);
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

  // With a brand selected, limit models to that brand; otherwise show every model
  // so the user can pick by model name first and have the brand filled in.
  const filteredModels = useMemo(() => {
    const list = editForm.manufacturer
      ? models.filter((model) => model.manufacturer === editForm.manufacturer)
      : models;
    return list
      .sort((a, b) => {
        const byName = a.name.localeCompare(b.name);
        return byName !== 0 ? byName : a.manufacturer.localeCompare(b.manufacturer);
      })
      .map((model) => ({
        value: String(model.id),
        label: editForm.manufacturer ? model.name : `${model.name} — ${model.manufacturer}`,
      }));
  }, [models, editForm.manufacturer]);

  const selectedModel = models.find((model) => String(model.id) === editForm.device_model);

  const handleEditBrandChange = (manufacturer) => {
    setEditForm((prev) => {
      const current = models.find((model) => String(model.id) === prev.device_model);
      const keepModel = current && (!manufacturer || current.manufacturer === manufacturer);
      return {
        ...prev,
        manufacturer,
        device_model: keepModel ? prev.device_model : '',
      };
    });
  };

  const handleEditModelChange = (device_model) => {
    const model = models.find((item) => String(item.id) === String(device_model));
    setEditForm((prev) => ({
      ...prev,
      device_model,
      manufacturer: model?.manufacturer || prev.manufacturer,
    }));
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setEditError('');
    setSaving(true);
    try {
      const payload = {
        imei: editForm.imei.trim(),
        sim_number: editForm.sim_number.trim(),
      };
      // If detail loading failed, do not accidentally clear the existing model.
      // A selected replacement is still safe to submit explicitly.
      if (editForm.device_model) {
        payload.device_model = Number(editForm.device_model);
      } else if (editModelLoaded) {
        payload.device_model = null;
      }
      await devicesAPI.update(editingDevice.id, payload);
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
    setEditModelLoaded(false);
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
      setEditModelLoaded(true);
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
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <DeviceMetric label="کل دستگاه‌ها" value={devices.length} icon={Cpu} />
        <DeviceMetric label="دریافت داده فعال" value={devices.filter((d) => d.data_active).length} icon={Activity} />
        <DeviceMetric label="در انبار" value={devices.filter((d) => d.is_in_warehouse).length} icon={Package} />
        <DeviceMetric label="تخصیص‌یافته" value={devices.filter((d) => !d.is_in_warehouse).length} icon={Truck} />
      </div>

      <Card>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4 xl:items-center">
          <div className="xl:col-span-2">
            <Input
              icon={Search}
              placeholder="جستجوی IMEI، شماره SIM، مدل یا پلاک..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div title="وضعیت مدیریتی">
            <Select
              placeholder="همه وضعیت‌ها"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              options={statusOptions}
            />
          </div>
          <div className="flex min-w-0 gap-2">
            <div
              className="min-w-0 flex-1"
              title="محل استقرار"
            >
              <Select
                value={filterWarehouse}
                onChange={(e) => setFilterWarehouse(e.target.value)}
                options={[
                  { value: '', label: 'همه دستگاه‌ها' },
                  { value: 'yes', label: 'فقط انبار' },
                  { value: 'no', label: 'فقط تخصیص‌یافته' },
                ]}
              />
            </div>
            {isSiteAdmin && (
              <Button icon={Plus} onClick={() => setAddModalOpen(true)} size="md">
                <span className="hidden 2xl:inline">افزودن دستگاه</span>
                <span className="2xl:hidden">افزودن</span>
              </Button>
            )}
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-border-base pt-3 text-[11px] text-text-muted">
          <span>نمایش {filtered.length.toLocaleString('fa-IR')} از {devices.length.toLocaleString('fa-IR')} دستگاه</span>
          {(search || filterStatus || filterWarehouse) && (
            <button
              type="button"
              onClick={() => { setSearch(''); setFilterStatus(''); setFilterWarehouse(''); }}
              className="text-brand-400 transition-colors hover:text-brand-300"
            >
              پاک‌کردن فیلترها
            </button>
          )}
        </div>
      </Card>

      <Card
        title="فهرست دستگاه‌ها"
        subtitle="اطلاعات شناسایی، تخصیص و وضعیت دریافت داده"
        action={<span className="rounded-full bg-bg-base px-2.5 py-1 text-xs text-text-secondary">{filtered.length.toLocaleString('fa-IR')} دستگاه</span>}
      >
        {filtered.length === 0 ? (
          <EmptyState
            icon={Cpu}
            title="دستگاهی یافت نشد"
            description="هنوز دستگاهی ثبت نشده یا با فیلترهای فعلی مطابقت ندارد."
          />
        ) : (
          <>
          <div className="grid grid-cols-1 gap-3 sm:hidden">
            {filtered.map((d) => {
              const mgmt = managementStatusMap[d.management_status] || managementStatusMap.warehouse;
              return (
                <article id={`device-card-${d.id}`} key={d.id} className="rounded-card border border-border-base bg-bg-base p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 font-mono text-sm font-semibold text-text-primary"><Hash size={13} className="text-text-muted" />{d.imei}</div>
                      <div className="mt-2"><Badge variant={d.protocol ? 'brand' : 'muted'}>{[d.device_model_manufacturer,d.device_model_name].filter(Boolean).join(' - ') || protocolLabelMap[(d.protocol || '').toLowerCase()] || d.protocol || 'در انتظار شناسایی'}</Badge></div>
                    </div>
                    <ActionMenu items={getMenuItems(d)} />
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-3 border-t border-border-base pt-3 text-xs">
                    <div><div className="text-text-muted">SIM</div><div className="mt-1 font-mono text-text-primary">{d.sim_number || '—'}</div></div>
                    {isSiteAdmin && <div><div className="text-text-muted">مشتری</div><div className="mt-1 text-text-primary">{d.customer_name || 'در انبار'}</div></div>}
                    <div><div className="text-text-muted">قرارداد</div><div className="mt-1 font-mono text-text-primary">{d.subscription_number || '—'}</div></div>
                    <div><div className="text-text-muted">نوع ارتباط</div><div className="mt-1 text-text-primary">{d.subscription_device_type_display || '—'}</div></div>
                    <div><div className="text-text-muted">خودرو</div><div className="mt-1 font-mono text-text-primary">{d.vehicle_plate || '—'}</div></div>
                    <div><div className="text-text-muted">وضعیت مدیریتی</div><div className="mt-1"><Badge variant={mgmt.variant}>{mgmt.label}</Badge></div></div>
                    <div><div className="text-text-muted">آخرین دریافت GPS</div><div className="mt-1 text-text-primary">{formatReceivedAt(d.last_data_received_at)}</div></div>
                    <div><div className="text-text-muted">وضعیت قرارداد داده</div><div className="mt-1"><Badge variant={d.data_active ? 'success' : 'muted'}>{d.data_active ? 'دریافت داده فعال' : 'دریافت داده غیرفعال'}</Badge></div></div>
                    {d.replacement_device_imei && <div className="col-span-2"><div className="text-text-muted">دستگاه مرتبط</div><button type="button" onClick={() => focusRelatedDevice(d.replacement_device_imei)} className="mt-1 text-brand-400">{d.replacement_device_imei}</button></div>}
                  </div>
                </article>
              );
            })}
          </div>
          <div className="hidden overflow-x-auto -m-5 sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base bg-bg-base/70">
                  <th className="text-right py-3 px-4 text-[11px] font-semibold text-text-muted whitespace-nowrap">IMEI</th>
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
          </>
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
              onChange={handleEditBrandChange}
              options={brandOptions}
              placeholder={loadingModels ? 'در حال دریافت فهرست...' : 'برای جستجو، نام برند را بنویسید یا از فهرست انتخاب کنید'}
              disabled={loadingModels || !brandOptions.length}
            />

            <SearchablePicker
              label="مدل دستگاه"
              value={editForm.device_model}
              onChange={handleEditModelChange}
              options={filteredModels}
              placeholder={loadingModels ? 'در حال دریافت فهرست...' : 'برای جستجو، نام مدل را بنویسید یا از فهرست انتخاب کنید'}
              disabled={loadingModels || !models.length}
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

function DeviceMetric({ label, value, icon: Icon }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5 rounded-xl border border-border-base bg-bg-elevated px-3 py-2.5 shadow-sm">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-bg-base text-brand-400">
        <Icon size={16} />
      </span>
      <div className="min-w-0">
        <div className="truncate text-[10px] text-text-muted sm:text-[11px]">{label}</div>
        <div className="text-sm font-semibold tabular-nums text-text-primary">{value.toLocaleString('fa-IR')}</div>
      </div>
    </div>
  );
}
