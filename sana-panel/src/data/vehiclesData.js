// داده‌های نمونه خودروها — بعداً از API جایگزین می‌شود

export const vehicleTypes = [
  { value: 'sedan',    label: 'سواری' },
  { value: 'truck',    label: 'کامیون' },
  { value: 'van',      label: 'وانت' },
  { value: 'motorcycle', label: 'موتور' },
  { value: 'bus',      label: 'اتوبوس' },
  { value: 'machinery', label: 'ماشین‌آلات' },
];

export const branches = [
  { value: 'tehran',  label: 'تهران' },
  { value: 'isfahan', label: 'اصفهان' },
  { value: 'shiraz',  label: 'شیراز' },
  { value: 'tabriz',  label: 'تبریز' },
  { value: 'unassigned', label: 'بدون شعبه' },
];

export const vehicles = [
  {
    id: 1,
    plate: '۱۲ب۳۴۵۶۷',
    type: 'truck',
    branch: 'tehran',
    device: { imei: '865123456789012', status: 'online' },
    driver: 'علی رضایی',
    lastSeen: '۲ دقیقه پیش',
  },
  {
    id: 2,
    plate: '۴۵ج۶۷۸۹۰',
    type: 'van',
    branch: 'tehran',
    device: { imei: '865123456789013', status: 'online' },
    driver: 'رضا محمدی',
    lastSeen: '۵ دقیقه پیش',
  },
  {
    id: 3,
    plate: '۷۸د۹۰۱۲۳',
    type: 'sedan',
    branch: 'isfahan',
    device: { imei: '865123456789014', status: 'offline' },
    driver: 'حسن کریمی',
    lastSeen: '۳ ساعت پیش',
  },
  {
    id: 4,
    plate: '۹۰س۱۲۳۴۵',
    type: 'truck',
    branch: 'isfahan',
    device: { imei: '865123456789015', status: 'online' },
    driver: 'محمد حسینی',
    lastSeen: '۱ دقیقه پیش',
  },
  {
    id: 5,
    plate: '۲۳ع۴۵۶۷۸',
    type: 'motorcycle',
    branch: 'shiraz',
    device: null,
    driver: null,
    lastSeen: '—',
  },
  {
    id: 6,
    plate: '۶۷ف۸۹۰۱۲',
    type: 'bus',
    branch: 'shiraz',
    device: { imei: '865123456789016', status: 'online' },
    driver: 'حسین نوری',
    lastSeen: '۱۰ دقیقه پیش',
  },
  {
    id: 7,
    plate: '۳۴ق۵۶۷۸۹',
    type: 'sedan',
    branch: 'tabriz',
    device: { imei: '865123456789017', status: 'faulty' },
    driver: 'امیر صادقی',
    lastSeen: '۲ روز پیش',
  },
  {
    id: 8,
    plate: '۸۹ل۰۱۲۳۴',
    type: 'van',
    branch: 'unassigned',
    device: null,
    driver: null,
    lastSeen: '—',
  },
];

export const deviceStatusMap = {
  online:  { label: 'آنلاین',     variant: 'success' },
  offline: { label: 'آفلاین',     variant: 'muted'   },
  faulty:  { label: 'خراب',       variant: 'danger'  },
  none:    { label: 'بدون دستگاه', variant: 'neutral' },
};
