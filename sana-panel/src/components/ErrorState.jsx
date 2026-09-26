import { AlertCircle, RefreshCw } from 'lucide-react';
import Button from './Button';

export default function ErrorState({ error, onRetry }) {
  const getMessage = () => {
    if (error?.response?.status === 403) {
      return 'شما به این بخش دسترسی ندارید';
    }
    if (error?.response?.status === 404) {
      return 'اطلاعات مورد نظر یافت نشد';
    }
    if (error?.response?.status === 500) {
      return 'خطای سرور. لطفاً دوباره تلاش کنید';
    }
    if (error?.code === 'ERR_NETWORK') {
      return 'ارتباط با سرور برقرار نشد';
    }
    return error?.response?.data?.detail || 'خطا در دریافت اطلاعات';
  };

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center gap-4">
      <div className="w-16 h-16 rounded-card bg-danger/10 flex items-center justify-center">
        <AlertCircle size={28} className="text-danger" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-text-primary mb-1">
          خطا در دریافت اطلاعات
        </h3>
        <p className="text-sm text-text-muted max-w-md">
          {getMessage()}
        </p>
      </div>
      {onRetry && (
        <Button variant="secondary" icon={RefreshCw} onClick={onRetry}>
          تلاش دوباره
        </Button>
      )}
    </div>
  );
}
