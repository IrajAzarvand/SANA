import { useNavigate } from 'react-router-dom';
import { ArrowRight, Route } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Button from '../components/Button';
import DeviceReportPlayback from '../components/DeviceReportPlayback';
import { useAuth } from '../context/AuthContext';

export default function DeviceTripReport() {
  const navigate = useNavigate();
  const { isSiteAdmin } = useAuth();

  return (
    <div className="space-y-6">
      <PageHeader
        title="گزارش سفرها"
        subtitle="تاریخچه مسیر دستگاه‌ها را در بازه زمانی دلخواه بررسی و بازپخش کنید."
        actions={(
          <Button variant="secondary" onClick={() => navigate('/panel/reports')}>
            <ArrowRight size={16} />
            بازگشت به گزارش‌ها
          </Button>
        )}
      />
      <div className="rounded-2xl border border-border-base bg-bg-elevated p-4 sm:p-6">
        <div className="mb-5 flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-500/10 text-brand-500">
            <Route size={21} />
          </div>
          <div>
            <h2 className="font-semibold text-text-primary">مسیر و تاریخچه موقعیت GPS</h2>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              دستگاه، سیم‌کارت یا راننده را جست‌وجو کنید، بازه زمانی را انتخاب کنید و مسیر ذخیره‌شده را روی نقشه بازپخش کنید.
            </p>
          </div>
        </div>
        <DeviceReportPlayback isSiteAdmin={isSiteAdmin} />
      </div>
    </div>
  );
}
