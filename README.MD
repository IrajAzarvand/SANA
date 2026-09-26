# SANA — سامانه اتوماسیون ناوگان ایران

## فاز ۱ — تحلیل و طراحی تئوری

### بخش 01: مدل مشتری، سازمان و ساختار دسترسی

**وضعیت:** FINAL

---

## 1. مدل کلی مشتریان

سانا یک پلتفرم مدیریت ناوگان است که به دو نوع مشتری اصلی سرویس ارائه می‌دهد:

1. مشتری شخصی
2. مشتری سازمانی

این دو نوع مشتری از نظر ساختار حساب و دسترسی از یکدیگر جدا هستند.

---

## 2. مشتری شخصی

هر شخص یک حساب شخصی در سامانه دارد.

یک شخص می‌تواند بیش از یک دستگاه خریداری کند و چند وسیله نقلیه داشته باشد.

مثال:

Personal Customer
│
├── Device 001 → Vehicle A
├── Device 002 → Vehicle B
└── Device 003 → Vehicle C

تمام دستگاه‌ها و خودروهای متعلق به شخص از طریق پنل شخصی او مدیریت می‌شوند.

در نسخه فعلی سیستم، مفهوم Driver برای مشتری شخصی کاربرد ندارد.

---

## 3. مشتری سازمانی

هر سازمان می‌تواند تعداد زیادی دستگاه از سانا خریداری کند.

پس از فروش، دستگاه‌ها متعلق به سازمان هستند.

مثال:

Organization X
│
├── Device 001
├── Device 002
├── Device 003
└── ...
└── Device 100

سازمان یک حساب اصلی برای مدیریت منابع خود خواهد داشت.

---

## 4. حساب اصلی سازمان

در زمان شروع همکاری، یک حساب اصلی در اختیار نماینده سازمان قرار می‌گیرد.

این حساب نقطه مدیریت اصلی سازمان است.

Organization Main User می‌تواند:

* تمام دستگاه‌های سازمان را مشاهده و مدیریت کند.
* تمام خودروهای سازمان را مشاهده و مدیریت کند.
* رانندگان سازمان را مدیریت کند.
* شعب ایجاد کند.
* کاربران شعبه را ایجاد کند.
* دستگاه‌ها و منابع را بین شعب مدیریت و جابه‌جا کند.
* امکانات مدیریتی مربوط به شعب را از سطح سازمان انجام دهد.

سازمان مجبور به ایجاد شعبه نیست و می‌تواند تمام منابع خود را مستقیماً از حساب اصلی مدیریت کند.

---

## 5. ساختار Branch

هر Organization می‌تواند در صورت نیاز Branch ایجاد کند.

ساختار Branch فقط یک سطح دارد.

مدل معتبر:

Organization
│
├── Branch Tehran
├── Branch Isfahan
└── Branch Shiraz

ساختار چندسطحی مجاز نیست.

مدل غیرمجاز:

Organization
└── Branch
└── Sub Branch
└── Sub Sub Branch

---

## 6. مدیر شعبه

هر Branch در نسخه فعلی دارای یک کاربر مدیریتی است:

Branch Manager

مدیر شعبه توسط Organization Main User ایجاد می‌شود.

مدیر شعبه فقط منابع اختصاص‌یافته به Branch خودش را مشاهده و مدیریت می‌کند.

منابع Branch می‌تواند شامل مواردی مانند:

* Devices
* Vehicles
* Drivers

باشد.

---

## 7. تفاوت سطح دسترسی Organization Main User و Branch Manager

Organization Main User دسترسی سراسری به کل Organization دارد.

مثال:

Organization Main User
│
├── Branch Tehran
├── Branch Isfahan
├── Branch Shiraz
└── Unassigned Resources

Organization Main User نیازی ندارد برای انجام عملیات مدیریتی وارد پنل یک Branch شود.

او باید بتواند عملیات مربوط به Branchها را از سطح پنل اصلی سازمان انجام دهد.

Branch Manager فقط به منابع Branch خودش دسترسی دارد.

Branch Manager نمی‌تواند:

* Branch جدید ایجاد کند.
* ساختار Organization را تغییر دهد.
* منابع خارج از Branch خودش را مدیریت کند.

---

## 8. تعداد کاربران اصلی سازمان

در نسخه فعلی، هر Organization فقط یک Organization Main User دارد.

سازمان می‌تواند تمام دستگاه‌های خود را با همین یک حساب مدیریت کند یا در صورت نیاز Branch ایجاد کرده و برای آنها Branch Manager بسازد.

امکان چند Organization Main User فعلاً وجود ندارد.

---

## 9. Roleها

در نسخه فعلی Roleهای اصلی عبارت‌اند از:

1. Organization Main User
2. Branch Manager

تعداد Roleها عمداً محدود نگه داشته شده است.

معماری سیستم باید قابلیت اضافه شدن Roleهای جدید در آینده را داشته باشد، اما فعلاً Roleهای بیشتری تعریف نمی‌شوند.

---

## 10. حساب شخصی و سازمانی

حساب شخصی و حساب سازمانی با یکدیگر ترکیب نمی‌شوند.

Personal Account:

Personal Account
│
├── Personal Vehicles
└── Personal Devices

Organization Account:

Organization
│
├── Main User
├── Branches
├── Vehicles
├── Devices
└── Drivers

در نسخه فعلی یک شخص از طریق یک حساب مشترک، همزمان Context شخصی و سازمانی نخواهد داشت.

---

## 11. مالکیت Device

پس از فروش Device، مالکیت آن متعلق به مشتری است.

این مشتری می‌تواند:

* شخص
* سازمان

باشد.

سانا مالک دائمی Device نیست.

---

## 12. سرویس و مالکیت دستگاه

مالکیت Device از سرویس نرم‌افزاری سانا جدا است.

