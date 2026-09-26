import { useState, useMemo } from 'react';
import { FileBarChart, Calendar, X } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Button from '../components/Button';
import Select from '../components/Select';
import Modal from '../components/Modal';
import Badge from '../components/Badge';
import EmptyState from '../components/EmptyState';
import ReportCard from '../components/ReportCard';
import {
  reportTypes,
  reportCategories,
  dateRanges,
  sampleTripsReport,
} from '../data/reportsData';
import { useAuth } from '../context/AuthContext';

// گزارش‌های مخصوص ادمین
const adminReports = [
  {
    id: 'companies-overview',
    title: 'گزارش کلی شرکت‌ها',
    description: 'خلاصه عملکرد همه شرکت‌های مشتری سامانه',
    icon: 'truck',
    color: 'brand',
    format: ['PDF', 'Excel'],
    category: 'مدیریتی',
  },
  {
    id: 'revenue',
    title: 'گزارش درآمد و قرارداد',
    description: 'درآمد ماهانه، قراردادهای فعال و اشتراک‌ها',
    icon: 'fuel',
    color: 'success',
    format: ['PDF', 'Excel'],
    category: 'مالی',
  },
  {
    id: 'system-usage',
    title: 'گزارش استفاده از سامانه',
    description: 'آمار کاربران، دستگاه‌ها و ترافیک سراسری',
    icon: 'cpu',
    color: 'info',
    format: ['PDF'],
    category: 'فنی',
  },
];

// گزارش‌های مخصوص مشتری شخصی
const personalReports = [
  {
    id: 'my-trips',
    title: 'گزارش سفرهای من',
    description: 'لیست کامل سفرهای خودروهای من',
    icon: 'route',
    color: 'brand',
    format: ['PDF', 'Excel'],
    category: 'شخصی',
  },
  {
    id: 'my-vehicle-usage',
    title: 'استفاده از خودروی من',
    description: 'میزان استفاده و مسافت طي‌شده خودروهای من',
    icon: 'truck',
    color: 'info',
    format: ['PDF'],
    category: 'شخصی',
  },
];

export default function Reports() {
  const [category, setCategory] = useState('all');
  const [dateRange, setDateRange] = useState('last7');
  const [preview, setPreview] = useState(null);

  const { isSiteAdmin, isPersonal, isBranchManager, user } = useAuth();

  // لیست گزارش‌ها بر اساس نقش
  const availableReports = useMemo(() => {
    if (isSiteAdmin) {
      return [...adminReports, ...reportTypes];
    }
    if (isPersonal) {
      return personalReports;
    }
    return reportTypes;
  }, [isSiteAdmin, isPersonal]);

  // دسته‌بندی‌ها
  const availableCategories = useMemo(() => {
    if (isSiteAdmin) {
      return [
        { value: 'all', label: 'همه' },
        { value: 'مدیریتی', label: 'مدیریتی' },
        { value: 'مالی', label: 'مالی' },
        { value: 'فنی', label: 'فنی' },
        { value: 'عملیاتی', label: 'عملیاتی' },
        { value: 'عملکردی', label: 'عملکردی' },
        { value: 'امنیتی', label: 'امنیتی' },
      ];
    }
    if (isPersonal) {
      return [
        { value: 'all', label: 'همه' },
        { value: 'شخصی', label: 'شخصی' },
      ];
    }
    return reportCategories;
  }, [isSiteAdmin, isPersonal]);

  const filtered = useMemo(() => {
    if (category === 'all') return availableReports;
    return availableReports.filter((r) => r.category === category);
  }, [availableReports, category]);

  // عنوان
  const getTitle = () => {
    if (isSiteAdmin) return 'گزارش‌های سامانه';
    if (isPersonal) return 'گزارش‌های من';
    if (isBranchManager) return `گزارش‌های شعبه ${user?.branch?.name || ''}`;
    return 'گزارش‌های سازمان';
  };

  return (
    <div className="space-y-6">

      <PageHeader
        title={getTitle()}
        subtitle={
          isSiteAdmin
            ? 'گزارش‌های مدیریتی و تحلیلی سراسر سامانه'
            : isPersonal
              ? 'گزارش‌های خودروهای شما'
              : 'گزارش‌های عملکردی و تحلیلی ناوگان'
        }
      />

      <Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Select
            label="دسته‌بندی"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={availableCategories}
          />
          <Select
            label="بازه زمانی"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            options={dateRanges}
          />
        </div>
      </Card>

      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon={FileBarChart}
            title="گزارشی یافت نشد"
            description="هیچ گزارشی در این دسته‌بندی وجود ندارد."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              onPreview={setPreview}
            />
          ))}
        </div>
      )}

      <Modal
        open={!!preview}
        onClose={() => setPreview(null)}
        title={preview ? `پیش‌نمایش — ${preview.title}` : ''}
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPreview(null)}>بستن</Button>
            <Button>دانلود گزارش</Button>
          </>
        }
      >
        {preview && (
          <div className="space-y-4">

            <div className="flex flex-wrap items-center gap-3 p-3 bg-bg-base border border-border-base rounded-field">
              <Calendar size={16} className="text-text-muted" />
              <span className="text-sm text-text-secondary">
                بازه: {dateRanges.find((d) => d.value === dateRange)?.label}
              </span>
              <Badge variant="brand">{filtered.length} گزارش موجود</Badge>
            </div>

            {preview.id === 'trips' || preview.id === 'my-trips' ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-base">
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">#</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">خودرو</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">راننده</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">تاریخ</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">مسافت</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">مدت</th>
                      <th className="text-right py-3 px-3 text-xs font-medium text-text-muted">حداکثر سرعت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sampleTripsReport.map((trip) => (
                      <tr key={trip.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                        <td className="py-3 px-3 text-text-muted font-mono text-xs">#{trip.id}</td>
                        <td className="py-3 px-3 text-text-primary font-mono text-xs">{trip.vehicle}</td>
                        <td className="py-3 px-3 text-text-secondary text-xs">{trip.driver}</td>
                        <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.date}</td>
                        <td className="py-3 px-3 text-text-primary font-mono text-xs">{trip.distance} km</td>
                        <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.duration}</td>
                        <td className="py-3 px-3 text-text-secondary font-mono text-xs">{trip.maxSpeed} km/h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-12 text-center">
                <FileBarChart size={48} className="text-text-muted mx-auto mb-4" />
                <p className="text-sm text-text-secondary mb-1">
                  پیش‌نمایش این گزارش آماده نیست
                </p>
                <p className="text-xs text-text-muted">
                  این گزارش در فاز پیاده‌سازی تکمیل خواهد شد
                </p>
              </div>
            )}

          </div>
        )}
      </Modal>

    </div>
  );
}