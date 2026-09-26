import { useState } from 'react';
import {
  Plus, MoreVertical, Pencil, Trash2, Camera, Mail, Phone,
  Shield, Smartphone, Building2, MapPin, Globe,
  UserX, Globe as GlobeIcon, Database, Server,
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
import {
  currentUser,
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

/* ============ پروفایل ============ */

function ProfileSection() {
  const [form, setForm] = useState(currentUser);

  return (
    <Card title="پروفایل من" subtitle="اطلاعات شخصی و تماس">
      <div className="space-y-6">

        <div className="flex items-center gap-5">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-brand-500 flex items-center justify-center text-bg-base text-2xl font-bold">
              {form.firstName[0]}
            </div>
            <button className="absolute bottom-0 left-0 w-7 h-7 rounded-full bg-bg-overlay border border-border-base flex items-center justify-center hover:bg-bg-hover transition-colors">
              <Camera size={14} className="text-text-secondary" />
            </button>
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary">
              {form.firstName} {form.lastName}
            </h3>
            <p className="text-xs text-text-muted mt-0.5">{form.role}</p>
          </div>
        </div>

        <div className="border-t border-border-base" />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="نام"
            value={form.firstName}
            onChange={(e) => setForm({ ...form, firstName: e.target.value })}
          />
          <Input
            label="نام خانوادگی"
            value={form.lastName}
            onChange={(e) => setForm({ ...form, lastName: e.target.value })}
          />
          <Input
            label="ایمیل"
            icon={Mail}
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <Input
            label="موبایل"
            icon={Phone}
            value={form.mobile}
            onChange={(e) => setForm({ ...form, mobile: e.target.value })}
          />
        </div>

        <div className="flex items-center justify-end gap-2 pt-4 border-t border-border-base">
          <Button variant="secondary">انصراف</Button>
          <Button>ذخیره تغییرات</Button>
        </div>

      </div>
    </Card>
  );
}

/* ============ امنیت ============ */

function SecuritySection() {
  const [pwForm, setPwForm] = useState({ current: '', new: '', confirm: '' });

  return (
    <div className="space-y-6">

      <Card title="تغییر رمز عبور" subtitle="برای امنیت بیشتر، رمز قوی انتخاب کنید">
        <div className="space-y-4">
          <Input type="password" label="رمز فعلی" icon={Shield} />
          <Input type="password" label="رمز جدید" icon={Shield} />
          <Input type="password" label="تکرار رمز جدید" icon={Shield} />

          <div className="flex items-center justify-end gap-2 pt-4 border-t border-border-base">
            <Button variant="secondary">انصراف</Button>
            <Button>تغییر رمز</Button>
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
            <Button size="sm">فعال‌سازی</Button>
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
  return (
    <div className="space-y-6">

      <Card title="تنظیمات عمومی سامانه" subtitle="پیکربندی سراسری سانا">
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="نام سامانه" value="سانا" />
            <Input label="نسخه" value="1.0.0" disabled />
            <Input label="منطقه زمانی" value="Asia/Tehran (UTC+3:30)" />
            <Input label="زبان پیش‌فرض" value="فارسی" />
          </div>

          <div className="flex items-center justify-end gap-2 pt-4 border-t border-border-base">
            <Button>ذخیره تغییرات</Button>
          </div>
        </div>
      </Card>

      <Card title="وضعیت سرور و سرویس‌ها" subtitle="مانیتورینگ زیرساخت">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-4 bg-bg-base border border-border-base rounded-field">
            <div className="w-10 h-10 rounded-field bg-success/10 flex items-center justify-center">
              <Server size={18} className="text-success" />
            </div>
            <div>
              <div className="text-xs text-text-muted">Ingestion Server</div>
              <div className="text-sm font-medium text-success">فعال</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-4 bg-bg-base border border-border-base rounded-field">
            <div className="w-10 h-10 rounded-field bg-success/10 flex items-center justify-center">
              <Database size={18} className="text-success" />
            </div>
            <div>
              <div className="text-xs text-text-muted">Database</div>
              <div className="text-sm font-medium text-success">سالم</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-4 bg-bg-base border border-border-base rounded-field">
            <div className="w-10 h-10 rounded-field bg-info/10 flex items-center justify-center">
              <GlobeIcon size={18} className="text-info" />
            </div>
            <div>
              <div className="text-xs text-text-muted">Neshan API</div>
              <div className="text-sm font-medium text-info">فعال</div>
            </div>
          </div>
        </div>
      </Card>

    </div>
  );
}