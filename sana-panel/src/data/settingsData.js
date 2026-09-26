// داده‌های نمونه تنظیمات — بعداً از API جایگزین می‌شود

export const currentUser = {
  firstName: 'ایرج',
  lastName: 'احمدی',
  email: 'iraj@example.com',
  mobile: '09121234567',
  role: 'مدیر سازمان',
  avatar: null,
};

export const organization = {
  name: 'شرکت حمل و نقل نمونه',
  registrationNumber: '۱۲۳۴۵۶۷۸۹۰',
  economyCode: '۴۱۱۳۵۶۷۸۹۰۱۲',
  phone: '۰۲۱-۱۲۳۴۵۶۷۸',
  email: 'info@example.com',
  address: 'تهران، خیابان ولیعصر، پلاک ۱۲۳',
  website: 'www.example.com',
};

export const branchesList = [
  {
    id: 1,
    name: 'تهران',
    code: 'THR-01',
    manager: 'حسین رحیمی',
    phone: '۰۲۱-۸۸۸۸۱۱۱۱',
    vehiclesCount: 12,
    devicesCount: 14,
    driversCount: 8,
    status: 'active',
  },
  {
    id: 2,
    name: 'اصفهان',
    code: 'ISF-01',
    manager: 'مریم کاظمی',
    phone: '۰۳۱-۳۶۶۶۲۲۲۲',
    vehiclesCount: 8,
    devicesCount: 9,
    driversCount: 6,
    status: 'active',
  },
  {
    id: 3,
    name: 'شیراز',
    code: 'SHZ-01',
    manager: 'علی صادقی',
    phone: '۰۷۱-۳۷۷۷۳۳۳۳',
    vehiclesCount: 6,
    devicesCount: 7,
    driversCount: 4,
    status: 'active',
  },
  {
    id: 4,
    name: 'تبریز',
    code: 'TBZ-01',
    manager: null,
    phone: '۰۴۱-۳۵۵۵۴۴۴۴',
    vehiclesCount: 3,
    devicesCount: 3,
    driversCount: 2,
    status: 'inactive',
  },
];

export const usersList = [
  {
    id: 1,
    firstName: 'ایرج',
    lastName: 'احمدی',
    email: 'iraj@example.com',
    mobile: '09121234567',
    role: 'main_user',
    branch: null,
    status: 'active',
    lastLogin: '۱۴۰۴/۰۶/۲۱ — ۰۸:۱۵',
  },
  {
    id: 2,
    firstName: 'حسین',
    lastName: 'رحیمی',
    email: 'h.rahimi@example.com',
    mobile: '09122345678',
    role: 'branch_manager',
    branch: 'تهران',
    status: 'active',
    lastLogin: '۱۴۰۴/۰۶/۲۰ — ۱۷:۴۰',
  },
  {
    id: 3,
    firstName: 'مریم',
    lastName: 'کاظمی',
    email: 'm.kazemi@example.com',
    mobile: '09123456789',
    role: 'branch_manager',
    branch: 'اصفهان',
    status: 'active',
    lastLogin: '۱۴۰۴/۰۶/۲۱ — ۰۹:۳۰',
  },
  {
    id: 4,
    firstName: 'علی',
    lastName: 'صادقی',
    email: 'a.sadeghi@example.com',
    mobile: '09124567890',
    role: 'branch_manager',
    branch: 'شیراز',
    status: 'active',
    lastLogin: '۱۴۰۴/۰۶/۱۹ — ۱۴:۲۰',
  },
];

export const roleMap = {
  main_user:      { label: 'مدیر سازمان', variant: 'brand'   },
  branch_manager: { label: 'مدیر شعبه',   variant: 'info'    },
};

export const userStatusMap = {
  active:   { label: 'فعال',    variant: 'success' },
  inactive: { label: 'غیرفعال', variant: 'muted'   },
};

export const notificationSettings = [
  { id: 'sos',          label: 'هشدار اضطراری (SOS)',   description: 'وقتی دکمه اضطراری فشرده می‌شود',   email: true,  sms: true,  push: true  },
  { id: 'speed',        label: 'سرعت غیرمجاز',          description: 'هنگام عبور از حد مجاز سرعت',       email: false, sms: false, push: true  },
  { id: 'geofence',     label: 'خروج از محدوده',         description: 'خروج خودرو از محدوده‌های مجاز',   email: true,  sms: false, push: true  },
  { id: 'offline',      label: 'قطع ارتباط دستگاه',      description: 'وقتی دستگاه بیش از ۳۰ دقیقه آفلاین شود', email: true, sms: false, push: false },
  { id: 'maintenance',  label: 'یادآوری سرویس',         description: 'یادآوری سرویس‌های دوره‌ای',        email: true,  sms: false, push: false },
  { id: 'daily_report', label: 'گزارش روزانه',          description: 'ارسال خلاصه فعالیت‌های روز',       email: true,  sms: false, push: false },
];
