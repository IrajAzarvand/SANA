import {
  BrainCircuit, ShieldCheck, FlaskConical, GitBranch,
  FileSearch, LockKeyhole, CircleCheck, Clock3, AlertTriangle,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';

const workflow = [
  {
    number: '01',
    icon: FileSearch,
    title: 'دریافت نمونه خام',
    description: 'انتخاب دستگاه ثبت‌شده و مشاهده نمونه‌های ورودی برای تحلیل؛ بدون تغییر در پردازش زنده.',
    status: 'در انتظار اتصال API',
  },
  {
    number: '02',
    icon: BrainCircuit,
    title: 'تشخیص پروتکل',
    description: 'بررسی شواهد و پیشنهاد پروتکل احتمالی همراه با میزان اطمینان و دلیل تشخیص.',
    status: 'در انتظار پیاده‌سازی',
  },
  {
    number: '03',
    icon: FlaskConical,
    title: 'تولید و آزمایش Decoder',
    description: 'ساخت نسخه پیشنهادی و اجرای تست‌ها در محیط ایزوله، خارج از سرویس GPS زنده.',
    status: 'غیرفعال برای ایمنی',
  },
  {
    number: '04',
    icon: GitBranch,
    title: 'بازبینی و انتشار',
    description: 'تأیید انسانی، ثبت نسخه، انتشار کنترل‌شده و امکان بازگشت به نسخه قبلی.',
    status: 'در انتظار طراحی',
  },
];

export default function AIManagement() {
  return (
    <div className="space-y-6" dir="rtl">
      <PageHeader
        title="مدیریت هوش مصنوعی"
        subtitle="تشخیص پروتکل و چرخه کنترل‌شده تولید Decoder برای دستگاه‌های GPS"
      />

      <section className="rounded-card border border-border-base bg-bg-elevated p-5 md:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-field bg-brand-500/10 text-brand-500">
            <BrainCircuit size={25} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-text-primary">زیرساخت AI در حال آماده‌سازی</h2>
              <span className="rounded-full border border-border-base px-2.5 py-1 text-xs text-text-muted">
                هنوز به API متصل نیست
              </span>
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-text-secondary">
              این صفحه فعلاً نمای مدیریتی و مراحل کار را مشخص می‌کند. هیچ مدل هوش مصنوعی اجرا نمی‌شود،
              هیچ Decoder ساخته یا منتشر نمی‌شود و آمار ساختگی از دستگاه‌ها نمایش داده نمی‌شود.
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold text-text-primary">چرخه کاری پیشنهادی</h2>
          <p className="mt-1 text-sm text-text-muted">هر مرحله بعد از پیاده‌سازی API و تست امنیتی فعال می‌شود.</p>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {workflow.map((step) => {
            const Icon = step.icon;
            return (
              <article key={step.number} className="rounded-card border border-border-base bg-bg-elevated p-5">
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-field bg-bg-base text-text-secondary">
                    <Icon size={21} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-text-muted">{step.number}</span>
                      <h3 className="text-sm font-semibold text-text-primary">{step.title}</h3>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">{step.description}</p>
                    <div className="mt-4 flex items-center gap-2 border-t border-border-base pt-3 text-xs text-text-muted">
                      <Clock3 size={14} />
                      <span>{step.status}</span>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="rounded-card border border-border-base bg-bg-elevated p-5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 text-text-secondary"><ShieldCheck size={21} /></div>
          <div>
            <h2 className="text-sm font-semibold text-text-primary">مرزهای امنیتی</h2>
            <ul className="mt-3 list-disc space-y-2 pr-5 text-sm leading-6 text-text-secondary">
              <li>این بخش فقط برای ادمین کل سایت در نظر گرفته شده است.</li>
              <li>نمونه‌های خام ممکن است شناسه دستگاه یا داده حساس داشته باشند؛ دسترسی و نگهداری آن‌ها باید کنترل شود.</li>
              <li>کد تولیدشده توسط مدل هرگز مستقیماً در سرویس زنده import یا اجرا نمی‌شود.</li>
              <li>اجرای ایزوله، تست خودکار و تأیید انسانی پیش از انتشار الزامی است.</li>
              <li>کلید API مدل فقط در محیط امن Backend نگهداری می‌شود، نه در کد مرورگر.</li>
            </ul>
          </div>
        </div>
      </section>

      <p className="flex items-start gap-2 text-xs leading-6 text-text-muted">
        <AlertTriangle size={15} className="mt-0.5 shrink-0" />
        <span>
          وضعیت این صفحه صرفاً وضعیت طراحی رابط است و سلامت سرویس GPS، اتصال مدل یا وضعیت Decoderهای موجود را گزارش نمی‌کند.
        </span>
      </p>
    </div>
  );
}