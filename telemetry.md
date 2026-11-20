# مستند فنی جامع SANA
## معماری، جریان داده، اجزای نرم‌افزار، پایگاه داده و عملیات

> **وضعیت سند:** بازنویسی کامل بر اساس کد شاخه main پس از ادغام PR شماره ۱۱۸  
> **Commit مبنا:** 83622d023a5fd6bcc1adc220f6bebb63ab007be7  
> **تاریخ بازبینی:** 2026-11-08  
> **اصل نگارش:** این سند وضعیت پیاده‌سازی موجود در مخزن را توصیف می‌کند؛ تصمیم‌های قدیمی، طرح‌های اجرا‌نشده و قابلیت‌های صرفاً نمایشی، به‌عنوان قابلیت فعال معرفی نمی‌شوند.

---

# ۱. هدف و دامنه سامانه

SANA سامانه مدیریت ناوگان و خدمات ردیابی خودرو است. مسئولیت‌های اصلی آن عبارت‌اند از:

- مدیریت مشتریان سازمانی و شخصی، شرکت‌ها، شعب و کاربران.
- مدیریت قراردادها، تخصیص دستگاه به قرارداد و دوره مجاز دریافت سرویس.
- مدیریت دستگاه GPS، شناسه IMEI، مدل، پروتکل، سیم‌کارت، وضعیت مدیریتی و ارتباط آن با خودرو.
- مدیریت خودرو، راننده و تاریخچه تخصیص راننده به خودرو.
- نمایش موقعیت زنده و گزارش مسیر تاریخی دستگاه‌ها.
- نگهداری نتیجه تطبیق مسیر با شبکه راه‌ها از سرویس نشان (Neshan)، بدون تبدیل SANA به مخزن داده خام GPS.
- ثبت عملیات مالی قرارداد، دریافت وجه، برنامه اقساط و تخصیص مبالغ.
- ثبت چرخه عمر و عملیات تعمیر، جایگزینی، انتقال و تعیین تکلیف دستگاه.
- ارائه ابزارهای مدیریتی برای بررسی سرویس‌ها، لاگ‌ها و پورت‌های Traccar.
- نگهداری مدل داده و ابزارهای اولیه بررسی پروتکل‌های ناشناخته.

SANA از چند جزء مستقل تشکیل شده است. Backend منطق تجاری و API را اجرا می‌کند، Panel رابط کاربری است، Traccar دریافت و رمزگشایی پروتکل GPS و نگهداری موقعیت‌ها را انجام می‌دهد و سرویس sana-gps کارهای هماهنگ‌سازی دستگاه و تطبیق نقشه را بر عهده دارد.

## ۱.۱. اصل بنیادین معماری GPS

**Traccar مرجع اصلی و مالک داده خام GPS و موقعیت‌های دستگاه است.**

SANA نباید نسخه موازی از موقعیت‌ها، بسته‌های خام، رویدادها، سفرها یا تاریخچه GPS در پایگاه داده خودش بسازد. SANA داده موردنیاز را از REST API ترکار می‌خواند و فقط داده‌ای را نگه می‌دارد که متعلق به منطق اختصاصی خودش است؛ در پیاده‌سازی فعلی، مهم‌ترین نمونه آن نتیجه تطبیق مختصات با جاده‌های نشان است.

بنابراین:

- Traccar دریافت TCP/UDP دستگاه، تشخیص پروتکل، رمزگشایی، ثبت Position، محاسبه وضعیت آنلاین، تاریخچه، Event، Trip و Geofence را مدیریت می‌کند.
- SANA اطلاعات ناوگان و رابطه‌های تجاری را نگه می‌دارد.
- SANA برای نمایش نقشه زنده و گزارش مسیر، مستقیماً از API ترکار استفاده می‌کند.
- SANA فقط شناسه‌های Traccar و داده‌های تکمیلی اختصاصی خودش را به موقعیت‌های ترکار مرتبط می‌کند.
- خطای Neshan نباید مختصات اصلی ترکار را تغییر دهد یا دریافت GPS را مختل کند.
- نبود اعتبار سرویس نشان نباید به معنی از دست رفتن موقعیت خام دستگاه باشد.

---

# ۲. نمای کلی معماری و اجزای مخزن

ساختار اصلی مخزن:

~~~text
SANA/
├── sana-backend/                 # Django و REST API
│   ├── accounts/                 # حساب کاربری، JWT و مجوزها
│   ├── organizations/            # سازمان، شعبه، قرارداد و امور مالی
│   ├── fleet/                    # خودرو، دستگاه، راننده و عملیات ناوگان
│   ├── dashboard/                # داشبورد و تنظیمات سراسری
│   ├── ops_monitoring/           # لاگ زنده و ابزارهای مدیریتی Traccar
│   ├── decoder_discovery/        # مدل داده و تحلیل اولیه پروتکل ناشناخته
│   └── sana_core/                # تنظیمات و URLهای اصلی Django
│
├── sana-gps/                     # سرویس پشتیبان GPS
│   ├── app/
│   │   ├── database/             # Connection Pool
│   │   ├── repositories/         # دسترسی محدود به داده ناوگان
│   │   ├── traccar/               # REST client و همگام‌سازی دستگاه
│   │   ├── processing/            # تطبیق موقعیت با جاده
│   │   ├── config.py
│   │   └── main.py
│   ├── sql/                       # نقش PostgreSQL و schema اختصاصی GPS
│   └── tests/
│
├── sana-panel/                   # رابط React/Vite
│   └── src/
│       ├── api/
│       ├── components/
│       ├── context/
│       ├── layouts/
│       ├── pages/
│       └── utils/
│
├── sana-map/                     # لایه مشترک نقشه و Providerها
│   └── src/
│       ├── providers/
│       ├── LiveDeviceMap.jsx
│       ├── markerAnimation.js
│       └── config.js
│
├── AI/auto_decoder_generator/    # فضای اولیه ماژول تولید/کشف Decoder
├── scripts/                      # اسکریپت نصب، بازسازی DB و ابزار پورت
├── docs/                         # مستندهای تکمیلی
├── .github/workflows/            # گردش‌کارهای CI
└── telemetry.md                  # همین مستند
~~~

## ۲.۱. مسئولیت هر جزء

| جزء | مسئولیت | خارج از مسئولیت |
|---|---|---|
| Traccar Server | دریافت و رمزگشایی پروتکل، نگهداری موقعیت و تاریخچه | مدیریت قرارداد، مشتری و مجوز تجاری SANA |
| sana-backend | منطق تجاری، احراز هویت، مجوز، API و دسترسی داده | دریافت مستقیم پروتکل GPS |
| sana-gps | اتصال به PostgreSQL، همگام‌سازی Device با Traccar، تطبیق نقشه | اجرای Listener پروتکل یا ذخیره Position خام |
| sana-panel | رابط کاربر و فراخوانی API | تصمیم نهایی امنیتی و اعمال مجوز در سمت سرور |
| sana-map | نمایش نقشه با Provider قابل تعویض و حرکت Marker | مالکیت یا ذخیره داده GPS |
| PostgreSQL/PostGIS | داده تجاری SANA و نتیجه تطبیق جاده | جایگزینی دیتابیس Traccar |
| اسکریپت‌های سیستم‌عامل | عملیات نصب، بازسازی و عیب‌یابی کنترل‌شده | منطق تجاری و مجوزدهی کاربران |

## ۲.۲. فناوری‌های اصلی

- Backend: Python، Django 6.1.1، Django REST Framework، SimpleJWT، django-filter و drf-spectacular.
- Database: PostgreSQL با PostGIS.
- GPS worker: Python 3.12، psycopg و psycopg-pool.
- Panel: React 19، React Router، Axios، Vite، Tailwind CSS، Leaflet و Recharts.
- Map: Leaflet با دو Provider فعلی OpenStreetMap و Neshan.
- Traccar: نسخه نصب‌شده مورد استفاده در محیط فعلی پروژه 6.16.0؛ نسخه نصب‌شده باید در خود سرور بررسی شود.
- ارتباط Backend و GPS worker با Traccar: REST API محلی و احراز هویت Basic بر پایه نام کاربری و رمز عبور Traccar.
- در معماری فعلی برای صف یا Cache عملیاتی GPS از Redis استفاده نشده است.

---

# ۳. جریان اصلی داده GPS

## ۳.۱. از دستگاه تا نمایش روی نقشه

~~~text
GPS Tracker
    │
    │ TCP / UDP
    ▼
Traccar Server
    │
    ├── تشخیص پروتکل بر اساس Listener و Decoder
    ├── استخراج IMEI / شناسه دستگاه
    ├── رمزگشایی مختصات، زمان، سرعت و Attributes
    ├── ثبت Position و تاریخچه در دیتابیس مستقل Traccar
    └── نگهداری وضعیت فعلی Device
             │
             │ REST API
             ▼
       sana-backend
             │
             ├── تطبیق Traccar Device.uniqueId با fleet.Device.imei
             ├── اعمال مجوز کاربر و محدوده دسترسی
             ├── دریافت Position فعلی یا تاریخچه
             ├── تبدیل واحدها و ساخت پاسخ API
             └── خواندن نتیجه Neshan از schema اختصاصی GPS
                      │
                      ▼
                 sana-panel
                      │
                      ▼
                   sana-map
~~~

دستگاه به Traccar متصل می‌شود، نه به Listener اختصاصی SANA. Traccar پروتکل را تشخیص می‌دهد و موقعیت را در مخزن خودش نگه می‌دارد. Backend با استفاده از شناسه Traccar، داده را به دستگاه ثبت‌شده در SANA مرتبط می‌کند و فقط دستگاه‌هایی را که کاربر اجازه مشاهده آن‌ها را دارد در پاسخ برمی‌گرداند.

## ۳.۲. دریافت داده خام و مرز ذخیره‌سازی

در وضعیت فعلی کد:

- سرویس sana-gps هیچ TCP Listener یا UDP Listener برای دریافت مستقیم دستگاه ندارد.
- سرویس sana-gps وب‌هوک دریافت Position از Traccar را نیز اجرا نمی‌کند.
- پیام‌های خام و Positionهای ترکار در دیتابیس Traccar باقی می‌مانند.
- SANA برای گزارش تاریخی، Positionها را از API ترکار می‌خواند.
- SANA پاسخ API ترکار را به‌عنوان بسته خام سیم‌کارت یا بسته اصلی TCP/UDP معرفی نمی‌کند.
- در schema فعلی SANA جدول‌های قدیمی raw_packet، location_history، current_state، event و trip ساخته نمی‌شوند.

این مرزبندی عمدی است؛ افزودن ذخیره موازی Position در SANA باعث دو مرجع متفاوت، اختلاف تاریخچه و پیچیدگی نگهداری خواهد شد.

## ۳.۳. ارتباط شناسه‌ها

دو شناسه متفاوت وجود دارد:

1. IMEI یا شناسه فیزیکی دستگاه که در SANA در جدول fleet_device ذخیره می‌شود.
2. شناسه عددی داخلی Traccar که در جدول‌ها و API خود Traccar استفاده می‌شود.

رابطه بین آن‌ها از طریق فیلد Traccar Device.uniqueId برقرار می‌شود:

