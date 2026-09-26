// داده‌های نمونه گزارش‌ها — بعداً از API جایگزین می‌شود

export const reportTypes = [
  {
    id: 'trips',
    title: 'گزارش سفرها',
    description: 'لیست کامل سفرهای انجام‌شده به تفکیک خودرو و راننده',
    icon: 'route',
    color: 'brand',
    format: ['PDF', 'Excel', 'CSV'],
    category: 'عملیاتی',
  },
  {
    id: 'driver-performance',
    title: 'عملکرد رانندگان',
    description: 'تحلیل عملکرد، مسافت، سرعت میانگین و رفتار رانندگی',
    icon: 'user',
    color: 'success',
    format: ['PDF', 'Excel'],
    category: 'عملکردی',
  },
  {
    id: 'vehicle-usage',
    title: 'استفاده از خودروها',
    description: 'میزان استفاده، مسافت طي‌شده و زمان کارکرد هر خودرو',
    icon: 'truck',
    color: 'info',
    format: ['PDF', 'Excel', 'CSV'],
    category: 'عملیاتی',
  },
  {
    id: 'fuel',
    title: 'گزارش سوخت',
    description: 'مصرف سوخت، افت سوخت و تحلیل مصرف هر خودرو',
    icon: 'fuel',
    color: 'warning',
    format: ['PDF', 'Excel'],
    category: 'مالی',
  },
  {
    id: 'alerts',
    title: 'گزارش هشدارها',
    description: 'لیست کامل هشدارهای ثبت‌شده در بازه زمانی مشخص',
    icon: 'alert',
    color: 'danger',
    format: ['PDF', 'Excel', 'CSV'],
    category: 'امنیتی',
  },
  {
    id: 'device-status',
    title: 'وضعیت دستگاه‌ها',
    description: 'وضعیت اتصال، آخرین ارتباط و سلامت دستگاه‌ها',
    icon: 'cpu',
    color: 'muted',
    format: ['PDF', 'Excel'],
    category: 'فنی',
  },
  {
    id: 'maintenance',
    title: 'تعمیر و نگهداری',
    description: 'تاریخچه سرویس‌ها، تعمیرات و هزینه‌های نگهداری',
    icon: 'wrench',
    color: 'warning',
    format: ['PDF', 'Excel'],
    category: 'فنی',
  },
  {
    id: 'geofence',
    title: 'ورود و خروج محدوده‌ها',
    description: 'لیست ورود و خروج خودروها به محدوده‌های تعریف‌شده',
    icon: 'map',
    color: 'info',
    format: ['PDF', 'Excel'],
    category: 'امنیتی',
  },
];

export const reportCategories = [
  { value: 'all',        label: 'همه' },
  { value: 'عملیاتی',    label: 'عملیاتی' },
  { value: 'عملکردی',    label: 'عملکردی' },
  { value: 'مالی',       label: 'مالی' },
  { value: 'امنیتی',     label: 'امنیتی' },
  { value: 'فنی',        label: 'فنی' },
];

export const dateRanges = [
  { value: 'today',      label: 'امروز' },
  { value: 'yesterday',  label: 'دیروز' },
  { value: 'last7',      label: '۷ روز گذشته' },
  { value: 'last30',     label: '۳۰ روز گذشته' },
  { value: 'thisMonth',  label: 'این ماه' },
  { value: 'lastMonth',  label: 'ماه گذشته' },
  { value: 'custom',     label: 'بازه دلخواه' },
];

// داده نمونه برای پیش‌نمایش گزارش سفرها
export const sampleTripsReport = [
  { id: 1024, vehicle: '۱۲ب۳۴۵۶۷', driver: 'علی رضایی',   date: '۱۴۰۴/۰۶/۲۱', distance: 82,  duration: '۱:۳۵', maxSpeed: 98  },
  { id: 1025, vehicle: '۴۵ج۶۷۸۹۰', driver: 'رضا محمدی',   date: '۱۴۰۴/۰۶/۲۱', distance: 45,  duration: '۰:۵۵', maxSpeed: 76  },
  { id: 1026, vehicle: '۷۸د۹۰۱۲۳', driver: 'حسن کریمی',   date: '۱۴۰۴/۰۶/۲۱', distance: 23,  duration: '۰:۳۰', maxSpeed: 62  },
  { id: 1027, vehicle: '۱۲ب۳۴۵۶۷', driver: 'علی رضایی',   date: '۱۴۰۴/۰۶/۲۰', distance: 67,  duration: '۱:۱۰', maxSpeed: 88  },
  { id: 1028, vehicle: '۹۰س۱۲۳۴۵', driver: 'محمد حسینی', date: '۱۴۰۴/۰۶/۲۰', distance: 112, duration: '۲:۰۵', maxSpeed: 105 },
  { id: 1029, vehicle: '۶۷ف۸۹۰۱۲', driver: 'حسین نوری',   date: '۱۴۰۴/۰۶/۱۹', distance: 54,  duration: '۱:۰۰', maxSpeed: 82  },
  { id: 1030, vehicle: '۳۴ق۵۶۷۸۹', driver: 'امیر صادقی',  date: '۱۴۰۴/۰۶/۱۹', distance: 38,  duration: '۰:۴۵', maxSpeed: 71  },
];
