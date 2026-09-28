import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  ArrowRight, Building2, User as UserIcon, FileText, Package, CreditCard,
  Pencil, Trash2, Plus, Calendar, Hash, Phone, MapPin, Users, Truck,
  RotateCw, Ban, CheckCircle2, AlertTriangle, Boxes, XCircle, RefreshCw,
  History,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Select from '../components/Select';
import Modal from '../components/Modal';
import AddDeviceModal from '../components/AddDeviceModal';
import ActionMenu from '../components/ActionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import JalaliDatePicker from '../components/JalaliDatePicker';
import { useAuth } from '../context/AuthContext';
import { subscriptionsAPI, subscriptionDevicesAPI, subscriptionPaymentsAPI } from '../api/services/subscriptions';
import { organizationsAPI } from '../api/services/organizations';
import { devicesAPI } from '../api/services/fleet';
import { usersAPI } from '../api/services/fleet';
import { useApi } from '../hooks/useApi';
import { toJalali, todayGregorian } from '../utils/dateUtils';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';

const statusMap = {
  active:    { label: 'فعال',          variant: 'success' },
  pending:   { label: 'در انتظار شروع', variant: 'info'    },
  suspended: { label: 'تعلیق‌شده',      variant: 'warning' },
  expired:   { label: 'منقضی',         variant: 'muted'   },
  cancelled: { label: 'لغو‌شده',        variant: 'danger'  },
};