~~~text
public.fleet_device.imei
        │
        │ برابر با
        ▼
Traccar Device.uniqueId
        │
        ▼
Traccar Device.id
        │
        ├── Position.deviceId
        └── Position.id
~~~

SANA نباید فرض کند مقدار Traccar Device.id برابر با شناسه دیتابیس SANA است. این دو سیستم شناسه مستقل دارند.

## ۳.۴. همگام‌سازی دستگاه‌ها با Traccar

کدهای مربوط:

- sana-gps/app/traccar/client.py
- sana-gps/app/traccar/device_sync.py
- sana-gps/app/repositories/device.py
- sana-gps/app/main.py

هنگام شروع sana-gps و سپس در بازه پیش‌فرض ۶۰ ثانیه:

1. IMEI دستگاه‌های ثبت‌شده در public.fleet_device خوانده می‌شود.
2. فهرست Deviceهای Traccar از API دریافت می‌شود.
3. هر IMEI که در SANA وجود دارد ولی در Traccar ثبت نشده، با name و uniqueId برابر IMEI در Traccar ساخته می‌شود.
4. دستگاه‌های موجود در Traccar حذف یا بازنویسی نمی‌شوند.
5. Positionهای فعلی Traccar خوانده می‌شوند.
6. از روی Position.deviceId، شناسه Traccar به uniqueId و سپس IMEI مرتبط می‌شود.
7. اگر IMEI در SANA ثبت شده باشد و Position فیلد protocol داشته باشد، مقدار protocol در fleet_device.protocol به‌روزرسانی می‌شود.

**جهت همگام‌سازی Device یک‌طرفه است:**

- دستگاه ثبت‌شده در SANA می‌تواند به Traccar اضافه شود.
- دستگاه ناشناخته Traccar به‌صورت خودکار به Device رسمی SANA تبدیل نمی‌شود.
- کد فعلی GPS worker هیچ فرایند عمومی برای واردکردن همه Deviceهای ناشناخته Traccar به fleet_device ندارد.

اگر اعتبار API ترکار تنظیم نشده باشد، همگام‌سازی غیرفعال می‌شود و در لاگ هشدار ثبت می‌شود. خطای همگام‌سازی اولیه مانع تلاش دوره‌ای بعدی نمی‌شود.

## ۳.۵. کاتالوگ برند و مدل دستگاه

فرمان مدیریت:

~~~bash
cd sana-backend
python manage.py sync_traccar_device_catalog
~~~

فایل اصلی:

sana-backend/fleet/management/commands/sync_traccar_device_catalog.py

منبع کاتالوگ، صفحه رسمی فهرست دستگاه‌های Traccar است. فرمان:

- جدول دستگاه‌های رسمی منتشرشده را دریافت می‌کند.
- نام سازنده و مدل را تا حد امکان جدا می‌کند.
- نام پروتکل و پورت اعلام‌شده در فهرست را ثبت می‌کند.
- فهرست قبلی را از حالت قابل انتخاب خارج می‌کند، اما رکوردهای قدیمی را حذف نمی‌کند تا Foreign Key دستگاه‌های قبلی حفظ شود.
- رکوردهای جدید یا به‌روزشده را با کلید سازنده، مدل و برچسب نسخه کاتالوگ ثبت می‌کند.
- در حالت dry-run فقط دریافت و پردازش را انجام می‌دهد و دیتابیس را تغییر نمی‌دهد.

نکته مهم: برچسب نسخه‌ای که این فرمان در حال حاضر ثبت می‌کند official-current است. این برچسب به معنی تضمین سازگاری تمام مدل‌های فهرست وب با نسخه نصب‌شده Traccar نیست. خود کد نیز این محدودیت را اعلام می‌کند.

فیلد Device.device_model برای ثبت اولیه اجباری نیست. پروتکل واقعی دستگاه از Position.protocol ترکار دریافت می‌شود و مقدار کاتالوگ صرفاً اطلاعات مدل/پروتکل مورد انتظار است؛ نباید آن را با پروتکل واقعی گزارش‌شده یکی دانست.

---

# ۴. اصول Traccar و نقش آن در SANA

## ۴.۱. وظایف Traccar

Traccar در این معماری مسئول موارد زیر است:

- بازکردن Listenerهای پروتکل‌های پشتیبانی‌شده.
- دریافت اتصال دستگاه‌ها روی پورت و Transport مناسب.
- شناسایی Decoder متناسب با پروتکل.
- استخراج شناسه دستگاه، مختصات، زمان، سرعت، جهت، اعتبار GPS و Attributes.
- ثبت Positionها و تاریخچه.
- نگهداری آخرین وضعیت Device.
- ارائه REST API برای Device، Position و گزارش‌های قابل پشتیبانی.
- مدیریت منطق داخلی Event، Trip، Geofence و پردازش‌های مربوط به خودش.

SANA نباید برای انجام دوباره این وظایف، Listener یا ساختار ذخیره‌سازی موازی ایجاد کند.

## ۴.۲. REST API مورد استفاده

فایل Backend:

sana-backend/fleet/traccar_api.py

فایل GPS worker:

sana-gps/app/traccar/client.py

APIهای مورد استفاده در کد فعلی:

| API ترکار | استفاده در SANA |
|---|---|
| GET /api/devices | فهرست دستگاه‌ها و نگاشت uniqueId |
| POST /api/devices | ایجاد Device متناظر با IMEI ثبت‌شده در SANA |
| GET /api/positions | موقعیت‌های فعلی دستگاه‌ها |
| GET /api/positions?deviceId=...&from=...&to=... | تاریخچه موقعیت یک دستگاه در بازه زمانی |
| GET /api/devices/{id} | دریافت جزئیات یک Device در صورت نیاز Client |

اتصال فعلی با Basic Authentication انجام می‌شود. نشانی پیش‌فرض API در کد http://127.0.0.1:8082/api است. API باید در شبکه عمومی منتشر نشود و دسترسی آن از مسیر محلی/مجاز سرور انجام شود.

## ۴.۳. زمان‌ها و تازگی داده

سه زمان مهم در Position ترکار ممکن است وجود داشته باشد:

- serverTime: زمان دریافت/ثبت از دید سرور.
- fixTime: زمان Fix موقعیت.
- deviceTime: زمان اعلام‌شده توسط دستگاه.

برای محاسبه تازگی ارتباط، مرتب‌سازی گزارش و صفحه‌بندی تاریخچه، کد فعلی Backend فقط serverTime را مرجع قرار می‌دهد. این تصمیم برای جلوگیری از اعتماد به ساعت نادرست یا باتری پشتیبان ضعیف دستگاه است.

در تابع normalize_traccar_history_positions:

- Position فاقد serverTime معتبر کنار گذاشته می‌شود.
- مختصات باید عددی، finite و در محدوده جغرافیایی معتبر باشند.
- Positionهای تکراری با id حذف می‌شوند.
- ترتیب با ترکیب serverTime و Position.id تعیین می‌شود.
- صفحه‌بندی بعدی از cursor_time و cursor_id استفاده می‌کند.

در خروجی API، زمان دستگاه/فیکس می‌تواند به‌عنوان اطلاعات نمایشی جداگانه باقی بماند؛ اما نباید به جای serverTime برای محاسبه تازگی یا ترتیب استفاده شود.

در GPS worker نیز زمان Position برای تطبیق نقشه با ترتیب serverTime، سپس fixTime و سپس deviceTime انتخاب می‌شود. این انتخاب مخصوص پردازش تطبیق است و جایگزین قاعده serverTime در Backend برای تازگی و گزارش نیست.

## ۴.۴. تبدیل واحد و Attributeها

Traccar سرعت را در API به واحد knot ارائه می‌کند. SANA در پاسخ‌های نقشه و گزارش سرعت را به km/h تبدیل می‌کند:

~~~text
speed_kmh = speed_knots × 1.852
~~~

course به عنوان جهت حرکت/heading استفاده می‌شود.

Attributes ترکار به شکل یک دیکشنری JSON دریافت می‌شوند. Backend مقادیر متعارف مورد نیاز UI را استخراج می‌کند، اما دیکشنری Attributes اصلی را نیز در پاسخ گزارش نگه می‌دارد تا فیلدهای خاص Decoder یا دستگاه حذف نشوند.

نمونه نگاشت فعلی در گزارش:

| فیلد خروجی گزارش SANA | منبع Position/Attributes ترکار |
|---|---|
| speed | Position.speed × 1.852 |
| heading | Position.course |
| latitude / longitude | Position.latitude / Position.longitude |
| gps_valid | Position.valid |
| server_received_at | Position.serverTime |
| device_time | زمان انتخاب‌شده برای نمایش نقطه |
| motion | attributes.motion |
| ignition | attributes.ignition |
| satellites | attributes.sat |
| battery_voltage | attributes.battery |
| external_voltage | attributes.power |
| gsm_signal | attributes.rssi |
| odometer | attributes.odometer |
| engine_hours | attributes.hours |
| fuel_level | attributes.fuel |
| attributes | کل attributes دریافتی از Position |

وجود یک کلید در دیکشنری Attributes به معنی پشتیبانی یکسان همه دستگاه‌ها از آن نیست. نام، واحد، نوع و معنی مقدار می‌تواند بر اساس پروتکل و Decoder متفاوت باشد. SANA نباید برای Attribute ناشناخته مقدار یا واحد ساختگی تولید کند.

## ۴.۵. وضعیت آنلاین و حرکت

در API نقشه زنده:

- وضعیت ارتباط از Traccar Device.status و serverTime آخرین Position تعیین می‌شود.
- اگر وضعیت Traccar برابر online نباشد یا زمان serverTime معتبر نباشد، دستگاه online تلقی نمی‌شود.
- Position با serverTime بیش از ۳۰۰ ثانیه قدیمی، برای وضعیت آنلاین معتبر نیست.
- اگر آنلاین باشد و attributes.motion برابر true باشد یا سرعت خام حداقل ۳ km/h باشد، وضعیت moving است.
- در غیر این صورت وضعیت stopped است.

این وضعیت نمایشی با وضعیت مدیریتی دستگاه در SANA متفاوت است. برای مثال دستگاه می‌تواند از نظر مدیریت در انبار یا خراب باشد، درحالی‌که Traccar هنوز برای IMEI آن Position دریافت کند.

## ۴.۶. پروتکل و مدل واقعی

سه مفهوم باید جدا بمانند:

1. DeviceModel.protocol: پروتکل مرتبط با مدل کاتالوگ.
2. Device.protocol: پروتکلی که از Position.protocol ترکار برای IMEI ثبت‌شده در SANA همگام می‌شود.
3. Traccar Device.model یا اطلاعاتی که ترکار در پاسخ فعلی خود ارائه می‌کند: داده تشخیصی/نمایشی که لزوماً معادل مدل انتخاب‌شده در کاتالوگ SANA نیست.

برای تشخیص پروتکل واقعی، Position.protocol ترکار مرجع عملیاتی است. مدل انتخابی در فرم نباید جایگزین داده واقعی Decoder شود.

---

# ۵. تطبیق مسیر با جاده‌های نشان (Neshan Map Matching)