مشتری می‌تواند پس از پایان قرارداد، در صورت تمایل با شرکت دیگری قرارداد ببندد و Deviceهای متعلق به خودش را روی سرور شرکت دیگری تنظیم کند.

بنابراین در طراحی آینده باید مفاهیم زیر از یکدیگر جدا باشند:

* Device Ownership
* Device Connectivity
* Service / Subscription

---

## 13. Device بدون Vehicle

Device می‌تواند در سیستم وجود داشته باشد ولی هنوز روی هیچ Vehicle نصب نشده باشد.

مثال:

Company
│
├── Device 001 → Vehicle A
├── Device 002 → Vehicle B
├── Device 003 → Uninstalled
└── Device 004 → Uninstalled

این وضعیت معتبر است.

---

## 14. Vehicle بدون Device

Vehicle نیز می‌تواند در سیستم وجود داشته باشد ولی فعلاً Device نداشته باشد.

مثال:

Vehicles
│
├── Truck 01 → Device 001
├── Truck 02 → Device 002
└── Van 01 → No Device

این وضعیت نیز معتبر است.

---

## 15. رابطه Device و Vehicle

هر Vehicle فقط یک Device فعال دارد.

اما یک Device در طول زمان می‌تواند روی Vehicleهای مختلف نصب شود.

مثال:

Device 001
│
├── Vehicle A
│
├── Vehicle B
│
└── Vehicle C

تاریخچه این Assignment باید نگهداری شود.

---

## 16. انتقال Device

Deviceها قابل انتقال هستند.

انتقال می‌تواند شامل موارد زیر باشد:

* انتقال بین Vehicleها
* انتقال بین Branchها
* خارج کردن Device از Vehicle
* اختصاص مجدد Device به Vehicle دیگر

تمام انتقال‌های مهم باید در تاریخچه سیستم ثبت شوند.

---

## 17. ساختار مفهومی فعلی

مدل کلی فعلی سانا:

SANA
│
├── Personal Customers
│   ├── Personal Account
│   ├── Vehicles
│   └── Devices
│
└── Organizations
│
├── Main User
│
├── Vehicles
├── Devices
├── Drivers
│
└── Branches
├── Branch Manager
├── Vehicles
├── Devices
└── Drivers

---

## تصمیمات قطعی این بخش

[✓] سانا به مشتری شخصی و سازمانی سرویس می‌دهد.

[✓] هر شخص یک حساب شخصی دارد.

[✓] شخص می‌تواند چند Device داشته باشد.

[✓] شخص می‌تواند چند Vehicle داشته باشد.

[✓] Organization می‌تواند تعداد زیادی Device داشته باشد.

[✓] Device پس از فروش متعلق به مشتری است.

[✓] هر Organization در نسخه فعلی یک Main User دارد.

[✓] Organization می‌تواند بدون Branch فعالیت کند.

[✓] Organization می‌تواند Branch ایجاد کند.

[✓] Branch فقط یک سطح زیر Organization دارد.

[✓] هر Branch یک Branch Manager دارد.

[✓] Branch Manager توسط Main User ایجاد می‌شود.

[✓] Branch Manager فقط منابع Branch خودش را مدیریت می‌کند.

[✓] Main User به کل Organization دسترسی دارد.

[✓] Main User برای مدیریت Branchها نیازی به ورود به پنل Branch ندارد.

[✓] Roleهای اصلی فعلاً Main User و Branch Manager هستند.

[✓] معماری Role باید قابل توسعه باشد.

[✓] حساب شخصی و سازمانی از یکدیگر جدا هستند.

[✓] Device می‌تواند بدون Vehicle وجود داشته باشد.

[✓] Vehicle می‌تواند بدون Device وجود داشته باشد.

[✓] هر Vehicle فقط یک Device فعال دارد.

[✓] Device می‌تواند در طول زمان روی Vehicleهای مختلف نصب شود.

[✓] انتقال Device باید دارای تاریخچه باشد.

[✓] مالکیت Device از سرویس و Connectivity جدا است.

[✓] مشتری پس از پایان قرارداد می‌تواند Device خود را روی زیرساخت شرکت دیگری استفاده کند.

---

## وضعیت پیشرفت فاز ۱

### تکمیل شده:

* مدل کلی مشتری
* Personal Customer
* Organization
* Organization Main User
* Branch
* Branch Manager
* ساختار یک‌سطحی Branch
* Roleهای اولیه
* مالکیت Device
* جداسازی Ownership و Service
* Device بدون Vehicle
* Vehicle بدون Device
* رابطه Device ↔ Vehicle
* انتقال Device

### بخش‌های بعدی:

* Driver Management
* Device Management
* Vehicle Management
* Subscription / Contract
* GPS Connectivity
* Tracking
* Location History
* Trips
* Alerts
* Geofencing
* Reports
* Notifications
* Users & Permissions
* Dashboard
* System Architecture
* Database Architecture
* API Architecture
* Security
* Logging & Audit
* Scalability
* Deployment
* AI-ready Architecture




========================================================



# SANA — سامانه اتوماسیون ناوگان ایران

## فاز ۱ — تحلیل و طراحی تئوری

### بخش 02: مدل راننده و تخصیص راننده به خودرو

**وضعیت:** FINAL

---

## 1. موجودیت راننده

راننده یک Entity مستقل در سیستم است و مستقیماً به Vehicle وابسته نیست.

راننده فقط در ساختار مشتریان سازمانی مورد استفاده قرار می‌گیرد.

مشتری شخصی فعلاً نیازی به مفهوم Driver ندارد.

---

## 2. مالکیت راننده

هر Driver متعلق به یک Organization است و در حالت عادی به یک Branch اختصاص دارد.

مدیر سازمان به تمام رانندگان سازمان دسترسی دارد.

مدیر شعبه فقط رانندگان شعبه خودش را مشاهده و مدیریت می‌کند.