export default function SubscriptionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isSiteAdmin } = useAuth();

  const fetchSubscription = useCallback(async () => {
    return await subscriptionsAPI.get(id);
  }, [id]);

  const { data: subscription, loading, error, refetch } =
    useApi(fetchSubscription, [id]);

    // اگه ?renew=true بود، مودال تمدید باز بشه
  useEffect(() => {
    if (searchParams.get('renew') === 'true' && subscription && subscription.status !== 'cancelled') {
      setRenewForm({
        new_end_date: subscription.end_date,
        notes: '',
        add_devices: [],
        remove_device_ids: [],
        payments: [],
        customer_changes: {},
      });
      setRenewModalOpen(true);
      // پاک کردن query string
      setSearchParams({}, { replace: true });
    }
  }, [subscription, searchParams, setSearchParams]);

  // ═══ State مودال‌ها ═══
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState({ start_date: '', end_date: '', notes: '', remove_device_ids: [], add_devices: [], remove_added_device_indices: [], payment_changes: {} });
  const [editCustomer, setEditCustomer] = useState({});
  const [editNewDevice, setEditNewDevice] = useState({ device_id: '', start_date: '', end_date: '' });
  const [editAddDeviceModalOpen, setEditAddDeviceModalOpen] = useState(false);
  const [editDevicePickerModalOpen, setEditDevicePickerModalOpen] = useState(false);
  const [editCustomerLoading, setEditCustomerLoading] = useState(false);
  const [renewModalOpen, setRenewModalOpen] = useState(false);
  const [renewForm, setRenewForm] = useState({
    new_end_date: '',
    notes: '',
    add_devices: [],
    remove_device_ids: [],
    payments: [],
    customer_changes: {},
  });
  const [renewCustomer, setRenewCustomer] = useState({});
  const [renewCustomerLoading, setRenewCustomerLoading] = useState(false);
  const [renewSections, setRenewSections] = useState({
    info: true,
    customer: false,
    devices: false,
    payments: false,
  });

  const toggleRenewSection = (section) => {
    setRenewSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };
  const [renewNewDevice, setRenewNewDevice] = useState({
    device_id: '',
    start_date: '',
    end_date: '',
  });
  const [renewPaymentDraft, setRenewPaymentDraft] = useState({
    amount: '',
    payment_date: todayGregorian(),
    device_count: 0,
    description: '',
  });

  const [deviceModalOpen, setDeviceModalOpen] = useState(false);
  const [deviceForm, setDeviceForm] = useState({
    device: '',
    start_date: '',
    end_date: '',
  });

  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [paymentForm, setPaymentForm] = useState({
    amount: '',
    payment_date: todayGregorian(),
    device_count: 0,
    description: '',
  });

  const [cancelModalOpen, setCancelModalOpen] = useState(false);

  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState('');

  // ═══ لیست دستگاه‌های انبار ═══
  const fetchWarehouseDevices = useCallback(async () => {
    if (!deviceModalOpen && !renewModalOpen && !editModalOpen) return [];
    const result = await devicesAPI.list({ in_warehouse: 'true' });
    return Array.isArray(result) ? result : result.results || [];
  }, [deviceModalOpen, renewModalOpen, editModalOpen]);

  const { data: warehouseDevices, refetch: refetchWarehouseDevices } = useApi(
    fetchWarehouseDevices,
    [deviceModalOpen, renewModalOpen, editModalOpen]
  );

  const warehouseOptions = useMemo(() => {
    return (warehouseDevices || []).map((d) => ({
      value: d.id,
      label: `${d.imei} ${d.device_model_name ? `(${d.device_model_name})` : ''}`,
    }));
  }, [warehouseDevices]);

  // ═══ تمدید ═══
  const openEditModal = async () => {
    const customerDefaults = isOrg
      ? { name: '', code: '', registration_number: '', economy_code: '', phone: '', email: '', address: '', website: '' }
      : { first_name: '', last_name: '', mobile: '', national_id: '', address: '' };

    setEditForm({
      start_date: subscription.start_date,
      end_date: subscription.end_date,
      notes: subscription.notes || '',
      remove_device_ids: [],
      add_devices: [],
      payment_changes: Object.fromEntries((subscription.payments || []).map((p) => [p.id, {
        amount: p.amount,
        payment_date: p.payment_date,
        device_count: p.device_count,
        description: p.description || '',
      }])),
    });
    setEditCustomer(customerDefaults);
    setEditNewDevice({ device_id: '', start_date: subscription.start_date, end_date: subscription.end_date });
    setActionError('');
    setEditCustomerLoading(true);
    setEditModalOpen(true);

    try {
      if (isOrg && subscription.organization) {
        const org = await organizationsAPI.get(subscription.organization);
        setEditCustomer({
          name: org.name || '', code: org.code || '', registration_number: org.registration_number || '',
          economy_code: org.economy_code || '', phone: org.phone || '', email: org.email || '',
          address: org.address || '', website: org.website || '',
        });
      } else if (!isOrg && subscription.user) {
        const user = await usersAPI.get(subscription.user);
        setEditCustomer({
          first_name: user.first_name || '', last_name: user.last_name || '', mobile: user.mobile || '',
          national_id: user.national_id || '', address: user.address || '',
        });
      }
    } catch (err) {
      console.error('Error loading customer details for edit:', err);
      setActionError('اطلاعات مشتری برای ویرایش کامل بارگذاری نشد.');
    } finally {
      setEditCustomerLoading(false);
    }
  };

  const handleModify = async (e) => {
    e.preventDefault();
    if (!editForm.start_date || !editForm.end_date || editForm.start_date > editForm.end_date) {
      setActionError('بازه تاریخ قرارداد نامعتبر است.');
      return;
    }

    const customer_changes = isOrg
      ? editCustomer
      : editCustomer;

    const payment_changes = Object.entries(editForm.payment_changes).map(([paymentId, payment]) => ({
      id: Number(paymentId),
      ...payment,
      amount: Number(payment.amount),
      device_count: Number(payment.device_count) || 0,
    }));

    setSaving(true);
    setActionError('');
    try {
      await subscriptionsAPI.modify(id, {
        contract_changes: {
          start_date: editForm.start_date,
          end_date: editForm.end_date,
          notes: editForm.notes,
        },
        customer_changes,
        remove_device_ids: editForm.remove_device_ids,
        add_devices: editForm.add_devices.filter((_, index) => !editForm.remove_added_device_indices.includes(index)),
        payment_changes,
      });
      setEditModalOpen(false);
      refetch();
    } catch (err) {
      console.error('Error modifying contract:', err);
      const msg = err.response?.data
        ? Object.entries(err.response.data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'خطا در ویرایش قرارداد';
      setActionError(msg);
    } finally {
      setSaving(false);
    }
  };

  const toggleEditDeviceRemoval = (linkId) => {
    setEditForm((prev) => ({
      ...prev,
      remove_device_ids: prev.remove_device_ids.includes(linkId)
        ? prev.remove_device_ids.filter((id) => id !== linkId)
        : [...prev.remove_device_ids, linkId],
    }));
  };

  const addEditDevice = () => {
    if (!editNewDevice.device_id) {
      setActionError('برای افزودن دستگاه، یک دستگاه انتخاب کنید.');
      return;
    }
    if (editNewDevice.start_date < editForm.start_date || editNewDevice.end_date > editForm.end_date) {
      setActionError('تاریخ دستگاه باید داخل بازه قرارداد باشد.');
      return;
    }
    setEditForm((prev) => ({
      ...prev,
      add_devices: [...prev.add_devices, { ...editNewDevice, device_id: Number(editNewDevice.device_id) }],
    }));
    setEditNewDevice({ device_id: '', start_date: editForm.start_date, end_date: editForm.end_date });
    setActionError('');
  };

  const updateEditPayment = (paymentId, field, value) => {
    setEditForm((prev) => ({
      ...prev,
      payment_changes: {
        ...prev.payment_changes,
        [paymentId]: { ...prev.payment_changes[paymentId], [field]: value },
      },
    }));
  };

  const openRenewModal = async () => {
    const customerDefaults = isOrg
      ? {
          name: subscription.organization_name || '',
          code: subscription.organization_code || '',
          registration_number: '',
          economy_code: '',
          phone: subscription.organization_phone || '',
          email: subscription.organization_email || '',
          address: '',
          website: '',
        }
      : {
          first_name: '',
          last_name: '',
          mobile: '',
          national_id: '',
          address: '',
        };

    setRenewForm({
      new_end_date: subscription.end_date,
      notes: '',
      add_devices: [],
      remove_device_ids: [],
      payments: [],
      customer_changes: {},
    });
    setRenewCustomer(customerDefaults);
    setRenewNewDevice({
      device_id: '',
      start_date: subscription.end_date,
      end_date: subscription.end_date,
    });
    setRenewPaymentDraft({
      amount: '',
      payment_date: todayGregorian(),
      device_count: subscription.device_count || 0,
      description: '',
    });
    setActionError('');
    setRenewSections({ info: true, customer: false, devices: false, payments: false });
    setRenewCustomerLoading(true);
    setRenewModalOpen(true);

    try {
      if (isOrg && subscription.organization) {
        const org = await organizationsAPI.get(subscription.organization);
        setRenewCustomer({
          name: org.name || '',
          code: org.code || '',
          registration_number: org.registration_number || '',
          economy_code: org.economy_code || '',
          phone: org.phone || '',
          email: org.email || '',
          address: org.address || '',
          website: org.website || '',
        });
      } else if (!isOrg && subscription.user) {
        const user = await usersAPI.get(subscription.user);
        setRenewCustomer({
          first_name: user.first_name || '',
          last_name: user.last_name || '',
          mobile: user.mobile || '',
          national_id: user.national_id || '',
          address: user.address || '',
        });
      }
    } catch (err) {
      console.error('Error loading customer details for renewal:', err);
      setActionError('اطلاعات کامل مشتری برای ویرایش بارگذاری نشد. سایر بخش‌های تمدید قابل استفاده هستند.');
    } finally {
      setRenewCustomerLoading(false);
    }
  };

  const handleRenew = async (e) => {
    e.preventDefault();

    if (!renewForm.new_end_date || renewForm.new_end_date <= subscription.end_date) {
      setActionError('تاریخ پایان جدید باید بعد از تاریخ پایان فعلی باشد.');
      return;
    }

    setSaving(true);
    setActionError('');
    try {
      const customer_changes = isOrg
        ? {
            name: renewCustomer.name || '',
            code: renewCustomer.code || '',
            registration_number: renewCustomer.registration_number || '',
            economy_code: renewCustomer.economy_code || '',
            phone: renewCustomer.phone || '',
            email: renewCustomer.email || '',
            address: renewCustomer.address || '',
            website: renewCustomer.website || '',
          }
        : {
            first_name: renewCustomer.first_name || '',
            last_name: renewCustomer.last_name || '',
            mobile: renewCustomer.mobile || '',
            national_id: renewCustomer.national_id || '',
            address: renewCustomer.address || '',
          };

      await subscriptionsAPI.renew(id, {
        ...renewForm,
        customer_changes,
      });
      setRenewModalOpen(false);
      setRenewForm({
        new_end_date: '',
        notes: '',
        add_devices: [],
        remove_device_ids: [],
        payments: [],
        customer_changes: {},
      });
      refetch();
    } catch (err) {
      console.error('Error renewing:', err);
      const msg = err.response?.data
        ? Object.entries(err.response.data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'خطا در تمدید قرارداد';
      setActionError(msg);
    } finally {
      setSaving(false);
    }
  };

  const toggleRenewDeviceRemoval = (linkId) => {
    setRenewForm((prev) => ({
      ...prev,
      remove_device_ids: prev.remove_device_ids.includes(linkId)
        ? prev.remove_device_ids.filter((id) => id !== linkId)
        : [...prev.remove_device_ids, linkId],
    }));
  };

  const addRenewDevice = () => {
    if (!renewNewDevice.device_id) {
      setActionError('برای افزودن دستگاه، یک دستگاه انتخاب کنید.');
      return;
    }

    const alreadyAdded = renewForm.add_devices.some(
      (item) => Number(item.device_id) === Number(renewNewDevice.device_id)
    );
    if (alreadyAdded) {
      setActionError('این دستگاه قبلاً برای تمدید انتخاب شده است.');
      return;
    }

    setRenewForm((prev) => ({
      ...prev,
      add_devices: [...prev.add_devices, { ...renewNewDevice, device_id: Number(renewNewDevice.device_id) }],
    }));
    setRenewNewDevice({
      device_id: '',
      start_date: subscription.end_date,
      end_date: renewForm.new_end_date || subscription.end_date,
    });
    setActionError('');
  };

  const addRenewPayment = () => {
    if (!renewPaymentDraft.amount || Number(renewPaymentDraft.amount) <= 0) {
      setActionError('مبلغ پرداخت باید بیشتر از صفر باشد.');
      return;
    }

    setRenewForm((prev) => ({
      ...prev,
      payments: [...prev.payments, {
        ...renewPaymentDraft,
        amount: Number(renewPaymentDraft.amount),
        device_count: Number(renewPaymentDraft.device_count) || 0,
      }],
    }));
    setRenewPaymentDraft({
      amount: '',
      payment_date: todayGregorian(),
      device_count: subscription.device_count || 0,
      description: '',
    });
    setActionError('');
  };

  // ═══ تغییر وضعیت ═══
  const handleStatusChange = async (action) => {
    if (!confirm('آیا از تغییر وضعیت قرارداد اطمینان دارید؟')) return;
    try {
      await subscriptionsAPI[action](id);
      refetch();
    } catch (err) {
      console.error('Error:', err);
      alert('خطا در انجام عملیات');
    }
  };

  // ═══ لغو قرارداد ═══
  const handleCancel = async () => {
    setSaving(true);
    try {
      await subscriptionsAPI.delete(id);
      setCancelModalOpen(false);
      refetch();
    } catch (err) {
      console.error('Error cancelling:', err);
      alert('خطا در لغو قرارداد');
    } finally {
      setSaving(false);
    }
  };

  // ═══ افزودن دستگاه ═══
  const handleAddDevice = async (e) => {
    e.preventDefault();
    setSaving(true);
    setActionError('');
    try {
      await subscriptionDevicesAPI.create({
        subscription: Number(id),
        device: Number(deviceForm.device),
        start_date: deviceForm.start_date,
        end_date: deviceForm.end_date,
      });
      setDeviceModalOpen(false);
      setDeviceForm({ device: '', start_date: '', end_date: '' });
      refetch();
    } catch (err) {
      console.error('Error adding device:', err);
      const msg = err.response?.data
        ? Object.entries(err.response.data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'خطا در افزودن دستگاه';
      setActionError(msg);
    } finally {
      setSaving(false);
    }
  };

  // ═══ حذف دستگاه ═══
  const handleRemoveDevice = async (linkId) => {
    if (!confirm('آیا از حذف این دستگاه از قرارداد اطمینان دارید؟\nدستگاه به انبار برمی‌گردد.')) return;
    try {
      await subscriptionDevicesAPI.delete(linkId);
      refetch();
    } catch (err) {
      console.error('Error removing device:', err);
      alert('خطا در حذف دستگاه');
    }
  };

  // ═══ افزودن پرداخت ═══
  const handleAddPayment = async (e) => {
    e.preventDefault();
    setSaving(true);
    setActionError('');
    try {
      await subscriptionPaymentsAPI.create({
        subscription: Number(id),
        amount: Number(paymentForm.amount),
        payment_date: paymentForm.payment_date,
        device_count: Number(paymentForm.device_count) || 0,
        description: paymentForm.description,
      });
      setPaymentModalOpen(false);
      setPaymentForm({
        amount: '',
        payment_date: todayGregorian(),
        device_count: 0,
        description: '',
      });
      refetch();
    } catch (err) {
      console.error('Error adding payment:', err);
      const msg = err.response?.data
        ? Object.entries(err.response.data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`).join('\n')
        : 'خطا در افزودن پرداخت';
      setActionError(msg);
    } finally {
      setSaving(false);
    }
  };

  // ═══ حذف پرداخت ═══
  const handleRemovePayment = async (paymentId) => {
    if (!confirm('آیا از حذف این پرداخت اطمینان دارید؟')) return;
    try {
      await subscriptionPaymentsAPI.delete(paymentId);
      refetch();
    } catch (err) {
      console.error('Error removing payment:', err);
      alert('خطا در حذف پرداخت');
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="جزئیات قرارداد" subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="جزئیات قرارداد" subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  if (!subscription) return null;

  const st = statusMap[subscription.status] || statusMap.expired;
  const isOrg = subscription.customer_type === 'organization';
  const daysLeft = subscription.days_until_expiry;
  const isCancelled = subscription.status === 'cancelled';

  const customerName = isOrg
    ? subscription.organization_name || 'سازمان بدون نام'
    : subscription.user_name || 'مشتری بدون نام';

  const customerMeta = isOrg
    ? [subscription.organization_code && `کد سازمان: ${subscription.organization_code}`, subscription.organization_phone]
        .filter(Boolean)
        .join(' · ')
    : subscription.user?.username || '';

  const totalPayments = Number(subscription.total_payment_amount || 0);
  const paidPayments = Number(subscription.paid_payment_amount || 0);
  const futurePayments = Number(subscription.future_payment_amount || 0);
  const outstandingPayments = Number(subscription.outstanding_payment_amount || 0);

  const sectionClass = 'border border-border-base rounded-2xl bg-bg-elevated overflow-hidden';

  return (
    <div className="space-y-5 pb-8">

      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={() => navigate('/panel/subscriptions')}
            className="p-2.5 rounded-xl text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors"
            aria-label="بازگشت"
          >
            <ArrowRight size={19} />
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold text-text-primary">جزئیات قرارداد</h1>
              <Badge variant={st.variant}>{st.label}</Badge>
              <Badge variant={isOrg ? 'brand' : 'info'}>{isOrg ? 'سازمانی' : 'شخصی'}</Badge>
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-text-muted">
              <span className="font-mono">{subscription.contract_number}</span>
              <span>·</span>
              <span>{customerName}</span>
            </div>
          </div>
        </div>

        {isSiteAdmin && !isCancelled && (
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant="secondary" icon={Pencil} onClick={openEditModal}>ویرایش قرارداد</Button>
            <Button variant="secondary" icon={RotateCw} onClick={openRenewModal}>تمدید</Button>
            {subscription.status === 'active' && (
              <Button variant="secondary" icon={Ban} onClick={() => handleStatusChange('suspend')}>تعلیق</Button>
            )}
            {subscription.status === 'suspended' && (
              <Button variant="secondary" icon={CheckCircle2} onClick={() => handleStatusChange('activate')}>فعال‌سازی</Button>
            )}
            {subscription.status === 'expired' && (
              <Button variant="secondary" icon={RefreshCw} onClick={() => handleStatusChange('activate')}>فعال‌سازی مجدد</Button>
            )}
            <Button variant="danger" icon={XCircle} onClick={() => setCancelModalOpen(true)}>لغو قرارداد</Button>
          </div>
        )}
      </div>

      {/* هشدارها */}
      {isCancelled && (
        <div className="bg-danger/10 border border-danger/30 rounded-2xl p-4 flex items-start gap-3">
          <XCircle size={20} className="text-danger flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-danger mb-1">این قرارداد لغو شده است</h4>
            <p className="text-xs text-text-secondary leading-6">
              سوابق قرارداد حفظ شده‌اند و این قرارداد فقط به‌صورت تاریخی قابل مشاهده است.
            </p>
          </div>
        </div>
      )}

      {!isCancelled && daysLeft === 0 && subscription.status !== 'expired' && (
        <div className="bg-danger/10 border border-danger/30 rounded-2xl p-4 flex items-start gap-3">
          <AlertTriangle size={20} className="text-danger flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-danger mb-1">امروز آخرین روز قرارداد است</h4>
            <p className="text-xs text-text-secondary leading-6">از فردا این قرارداد منقضی می‌شود.</p>
          </div>
        </div>
      )}

      {!isCancelled && subscription.is_expiring_soon && daysLeft > 0 && (
        <div className="bg-warning/10 border border-warning/30 rounded-2xl p-4 flex items-start gap-3">
          <AlertTriangle size={20} className="text-warning flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-warning mb-1">قرارداد به‌زودی منقضی می‌شود</h4>
            <p className="text-xs text-text-secondary leading-6">{daysLeft} روز تا پایان قرارداد مانده است.</p>
          </div>
        </div>
      )}

      {subscription.status === 'expired' && !isCancelled && (
        <div className="bg-muted/10 border border-border-base rounded-2xl p-4 flex items-start gap-3">
          <AlertTriangle size={20} className="text-text-muted flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-text-muted mb-1">این قرارداد منقضی شده است</h4>
            <p className="text-xs text-text-secondary leading-6">{Math.abs(daysLeft)} روز از انقضا گذشته است.</p>
          </div>
        </div>
      )}

      {/* ═══ بخش مستقل مشتری ═══ */}
      <section className="rounded-2xl border border-border-base bg-bg-elevated overflow-hidden">
        <div className="p-5 border-b border-border-base">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-brand-500/10 flex items-center justify-center">
                {isOrg ? <Building2 size={21} className="text-brand-400" /> : <UserIcon size={21} className="text-brand-400" />}
              </div>
              <div>
                <div className="text-[11px] text-text-muted mb-1">مشتری</div>
                <h2 className="text-lg font-semibold text-text-primary">{customerName}</h2>
                <p className="text-xs text-text-muted mt-1">{customerMeta || (isOrg ? 'اطلاعات سازمان' : 'حساب مشتری شخصی')}</p>
              </div>
            </div>
            <Badge variant={isOrg ? 'brand' : 'info'}>{isOrg ? 'سازمان' : 'شخص'}</Badge>
          </div>
        </div>

        <div className="p-5">
          {isOrg ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <DetailItem icon={Building2} label="نام سازمان" value={subscription.organization_name} />
              <DetailItem icon={Hash} label="کد سازمان" value={subscription.organization_code} mono />
              <DetailItem icon={Phone} label="تلفن" value={subscription.organization_phone} mono />
              <DetailItem icon={Hash} label="شماره ثبت" value={subscription.organization_registration_number} mono />
              <DetailItem icon={MapPin} label="آدرس" value={subscription.organization_address} />
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <DetailItem icon={UserIcon} label="نام و نام خانوادگی" value={subscription.user_name} />
              <DetailItem icon={Phone} label="موبایل" value={subscription.user_mobile} mono />
              <DetailItem icon={Hash} label="کد ملی" value={subscription.user_national_id} mono />
              <DetailItem icon={MapPin} label="آدرس" value={subscription.user_address} />
            </div>
          )}
        </div>
      </section>

      {/* ═══ قرارداد ═══ */}
      <section className="rounded-2xl border border-border-base bg-bg-elevated overflow-hidden">
        <div className="p-5 border-b border-border-base">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="text-[11px] text-text-muted mb-1">قرارداد</div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-semibold font-mono text-text-primary">{subscription.contract_number}</h2>
                <Badge variant={st.variant}>{st.label}</Badge>
              </div>
              <p className="text-xs text-text-muted mt-1">تمام اطلاعات، دستگاه‌ها، پرداخت‌ها و تاریخچه مربوط به همین قرارداد در این بخش قرار دارد.</p>
            </div>
            <div className="text-left">
              <div className="text-[10px] text-text-muted">مبلغ قرارداد</div>
              <div className="text-base font-bold font-mono text-brand-400 mt-1">
                {Number(subscription.price || 0).toLocaleString('fa-IR')} ریال
              </div>
            </div>
          </div>
        </div>

        <div className="p-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">شروع قرارداد</div>
              <div className="font-mono text-sm text-text-primary">{toJalali(subscription.start_date)}</div>
            </div>
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">پایان فعلی قرارداد</div>
              <div className="font-mono text-sm text-brand-400">{toJalali(subscription.end_date)}</div>
            </div>
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">زمان باقی‌مانده</div>
              <div className={`font-mono text-sm font-medium ${daysLeft < 0 ? 'text-danger' : daysLeft <= 30 ? 'text-warning' : 'text-text-primary'}`}>
                {daysLeft < 0 ? `منقضی · ${Math.abs(daysLeft)} روز` : `${daysLeft} روز`}
              </div>
            </div>
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">دستگاه‌های فعال قرارداد</div>
              <div className="font-mono text-sm text-text-primary">{subscription.active_device_count ?? 0} دستگاه</div>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">کل مبالغ ثبت‌شده</div>
              <div className="font-mono text-sm font-semibold text-text-primary">{Number(subscription.total_payment_amount || 0).toLocaleString('fa-IR')} ریال</div>
            </div>
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">پرداخت‌شده تا امروز</div>
              <div className="font-mono text-sm font-semibold text-brand-400">{Number(subscription.paid_payment_amount || 0).toLocaleString('fa-IR')} ریال</div>
            </div>
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">پرداخت آینده</div>
              <div className="font-mono text-sm font-semibold text-text-primary">{Number(subscription.future_payment_amount || 0).toLocaleString('fa-IR')} ریال</div>
            </div>
            <div className="p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">مانده پرداخت</div>
              <div className="font-mono text-sm font-semibold text-warning">{Number(subscription.outstanding_payment_amount || 0).toLocaleString('fa-IR')} ریال</div>
            </div>
          </div>

          {subscription.notes && (
            <div className="mt-4 p-4 rounded-xl bg-bg-base border border-border-base">
              <div className="text-[10px] text-text-muted mb-1">یادداشت قرارداد</div>
              <p className="text-xs text-text-secondary leading-6">{subscription.notes}</p>
            </div>
          )}
        </div>
      </section>

      {/* ═══ دستگاه‌های قرارداد ═══ */}
      <section className={sectionClass}>
        <div className="px-5 py-4 border-b border-border-base flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">دستگاه‌های قرارداد</h3>
            <p className="text-[11px] text-text-muted mt-1">{subscription.devices?.length || 0} دستگاه تخصیص‌یافته به این قرارداد</p>
          </div>
          {isSiteAdmin && !isCancelled && (
            <Button
              size="sm"
              icon={Plus}
              variant="secondary"
              onClick={() => {
                setDeviceForm({ device: '', start_date: subscription.start_date, end_date: subscription.end_date });
                setActionError('');
                setDeviceModalOpen(true);
              }}
            >
              افزودن دستگاه
            </Button>
          )}
        </div>
        {(!subscription.devices || subscription.devices.length === 0) ? (
          <div className="py-10 text-center">
            <Package size={30} className="text-text-muted mx-auto mb-2" />
            <p className="text-xs text-text-muted">هنوز دستگاهی به این قرارداد تخصیص داده نشده است.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base bg-bg-base/50">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">IMEI</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">مدل</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">SIM</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">خودرو</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">شروع</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">پایان</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {subscription.devices.map((d) => (
                  <tr key={d.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                    <td className="py-3 px-4 font-mono text-text-primary text-xs">{d.device_imei}</td>
                    <td className="py-3 px-4 text-text-secondary text-xs">{d.device_model || '—'}</td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{d.device_sim || '—'}</td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{d.vehicle_plate || '—'}</td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{toJalali(d.start_date)}</td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{toJalali(d.end_date)}</td>
                    <td className="py-3 px-4"><Badge variant={d.is_active ? 'success' : 'muted'}>{d.is_active ? 'فعال' : 'غیرفعال'}</Badge></td>
                    <td className="py-3 px-2">
                      {isSiteAdmin && !isCancelled && (
                        <ActionMenu items={[{ label: 'حذف از قرارداد', icon: Trash2, variant: 'danger', onClick: () => handleRemoveDevice(d.id) }]} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ═══ پرداخت‌های قرارداد ═══ */}
      <section className={sectionClass}>
        <div className="px-5 py-4 border-b border-border-base flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">پرداخت‌های قرارداد</h3>
            <p className="text-[11px] text-text-muted mt-1">{subscription.payments?.length || 0} پرداخت ثبت‌شده</p>
          </div>
          {isSiteAdmin && !isCancelled && (
            <Button
              size="sm"
              icon={Plus}
              variant="secondary"
              onClick={() => {
                setPaymentForm({ amount: '', payment_date: todayGregorian(), device_count: subscription.device_count || 0, description: '' });
                setActionError('');
                setPaymentModalOpen(true);
              }}
            >
              افزودن پرداخت
            </Button>
          )}
        </div>
        {(!subscription.payments || subscription.payments.length === 0) ? (
          <div className="py-10 text-center">
            <CreditCard size={30} className="text-text-muted mx-auto mb-2" />
            <p className="text-xs text-text-muted">هنوز پرداختی برای این قرارداد ثبت نشده است.</p>
          </div>
        ) : (
          <div className="p-4 space-y-2">
            {subscription.payments.map((p) => {
              const paymentDate = new Date(p.payment_date);
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              const isFuture = paymentDate > today;
              const isToday = paymentDate.getTime() === today.getTime();

              return (
                <div key={p.id} className="flex items-center justify-between gap-4 p-3.5 bg-bg-base border border-border-base rounded-xl">
                  <div className="flex items-center gap-4 min-w-0 flex-wrap">
                    <span className="font-mono text-sm font-medium text-text-primary">{Number(p.amount).toLocaleString('fa-IR')} ریال</span>
                    <span className="text-xs text-text-muted">{p.device_count} دستگاه</span>
                    <span className="text-xs text-text-muted font-mono">{toJalali(p.payment_date)}</span>
                    {p.description && <span className="text-xs text-text-muted truncate">{p.description}</span>}
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {isFuture && <Badge variant="info">پرداخت در آینده</Badge>}
                    {isToday && <Badge variant="warning">امروز</Badge>}
                    {isSiteAdmin && !isCancelled && (
                      <button onClick={() => handleRemovePayment(p.id)} className="p-1.5 rounded-field text-text-muted hover:bg-danger/10 hover:text-danger transition-colors" title="حذف پرداخت">
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
            <div className="flex items-center justify-between p-4 rounded-xl bg-brand-500/10 border border-brand-500/30">
              <span className="text-sm text-text-secondary">مجموع پرداخت‌های ثبت‌شده</span>
              <span className="font-mono text-base font-bold text-brand-400">{totalPayments.toLocaleString('fa-IR')} ریال</span>
            </div>
          </div>
        )}
      </section>

      {/* ═══ تاریخچه قرارداد ═══ */}
      {subscription.operations && subscription.operations.length > 0 && (
        <section className={sectionClass}>
          <div className="px-5 py-4 border-b border-border-base">
            <h3 className="text-sm font-semibold text-text-primary">تاریخچه قرارداد</h3>
            <p className="text-[11px] text-text-muted mt-1">{subscription.operations.length} عملیات ثبت‌شده روی این قرارداد</p>
          </div>
          <div className="p-4 space-y-2">
            {subscription.operations.map((operation) => (
              <details key={operation.id} className="group border border-border-base rounded-xl bg-bg-base overflow-hidden">
                <summary className="list-none cursor-pointer px-4 py-3.5 flex items-center justify-between gap-4 hover:bg-bg-hover transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-brand-500/10 flex items-center justify-center flex-shrink-0">
                      <History size={16} className="text-brand-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-text-primary">{operation.operation_type_display || operation.operation_type}</div>
                      <div className="text-[10px] text-text-muted mt-0.5">
                        {operation.performed_at ? new Date(operation.performed_at).toLocaleString('fa-IR') : '—'}
                        {operation.performed_by_name ? ` · توسط ${operation.performed_by_name}` : ''}
                      </div>
                    </div>
                  </div>
                  <span className="text-text-muted text-xs group-open:rotate-180 transition-transform">⌄</span>
                </summary>
                <div className="px-4 pb-4 space-y-3 border-t border-border-base">
                  {(operation.old_end_date || operation.new_end_date) && (
                    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 pt-4">
                      <div className="p-3 rounded-lg bg-bg-elevated text-center">
                        <div className="text-[10px] text-text-muted mb-1">پایان قبلی</div>
                        <div className="text-sm font-mono text-text-secondary">{toJalali(operation.old_end_date)}</div>
                      </div>
                      <ArrowRight size={15} className="text-brand-400 rotate-180" />
                      <div className="p-3 rounded-lg bg-bg-elevated text-center">
                        <div className="text-[10px] text-text-muted mb-1">پایان جدید</div>
                        <div className="text-sm font-mono text-brand-400">{toJalali(operation.new_end_date)}</div>
                      </div>
                    </div>
                  )}
                  {operation.changes?.length > 0 && (
                    <div className="pt-4">
                      <div className="text-[10px] font-medium text-text-muted mb-2">تغییرات این عملیات</div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                        {operation.changes.map((change) => {
                          const changeInfo = getChangeDisplay(change);
                          return (
                            <div
                              key={change.id}
                              className="rounded-xl border border-border-base bg-bg-elevated p-3.5"
                            >
                              <div className="flex items-center gap-2 mb-3">
                                <div className="w-7 h-7 rounded-lg bg-brand-500/10 flex items-center justify-center flex-shrink-0">
                                  <Pencil size={13} className="text-brand-400" />
                                </div>
                                <div className="text-xs font-medium text-text-primary">
                                  {changeInfo.label}
                                </div>
                              </div>

                              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                                <div className="min-w-0">
                                  <div className="text-[9px] text-text-muted mb-1">قبل</div>
                                  <div className="text-xs text-text-secondary break-words">
                                    {changeInfo.oldValue}
                                  </div>
                                </div>

                                <ArrowRight size={14} className="text-brand-400 rotate-180 flex-shrink-0" />

                                <div className="min-w-0 text-left">
                                  <div className="text-[9px] text-text-muted mb-1">بعد</div>
                                  <div className="text-xs font-medium text-brand-400 break-words">
                                    {changeInfo.newValue}
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {operation.notes && <div className="text-xs text-text-secondary">یادداشت: {operation.notes}</div>}
                </div>
              </details>
            ))}
          </div>
        </section>
      )}

      {/* ═══ مودال ویرایش قرارداد ═══ */}
      <Modal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title="ویرایش قرارداد"
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditModalOpen(false)} disabled={saving}>انصراف</Button>
            <Button type="submit" form="edit-form" disabled={saving || editCustomerLoading}>
              {saving ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
            </Button>
          </>
        }
      >
        <form id="edit-form" onSubmit={handleModify} className="space-y-4 pl-1">
          {actionError && <div className="bg-danger/10 border border-danger/30 rounded-field p-3"><p className="text-xs text-danger whitespace-pre-line">{actionError}</p></div>}

          <div className="border border-border-base rounded-card p-4 space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">اطلاعات قرارداد</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <JalaliDatePicker label="تاریخ شروع قرارداد" value={editForm.start_date} onChange={(val) => setEditForm({...editForm, start_date: val})} required />
              <JalaliDatePicker label="تاریخ پایان قرارداد" value={editForm.end_date} minDate={editForm.start_date} onChange={(val) => setEditForm({...editForm, end_date: val})} required />
            </div>
            <Input label="یادداشت قرارداد" value={editForm.notes} onChange={(e) => setEditForm({...editForm, notes: e.target.value})} />
          </div>

          <div className="border border-border-base rounded-card p-4 space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">اطلاعات مشتری</h3>
            {isOrg ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Input label="نام سازمان" value={editCustomer.name || ''} onChange={(e) => setEditCustomer({...editCustomer,name:e.target.value})} />
                <Input label="کد سازمان" value={editCustomer.code || ''} onChange={(e) => setEditCustomer({...editCustomer,code:e.target.value})} />
                <Input label="شماره ثبت" value={editCustomer.registration_number || ''} onChange={(e) => setEditCustomer({...editCustomer,registration_number:e.target.value})} />
                <Input label="کد اقتصادی" value={editCustomer.economy_code || ''} onChange={(e) => setEditCustomer({...editCustomer,economy_code:e.target.value})} />
                <Input label="تلفن" value={editCustomer.phone || ''} onChange={(e) => setEditCustomer({...editCustomer,phone:e.target.value})} />
                <Input label="ایمیل" value={editCustomer.email || ''} onChange={(e) => setEditCustomer({...editCustomer,email:e.target.value})} />
                <Input label="آدرس" value={editCustomer.address || ''} onChange={(e) => setEditCustomer({...editCustomer,address:e.target.value})} />
                <Input label="وبسایت" value={editCustomer.website || ''} onChange={(e) => setEditCustomer({...editCustomer,website:e.target.value})} />
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Input label="نام" value={editCustomer.first_name || ''} onChange={(e) => setEditCustomer({...editCustomer,first_name:e.target.value})} />
                <Input label="نام خانوادگی" value={editCustomer.last_name || ''} onChange={(e) => setEditCustomer({...editCustomer,last_name:e.target.value})} />
                <Input label="موبایل" value={editCustomer.mobile || ''} onChange={(e) => setEditCustomer({...editCustomer,mobile:e.target.value})} />
                <Input label="کد ملی" value={editCustomer.national_id || ''} onChange={(e) => setEditCustomer({...editCustomer,national_id:e.target.value})} />
                <Input label="آدرس" value={editCustomer.address || ''} onChange={(e) => setEditCustomer({...editCustomer,address:e.target.value})} />
              </div>
            )}
          </div>

          <div className="border border-border-base rounded-card p-4 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-text-primary">دستگاه‌های قرارداد</h3>
              <Button type="button" size="sm" variant="secondary" icon={Plus} onClick={() => setEditDevicePickerModalOpen(true)}>
                افزودن دستگاه جدید
              </Button>
            </div>
            {(subscription.devices || []).map((d) => {
              const marked = editForm.remove_device_ids.includes(d.id);
              return <label key={d.id} className={`flex items-center gap-3 p-3 rounded-field border ${marked ? 'border-danger/40 bg-danger/5' : 'border-border-base bg-bg-base'} cursor-pointer`}>
                <input type="checkbox" checked={marked} onChange={() => toggleEditDeviceRemoval(d.id)} className="accent-danger" />
                <div className="flex-1"><div className="text-xs font-mono">{d.device_imei}</div><div className="text-[10px] text-text-muted">شروع {toJalali(d.start_date)} · پایان {toJalali(d.end_date)}</div></div>
                <span className={`text-[10px] ${marked ? 'text-danger' : 'text-text-muted'}`}>{marked ? 'حذف می‌شود' : 'باقی می‌ماند'}</span>
              </label>;
            })}
            {editForm.add_devices.map((item,index) => {
              const marked = editForm.remove_added_device_indices.includes(index);
              return (
                <label key={`${item.device_id}-${index}`} className={`flex items-center gap-3 p-3 rounded-field border ${marked ? 'border-danger/40 bg-danger/5' : 'border-border-base bg-bg-base'} cursor-pointer`}>
                  <input
                    type="checkbox"
                    checked={marked}
                    onChange={() => setEditForm((prev) => ({
                      ...prev,
                      remove_added_device_indices: prev.remove_added_device_indices.includes(index)
                        ? prev.remove_added_device_indices.filter((i) => i !== index)
                        : [...prev.remove_added_device_indices, index],
                    }))}
                    className="accent-danger"
                  />
                  <div className="flex-1 text-xs font-mono">
                    <div>{(warehouseDevices || []).find((d) => Number(d.id) === Number(item.device_id))?.imei || item.device_id}</div>
                    <div className="text-[10px] text-text-muted">شروع {toJalali(item.start_date)} · پایان {toJalali(item.end_date)}</div>
                  </div>
                  <span className={`text-[10px] ${marked ? 'text-danger' : 'text-text-muted'}`}>
                    {marked ? 'حذف می‌شود' : 'باقی می‌ماند'}
                  </span>
                </label>
              );
            })}
          </div>

          <div className="border border-border-base rounded-card p-4 space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">اصلاح پرداخت‌ها</h3>
            {(subscription.payments || []).map((p) => {
              const payment = editForm.payment_changes[p.id] || p;
              return <div key={p.id} className="grid grid-cols-1 md:grid-cols-4 gap-3 p-3 bg-bg-base border border-border-base rounded-field">
                <Input type="number" label="مبلغ" value={payment.amount} onChange={(e) => updateEditPayment(p.id,'amount',e.target.value)} />
                <JalaliDatePicker label="تاریخ پرداخت" value={payment.payment_date} onChange={(val) => updateEditPayment(p.id,'payment_date',val)} />
                <Input type="number" label="تعداد دستگاه" value={payment.device_count} onChange={(e) => updateEditPayment(p.id,'device_count',e.target.value)} />
                <Input label="توضیحات" value={payment.description || ''} onChange={(e) => updateEditPayment(p.id,'description',e.target.value)} />
              </div>;
            })}
            {(!subscription.payments || subscription.payments.length === 0) && <p className="text-xs text-text-muted">پرداختی برای ویرایش وجود ندارد.</p>}
          </div>
        </form>
      </Modal>

      {/* ═══ مودال تمدید ═══ */}
      <Modal
        open={renewModalOpen}
        onClose={() => setRenewModalOpen(false)}
        title="تمدید قرارداد"
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRenewModalOpen(false)} disabled={saving}>
              انصراف
            </Button>
            <Button type="submit" form="renew-form" disabled={saving || renewCustomerLoading}>
              {saving ? 'در حال ذخیره...' : 'ثبت تمدید'}
            </Button>
          </>
        }
      >
        <form id="renew-form" onSubmit={handleRenew} className="space-y-3 pl-1">
          {actionError && (
            <div className="bg-danger/10 border border-danger/30 rounded-field p-3">
              <p className="text-xs text-danger whitespace-pre-line">{actionError}</p>
            </div>
          )}

          <div className="border border-border-base rounded-card overflow-hidden">
            <button
              type="button"
              onClick={() => toggleRenewSection('info')}
              className="w-full flex items-center justify-between gap-4 p-4 text-right hover:bg-bg-hover transition-colors"
            >
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-text-primary">اطلاعات تمدید</h3>
                <p className="text-[11px] text-text-muted mt-1">تاریخ پایان قرارداد و توضیحات عملیات</p>
              </div>
              <span className="text-text-muted text-lg leading-none flex-shrink-0">{renewSections.info ? '−' : '+'}</span>
            </button>
            {renewSections.info && (
              <div className="px-4 pb-4 space-y-4">

            <JalaliDatePicker
              label="تاریخ پایان جدید"
              value={renewForm.new_end_date}
              onChange={(val) => {
                setRenewForm({ ...renewForm, new_end_date: val });
                setRenewNewDevice((prev) => ({
                  ...prev,
                  end_date: prev.end_date === subscription.end_date ? val : prev.end_date,
                }));
              }}
              minDate={subscription.end_date}
              required
            />
            <Input
              label="یادداشت (اختیاری)"
              value={renewForm.notes}
              onChange={(e) => setRenewForm({ ...renewForm, notes: e.target.value })}
              placeholder="مثلاً تمدید یک‌ساله همراه با افزایش سرویس"
            />
          
              </div>
            )}
          </div>

          <div className="border border-border-base rounded-card overflow-hidden">
            <button
              type="button"
              onClick={() => toggleRenewSection('customer')}
              className="w-full flex items-center justify-between gap-4 p-4 text-right hover:bg-bg-hover transition-colors"
            >
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-text-primary">اطلاعات مشتری</h3>
                <p className="text-[11px] text-text-muted mt-1">هر تغییری که اینجا ثبت شود داخل تاریخچه همین عملیات ذخیره می‌شود.</p>
              </div>
              <span className="text-text-muted text-lg leading-none flex-shrink-0">{renewSections.customer ? '−' : '+'}</span>
            </button>
            {renewSections.customer && (
              <div className="px-4 pb-4 space-y-4">


            {renewCustomerLoading ? (
              <LoadingSpinner />
            ) : isOrg ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input label="نام سازمان" value={renewCustomer.name || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, name: e.target.value })} />
                <Input label="کد سازمان" value={renewCustomer.code || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, code: e.target.value })} />
                <Input label="شماره ثبت" value={renewCustomer.registration_number || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, registration_number: e.target.value })} />
                <Input label="کد اقتصادی" value={renewCustomer.economy_code || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, economy_code: e.target.value })} />
                <Input label="تلفن" value={renewCustomer.phone || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, phone: e.target.value })} />
                <Input label="ایمیل" type="email" value={renewCustomer.email || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, email: e.target.value })} />
                <Input label="وبسایت" value={renewCustomer.website || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, website: e.target.value })} />
                <Input label="آدرس" value={renewCustomer.address || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, address: e.target.value })} />
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input label="نام" value={renewCustomer.first_name || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, first_name: e.target.value })} />
                <Input label="نام خانوادگی" value={renewCustomer.last_name || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, last_name: e.target.value })} />
                <Input label="موبایل" value={renewCustomer.mobile || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, mobile: e.target.value })} />
                <Input label="کد ملی" value={renewCustomer.national_id || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, national_id: e.target.value })} />
                <Input label="آدرس" value={renewCustomer.address || ''} onChange={(e) => setRenewCustomer({ ...renewCustomer, address: e.target.value })} />
              </div>
            )}
          
              </div>
            )}
          </div>

          <div className="border border-border-base rounded-card overflow-hidden">
            <button
              type="button"
              onClick={() => toggleRenewSection('devices')}
              className="w-full flex items-center justify-between gap-4 p-4 text-right hover:bg-bg-hover transition-colors"
            >
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-text-primary">دستگاه‌های قرارداد</h3>
                <p className="text-[11px] text-text-muted mt-1">می‌توانید هم‌زمان دستگاه اضافه یا از قرارداد خارج کنید.</p>
              </div>
              <span className="text-text-muted text-lg leading-none flex-shrink-0">{renewSections.devices ? '−' : '+'}</span>
            </button>
            {renewSections.devices && (
              <div className="px-4 pb-4 space-y-4">


            {(subscription.devices || []).length > 0 ? (
              <div className="space-y-2">
                {subscription.devices.map((d) => {
                  const marked = renewForm.remove_device_ids.includes(d.id);
                  return (
                    <label key={d.id} className={`flex items-center gap-3 p-3 rounded-field border ${marked ? 'border-danger/40 bg-danger/5' : 'border-border-base bg-bg-base'} cursor-pointer`}>
                      <input
                        type="checkbox"
                        checked={marked}
                        onChange={() => toggleRenewDeviceRemoval(d.id)}
                        className="accent-danger"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-mono text-text-primary">{d.device_imei}</div>
                        <div className="text-[10px] text-text-muted">{d.device_model || '—'} · پایان {toJalali(d.end_date)}</div>
                      </div>
                      <span className={`text-[10px] ${marked ? 'text-danger' : 'text-text-muted'}`}>
                        {marked ? 'حذف می‌شود' : 'باقی می‌ماند'}
                      </span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-text-muted">این قرارداد در حال حاضر دستگاه فعالی ندارد.</p>
            )}

            <div className="p-3 bg-bg-base border border-border-base rounded-field space-y-3">
              <div className="text-xs font-medium text-text-secondary">افزودن دستگاه از انبار</div>
              <Select
                label="دستگاه"
                placeholder="انتخاب دستگاه انبار..."
                value={renewNewDevice.device_id}
                onChange={(e) => setRenewNewDevice({ ...renewNewDevice, device_id: e.target.value })}
                options={warehouseOptions.filter((option) => !renewForm.add_devices.some((item) => Number(item.device_id) === Number(option.value)))}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <JalaliDatePicker
                  label="شروع دستگاه"
                  value={renewNewDevice.start_date}
                  minDate={subscription.start_date}
                  maxDate={renewForm.new_end_date}
                  onChange={(val) => setRenewNewDevice({ ...renewNewDevice, start_date: val })}
                  required
                />
                <JalaliDatePicker
                  label="پایان دستگاه"
                  value={renewNewDevice.end_date}
                  minDate={subscription.start_date}
                  maxDate={renewForm.new_end_date}
                  onChange={(val) => setRenewNewDevice({ ...renewNewDevice, end_date: val })}
                  required
                />
              </div>
              <Button type="button" size="sm" variant="secondary" icon={Plus} onClick={addRenewDevice}>
                افزودن به تمدید
              </Button>
            </div>

            {renewForm.add_devices.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-medium text-text-secondary">دستگاه‌های انتخاب‌شده برای افزودن</div>
                {renewForm.add_devices.map((item, index) => {
                  const device = (warehouseDevices || []).find((d) => Number(d.id) === Number(item.device_id));
                  return (
                    <div key={`${item.device_id}-${index}`} className="flex items-center gap-3 p-3 bg-bg-base border border-border-base rounded-field">
                      <div className="flex-1">
                        <div className="text-xs font-mono">{device?.imei || item.device_id}</div>
                        <div className="text-[10px] text-text-muted">{toJalali(item.start_date)} تا {toJalali(item.end_date)}</div>
                      </div>
                      <button
                        type="button"
                        className="p-1.5 text-text-muted hover:text-danger"
                        onClick={() => setRenewForm((prev) => ({
                          ...prev,
                          add_devices: prev.add_devices.filter((_, i) => i !== index),
                        }))}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          
              </div>
            )}
          </div>

          <div className="border border-border-base rounded-card overflow-hidden">
            <button
              type="button"
              onClick={() => toggleRenewSection('payments')}
              className="w-full flex items-center justify-between gap-4 p-4 text-right hover:bg-bg-hover transition-colors"
            >
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-text-primary">پرداخت‌های این تمدید</h3>
                <p className="text-[11px] text-text-muted mt-1">تمام پرداخت‌های اضافه‌شده با همین عملیات تمدید مرتبط می‌شوند.</p>
              </div>
              <span className="text-text-muted text-lg leading-none flex-shrink-0">{renewSections.payments ? '−' : '+'}</span>
            </button>
            {renewSections.payments && (
              <div className="px-4 pb-4 space-y-4">


            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Input
                type="number"
                label="مبلغ (ریال)"
                value={renewPaymentDraft.amount}
                onChange={(e) => setRenewPaymentDraft({ ...renewPaymentDraft, amount: e.target.value })}
                placeholder="مثلاً 50000000"
              />
              <JalaliDatePicker
                label="تاریخ پرداخت"
                value={renewPaymentDraft.payment_date}
                onChange={(val) => setRenewPaymentDraft({ ...renewPaymentDraft, payment_date: val })}
              />
              <Input
                type="number"
                label="تعداد دستگاه"
                value={renewPaymentDraft.device_count}
                onChange={(e) => setRenewPaymentDraft({ ...renewPaymentDraft, device_count: e.target.value })}
              />
              <Input
                label="توضیحات پرداخت"
                value={renewPaymentDraft.description}
                onChange={(e) => setRenewPaymentDraft({ ...renewPaymentDraft, description: e.target.value })}
                placeholder="مثلاً پرداخت تمدید دو دستگاه"
              />
            </div>

            <Button type="button" size="sm" variant="secondary" icon={Plus} onClick={addRenewPayment}>
              افزودن پرداخت به تمدید
            </Button>

            {renewForm.payments.length > 0 && (
              <div className="space-y-2">
                {renewForm.payments.map((payment, index) => (
                  <div key={index} className="flex items-center gap-3 p-3 bg-bg-base border border-border-base rounded-field">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-mono">{Number(payment.amount).toLocaleString('fa-IR')} ریال</div>
                      <div className="text-[10px] text-text-muted">
                        {toJalali(payment.payment_date)} · {payment.device_count || 0} دستگاه
                        {payment.description ? ` · ${payment.description}` : ''}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="p-1.5 text-text-muted hover:text-danger"
                      onClick={() => setRenewForm((prev) => ({
                        ...prev,
                        payments: prev.payments.filter((_, i) => i !== index),
                      }))}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          
              </div>
            )}
          </div>

          <div className="text-[10px] text-text-muted leading-relaxed px-1">
            هر چیزی که در این فرم تغییر دهید در قالب یک <strong>عملیات تمدید</strong> ثبت می‌شود؛
            یعنی تاریخ، اطلاعات مشتری، دستگاه‌های افزوده/حذف‌شده و پرداخت‌ها همگی به یک رویداد واحد متصل خواهند بود.
          </div>
        </form>
      </Modal>

      <Modal
        open={editDevicePickerModalOpen}
        onClose={() => setEditDevicePickerModalOpen(false)}
        title="افزودن دستگاه به قرارداد"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditDevicePickerModalOpen(false)}>
              انصراف
            </Button>
            <Button type="button" onClick={() => {
              if (!editNewDevice.device_id) {
                setActionError('برای افزودن دستگاه، یک دستگاه انتخاب کنید.');
                return;
              }
              addEditDevice();
              setEditDevicePickerModalOpen(false);
            }}>
              افزودن به ویرایش
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {actionError && (
            <div className="bg-danger/10 border border-danger/30 rounded-field p-3">
              <p className="text-xs text-danger whitespace-pre-line">{actionError}</p>
            </div>
          )}
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-text-secondary">انتخاب از دستگاه‌های موجود در انبار</div>
            <Button type="button" size="sm" variant="secondary" icon={Plus} onClick={() => setEditAddDeviceModalOpen(true)}>
              افزودن دستگاه جدید
            </Button>
          </div>
          <Select
            label="دستگاه"
            placeholder="انتخاب دستگاه انبار..."
            value={editNewDevice.device_id}
            onChange={(e) => setEditNewDevice({...editNewDevice,device_id:e.target.value})}
            options={warehouseOptions.filter((option) => !editForm.add_devices.some((item) => Number(item.device_id) === Number(option.value)))}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <JalaliDatePicker label="شروع دستگاه" value={editNewDevice.start_date} minDate={editForm.start_date} maxDate={editForm.end_date} onChange={(val) => setEditNewDevice({...editNewDevice,start_date:val})} required />
            <JalaliDatePicker label="پایان دستگاه" value={editNewDevice.end_date} minDate={editForm.start_date} maxDate={editForm.end_date} onChange={(val) => setEditNewDevice({...editNewDevice,end_date:val})} required />
          </div>
        </div>
      </Modal>

      {/* ═══ افزودن دستگاه جدید از داخل ویرایش قرارداد ═══ */}
      <AddDeviceModal
        open={editAddDeviceModalOpen}
        onClose={() => setEditAddDeviceModalOpen(false)}
        onSuccess={async (newDevice) => {
          await refetchWarehouseDevices();
          setEditNewDevice({
            device_id: newDevice.id,
            start_date: editForm.start_date,
            end_date: editForm.end_date,
          });
          setActionError('');
        }}
      />

      {/* ═══ مودال افزودن دستگاه ═══ */}
      <Modal
        open={deviceModalOpen}
        onClose={() => setDeviceModalOpen(false)}
        title="افزودن دستگاه به قرارداد"
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeviceModalOpen(false)} disabled={saving}>
              انصراف
            </Button>
            <Button type="submit" form="add-device-form" disabled={saving}>
              {saving ? 'در حال ذخیره...' : 'افزودن'}
            </Button>
          </>
        }
      >
        <form id="add-device-form" onSubmit={handleAddDevice} className="space-y-4">
          {actionError && (
            <div className="bg-danger/10 border border-danger/30 rounded-field p-3">
              <p className="text-xs text-danger whitespace-pre-line">{actionError}</p>
            </div>
          )}

          <Select
            label="دستگاه"
            placeholder="انتخاب کنید..."
            value={deviceForm.device}
            onChange={(e) => setDeviceForm({ ...deviceForm, device: e.target.value })}
            options={warehouseOptions}
            required
          />

          {(!warehouseDevices || warehouseDevices.length === 0) && (
            <div className="bg-warning/10 border border-warning/30 rounded-field p-3">
              <p className="text-xs text-warning">
                هیچ دستگاهی در انبار موجود نیست. ابتدا از بخش «دستگاه‌ها» دستگاه جدید اضافه کنید.
              </p>
            </div>
          )}

          <JalaliDatePicker
            label="تاریخ شروع"
            value={deviceForm.start_date}
            onChange={(val) => setDeviceForm({ ...deviceForm, start_date: val })}
            required
          />
          <JalaliDatePicker
            label="تاریخ پایان"
            value={deviceForm.end_date}
            onChange={(val) => setDeviceForm({ ...deviceForm, end_date: val })}
            required
          />
        </form>
      </Modal>

      {/* ═══ مودال افزودن پرداخت ═══ */}
      <Modal
        open={paymentModalOpen}
        onClose={() => setPaymentModalOpen(false)}
        title="افزودن پرداخت"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPaymentModalOpen(false)} disabled={saving}>
              انصراف
            </Button>
            <Button type="submit" form="add-payment-form" disabled={saving}>
              {saving ? 'در حال ذخیره...' : 'افزودن'}
            </Button>
          </>
        }
      >
        <form id="add-payment-form" onSubmit={handleAddPayment} className="space-y-4">
          {actionError && (
            <div className="bg-danger/10 border border-danger/30 rounded-field p-3">
              <p className="text-xs text-danger whitespace-pre-line">{actionError}</p>
            </div>
          )}

          <Input
            type="number"
            label="مبلغ (ریال)"
            value={paymentForm.amount}
            onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
            placeholder="مثلاً 50000000"
            required
          />
          <JalaliDatePicker
            label="تاریخ پرداخت"
            value={paymentForm.payment_date}
            onChange={(val) => setPaymentForm({ ...paymentForm, payment_date: val })}
            required
          />
          <Input
            type="number"
            label="تعداد دستگاه"
            value={paymentForm.device_count}
            onChange={(e) => setPaymentForm({ ...paymentForm, device_count: e.target.value })}
          />
          <Input
            label="توضیحات"
            value={paymentForm.description}
            onChange={(e) => setPaymentForm({ ...paymentForm, description: e.target.value })}
            placeholder="مثلاً پرداخت برای ۲ دستگاه"
          />
        </form>
      </Modal>

      {/* ═══ مودال لغو قرارداد ═══ */}
      <Modal
        open={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        title="لغو قرارداد"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCancelModalOpen(false)} disabled={saving}>
              انصراف
            </Button>
            <Button
              variant="danger"
              onClick={handleCancel}
              disabled={saving}
              icon={XCircle}
            >
              {saving ? 'در حال لغو...' : 'لغو قرارداد'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="bg-warning/10 border border-warning/30 rounded-field p-4 flex items-start gap-3">
            <AlertTriangle size={20} className="text-warning flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-semibold text-warning mb-1">
                هشدار
              </h4>
              <p className="text-xs text-text-secondary leading-relaxed">
                با لغو قرارداد:
              </p>
              <ul className="text-xs text-text-secondary leading-relaxed mt-2 space-y-1 list-disc list-inside">
                <li>تمام دستگاه‌های این قرارداد به انبار برگردانده می‌شوند</li>
                <li>وضعیت قرارداد به «لغو‌شده» تغییر می‌کند</li>
                <li>سوابق قرارداد برای تاریخچه حفظ می‌شود</li>
                <li>این عملیات قابل بازگشت است (می‌توانید مجدداً فعال کنید)</li>
              </ul>
            </div>
          </div>

          <p className="text-sm text-text-secondary">
            آیا از لغو قرارداد
            <span className="font-mono font-bold text-text-primary mx-1">
              {subscription.contract_number}
            </span>
            اطمینان دارید؟
          </p>
        </div>
      </Modal>

    </div>
  );
}

const changeFieldLabels = {
  name: 'نام سازمان',
  code: 'کد سازمان',
  registration_number: 'شماره ثبت',
  economy_code: 'کد اقتصادی',
  phone: 'تلفن',
  email: 'ایمیل',
  address: 'آدرس',
  website: 'وب‌سایت',
  first_name: 'نام',
  last_name: 'نام خانوادگی',
  mobile: 'موبایل',
  national_id: 'کد ملی',
  start_date: 'تاریخ شروع قرارداد',
  end_date: 'تاریخ پایان قرارداد',
  notes: 'یادداشت قرارداد',
  status: 'وضعیت قرارداد',
};

const entityLabels = {
  Organization: 'اطلاعات سازمان',
  User: 'اطلاعات مشتری',
  Subscription: 'اطلاعات قرارداد',
  SubscriptionPayment: 'اطلاعات پرداخت',
  SubscriptionDevice: 'دستگاه قرارداد',
};

function formatChangeValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

function getChangeDisplay(change) {
  const entityLabel = entityLabels[change.entity_type] || change.entity_type || 'اطلاعات';
  const fieldLabel = changeFieldLabels[change.field_name] || change.field_name || 'تغییر';
  return {
    label: fieldLabel,
    oldValue: formatChangeValue(change.old_value),
    newValue: formatChangeValue(change.new_value),
    entityLabel,
  };
}

function DetailItem({ icon: Icon, label, value, color, mono }) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-field bg-bg-base flex items-center justify-center flex-shrink-0">
        <Icon size={16} className="text-text-muted" />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] text-text-muted mb-0.5">{label}</div>
        <div className={`text-sm ${color || 'text-text-primary'} ${mono ? 'font-mono' : ''} truncate`}>
          {value || '—'}
        </div>
      </div>
    </div>
  );
}