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

