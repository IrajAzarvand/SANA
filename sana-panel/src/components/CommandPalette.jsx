import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowUp, ArrowDown, CornerDownLeft, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const normalize = (value = '') => String(value)
  .toLocaleLowerCase('fa')
  .replace(/[ي]/g, 'ی')
  .replace(/[ك]/g, 'ک')
  .replace(/[\u064B-\u065F\u0670]/g, '')
  .trim();

function getCommands(user) {
  const role = user?.role;
  const common = [
    { path: '/panel/dashboard', label: 'داشبورد', keywords: 'خانه نمای کلی' },
    { path: '/panel/map', label: 'نقشه زنده', keywords: 'نقشه موقعیت خودرو مکان' },
    { path: '/panel/devices', label: role === 'personal_user' ? 'دستگاه‌های من' : role === 'branch_manager' ? 'دستگاه‌های شعبه' : role === 'main_user' ? 'دستگاه‌های سازمان' : 'همه دستگاه‌ها', keywords: 'gps tracker دستگاه ردیاب سیم کارت imei' },
    { path: '/panel/reports/trips', label: 'گزارش مسیرها', keywords: 'گزارش سفر مسیر تاریخ' },
    { path: '/panel/alerts', label: 'مرکز اعلان‌ها و هشدارها', keywords: 'اعلان نوتیفیکیشن notification رویداد زنگ gps آفلاین آنلاین' },
    { path: '/panel/settings', label: role === 'site_admin' ? 'تنظیمات سایت' : role === 'personal_user' ? 'تنظیمات حساب' : 'تنظیمات سازمان', keywords: 'پروفایل حساب تنظیمات سایت سازمان' },
  ];

  if (role === 'personal_user') {
    return [...common, { path: '/panel/reports', label: 'گزارش‌ها', keywords: 'آمار' }];
  }
  if (role === 'site_admin') {
    return [
      ...common,
      { path: '/panel/vehicles', label: 'خودروها', keywords: 'ناوگان' },
      { path: '/panel/drivers', label: 'رانندگان', keywords: 'راننده' },
      { path: '/panel/branches', label: 'شعبه‌ها', keywords: 'شعب' },
      { path: '/panel/users', label: 'کاربران', keywords: 'حساب کاربری' },
      { path: '/panel/companies', label: 'شرکت‌ها', keywords: 'سازمان' },
      { path: '/panel/subscriptions', label: 'قراردادها', keywords: 'اشتراک' },
      { path: '/panel/ai', label: 'مدیریت هوش مصنوعی', keywords: 'ai هوش' },
      { path: '/panel/reports/live-logs', label: 'لاگ زنده سامانه', keywords: 'لاگ ثبت رخداد tcp ترافیک شبکه systemd traccar' },
      { path: '/panel/reports', label: 'گزارش‌ها', keywords: 'آمار' },
    ];
  }
  return [
    ...common,
    { path: '/panel/vehicles', label: 'خودروها', keywords: 'ناوگان' },
    { path: '/panel/drivers', label: 'رانندگان', keywords: 'راننده' },
    { path: '/panel/reports', label: 'گزارش‌ها', keywords: 'آمار' },
    ...(role === 'main_user' ? [
      { path: '/panel/branches', label: 'شعبه‌ها', keywords: 'شعب' },
      { path: '/panel/users', label: 'کاربران سازمان', keywords: 'حساب کاربری اعضا مدیریت کاربران' },
    ] : []),
  ];
}

export default function CommandPalette({ open, onClose }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);

  const commands = useMemo(() => getCommands(user), [user]);
  const results = useMemo(() => {
    const q = normalize(query);
    return q ? commands.filter((item) => normalize(`${item.label} ${item.keywords}`).includes(q)) : commands;
  }, [commands, query]);

  useEffect(() => {
    if (!open) return undefined;
    setQuery('');
    setActiveIndex(0);
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(focusTimer);
  }, [open]);

  useEffect(() => {
    setActiveIndex((index) => Math.min(index, Math.max(results.length - 1, 0)));
  }, [results.length]);

  const select = useCallback((item) => {
    if (!item) return;
    navigate(item.path);
    onClose();
  }, [navigate, onClose]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setActiveIndex((index) => results.length ? (index + 1) % results.length : 0);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        setActiveIndex((index) => results.length ? (index - 1 + results.length) % results.length : 0);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        select(results[activeIndex]);
      } else if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, results, activeIndex, onClose, select]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center bg-black/50 px-3 pt-[12vh]" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label="دستیار دسترسی سریع" className="w-full max-w-xl overflow-hidden rounded-xl border border-border-base bg-bg-overlay shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-border-base px-4">
          <Search size={18} className="shrink-0 text-text-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); }}
            placeholder="نام بخش یا قابلیت را بنویسید..."
            className="min-w-0 flex-1 bg-transparent py-4 text-sm text-text-primary placeholder:text-text-muted outline-none"
            aria-label="جستجوی بخش‌ها"
          />
          <button type="button" onClick={onClose} className="rounded p-1.5 text-text-muted hover:bg-bg-hover" aria-label="بستن"><X size={16} /></button>
        </div>
        <div className="max-h-[55vh] overflow-y-auto p-2">
          {results.length ? results.map((item, index) => (
            <button type="button" key={item.path} onClick={() => select(item)} onMouseEnter={() => setActiveIndex(index)} className={`flex w-full items-center justify-between rounded-lg px-3 py-3 text-right text-sm transition-colors ${activeIndex === index ? 'bg-bg-hover text-text-primary' : 'text-text-secondary hover:bg-bg-hover'}`}>
              <span>{item.label}</span>
              {activeIndex === index && <CornerDownLeft size={15} className="text-text-muted" />}
            </button>
          )) : <div className="px-4 py-8 text-center text-sm text-text-muted">نتیجه‌ای پیدا نشد.</div>}
        </div>
        <div className="flex items-center gap-4 border-t border-border-base px-3 py-2 text-[10px] text-text-muted">
          <span className="flex items-center gap-1"><ArrowUp size={12} /><ArrowDown size={12} /> انتخاب</span>
          <span className="flex items-center gap-1"><CornerDownLeft size={12} /> ورود</span>
          <span>Esc بستن</span>
        </div>
      </div>
    </div>
  );
}