---

## 3. انتقال راننده بین شعب

در حالت عادی راننده به یک شعبه اختصاص دارد.

سیستم امکان انتقال راننده بین شعب را خواهد داشت، هرچند این عملیات جزو عملیات معمول سیستم محسوب نمی‌شود.

تمام انتقال‌های بین شعب باید دارای تاریخچه باشند.

نمونه:

Tehran → 2026/01/01 تا 2026/07/31

Isfahan → 2026/08/01 تا ...

---

## 4. راننده بدون خودرو

راننده می‌تواند در سیستم وجود داشته باشد ولی در حال حاضر به هیچ خودرویی اختصاص داده نشده باشد.

مثال:

Driver: Ali
Vehicle: None

---

## 5. رابطه Driver و Vehicle

رابطه Driver و Vehicle چندبه‌چند است.

* یک راننده می‌تواند در طول زمان با چند خودرو کار کند.
* یک خودرو می‌تواند در طول زمان چند راننده داشته باشد.

این رابطه باید به‌صورت تاریخی و زمان‌دار ذخیره شود.

---

## 6. Assignment راننده به خودرو

هر Assignment حداقل دارای مفاهیم زیر خواهد بود:

* Driver
* Vehicle
* Start Date/Time
* End Date/Time

End Date/Time برای Assignment فعال می‌تواند خالی باشد.

---

## 7. راننده فعال خودرو

یک Vehicle می‌تواند در طول روز چند راننده داشته باشد، اما Assignmentهای رانندگان نباید از نظر زمانی با یکدیگر تداخل داشته باشند.

مثال معتبر:

08:00 → 16:00 : Ali

16:00 → 00:00 : Reza

مثال نامعتبر:

08:00 → 16:00 : Ali

12:00 → 18:00 : Reza

زیرا دو راننده در یک بازه زمانی روی یک Vehicle فعال هستند.

---

## 8. Login راننده

Driver در نسخه فعلی سیستم User Account ندارد.

راننده صرفاً یک رکورد اطلاعاتی است.

ایجاد و مدیریت Driver توسط موارد زیر انجام می‌شود:

* Organization Main User
* Branch Manager

---

## 9. اطلاعات راننده

اطلاعات پایه مورد نیاز:

### Identity

* First Name
* Last Name
* National ID

### Contact

* Mobile

### Employment

* Personnel Code
* Position

### Driving

* License Number
* License Type
* License Expiry Date

---

## 10. ارتباط Driver با Trip

در زمان ایجاد یا پردازش Trip، سیستم باید بتواند بر اساس Assignment تاریخی Driver ↔ Vehicle تشخیص دهد که چه راننده‌ای در زمان انجام سفر مسئول Vehicle بوده است.

نمونه:

Trip #1024

* Vehicle: Truck 01
* Driver: Ali
* Start: 10:05
* End: 11:40
* Distance: 82 km

این اطلاعات در آینده برای گزارش‌های عملکرد رانندگان و تحلیل رفتار رانندگی قابل استفاده خواهد بود.

---

## تصمیمات قطعی این بخش

[✓] Driver موجودیت مستقل است.

[✓] Driver فقط برای سازمان‌ها استفاده می‌شود.

[✓] هر Driver متعلق به یک Organization است.

[✓] هر Driver در حالت عادی متعلق به یک Branch است.

[✓] Driver می‌تواند بدون Vehicle باشد.

[✓] یک Driver می‌تواند با چند Vehicle کار کند.

[✓] یک Vehicle می‌تواند چند Driver داشته باشد.

[✓] رابطه Driver و Vehicle تاریخی و زمان‌دار است.

[✓] Assignmentهای فعال یک Vehicle نباید از نظر زمانی با هم تداخل داشته باشند.

[✓] انتقال Driver بین Branchها امکان‌پذیر است.

[✓] تاریخچه انتقال Branch ذخیره می‌شود.

[✓] Driver فعلاً Login ندارد.

[✓] اطلاعات پایه Driver شامل مشخصات هویتی، تماس، استخدامی و گواهینامه است.

[✓] سیستم باید بتواند Driver مربوط به هر Trip را از روی تاریخچه Assignment تشخیص دهد.

---

## وضعیت پیشرفت فاز ۱

### تکمیل شده:

* مدل مشتری شخصی
* مدل مشتری سازمانی
* ساختار Organization
* ساختار Branch
* مدل User اولیه
* Roleهای اولیه
* مالکیت Device
* انتقال Device
* Device بدون Vehicle
* Vehicle بدون Device
* رابطه Device ↔ Vehicle
* مدل Driver
* رابطه Driver ↔ Vehicle
* رابطه Driver ↔ Branch
* تاریخچه Assignment

### بخش بعدی پیشنهادی:

**بخش 03 — Device Management و چرخه حیات دستگاه**

موضوعات:

* ثبت دستگاه
* Serial Number
* IMEI
* سیم‌کارت
* وضعیت دستگاه
* فعال/غیرفعال بودن
* مالکیت
* تحویل به مشتری
* نصب
* تعویض
* انتقال
* مفقودی
* خرابی
* تعمیر
* بازگشت
* تاریخچه کامل دستگاه
* وضعیت سرویس و قرارداد
=====================================================
# SANA — سامانه اتوماسیون ناوگان ایران

## فاز ۱ — تحلیل و طراحی تئوری

# بخش 03 — Device Management

**وضعیت: FINAL**

---

# 1. مفهوم Device

Device یکی از موجودیت‌های اصلی سانا است.

Device همان GPS Tracker فیزیکی است که توسط سانا به مشتری فروخته می‌شود.

مالکیت Device پس از فروش متعلق به مشتری خواهد بود.

مشتری می‌تواند:

* شخص
* سازمان

باشد.

---

# 2. شناسه Device

هر Device دارای یک `id` داخلی در دیتابیس است.

