import { useEffect, useRef, useState } from 'react';
import {
  Plus, Pencil, Trash2, Camera, Mail, Phone,
  Shield, Smartphone, Building2, MapPin, Globe,
  UserX, Globe as GlobeIcon, Database, Server, Copy,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Modal from '../components/Modal';
import ActionMenu from '../components/ActionMenu';
import SettingsNav from '../components/SettingsNav';
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../api/services/auth';
import apiClient from '../api/client';
import { MAP_PROVIDERS } from '../../../sana-map/src/config';
import {
  organization,
  branchesList,
  usersList,
  roleMap,
  userStatusMap,
  notificationSettings,
} from '../data/settingsData';

export default function Settings() {
  const [section, setSection] = useState('profile');
  const { isSiteAdmin, isMainUser } = useAuth();

  return (
    <div className="space-y-6">

      <PageHeader
        title="تنظیمات"
        subtitle={
          isSiteAdmin
            ? 'مدیریت پروفایل، سازمان‌ها و تنظیمات سامانه'
            : isMainUser
              ? 'مدیریت پروفایل، سازمان و کاربران'
              : 'مدیریت پروفایل و اعلان‌ها'
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">

        <SettingsNav active={section} onChange={setSection} />

        <div>
          {section === 'profile'        && <ProfileSection />}
          {section === 'security'       && <SecuritySection />}
          {section === 'organization'   && <OrganizationSection />}
          {section === 'branches'       && <BranchesSection />}
          {section === 'users'          && <UsersSection />}
          {section === 'notifications'  && <NotificationsSection />}
          {section === 'system'         && <SystemSection />}
        </div>

      </div>

    </div>
  );
}

const mapProfileData = (data) => ({
  firstName: data.first_name || '',
  lastName: data.last_name || '',
  email: data.email || '',
  mobile: data.mobile || '',
});

/* ============ پروفایل ============ */

function ProfileSection() {
  const { user, updateUser } = useAuth();
  const [form, setForm] = useState({
    firstName: user?.first_name || '',
    lastName: user?.last_name || '',
    email: user?.email || '',
    mobile: user?.mobile || '',
  });
  const [savedForm, setSavedForm] = useState(form);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const roleLabels = {
    site_admin: 'ادمین کل سایت',
    main_user: 'مدیر شرکت',
    branch_manager: 'مدیر شعبه',
    personal_user: 'کاربر شخصی',
  };

  useEffect(() => {
    let active = true;

    authAPI.me()
      .then((data) => {
        if (!active) return;
        const profileData = mapProfileData(data);
        setForm(profileData);
        setSavedForm(profileData);
      })
      .catch(() => {
        if (!active) return;
        setError('دریافت اطلاعات پروفایل با خطا مواجه شد.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
    setError('');
    setSuccess('');
  };

  const handleCancel = () => {
    setForm(savedForm);
    setError('');
    setSuccess('');
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const updatedUser = await authAPI.updateProfile({
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        mobile: form.mobile,
      });
      const profileData = mapProfileData(updatedUser);
      setForm(profileData);
      setSavedForm(profileData);
      updateUser(updatedUser);
      setSuccess('اطلاعات پروفایل با موفقیت ذخیره شد.');
    } catch (requestError) {
      const responseData = requestError.response?.data;
      const firstError = responseData && Object.values(responseData).flat()[0];
      setError(firstError || 'ذخیره اطلاعات پروفایل انجام نشد. دوباره تلاش کنید.');
    } finally {
      setSaving(false);
    }
  };

  const initials = form.firstName.trim().charAt(0) || user?.username?.charAt(0) || '?';
  const roleLabel = roleLabels[user?.role] || '—';

  return (
    <Card title="پروفایل من" subtitle="اطلاعات شخصی و تماس">
      <div className="space-y-6">
        <div className="flex items-center gap-5">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-brand-500 flex items-center justify-center text-bg-base text-2xl font-bold">
              {initials}
            </div>
            <div className="absolute bottom-0 left-0 w-7 h-7 rounded-full bg-bg-overlay border border-border-base flex items-center justify-center">
              <Camera size={14} className="text-text-secondary" />
            </div>
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary">
              {form.firstName} {form.lastName}
            </h3>
            <p className="text-xs text-text-muted mt-0.5">{roleLabel}</p>
          </div>
        </div>

        <div className="border-t border-border-base" />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="نام"
            value={form.firstName}
            onChange={(event) => handleChange('firstName', event.target.value)}
            disabled={loading || saving}
          />
          <Input
            label="نام خانوادگی"
            value={form.lastName}
            onChange={(event) => handleChange('lastName', event.target.value)}
            disabled={loading || saving}
          />
          <Input
            label="ایمیل"
            icon={Mail}
            type="email"
            value={form.email}
            onChange={(event) => handleChange('email', event.target.value)}
            disabled={loading || saving}
          />
          <Input
            label="موبایل"
            icon={Phone}
            type="tel"
            value={form.mobile}
            onChange={(event) => handleChange('mobile', event.target.value)}
            disabled={loading || saving}
          />
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}
        {success && <p className="text-sm text-success">{success}</p>}

        <div className="flex items-center justify-end gap-2 pt-4 border-t border-border-base">
          <Button variant="secondary" onClick={handleCancel} disabled={loading || saving}>
            انصراف
          </Button>
          <Button onClick={handleSave} disabled={loading || saving}>
            {saving ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
          </Button>
        </div>
      </div>
    </Card>
  );
}

/* ============ امنیت ============ */

function SecuritySection() {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const resetForm = () => {
    setOldPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setError('');
    setSuccess('');
  };

  const handleChangePassword = async () => {
    setError('');
    setSuccess('');

    if (!oldPassword || !newPassword || !confirmPassword) {
      setError('لطفاً هر سه فیلد رمز عبور را تکمیل کنید.');
      return;
    }
    if (newPassword.length < 8) {
      setError('رمز عبور جدید باید حداقل ۸ کاراکتر باشد.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('تکرار رمز عبور جدید با آن مطابقت ندارد.');
      return;
    }
    if (oldPassword === newPassword) {
      setError('رمز عبور جدید باید با رمز فعلی متفاوت باشد.');
      return;
    }

    setSaving(true);
    try {
      const response = await authAPI.changePassword(oldPassword, newPassword);
      setSuccess(response.detail || 'رمز عبور با موفقیت تغییر کرد.');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (requestError) {
      const data = requestError.response?.data;
      const firstError = data && Object.values(data).flat().find((item) => typeof item === 'string');
      setError(firstError || 'تغییر رمز عبور انجام نشد. لطفاً دوباره تلاش کنید.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">

      <Card title="تغییر رمز عبور" subtitle="برای امنیت بیشتر، رمز قوی انتخاب کنید">
        <div className="space-y-4">
          <Input
            type="password"
            label="رمز فعلی"
            icon={Shield}
            value={oldPassword}
            onChange={(event) => { setOldPassword(event.target.value); setError(''); setSuccess(''); }}
            disabled={saving}
            autoComplete="current-password"
          />
          <Input
            type="password"
            label="رمز جدید"
            icon={Shield}
            value={newPassword}
            onChange={(event) => { setNewPassword(event.target.value); setError(''); setSuccess(''); }}
            disabled={saving}
            autoComplete="new-password"
          />
          <Input
            type="password"
            label="تکرار رمز جدید"
            icon={Shield}
            value={confirmPassword}
            onChange={(event) => { setConfirmPassword(event.target.value); setError(''); setSuccess(''); }}
            disabled={saving}
            autoComplete="new-password"
          />

          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
          {success && <p role="status" className="text-sm text-success">{success}</p>}

          <div className="flex items-center justify-end gap-2 pt-4 border-t border-border-base">
            <Button variant="secondary" onClick={resetForm} disabled={saving}>
              انصراف
            </Button>
            <Button onClick={handleChangePassword} disabled={saving}>
              {saving ? 'در حال تغییر رمز...' : 'تغییر رمز'}
            </Button>
          </div>
        </div>
      </Card>

      <Card title="احراز هویت دو مرحله‌ای" subtitle="لایه امنیتی اضافه برای حساب شما">
        <div className="flex items-start gap-4 p-4 bg-bg-base border border-border-base rounded-field">
          <div className="w-10 h-10 rounded-field bg-bg-hover flex items-center justify-center flex-shrink-0">
            <Smartphone size={18} className="text-text-secondary" />
          </div>
          <div className="flex-1">
            <h4 className="text-sm font-medium text-text-primary mb-1">
              احراز هویت دو مرحله‌ای فعال نیست
            </h4>
            <p className="text-xs text-text-muted mb-3">
              با فعال‌سازی، هنگام ورود یک کد تأیید به موبایل شما ارسال می‌شود.
            </p>
            <Button size="sm" disabled>فعال‌سازی</Button>
          </div>
        </div>
      </Card>

    </div>
  );
}

/* ============ سازمان ============ */

function OrganizationSection() {
  const [form, setForm] = useState(organization);
  const { isSiteAdmin } = useAuth();

  return (
    <Card
      title={isSiteAdmin ? 'اطلاعات سازمان' : 'اطلاعات سازمان شما'}
      subtitle="اطلاعات پایه سازمان"
    >
      <div className="space-y-6">

        <div className="flex items-center gap-5">
          <div className="w-20 h-20 rounded-card bg-bg-base border border-border-base flex items-center justify-center">
            <Building2 size={32} className="text-text-muted" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-text-primary mb-1">لوگوی سازمان</h3>
            <p className="text-xs text-text-muted mb-2">حداکثر حجم ۲ مگابایت — PNG یا SVG</p>
            <Button size="sm" variant="secondary">تغییر لوگو</Button>
          </div>
        </div>

        <div className="border-t border-border-base" />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="نام سازمان" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input label="شماره ثبت" value={form.registrationNumber} onChange={(e) => setForm({ ...form, registrationNumber: e.target.value })} />
          <Input label="کد اقتصادی" value={form.economyCode} onChange={(e) => setForm({ ...form, economyCode: e.target.value })} />
          <Input label="تلفن" icon={Phone} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <Input label="ایمیل" icon={Mail} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <Input label="وبسایت" icon={Globe} value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
        </div>

        <Input label="آدرس" icon={MapPin} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />

        <div className="flex items-center justify-end gap-2 pt-4 border-t border-border-base">
          <Button variant="secondary">انصراف</Button>
          <Button>ذخیره تغییرات</Button>
        </div>

      </div>
    </Card>
  );
}

/* ============ شعبه‌ها ============ */

function BranchesSection() {
  const [modalOpen, setModalOpen] = useState(false);

  const getMenuItems = (branch) => [
    { label: 'ویرایش', icon: Pencil, onClick: () => console.log('Edit branch:', branch.id) },
    { label: 'حذف', icon: Trash2, variant: 'danger', onClick: () => console.log('Delete branch:', branch.id) },
  ];

  return (
    <>
      <Card
        title="شعبه‌ها"
        subtitle={`${branchesList.length} شعبه ثبت شده`}
        action={
          <Button size="sm" icon={Plus} onClick={() => setModalOpen(true)}>
            افزودن شعبه
          </Button>
        }
      >
        <div className="overflow-x-auto -m-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-base">
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نام شعبه</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">کد</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">مدیر</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">تلفن</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">منابع</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                <th className="w-12"></th>
              </tr>
            </thead>
            <tbody>
              {branchesList.map((b) => (
                <tr key={b.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                  <td className="py-3 px-4 font-medium text-text-primary">{b.name}</td>
                  <td className="py-3 px-4 text-text-secondary font-mono text-xs">{b.code}</td>
                  <td className="py-3 px-4 text-text-secondary text-xs">
                    {b.manager || <span className="text-text-muted">تعیین نشده</span>}
                  </td>
                  <td className="py-3 px-4 text-text-secondary font-mono text-xs">{b.phone}</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3 text-[10px] text-text-muted">
                      <span>🚗 {b.vehiclesCount}</span>
                      <span>📡 {b.devicesCount}</span>
                      <span>👤 {b.driversCount}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <Badge variant={b.status === 'active' ? 'success' : 'muted'}>
                      {b.status === 'active' ? 'فعال' : 'غیرفعال'}
                    </Badge>
                  </td>
                  <td className="py-3 px-2">
                    <ActionMenu items={getMenuItems(b)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="افزودن شعبه"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>انصراف</Button>
            <Button>ذخیره</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input label="نام شعبه" placeholder="مثلاً مشهد" />
          <Input label="کد شعبه" placeholder="مثلاً MHD-01" />
          <Input label="تلفن" icon={Phone} placeholder="۰۵۱-xxxxxxxx" />
          <Input label="آدرس" icon={MapPin} placeholder="آدرس کامل شعبه" />
        </div>
      </Modal>
    </>
  );
}

/* ============ کاربران ============ */

function UsersSection() {
  const [modalOpen, setModalOpen] = useState(false);

  const getUserMenu = (u) => [
    { label: 'ویرایش', icon: Pencil, onClick: () => console.log('Edit:', u.id) },
    { label: 'غیرفعال', icon: UserX, onClick: () => console.log('Disable:', u.id) },
    { label: 'حذف', icon: Trash2, variant: 'danger', onClick: () => console.log('Delete:', u.id) },
  ];

  return (
    <>
      <Card
        title="کاربران سازمان"
        subtitle={`${usersList.length} کاربر`}
        action={
          <Button size="sm" icon={Plus} onClick={() => setModalOpen(true)}>
            افزودن کاربر
          </Button>
        }
      >
        <div className="overflow-x-auto -m-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-base">
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نام</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">ایمیل</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نقش</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">شعبه</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">آخرین ورود</th>
                <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                <th className="w-12"></th>
              </tr>
            </thead>
            <tbody>
              {usersList.map((u) => {
                const role = roleMap[u.role];
                const status = userStatusMap[u.status];
                return (
                  <tr key={u.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-brand-900/40 flex items-center justify-center text-brand-400 font-bold text-xs flex-shrink-0">
                          {u.firstName[0]}
                        </div>
                        <div>
                          <div className="font-medium text-text-primary text-xs">{u.firstName} {u.lastName}</div>
                          <div className="text-[10px] text-text-muted font-mono">{u.mobile}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-text-secondary text-xs font-mono">{u.email}</td>
                    <td className="py-3 px-4"><Badge variant={role.variant}>{role.label}</Badge></td>
                    <td className="py-3 px-4 text-text-secondary text-xs">
                      {u.branch || <span className="text-text-muted">—</span>}
                    </td>
                    <td className="py-3 px-4 text-text-muted text-xs font-mono">{u.lastLogin}</td>
                    <td className="py-3 px-4"><Badge variant={status.variant}>{status.label}</Badge></td>
                    <td className="py-3 px-2">
                      <ActionMenu items={getUserMenu(u)} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="افزودن کاربر"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>انصراف</Button>
            <Button>ذخیره</Button>
          </>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input label="نام" />
          <Input label="نام خانوادگی" />
          <Input label="ایمیل" icon={Mail} />
          <Input label="موبایل" icon={Phone} />
          <Input label="رمز عبور موقت" icon={Shield} />
          <div>
            <label className="block text-sm text-text-secondary mb-2">نقش</label>
            <select className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-brand-500">
              <option value="branch_manager">مدیر شعبه</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm text-text-secondary mb-2">شعبه</label>
            <select className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-brand-500">
              <option value="">انتخاب کنید...</option>
              {branchesList.map((b) => (
                <option key={b.id} value={b.name}>{b.name}</option>
              ))}
            </select>
          </div>
        </div>
      </Modal>
    </>
  );
}

/* ============ اعلان‌ها ============ */

function NotificationsSection() {
  const [settings, setSettings] = useState(notificationSettings);

  const toggle = (id, channel) => {
    setSettings((prev) =>
      prev.map((s) => (s.id === id ? { ...s, [channel]: !s[channel] } : s))
    );
  };

  return (
    <Card title="تنظیمات اعلان‌ها" subtitle="انتخاب کانال دریافت هر نوع هشدار">
      <div className="overflow-x-auto -m-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-base">
              <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نوع اعلان</th>
              <th className="text-center py-3 px-4 text-xs font-medium text-text-muted">ایمیل</th>
              <th className="text-center py-3 px-4 text-xs font-medium text-text-muted">پیامک</th>
              <th className="text-center py-3 px-4 text-xs font-medium text-text-muted">پوش</th>
            </tr>
          </thead>
          <tbody>
            {settings.map((s) => (
              <tr key={s.id} className="border-b border-border-base last:border-0">
                <td className="py-3 px-4">
                  <div className="font-medium text-text-primary text-xs">{s.label}</div>
                  <div className="text-[10px] text-text-muted mt-0.5">{s.description}</div>
                </td>
                {['email', 'sms', 'push'].map((ch) => (
                  <td key={ch} className="py-3 px-4 text-center">
                    <label className="inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={s[ch]}
                        onChange={() => toggle(s.id, ch)}
                        className="w-4 h-4 rounded border-border-base bg-bg-base text-brand-500 focus:ring-brand-500/20 focus:ring-2 cursor-pointer accent-brand-500"
                      />
                    </label>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-end gap-2 pt-4 mt-5 border-t border-border-base">
        <Button variant="secondary">انصراف</Button>
        <Button>ذخیره تغییرات</Button>
      </div>
    </Card>
  );
}

/* ============ تنظیمات سامانه (فقط ادمین) ============ */

function SystemSection() {
  const [settings, setSettings] = useState({
    map_provider: MAP_PROVIDERS.LEAFLET_OSM,
    map_refresh_interval_seconds: 10,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let active = true;
    apiClient.get('/site-settings/')
      .then(({ data }) => {
        if (active) {
          setSettings({
            map_provider: data.map_provider || MAP_PROVIDERS.LEAFLET_OSM,
            map_refresh_interval_seconds: Number(data.map_refresh_interval_seconds) || 10,
          });
        }
      })
      .catch((requestError) => {
        if (active) setError(requestError.response?.data?.detail || 'دریافت تنظیمات سامانه ناموفق بود.');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const { data } = await apiClient.patch('/site-settings/', {
        map_provider: settings.map_provider,
        map_refresh_interval_seconds: Number(settings.map_refresh_interval_seconds),
      });
      setSettings({
        map_provider: data.map_provider,
        map_refresh_interval_seconds: Number(data.map_refresh_interval_seconds),
      });
      setSuccess('تنظیمات با موفقیت ذخیره شد. از این پس نقشه با این مقادیر پیش‌فرض بارگذاری می‌شود.');
    } catch (requestError) {
      const data = requestError.response?.data;
      const detail = data?.detail
        || data?.map_provider?.[0]
        || data?.map_refresh_interval_seconds?.[0]
        || 'ذخیره تنظیمات انجام نشد؛ ارتباط با سرور را بررسی کنید.';
      setError(detail);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card title="تنظیمات نقشه زنده" subtitle="مقادیر سراسری سامانه؛ ذخیره‌شده در پایگاه داده و قابل استفاده برای همه کاربران">
        <div className="space-y-6">
          {error && <div role="alert" className="rounded-field border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div>}
          {success && <div role="status" className="rounded-field border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">{success}</div>}

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <div className="rounded-card border border-border-base bg-bg-base p-4">
              <div className="mb-3 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-field bg-brand-500/10 text-brand-400"><GlobeIcon size={19} /></div>
                <div>
                  <h3 className="text-sm font-semibold text-text-primary">ارائه‌دهنده پیش‌فرض نقشه</h3>
                  <p className="mt-1 text-xs text-text-muted">نقشه‌ای که هنگام بازکردن صفحه نقشه زنده نمایش داده می‌شود</p>
                </div>
              </div>
              <label htmlFor="default-map-provider" className="mb-2 block text-sm text-text-secondary">انتخاب نقشه</label>
              <select
                id="default-map-provider"
                value={settings.map_provider}
                disabled={loading || saving}
                onChange={(event) => setSettings((previous) => ({ ...previous, map_provider: event.target.value }))}
                className="w-full rounded-field border border-border-base bg-bg-elevated px-4 py-3 text-sm text-text-primary outline-none transition focus:border-brand-500 disabled:opacity-60"
              >
                <option value={MAP_PROVIDERS.LEAFLET_OSM}>OpenStreetMap</option>
                <option value={MAP_PROVIDERS.NESHAN_LEAFLET}>نشان</option>
              </select>
              <p className="mt-2 text-xs leading-6 text-text-muted">این گزینه پیش‌فرض مشترک سایت را تعیین می‌کند. انتخاب موقت داخل صفحه نقشه، تا بارگذاری مجدد همان صفحه اعمال می‌شود.</p>
            </div>

            <div className="rounded-card border border-border-base bg-bg-base p-4">
              <div className="mb-3 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-field bg-brand-500/10 text-brand-400"><ActivityIcon /></div>
                <div>
                  <h3 className="text-sm font-semibold text-text-primary">بازه به‌روزرسانی خودکار</h3>
                  <p className="mt-1 text-xs text-text-muted">فاصله دریافت دوباره موقعیت دستگاه‌ها از API</p>
                </div>
              </div>
              <label htmlFor="map-refresh-interval" className="mb-2 block text-sm text-text-secondary">فاصله زمانی (ثانیه)</label>
              <div className="flex items-center gap-3">
                <input
                  id="map-refresh-interval"
                  type="number"
                  min="5"
                  max="300"
                  step="1"
                  inputMode="numeric"
                  value={settings.map_refresh_interval_seconds}
                  disabled={loading || saving}
                  onChange={(event) => setSettings((previous) => ({ ...previous, map_refresh_interval_seconds: event.target.value }))}
                  className="w-full rounded-field border border-border-base bg-bg-elevated px-4 py-3 text-sm text-text-primary outline-none transition focus:border-brand-500 disabled:opacity-60"
                />
                <span className="whitespace-nowrap text-sm text-text-muted">ثانیه</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-text-muted">
                {[5, 10, 15, 30, 60].map((seconds) => (
                  <button
                    key={seconds}
                    type="button"
                    disabled={loading || saving}
                    onClick={() => setSettings((previous) => ({ ...previous, map_refresh_interval_seconds: seconds }))}
                    className={`rounded-full border px-3 py-1.5 transition ${Number(settings.map_refresh_interval_seconds) === seconds ? 'border-brand-500 bg-brand-500/10 text-brand-400' : 'border-border-base hover:bg-bg-hover'}`}
                  >{seconds.toLocaleString('fa-IR')} ثانیه</button>
                ))}
              </div>
              <p className="mt-2 text-xs leading-6 text-text-muted">مقدار مجاز بین ۵ تا ۳۰۰ ثانیه است. بازه کوتاه‌تر درخواست‌های بیشتری به سرور ارسال می‌کند.</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border-base pt-4">
            <p className="text-xs text-text-muted">تغییرات فقط پس از ذخیره، برای بارگذاری‌های بعدی صفحه نقشه اعمال می‌شوند.</p>
            <Button onClick={saveSettings} disabled={loading || saving}>
              {saving ? 'در حال ذخیره…' : loading ? 'در حال دریافت…' : 'ذخیره تنظیمات'}
            </Button>
          </div>
        </div>
      </Card>

      <TraccarPortManager />

      <Card title="وضعیت سرور و سرویس‌ها" subtitle="نمای کلی زیرساخت سامانه">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="flex items-center gap-3 rounded-field border border-border-base bg-bg-base p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-field bg-success/10"><Server size={18} className="text-success" /></div>
            <div><div className="text-xs text-text-muted">Ingestion Server</div><div className="text-sm font-medium text-text-primary">وضعیت از مانیتورینگ قابل بررسی است</div></div>
          </div>
          <div className="flex items-center gap-3 rounded-field border border-border-base bg-bg-base p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-field bg-brand-500/10"><Database size={18} className="text-brand-400" /></div>
            <div><div className="text-xs text-text-muted">Database</div><div className="text-sm font-medium text-text-primary">تنظیمات در PostgreSQL ذخیره می‌شود</div></div>
          </div>
          <div className="flex items-center gap-3 rounded-field border border-border-base bg-bg-base p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-field bg-info/10"><GlobeIcon size={18} className="text-info" /></div>
            <div><div className="text-xs text-text-muted">نقشه پیش‌فرض</div><div className="text-sm font-medium text-text-primary">{settings.map_provider === MAP_PROVIDERS.NESHAN_LEAFLET ? 'نشان' : 'OpenStreetMap'}</div></div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function ActivityIcon() {
  return <Globe size={19} />;
}


/* ============ مدیریت پورت‌های ورودی Traccar (ادمین) ============ */

function TraccarPortManager() {
  const CAPTURE_TEST_PORT = 1256;
  const [port, setPort] = useState('9026');
  const [models, setModels] = useState([]);
  const [modelSearch, setModelSearch] = useState('');
  const [modelId, setModelId] = useState('');
  const [modelsLoading, setModelsLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState([
    'آماده؛ آزمون API مستقل است؛ برای پیکربندی پورت، مدل دستگاه را انتخاب کنید.',
  ]);
  const [error, setError] = useState('');
  const [captureRunning, setCaptureRunning] = useState(false);
  const [captureStreaming, setCaptureStreaming] = useState(false);
  const [captureRemainingSeconds, setCaptureRemainingSeconds] = useState(0);
  const [copyFeedback, setCopyFeedback] = useState('');
  const captureAbortRef = useRef(null);

  useEffect(() => {
    let active = true;
    apiClient.get('/device-models/')
      .then(({ data }) => {
        if (active) setModels(Array.isArray(data) ? data : (data.results || []));
      })
      .catch((requestError) => {
        if (active) setError(requestError.response?.data?.detail || 'دریافت فهرست مدل‌های دستگاه ناموفق بود.');
      })
      .finally(() => { if (active) setModelsLoading(false); });
    return () => { active = false; };
  }, []);

  const matchingModels = models.filter((model) => {
    const label = `${model.manufacturer || ''} ${model.name || ''} ${model.code || ''}`.toLowerCase();
    return label.includes(modelSearch.trim().toLowerCase());
  }).slice(0, 100);

  const runOperation = async (action, requestedPort = port) => {
    const isApiTest = action === 'api-test';
    const parsedPort = Number(requestedPort);
    if (!isApiTest && (!Number.isInteger(parsedPort) || parsedPort < 1024 || parsedPort > 65535)) {
      setError('شماره پورت باید عدد صحیح بین ۱۰۲۴ و ۶۵۵۳۵ باشد.');
      return { success: false, lines: [] };
    }
    if (action === 'apply' && !modelId) {
      setError('برای پیکربندی خودکار Traccar، مدل دستگاه را انتخاب کنید.');
      return { success: false, lines: [] };
    }
    setBusy(true);
    setError('');
    setLogs((previous) => [...previous, isApiTest ? '> شروع آزمون اتصال API ترکار…' : '> شروع عملیات ' + action + ' برای پورت ' + parsedPort + '…']);
    let operationSucceeded = true;
    const operationLines = [];
    try {
      const token = localStorage.getItem('sana_access_token');
      const response = await fetch(apiClient.defaults.baseURL + '/gps-monitor/ports/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
        body: JSON.stringify({ action, ...(!isApiTest ? { port: parsedPort } : {}), ...(action === 'apply' ? { device_model_id: Number(modelId) } : {}) }),
      });
      if (!response.ok) {
        let detail = 'درخواست با خطای HTTP ' + response.status + ' مواجه شد.';
        try { const body = await response.json(); detail = body.detail || detail; } catch { /* پاسخ خطا ممکن است JSON نباشد. */ }
        throw new Error(detail);
      }
      if (!response.body) throw new Error('مرورگر امکان دریافت جریان زنده لاگ را فراهم نکرد.');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        for (const event of events) {
          const dataLine = event.split('\n').find((line) => line.startsWith('data: '));
          if (!dataLine) continue;
          try {
            const item = JSON.parse(dataLine.slice(6));
            const line = String(item.line || '');
            operationLines.push(line);
            if (line.startsWith('خطا:') || line.includes('عملیات ناموفق بود')) operationSucceeded = false;
            setLogs((previous) => [...previous, line]);
          } catch {
            operationLines.push(dataLine.slice(6));
            setLogs((previous) => [...previous, dataLine.slice(6)]);
          }
        }
        if (done) break;
      }
    } catch (requestError) {
      operationSucceeded = false;
      operationLines.push('خطا: ' + (requestError.message || 'ارتباط با سرور برقرار نشد.'));
      setError(requestError.message || 'اجرای عملیات ناموفق بود.');
      setLogs((previous) => [...previous, 'خطا: ' + (requestError.message || 'ارتباط با سرور برقرار نشد.')]);
    } finally { setBusy(false); }
    return { success: operationSucceeded, lines: operationLines };
  };

  useEffect(() => {
    let active = true;
    let controller;
    let statusPoll;
    (async () => {
      try {
        const token = localStorage.getItem('sana_access_token');
        const statusResponse = await fetch(apiClient.defaults.baseURL + '/gps-monitor/ports/', {
          method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
          body: JSON.stringify({ action: 'capture-status', port: CAPTURE_TEST_PORT }),
        });
        if (!statusResponse.ok || !statusResponse.body) return;
        const statusText = await statusResponse.text();
        const isRunning = statusText.includes('فعال است');
        const remainingMatch = statusText.match(/زمان باقی‌مانده:\s*(\d+)\s*ثانیه/);
        if (!active || !isRunning) return;
        setCaptureRemainingSeconds(remainingMatch ? Number(remainingMatch[1]) : 0);
        setCaptureRunning(true); setCaptureStreaming(true);
        setLogs((previous) => [...previous, 'شنود قبلی روی سرور فعال است؛ در حال بازیابی لاگ ذخیره‌شده و زنده…']);
        statusPoll = window.setInterval(async () => {
          try {
            const check = await fetch(apiClient.defaults.baseURL + '/gps-monitor/ports/', {
              method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
              body: JSON.stringify({ action: 'capture-status', port: CAPTURE_TEST_PORT }),
            });
            const status = await check.text();
            const remaining = status.match(/زمان باقی‌مانده:\s*(\d+)\s*ثانیه/);
            if (!status.includes('فعال است')) {
              controller?.abort(); setCaptureRunning(false); setCaptureStreaming(false);
              setCaptureRemainingSeconds(0);
              setLogs((previous) => [...previous, 'مهلت شنود پایان یافته یا دریافت متوقف شده است.']);
              window.clearInterval(statusPoll);
            } else if (remaining) {
              setCaptureRemainingSeconds(Number(remaining[1]));
            }
          } catch { /* retry on the next poll */ }
        }, 10000);
        controller = new AbortController();
        const logResponse = await fetch(apiClient.defaults.baseURL + '/gps-monitor/ports/capture/' + CAPTURE_TEST_PORT + '/', {
          headers: { Accept: 'text/event-stream', ...(token ? { Authorization: 'Bearer ' + token } : {}) }, signal: controller.signal,
        });
        if (!logResponse.ok || !logResponse.body) throw new Error('خواندن لاگ شنود ناموفق بود.');
        const reader = logResponse.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (active) {
          const { value, done } = await reader.read();

          buffer += decoder.decode(value || new Uint8Array(), {
            stream: !done,
          });

          const events = buffer.split('\n\n');
          buffer = events.pop() || '';

          for (const event of events) {
            const dataLine = event
              .split('\n')
              .find((item) => item.startsWith('data: '));

            if (!dataLine) continue;

            try {
              const item = JSON.parse(dataLine.slice(6));

              if (typeof item.line === 'string') {
                setLogs((previous) => [...previous, item.line]);
              }
            } catch {
              setLogs((previous) => [
                ...previous,
                dataLine.slice(6),
              ]);
            }
          }

          if (done) break;
        }
      } catch (err) { if (active && err.name !== 'AbortError') setLogs((previous) => [...previous, 'بازیابی لاگ: ' + err.message]); }
      finally { if (active) setCaptureStreaming(false); }
    })();
    return () => { active = false; controller?.abort(); if (statusPoll) window.clearInterval(statusPoll); };
  }, []);

  useEffect(() => {
    if (!captureRunning || captureRemainingSeconds <= 0) return undefined;
    const timer = window.setInterval(() => {
      setCaptureRemainingSeconds((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [captureRunning, captureRemainingSeconds > 0]);

  const formatCaptureTime = (seconds) => {
    const safeSeconds = Math.max(0, Number(seconds) || 0);
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const remainder = safeSeconds % 60;
    return [hours, minutes, remainder].map((value) => String(value).padStart(2, '0')).join(':');
  };

  const copyLogs = async () => {
    const content = logs.join('\n');
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopyFeedback('متن لاگ کپی شد');
    } catch {
      setCopyFeedback('کپی خودکار در این مرورگر مجاز نیست؛ از انتخاب و کپی متن استفاده کنید.');
    }
    window.setTimeout(() => setCopyFeedback(''), 3000);
  };

  const toggleCapture = async () => {
    const result = await runOperation('capture-toggle', CAPTURE_TEST_PORT);
    if (!result || !result.success) return;
    const started = result.lines.some((line) => line.includes('شروع شد'));
    const stopped = result.lines.some((line) => line.includes('متوقف شد') || line.includes('فعال نیست'));
    if (started) {
      setCaptureRunning(true);
      setCaptureRemainingSeconds(6 * 60 * 60);
      setCaptureStreaming(true);
      const controller = new AbortController();
      captureAbortRef.current = controller;
      try {
        const token = localStorage.getItem('sana_access_token');
        const response = await fetch(apiClient.defaults.baseURL + '/gps-monitor/ports/capture/' + CAPTURE_TEST_PORT + '/', {
          headers: { Accept: 'text/event-stream', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) throw new Error('دریافت لاگ زنده ناموفق بود (HTTP ' + response.status + ').');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const event of events) {
            const dataLine = event.split('\n').find((line) => line.startsWith('data: '));
            if (!dataLine) continue;
            try { const item = JSON.parse(dataLine.slice(6)); setLogs((previous) => [...previous, item.line]); }
            catch { setLogs((previous) => [...previous, dataLine.slice(6)]); }
          }
          if (done) break;
        }
      } catch (streamError) {
        if (streamError.name !== 'AbortError') setLogs((previous) => [...previous, 'خطای دریافت لاگ: ' + streamError.message]);
      } finally { setCaptureStreaming(false); captureAbortRef.current = null; }
    } else if (stopped) {
      captureAbortRef.current?.abort();
      captureAbortRef.current = null;
      setCaptureRunning(false);
      setCaptureRemainingSeconds(0);
      setCaptureStreaming(false);
    }
  };

  return (
    <Card title="مدیریت پورت‌های ورودی GPS" subtitle="پیکربندی شنونده Traccar، تنظیم فایروال و بررسی دریافت ترافیک ورودی">
      <div className="space-y-5">
        {error && <div role="alert" className="rounded-field border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div>}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="traccar-input-port" className="mb-2 block text-sm text-text-secondary">شماره پورت</label>
            <input
              id="traccar-input-port"
              type="number"
              min="1024"
              max="65535"
              step="1"
              value={port}
              disabled={busy || captureRunning}
              onChange={(event) => setPort(event.target.value)}
              className="w-full rounded-field border border-border-base bg-bg-elevated px-4 py-3 text-sm text-text-primary outline-none focus:border-brand-500 disabled:opacity-60"
              placeholder="مثلاً 9026"
            />
            <p className="mt-2 text-xs leading-6 text-text-muted">این شماره باید با پورت تنظیم‌شده روی دستگاه و فورواردشده توسط ISP مطابقت داشته باشد.</p>
          </div>
          <div>
            <label htmlFor="traccar-device-model-search" className="mb-2 block text-sm text-text-secondary">مدل دستگاه برای تنظیم خودکار Traccar</label>
            <input
              id="traccar-device-model-search"
              type="search"
              value={modelSearch}
              disabled={busy || captureRunning || modelsLoading}
              onChange={(event) => setModelSearch(event.target.value)}
              className="mb-2 w-full rounded-field border border-border-base bg-bg-elevated px-4 py-3 text-sm text-text-primary outline-none focus:border-brand-500 disabled:opacity-60"
              placeholder="جست‌وجوی سازنده یا مدل…"
            />
            <select
              aria-label="مدل دستگاه"
              value={modelId}
              disabled={busy || captureRunning || modelsLoading}
              onChange={(event) => setModelId(event.target.value)}
              className="w-full rounded-field border border-border-base bg-bg-elevated px-4 py-3 text-sm text-text-primary outline-none focus:border-brand-500 disabled:opacity-60"
            >
              <option value="">{modelsLoading ? 'در حال دریافت مدل‌ها…' : 'انتخاب مدل دستگاه'}</option>
              {matchingModels.map((model) => (
                <option key={model.id} value={model.id}>{model.manufacturer} — {model.name}</option>
              ))}
            </select>
            <p className="mt-2 text-xs leading-6 text-text-muted">پروتکل در رابط کاربری نمایش داده یا انتخاب نمی‌شود؛ تنظیم داخلی از کاتالوگ مدل انتخاب‌شده استخراج می‌شود.</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy || captureRunning} onClick={() => runOperation('api-test')}>آزمون اتصال API ترکار</Button>
          <Button variant={captureRunning ? 'danger' : 'primary'} disabled={busy} onClick={toggleCapture}>{captureRunning ? 'توقف رصد زنده پورت ۱۲۵۶' : 'دریافت دیتای تست پورت ۱۲۵۶ (ثابت)'}</Button>
          <Button disabled={busy || captureRunning || modelsLoading || !modelId} onClick={() => runOperation('apply')}>
            {busy ? 'در حال اجرا…' : 'پیکربندی فایروال و Traccar'}
          </Button>
          <Button variant="secondary" disabled={busy || captureRunning} onClick={() => runOperation('status')}>بررسی شنونده پورت</Button>
          <Button variant="secondary" disabled={busy || captureRunning} onClick={() => runOperation('diagnostics')}>گزارش وضعیت و خطاهای Traccar</Button>
          <Button
            variant="secondary"
            disabled={busy || captureRunning}
            onClick={() => {
              if (window.confirm('مالکیت و مجوز خواندن فایل تنظیمات فقط برای کاربر سرویس Traccar اصلاح و سرویس دوباره راه‌اندازی می‌شود. هیچ قانون فایروالی تغییر نمی‌کند. ادامه می‌دهید؟')) {
                runOperation('repair-permissions');
              }
            }}
          >ترمیم دسترسی فایل تنظیمات Traccar</Button>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => {
              if (window.confirm('آخرین نسخه پشتیبان traccar.xml بازیابی و مجوز دسترسی سرویس نیز اصلاح می‌شود؛ سپس Traccar راه‌اندازی مجدد می‌شود. هیچ قانون فایروالی تغییر نمی‌کند. ادامه می‌دهید؟')) {
                runOperation('restore');
              }
            }}
          >بازیابی آخرین نسخه پشتیبان</Button>
          <Button variant="secondary" disabled={busy || captureRunning} onClick={() => runOperation('test')}>آزمون ترافیک ورودی (۲۰ ثانیه)</Button>
          <Button variant="secondary" disabled={busy} onClick={() => setLogs([])}>پاک‌کردن خروجی</Button>
        </div>

        <div className="overflow-hidden rounded-field border border-border-base bg-[#0b1220]">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-slate-200">گزارش اجرای عملیات</span>
              <button type="button" title="کپی تمام لاگ‌ها" aria-label="کپی تمام لاگ‌ها" disabled={!logs.length} onClick={copyLogs} className="inline-flex h-8 w-8 items-center justify-center rounded-field border border-white/15 text-slate-300 transition-colors hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"><Copy size={15} aria-hidden="true" /></button>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-slate-400">
              {captureRunning && <span dir="ltr" className="font-mono">{formatCaptureTime(captureRemainingSeconds)}</span>}
              <span>{captureStreaming ? 'رصد زنده فعال' : busy ? 'در حال اجرا' : captureRunning ? 'شنود فعال' : 'آماده'}</span>
            </div>
          </div>
          {copyFeedback && <div role="status" className="border-b border-white/10 px-4 py-1 text-[10px] text-slate-300">{copyFeedback}</div>}
          <pre
            role="log"
            aria-live="polite"
            className="max-h-80 min-h-36 overflow-auto whitespace-pre-wrap break-words p-4 font-mono text-xs leading-6 text-emerald-300"
          >{logs.length ? logs.join('\n') : 'خروجی خالی است.'}</pre>
        </div>
        <p className="text-xs leading-6 text-text-muted">
          برای شناسایی پروتکل ناشناخته، پورت ثابت ۱۲۵۶ مخصوص شنود آزمایشی است و از شماره پورت بالای این بخش مستقل عمل می‌کند. ابتدا فوروارد ورودی TCP و UDP پورت ۱۲۵۶ را در روتر/رادیو برقرار کنید؛ UFW سرور هنگام شروع شنود باز می‌شود. سپس دستگاه را موقتاً به پورت ۱۲۵۶ بفرستید و «دریافت دیتای تست پورت ۱۲۵۶» را بزنید. داده خام به‌صورت HEX ثبت می‌شود و وارد جداول GPS سانا نمی‌شود. هنگام ضبط، Traccar نباید روی ۱۲۵۶ شنونده داشته باشد. پس از دریافت نمونه، شنود را متوقف کنید. با توقف شنود، فقط قانون‌های موقت UFW که این ابزار ایجاد کرده است حذف می‌شوند؛ فوروارد TCP/UDP پورت ۱۲۵۶ در روتر باید دائماً فعال بماند تا برای آزمایش دستگاه‌های بعدی نیز آماده باشد. سپس پروتکل را از روی داده خام شناسایی کنید و دستگاه را به پورت واقعی و فعال همان پروتکل در Traccar تنظیم کنید؛ پورت ۱۲۵۶ هرگز نباید در تنظیمات Traccar وارد یا به آن اختصاص داده شود. سقف فایل ضبط ۴ مگابایت است.
        </p>
      </div>
    </Card>
  );
}