فایل:

sana-gps/app/processing/map_matching.py

هدف این قابلیت اصلاح نمایشی مختصات خام برای قرارگرفتن روی مسیر جاده است. این عملیات Position خام Traccar را تغییر نمی‌دهد.

## ۵.۱. شرط اجرای تطبیق

تطبیق فقط زمانی انجام می‌شود که حداقل یک نشست فعال نقشه در جدول gps.map_matching_watchers وجود داشته باشد.

در Panel صفحه نقشه:

- یک session_id برای صفحه/نشست ساخته می‌شود.
- هر ۱۵ ثانیه heartbeat به endpoint زیر فرستاده می‌شود:
  POST /api/devices/map-matching-activity/
- هنگام خروج صفحه، active=false ارسال می‌شود.
- اگر مرورگر ناگهان بسته شود، رکورد watcher با expires_at منقضی خواهد شد.

Backend برای heartbeat مقدار انقضای ۴۵ ثانیه ثبت می‌کند. Worker هر ۱۰ ثانیه وضعیت watcherها را بررسی می‌کند و watcherهای منقضی‌شده را پاک می‌کند.

بنابراین گزارش تاریخی به‌تنهایی نباید Worker تطبیق زنده را فعال کند؛ فعال‌بودن نقشه زنده شرط شروع polling است.

## ۵.۲. دریافت نقاط و محدودیت درخواست

Worker:

1. IMEIهای ثبت‌شده در public.fleet_device را می‌خواند.
2. Deviceهای Traccar را می‌خواند و IMEI را به Traccar Device.id مرتبط می‌کند.
3. Positionهای سه دقیقه اخیر را برای هر دستگاه از API ترکار دریافت می‌کند.
4. فقط مختصات معتبر و Position دارای شناسه و زمان معتبر را نگه می‌دارد.
5. نقاط را بر اساس زمان مرتب می‌کند.
6. حداکثر ۱۰۰ نقطه برای هر درخواست انتخاب می‌کند.
7. Positionهایی را که قبلاً در جدول تطبیق ثبت شده‌اند کنار می‌گذارد.
8. برای حداقل دو نقطه معتبر، مسیر را به API نشان می‌فرستد.
9. مختصات Snap شده را بر اساس originalIndex به Position ID ترکار مرتبط می‌کند.

## ۵.۳. مرز داده خام و نتیجه تطبیق

- مختصات خام فقط از Traccar خوانده می‌شود.
- خروجی Neshan در SANA ذخیره می‌شود.
- داده خام ترکار هرگز با مختصات Snap شده جایگزین نمی‌شود.
- اگر درخواست Neshan خطا بدهد یا اعتبار سرویس تمام شده باشد، خطا در لاگ Worker ثبت می‌شود و پردازش به چرخه بعد موکول می‌شود.
- خطای Neshan نباید مانع دریافت یا نمایش مختصات خام ترکار شود.

## ۵.۴. انتخاب مختصات در UI

در نقشه و گزارش، اگر نتیجه تطبیق برای شناسه Position وجود داشته باشد، مختصات matched_latitude و matched_longitude برای نمایش مسیر استفاده می‌شوند؛ در غیر این صورت مختصات خام Traccar نمایش داده می‌شود.

پاسخ API باید مشخص کند که نقطه تطبیق‌یافته است یا خیر و در صورت وجود، Provider و زمان تطبیق را برگرداند.

---

# ۶. Backend و ماژول‌های Django

## ۶.۱. sana_core

فایل‌های اصلی:

- sana-backend/sana_core/settings.py
- sana-backend/sana_core/urls.py

مسئولیت‌ها:

- تنظیمات Django و اپلیکیشن‌ها.
- اتصال PostgreSQL با PostGIS.
- تعریف مدل کاربر سفارشی accounts.User.
- تنظیم JWT، CORS، زبان و منطقه زمانی.
- ثبت URLهای API و مستندات OpenAPI/Swagger.
- تنظیم Pagination پیش‌فرض API روی ۲۰ رکورد.

منطقه زمانی Django برابر Asia/Tehran و USE_TZ فعال است.

تنظیمات اصلی REST Framework:

- Authentication: ContractAwareJWTAuthentication.
- Permission پیش‌فرض: IsAuthenticated.
- Filter backend: django-filter، SearchFilter و OrderingFilter.
- Pagination: PageNumberPagination با PAGE_SIZE=20.
- Schema: drf-spectacular.

## ۶.۲. accounts

فایل‌ها:

- accounts/models.py
- accounts/authentication.py
- accounts/permissions.py
- accounts/serializers.py
- accounts/views.py
- accounts/urls.py

این ماژول مسئول هویت، ورود، نقش و دسترسی پایه کاربران است.

### نوع حساب

- admin: مدیر کل سایت.
- organization: حساب سازمانی.
- personal: حساب شخصی.

### نقش

- site_admin: ادمین کل سایت.
- main_user: مدیر شرکت.
- branch_manager: مدیر شعبه.
- personal_user: کاربر شخصی.

نوع حساب و نقش دو فیلد جدا هستند و نباید به جای یکدیگر استفاده شوند.

### ارتباط کاربر

User می‌تواند به Organization و Branch متصل باشد. کاربران شخصی به عنوان owner مستقل شناخته می‌شوند. نقش ادمین کل سایت وابسته به سازمان مشتری نیست.

### کنترل ورود و دسترسی قرارداد

User دارای منطق زیر است:

- is_active حساب باید فعال باشد.
- سازمان مرتبط باید فعال باشد.
- برای حساب سازمانی یا شخصی باید قرارداد فعال و معتبر از نظر تاریخ وجود داشته باشد.
- ادمین کل سایت از کنترل قرارداد مشتری مستثنی است.

ContractAwareJWTAuthentication این شرط را در هر درخواست احراز هویت‌شده دوباره بررسی می‌کند؛ یعنی داشتن توکن قدیمی به‌تنهایی اجازه دسترسی دائمی نمی‌دهد.

### Permissionهای اصلی

- IsSiteAdminOrReadOnly: خواندن برای کاربر احراز هویت‌شده، نوشتن فقط ادمین.
- IsSiteAdmin: فقط ادمین کل سایت.
- IsMainUserOrSiteAdmin: مدیر شرکت یا ادمین.
- IsOrganizationMember: عضو سازمان یا ادمین.

### APIهای اصلی

| مسیر | کاربرد |
|---|---|
| POST /api/auth/login/ | دریافت توکن |
| POST /api/auth/refresh/ | تمدید توکن |
| POST /api/auth/verify/ | اعتبارسنجی توکن |
| /api/users/ | مدیریت/فهرست کاربران |
| GET /api/users/me/ | اطلاعات حساب جاری |
| GET /api/users/username-availability/ | بررسی امکان استفاده از نام کاربری |
| POST /api/users/change-password/ | تغییر رمز عبور |

JWT فعلی: عمر Access Token برابر ۲ ساعت و Refresh Token برابر ۷ روز است. Refresh Token در تنظیمات فعلی rotate می‌شود.

## ۶.۳. organizations

فایل‌ها:

- organizations/models.py
- organizations/serializers.py
- organizations/views.py
- organizations/financial.py
- organizations/urls.py

این ماژول اطلاعات مشتریان، شعب، قراردادها، تخصیص دستگاه به قرارداد و ساختار مالی قرارداد را مدیریت می‌کند.

### سازمان و شعبه

Organization مشتری سازمانی است. Branch زیرمجموعه یک Organization است و کد شعبه در محدوده همان سازمان یکتا است.

### قرارداد

Subscription برای مشتری سازمانی یا شخصی ساخته می‌شود. شماره قرارداد در مدل unique است.

وضعیت ذخیره‌شده قرارداد شامل active، suspended، expired و cancelled است. computed_status وضعیت مؤثر را با توجه به وضعیت دستی و تاریخ شروع/پایان محاسبه می‌کند؛ بنابراین وضعیت ذخیره‌شده به‌تنهایی معیار قطعی اعتبار قرارداد نیست.

شماره قرارداد از الگوی سال شمسی و پیشوند نوع مشتری ساخته می‌شود:

- ORG برای قرارداد سازمانی.
- PRS برای قرارداد شخصی.

نمونه الگو: ORG-1405-0001. فیلد contract_number در دیتابیس unique است؛ بررسی نهایی یکتایی باید در سطح دیتابیس و منطق ایجاد رعایت شود.

### تخصیص دستگاه به قرارداد

SubscriptionDevice جدول واسط تاریخی بین Subscription و Device است.

هر رکورد شامل:

- قرارداد و دستگاه.
- تاریخ شروع و پایان اعتبار دستگاه در قرارداد.
- زمان ایجاد اتصال.
- زمان جداشدن (unassigned_at).
- عملیات افزودن و حذف مرتبط، در صورت وجود.

در ایجاد اتصال جدید، اتصال باز قبلی همان دستگاه بسته می‌شود. این جدول رابطه تاریخی است و نباید با مالکیت قانونی یا دسترسی مشاهده اشتباه گرفته شود.

### عملیات و تاریخچه قرارداد

SubscriptionOperation نوع عملیات تجاری/قراردادی را ثبت می‌کند؛ مانند ایجاد، تمدید، ویرایش، پرداخت، افزودن/حذف دستگاه، تعلیق، فعال‌سازی و لغو.

SubscriptionOperationChange تغییر فیلدهای ثبت‌شده در یک عملیات را با مقدار قبل و بعد نگه می‌دارد.

این دو جدول برای audit trail عملیات قرارداد هستند.

### پرداخت و اقساط

SubscriptionPayment دریافت واقعی وجه را ثبت می‌کند. ثبت پرداخت با تخصیص پرداخت به قسط یکسان نیست.

SubscriptionInstallmentPlan برنامه اقساط نسخه‌دار برای یک قرارداد است. برای هر قرارداد حداکثر یک برنامه active وجود دارد. هنگام بازنگری برنامه، نسخه قبلی superseded می‌شود و برنامه جدید ساخته می‌شود.

SubscriptionInstallment قسط هر نسخه برنامه را نگه می‌دارد.

SubscriptionPaymentAllocation مشخص می‌کند چه بخشی از یک دریافتی به چه قسط یا پیش‌پرداخت قرارداد تخصیص یافته است. مقدار تخصیص مثبت است و رابطه تخصیص با پرداخت و قسط حفظ می‌شود.

منطق مالی در بخش‌های مربوط به مدل و ViewSetهای organizations پیاده شده است؛ فایل organizations/financial.py در وضعیت فعلی منبع اصلی این منطق نیست.

### قواعد تخصیص وجه

- تخصیص دستی باید به اقساط فعال همان قرارداد و همان برنامه فعال انجام شود.
- یک قسط در یک درخواست تخصیص دستی نباید دوبار تکرار شود.
- مبلغ تخصیص باید مثبت، صحیح و حداکثر برابر مانده قسط باشد.
- مجموع تخصیص‌ها نباید از مبلغ آزاد پرداخت بیشتر شود.
- تخصیص خودکار ابتدا اقساط سررسیدشده را پوشش می‌دهد.
- تخصیص به اقساط آینده فقط با سیاست surplus_policy برابر future انجام می‌شود.
- مازاد تخصیص‌نیافته به‌عنوان اعتبار مشتری باقی می‌ماند.
- پیش‌پرداخت قرارداد نوع تخصیص جداگانه دارد و installment آن تهی است.
- تخصیص‌ها از پرداخت بیشتر نمی‌شوند و روابط مالی برای ممیزی حفظ می‌شوند.

