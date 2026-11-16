import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock3, MapPinned, Route, ShieldCheck } from 'lucide-react';
import Button from '../components/Button';
import { useAuth } from '../context/AuthContext';

export default function Reports() {
  const navigate = useNavigate();
  const { isSiteAdmin, isPersonal, isBranchManager, user } = useAuth();

  const title = isSiteAdmin
    ? 'گزارش‌های سامانه'
    : isPersonal
      ? 'گزارش‌های من'
      : isBranchManager
        ? `گزارش‌های شعبه ${user?.branch?.name || ''}`
        : 'گزارش‌های سازمان';

  const description = isPersonal
    ? 'گزارش مسیر و عملکرد دستگاه‌های متصل به حساب شما'
    : isSiteAdmin
      ? 'گزارش مسیر دستگاه‌ها و بررسی داده‌های دریافتی سامانه'
      : 'گزارش مسیر و عملکرد دستگاه‌های تحت دسترسی شما';

  return (
    <div className="min-w-0 space-y-5">
      <header className="flex min-w-0 items-center gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-500/10 text-brand-500">
          <MapPinned size={21} />
        </div>
        <div className="min-w-0">
          <h1 className="text-base font-semibold text-text-primary sm:text-lg">{title}</h1>
          <p className="mt-1 text-xs leading-5 text-text-muted">{description}</p>
        </div>
      </header>

      <section className="rounded-2xl border border-border-base bg-bg-elevated p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500/10 text-brand-500">
              <Route size={19} />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-text-primary">گزارش مسیر و بازپخش حرکت</h2>
              <p className="mt-1 max-w-2xl text-xs leading-6 text-text-secondary">
                انتخاب دستگاه و بازه زمانی، مشاهده مسیر روی نقشه، بازپخش حرکت و بررسی سرعت، توقف‌ها و اطلاعات ثبت‌شده هر نقطه.
              </p>
            </div>
          </div>
          <Button onClick={() => navigate('/panel/reports/trips')} className="shrink-0">
            مشاهده گزارش مسیرها
            <ArrowLeft size={15} />
          </Button>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-2 border-t border-border-base pt-4 sm:grid-cols-3">
          <div className="flex items-center gap-2 rounded-lg bg-bg-base px-3 py-2.5">
            <Clock3 size={15} className="shrink-0 text-text-muted" />
            <span className="text-[11px] text-text-secondary">انتخاب تاریخ و ساعت شمسی</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-bg-base px-3 py-2.5">
            <MapPinned size={15} className="shrink-0 text-text-muted" />
            <span className="text-[11px] text-text-secondary">نمایش مسیر و بازپخش روی نقشه</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-bg-base px-3 py-2.5">
            <ShieldCheck size={15} className="shrink-0 text-text-muted" />
            <span className="text-[11px] text-text-secondary">محدود به دستگاه‌ها و بازه مجاز</span>
          </div>
        </div>
      </section>

      <p className="text-[11px] leading-5 text-text-muted">
        اطلاعات این گزارش از تاریخچه واقعی Traccar دریافت می‌شود. آمار مسافت و زمان، برآوردی از نقاط ثبت‌شده است و جایگزین کیلومترشمار رسمی خودرو نیست.
      </p>
    </div>
  );
}
