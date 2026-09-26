// داده‌های نمونه — بعداً از API جایگزین می‌شود

export const stats = {
  activeVehicles: 47,
  movingVehicles: 23,
  offlineVehicles: 8,
  activeAlerts: 5,
};

// داده حرکت خودروها در ۲۴ ساعت گذشته
export const movementData = [
  { hour: '۰۰', moving: 5,  stopped: 20 },
  { hour: '۰۲', moving: 3,  stopped: 22 },
  { hour: '۰۴', moving: 2,  stopped: 23 },
  { hour: '۰۶', moving: 8,  stopped: 17 },
  { hour: '۰۸', moving: 28, stopped: 5  },
  { hour: '۱۰', moving: 35, stopped: 3  },
  { hour: '۱۲', moving: 30, stopped: 8  },
  { hour: '۱۴', moving: 38, stopped: 4  },
  { hour: '۱۶', moving: 42, stopped: 2  },
  { hour: '۱۸', moving: 30, stopped: 10 },
  { hour: '۲۰', moving: 18, stopped: 15 },
  { hour: '۲۲', moving: 10, stopped: 20 },
];

export const recentAlerts = [
  { id: 1, type: 'speed',   vehicle: '۱۲ب۳۴۵۶۷', driver: 'علی رضایی',   message: 'سرعت غیرمجاز — ۱۲۰ km/h', time: '۵ دقیقه پیش',  severity: 'danger'  },
  { id: 2, type: 'offline', vehicle: '۴۵ج۶۷۸۹۰', driver: 'رضا محمدی',   message: 'قطع ارتباط دستگاه',       time: '۱۲ دقیقه پیش', severity: 'warning' },
  { id: 3, type: 'geofence',vehicle: '۷۸د۹۰۱۲۳', driver: 'حسن کریمی',   message: 'خروج از محدوده مجاز',    time: '۲۵ دقیقه پیش', severity: 'warning' },
  { id: 4, type: 'ignition',vehicle: '۱۲ب۳۴۵۶۷', driver: 'علی رضایی',   message: 'روشن شدن خودرو',         time: '۴۰ دقیقه پیش', severity: 'info'    },
  { id: 5, type: 'speed',   vehicle: '۹۰س۱۲۳۴۵', driver: 'محمد حسینی', message: 'سرعت غیرمجاز — ۱۳۵ km/h', time: '۱ ساعت پیش',   severity: 'danger'  },
];

export const recentTrips = [
  { id: 1024, vehicle: '۱۲ب۳۴۵۶۷', driver: 'علی رضایی',   start: '۱۰:۰۵', end: '۱۱:۴۰', distance: 82,  status: 'completed' },
  { id: 1025, vehicle: '۴۵ج۶۷۸۹۰', driver: 'رضا محمدی',   start: '۱۱:۲۰', end: '۱۲:۱۵', distance: 45,  status: 'completed' },
  { id: 1026, vehicle: '۷۸د۹۰۱۲۳', driver: 'حسن کریمی',   start: '۱۲:۰۰', end: '—',      distance: 23,  status: 'active'    },
  { id: 1027, vehicle: '۱۲ب۳۴۵۶۷', driver: 'علی رضایی',   start: '۱۳:۳۰', end: '۱۴:۲۰', distance: 67,  status: 'completed' },
  { id: 1028, vehicle: '۹۰س۱۲۳۴۵', driver: 'محمد حسینی', start: '۱۴:۰۰', end: '—',      distance: 12,  status: 'active'    },
];

export const movingVehicles = [
  { id: 1, plate: '۱۲ب۳۴۵۶۷', driver: 'علی رضایی',   speed: 78, status: 'moving' },
  { id: 2, plate: '۴۵ج۶۷۸۹۰', driver: 'رضا محمدی',   speed: 45, status: 'moving' },
  { id: 3, plate: '۷۸د۹۰۱۲۳', driver: 'حسن کریمی',   speed: 92, status: 'moving' },
  { id: 4, plate: '۹۰س۱۲۳۴۵', driver: 'محمد حسینی', speed: 60, status: 'moving' },
  { id: 5, plate: '۲۳ع۴۵۶۷۸', driver: 'حسین نوری',   speed: 0,  status: 'stopped' },
];
