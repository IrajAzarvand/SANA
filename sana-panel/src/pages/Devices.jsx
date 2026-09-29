import { useState, useMemo, useCallback } from 'react';
import {
  Search, Plus, Cpu, Pencil, Trash2 , Hash, Phone, Eye, Boxes, Package, History, RotateCcw,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Select from '../components/Select';
import Modal from '../components/Modal';
import JalaliDatePicker from '../components/JalaliDatePicker';
import EmptyState from '../components/EmptyState';
import ActionMenu from '../components/ActionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import Tabs from '../components/Tabs';
import AddDeviceModal from '../components/AddDeviceModal';
import { useAuth } from '../context/AuthContext';
import { devicesAPI, deviceLifecycleAPI, deviceReplacementAPI, deviceOperationsAPI } from '../api/services/fleet';
import { deviceModelsAPI } from '../api/services/deviceModels';
import { useApi } from '../hooks/useApi';
import { toJalali } from '../utils/dateUtils';
import { organizationsAPI, branchesAPI } from '../api/services/organizations';
import { subscriptionsAPI } from '../api/services/subscriptions';

const managementStatusMap = {
  warehouse:    { label: 'در انبار',      variant: 'info'    },
  sold:         { label: 'فروخته شده',    variant: 'brand'   },
  installed:    { label: 'نصب شده',       variant: 'brand'   },
  active:       { label: 'فعال',          variant: 'success' },
  faulty:       { label: 'خراب',          variant: 'danger'  },
  lost:         { label: 'گمشده',         variant: 'warning' },
  stolen:       { label: 'سرقت شده',      variant: 'danger'  },
  disconnected: { label: 'قطع سرویس',     variant: 'muted'   },
  retired:      { label: 'بازنشسته',       variant: 'muted'   },
  disposed:     { label: 'امحاء شده',      variant: 'danger'  },
};

export default function Devices() {
  const [activeTab, setActiveTab] = useState('devices');

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
            { value: 'models',  label: 'مدل‌های دستگاه' },
          ]}
        />
      </Card>

      {activeTab === 'devices' && <DevicesTab />}
      {activeTab === 'models'  && <DeviceModelsTab />}
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
  const [historyDevice, setHistoryDevice] = useState(null);
  const [historyEvents, setHistoryEvents] = useState([]);
  const [replacementRelations, setReplacementRelations] = useState([]);
  const [operationHistory, setOperationHistory] = useState([]);
  const [replacementCandidates, setReplacementCandidates] = useState([]);
  const [operationTargets, setOperationTargets] = useState({ organizations: [], users: [], branches: [], vehicles: [], subscriptions: [] });
  const [replacementModalOpen, setReplacementModalOpen] = useState(false);
  const [operationSaving, setOperationSaving] = useState(false);
  const [operationForm, setOperationForm] = useState({
    operation_type: 'return_for_repair',
    replacement_type: '',
    replacement_device: '',
    reason: 'repair',
    description: '',
    target_organization: '',
    target_user: '',
    target_branch: '',
    target_vehicle: '',
    target_subscription: '',
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [eventSaving, setEventSaving] = useState(false);
  const [eventForm, setEventForm] = useState({ event_type: 'returned', reason: 'other', event_date: '', description: '' });

  const { isSiteAdmin, isPersonal } = useAuth();

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

  const openHistory = async (device) => {
    setHistoryDevice(device);
    setHistoryLoading(true);
    try {
      const [historyResult, replacementResult, operationResult] = await Promise.all([
        deviceLifecycleAPI.list({ device: device.id }),
        deviceReplacementAPI.list({ device: device.id }),
        deviceOperationsAPI.list({ device: device.id }),
      ]);
      setHistoryEvents(Array.isArray(historyResult) ? historyResult : historyResult.results || []);
      setReplacementRelations(Array.isArray(replacementResult) ? replacementResult : replacementResult.results || []);
      setOperationHistory(Array.isArray(operationResult) ? operationResult : operationResult.results || []);
    } catch (err) {
      console.error('Error loading device history:', err);
      setHistoryEvents([]);
      setReplacementRelations([]);
      setOperationHistory([]);
      alert('خطا در دریافت تاریخچه دستگاه');
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadReplacementCandidates = async () => {
    try {
      const result = await devicesAPI.list({ in_warehouse: 'true' });
      const list = Array.isArray(result) ? result : result.results || [];
      setReplacementCandidates(list.filter((item) => item.id !== historyDevice?.id));
    } catch (err) {
      console.error('Error loading replacement candidates:', err);
      setReplacementCandidates([]);
    }
  };

  const loadOperationTargets = async (operationType) => {
    try {
      if (operationType === 'transfer_customer') {
        const [orgs, users, subs] = await Promise.all([
          organizationsAPI.list(),
          usersAPI.list(),
          subscriptionsAPI.list({ status: 'active' }),
        ]);
        const normalize = (result) => Array.isArray(result) ? result : result.results || [];
        setOperationTargets((current) => ({
          ...current,
          organizations: normalize(orgs),
          users: normalize(users),
          subscriptions: normalize(subs),
        }));
      } else if (operationType === 'transfer_branch') {
        const result = await branchesAPI.list(historyDevice?.organization ? { organization: historyDevice.organization } : {});
        setOperationTargets((current) => ({ ...current, branches: Array.isArray(result) ? result : result.results || [] }));
      } else if (operationType === 'transfer_vehicle') {
        const result = await vehiclesAPI.list(historyDevice?.organization ? { organization: historyDevice.organization } : {});
        setOperationTargets((current) => ({ ...current, vehicles: Array.isArray(result) ? result : result.results || [] }));
      }
    } catch (err) {
      console.error('Error loading operation targets:', err);
    }
  };

  const handleDeviceOperation = async (e) => {
    e.preventDefault();
    if (!historyDevice) return;
    setOperationSaving(true);
    try {
      const payload = {
        device: historyDevice.id,
        operation_type: operationForm.operation_type,
        reason: operationForm.reason || '',
        description: operationForm.description || '',
      };
      ['target_organization', 'target_user', 'target_branch', 'target_vehicle', 'target_subscription'].forEach((key) => {
        if (operationForm[key]) payload[key] = Number(operationForm[key]);
      });
      if (operationForm.replacement_device) {
        payload.replacement_device = Number(operationForm.replacement_device);
        payload.replacement_type = operationForm.replacement_type;
      }
      await deviceOperationsAPI.create(payload);
      setOperationForm({
        operation_type: 'return_for_repair',
        replacement_type: '',
        replacement_device: '',
        reason: 'repair',
        description: '',
        target_organization: '', target_user: '', target_branch: '', target_vehicle: '', target_subscription: '',
      });
      await openHistory(historyDevice);
      refetch();
    } catch (err) {
      console.error('Error saving device operation:', err);
      const data = err.response?.data;
      const message = data
        ? Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value[0] : value}`).join('\n')
        : 'ثبت عملیات ناموفق بود';
      alert(message);
    } finally {
      setOperationSaving(false);
    }
  };

  const handleReplacementCreated = (createdDevice) => {
    setReplacementModalOpen(false);
    setOperationForm((current) => ({
      ...current,
      replacement_device: createdDevice.id,
    }));
  };

  const operationNeedsReplacement = ['return_for_repair', 'lost', 'stolen'].includes(operationForm.operation_type);
  const operationNeedsReplacementType = operationForm.operation_type === 'return_for_repair' && Boolean(operationForm.replacement_device);

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

  const getMenuItems = (device) => {
    const items = [
      {
        label: 'تاریخچه و رویدادها',
        icon: History,
        onClick: () => openHistory(device),
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
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">خودرو</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
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
                    <tr key={d.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
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
                          {d.organization_name || d.owner_name || (
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
                        {d.vehicle_plate ? (
                          <span className="font-mono text-text-primary text-xs">{d.vehicle_plate}</span>
                        ) : (
                          <span className="text-text-muted text-xs">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={mgmt.variant}>{mgmt.label}</Badge>
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

      {/* تاریخچه چرخه عمر دستگاه */}
      <Modal
        open={Boolean(historyDevice)}
        onClose={() => setHistoryDevice(null)}
        title={historyDevice ? 'تاریخچه دستگاه ' + historyDevice.imei : 'تاریخچه دستگاه'}
        footer={<Button variant="secondary" onClick={() => setHistoryDevice(null)}>بستن</Button>}
      >
        <div className="space-y-5">
          {!historyLoading && historyDevice && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 rounded-card border border-border-base bg-bg-base p-4">
              <div>
                <div className="text-[11px] text-text-muted">مالک</div>
                <div className="text-sm text-text-primary mt-1">{historyDevice.organization_name || historyDevice.owner_name || 'سانا'}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-muted">تحویل‌گیرنده فعلی</div>
                <div className="text-sm text-text-primary mt-1">
                  {historyDevice.current_holder_organization_name || historyDevice.current_holder_user_name || 'سانا'}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-text-muted">خودرو</div>
                <div className="text-sm text-text-primary mt-1">{historyDevice.vehicle_plate || '—'}</div>
              </div>
            </div>
          )}
          {historyLoading ? <LoadingSpinner /> : (
            <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
              {operationHistory.length > 0 && (
            <div className="rounded-card border border-border-base bg-bg-base p-4 space-y-3">
              <div className="text-sm font-semibold text-text-primary">سوابق عملیات دستگاه</div>
              <div className="space-y-2">
                {operationHistory.map((operation) => (
                  <div key={operation.id} className="rounded-card border border-border-base bg-bg-surface p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-text-primary">{operation.operation_type_display}</div>
                      <span className="text-[11px] text-text-muted">{operation.performed_at ? toJalali(operation.performed_at) : '—'}</span>
                    </div>
                    {operation.replacement_device_imei && <div className="text-xs text-text-secondary mt-2">دستگاه جایگزین: <span className="font-mono">{operation.replacement_device_imei}</span></div>}
                    {operation.description && <div className="text-xs text-text-secondary mt-2 leading-6">{operation.description}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
          {historyEvents.length === 0 ? <div className="text-sm text-text-muted text-center py-6">هنوز رویدادی ثبت نشده است.</div> : historyEvents.map((event) => (
                <div key={event.id} className="rounded-card border border-border-base bg-bg-base p-3">
                  <div className="flex items-start justify-between gap-3"><div><div className="text-sm font-semibold text-text-primary">{event.event_type_display}</div><div className="text-[11px] text-text-muted mt-1 font-mono">{event.event_date ? toJalali(event.event_date) : '—'}</div></div><Badge variant={event.new_status === 'warehouse' ? 'info' : 'brand'}>{managementStatusMap[event.new_status]?.label || event.new_status || '—'}</Badge></div>
                  {event.reason_display && <div className="text-xs text-text-secondary mt-2">دلیل: {event.reason_display}</div>}
                  {event.description && <div className="text-xs text-text-secondary mt-2 leading-6">{event.description}</div>}
                  {(event.subscription_number || event.organization_name || event.vehicle_plate) && <div className="flex flex-wrap gap-2 mt-3 text-[11px] text-text-muted">{event.subscription_number && <span>قرارداد: {event.subscription_number}</span>}{event.organization_name && <span>مشتری: {event.organization_name}</span>}{event.vehicle_plate && <span>خودرو: {event.vehicle_plate}</span>}</div>}
                </div>
              ))}
            </div>
          )}

          {!historyLoading && replacementRelations.length > 0 && (
            <div className="rounded-card border border-border-base bg-bg-base p-4 space-y-3">
              <div className="text-sm font-semibold text-text-primary">رابطه جایگزینی</div>
              <div className="space-y-2">
                {replacementRelations.map((relation) => {
                  const isSource = relation.source_device === historyDevice?.id;
                  return (
                    <div key={relation.id} className="rounded-card border border-border-base bg-bg-surface p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-xs text-text-secondary">
                          {isSource ? 'این دستگاه جایگزین شده با' : 'این دستگاه جایگزین'}
                        </div>
                        <Badge variant={relation.replacement_type === 'temporary_repair' ? 'warning' : 'brand'}>
                          {relation.replacement_type_display}
                        </Badge>
                      </div>
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <span className="font-mono text-xs text-text-primary">
                          {isSource ? relation.replacement_device_imei : relation.source_device_imei}
                        </span>
                        <span className="text-[11px] text-text-muted">
                          {relation.replacement_date ? toJalali(relation.replacement_date) : '—'}
                        </span>
                      </div>
                      {relation.description && (
                        <div className="text-xs text-text-secondary mt-2 leading-6">{relation.description}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {isSiteAdmin && (
            <>
              <div className="border-t border-border-base pt-4">
                <form onSubmit={handleDeviceOperation} className="space-y-4">
                  <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <RotateCcw size={16} />عملیات دستگاه
                  </div>
                  <Select
                    label="نوع عملیات"
                    value={operationForm.operation_type}
                    onChange={async (e) => {
                      const value = e.target.value;
                      setOperationForm((current) => ({
                        ...current,
                        operation_type: value,
                        replacement_type: '',
                        replacement_device: '',
                        reason: value === 'return_for_repair' ? 'repair' : current.reason,
                      }));
                      if (['return_for_repair', 'lost', 'stolen'].includes(value)) {
                        await loadReplacementCandidates();
                      }
                      if (['transfer_customer', 'transfer_branch', 'transfer_vehicle'].includes(value)) {
                        await loadOperationTargets(value);
                      }
                    }}
                    options={[
                      { value: 'return_for_repair', label: 'بازگشت برای تعمیر' },
                      { value: 'repaired', label: 'اتمام تعمیر' },
                      { value: 'lost', label: 'گم‌شدن' },
                      { value: 'stolen', label: 'سرقت' },
                      { value: 'transfer_customer', label: 'انتقال به مشتری دیگر' },
                      { value: 'transfer_branch', label: 'انتقال بین شعب' },
                      { value: 'transfer_vehicle', label: 'انتقال بین خودروها' },
                      { value: 'retire', label: 'بازنشستگی' },
                      { value: 'dispose', label: 'امحاء' },
                    ]}
                  />
                  {operationForm.operation_type === 'transfer_customer' && (
                    <div className="space-y-3 rounded-card border border-border-base bg-bg-base p-3">
                      <Select label="سازمان مقصد" placeholder="انتخاب سازمان" value={operationForm.target_organization} onChange={(e) => setOperationForm({ ...operationForm, target_organization: e.target.value, target_user: '' })} options={operationTargets.organizations.map((item) => ({ value: item.id, label: item.name }))} />
                      <Select label="کاربر شخصی مقصد" placeholder="در صورت انتقال به مشتری شخصی" value={operationForm.target_user} onChange={(e) => setOperationForm({ ...operationForm, target_user: e.target.value, target_organization: '' })} options={operationTargets.users.filter((item) => item.account_type === 'personal').map((item) => ({ value: item.id, label: item.full_name || item.username }))} />
                      <Select label="قرارداد مقصد (اختیاری)" placeholder="انتخاب قرارداد" value={operationForm.target_subscription} onChange={(e) => setOperationForm({ ...operationForm, target_subscription: e.target.value })} options={operationTargets.subscriptions.map((item) => ({ value: item.id, label: item.contract_number }))} />
                    </div>
                  )}

                  {operationForm.operation_type === 'transfer_branch' && (
                    <Select label="شعبه مقصد" placeholder="انتخاب شعبه" value={operationForm.target_branch} onChange={(e) => setOperationForm({ ...operationForm, target_branch: e.target.value })} options={operationTargets.branches.map((item) => ({ value: item.id, label: item.name }))} />
                  )}

                  {operationForm.operation_type === 'transfer_vehicle' && (
                    <Select label="خودرو مقصد" placeholder="انتخاب خودرو" value={operationForm.target_vehicle} onChange={(e) => setOperationForm({ ...operationForm, target_vehicle: e.target.value })} options={operationTargets.vehicles.map((item) => ({ value: item.id, label: item.plate }))} />
                  )}

                  {operationNeedsReplacement && (
                    <div className="space-y-3 rounded-card border border-border-base bg-bg-base p-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs font-medium text-text-secondary">جایگزین</span>
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          icon={Plus}
                          onClick={() => {
                            loadReplacementCandidates();
                            setReplacementModalOpen(true);
                          }}
                        >
                          افزودن دستگاه جدید
                        </Button>
                      </div>
                      <Select
                        label="دستگاه جایگزین"
                        placeholder="بدون جایگزین"
                        value={operationForm.replacement_device}
                        onChange={(e) => setOperationForm({ ...operationForm, replacement_device: e.target.value })}
                        options={[
                          { value: '', label: 'بدون جایگزین' },
                          ...replacementCandidates.map((item) => ({
                            value: item.id,
                            label: `${item.imei} — ${item.device_model_manufacturer || ''} ${item.device_model_name || ''}`,
                          })),
                        ]}
                      />
                      {operationNeedsReplacementType && (
                        <Select
                          label="نوع جایگزینی"
                          value={operationForm.replacement_type}
                          onChange={(e) => setOperationForm({ ...operationForm, replacement_type: e.target.value })}
                          options={[
                            { value: 'temporary_repair', label: 'جایگزینی موقت برای تعمیر' },
                            { value: 'permanent_replacement', label: 'تعویض دائمی' },
                          ]}
                        />
                      )}
                    </div>
                  )}
                  <Select
                    label="دلیل"
                    value={operationForm.reason}
                    onChange={(e) => setOperationForm({ ...operationForm, reason: e.target.value })}
                    options={[
                      { value: 'repair', label: 'تعمیر' },
                      { value: 'replacement', label: 'تعویض' },
                      { value: 'defective', label: 'خرابی' },
                      { value: 'other', label: 'سایر' },
                    ]}
                  />
                  <Input
                    label="شرح"
                    value={operationForm.description}
                    onChange={(e) => setOperationForm({ ...operationForm, description: e.target.value })}
                    placeholder="شرح کامل عملیات..."
                  />
                  <div className="flex justify-end">
                    <Button type="submit" disabled={operationSaving}>
                      {operationSaving ? 'در حال ثبت...' : 'ثبت عملیات'}
                    </Button>
                  </div>
                </form>
              </div>
              <AddDeviceModal
                open={replacementModalOpen}
                onClose={() => setReplacementModalOpen(false)}
                onSuccess={handleReplacementCreated}
              />
            </>
          )}
        </div>
      </Modal>
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