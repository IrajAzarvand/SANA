import { useEffect, useState } from 'react';
import { Plus, RotateCcw } from 'lucide-react';
import Badge from './Badge';
import Button from './Button';
import Input from './Input';
import Select from './Select';
import LoadingSpinner from './LoadingSpinner';
import AddDeviceModal from './AddDeviceModal';
import Modal from './Modal';
import {
  devicesAPI,
  deviceLifecycleAPI,
  deviceReplacementAPI,
  deviceOperationsAPI,
  vehiclesAPI,
  usersAPI,
} from '../api/services/fleet';
import { toJalali } from '../utils/dateUtils';
import { useAuth } from '../context/AuthContext';
import { organizationsAPI, branchesAPI } from '../api/services/organizations';
import { subscriptionsAPI } from '../api/services/subscriptions';

const managementStatusMap = {
  warehouse: { label: 'در انبار', variant: 'info' },
  sold: { label: 'فروخته شده', variant: 'brand' },
  installed: { label: 'نصب شده', variant: 'brand' },
  active: { label: 'فعال', variant: 'success' },
  ready: { label: 'آماده تعیین تکلیف', variant: 'info' },
  faulty: { label: 'خراب', variant: 'danger' },
  lost: { label: 'گمشده', variant: 'warning' },
  stolen: { label: 'سرقت شده', variant: 'danger' },
  disconnected: { label: 'قطع سرویس', variant: 'muted' },
  retired: { label: 'بازنشسته', variant: 'muted' },
  disposed: { label: 'امحاء', variant: 'danger' },
};

const deviceOperationTypeMap = {
  return_for_repair: 'بازگشت برای تعمیر',
  repaired: 'اتمام تعمیر',
  temporary_replacement: 'جایگزینی موقت',
  permanent_replacement: 'تعویض دائمی',
  lost: 'گم‌شدن',
  stolen: 'سرقت',
  found: 'پیدا شدن دستگاه',
  disposition: 'تعیین تکلیف دستگاه',
  transfer_customer: 'انتقال به مشتری دیگر',
  transfer_branch: 'انتقال بین شعب',
  transfer_vehicle: 'انتقال بین خودروها',
  retire: 'بازنشستگی',
  dispose: 'امحاء',
};

const deviceOperationReasonMap = {
  repair: 'تعمیر',
  replacement: 'تعویض',
  defective: 'خرابی',
  other: 'سایر',
};

const deviceReplacementTypeMap = {
  temporary_repair: 'جایگزینی موقت برای تعمیر',
  permanent_replacement: 'تعویض دائمی',
};

const deviceReplacementMethodMap = {
  loaner: 'امانی / موقت',
  sold: 'فروش به مشتری',
  free_exchange: 'تعویض بدون هزینه',
  paid_exchange: 'تعویض با هزینه',
  warranty: 'تعویض گارانتی',
  refurbished: 'دستگاه بازسازی‌شده',
  other: 'سایر',
};

const deviceOutcomeActionMap = {
  return_customer_same_vehicle: 'بازگشت به مشتری و نصب روی همان خودرو',
  return_customer_no_vehicle: 'بازگشت به مشتری بدون نصب',
  sana_warehouse: 'بازگشت به انبار سانا',
  customer_spare: 'تحویل به مشتری به عنوان دستگاه یدکی',
  install_other_vehicle: 'نصب روی خودروی دیگر',
  transfer_customer: 'انتقال به مشتری دیگر',
  retire: 'بازنشستگی',
  dispose: 'امحاء',
  other: 'سایر',
};