اما شناسه فنی و اصلی Device در سطح Domain، **IMEI** است.

ساختار مفهومی:

```text
Device
├── Internal ID
└── IMEI
```

IMEI باید در کل سیستم Unique باشد.

---

# 3. Device Model

سانا باید بتواند از برندها و مدل‌های مختلف GPS Tracker پشتیبانی کند.

بنابراین `Device Model` یک Entity مستقل خواهد بود.

هر Device به یک Device Model متصل می‌شود.

مثال:

```text
Device 001
   ↓
Model A
```

Device Model می‌تواند در آینده اطلاعاتی مانند موارد زیر داشته باشد:

* Manufacturer
* Model Name
* Model Code
* Communication Protocol
* Supported Features
* Firmware Information

---

# 4. Multi-Protocol Architecture

سانا باید از ابتدا به‌صورت **Multi-Protocol Tracking Platform** طراحی شود.

دستگاه‌های مختلف ممکن است:

* پروتکل متفاوت داشته باشند.
* ساختار Packet متفاوت داشته باشند.
* روش Encoding متفاوت داشته باشند.
* اطلاعات متفاوتی ارسال کنند.

بنابراین اضافه کردن یک Device Model جدید نباید نیازمند تغییر در هسته اصلی سیستم باشد.

مدل مفهومی:

```text
Device Model A
      ↓
Protocol Handler A

Device Model B
      ↓
Protocol Handler B

Device Model C
      ↓
Protocol Handler C
```

در آینده برای اضافه کردن دستگاه جدید، Handler/Parser مربوط به آن اضافه می‌شود.

---

# 5. ورود Device به سانا

دستگاه‌هایی که هنوز فروخته نشده‌اند در نسخه فعلی وارد سیستم عملیاتی سانا نمی‌شوند.

یعنی سانا در این مرحله Inventory Management برای دستگاه‌های انبار را انجام نمی‌دهد.

Device زمانی وارد سیستم می‌شود که به مشتری فروخته شده باشد.

چرخه اولیه:

```text
Device Sold
     ↓
Register Device
     ↓
Assign Ownership
```

---

# 6. SIM Card

SIM Card یک Entity مستقل از Device است.

SIM متعلق به مشتری است و توسط مشتری تهیه می‌شود.

سانا مسئول تهیه و تأمین SIM نیست.

بنابراین:

```text
Customer
   │
   ├── Device
   └── SIM
```

سانا فقط Device را تنظیم کرده و به مشتری تحویل می‌دهد.

---

# 7. رابطه SIM و Device

هر Device در هر لحظه فقط **یک SIM فعال** دارد.

اما SIM یک Entity مستقل است و می‌تواند در طول زمان از یک Device جدا شده و روی Device دیگری قرار گیرد.

مثال:

```text
SIM 001
   │
   ├── Device 001
   │
   └── بعداً Device 025
```

این انتقال باید دارای تاریخچه باشد.

بنابراین رابطه Device و SIM صرفاً یک Foreign Key ساده نخواهد بود و تاریخچه Assignment آن اهمیت دارد.

---

# 8. اطلاعات SIM

اطلاعات مورد نیاز SIM فعلاً شامل:

* SIM ID
* Phone Number

است.

اپراتور SIM در نسخه فعلی ثبت نمی‌شود.

شماره SIM به دلیل امکان ارسال SMS Command به Device باید در سیستم ذخیره شود.

---

# 9. ارتباط Device با Server

Device برای ارسال اطلاعات به سانا از طریق شبکه موبایل و اینترنت به Server متصل می‌شود.

سرور سانا یک Address و Port مشخص برای دریافت اطلاعات خواهد داشت.

مدل مفهومی:

```text
Device
   ↓
Mobile Network
   ↓
Internet
   ↓
SANA Server
Address + Port
```

آدرس و Port مربوط به سرور در تنظیمات Device قرار می‌گیرد.

---

# 10. ارتباط یک‌طرفه

ارتباط اصلی Device و Server یک‌طرفه است.

```text
Device ─────────→ SANA
```

Device اطلاعات خود را به Server ارسال می‌کند.

سانا در حالت عادی Command را از طریق Connection به Device ارسال نمی‌کند.

---

# 11. ارسال Command به Device

در صورت نیاز به ارسال دستور به Device، از SMS استفاده خواهد شد.

```text
SANA Operator
      ↓
SMS
      ↓
SIM
      ↓
Device
```

ارسال Command به‌صورت دستی انجام می‌شود.

این موضوع فعلاً به‌عنوان یک سیستم Command مرکزی در معماری طراحی نمی‌شود.

---

# 12. قطع سرویس و تغییر Server

Device متعلق به مشتری است و سانا مالک آن نیست.

پس از پایان قرارداد، مشتری می‌تواند Device را برای استفاده در Server شرکت دیگری تنظیم کند.

پس از Disconnect شدن Device:

```text
Device
   ↓
Other Company Server
```

سانا دیگر مسئولیتی در قبال:

* Server جدید
* Connectivity جدید
* عملکرد Device روی Server جدید

ندارد.

اما سابقه استفاده Device در سانا حفظ خواهد شد.

---

# 13. Management Status

وضعیت مدیریتی Device از وضعیت لحظه‌ای Device جدا است.

Statusهای فعلی:

```text
Sold
Installed
Active
Faulty
Lost
Stolen
Disconnected
```

این فهرست در آینده قابل توسعه است.

---

# 14. Live Device State

وضعیت لحظه‌ای Device در یک مفهوم جداگانه مدیریت خواهد شد.

نمونه‌های آینده:

```text
Online
Offline
Moving
Stopped
Ignition ON
Ignition OFF
```

این موارد نباید با Management Status ترکیب شوند.

مثلاً:

```text
Management Status = Active
Live State = Moving
```

یا:

```text
Management Status = Active
Live State = Offline
```

---

# 15. Device History

تاریخچه کامل Device باید حفظ شود.

هدف این است که بتوان تمام اتفاقات مهم زندگی Device را بازسازی کرد.

مثال:

```text
Sold
 ↓
Assigned to Customer
 ↓
Assigned to Branch
 ↓
Installed on Vehicle A
 ↓
Removed from Vehicle A
 ↓
Installed on Vehicle B
 ↓
Faulty
 ↓
Replaced
 ↓
Disconnected
```

اطلاعات تاریخی نباید با تغییر وضعیت‌ها حذف شوند.

---

# 16. Device Replacement

سانا تعمیرگاه نیست.

در صورت خرابی Device، فرآیند اصلی:

```text
Device Faulty
      ↓
 بررسی علت
      ↓
 ┌───────────────┐
 │               │
User Fault    Device Fault
 │               │
 ↓               ↓
هزینه          Replacement
تعویض          بدون هزینه
```

اگر خرابی ناشی از کاربر باشد، هزینه جایگزینی می‌تواند از مشتری دریافت شود.

اگر خرابی مربوط به خود Device باشد، Device بدون هزینه برای مشتری جایگزین خواهد شد.

جزئیات فرآیند Replacement در طراحی بعدی مشخص می‌شود.

---

# 17. Device Lost

اگر Device گم شود:

```text
Active
   ↓
Lost
```

در صورت پیدا شدن:

```text
Lost
 ↓
Recovered
 ↓
Active
```

و تمام این تغییرات در History ثبت می‌شوند.

---

# 18. Device Stolen

`Stolen` از `Lost` جدا است.

```text
Lost
```

یعنی دستگاه مفقود شده است.

```text
Stolen
```

یعنی مشتری اعلام کرده دستگاه سرقت شده است.

این تفکیک برای موارد زیر مفید است:

* گزارش‌گیری
* پشتیبانی
* پیگیری خسارت
* مسائل قراردادی
* آمار دستگاه‌های Lost و Stolen
* تاریخچه Device

در صورت پیدا شدن، Device می‌تواند دوباره وارد چرخه استفاده شود.

---

# 19. Device Disconnected

وقتی مشتری دیگر از سرویس سانا استفاده نکند:

```text
Active
   ↓
Disconnected
```

تاریخچه Device همچنان در سانا باقی می‌ماند.

اگر مشتری در آینده دوباره از سرویس سانا استفاده کند:

```text
Disconnected
     ↓
Reactivated
     ↓
Active
```

---

# 20. Raw Device Data

داده خام Device به‌صورت دائمی ذخیره نمی‌شود.

Raw Data صرفاً در مرحله‌ای که برای شناسایی و تحلیل Protocol لازم است نگهداری می‌شود.

کاربرد Raw Data:

* شناخت Protocol
* شناخت ساختار Packet
* شناسایی فیلدهای جدید
* Debug کردن Parser
* بررسی Device Model جدید
* بررسی Packetهای ناشناخته

پس از اینکه ساختار داده کاملاً شناخته و به داده استاندارد سانا تبدیل شد، نیازی به نگهداری دائمی Raw Data وجود ندارد.

---

# 21. Unknown / Unparsed Data

اگر Device داده‌ای ارسال کند که Parser فعلی آن را نمی‌شناسد، آن Raw Data باید موقتاً ذخیره شود تا امکان تحلیل آن وجود داشته باشد.

فرآیند:

```text
Raw Packet
    ↓
Parser
    ↓
شناخته شده؟
   / \
 Yes  No
  ↓    ↓
Store  Temporary Raw Storage
       ↓
       Analyze
       ↓
       Update Parser
```

پس از مشخص شدن ساختار Packet، اطلاعات قابل استفاده باید در ساختار استاندارد سانا ذخیره شود.

---

# 22. Standardized Data

هدف معماری این است که بعد از Parse شدن اطلاعات، داده‌ها به یک ساختار استاندارد سانا تبدیل شوند.

مثلاً:

```text
Device Protocol
       ↓
Protocol Parser
       ↓
Normalized Data
       ↓
SANA Tracking System
```

در نتیجه سیستم‌های بالادستی نباید مجبور باشند تفاوت Protocolهای مختلف را بشناسند.

---

# 23. GPS History

سانا باید تاریخچه اطلاعات دریافتی از Device را نگهداری کند.

این اطلاعات برای مواردی مانند:

* مشاهده مسیر
* گزارش‌گیری
* بازسازی مسیر
* بررسی عملکرد خودرو
* بررسی رفتار رانندگی
* تحلیل ناوگان
* گزارش‌های تاریخی

ضروری است.

نمونه:

```text
Device 001

10:00 → Location A
10:01 → Location B
10:02 → Location C
10:03 → Location D
...
```

این داده‌ها باید به‌صورت دائمی در سیستم ذخیره شوند.

---

# 24. اصل تفکیک داده‌ها

در معماری سانا باید حداقل چهار مفهوم از هم جدا باشند:

```text
Device Identity
       +
Management Status
       +
Live State
       +
Historical Tracking Data
```

همچنین:

```text
Device
   ≠
SIM
```

و:

```text
Device
   ≠
Vehicle
```

و:

```text
Device Ownership
   ≠
SANA Service
```

---

# تصمیمات قطعی بخش Device Management

[✓] IMEI شناسه اصلی فنی Device است.

[✓] Device دارای Internal ID نیز هست.

[✓] IMEI باید Unique باشد.

[✓] Device Model به‌عنوان Entity مستقل وجود دارد.

[✓] سانا Multi-Protocol خواهد بود.

[✓] اضافه کردن Protocol جدید نباید نیازمند تغییر هسته سیستم باشد.

[✓] Device قبل از فروش وارد سیستم عملیاتی نمی‌شود.