### APIهای اصلی

| مسیر | کاربرد |
|---|---|
| /api/organizations/ | سازمان‌ها |
| /api/branches/ | شعب |
| /api/subscriptions/ | قراردادها |
| /api/subscriptions/next_number/ | شماره پیشنهادی قرارداد |
| /api/subscriptions/{id}/renew/ | تمدید |
| /api/subscriptions/{id}/modify/ | ویرایش |
| /api/subscriptions/{id}/revise_installment_plan/ | بازنگری برنامه اقساط |
| /api/subscriptions/{id}/operations/ | تاریخچه عملیات |
| /api/subscriptions/{id}/suspend/ | تعلیق |
| /api/subscriptions/{id}/activate/ | فعال‌سازی |
| /api/subscriptions/{id}/cancel/ | لغو |
| /api/subscription-devices/ | تخصیص دستگاه به قرارداد |
| /api/subscription-payments/ | دریافت وجه |
| /api/subscription-payments/{id}/allocate/ | تخصیص وجه |

## ۶.۴. fleet

فایل‌ها:

- fleet/models.py
- fleet/serializers.py
- fleet/views.py
- fleet/device_operations.py
- fleet/lifecycle.py
- fleet/traccar_api.py
- fleet/traccar_attributes.py
- fleet/management/commands/sync_traccar_device_catalog.py

این ماژول مرکز مدیریت خودرو، دستگاه GPS، مدل دستگاه، راننده، تخصیص راننده و چرخه عمر دستگاه است.

### VehicleType

نوع خودرو؛ می‌تواند عمومی یا متعلق به یک سازمان باشد.

### Vehicle

خودرو با پلاک، نوع خودرو، مالک سازمانی یا شخصی و شعبه. دستگاه به خودرو از طریق Device.vehicle مرتبط می‌شود.

### DeviceModel

کاتالوگ مدل دستگاه GPS. اطلاعات اصلی:

- manufacturer
- name
- code
- protocol
- port
- traccar_version
- source_url
- is_verified

مدل‌های قابل انتخاب از endpoint فقط رکوردهای تأییدشده را برمی‌گردانند. CRUD این کاتالوگ از API عمومی DeviceModelViewSet در دسترس نیست؛ این ViewSet فقط خواندنی است.

### Device

رکورد اصلی دستگاه GPS در SANA. فیلدهای مهم:

- imei: شناسه یکتا و unique.
- device_model: ارتباط اختیاری با DeviceModel.
- protocol: پروتکل واقعی همگام‌شده از Traccar Position.protocol.
- organization یا owner_user: مالکیت مشتری.
- branch: شعبه مرتبط.
- current_holder_organization و current_holder_user: تحویل‌گیرنده فعلی؛ مستقل از مالکیت.
- sim_number: شماره سیم‌کارت.
- vehicle: خودروی نصب‌شده.
- management_status: وضعیت مدیریتی.
- installed_at: تاریخ نصب.

ثبت اولیه Device فقط به IMEI وابسته است و انتخاب مدل اجباری نیست.

### وضعیت مدیریتی Device

مقادیر فعلی:

- warehouse: در انبار.
- sold: فروخته‌شده.
- installed: نصب‌شده.
- active: فعال.
- ready: آماده تعیین تکلیف.
- faulty: خراب.
- lost: گمشده.
- stolen: سرقت‌شده.
- disconnected: قطع سرویس.
- retired: بازنشسته.
- disposed: امحاء‌شده.

این وضعیت با وضعیت آنلاین/آفلاین Traccar متفاوت است.

### مالکیت، دسترسی و قرارداد سه رابطه مستقل هستند

برای جلوگیری از اشتباه مفهومی:

1. DeviceOwnershipHistory تاریخچه مالکیت قانونی دستگاه را ثبت می‌کند.
2. DeviceCustomerAccessPeriod بازه زمانی مجاز مشاهده/رصد دستگاه برای یک مشتری را ثبت می‌کند.
3. SubscriptionDevice اتصال دستگاه به قرارداد و بازه اعتبار آن را نگه می‌دارد.

این روابط جایگزین یکدیگر نیستند. برای مثال دستگاه امانی می‌تواند مالکیت یک طرف را حفظ کند، در اختیار مشتری دیگری باشد و هم‌زمان در قرارداد مشخصی سرویس بگیرد.

DeviceCustomerAccessPeriod می‌تواند به سازمان یا کاربر شخصی، قرارداد و شعبه مرتبط باشد. در هر رکورد باید دقیقاً یکی از organization یا user پر باشد.

### مجازبودن سرویس دستگاه

Device.is_data_active و منطق DeviceListSerializer وضعیت فعال‌بودن سرویس دستگاه را از روی اتصال قرارداد، بازه زمانی تخصیص، وضعیت مؤثر قرارداد و وضعیت مدیریتی بررسی می‌کنند.

دستگاه فاقد تخصیص فعال، خارج از بازه اعتبار یا مرتبط با قرارداد معلق/لغوشده/منقضی/شروع‌نشده، نباید به‌عنوان دستگاه مجاز برای سرویس مشتری نمایش داده شود. وضعیت‌هایی مانند faulty، ready، lost، stolen، disconnected، retired و disposed نیز مانع فعال‌بودن سرویس در منطق فهرست دستگاه‌ها هستند.

این کنترل تجاری در SANA انجام می‌شود؛ Traccar همچنان ممکن است از نظر فنی برای IMEI همان دستگاه داده دریافت کند. قطع دریافت فیزیکی از Traccar، صرفاً با غیرفعال‌شدن قرارداد SANA اتفاق نمی‌افتد.

### عملیات دستگاه

DeviceOperation عملیات مدیریتی/فنی روی دستگاه را ثبت می‌کند؛ از جمله:

- بازگشت برای تعمیر.
- ثبت اتمام تعمیر.
- پیدا شدن دستگاه.
- تعیین تکلیف.
- جایگزینی موقت یا دائمی.
- گم‌شدن یا سرقت.
- انتقال به مشتری، شعبه یا خودرو.
- بازنشستگی و امحاء.

منطق اصلی اجرای عملیات در execute_device_operation در فایل fleet/device_operations.py قرار دارد و با transaction.atomic و قفل رکوردهای لازم اجرا می‌شود.

بر اساس نوع عملیات، ممکن است اتصال قبلی قرارداد بسته شود، دستگاه جایگزین به قرارداد متصل شود، اطلاعات تحویل‌گیرنده/خودرو به‌روزرسانی شود و رویدادهای چرخه عمر ثبت شوند.

### رابطه جایگزینی

DeviceReplacementRelation ارتباط بین دستگاه قبلی و جایگزین را مستقل از وضعیت فعلی دستگاه ثبت می‌کند. این رابطه می‌تواند موقت برای تعمیر یا دائمی باشد.

### رویداد چرخه عمر

DeviceLifecycleEvent تاریخچه رویدادهای مهم دستگاه را نگه می‌دارد. ثبت رویداد از تابع record_device_lifecycle_event انجام می‌شود و در صورت تعریف نگاشت، وضعیت مدیریتی فعلی دستگاه نیز همگام می‌شود.

### راننده و تخصیص راننده

Driver متعلق به سازمان و در صورت نیاز شعبه است.

DriverVehicleAssignment تاریخچه بازه‌ای تخصیص راننده به خودرو را نگه می‌دارد. در validation:

- پایان باید بعد از شروع باشد.
- راننده و خودرو باید متعلق به یک سازمان باشند.
- شعبه‌ها در صورت تعیین باید سازگار باشند.
- بازه‌های تخصیص متداخل برای یک خودرو رد می‌شوند.

### گزارش مسیر و نقشه

DeviceViewSet دو endpoint مهم دارد:

- report-history: دریافت تاریخچه Position از Traccar با محدودیت دسترسی و صفحه‌بندی cursor-based.
- map-positions: دریافت موقعیت‌های فعلی Traccar و Overlay تطبیق Neshan.

در گزارش تاریخچه، هر Position با شناسه واقعی Position ترکار نگه داشته می‌شود تا نتیجه map matching با همان شناسه مرتبط شود.

### APIهای اصلی fleet

| مسیر | کاربرد |
|---|---|
| /api/vehicle-types/ | انواع خودرو |
| /api/vehicles/ | خودروها |
| /api/device-models/ | کاتالوگ مدل‌های تأییدشده، فقط خواندنی |
| /api/devices/ | دستگاه‌ها |
| /api/devices/report-history/ | تاریخچه مسیر |
| /api/devices/map-positions/ | موقعیت زنده |
| /api/devices/map-matching-activity/ | heartbeat نشست نقشه |
| /api/drivers/ | رانندگان |
| /api/driver-vehicle-assignments/ | تاریخچه تخصیص راننده |
| /api/device-lifecycle-events/ | رویدادهای چرخه عمر |
| /api/device-replacement-relations/ | روابط جایگزینی |
| /api/device-operations/ | عملیات دستگاه |

## ۶.۵. dashboard

فایل‌ها:

- dashboard/models.py
- dashboard/views.py
- dashboard/urls.py

دو مسئولیت اصلی:

1. آمار داشبورد از داده‌های تجاری و ناوگان.
2. تنظیمات سراسری سایت.

SiteSettings یک رکورد singleton با شناسه ثابت ۱ است و شامل:

- map_provider: leaflet-osm یا neshan-leaflet.
- map_refresh_interval_seconds: بازه به‌روزرسانی نقشه، بین ۵ تا ۳۰۰ ثانیه و مقدار پیش‌فرض ۱۰.
- updated_at.

APIها:

- GET /api/dashboard/stats/
- GET /api/site-settings/
- PATCH /api/site-settings/

## ۶.۶. ops_monitoring

فایل‌ها:

- ops_monitoring/views.py
- ops_monitoring/urls.py
- ops_monitoring/deploy/sana-gps-network-capture

این ماژول ابزار تشخیصی ادمین سایت است و مدل تجاری جداگانه‌ای ندارد.

تمام endpointهای آن به احراز هویت و نقش site_admin محدود هستند.

### لاگ زنده

GET /api/gps-monitor/logs/

منابع لاگ در کد فعلی:

- sana-gps.service
- traccar.service
- sana-backend.service
- postgresql.service
- پیام‌های warning و بالاتر سیستم

لاگ‌ها با Server-Sent Events (SSE) به مرورگر فرستاده می‌شوند. در صورت قطع مرورگر، فرایندهای reader خاتمه داده می‌شوند.

### عملیات پورت Traccar

POST /api/gps-monitor/ports/

عملیات API شامل آزمون اتصال REST API و عملیات مدیریتی پورت است. درخواست‌های مدیریتی از helper سطح سیستم‌عامل عبور می‌کنند و فقط ادمین اجازه فراخوانی دارد.

