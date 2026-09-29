import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2, User as UserIcon, FileText, Package, CreditCard, CheckCircle2,
  ArrowLeft, ArrowRight, Check, AlertCircle, Hash, Phone, Plus, Trash2,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import Input from '../components/Input';
import Badge from '../components/Badge';
import LoadingSpinner from '../components/LoadingSpinner';
import AddDeviceModal from '../components/AddDeviceModal';
import { useApi } from '../hooks/useApi';
import { devicesAPI } from '../api/services/fleet';
import { subscriptionsAPI } from '../api/services/subscriptions';
import JalaliDatePicker from '../components/JalaliDatePicker';
import { toJalali } from '../utils/dateUtils';
import UserComboBox from '../components/UserComboBox';


const STEPS = [
  { id: 1, title: 'نوع مشتری',      icon: UserIcon },
  { id: 2, title: 'اطلاعات مشتری',  icon: Building2 },
  { id: 3, title: 'اطلاعات قرارداد', icon: FileText },
  { id: 4, title: 'دستگاه‌ها',       icon: Package },
  { id: 5, title: 'پرداخت',         icon: CreditCard },
  { id: 6, title: 'خلاصه',          icon: CheckCircle2 },
];

export default function SubscriptionWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loadingNumber, setLoadingNumber] = useState(false);

  const [form, setForm] = useState({
    customer_type: 'organization',
    organization_name: '',
    organization_code: '',
    registration_number: '',
    economy_code: '',
    organization_phone: '',
    organization_email: '',
    organization_address: '',
    username: '',
    password: '',
    first_name: '',
    last_name: '',
    mobile: '',
    national_id: '',
    address: '',
    contract_number: '',
    existing_user_id: null,
    start_date: '',
    end_date: '',
    notes: '',
    devices: [],
    payments: [],
  });

  // تولید شماره قرارداد خودکار از Backend
  useEffect(() => {
    const fetchNextNumber = async () => {
      setLoadingNumber(true);
      try {
        const data = await subscriptionsAPI.getNextNumber(form.customer_type);
        setForm((f) => ({ ...f, contract_number: data.contract_number }));
      } catch (err) {
        console.error('Error fetching contract number:', err);
        const prefix = form.customer_type === 'organization' ? 'ORG' : 'PRS';
        setForm((f) => ({ ...f, contract_number: `${prefix}-TEMP-0001` }));
      } finally {
        setLoadingNumber(false);
      }
    };

    fetchNextNumber();
  }, [form.customer_type]); // eslint-disable-line
  const updateForm = (key, value) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const validateStep = () => {
    setError('');

    if (step === 1) {
      if (!form.customer_type) {
        setError('نوع مشتری را انتخاب کنید');
        return false;
      }
    }

    if (step === 2) {
      if (form.customer_type === 'organization') {
        if (!form.organization_name) {
          setError('نام سازمان الزامی است');
          return false;
        }
      }
      if (!form.username) {
        setError('نام کاربری الزامی است');
        return false;
      }
      if (!form.existing_user_id && (!form.password || form.password.length < 8)) {
        setError('رمز عبور باید حداقل ۸ کاراکتر باشد');
        return false;
      }
      if (!form.first_name || !form.last_name) {
        setError('نام و نام خانوادگی الزامی است');
        return false;
      }
      if (!form.mobile) {
        setError('موبایل الزامی است');
        return false;
      }
    }

    if (step === 3) {
      if (!form.contract_number) {
        setError('شماره قرارداد الزامی است');
        return false;
      }
      if (!form.start_date) {
        setError('تاریخ شروع الزامی است');
        return false;
      }
      if (!form.end_date) {
        setError('تاریخ پایان الزامی است');
        return false;
      }
      if (form.start_date > form.end_date) {
        setError('تاریخ پایان باید بعد از تاریخ شروع باشد');
        return false;
      }
    }

    if (step === 4) {
      if (form.devices.length === 0) {
        setError('حداقل یک دستگاه انتخاب کنید');
        return false;
      }
    }

    return true;
  };

  const nextStep = () => {
    if (validateStep()) {
      setStep((s) => Math.min(s + 1, 6));
    }
  };

  const prevStep = () => {
    setError('');
    setStep((s) => Math.max(s - 1, 1));
  };

  const handleSubmit = async () => {
    setSaving(true);
    setError('');

    try {
      const payload = {
        customer_type: form.customer_type,
        ...(form.customer_type === 'organization' ? {
          organization_name: form.organization_name,
          organization_code: form.organization_code,
          registration_number: form.registration_number,
          economy_code: form.economy_code,
          organization_phone: form.organization_phone,
          organization_email: form.organization_email,
          organization_address: form.organization_address,
        } : {}),
        username: form.username,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
        mobile: form.mobile,
        national_id: form.national_id,
        address: form.address,
        existing_user_id: form.existing_user_id || null,
        contract_number: form.contract_number,
        start_date: form.start_date,
        end_date: form.end_date,
        notes: form.notes,
        devices: form.devices,
        payments: form.payments,
      };

      const result = await subscriptionsAPI.create(payload);
      navigate(`/panel/subscriptions/${result.id}`);
    } catch (err) {
      console.error('Error creating subscription:', err);
      const errData = err.response?.data;
      if (errData) {
        const messages = Object.entries(errData)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`)
          .join('\n');
        setError(messages);
      } else {
        setError('خطا در ساخت قرارداد. لطفاً دوباره تلاش کنید.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">

      <PageHeader
        title="افزودن قرارداد جدید"
        subtitle="اطلاعات را در ۶ مرحله وارد کنید"
        actions={
          <Button variant="secondary" onClick={() => navigate('/panel/subscriptions')}>
            انصراف
          </Button>
        }
      />

      <Card>
        <div className="flex items-center justify-between gap-2">
          {STEPS.map((s, idx) => {
            const Icon = s.icon;
            const isActive = step === s.id;
            const isDone = step > s.id;
            return (
              <div key={s.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center gap-2 flex-1">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-all
                      ${isDone ? 'bg-success text-bg-base' : ''}
                      ${isActive ? 'bg-brand-500 text-bg-base' : ''}
                      ${!isActive && !isDone ? 'bg-bg-base border border-border-base text-text-muted' : ''}
                    `}
                  >
                    {isDone ? <Check size={18} /> : <Icon size={18} />}
                  </div>
                  <span className={`text-[10px] text-center ${isActive ? 'text-text-primary font-medium' : 'text-text-muted'}`}>
                    {s.title}
                  </span>
                </div>
                {idx < STEPS.length - 1 && (
                  <div className={`h-px flex-1 mx-2 mb-5 ${step > s.id ? 'bg-success' : 'bg-border-base'}`} />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {error && (
        <div className="bg-danger/10 border border-danger/30 rounded-field p-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-danger flex-shrink-0 mt-0.5" />
          <p className="text-sm text-danger whitespace-pre-line">{error}</p>
        </div>
      )}

      <Card>
        {step === 1 && <Step1 form={form} updateForm={updateForm} />}
        {step === 2 && <Step2 form={form} updateForm={updateForm} setForm={setForm} />}
        {step === 3 && <Step3 form={form} updateForm={updateForm} />}
        {step === 4 && <Step4 form={form} updateForm={updateForm} />}
        {step === 5 && <Step5 form={form} updateForm={updateForm} />}
        {step === 6 && <Step6 form={form} />}
      </Card>

      <div className="flex items-center justify-between">
        <Button
          variant="secondary"
          onClick={prevStep}
          disabled={step === 1}
          icon={ArrowRight}
        >
          مرحله قبل
        </Button>

        {step < 6 ? (
          <Button onClick={nextStep} icon={ArrowLeft}>
            مرحله بعد
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={saving}
            icon={Check}
          >
            {saving ? 'در حال ثبت...' : 'ثبت قرارداد'}
          </Button>
        )}
      </div>

    </div>
  );
}

/* ═══════════════════════════════════════════════
   مرحله ۱ — نوع مشتری
   ═══════════════════════════════════════════════ */

function Step1({ form, updateForm }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-text-primary mb-1">نوع مشتری</h3>
        <p className="text-sm text-text-muted">مشخص کنید قرارداد برای شخص حقیقی است یا شرکت/سازمان</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={() => updateForm('customer_type', 'organization')}
          className={`p-6 rounded-card border-2 text-right transition-all
            ${form.customer_type === 'organization'
              ? 'border-brand-500 bg-brand-500/5'
              : 'border-border-base hover:border-border-strong'
            }`}
        >
          <div className="flex items-start gap-4">
            <div className={`w-12 h-12 rounded-field flex items-center justify-center flex-shrink-0
              ${form.customer_type === 'organization' ? 'bg-brand-500/20' : 'bg-bg-hover'}`}>
              <Building2 size={24} className={form.customer_type === 'organization' ? 'text-brand-400' : 'text-text-muted'} />
            </div>
            <div className="flex-1">
              <h4 className="text-base font-semibold text-text-primary mb-1">سازمانی</h4>
              <p className="text-xs text-text-muted leading-relaxed">
                شرکت، سازمان یا مجموعه‌ای که می‌تواند شعبه، کاربر و ناوگان داشته باشد
              </p>
            </div>
          </div>
        </button>

        <button
          type="button"
          onClick={() => updateForm('customer_type', 'personal')}
          className={`p-6 rounded-card border-2 text-right transition-all
            ${form.customer_type === 'personal'
              ? 'border-info bg-info/5'
              : 'border-border-base hover:border-border-strong'
            }`}
        >
          <div className="flex items-start gap-4">
            <div className={`w-12 h-12 rounded-field flex items-center justify-center flex-shrink-0
              ${form.customer_type === 'personal' ? 'bg-info/20' : 'bg-bg-hover'}`}>
              <UserIcon size={24} className={form.customer_type === 'personal' ? 'text-info' : 'text-text-muted'} />
            </div>
            <div className="flex-1">
              <h4 className="text-base font-semibold text-text-primary mb-1">شخصی</h4>
              <p className="text-xs text-text-muted leading-relaxed">
                شخص حقیقی که خودروی شخصی دارد و به مدیریت شعبه یا کاربر نیازی ندارد
              </p>
            </div>
          </div>
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   مرحله ۲ — اطلاعات مشتری
   ═══════════════════════════════════════════════ */

function Step2({ form, updateForm, setForm }) {
  const isOrg = form.customer_type === 'organization';

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-text-primary mb-1">
          {isOrg ? 'اطلاعات سازمان و کاربر مدیر' : 'اطلاعات مشتری'}
        </h3>
        <p className="text-sm text-text-muted">
          {isOrg
            ? 'اطلاعات شرکت و کاربر اصلی (مدیر شرکت) را وارد کنید'
            : 'اطلاعات شخصی و اطلاعات ورود را وارد کنید'}
        </p>
      </div>

      {isOrg && (
        <div className="space-y-4">
          <h4 className="text-xs font-medium text-text-muted">اطلاعات سازمان</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="نام سازمان"
              value={form.organization_name}
              onChange={(e) => updateForm('organization_name', e.target.value)}
              placeholder="نام کامل شرکت"
              required
            />
            <Input
              label="شماره ثبت"
              value={form.registration_number}
              onChange={(e) => updateForm('registration_number', e.target.value)}
            />
            <Input
              label="کد اقتصادی"
              value={form.economy_code}
              onChange={(e) => updateForm('economy_code', e.target.value)}
            />
            <Input
              label="تلفن سازمان"
              icon={Phone}
              value={form.organization_phone}
              onChange={(e) => updateForm('organization_phone', e.target.value)}
            />
            <Input
              label="ایمیل سازمان"
              value={form.organization_email}
              onChange={(e) => updateForm('organization_email', e.target.value)}
            />
          </div>
          <Input
            label="آدرس سازمان"
            value={form.organization_address}
            onChange={(e) => updateForm('organization_address', e.target.value)}
          />
        </div>
      )}

      <div className="space-y-4 pt-4 border-t border-border-base">
        <h4 className="text-xs font-medium text-text-muted">
          {isOrg ? 'اطلاعات کاربر مدیر شرکت' : 'اطلاعات کاربری و اطلاعات ورود'}
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <UserComboBox
            label="نام کاربری"
            value={form.username}
            onChange={(val) => updateForm('username', val)}
            selectedUserId={form.existing_user_id}
            accountType={form.customer_type}
            onSelectUser={(user) => {
              setForm((f) => {
                const updates = {
                  ...f,
                  existing_user_id: user.id,
                  username: user.username,
                  first_name: user.first_name || '',
                  last_name: user.last_name || '',
                  mobile: user.mobile || '',
                  national_id: user.national_id || '',
                  address: user.address || '',
                };

                // اگه کاربر سازمانی بود، اطلاعات سازمان رو هم پر کن
                if (user.account_type === 'organization' && user.organization_data) {
                  const org = user.organization_data;
                  updates.organization_name = org.name || '';
                  updates.organization_code = org.code || '';
                  updates.registration_number = org.registration_number || '';
                  updates.economy_code = org.economy_code || '';
                  updates.organization_phone = org.phone || '';
                  updates.organization_email = org.email || '';
                  updates.organization_address = org.address || '';
                }

                return updates;
              });
            }}
            onClearUser={() => {
              setForm((f) => ({
                ...f,
                existing_user_id: null,
                // پاک کردن اطلاعات کاربر
                first_name: '',
                last_name: '',
                mobile: '',
                national_id: '',
                address: '',
                // پاک کردن اطلاعات سازمان
                organization_name: '',
                organization_code: '',
                registration_number: '',
                economy_code: '',
                organization_phone: '',
                organization_email: '',
                organization_address: '',
              }));
            }}
            required
          />

          {/* رمز عبور — فقط برای کاربر جدید */}
          {!form.existing_user_id && (
            <Input
              type="password"
              label="رمز عبور"
              value={form.password}
              onChange={(e) => updateForm('password', e.target.value)}
              placeholder="حداقل ۸ کاراکتر"
              required
            />
          )}

          {form.existing_user_id && (
            <div className="bg-info/10 border border-info/30 rounded-field p-3 flex items-start gap-2">
              <Check size={16} className="text-info flex-shrink-0 mt-0.5" />
              <p className="text-xs text-text-secondary leading-relaxed">
                کاربر موجود انتخاب شده — رمز عبور فعلی حفظ می‌شود. می‌توانید اطلاعات زیر را ویرایش کنید.
              </p>
            </div>
          )}

          <Input
            label="نام"
            value={form.first_name}
            onChange={(e) => updateForm('first_name', e.target.value)}
            required
          />
          <Input
            label="نام خانوادگی"
            value={form.last_name}
            onChange={(e) => updateForm('last_name', e.target.value)}
            required
          />
          <Input
            label="موبایل"
            icon={Phone}
            value={form.mobile}
            onChange={(e) => updateForm('mobile', e.target.value)}
            placeholder="۰۹xxxxxxxxx"
            required
          />
          <Input
            label="کد ملی"
            value={form.national_id}
            onChange={(e) => updateForm('national_id', e.target.value)}
            placeholder="۱۰ رقم"
          />

          {/* آدرس مشتری شخصی */}
          {!isOrg && (
          <Input
            label="آدرس"
            value={form.address}
            onChange={(e) => updateForm('address', e.target.value)}
            placeholder="آدرس محل سکونت"
          />
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   مرحله ۳ — اطلاعات قرارداد
   ═══════════════════════════════════════════════ */

function Step3({ form, updateForm }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-text-primary mb-1">اطلاعات قرارداد</h3>
        <p className="text-sm text-text-muted">شماره قرارداد و بازه‌ی زمانی آن را مشخص کنید</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Input
          label="شماره قرارداد"
          value={form.contract_number}
          onChange={(e) => updateForm('contract_number', e.target.value)}
          placeholder="در حال بارگذاری..."
          required
        />
        <JalaliDatePicker
          label="تاریخ شروع"
          value={form.start_date}
          onChange={(val) => updateForm('start_date', val)}
          required
        />
        <JalaliDatePicker
          label="تاریخ پایان"
          value={form.end_date}
          onChange={(val) => updateForm('end_date', val)}
          required
        />
      </div>

      <div>
        <label className="block text-sm text-text-secondary mb-2">یادداشت</label>
        <textarea
          value={form.notes}
          onChange={(e) => updateForm('notes', e.target.value)}
          rows={3}
          className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-brand-500"
          placeholder="یادداشت اختیاری..."
        />
      </div>

      <div className="bg-info/10 border border-info/30 rounded-field p-3">
        <p className="text-xs text-text-secondary leading-relaxed">
          <span className="font-medium text-info">نکته:</span> تاریخ شروع و پایان قرارداد، پیش‌فرض دستگاه‌های این قرارداد هم است. در مرحله‌ی بعد می‌توانید برای هر دستگاه تاریخ جدا تنظیم کنید.
        </p>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   مرحله ۴ — انتخاب دستگاه‌ها
   ═══════════════════════════════════════════════ */

function Step4({ form, updateForm }) {
  const [search, setSearch] = useState('');
  const [addModalOpen, setAddModalOpen] = useState(false);

  const fetchDevices = useCallback(async () => {
    const result = await devicesAPI.list({ in_warehouse: 'true' });
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const { data: devices, loading, error, refetch } = useApi(fetchDevices, []);

  const filtered = (devices || []).filter((d) => {
    if (!search) return true;
    return d.imei.includes(search) || (d.sim_number && d.sim_number.includes(search));
  });

  const toggleDevice = (device) => {
    const isSelected = form.devices.some((d) => d.device_id === device.id);
    if (isSelected) {
      updateForm('devices', form.devices.filter((d) => d.device_id !== device.id));
    } else {
      updateForm('devices', [
        ...form.devices,
        {
          device_id: device.id,
          device_imei: device.imei,
          device_model: device.device_model_name || '',
          start_date: form.start_date,
          end_date: form.end_date,
        },
      ]);
    }
  };

  const updateDeviceDates = (deviceId, key, value) => {
    updateForm('devices', form.devices.map((d) =>
      d.device_id === deviceId ? { ...d, [key]: value } : d
    ));
  };

  // وقتی دستگاه جدید اضافه شد
  const handleDeviceAdded = (newDevice) => {
    refetch();

    // خودکار انتخابش کن
    updateForm('devices', [
      ...form.devices,
      {
        device_id: newDevice.id,
        device_imei: newDevice.imei,
        device_model: newDevice.device_model_name || '',
        start_date: form.start_date,
        end_date: form.end_date,
      },
    ]);
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-danger text-sm">خطا در دریافت دستگاه‌ها</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary mb-1">انتخاب دستگاه‌ها</h3>
          <p className="text-sm text-text-muted">
            از دستگاه‌های موجود در انبار انتخاب کنید. برای هر دستگاه می‌توانید تاریخ جدا تنظیم کنید.
          </p>
        </div>
        <Button
          type="button"
          icon={Plus}
          onClick={() => setAddModalOpen(true)}
        >
          افزودن دستگاه جدید
        </Button>
      </div>

      {(!devices || devices.length === 0) ? (
        <div className="py-12 text-center bg-bg-base border border-border-base rounded-card">
          <Package size={40} className="text-text-muted mx-auto mb-3" />
          <p className="text-sm text-text-muted mb-2">هیچ دستگاهی در انبار موجود نیست</p>
          <p className="text-xs text-text-muted mb-4">می‌توانید همین حالا دستگاه جدید اضافه کنید</p>
          <Button
            type="button"
            icon={Plus}
            onClick={() => setAddModalOpen(true)}
          >
            افزودن دستگاه جدید
          </Button>
        </div>
      ) : (
        <>
          <Input
            icon={Hash}
            placeholder="جستجوی IMEI یا شماره SIM..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <div className="bg-brand-500/10 border border-brand-500/30 rounded-field p-3 flex items-center justify-between">
            <span className="text-xs text-text-secondary">
              انتخاب‌شده: <span className="font-mono font-bold text-brand-400">{form.devices.length}</span> دستگاه
            </span>
            <button
              type="button"
              onClick={() => setAddModalOpen(true)}
              className="text-xs text-brand-400 hover:text-brand-500 transition-colors flex items-center gap-1"
            >
              <Plus size={14} />
              افزودن دستگاه
            </button>
          </div>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {filtered.map((device) => {
              const isSelected = form.devices.some((d) => d.device_id === device.id);
              const selectedData = form.devices.find((d) => d.device_id === device.id);

              return (
                <div
                  key={device.id}
                  className={`rounded-card border transition-all
                    ${isSelected ? 'border-brand-500 bg-brand-500/5' : 'border-border-base'}`}
                >
                  <button
                    type="button"
                    onClick={() => toggleDevice(device)}
                    className="w-full p-3 text-right flex items-center gap-3"
                  >
                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0
                      ${isSelected ? 'bg-brand-500 border-brand-500' : 'border-border-base'}`}>
                      {isSelected && <Check size={12} className="text-bg-base" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-text-primary">{device.imei}</span>
                        {device.device_model_name && (
                          <Badge variant="brand">{device.device_model_name}</Badge>
                        )}
                      </div>
                      {device.sim_number && (
                        <div className="text-[10px] text-text-muted font-mono mt-1">
                          SIM: {device.sim_number}
                        </div>
                      )}
                    </div>
                  </button>

                  {isSelected && selectedData && (
                    <div className="px-3 pb-3 pt-1 grid grid-cols-1 md:grid-cols-2 gap-3 border-t border-border-base mt-2">
                      <JalaliDatePicker
                        label="تاریخ شروع دستگاه"
                        value={selectedData.start_date}
                        minDate={form.start_date}
                        maxDate={form.end_date}
                        onChange={(val) => updateDeviceDates(device.id, 'start_date', val)}
                      />
                      <JalaliDatePicker
                        label="تاریخ پایان دستگاه"
                        value={selectedData.end_date}
                        minDate={form.start_date}
                        maxDate={form.end_date}
                        onChange={(val) => updateDeviceDates(device.id, 'end_date', val)}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      <AddDeviceModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onSuccess={handleDeviceAdded}
      />
    </div>
  );
}

/* ═══════════════════════════════════════════════
   مرحله ۵ — پرداخت اولیه
   ═══════════════════════════════════════════════ */

function formatAmountInput(value) {
  const digits = String(value ?? '').replace(/[^0-9]/g, '');
  return digits ? digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '';
}

function parseAmountInput(value) {
  const digits = String(value ?? '').replace(/[^0-9]/g, '');
  return digits ? Number(digits) : 0;
}

function Step5({ form, updateForm }) {
  const [payment, setPayment] = useState({
    amount: '',
    payment_date: new Date().toISOString().split('T')[0],
    device_count: form.devices.length,
    description: 'پرداخت اولیه',
  });

  const addPayment = () => {
    if (!payment.amount) return;
    updateForm('payments', [...form.payments, { ...payment, amount: parseAmountInput(payment.amount) }]);
    setPayment({
      amount: '',
      payment_date: new Date().toISOString().split('T')[0],
      device_count: form.devices.length,
      description: '',
    });
  };

  const removePayment = (idx) => {
    updateForm('payments', form.payments.filter((_, i) => i !== idx));
  };

  const totalAmount = form.payments.reduce((sum, p) => sum + Number(p.amount), 0);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-text-primary mb-1">پرداخت اولیه</h3>
        <p className="text-sm text-text-muted">
          پرداخت‌های مشتری را ثبت کنید. می‌توانید بعداً از صفحه‌ی قرارداد، پرداخت‌های بیشتر اضافه کنید.
        </p>
      </div>

      <div className="bg-bg-base border border-border-base rounded-card p-4 space-y-3">
        <h4 className="text-xs font-medium text-text-muted">افزودن پرداخت</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Input
            inputMode="numeric"
            label="مبلغ (ریال)"
            value={payment.amount}
            onChange={(e) => setPayment({ ...payment, amount: formatAmountInput(e.target.value) })}
            placeholder="مثلاً 50,000,000"
          />
          <JalaliDatePicker
            label="تاریخ پرداخت"
            value={payment.payment_date}
            onChange={(val) => setPayment({ ...payment, payment_date: val })}
          />
          <Input
            type="number"
            label="تعداد دستگاه"
            value={payment.device_count}
            onChange={(e) => setPayment({ ...payment, device_count: Number(e.target.value) })}
          />
        </div>
        <Input
          label="توضیحات"
          value={payment.description}
          onChange={(e) => setPayment({ ...payment, description: e.target.value })}
          placeholder="مثلاً پرداخت اولیه بابت ۲ دستگاه"
        />
        <div className="flex justify-end">
          <Button type="button" onClick={addPayment} icon={Plus} size="sm">
            افزودن پرداخت
          </Button>
        </div>
      </div>

      {form.payments.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-text-muted">پرداخت‌های ثبت‌شده</h4>
          {form.payments.map((p, idx) => (
            <div key={idx} className="flex items-center justify-between p-3 bg-bg-base border border-border-base rounded-field">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm text-text-primary">
                    {Number(p.amount).toLocaleString('fa-IR')} ریال
                  </span>
                  <span className="text-xs text-text-muted">{p.device_count} دستگاه</span>
                  <span className="text-xs text-text-muted font-mono">{toJalali(p.payment_date)}</span>
                </div>
                {p.description && (
                  <div className="text-[10px] text-text-muted mt-1">{p.description}</div>
                )}
              </div>
              <button
                type="button"
                onClick={() => removePayment(idx)}
                className="p-1.5 rounded-field text-text-muted hover:bg-danger/10 hover:text-danger transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}

          <div className="flex items-center justify-between p-3 bg-brand-500/10 border border-brand-500/30 rounded-field">
            <span className="text-sm text-text-secondary">مجموع پرداخت‌ها</span>
            <span className="font-mono text-base font-bold text-brand-400">
              {totalAmount.toLocaleString('fa-IR')} ریال
            </span>
          </div>
        </div>
      )}

      <div className="bg-info/10 border border-info/30 rounded-field p-3">
        <p className="text-xs text-text-secondary leading-relaxed">
          <span className="font-medium text-info">اختیاری:</span> اگه الان پرداختی ثبت نکنید، می‌تونید بعداً از صفحه‌ی قرارداد اضافه کنید.
        </p>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   مرحله ۶ — خلاصه
   ═══════════════════════════════════════════════ */

function Step6({ form }) {
  const totalAmount = form.payments.reduce((sum, p) => sum + Number(p.amount), 0);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-text-primary mb-1">خلاصه و تأیید</h3>
        <p className="text-sm text-text-muted">اطلاعات را مرور کنید و در صورت صحت، ثبت کنید</p>
      </div>

      <div className="space-y-3">
        <h4 className="text-xs font-medium text-text-muted">نوع مشتری</h4>
        <Badge variant={form.customer_type === 'organization' ? 'brand' : 'info'}>
          {form.customer_type === 'organization' ? 'سازمانی' : 'شخصی'}
        </Badge>
      </div>

      <div className="pt-4 border-t border-border-base space-y-3">
        <h4 className="text-xs font-medium text-text-muted">اطلاعات مشتری</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          {form.customer_type === 'organization' && (
            <>
              <SummaryItem label="نام سازمان" value={form.organization_name} />
              {form.registration_number && <SummaryItem label="شماره ثبت" value={form.registration_number} mono />}
              {form.economy_code && <SummaryItem label="کد اقتصادی" value={form.economy_code} mono />}
              {form.organization_phone && <SummaryItem label="تلفن سازمان" value={form.organization_phone} mono />}
            </>
          )}
          <SummaryItem label="نام کاربری" value={form.username} mono />
          <SummaryItem label="نام و نام خانوادگی" value={`${form.first_name} ${form.last_name}`} />
          <SummaryItem label="موبایل" value={form.mobile} mono />
          {form.national_id && <SummaryItem label="کد ملی" value={form.national_id} mono />}
          {form.customer_type === 'personal' && form.address && (
            <div className="md:col-span-2">
              <SummaryItem label="آدرس" value={form.address} />
            </div>
          )}
        </div>
      </div>

      <div className="pt-4 border-t border-border-base space-y-3">
        <h4 className="text-xs font-medium text-text-muted">اطلاعات قرارداد</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <SummaryItem label="شماره قرارداد" value={form.contract_number} mono />
          <SummaryItem label="تاریخ شروع" value={toJalali(form.start_date)} mono />
          <SummaryItem label="تاریخ پایان" value={toJalali(form.end_date)} mono />
        </div>
        {form.notes && (
          <div>
            <div className="text-[10px] text-text-muted mb-1">یادداشت</div>
            <p className="text-xs text-text-secondary">{form.notes}</p>
          </div>
        )}
      </div>

      <div className="pt-4 border-t border-border-base space-y-3">
        <h4 className="text-xs font-medium text-text-muted">
          دستگاه‌ها ({form.devices.length})
        </h4>
        <div className="space-y-2">
          {form.devices.map((d) => (
            <div key={d.device_id} className="flex items-center justify-between p-2 bg-bg-base border border-border-base rounded-field text-xs">
              <div className="flex items-center gap-2">
                <span className="font-mono text-text-primary">{d.device_imei || `#${d.device_id}`}</span>
                {d.device_model && (
                  <span className="text-text-muted">({d.device_model})</span>
                )}
              </div>
              <span className="text-text-muted font-mono">
                {toJalali(d.start_date)} → {toJalali(d.end_date)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {form.payments.length > 0 && (
        <div className="pt-4 border-t border-border-base space-y-3">
          <h4 className="text-xs font-medium text-text-muted">
            پرداخت‌ها ({form.payments.length})
          </h4>
          <div className="space-y-2">
            {form.payments.map((p, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-bg-base border border-border-base rounded-field text-xs">
                <span className="font-mono text-text-primary">
                  {Number(p.amount).toLocaleString('fa-IR')} ریال
                </span>
                <span className="text-text-muted font-mono">{toJalali(p.payment_date)}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between p-3 bg-brand-500/10 border border-brand-500/30 rounded-field">
            <span className="text-sm text-text-secondary">مجموع</span>
            <span className="font-mono text-base font-bold text-brand-400">
              {totalAmount.toLocaleString('fa-IR')} ریال
            </span>
          </div>
        </div>
      )}

      <div className="bg-success/10 border border-success/30 rounded-field p-3 flex items-start gap-2">
        <CheckCircle2 size={16} className="text-success flex-shrink-0 mt-0.5" />
        <p className="text-xs text-text-secondary leading-relaxed">
          با کلیک روی <span className="font-medium text-success">«ثبت قرارداد»</span>، کاربر به صورت خودکار ساخته می‌شود و می‌تواند با اطلاعات وارد شده لاگین کند.
        </p>
      </div>
    </div>
  );
}

function SummaryItem({ label, value, mono }) {
  return (
    <div>
      <div className="text-[10px] text-text-muted mb-0.5">{label}</div>
      <div className={`text-sm text-text-primary ${mono ? 'font-mono' : ''}`}>{value || '—'}</div>
    </div>
  );
}