[✓] Device هنگام فروش ثبت می‌شود.

[✓] SIM یک Entity مستقل است.

[✓] SIM توسط مشتری تهیه می‌شود.

[✓] سانا مسئول تأمین SIM نیست.

[✓] هر Device در هر لحظه فقط یک SIM دارد.

[✓] یک SIM می‌تواند در طول زمان روی Deviceهای مختلف قرار گیرد.

[✓] تاریخچه SIM ↔ Device نگهداری می‌شود.

[✓] شماره SIM ذخیره می‌شود.

[✓] Operator فعلاً ذخیره نمی‌شود.

[✓] Device از طریق Address + Port مشخص به Server متصل می‌شود.

[✓] ارتباط اصلی Device → Server یک‌طرفه است.

[✓] Commandها در صورت نیاز از طریق SMS ارسال می‌شوند.

[✓] پس از پایان قرارداد، مشتری می‌تواند Device را روی Server دیگری تنظیم کند.

[✓] سانا پس از Disconnect مسئول Server جدید نیست.

[✓] تاریخچه قبلی Device در سانا حفظ می‌شود.

[✓] Management Status و Live State جدا هستند.

[✓] Statusهای فعلی شامل Sold، Installed، Active، Faulty، Lost، Stolen و Disconnected هستند.

[✓] Statusها در آینده قابل توسعه هستند.

[✓] Device History دائمی است.

[✓] Device Faulty می‌تواند منجر به Replacement شود.

[✓] خرابی ناشی از کاربر می‌تواند مشمول هزینه Replacement باشد.

[✓] خرابی خود Device با Replacement بدون هزینه همراه است.

[✓] Lost و Stolen جدا هستند.

[✓] Lost/Stolen می‌توانند دوباره وارد چرخه استفاده شوند.

[✓] Disconnected به معنی عدم استفاده از سرویس سانا است.

[✓] تاریخچه پس از Disconnected حفظ می‌شود.

[✓] Raw Data فقط تا زمان تحلیل و Parse شدن نگهداری می‌شود.

[✓] Unknown Packetها به‌صورت موقت ذخیره می‌شوند.

[✓] داده Parse شده به ساختار استاندارد سانا تبدیل می‌شود.

[✓] GPS/Tracking History دائمی ذخیره می‌شود.

---

# وضعیت بخش 03

**Device Management — COMPLETED / FINAL**

### تکمیل شد:

* Device Identity
* IMEI
* Device Model
* Multi-Protocol Architecture
* Device Registration
* SIM Management
* SIM ↔ Device Assignment
* Server Connectivity
* Communication Model
* SMS Commands
* Disconnect / Reactivation
* Management Status
* Live State Separation
* Device History
* Device Fault
* Device Replacement
* Lost Device
* Stolen Device
* Raw Data Strategy
* Protocol Parsing
* Normalized Data
* GPS History

---

## بخش بعدی

### بخش 04 — Vehicle Management

در بخش بعدی خود **Vehicle** را از صفر طراحی می‌کنیم:

* مشخصات خودرو
* نوع وسیله
* پلاک
* VIN
* برند و مدل
* سال ساخت
* رنگ
* اطلاعات فنی
* مالکیت
* شعبه
* Device
* راننده
* وضعیت خودرو
* خودرو فعال/غیرفعال
* فروش یا خروج از ناوگان
* تاریخچه خودرو
* انتقال خودرو بین شعب
* تعویض پلاک
* خودرو بدون Device
* و ارتباط Vehicle با Tracking

**و نکته مهم:** از اینجا به بعد هر چیزی که درباره Vehicle تصمیم بگیریم، باید با تصمیم‌های قطعی بخش‌های ۱، ۲ و ۳ سازگار باشد.
============================================================================

# SANA — سامانه اتوماسیون ناوگان ایران

## فاز ۱ — تحلیل و طراحی تئوری

# بخش 04 — Vehicle Management

**وضعیت: FINAL**

---

## 1. مفهوم Vehicle

Vehicle یک موجودیت مستقل در سانا است که نماینده وسیله نقلیه یا وسیله عملیاتی مشتری است.

سانا فقط مخصوص خودرو سواری نیست و می‌تواند برای انواع وسایل مورد استفاده قرار گیرد.

نمونه:

```text
Car
Truck
Motorcycle
Bus
Van
Pickup
...
```

---

## 2. مالکیت Vehicle

هر Vehicle متعلق به همان Account است که Vehicle در آن ایجاد شده است.

برای حساب شخصی:

```text
Personal Customer
      ↓
Vehicle
```

برای سازمان:

```text
Organization
      ↓
Vehicle
```

در نسخه فعلی Entity مستقل برای مالکیت Vehicle ایجاد نمی‌شود.

---

## 3. Vehicle ID

هر Vehicle دارای `Internal ID` در دیتابیس است.

شناسه عملیاتی و نمایشی اصلی Vehicle، **Plate Number** است.

---

## 4. Plate Number

پلاک به‌صورت `String` ذخیره می‌شود.

ساختار پلاک در نسخه اول پیچیده و چندفیلدی نمی‌شود.

نمونه:

```text
12ب34567
```

---

## 5. یکتایی پلاک

هر پلاک در هر لحظه فقط می‌تواند روی یک Vehicle قرار داشته باشد.

اما یک پلاک می‌تواند در طول سال‌های مختلف به Vehicleهای مختلف اختصاص داده شود.

مثال:

```text
Plate 12ب34567

Vehicle A
1402 → 1405

Vehicle B
1407 → ...
```

بنابراین پلاک در طول تاریخ سیستم الزاماً Unique نیست، اما در هر لحظه فقط یک Vehicle می‌تواند آن را داشته باشد.

---

## 6. Plate History

تغییر پلاک باید دارای History باشد.

نمونه:

```text
Vehicle 01

2026/01/01
Plate = 12ب34567

2026/08/01
Plate = 45ج67890
```