Helper اصلی نصب‌شده:

/usr/local/sbin/sana-traccar-port-manager

این ابزار برای عملیات allowlist شده مانند بررسی وضعیت، عیب‌یابی، تنظیم پروتکل/پورت، آزمون ترافیک، بازیابی و ترمیم مجوزها استفاده می‌شود. تغییر تنظیم Traccar باید با کنترل تداخل پورت و بررسی وضعیت Listener انجام شود.

### Capture خام

برای Capture خام، پورت ثابت آزمون در Backend برابر ۱۲۵۶ است. کاربر ادمین باید صریحاً Capture را شروع کند. درخواست Capture روی پورت دلخواه پذیرفته نمی‌شود.

- Capture موقت است و start/stop/status دارد.
- برای جلوگیری از ثبت دائمی و بی‌رویه ترافیک، مسیر Capture از مسیر لاگ عادی جدا است.
- فایل Capture در مسیر عملیاتی تعریف‌شده در helper مدیریت پورت نگهداری می‌شود و سقف حجم در اسکریپت محدود شده است.
- endpoint مشاهده زنده Capture فقط پورت ثابت ۱۲۵۶ را قبول می‌کند.
- Capture نباید به‌عنوان ذخیره‌سازی دائمی Telemetry تلقی شود.

APIها:

- GET /api/gps-monitor/logs/
- POST /api/gps-monitor/ports/
- GET /api/gps-monitor/ports/capture/1256/

## ۶.۷. decoder_discovery

فایل‌ها:

- decoder_discovery/models.py
- decoder_discovery/discovery_engine.py
- decoder_discovery/sample_analysis.py
- decoder_discovery/internet_research.py
- decoder_discovery/tests.py

این ماژول مدل داده و ابزارهای اولیه برای بررسی پروتکل ناشناخته را فراهم می‌کند.

مدل‌ها:

- ReferenceSource: منبع مرجع برای جست‌وجوی Decoder.
- DiscoveryCase: پرونده بررسی شناسه/نمونه ناشناخته.
- DecoderCandidate: نامزد Decoder و اطلاعات منبع، نسخه، زبان، runtime، وابستگی و مجوز.
- CandidateTestRun: اجرای آزمون نامزد و گزارش نتیجه.
- PublishedDecoderVersion: نسخه Decoder منتشرشده با تأییدکننده و وضعیت فعال/غیرفعال.

ابزار تحلیل نمونه:

- طول داده.
- SHA-256.
- entropy.
- نسبت ASCII قابل چاپ.
- prefix و suffix به صورت hex.
- رشته‌های قابل چاپ.
- شمارش byteهای متمایز و صفر.

برای فریم‌های شبیه JT/T 808، کد می‌تواند شواهد اولیه framing و شناسه‌های احتمالی را استخراج کند؛ این شواهد به‌تنهایی تأیید پروتکل نیستند و checksum یا بدنه کامل پیام را اعتبارسنجی نمی‌کنند.

جست‌وجوی مرجع از DuckDuckGo و GitHub repository search استفاده می‌کند. طبق کد، کل payload خام برای جست‌وجوی وب ارسال نمی‌شود؛ فقط سرنخ‌های محدود و signature کوتاه استفاده می‌شوند.

**محدودیت وضعیت فعلی:** این ماژول در مخزن دارای مدل‌ها، توابع تحلیل و تست مدل است، اما در sana_core/urls.py مسیر API برای decoder_discovery ثبت نشده و سرویس sana-gps نیز در main.py این ماژول را به دریافت زنده متصل نمی‌کند. صفحه AIManagement فعلی نیز یک گردش‌کار نمایشی/مقدماتی است و اتصال کامل عملیاتی آن به API و Worker از کد فعلی تأیید نمی‌شود. بنابراین نباید آن را Decoder خودکار فعال در مسیر دریافت GPS معرفی کرد.

همچنین مسیر AI/auto_decoder_generator در وضعیت فعلی فقط فایل آغازین ماژول دارد و به‌تنهایی نشان‌دهنده یک سرویس اجرایی کامل نیست.

---

# ۷. Panel و لایه نقشه

## ۷.۱. sana-panel

Panel با React و Vite ساخته شده است. API client مرکزی در:

sana-panel/src/api/client.js

قرار دارد. توکن‌های دسترسی در درخواست‌ها استفاده می‌شوند و مسیرهای محافظت‌شده با ProtectedRoute و AuthContext کنترل می‌شوند. این کنترل سمت مرورگر برای تجربه کاربری است؛ کنترل امنیتی اصلی در Backend انجام می‌شود.

### مسیرهای اصلی رابط کاربری

| مسیر Panel | صفحه | کاربرد |
|---|---|---|
| /login | Login | ورود |
| /panel/dashboard | Dashboard | آمار و نمای کلی |
| /panel/map | Map | نقشه زنده |
| /panel/devices | Devices | فهرست و مدیریت دستگاه |
| /panel/vehicles | Vehicles | خودروها |
| /panel/drivers | Drivers | رانندگان |
| /panel/reports | Reports | بخش گزارش‌ها |
| /panel/reports/trips | DeviceTripReport | گزارش مسیر و بازپخش |
| /panel/reports/live-logs | LiveLogs | لاگ زنده مدیریتی |
| /panel/alerts | Alerts | صفحه هشدار فعلی |
| /panel/settings | Settings | تنظیمات و ابزارهای مدیریتی |
| /panel/companies | Companies | سازمان‌ها |
| /panel/branches | Branches | شعب |
| /panel/users | Users | کاربران |
| /panel/subscriptions | Subscriptions | قراردادها |
| /panel/subscriptions/new | SubscriptionWizard | ساخت قرارداد |
| /panel/subscriptions/:id | SubscriptionDetail | جزئیات و عملیات قرارداد |
| /panel/ai | AIManagement | صفحه مقدماتی مدیریت کشف Decoder |

دسترسی هر صفحه علاوه بر ProtectedRoute باید با مجوز API متناظر Backend هماهنگ باشد.

## ۷.۲. نقشه زنده

فایل:

sana-panel/src/pages/Map.jsx

فرایند:

1. تنظیمات نقشه از /api/site-settings/ خوانده می‌شود.
2. صفحه هر ۱۵ ثانیه heartbeat تطبیق نقشه می‌فرستد.
3. موقعیت‌های زنده از /api/devices/map-positions/ دریافت می‌شوند.
4. بازه polling از map_refresh_interval_seconds تنظیم می‌شود.
5. داده‌ها به LiveDeviceMap ارسال می‌شوند.
6. Provider انتخابی نقشه، Marker و مسیر را رسم می‌کند.

## ۷.۳. sana-map

لایه مشترک نقشه در sana-map/src قرار دارد.

Providerهای فعلی:

- OpenStreetMapLeafletMap
- NeshanLeafletMap

LiveDeviceMap رابط مشترک Panel با Providerها است. منبع داده و قرارداد Position مستقل از Provider نقشه باقی می‌ماند.

فایل config.js متغیرهای محیطی Provider پیش‌فرض و کلید/نوع نقشه نشان را می‌خواند. تنظیم Provider پیش‌فرض سراسری نیز از SiteSettings قابل تغییر است.

## ۷.۴. گزارش مسیر و بازپخش

فایل‌های اصلی:

- sana-panel/src/pages/DeviceTripReport.jsx
- sana-panel/src/components/DeviceReportPlayback.jsx
- sana-backend/fleet/views.py

گزارش تاریخی Positionها را از Traccar دریافت می‌کند، نه از جدول GPS موازی در SANA.

قابلیت‌های فعلی UI شامل انتخاب دستگاه، بازه زمانی جلالی، دریافت نقاط تاریخچه، نمایش مسیر، حرکت روی مسیر، آمار بازه، جزئیات نقطه انتخاب‌شده و خروجی CSV است.

Backend تاریخچه را با serverTime اعتبارسنجی و مرتب می‌کند و از cursor_time و cursor_id برای صفحه‌بندی استفاده می‌کند. این روش از تکرار یا جاافتادن نقطه‌هایی که زمان دریافت یکسان دارند جلوگیری می‌کند.

برای هر نقطه، اطلاعات خام Traccar و در صورت وجود Overlay تطبیق‌یافته Neshan در پاسخ ارائه می‌شود.

## ۷.۵. نمایش Attributeها و راهنمای پارامترها

دو لایه ارائه Attribute وجود دارد:

1. fleet/traccar_attributes.py: Registry سمت Backend برای نام فارسی، دسته‌بندی، نوع و واحدهایی که به‌صورت عمومی قابل اتکا هستند. Attribute ناشناخته حذف نمی‌شود و کلید اصلی آن حفظ می‌شود.
2. DeviceReportPlayback.jsx: نمایش مقادیر و عنوان‌های فارسی در جزئیات نقطه گزارش.

در نمایش گزارش، مقادیر خام Attributes همچنان از Traccar می‌آیند. تغییر عنوان فارسی نباید مقدار خام یا کلید اصلی را تغییر دهد.

برای دستگاه Teltonika FMB920 عنوان‌های کوتاه و Tooltipهای مصوب در UI گزارش قرار گرفته‌اند؛ از جمله priority، io200، io69، pdop، io68 و operator. Tooltip با Hover و لمس عنوان فعال می‌شود. توضیح priority به معنی اولویت ارسال بسته AVL است و نباید به‌عنوان سطح خطر یا دکمه اضطراری تفسیر شود.

نمونه عنوان‌ها:

| کلید | عنوان |
|---|---|
| priority | اولویت |
| io200 | خواب |
| io69 | ماهواره |
| pdop | دقت |
| io68 | جریان |
| operator | اپراتور |

نام‌های مشابه در UI به معنی یکسان بودن داده خام نیستند. برای مثال odometer و totalDistance می‌توانند منبع یا مبنای محاسبه متفاوت داشته باشند و نباید صرفاً به دلیل شباهت عنوان، در داده اصلی ادغام شوند.

## ۷.۶. هشدار و اعلان

صفحه Alerts فعلی از داده اولیه محلی در sana-panel/src/data/alertsData.js استفاده می‌کند. صفحه تنظیمات اعلان نیز از داده تنظیمات محلی استفاده می‌کند.

در کد فعلی:

- مدل Django اختصاصی برای Notification وجود ندارد.
- API مرکزی اعلان ثبت نشده است.
- سرویس ارسال Push، SMS یا Email در این مخزن به‌عنوان مسیر فعال اعلان تعریف نشده است.
- صفحه Alerts را نباید سامانه اعلان عملیاتی و متصل به رخدادهای مالی یا GPS تلقی کرد.

پیاده‌سازی اعلان‌های واقعی، از جمله اعلان مالی، هشدار دستگاه و توزیع اعلان بر اساس نقش و مجوز، نیازمند طراحی و اتصال Backend، ذخیره‌سازی، سیاست گیرنده و کانال ارسال است.

---

# ۸. مدل داده و جداول PostgreSQL

پایگاه داده SANA یک PostgreSQL مشترک برای Backend و سرویس sana-gps است. Backend از Django ORM و GPS worker از psycopg استفاده می‌کند.