export default function DeviceHistoryModal({ open, deviceId, onClose }) {
  const [historyDevice, setHistoryDevice] = useState(null);
  const [historyEvents, setHistoryEvents] = useState([]);
  const [replacementRelations, setReplacementRelations] = useState([]);
  const [operationHistory, setOperationHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const { isSiteAdmin } = useAuth();
  const [replacementCandidates, setReplacementCandidates] = useState([]);
  const [operationTargets, setOperationTargets] = useState({ organizations: [], users: [], branches: [], vehicles: [], subscriptions: [] });
  const [replacementModalOpen, setReplacementModalOpen] = useState(false);
  const [operationSaving, setOperationSaving] = useState(false);
  const [operationForm, setOperationForm] = useState({
    operation_type: 'return_for_repair',
    replacement_type: 'temporary_repair',
    replacement_method: '',
    outcome_action: '',
    replacement_device: '',
    reason: 'repair',
    description: '',
    target_organization: '',
    target_user: '',
    target_branch: '',
    target_vehicle: '',
    target_subscription: '',
  });

  useEffect(() => {
    let cancelled = false;

    if (!open || !deviceId) {
      setHistoryDevice(null);
      setHistoryEvents([]);
      setReplacementRelations([]);
      setOperationHistory([]);
      setHistoryError('');
      return undefined;
    }

    const loadHistory = async () => {
      setHistoryLoading(true);
      setHistoryError('');

      try {
        const [device, historyResult, replacementResult, operationResult] = await Promise.all([
          devicesAPI.get(deviceId),
          deviceLifecycleAPI.list({ device: deviceId }),
          deviceReplacementAPI.list({ device: deviceId }),
          deviceOperationsAPI.list({ device: deviceId }),
        ]);

        if (cancelled) return;

        setHistoryDevice(device);
        setHistoryEvents(Array.isArray(historyResult) ? historyResult : historyResult.results || []);
        setReplacementRelations(Array.isArray(replacementResult) ? replacementResult : replacementResult.results || []);
        setOperationHistory(Array.isArray(operationResult) ? operationResult : operationResult.results || []);
      } catch (err) {
        if (cancelled) return;
        console.error('Error loading device history:', err);
        setHistoryDevice(null);
        setHistoryEvents([]);
        setReplacementRelations([]);
        setOperationHistory([]);
        setHistoryError('خطا در دریافت تاریخچه دستگاه');
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    };

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [open, deviceId]);

  const loadReplacementCandidates = async () => {
    if (!historyDevice) return;
    try {
      const result = await devicesAPI.list({ in_warehouse: 'true' });
      const list = Array.isArray(result) ? result : result.results || [];
      setReplacementCandidates(list.filter((item) => item.id !== historyDevice.id));
    } catch (err) {
      console.error('Error loading replacement candidates:', err);
      setReplacementCandidates([]);
    }
  };

  const loadOperationTargets = async (operationType) => {
    if (!historyDevice) return;
    try {
      const normalize = (result) => Array.isArray(result) ? result : result.results || [];
      if (operationType === 'disposition') {
        const [orgs, users, subs, vehicles] = await Promise.all([
          organizationsAPI.list(),
          usersAPI.list(),
          subscriptionsAPI.list({ status: 'active' }),
          vehiclesAPI.list(historyDevice.organization ? { organization: historyDevice.organization } : {}),
        ]);
        setOperationTargets((current) => ({
          ...current,
          organizations: normalize(orgs),
          users: normalize(users),
          subscriptions: normalize(subs),
          vehicles: normalize(vehicles),
        }));
      } else if (operationType === 'transfer_customer') {
        const [orgs, users, subs] = await Promise.all([
          organizationsAPI.list(),
          usersAPI.list(),
          subscriptionsAPI.list({ status: 'active' }),
        ]);
        setOperationTargets((current) => ({
          ...current,
          organizations: normalize(orgs),
          users: normalize(users),
          subscriptions: normalize(subs),
        }));
      } else if (operationType === 'transfer_branch') {
        const result = await branchesAPI.list(historyDevice.organization ? { organization: historyDevice.organization } : {});
        setOperationTargets((current) => ({ ...current, branches: normalize(result) }));
      } else if (operationType === 'transfer_vehicle') {
        const result = await vehiclesAPI.list(historyDevice.organization ? { organization: historyDevice.organization } : {});
        setOperationTargets((current) => ({ ...current, vehicles: normalize(result) }));
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
        replacement_method: operationForm.replacement_method || '',
        outcome_action: operationForm.outcome_action || '',
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
        replacement_type: 'temporary_repair',
        replacement_method: '',
        outcome_action: '',
        replacement_device: '',
        reason: 'repair',
        description: '',
        target_organization: '',
        target_user: '',
        target_branch: '',
        target_vehicle: '',
        target_subscription: '',
      });

      const updatedDevice = await devicesAPI.get(historyDevice.id);
      const [historyResult, replacementResult, operationResult] = await Promise.all([
        deviceLifecycleAPI.list({ device: historyDevice.id }),
        deviceReplacementAPI.list({ device: historyDevice.id }),
        deviceOperationsAPI.list({ device: historyDevice.id }),
      ]);
      setHistoryDevice(updatedDevice);
      setHistoryEvents(Array.isArray(historyResult) ? historyResult : historyResult.results || []);
      setReplacementRelations(Array.isArray(replacementResult) ? replacementResult : replacementResult.results || []);
      setOperationHistory(Array.isArray(operationResult) ? operationResult : operationResult.results || []);
    } catch (err) {
      console.error('Error saving device operation:', err);
      const data = err.response?.data;
      const message = typeof data === 'string'
        ? data
        : data?.detail
          ? data.detail
          : data
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

  const canAddFollowUpReplacement = ['faulty', 'lost', 'stolen'].includes(historyDevice?.management_status);
  const operationNeedsReplacement = ['return_for_repair', 'lost', 'stolen', 'temporary_replacement', 'permanent_replacement'].includes(operationForm.operation_type);
  const operationNeedsReplacementType = operationNeedsReplacement && Boolean(operationForm.replacement_device);
  const operationNeedsReplacementMethod = operationNeedsReplacement && Boolean(operationForm.replacement_device);
  const operationNeedsDisposition = operationForm.operation_type === 'disposition';

  const closeModal = () => {
    if (!historyLoading) onClose();
  };

  return (
    <Modal
      open={open}
      onClose={closeModal}
      title={historyDevice ? 'تاریخچه دستگاه ' + historyDevice.imei : 'تاریخچه دستگاه'}
      footer={<Button variant="secondary" onClick={onClose}>بستن</Button>}
    >
      <div className="space-y-5">
        {historyLoading && <LoadingSpinner />}

        {historyError && !historyLoading && (
          <div className="rounded-card border border-danger/20 bg-danger/5 p-4 text-sm text-danger">
            {historyError}
          </div>
        )}

        {!historyLoading && historyDevice && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 rounded-card border border-border-base bg-bg-base p-4">
              <div>
                <div className="text-[11px] text-text-muted">مدل دستگاه</div>
                <div className="text-sm text-text-primary mt-1">
                  {historyDevice.device_model_manufacturer && historyDevice.device_model_name
                    ? `${historyDevice.device_model_manufacturer} ${historyDevice.device_model_name}`
                    : '—'}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-text-muted">IMEI</div>
                <div className="text-sm font-mono text-text-primary mt-1">{historyDevice.imei || '—'}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-muted">شماره سیم‌کارت</div>
                <div dir="ltr" className="text-sm font-mono text-text-primary mt-1 text-right">{historyDevice.sim_number || '—'}</div>
              </div>
              <div>
                <div className="text-[11px] text-text-muted">وضعیت فعلی</div>
                <div className="mt-1">
                  <Badge variant={(managementStatusMap[historyDevice.management_status] || managementStatusMap.warehouse).variant}>
                    {(managementStatusMap[historyDevice.management_status] || managementStatusMap.warehouse).label}
                  </Badge>
                </div>
              </div>
            </div>

            <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
              {operationHistory.length > 0 && (
                <div className="rounded-card border border-border-base bg-bg-base p-4 space-y-3">
                  <div className="text-sm font-semibold text-text-primary">سوابق عملیات دستگاه</div>
                  <div className="space-y-2">
                    {operationHistory.map((operation) => {
                      const linkedEvent = historyEvents.find((event) => event.device_operation === operation.id)
                        || historyEvents.find((event) =>
                          !event.device_operation
                          && event.description === operation.description
                          && event.subscription === operation.subscription
                          && event.event_date
                          && operation.performed_at
                          && Math.abs(new Date(event.event_date).getTime() - new Date(operation.performed_at).getTime()) <= 5000
                        );

                      return (
                        <div key={operation.id} className="rounded-card border border-border-base bg-bg-surface p-3">
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-medium text-text-primary">
                              {deviceOperationTypeMap[operation.operation_type] || operation.operation_type_display || 'عملیات دستگاه'}
                            </div>
                            <span className="text-[11px] text-text-muted">
                              {operation.performed_at ? toJalali(operation.performed_at) : '—'}
                            </span>
                          </div>

                          <div className="flex flex-wrap gap-2 mt-3 text-[11px] text-text-muted">
                            {operation.old_status && (
                              <span>وضعیت قبل: {managementStatusMap[operation.old_status]?.label || operation.old_status}</span>
                            )}
                            {operation.new_status && (
                              <span>وضعیت بعد: {managementStatusMap[operation.new_status]?.label || operation.new_status}</span>
                            )}
                            {operation.subscription_number && <span>قرارداد: {operation.subscription_number}</span>}
                            {linkedEvent?.organization_name && <span>مشتری: {linkedEvent.organization_name}</span>}
                            {linkedEvent?.vehicle_plate && <span>خودرو: {linkedEvent.vehicle_plate}</span>}
                          </div>

                          {operation.replacement_device_imei && (
                            <div className="text-xs text-text-secondary mt-2">
                              دستگاه جایگزین: <span className="font-mono">{operation.replacement_device_imei}</span>
                            </div>
                          )}

                          {operation.replacement_type && (
                            <div className="text-xs text-text-secondary mt-2">
                              ماهیت جایگزینی: {deviceReplacementTypeMap[operation.replacement_type] || operation.replacement_type}
                            </div>
                          )}

                          {operation.replacement_method && (
                            <div className="text-xs text-text-secondary mt-2">
                              نحوه جایگزینی: {operation.replacement_method}
                            </div>
                          )}

                          {operation.outcome_action && (
                            <div className="text-xs text-text-secondary mt-2">
                              سرنوشت پس از تعمیر: {operation.outcome_action}
                            </div>
                          )}

                          {operation.reason && (
                            <div className="text-xs text-text-secondary mt-2">
                              دلیل: {linkedEvent?.reason_display || deviceOperationReasonMap[operation.reason] || operation.reason}
                            </div>
                          )}

                          {operation.description && (
                            <div className="text-xs text-text-secondary mt-2 leading-6">{operation.description}</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {operationHistory.length === 0 && historyEvents.filter((event) => !event.device_operation).length === 0 && (
                <div className="text-sm text-text-muted text-center py-6">هنوز رویدادی ثبت نشده است.</div>
              )}

              {historyEvents.filter((event) => {
                if (event.device_operation) return false;
                return !operationHistory.some((operation) =>
                  event.description === operation.description
                  && event.subscription === operation.subscription
                  && event.event_date
                  && operation.performed_at
                  && Math.abs(new Date(event.event_date).getTime() - new Date(operation.performed_at).getTime()) <= 5000
                );
              }).map((event) => (
                <div key={event.id} className="rounded-card border border-border-base bg-bg-base p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-text-primary">
                        {event.event_type_display || deviceOperationTypeMap[event.event_type] || event.event_type || 'رویداد دستگاه'}
                      </div>
                      <div className="text-[11px] text-text-muted mt-1 font-mono">
                        {event.event_date ? toJalali(event.event_date) : '—'}
                      </div>
                    </div>
                    <Badge variant={event.new_status === 'warehouse' ? 'info' : 'brand'}>
                      {managementStatusMap[event.new_status]?.label || event.new_status || '—'}
                    </Badge>
                  </div>
                  {event.reason_display && <div className="text-xs text-text-secondary mt-2">دلیل: {event.reason_display}</div>}
                  {event.description && <div className="text-xs text-text-secondary mt-2 leading-6">{event.description}</div>}
                  {(event.subscription_number || event.organization_name || event.vehicle_plate) && (
                    <div className="flex flex-wrap gap-2 mt-3 text-[11px] text-text-muted">
                      {event.subscription_number && <span>قرارداد: {event.subscription_number}</span>}
                      {event.organization_name && <span>مشتری: {event.organization_name}</span>}
                      {event.vehicle_plate && <span>خودرو: {event.vehicle_plate}</span>}
                    </div>
                  )}
                </div>
              ))}

              {replacementRelations.length > 0 && (
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
                              {deviceReplacementTypeMap[relation.replacement_type] || relation.replacement_type_display || relation.replacement_type || '—'}
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
            </div>
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
                          replacement_type: value === 'temporary_replacement' ? 'temporary_repair' : value === 'permanent_replacement' ? 'permanent_replacement' : '',
                          replacement_method: '',
                          outcome_action: '',
                          replacement_device: '',
                          reason: ['return_for_repair', 'temporary_replacement', 'permanent_replacement'].includes(value) ? 'repair' : current.reason,
                        }));
                        if (['return_for_repair', 'lost', 'stolen', 'temporary_replacement', 'permanent_replacement'].includes(value)) await loadReplacementCandidates();
                        if (['disposition', 'transfer_customer', 'transfer_branch', 'transfer_vehicle'].includes(value)) await loadOperationTargets(value);
                      }}
                      options={[
                        { value: 'return_for_repair', label: 'بازگشت برای تعمیر' },
                        ...(canAddFollowUpReplacement ? [
                          { value: 'temporary_replacement', label: 'جایگزینی موقت' },
                          { value: 'permanent_replacement', label: 'تعویض دائمی' },
                        ] : []),
                        { value: 'repaired', label: 'اتمام تعمیر' },
                        { value: 'found', label: 'پیدا شدن دستگاه' },
                        { value: 'disposition', label: 'تعیین تکلیف دستگاه' },
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
                        <Select label="سازمان مقصد" placeholder="انتخاب سازمان" value={operationForm.target_organization} onChange={(e) => setOperationForm((current) => ({ ...current, target_organization: e.target.value, target_user: '' }))} options={operationTargets.organizations.map((item) => ({ value: item.id, label: item.name }))} />
                        <Select label="کاربر شخصی مقصد" placeholder="در صورت انتقال به مشتری شخصی" value={operationForm.target_user} onChange={(e) => setOperationForm((current) => ({ ...current, target_user: e.target.value, target_organization: '' }))} options={operationTargets.users.filter((item) => item.account_type === 'personal').map((item) => ({ value: item.id, label: item.full_name || item.username }))} />
                        <Select label="قرارداد مقصد (اختیاری)" placeholder="انتخاب قرارداد" value={operationForm.target_subscription} onChange={(e) => setOperationForm((current) => ({ ...current, target_subscription: e.target.value }))} options={operationTargets.subscriptions.map((item) => ({ value: item.id, label: item.contract_number }))} />
                      </div>
                    )}
                    {operationForm.operation_type === 'transfer_branch' && <Select label="شعبه مقصد" placeholder="انتخاب شعبه" value={operationForm.target_branch} onChange={(e) => setOperationForm((current) => ({ ...current, target_branch: e.target.value }))} options={operationTargets.branches.map((item) => ({ value: item.id, label: item.name }))} />}
                    {operationForm.operation_type === 'transfer_vehicle' && <Select label="خودرو مقصد" placeholder="انتخاب خودرو" value={operationForm.target_vehicle} onChange={(e) => setOperationForm((current) => ({ ...current, target_vehicle: e.target.value }))} options={operationTargets.vehicles.map((item) => ({ value: item.id, label: item.plate }))} />}
                    {operationNeedsDisposition && (
                      <div className="space-y-3 rounded-card border border-border-base bg-bg-base p-3">
                        <Select label="تعیین تکلیف دستگاه" required value={operationForm.outcome_action} onChange={(e) => setOperationForm((current) => ({ ...current, outcome_action: e.target.value }))} options={Object.entries(deviceOutcomeActionMap).map(([value, label]) => ({ value, label }))} />
                        {['install_other_vehicle', 'transfer_customer'].includes(operationForm.outcome_action) && <Select label="خودروی مقصد" placeholder="انتخاب خودرو" value={operationForm.target_vehicle} onChange={(e) => setOperationForm((current) => ({ ...current, target_vehicle: e.target.value }))} options={operationTargets.vehicles.map((item) => ({ value: item.id, label: item.plate }))} />}
                        {operationForm.outcome_action === 'transfer_customer' && (
                          <div className="space-y-3">
                            <Select label="سازمان مقصد" placeholder="انتخاب سازمان" value={operationForm.target_organization} onChange={(e) => setOperationForm((current) => ({ ...current, target_organization: e.target.value, target_user: '' }))} options={operationTargets.organizations.map((item) => ({ value: item.id, label: item.name }))} />
                            <Select label="کاربر شخصی مقصد" placeholder="در صورت انتقال به مشتری شخصی" value={operationForm.target_user} onChange={(e) => setOperationForm((current) => ({ ...current, target_user: e.target.value, target_organization: '' }))} options={operationTargets.users.filter((item) => item.account_type === 'personal').map((item) => ({ value: item.id, label: item.full_name || item.username }))} />
                            <Select label="قرارداد مقصد (اختیاری)" placeholder="انتخاب قرارداد" value={operationForm.target_subscription} onChange={(e) => setOperationForm((current) => ({ ...current, target_subscription: e.target.value }))} options={operationTargets.subscriptions.map((item) => ({ value: item.id, label: item.contract_number }))} />
                          </div>
                        )}
                      </div>
                    )}
                    {operationNeedsReplacement && (
                      <div className="space-y-3 rounded-card border border-border-base bg-bg-base p-3">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-xs font-medium text-text-secondary">جایگزین</span>
                          <Button type="button" size="sm" variant="secondary" icon={Plus} onClick={() => { loadReplacementCandidates(); setReplacementModalOpen(true); }}>افزودن دستگاه جدید</Button>
                        </div>
                        <Select label="دستگاه جایگزین" placeholder="بدون جایگزین" value={operationForm.replacement_device} onChange={(e) => setOperationForm((current) => ({ ...current, replacement_device: e.target.value, replacement_type: current.replacement_type || 'temporary_repair' }))} options={replacementCandidates.map((item) => ({ value: item.id, label: item.imei + ' — ' + (item.device_model_manufacturer || '') + ' ' + (item.device_model_name || '') }))} />
                        {operationNeedsReplacementType && <Select label="نوع جایگزینی" required value={operationForm.replacement_type} onChange={(e) => setOperationForm((current) => ({ ...current, replacement_type: e.target.value }))} options={[{ value: 'temporary_repair', label: 'جایگزینی موقت برای تعمیر' }, { value: 'permanent_replacement', label: 'تعویض دائمی' }]} />}
                        {operationNeedsReplacementMethod && <Select label="نحوه جایگزینی" required value={operationForm.replacement_method} onChange={(e) => setOperationForm((current) => ({ ...current, replacement_method: e.target.value }))} options={Object.entries(deviceReplacementMethodMap).map(([value, label]) => ({ value, label }))} />}
                      </div>
                    )}
                    <Select label="دلیل" value={operationForm.reason} onChange={(e) => setOperationForm({ ...operationForm, reason: e.target.value })} options={[{ value: 'repair', label: 'تعمیر' }, { value: 'replacement', label: 'تعویض' }, { value: 'defective', label: 'خرابی' }, { value: 'other', label: 'سایر' }]} />
                    <Input label="شرح" value={operationForm.description} onChange={(e) => setOperationForm({ ...operationForm, description: e.target.value })} placeholder="شرح کامل عملیات..." />
                    <div className="flex justify-end"><Button type="submit" disabled={operationSaving}>{operationSaving ? 'در حال ثبت...' : 'ثبت عملیات'}</Button></div>
                  </form>
                </div>
                <AddDeviceModal open={replacementModalOpen} onClose={() => setReplacementModalOpen(false)} onSuccess={handleReplacementCreated} />
              </>
            )}

          </>
        )}
      </div>
    </Modal>
  );
}