در پنل، پلاک فعلی نمایش داده می‌شود و پلاک‌های قبلی در History قابل مشاهده هستند.

---

## 7. Vehicle Type

Vehicle Type توسط خود Customer تعریف می‌شود.

این قابلیت هم برای Organization و هم برای Personal Account وجود دارد.

مثلاً:

```text
Vehicle Types

سواری
کامیون
وانت
موتور
اتوبوس
ماشین‌آلات
```

Customer هنگام ایجاد Vehicle، نوع وسیله را انتخاب می‌کند.

در نسخه فعلی Vehicle Type توسط سیستم به یک لیست ثابت محدود نمی‌شود.

---

## 8. اطلاعات اضافی Vehicle

در نسخه فعلی اطلاعات فنی و ظاهری اضافی برای Vehicle ذخیره نمی‌شود.

مواردی مانند:

* رنگ
* برند
* مدل
* سال ساخت
* ظرفیت
* تعداد محور
* مشخصات فنی

فعلاً جزو مدل Vehicle نیستند.

در آینده در صورت نیاز قابل اضافه شدن هستند.

---

## 9. Vehicle و Branch

Vehicle در Organization می‌تواند:

* به یک Branch اختصاص داشته باشد.
* یا فعلاً به هیچ Branchی اختصاص نداشته باشد.

نمونه:

```text
Organization
│
├── Branch Tehran
│   ├── Vehicle 01
│   └── Vehicle 02
│
├── Branch Tabriz
│   └── Vehicle 03
│
└── Unassigned
    ├── Vehicle 04
    └── Vehicle 05
```

---

## 10. انتقال Vehicle بین Branchها

Vehicle می‌تواند بین Branchهای یک Organization منتقل شود.

این عملیات فقط توسط **Main User / مدیر اصلی سازمان** انجام می‌شود.

مثال:

```text
Branch Tehran
      ↓
Transfer
      ↓
Branch Tabriz
```

همچنین مدیر اصلی می‌تواند Vehicle را از یک Branch خارج کرده و به حالت Unassigned منتقل کند.

تمام انتقال‌ها در History ثبت می‌شوند.

---

## 11. Vehicle بدون Branch

Vehicle می‌تواند بدون Branch در Organization وجود داشته باشد.

این حالت برای خودروهای تازه واردشده یا خودروهایی که هنوز به شعبه‌ای اختصاص داده نشده‌اند مجاز است.

---

## 12. Vehicle بدون Device

Vehicle می‌تواند بدون Device در سیستم وجود داشته باشد.

مثال:

```text
Vehicle 01
Device = None
```

در این حالت:

* Vehicle در سیستم وجود دارد.
* قابل مدیریت است.
* Driver می‌تواند به آن اختصاص پیدا کند.
* اما Tracking ندارد.
* موقعیت لحظه‌ای ندارد.
* GPS History ندارد.

پس وجود Vehicle وابسته به وجود Device نیست.

---

## 13. Device Assignment

هر Vehicle در هر لحظه حداکثر یک Device فعال دارد.

Device می‌تواند از یک Vehicle جدا شده و Device دیگری روی Vehicle نصب شود.

مثال:

```text
Vehicle 01

Device 001
   ↓
Removed

Device 002
   ↓
Installed
```

Deviceهای قبلی حذف نمی‌شوند و History آنها حفظ می‌شود.

---

## 14. Device History روی Vehicle

Vehicle باید تاریخچه Deviceهای متصل به خودش را نگه دارد.

مثال:

```text
Vehicle 01

2026/01/01 → Device 001
2026/05/01 → Device 002
2026/08/01 → Device 005
```

در صفحه Vehicle، Device فعلی و تاریخچه Deviceهای قبلی قابل مشاهده خواهد بود.

---

## 15. Vehicle Status

در نسخه فعلی برای Vehicle سیستم Status مستقل ایجاد نمی‌کنیم.

وضعیت‌هایی مانند:

```text
Active
Inactive
Broken
Sold
Out of Service
```

فعلاً جزو مدل Vehicle نیستند.

تمرکز وضعیت عملیاتی روی Device خواهد بود.

---

## 16. حذف Vehicle

اطلاعات Vehicle نباید به‌صورت فیزیکی از سیستم حذف شوند، زیرا Vehicle ممکن است دارای:

* Device History
* Driver History
* Plate History
* Branch History
* Tracking History

باشد.

بنابراین حذف فیزیکی داده‌های عملیاتی مجاز نیست.

برای خارج کردن Vehicle از چرخه فعال سیستم از مکانیزم مناسب Archive/Inactive در طراحی نهایی استفاده خواهد شد.

جزئیات این مکانیزم در بخش Lifecycle و Data Retention نهایی خواهد شد.

---

## 17. تغییر اطلاعات Vehicle

اصل کلی:

**اطلاعات مهم و هویتی Vehicle باید در صورت تغییر، History داشته باشند.**

در نسخه فعلی مهم‌ترین مورد:

```text
Plate History
```

است.

اطلاعات دیگری مانند رنگ، مدل و مشخصات فنی فعلاً در Vehicle ذخیره نمی‌شوند.

---

## 18. Vehicle و Driver

Driver مستقل از Vehicle است.

رابطه:

```text
Driver ←→ Vehicle
```

چندبه‌چند است.

یک Driver می‌تواند چند Vehicle داشته باشد.

یک Vehicle نیز می‌تواند چند Driver داشته باشد.

---

## 19. Driver Assignment

در صفحه Vehicle، راننده یا رانندگان فعلی قابل مشاهده هستند.

مثال:

```text
Truck 01

Current Drivers:
Ali
Reza
```

سوابق رانندگان قبلی نیز باید قابل مشاهده باشد.

---

## 20. Driver بدون Vehicle

