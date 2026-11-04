import { useAuth } from '../context/AuthContext';

export default function Reports() {
  const { isSiteAdmin, isPersonal, isBranchManager, user } = useAuth();

  const getTitle = () => {
    if (isSiteAdmin) return 'گزارش‌های سامانه';
    if (isPersonal) return 'گزارش‌های من';
    if (isBranchManager) return `گزارش‌های شعبه ${user?.branch?.name || ''}`;
    return 'گزارش‌های سازمان';
  };

  return (
    <div className="space-y-4">
      <header className="flex shrink-0 items-center gap-3">
        <div className="min-w-0">
          <h1 className="text-base font-semibold text-text-primary sm:text-lg">{getTitle()}</h1>
          <p className="mt-0.5 text-[11px] text-text-muted sm:text-xs">
            {isSiteAdmin
              ? 'گزارش‌های مدیریتی و تحلیلی سراسر سامانه'
              : isPersonal
                ? 'گزارش‌های خودروهای شما'
                : 'گزارش‌های عملکردی و تحلیلی ناوگان'}
          </p>
        </div>
      </header>

      {isSiteAdmin && <AdminGPSMonitor />}
    </div>
  );
}

