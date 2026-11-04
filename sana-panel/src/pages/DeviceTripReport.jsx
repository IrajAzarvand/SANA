import { useNavigate } from 'react-router-dom';
import { ArrowRight, Route } from 'lucide-react';
import Button from '../components/Button';
import DeviceReportPlayback from '../components/DeviceReportPlayback';
import { useAuth } from '../context/AuthContext';

export default function DeviceTripReport() {
  const navigate = useNavigate();
  const { isSiteAdmin } = useAuth();

  return (
    <div className="min-w-0 space-y-4">
      <header className="flex min-w-0 flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500/10 text-brand-500">
            <Route size={19} />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-text-primary sm:text-base">گزارش جامع دستگاه</h1>
            <p className="mt-0.5 text-[11px] leading-5 text-text-muted sm:text-xs">
              بررسی مسیر، عملکرد، وضعیت GPS و داده‌های دریافتی دستگاه
            </p>
          </div>
        </div>
        <Button variant="secondary" onClick={() => navigate('/panel/reports')}>
          <ArrowRight size={15} />
          بازگشت به گزارش‌ها
        </Button>
      </header>

      <DeviceReportPlayback isSiteAdmin={isSiteAdmin} />
    </div>
  );
}