Driver می‌تواند در Organization وجود داشته باشد ولی فعلاً هیچ Vehicleی به او اختصاص داده نشده باشد.

مثال:

```text
Ali     → Truck 01
Reza    → Truck 02
Hassan  → No Vehicle
```

این حالت مجاز است.

---

## 21. زمان‌بندی Driver Assignment

Assignment راننده به Vehicle دارای بازه زمانی است.

مثال:

```text
Truck 01

08:00 → 16:00
Ali

16:00 → 00:00
Reza
```

همچنین Overlap بین Assignmentها مجاز است.

مثال:

```text
08:00 → 16:00
Ali

12:00 → 20:00
Reza
```

سیستم نباید صرفاً به دلیل Overlap، Assignment را رد کند.

---

## 22. Vehicle Type و ویژگی‌های اختصاصی

در نسخه اول همه Vehicleها از ساختار پایه مشترک استفاده می‌کنند.

Vehicle Type صرفاً مشخص می‌کند وسیله از چه نوعی است.

ساختن ساختارهای پیچیده و فیلدهای اختصاصی برای هر Vehicle Type فعلاً انجام نمی‌شود.

در آینده در صورت نیاز قابل توسعه است.

---

# تصمیمات قطعی بخش Vehicle Management

[✓] Vehicle Entity مستقل دارد.

[✓] Vehicle دارای Internal ID است.

[✓] Plate Number شناسه عملیاتی اصلی Vehicle است.

[✓] Plate به‌صورت String ذخیره می‌شود.

[✓] هر پلاک در هر لحظه فقط روی یک Vehicle قرار دارد.

[✓] پلاک در طول زمان می‌تواند به Vehicle دیگری منتقل شود.

[✓] Plate History نگهداری می‌شود.

[✓] Vehicle متعلق به همان Personal Account یا Organization ایجادکننده آن است.

[✓] مالکیت Vehicle به Entity جداگانه تبدیل نمی‌شود.

[✓] Vehicle Type توسط خود Customer تعریف می‌شود.

[✓] Vehicle Type برای Personal Account نیز قابل تعریف است.

[✓] فعلاً اطلاعات فنی و ظاهری اضافی Vehicle ذخیره نمی‌شود.

[✓] Vehicle سازمانی می‌تواند به Branch اختصاص داشته باشد.

[✓] Vehicle می‌تواند بدون Branch باشد.

[✓] انتقال Vehicle بین Branchها مجاز است.

[✓] انتقال Vehicle فقط توسط Main User انجام می‌شود.

[✓] Main User می‌تواند Vehicle را از Branch خارج و Unassigned کند.

[✓] تمام انتقال‌های Branch در History ذخیره می‌شوند.

[✓] Vehicle می‌تواند بدون Device وجود داشته باشد.

[✓] Vehicle بدون Device قابلیت Tracking ندارد.

[✓] هر Vehicle در هر لحظه حداکثر یک Device فعال دارد.

[✓] Deviceهای قبلی Vehicle حذف نمی‌شوند.

[✓] Device Assignment History روی Vehicle نگهداری می‌شود.

[✓] Vehicle در نسخه فعلی Management Status مستقل ندارد.

[✓] حذف فیزیکی Vehicle مجاز نیست.

[✓] داده‌های تاریخی Vehicle باید حفظ شوند.

[✓] Driver مستقل از Vehicle است.

[✓] Driver و Vehicle رابطه چندبه‌چند دارند.

[✓] Driver می‌تواند بدون Vehicle باشد.

[✓] Vehicle می‌تواند چند Driver داشته باشد.

[✓] Driver Assignment دارای بازه زمانی است.

[✓] Overlap بین Driver Assignmentها مجاز است.

[✓] تاریخچه Driver Assignment نگهداری می‌شود.

---

# وضعیت بخش

**Vehicle Management — COMPLETED / FINAL**

بخش 04 تکمیل شد.
============================================================



# SANA — سامانه اتوماسیون ناوگان ایران

## فاز ۱ — تحلیل و طراحی تئوری

# بخش 05 — Subscription / Contract

**وضعیت: FINAL**

---

## 1. مفهوم Subscription

Subscription (اشتراک/قرارداد) سندی است که بین سانا و مشتری (شخص یا سازمان) بسته می‌شود و مشخص می‌کند:

- سانا به مشتری چه سرویسی می‌دهد
- از چه تاریخی شروع می‌شود
- تا چه تاریخی ادامه دارد
- چه دستگاه‌هایی زیر این قرارداد هستند
- مبلغ قرارداد چقدر است

---

## 2. مالکیت Subscription

Subscription متعلق به یک مشتری است. مشتری می‌تواند:

- شخص باشد
- سازمان باشد

---

## 3. تفاوت Subscription و Device

- **Device** = سخت‌افزار فیزیکی که مالکش مشتری است
- **Subscription** = قرارداد سرویس نرم‌افزاری که توسط سانا به مشتری فروخته می‌شود

مشتری می‌تواند:

- Device داشته باشد ولی Subscription فعال نداشته باشد
- Subscription داشته باشد و چندین Device زیر آن باشد

---

## 4. ساختار Subscription

هر Subscription شامل:

- `contract_number` — شماره یکتای قرارداد
- `customer` — مشتری (شخص یا سازمان)
- `start_date` — تاریخ شروع (شمسی)
- `end_date` — تاریخ پایان (شمسی)
- `status` — وضعیت
- `price` — مبلغ قرارداد
- `notes` — یادداشت‌ها
- `created_at`

### وضعیت‌های Subscription

```text
Active       — فعال (در جریان)
Suspended    — تعلیق‌شده (موقتاً غیرفعال)
Expired      — منقضی‌شده
Cancelled    — لغو‌شده



BACKEND RUN: python manage.py runserver 0.0.0.0:8000
FRONTEND RUN: npm run dev -- --host