نام دیتابیس پیش‌فرض در تنظیمات sana_db و نام نقش برنامه sana_user است. هر دو سرویس از همان پایگاه داده استفاده می‌کنند؛ اما مسئولیت آن‌ها متفاوت است.

## ۸.۱. جداول accounts

| جدول | مدل | کاربرد |
|---|---|---|
| accounts_user | User | حساب کاربری سفارشی SANA |
| accounts_user_groups | رابطه User و Group | گروه‌های مجوز Django |
| accounts_user_user_permissions | رابطه User و Permission | مجوزهای مستقیم کاربر |

به‌دلیل استفاده از AbstractBaseUser و PermissionsMixin، جداول احراز هویت Django نیز وجود دارند.

## ۸.۲. جداول organizations

| جدول | مدل | کاربرد و ارتباط |
|---|---|---|
| organizations_organization | Organization | مشتری سازمانی |
| organizations_branch | Branch | شعبه متعلق به Organization |
| organizations_subscription | Subscription | قرارداد سازمانی یا شخصی |
| organizations_subscriptionoperation | SubscriptionOperation | عملیات قرارداد |
| organizations_subscriptionoperationchange | SubscriptionOperationChange | تغییرات فیلدی عملیات |
| organizations_subscriptiondevice | SubscriptionDevice | رابطه تاریخی قرارداد و Device |
| organizations_subscriptionpayment | SubscriptionPayment | دریافت وجه |
| organizations_subscriptioninstallmentplan | SubscriptionInstallmentPlan | نسخه برنامه اقساط |
| organizations_subscriptioninstallment | SubscriptionInstallment | اقساط یک نسخه برنامه |
| organizations_subscriptionpaymentallocation | SubscriptionPaymentAllocation | تخصیص دریافتی به قسط یا پیش‌پرداخت |

روابط اصلی:

~~~text
Organization
  ├── Branch
  ├── User
  ├── Vehicle
  ├── Device
  └── Subscription
        ├── SubscriptionOperation
        │     ├── SubscriptionOperationChange
        │     └── SubscriptionPayment (در صورت ارتباط با عملیات)
        ├── SubscriptionDevice ───────── Device
        ├── SubscriptionPayment
        │     └── SubscriptionPaymentAllocation
        │               └── SubscriptionInstallment
        └── SubscriptionInstallmentPlan
                  └── SubscriptionInstallment
~~~

Subscription برای مشتری شخصی می‌تواند به User مرتبط شود و برای مشتری سازمانی به Organization. این دو مسیر مالک قرارداد باید مطابق نوع مشتری اعتبارسنجی شوند.

## ۸.۳. جداول fleet

| جدول | مدل | کاربرد |
|---|---|---|
| fleet_vehicletype | VehicleType | انواع خودرو |
| fleet_vehicle | Vehicle | خودرو |
| fleet_devicemodel | DeviceModel | کاتالوگ مدل GPS |
| fleet_device | Device | دستگاه GPS و IMEI |
| fleet_deviceownershiphistory | DeviceOwnershipHistory | تاریخچه مالکیت |
| fleet_devicecustomeraccessperiod | DeviceCustomerAccessPeriod | دوره دسترسی مشتری به دستگاه |
| fleet_deviceoperation | DeviceOperation | عملیات دستگاه |
| fleet_devicereplacementrelation | DeviceReplacementRelation | ارتباط دستگاه قبلی و جایگزین |
| fleet_driver | Driver | راننده |
| fleet_drivervehicleassignment | DriverVehicleAssignment | تاریخچه تخصیص راننده به خودرو |
| fleet_devicelifecycleevent | DeviceLifecycleEvent | رویدادهای چرخه عمر دستگاه |

روابط اصلی:

~~~text
Organization / User
      │
      ├── Vehicle ───── VehicleType
      │     └── Device.vehicle
      │
      ├── Driver
      │     └── DriverVehicleAssignment ─── Vehicle
      │
      └── Device
            ├── DeviceModel
            ├── SubscriptionDevice ─── Subscription
            ├── DeviceOwnershipHistory
            ├── DeviceCustomerAccessPeriod
            ├── DeviceOperation
            ├── DeviceReplacementRelation
            └── DeviceLifecycleEvent
~~~

DeviceOwnershipHistory، DeviceCustomerAccessPeriod و SubscriptionDevice سه جدول مستقل با معنی متفاوت هستند.

## ۸.۴. جداول dashboard

| جدول | مدل | کاربرد |
|---|---|---|
| dashboard_sitesettings | SiteSettings | تنظیمات singleton سراسری سایت |

## ۸.۵. جداول decoder_discovery

| جدول | مدل | کاربرد |
|---|---|---|
| decoder_discovery_referencesource | ReferenceSource | منابع جست‌وجوی Decoder |
| decoder_discovery_discoverycase | DiscoveryCase | پرونده بررسی نمونه/شناسه |
| decoder_discovery_decodercandidate | DecoderCandidate | نامزد Decoder |
| decoder_discovery_candidatetestrun | CandidateTestRun | گزارش اجرای آزمون |
| decoder_discovery_publisheddecoderversion | PublishedDecoderVersion | نسخه منتشرشده و تأییدشده |

این جداول در مدل Django تعریف شده‌اند؛ اما وجود آن‌ها به معنی فعال بودن API یا Worker عملیاتی کشف Decoder نیست.

## ۸.۶. جداول پیش‌فرض Django

بسته به Migrationهای نصب‌شده، جداول زیر نیز در پایگاه داده وجود دارند:

- django_migrations
- django_content_type
- auth_permission
- auth_group
- auth_group_permissions
- django_admin_log
- django_session

جداول رابطه کاربر با گروه و مجوز نیز توسط Django ساخته می‌شوند. نام دقیق جداول سیستمی باید از schema واقعی همان نصب بررسی شود.

## ۸.۷. Schema اختصاصی gps

فایل SQL رسمی فعلی:

sana-gps/sql/0001_traccar_authoritative_schema.sql

در schema gps فقط داده‌های تکمیلی موردنیاز این معماری ساخته می‌شوند.

### gps.map_matched_position

نتیجه تطبیق جاده را به Position اصلی Traccar متصل می‌کند.

| ستون | کاربرد |
|---|---|
| id | شناسه داخلی SANA |
| traccar_position_id | شناسه Position در Traccar؛ یکتا |
| traccar_device_id | شناسه Device در Traccar |
| device_id | FK به public.fleet_device |
| device_time | زمان انتخاب‌شده برای نقطه |
| matched_latitude | عرض جغرافیایی تطبیق‌یافته |
| matched_longitude | طول جغرافیایی تطبیق‌یافته |
| matched_geom | هندسه PostGIS از نوع Point با SRID 4326 |
| match_provider | Provider تطبیق؛ پیش‌فرض neshan |
| matched_at | زمان ثبت نتیجه |

قیدها و Indexهای مهم:

- traccar_position_id یکتا است تا یک Position دوبار نتیجه تطبیق ثبت نکند.
- device_id به fleet_device.id متصل است و با حذف Device، رکوردهای وابسته حذف می‌شوند.
- مختصات در محدوده معتبر جغرافیایی کنترل می‌شوند.
- Index روی device_id و device_time برای بازیابی تاریخچه وجود دارد.
- Index روی device_id و matched_at برای بازیابی نتایج اخیر وجود دارد.

### gps.map_matching_watchers

نشست‌های فعال نقشه را نگه می‌دارد.

| ستون | کاربرد |
|---|---|
| session_id | شناسه نشست و کلید اصلی |
| user_id | شناسه کاربر ارسال‌کننده heartbeat |
| expires_at | زمان انقضای نشست |
| updated_at | آخرین به‌روزرسانی |

user_id در SQL فعلی Foreign Key به accounts_user تعریف نشده است؛ این جدول یک مکانیزم heartbeat کوتاه‌عمر است، نه جدول مالکیت یا تاریخچه کاربران.

## ۸.۸. جدول‌هایی که عمداً در schema فعلی GPS وجود ندارند

SQL فعلی قبل از ساخت schema جدید، جدول‌ها و توابع قدیمی GPS را حذف می‌کند. این موارد در schema نهایی ساخته نمی‌شوند:

- gps.raw_packet
- gps.location_history
- gps.current_state
- gps.event
- gps.trip
- gps.geofence
- gps.geofence_version
- gps.geofence_assignment
- gps.vehicle_geofence_state
- gps.traccar_unknown_device

همچنین تابع‌ها و sequenceهای قدیمی مرتبط با ذخیره/پاک‌سازی Telemetry حذف می‌شوند.

بنابراین مستند یا کد جدید نباید فرض کند SANA دارای مخزن خام GPS یا جدول current_state است. مرجع این داده‌ها Traccar است.

---

# ۹. قواعد مهم رابطه‌ها و یکپارچگی داده

## ۹.۱. IMEI

- IMEI در fleet_device یکتا است.
- IMEI کلید تطبیق SANA با Traccar Device.uniqueId است.
- ثبت یک IMEI تکراری باید در سطح دیتابیس رد شود.
- شناسه Traccar Device.id جایگزین IMEI نیست.

## ۹.۲. مالکیت و تحویل

- مالکیت سازمانی و شخصی دو مسیر جدا هستند.
- DeviceOwnershipHistory باید دقیقاً یک مالک از نوع Organization یا User داشته باشد.
- تحویل‌گیرنده فعلی می‌تواند از مالکیت قانونی مستقل باشد.
- تغییر مشتری باید تاریخچه مالکیت و دوره دسترسی را با عملیات مربوط هماهنگ کند.

## ۹.۳. قرارداد و دستگاه

- SubscriptionDevice تاریخچه اتصال دستگاه به قرارداد است.
- اتصال فعال با unassigned_at تهی شناخته می‌شود، اما اعتبار آن به تاریخ شروع/پایان و وضعیت مؤثر قرارداد هم وابسته است.
- ایجاد اتصال جدید، اتصال باز قبلی همان دستگاه را می‌بندد.
- پایان قرارداد و پایان تخصیص دستگاه مفاهیم جدا هستند.
- دستگاهی که قرارداد فعال ندارد، نباید به‌عنوان سرویس فعال مشتری گزارش شود.

## ۹.۴. خودرو و راننده

- تخصیص راننده به خودرو بازه زمانی دارد.
- بازه‌های متداخل برای یک خودرو رد می‌شوند.
- راننده و خودرو باید از نظر سازمان و در صورت تعیین، شعبه سازگار باشند.
- Device.vehicle رابطه نصب فعلی دستگاه با خودرو است؛ تاریخچه جابه‌جایی در رویدادها و عملیات نگهداری می‌شود.

## ۹.۵. عملیات و ممیزی

عملیات مهم دستگاه و قرارداد باید در رکوردهای عملیات و رویدادهای مرتبط قابل پیگیری باشند. حذف مستقیم رکوردهای تاریخی یا دستکاری وضعیت بدون ثبت عملیات می‌تواند تاریخچه و گزارش را ناسازگار کند.

---

# ۱۰. امنیت، نقش‌ها و محدوده دسترسی

## ۱۰.۱. احراز هویت

