export default function LoadingSpinner({ message = 'در حال بارگذاری...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <div className="w-8 h-8 border-3 border-brand-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-text-muted">{message}</p>
    </div>
  );
}