- ورود با نام کاربری و رمز عبور.
- JWT برای درخواست‌های API.
- احراز هویت در هر درخواست با بررسی وضعیت فعال حساب و قرارداد.
- عمر Access Token دو ساعت و Refresh Token هفت روز.
- APIهای حساس باید در Backend Permission مستقل داشته باشند.

## ۱۰.۲. نقش‌ها و محدوده داده

| نقش | محدوده اصلی |
|---|---|
| site_admin | دسترسی مدیریتی سراسری |
| main_user | داده سازمان خود |
| branch_manager | داده سازمان و شعبه مجاز |
| personal_user | داده‌های متعلق به حساب شخصی و دوره دسترسی معتبر |

فیلتر QuerySet در ViewSetها مرز اصلی جلوگیری از مشاهده داده مشتری دیگر است. مخفی‌کردن منو یا Route در React جایگزین این کنترل نیست.

## ۱۰.۳. دسترسی تاریخی دستگاه

برای رویدادهای چرخه عمر و عملیات دستگاه، دسترسی مشتری می‌تواند بر اساس DeviceCustomerAccessPeriod و تاریخ وقوع رویداد محاسبه شود. این موضوع اجازه می‌دهد کاربر رویدادهای دوره‌ای را که دستگاه در اختیار او بوده مشاهده کند، بدون اینکه لزوماً مالک فعلی دستگاه باشد.

## ۱۰.۴. عملیات فقط ادمین

عملیات مدیریتی حساس از جمله مدیریت دستگاه، عملیات چرخه عمر، تنظیمات مدیریتی Traccar و مشاهده لاگ‌های سیستمی به نقش site_admin محدود شده‌اند؛ جزئیات هر endpoint باید از get_permissions و get_queryset همان ViewSet بررسی شود.

---

# ۱۱. پیکربندی و متغیرهای محیطی

مقادیر محرمانه نباید در Git یا مستندات عملیاتی ثبت شوند. نام متغیرها مستند می‌شود، نه مقدار واقعی رمزها و کلیدها.

## ۱۱.۱. Django

متغیرهای اصلی:

- SECRET_KEY
- DEBUG
- ALLOWED_HOSTS
- DB_NAME
- DB_USER
- DB_PASSWORD
- DB_HOST
- DB_PORT
- TRACCAR_API_URL
- TRACCAR_API_USERNAME
- TRACCAR_API_PASSWORD
- CORS_ALLOWED_ORIGINS

Backend از فایل تنظیمات Django و محیط سرویس systemd مقدارها را دریافت می‌کند.

## ۱۱.۲. sana-gps

متغیرهای اصلی:

- SANA_GPS_DB_HOST
- SANA_GPS_DB_PORT
- SANA_GPS_DB_NAME
- SANA_GPS_DB_USER
- SANA_GPS_DB_PASSWORD
- SANA_GPS_DB_POOL_MIN
- SANA_GPS_DB_POOL_MAX
- SANA_GPS_LOG_LEVEL
- SANA_GPS_TRACCAR_API_URL
- SANA_GPS_TRACCAR_API_USERNAME
- SANA_GPS_TRACCAR_API_PASSWORD
- SANA_GPS_TRACCAR_SYNC_INTERVAL
- NESHAN_MAP_MATCHING_API_KEY

مقادیر پیش‌فرض کد:

- DB host: 127.0.0.1
- DB port: 5432
- DB user: sana_user
- Pool min: 2
- Pool max: 10
- Traccar API: http://127.0.0.1:8082/api
- Sync interval: 60 ثانیه
- Log level: INFO

نام دیتابیس و رمز اتصال باید در محیط واقعی تنظیم شوند. SANA_GPS_DB_USER در کد فعلی باید sana_user باشد.

Pool هنگام اتصال، timezone نشست PostgreSQL را روی Asia/Tehran تنظیم می‌کند.

## ۱۱.۳. Panel و Map

متغیرهای اصلی:

- VITE_API_URL
- VITE_MAP_PROVIDER
- VITE_NESHAN_API_KEY
- VITE_NESHAN_MAP_TYPE

Providerهای فعلی:

- leaflet-osm
- neshan-leaflet

## ۱۱.۴. تنظیمات Traccar

تنظیمات واقعی Traccar در فایل نصب‌شده روی سرور، معمولاً traccar.xml، قرار دارند و بخشی از migration دیتابیس Django نیستند.

- API محلی باید برای Backend و GPS worker قابل دسترسی باشد.
- پورت‌های Listener باید با پروتکل‌های فعال و پیکربندی واقعی Traccar مطابقت داشته باشند.
- تغییر پورت باید از ابزار مدیریتی کنترل‌شده انجام شود.
- رمز API و تنظیمات محرمانه نباید در مخزن ثبت شوند.
- Traccar و دیتابیس خودش مستقل از دیتابیس SANA هستند.

---

# ۱۲. ساخت دیتابیس تازه و اسکریپت Reset

اسکریپت:

scripts/reset_sana_db.sh

**هشدار: اجرای این اسکریپت مخرب است و دیتابیس sana_db را حذف و دوباره ایجاد می‌کند.** همه داده‌های تجاری، کاربران، قراردادها، دستگاه‌ها و داده‌های اختصاصی SANA در آن دیتابیس از بین می‌روند. اسکریپت فعلی قبل از حذف، Backup خودکار از دیتابیس تهیه نمی‌کند.

## ۱۲.۱. مراحل فعلی اسکریپت

1. تشخیص ریشه مخزن و مسیر Backend/GPS.
2. بررسی فایل‌ها، محیط مجازی Python، psql، sudo و systemctl.
3. بررسی وجود SQLهای موردنیاز.
4. دریافت تأیید صریح نام دیتابیس از اپراتور.
5. دریافت مشخصات Traccar و ثبت آن در فایل محافظت‌شده /etc/sana-gps.env.
6. ساخت یا به‌روزرسانی Drop-in سرویس Backend برای EnvironmentFile.
7. اعتبارسنجی sudo.
8. توقف sana-gps و sana-backend.
9. بررسی وجود نقش PostgreSQL sana_user.
10. حذف و ساخت دوباره دیتابیس با مالک sana_user.
11. فعال‌سازی PostGIS.
12. اجرای 0000_roles.sql برای نقش و schema پایه.
13. اجرای Migrationهای Django.
14. اجرای sync_traccar_device_catalog برای پرکردن کاتالوگ مدل‌ها.
15. اجرای manage.py check و makemigrations --check --dry-run.
16. اجرای SQL رسمی GPS یعنی 0001_traccar_authoritative_schema.sql.
17. بررسی اتصال دیتابیس، کاربر جاری، PostGIS و آخرین Migrationها.
18. ساخت سوپریوزر Django به‌صورت تعاملی.
19. راه‌اندازی sana-backend و sana-gps.
20. بررسی فعال‌بودن سرویس‌ها و شنود Backend روی پورت ۸۰۰۰.

اسکریپت پنل Vite را مدیریت نمی‌کند و تنظیمات نصب Traccar یا مجوزهای Router را نیز جایگزین نمی‌کند.

## ۱۲.۲. SQL پایه نقش

فایل:

sana-gps/sql/0000_roles.sql

کارهای اصلی:

- ایجاد یا اصلاح نقش login به نام sana_user.
- جلوگیری از SUPERUSER، CREATEDB و CREATEROLE بودن نقش برنامه.
- اعطای مجوز لازم روی دیتابیس جاری.
- فعال‌سازی PostGIS.
- ساخت schema gps و تنظیم مالکیت آن.
- اعطای مجوزهای محدود لازم روی جداول عمومی مرتبط، در صورت وجود.

## ۱۲.۳. SQL نهایی GPS

فایل:

sana-gps/sql/0001_traccar_authoritative_schema.sql

این فایل schema اختصاصی تطبیق جاده و heartbeat را ایجاد می‌کند و ساختارهای قدیمی ذخیره خام GPS را حذف می‌کند.

## ۱۲.۴. نکته عملیاتی مهم

قبل از اجرای Reset روی سرور واقعی:

- از دیتابیس موجود Backup قابل بازیابی تهیه شود.
- نام دیتابیس و مالک بررسی شوند.
- فایل‌های Migration و SQL دقیقاً با main هماهنگ باشند.
- اعتبار REST API ترکار در فایل محیطی درست باشد.
- توقف سرویس‌ها و راه‌اندازی مجدد آن‌ها برنامه‌ریزی شود.
- پس از اجرا، وجود جداول، Migrationها، PostGIS، سوپریوزر، وضعیت سرویس‌ها و دریافت واقعی داده از Traccar جداگانه بررسی شود.

موفقیت اسکریپت Reset به‌تنهایی اثبات نمی‌کند که دستگاه فیزیکی به Traccar متصل است یا موقعیت واقعی در API قابل دریافت است.

---

# ۱۳. سرویس‌ها و عملیات محیط اجرا

سرویس‌های اصلی شناخته‌شده در محیط فعلی:

| سرویس | وظیفه |
|---|---|
| traccar.service | Listenerهای GPS، Decoder و API ترکار |
| sana-backend.service | Django API |
| sana-gps.service | همگام‌سازی Device و Map Matching |
| postgresql.service | دیتابیس SANA |

Panel در محیط توسعه با Vite اجرا می‌شود و در اسکریپت Reset مدیریت نمی‌شود.

## ۱۳.۱. راهنمای عیب‌یابی بر اساس مرز سرویس

### دستگاه داده نمی‌فرستد

1. اتصال شبکه و مسیر ورودی پورت را بررسی کن.
2. Listener واقعی Traccar برای پروتکل/پورت موردنظر را بررسی کن.
3. لاگ Traccar را ببین.
4. بررسی کن Traccar Device را با uniqueId درست می‌شناسد یا نه.
5. Positionهای API را بررسی کن.
6. پس از تأیید Position، ارتباط IMEI با fleet_device را بررسی کن.

### Traccar داده دارد ولی SANA نمایش نمی‌دهد

1. REST API و اعتبارنامه آن را بررسی کن.
2. مطابقت Traccar Device.uniqueId با fleet_device.imei را بررسی کن.
3. دسترسی کاربر، سازمان، شعبه، قرارداد و DeviceCustomerAccessPeriod را بررسی کن.
4. لاگ sana-backend و خطای API را بررسی کن.
5. در گزارش تاریخی serverTime و بازه انتخابی را بررسی کن.

### نقطه خام هست ولی روی جاده قرار نمی‌گیرد

1. بازبودن صفحه نقشه و heartbeat را بررسی کن.
2. وجود watcher معتبر در gps.map_matching_watchers را بررسی کن.
3. تنظیم NESHAN_MAP_MATCHING_API_KEY را بررسی کن.
4. لاگ sana-gps را برای خطای Neshan بررسی کن.
5. وجود رکورد متناظر در gps.map_matched_position را بررسی کن.

در این وضعیت مختصات خام باید همچنان قابل نمایش باشد.

### مدل یا پروتکل دستگاه نامشخص است

1. Position فعلی Traccar را بررسی کن.
2. فیلد protocol را ببین.
3. وضعیت Device.protocol در SANA را بررسی کن.
4. مدل انتخاب‌شده در کاتالوگ را از پروتکل واقعی گزارش‌شده جدا کن.
5. در صورت نیاز کاتالوگ Traccar را با فرمان مدیریت به‌روزرسانی کن.

---

# ۱۴. تست‌ها و کنترل کیفیت

## ۱۴.۱. تست‌های Backend

پوشه‌های تست شامل موارد زیر هستند:

- accounts/tests.py
- dashboard/tests.py
- fleet/tests.py
- fleet/test_permissions.py
- organizations/tests.py
- ops_monitoring/tests.py
- decoder_discovery/tests.py
- decoder_discovery/test_discovery_engine.py
- decoder_discovery/test_sample_intake.py

اجرای کامل:

~~~bash
cd sana-backend
python manage.py test --verbosity 2
~~~

## ۱۴.۲. تست‌های GPS worker

پوشه sana-gps/tests شامل تست تنظیمات، Pool، Repository، main، Map Matching و Traccar Client/Sync است.

~~~bash
cd sana-gps
python -m pytest -q
~~~

## ۱۴.۳. تست یکپارچه PostgreSQL/PostGIS

test_gps_postgres_integration.py دسترسی نقش sana_user، schema GPS و امکان به‌روزرسانی protocol در جدول fleet_device را بررسی می‌کند.

این تست از دیتابیس آزمایشی PostGIS استفاده می‌کند و نباید به دیتابیس عملیاتی متصل شود.

## ۱۴.۴. CI مهاجرت Django

Workflow:

.github/workflows/sana-django-migrations.yml

موارد بررسی‌شده در Workflow:

- نصب Python 3.12 و وابستگی‌های Django.
- PostgreSQL/PostGIS.
- اجرای Migration روی دیتابیس تازه.
- اجرای makemigrations --check --dry-run.
- اجرای کامل تست Backend.
- بررسی وجود جدول‌های اصلی و نبود جدول‌های بازنشسته GPS.
- بررسی کاتالوگ DeviceModel.
- بررسی ارتقا از زنجیره تاریخی Migrationها.
- بررسی وضعیت‌های نیمه‌اعمال‌شده تاریخی fleet و حفظ داده Device.

## ۱۴.۵. CI سرویس GPS

Workflow:

.github/workflows/sana-gps-tests.yml

موارد بررسی‌شده:

- نصب وابستگی‌های sana-gps.
- اجرای pytest.
- ایجاد جداول حداقلی ناوگان در PostgreSQL آزمایشی.
- اجرای SQL نقش و PostGIS.
- اجرای SQL schema نهایی GPS.
- آزمون دسترسی sana_user و Integration Test.

## ۱۴.۶. CI پنل

Workflow:

.github/workflows/sana-panel-build.yml

اسکریپت‌های محلی پنل:

~~~bash
cd sana-panel
npm run lint
npm run build
~~~

تست Build پنل جایگزین بررسی عملکرد UI با داده واقعی و API عملیاتی نیست.

---

# ۱۵. قابلیت‌های موجود و مواردی که هنوز نباید فعال فرض شوند

این بخش برای جلوگیری از برداشت اشتباه از نام فایل‌ها یا طرح‌های قدیمی است.

| موضوع | وضعیت در کد فعلی |
|---|---|
| دریافت و Decoder پروتکل GPS | فعال در Traccar |
| ذخیره خام GPS و تاریخچه Position | در Traccar |
| دریافت مستقیم TCP/UDP در sana-gps | غیرفعال/وجود ندارد |
| وب‌هوک Position از Traccar به sana-gps | در main.py غیرفعال/وجود ندارد |
| همگام‌سازی IMEIهای ثبت‌شده SANA به Traccar | پیاده‌سازی شده |
| واردکردن خودکار Device ناشناخته Traccar به SANA | پیاده‌سازی نشده |
| همگام‌سازی protocol از Traccar به fleet_device | پیاده‌سازی شده |
| نقشه زنده از API ترکار | پیاده‌سازی شده |
| گزارش تاریخچه از API ترکار | پیاده‌سازی شده |
| Map Matching نشان هنگام حضور Viewer نقشه | پیاده‌سازی شده |
| نگهداری Position خام در SANA | عمداً انجام نمی‌شود |
| نگهداری نتیجه Map Matching در SANA | پیاده‌سازی شده |
| عملیات مالی قرارداد و تخصیص پرداخت/قسط | مدل و منطق Backend پیاده‌سازی شده |
| اعلان واقعی مالی/GPS با کانال ارسال | در کد فعلی پیاده‌سازی نشده |
| صفحه Alerts | داده اولیه محلی/نمایشی |
| تنظیمات اعلان | در وضعیت فعلی محلی/نمایشی |
| Decoder Discovery | مدل‌ها و ابزارهای تحلیل اولیه موجود؛ اتصال کامل به Runtime و API تأیید نشده |
| صفحه AIManagement | صفحه مقدماتی؛ گردش‌کار اجرایی کامل از کد فعلی تأیید نمی‌شود |
| لاگ زنده سرویس‌ها برای ادمین | پیاده‌سازی شده |
| Capture خام شبکه | ابزار تشخیصی محدود و صریحاً آغازشونده توسط ادمین |
| Redis | در معماری فعلی استفاده نمی‌شود |

---

# ۱۶. قواعد توسعه و نگهداری آینده

هر تغییر جدید باید با اصول زیر سازگار باشد:

1. Traccar تنها مرجع داده خام GPS و Position باقی بماند.
2. هیچ جدول خام GPS موازی در SANA بدون تصمیم معماری صریح اضافه نشود.
3. شناسه Position ترکار برای اتصال داده‌های تکمیلی استفاده شود؛ شناسه‌های داخلی دو سیستم با هم اشتباه نشوند.
4. خطای Neshan نباید دریافت و نمایش Position خام را متوقف کند.
5. Map Matching فقط هنگام وجود Viewer فعال نقشه اجرا شود.
6. داده‌های خام Attributes حذف نشوند؛ کلیدهای ناشناخته باید قابل مشاهده و قابل بررسی بمانند.
7. واحدها فقط زمانی نمایش داده شوند که برای منبع مربوط معتبر باشند.
8. مدل انتخاب‌شده در کاتالوگ با پروتکل واقعی گزارش‌شده توسط Traccar یکی فرض نشود.
9. مالکیت، تحویل‌گیرنده، دوره دسترسی مشتری و اتصال قراردادی دستگاه جداگانه نگهداری شوند.
10. تغییرات چرخه عمر دستگاه از مسیر عملیات و رویدادهای مرتبط انجام شوند تا تاریخچه از بین نرود.
11. پرداخت واقعی، تخصیص پرداخت و قسط سه مفهوم مجزا هستند؛ مانده مالی از روی تخصیص‌ها محاسبه شود.
12. مجوزهای دسترسی در Backend اعمال شوند؛ محدودسازی UI به‌تنهایی کافی نیست.
13. کد و آرتیفکت Decoder ناشناخته نباید در مسیر عملیاتی GPS اجرا شود.
14. قبل از انتشار Migration جدید، مسیر نصب تازه و ارتقای دیتابیس موجود آزمایش شود.
15. Reset دیتابیس عملیاتی بدون Backup قابل بازیابی و تأیید صریح انجام نشود.
16. مستندات باید پس از تغییر واقعی کد به‌روزرسانی شوند؛ طرح آینده نباید به‌عنوان قابلیت فعال نوشته شود.

---

# ۱۷. نقشه فایل‌های مرجع برای تغییرات متداول

| موضوع تغییر | فایل‌های مرجع |
|---|---|
| نقش، ورود و مجوز کاربر | accounts/models.py، authentication.py، permissions.py |
| قرارداد و امور مالی | organizations/models.py، views.py، serializers.py |
| چرخه عمر دستگاه | fleet/device_operations.py، fleet/lifecycle.py، fleet/models.py |
| نگاشت Traccar به Device | fleet/traccar_api.py، fleet/views.py، sana-gps/app/traccar/ |
| نگاشت Attributeهای ترکار | fleet/traccar_attributes.py |
| گزارش مسیر | fleet/views.py، DeviceReportPlayback.jsx، DeviceTripReport.jsx |
| نقشه زنده | fleet/views.py، Map.jsx، sana-map/src/ |
| Map Matching | sana-gps/app/processing/map_matching.py، sana-gps/sql/0001... |
| تنظیمات سراسری | dashboard/models.py، dashboard/views.py، Settings.jsx |
| لاگ و Capture | ops_monitoring/views.py، scripts/sana-traccar-live-capture، scripts/sana-traccar-port-manager |
| کشف پروتکل | decoder_discovery/ |
| بازسازی دیتابیس | scripts/reset_sana_db.sh، sana-gps/sql/، Django migrations |
| تست مهاجرت | .github/workflows/sana-django-migrations.yml |
| تست GPS | .github/workflows/sana-gps-tests.yml |

---

# ۱۸. واژه‌نامه

| اصطلاح | معنی در SANA |
|---|---|
| IMEI | شناسه دستگاه GPS که در SANA یکتا است |
| Traccar Device.id | شناسه داخلی Device در Traccar |
| Traccar Device.uniqueId | شناسه‌ای که در SANA با IMEI تطبیق داده می‌شود |
| Position | یک رکورد موقعیت در Traccar |
| Position.id | شناسه یکتای Position در Traccar |
| serverTime | زمان دریافت/ثبت Position از دید سرور |
| fixTime | زمان Fix موقعیت |
| deviceTime | زمان اعلام‌شده توسط دستگاه |
| protocol | نام Decoder/پروتکل گزارش‌شده توسط Traccar |
| Attributes | فیلدهای تکمیلی وابسته به پروتکل و دستگاه |
| Map Matching | تطبیق مختصات مسیر با شبکه راه‌ها |
| Raw Position | موقعیت اصلی ثبت‌شده در Traccar |
| Matched Position | مختصات Snap شده که SANA برای نمایش مسیر نگه می‌دارد |
| Ownership | مالکیت قانونی دستگاه |
| Customer Access Period | دوره مجاز دسترسی مشتری به دستگاه |
| SubscriptionDevice | اتصال تاریخی دستگاه به قرارداد |
| Management Status | وضعیت مدیریتی/فیزیکی دستگاه در SANA |
| Online Status | وضعیت ارتباط دستگاه از دید Traccar |
| SSE | انتقال رویداد/لاگ زنده از سرور به مرورگر |

---

## ۱۹. قاعده نهایی مرجعیت

در صورت اختلاف میان این سند و کد اجرایی، ابتدا کد و Migrationهای شاخه main بررسی می‌شوند و سپس همین سند اصلاح می‌شود. در صورت اختلاف میان موقعیت خام و نتیجه تطبیق، Position خام Traccar مرجع اصلی باقی می‌ماند. در صورت اختلاف میان عنوان نمایشی و کلید Attribute، کلید و مقدار اصلی Traccar حفظ می‌شوند.

این مستند توصیف وضعیت پیاده‌سازی در Commit مبنای ابتدای سند است؛ پس از هر تغییر معماری یا Migration مهم باید Commit مبنا و تاریخ بازبینی آن به‌روزرسانی شوند.
