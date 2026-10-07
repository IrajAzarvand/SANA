# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry

> این سند شامل تصمیماتی است که تا این مرحله درباره معماری GPS، دریافت داده و ساختار `Normalized Telemetry` در پروژه SANA قطعی شده‌اند.
>
> **وضعیت:** سند تجمیعی تصمیمات معماری قطعی GPS/Telemetry تا مرحله Protocol Decoder و Normalization؛ Implementation هنوز شروع نشده است.

---

## 1. معماری کلی GPS

پروژه SANA از چند بخش اصلی تشکیل می‌شود:

```text
SANA/
├── sana-backend/      → Django، منطق کسب‌وکار، API، احراز هویت و دسترسی‌ها
├── sana-gps/          → دریافت و پردازش داده GPS
├── sana-panel/        → پنل وب
└── sana-mobile/       → اپلیکیشن موبایل در آینده
```

`सana-gps` مسئول دریافت و پردازش داده GPS است و نباید منطق کسب‌وکار SANA را در خود داشته باشد.

### مسئولیت‌های sana-gps

* TCP
* UDP
* مدیریت Connection / Session
* ACK
* تشخیص Protocol
* Protocol Decoder
* Protocol Normalizer
* تبدیل داده پروتکل به ساختار استاندارد SANA
* اعتبارسنجی فنی داده
* نگهداری موقت Raw Packet
* پردازش Telemetry
* Current State
* Location History

### مواردی که sana-gps مسئول آن‌ها نیست

* User
* Permission
* Customer
* Organization
* Branch
* Contract
* Subscription
* Driver
* منطق کسب‌وکار

این موارد متعلق به `sana-backend` هستند.

---

# 2. معماری پردازش داده

مسیر کلی داده:

```text
GPS Device
    ↓
TCP / UDP
    ↓
sana-gps
    ↓
Framing / Protocol Detection
    ↓
Protocol Decoder
    ↓
ProtocolMessage
    ↓
Normalizer
    ↓
Normalized Telemetry
    ↓
┌───────────────┬──────────────────┬──────────────┐
↓               ↓                  ↓
Current State   Location History   Event
↓               ↓                  ↓
WebSocket       Trip / Reports     Alert
↓
Live Map
```

`NormalizedTelemetry` یک **ساختار داخلی استاندارد** است.

قرار نیست الزاماً هر `NormalizedTelemetry` مستقیماً تبدیل به یک رکورد دیتابیس شود.

پس:

```text
NormalizedTelemetry
        ↓
Storage / State Engine
        ↓
تصمیم می‌گیرد:
- Current State update شود؟
- History ثبت شود؟
- Event ساخته شود؟
- State Interval ایجاد/بسته شود؟
```

---

# 3. Traccar / Flespi

از معماری و تجربه پروژه‌هایی مثل Traccar و Flespi به‌عنوان مرجع استفاده می‌شود، اما SANA قرار نیست آن‌ها را کامل کپی کند.

هدف:

* استفاده از ایده‌های مناسب
* بررسی Decoderهای Protocolها
* جلوگیری از بازنویسی بی‌دلیل صدها Protocol
* مستقل باقی ماندن معماری SANA

در صورت استفاده از کد Protocol Decoder، License هر Protocol باید جداگانه بررسی شود.

---

# 4. دیتابیس

`सana-gps` مستقیماً به PostgreSQL فعلی SANA متصل خواهد شد.

اما دسترسی آن باید منطقی و محدود باشد.

`सana-gps` فقط باید به داده‌هایی که برای GPS لازم دارد دسترسی داشته باشد.

مثلاً:

```text
Device
DeviceModel
Protocol
IMEI
...
GPS/Telemetry tables
```

منطق کسب‌وکار نباید از طریق دسترسی مستقیم دیتابیس وارد `sana-gps` شود.

---

# 5. مقیاس اولیه

هدف معماری:

```text
حدود 10,000 دستگاه
حداکثر حدود 15,000 دستگاه
```

در شروع از معماری ساده استفاده می‌شود.

فعلاً:

```text
GPS
 ↓
sana-gps
 ↓
PostgreSQL
```

و از ابتدا Kafka / RabbitMQ / Queue / Workerهای سنگین اضافه نمی‌شوند.

اما معماری باید طوری باشد که بعداً بتوان:

```text
sana-gps instance 1 ─┐
sana-gps instance 2 ─┼→ Queue → Workers → Database
sana-gps instance 3 ─┘
```

را اضافه کرد.

---

# 6. IMEI

IMEI شناسه اصلی دستگاه در SANA است.

اما IMEI به‌تنهایی مکانیزم امنیتی کامل محسوب نمی‌شود.

معماری باید امکان اضافه شدن روش‌های احراز هویت دیگر در آینده را داشته باشد.

---

# 7. دستگاه ناشناخته

اگر IMEI در SANA ثبت نشده باشد:

```text
GPS Device
   ↓
sana-gps
   ↓
IMEI
   ↓
Device پیدا نشد
   ↓
Reject سریع
```

داده دستگاه ناشناخته نباید وارد پردازش سنگین شود.

در آینده در صورت نیاز می‌توان قابلیت Pending / Unknown Device اضافه کرد.

---

# 8. Protocol و Port

هر Protocol می‌تواند Port مخصوص خود را داشته باشد.

Portها باید در آینده قابل تنظیم توسط Admin باشند.

معماری باید امکان Protocol Detection روی Port مشترک را نیز در آینده داشته باشد.

مثلاً:

```text
Port 5001 → Teltonika
Port 5002 → GT06
Port 5003 → ...
```

و در آینده:

```text
Shared Port
     ↓
Protocol Detection
     ↓
Decoder مناسب
```

---

# 9. Session

برای هر Device / IMEI در حالت عادی فقط یک Session فعال در نظر گرفته می‌شود.

اگر اتصال جدیدی از همان دستگاه ایجاد شود، Session قبلی می‌تواند جایگزین/غیرفعال شود.

---

# 10. ACK

ارسال ACK وظیفه `sana-gps` است.

Django نباید در مسیر ACK قرار بگیرد.

```text
GPS
 ↓
sana-gps
 ↓
ACK
```

و نه:

```text
GPS
 ↓
Django
 ↓
ACK
```

---

# 11. زمان‌ها

در Telemetry دو زمان مستقل داریم:

### `device_time`

زمانی که خود GPS Device گزارش می‌کند.

ویژگی‌ها:

* UTC
* مبنای اصلی History
* مبنای Trip
* مبنای Reports
* باید از Device دریافت شود

اگر زمان دستگاه نامعتبر باشد، نباید بدون اعلام/ثبت وضعیت، آن را با `server_received_at` جایگزین کنیم.

---

### `server_received_at`

زمان واقعی دریافت Packet توسط `sana-gps`.

ویژگی‌ها:

* UTC
* توسط Server تعیین می‌شود
* برای بررسی Latency مناسب است
* برای تشخیص وضعیت ارتباط و Offline مناسب است

مثال:

```text
device_time        = 10:35:20
server_received_at = 10:35:23
```

یعنی Packet حدود 3 ثانیه بعد از زمان گزارش‌شده توسط دستگاه به Server رسیده است.

---

# 12. مختصات

مختصات به دو فیلد تقسیم می‌شوند:

```text
latitude
longitude
```

نوع مفهومی:

```text
Decimal
```

و نه Float.

دقت موردنظر اولیه حدود 6 رقم اعشار است.

مثال:

```text
latitude  = 35.721907
longitude = 51.334921
```

محدوده معتبر:

```text
latitude  = -90 ... +90
longitude = -180 ... +180
```

مختصات نامعتبر نباید به‌عنوان Location معتبر وارد سیستم شوند.

Raw Packet در صورت نیاز برای Debug حفظ می‌شود.

---

# 13. GPS Fix

وضعیت GPS از مختصات جداست.

فیلد اصلی:

```text
gps_valid
```

و فیلدهای مرتبط:

```text
satellites
accuracy
```

هر دو `satellites` و `accuracy` می‌توانند NULL باشند، چون همه دستگاه‌ها این اطلاعات را ارائه نمی‌کنند.

---

# 14. زمانی که GPS Fix وجود ندارد

وقتی Device GPS Fix ندارد:

```text
gps_valid = false
latitude  = NULL
longitude = NULL
```

نباید مختصات قبلی را دوباره به‌عنوان مختصات فعلی ذخیره کنیم.

اما این به معنی از بین رفتن آخرین موقعیت معتبر نیست.

باید بین این دو مفهوم تفاوت وجود داشته باشد:

```text
Last Known Position
```

و

```text
Current Valid GPS Position
```

مثلاً:

```text
آخرین موقعیت معتبر:
35.721907, 51.334921

GPS فعلی:
No Fix
```

در Current State می‌توان آخرین موقعیت معتبر را نگه داشت، ولی وضعیت فعلی را:

```text
gps_valid = false
```

ثبت کرد.

---

# 15. No-Fix Interval

اگر دستگاه برای مدت زیادی GPS Fix نداشته باشد، نباید هزاران رکورد تکراری ساخته شود.

مثلاً:

```text
08:30:10 → GPS Fix lost
09:15:10 → GPS Fix restored
```

می‌توان این وضعیت را به‌صورت یک Interval در نظر گرفت:

```text
GPS_NO_FIX
start = 08:30:10
end   = 09:15:10
```

به این ترتیب اطلاعات شروع و پایان وضعیت حفظ می‌شود بدون اینکه برای هر Packet یک رکورد تکراری ذخیره شود.

---

# 16. مرز Protocol Decoder و Normalizer

هر Protocol ممکن است GPS Fix و سایر Telemetryها را به شکل متفاوتی اعلام کند.

مرز معماری قطعی SANA این است:

```text
Raw Protocol Frame
      ↓
Framer
      ↓
Protocol Decoder
      ↓
ProtocolMessage
      ↓
Normalizer
      ↓
NormalizedTelemetry
```

### Protocol Decoder

Decoder مسئول Parse، Decode، Message Type، Protocol Metadata و ساختار Protocol-specific است.

Decoder مستقیماً `NormalizedTelemetry` تولید نمی‌کند و نباید منطق Domain یا Database داشته باشد.

### Normalizer

Normalizer مسئول Field Mapping، Unit Conversion، Representation Conversion و تبدیل ProtocolMessage به مفاهیم استاندارد SANA است.

بعد از Normalizer، لایه‌های بعدی نباید مجبور باشند جزئیات Protocol خاص را بدانند.

---

# 17. NormalizedTelemetry فعلی

تا این مرحله ساختار مفهومی زیر قطعی شده است:

```text
NormalizedTelemetry
├── device              REQUIRED
├── device_time         REQUIRED
├── server_received_at  REQUIRED
├── latitude            NULLABLE
├── longitude           NULLABLE
├── gps_valid           REQUIRED
├── accuracy        NULLABLE
├── satellites          NULLABLE
└── ...
```

هنوز برای این ساختار Database Model ساخته نشده است.

---

# 18. Raw Packet

Raw Packet برای Debug و توسعه Decoderها مفید است.

اما قرار نیست برای همیشه نگهداری شود.

Retention باید قابل تنظیم باشد؛ مثلاً:

```text
7 روز
30 روز
...
```

پس:

```text
Raw Packet
→ نگهداری موقت
→ حذف بعد از Retention
```

در مقابل، داده Normalized و اطلاعات موردنیاز History باید برای مدت طولانی‌تر نگهداری شوند.

---

# 19. اصل مهم ذخیره‌سازی Telemetry

قرار نیست تمام Packetهای GPS بدون فیلتر و برای همیشه در دیتابیس ذخیره شوند.

مثلاً اگر خودرو چهار ساعت ثابت باشد:

```text
08:30
08:30:10
08:30:20
08:30:30
...
12:30
```

نباید هزاران رکورد کاملاً تکراری ایجاد شود.

سیستم باید بتواند وضعیت را به شکل Interval/State نگهداری کند.

اما فشرده‌سازی فقط بر اساس تغییر Latitude/Longitude انجام نمی‌شود.

چون ممکن است در حالت ثابت مواردی مثل این‌ها تغییر کنند:

* Ignition
* Battery
* External Voltage
* Alarm
* Temperature
* GSM
* Fuel
* سایر Telemetry

بنابراین تغییر State نیز باید در تصمیم‌گیری برای ذخیره‌سازی لحاظ شود.

---

# 20. Current State

برای Live Map یک وضعیت فعلی برای هر Device لازم است.

مفهوم:

```text
CurrentState
```

که وضعیت فعلی دستگاه را نگه می‌دارد.

این بخش بعداً برای:

```text
Live Map
WebSocket
Offline Detection
```

استفاده خواهد شد.

Live Map نباید برای نمایش وضعیت لحظه‌ای، کل Location History را Query کند.

---

# 21. Location متعلق به Device است

موقعیت GPS مستقیماً متعلق به:

```text
Device
```

است، نه Vehicle.

چون یک Device ممکن است در طول عمر خود روی چند Vehicle نصب شود.

بنابراین History دستگاه مستقل از Vehicle ذخیره می‌شود.

بعداً می‌توان با تاریخچه نصب Device روی Vehicle، History مربوط به یک Vehicle را استخراج کرد.

---

# 22. WebSocket

WebSocket از همان ابتدای طراحی Live Map در معماری وجود خواهد داشت.

مسیر کلی:

```text
GPS
 ↓
sana-gps
 ↓
Current State
 ↓
WebSocket
 ↓
Authorized User
 ↓
Live Map
```

صفحه نباید برای دریافت موقعیت جدید Refresh شود.

---

# 23. Permission

Permission توسط `sana-backend` کنترل می‌شود.

کاربر فقط باید Current State دستگاه‌هایی را دریافت کند که اجازه دسترسی به آن‌ها را دارد.

مهم:

> مخفی کردن Marker در Frontend امنیت محسوب نمی‌شود.

مختصات دستگاهی که کاربر اجازه دیدنش را ندارد، نباید اصلاً به Browser ارسال شود.

---

# 24. Live Map

در مرحله اول Marker می‌تواند شامل این اطلاعات باشد:

```text
Vehicle
Driver
Speed
Status
Last Update
```

و در مراحل بعد:

```text
Device Detail
Today Path
History
Reports
Trip
Events
```

اضافه خواهند شد.

---

# 25. Marker Clustering

در Live Map:

* در Zoom پایین → Markerها Cluster شوند.
* در Zoom بالاتر → Markerهای جداگانه نمایش داده شوند.

هدف کاهش شلوغی نقشه در تعداد بالای دستگاه‌هاست.

---

# 26. Trip

دو مفهوم در نظر گرفته می‌شود:

```text
Current Trip
```

برای وضعیت لحظه‌ای و Live UI.

و:

```text
Final Trip
```

که بعد از پایان حرکت محاسبه و نهایی می‌شود.

---

# 27. Reports

گزارش‌های Tracking و GPS بر پایه ترکیبی از این داده‌ها ساخته خواهند شد:

```text
Location History
Trip
Event
Aggregation
```

گزارش‌ها باید امکان تعیین بازه دقیق:

```text
Start Date/Time
End Date/Time
```

را داشته باشند.

---

# 28. وضعیت فعلی طراحی Telemetry

موارد زیر تا این مرحله به‌صورت قطعی طراحی شده‌اند:

```text
Time
Location
GPS Fix
Speed
Heading
Altitude
Motion
Ignition
Battery Voltage
External Voltage
GSM Signal
Odometer
Engine Hours
Fuel Level
Attributes
CurrentState
LocationHistory
Event
Trip
Protocol Decoder
ProtocolMessage
Normalizer
Validation
Deduplication
Temporal Ordering
Sampling
```

مواردی که هنوز تصمیم مستقل و نهایی درباره آن‌ها لازم است، نباید با تصمیمات بالا مخلوط شوند.

---

## وضعیت تصمیم‌گیری

### قطعی شده

* معماری جداگانه `sana-gps`
* Normalized Telemetry به‌عنوان ساختار داخلی
* جداسازی Current State / Location History / Event
* دو زمان مستقل Device و Server
* UTC داخلی
* Decimal برای مختصات
* Nullable بودن مختصات در No-Fix
* جداسازی GPS Fix از مختصات
* نگهداری Last Known Position
* Interval برای No-Fix طولانی
* Raw Packet با Retention محدود
* جلوگیری از ذخیره‌سازی بی‌رویه Packetهای تکراری
* توجه به تغییرات Telemetry در Compression
* Location متعلق به Device
* WebSocket از ابتدای Live Map
* Permission در Backend
* عدم ارسال مختصات غیرمجاز به Browser
* Reject سریع IMEI ناشناخته
* یک Session فعال برای هر Device
* ACK در sana-gps
* معماری ساده اولیه بدون Queue سنگین
* قابلیت Scale-out در آینده

============================================================================
============================================================================
# SANA GPS — تصمیمات قطعی Speed, Heading, Altitude و Motion

> این سند ادامه تصمیمات معماری `NormalizedTelemetry` در پروژه SANA است.
>
> **وضعیت:** تصمیمات قطعی مرحله Speed / Heading / Altitude / Motion

---

## 1. Speed

فیلد:

```text
speed
```

### واحد استاندارد SANA

```text
km/h
```

Protocol Decoder فقط مقدار و واحد/نمایش Protocol را استخراج می‌کند؛ تبدیل واحد متعلق به Normalizer است.

مثلاً:

```text
Device → knots
Decoder → ProtocolMessage(speed=..., unit=knots)
Normalizer → km/h
NormalizedTelemetry.speed → km/h
```

### نوع داده

```text
Decimal
```

مثال:

```text
0
12.5
63.7
102.3
```

### Nullable

بله.

اگر دستگاه سرعت معتبر ارائه نکند:

```text
speed = NULL
```

نباید مقدار `0` به‌صورت مصنوعی قرار داده شود.

تفاوت:

```text
speed = 0
```

یعنی سرعت واقعاً صفر گزارش شده.

اما:

```text
speed = NULL
```

یعنی سرعت در دسترس یا معتبر نیست.

### نقش در تشخیص حرکت

`speed` یکی از ورودی‌های تشخیص حرکت است، اما به‌تنهایی معیار قطعی Motion نیست.

نباید صرفاً این منطق را داشته باشیم:

```text
speed > 0 → moving
speed = 0 → stopped
```

زیرا GPS ممکن است خطا داشته باشد یا دستگاه سرعت نامعتبر گزارش کند.

---

# 2. Heading

فیلد:

```text
heading
```

جهت حرکت دستگاه را بر حسب درجه مشخص می‌کند.

### واحد

```text
degree
```

### محدوده

```text
0 <= heading < 360
```

تقریباً:

```text
0°   → شمال
90°  → شرق
180° → جنوب
270° → غرب
```

### نوع داده

```text
Decimal
```

مثال:

```text
91.4
183.7
274.2
```

### Nullable

بله.

اگر Heading معتبر نباشد:

```text
heading = NULL
```

نباید مقدار ساختگی `0` قرار داده شود.

### نکته مهم

Heading به‌تنهایی معیار حرکت نیست.

وقتی خودرو متوقف است ممکن است دستگاه Headingهای متفاوتی گزارش کند:

```text
91°
94°
88°
97°
...
```

این تغییر نباید باعث شود سیستم تصور کند خودرو حرکت کرده است.

بنابراین Heading باید در کنار Speed، GPS Fix و سایر Stateها تفسیر شود.

---

# 3. Altitude

فیلد:

```text
altitude
```

ارتفاع نسبت به سطح دریا را نشان می‌دهد.

### واحد

```text
meter
```

### نوع داده

```text
Decimal
```

مثال:

```text
1205.4
```

### Nullable

بله.

ممکن است Device این اطلاعات را ارائه نکند یا مقدار معتبر نداشته باشد:

```text
altitude = NULL
```

### اهمیت در Location

Altitude برای معتبر بودن Location ضروری نیست.

این وضعیت کاملاً معتبر است:

```text
latitude       ✓
longitude      ✓
gps_valid      ✓
altitude       NULL
```

### نقش در Motion

Altitude به‌تنهایی نباید باعث تشخیص حرکت شود.

مثلاً تغییر ارتفاع 20 متر نباید به‌تنهایی به معنی حرکت Vehicle تلقی شود.

---

# 4. Motion

فیلد:

```text
motion
```

نمایانگر وضعیت Normalized حرکت Device است.

مثلاً:

```text
motion = true
```

یا:

```text
motion = false
```

### تفاوت Motion و Speed

این دو مفهوم یکی نیستند.

```text
speed
```

داده Telemetry است.

اما:

```text
motion
```

یک State نرمال‌شده است.

مثلاً:

```text
speed  = 43.7
motion = true
```

یا:

```text
speed  = 0
motion = false
```

### Motion نباید فقط از Speed ساخته شود

تشخیص Motion می‌تواند بر اساس چند منبع انجام شود:

```text
GPS Speed
Device Motion Flag
Ignition
Accelerometer
سایر Telemetry
SANA Motion Engine
```

بنابراین معماری نباید Motion را به یک Protocol یا یک روش خاص وابسته کند.

---

# 5. Motion در حالت No-Fix

اگر:

```text
gps_valid = false
```

نباید صرفاً به دلیل:

```text
speed = 0
```

نتیجه بگیریم Vehicle متوقف است.

مثلاً:

```text
gps_valid = false
speed = NULL
```

در این شرایط Motion ممکن است قابل تعیین نباشد.

این موضوع در طراحی State Engine باید مدیریت شود.

---

# 6. ساختار فعلی NormalizedTelemetry

بعد از این مرحله ساختار مفهومی به این شکل است:

```text
NormalizedTelemetry
├── device              REQUIRED
├── device_time         REQUIRED
├── server_received_at  REQUIRED
│
├── latitude            NULLABLE
├── longitude           NULLABLE
├── gps_valid           REQUIRED
├── accuracy        NULLABLE
├── satellites          NULLABLE
│
├── speed               NULLABLE
├── heading             NULLABLE
├── altitude            NULLABLE
└── motion              NULLABLE BOOLEAN
```

---

# 7. واحدهای استاندارد SANA

Normalizer باید داده‌های `ProtocolMessage` را قبل از ورود به `NormalizedTelemetry` به واحد استاندارد SANA تبدیل کند.

در این مرحله:

```text
speed    → km/h
heading  → degree
altitude → meter
```

بنابراین لایه‌های بعدی SANA نباید لازم باشد بدانند هر Protocol از چه واحدی استفاده کرده است.

---

# 8. اصل معماری

ساختار داخلی SANA باید Protocol-independent باشد.

یعنی مثلاً:

```text
Teltonika
      ↓
Teltonika Decoder
      ↓
ProtocolMessage
      ↓
Normalizer
      ↓
NormalizedTelemetry
```

و:

```text
GT06
      ↓
GT06 Decoder
      ↓
NormalizedTelemetry
```

هر دو باید خروجی استاندارد یکسانی تولید کنند:

```text
speed
heading
altitude
motion
```

---

# 9. وضعیت تصمیم‌گیری

### قطعی شده

* `speed` با واحد `km/h`
* `speed` از نوع Decimal
* `speed` می‌تواند NULL باشد
* `speed = 0` با `speed = NULL` متفاوت است
* `heading` با واحد degree
* محدوده Heading برابر `0 <= heading < 360`
* `heading` می‌تواند NULL باشد
* Heading به‌تنهایی معیار Motion نیست
* `altitude` با واحد meter
* `altitude` می‌تواند NULL باشد
* Altitude برای معتبر بودن Location ضروری نیست
* Altitude به‌تنهایی معیار Motion نیست
* `motion` یک State نرمال‌شده است
* Motion با Speed یکی نیست
* Motion می‌تواند از چند منبع استخراج شود
* Motion نباید صرفاً بر اساس Speed تعیین شود
* در No-Fix نباید Speed صفر را به معنی توقف قطعی در نظر گرفت
* Protocol Decoder مسئول تبدیل واحدها به استاندارد SANA است
* لایه‌های بعدی نباید به واحد یا ساختار Protocol خاص وابسته باشند

---

## مرحله بعد

فیلدهای بعدی:

```text
ignition
battery_voltage
external_voltage
```

این سه مورد برای طراحی:

```text
Vehicle State
Power Events
Ignition Events
Battery Status
Power Cut Detection
Device Health
```

اهمیت زیادی دارند.




============================================================================
============================================================================



# SANA GPS — تصمیمات قطعی Ignition

## 1. مفهوم Ignition

فیلد:

```text
ignition
```

نمایانگر وضعیت **سوئیچ/احتراق خودرو** است و با حرکت خودرو یکی نیست.

مقادیر:

```text
true  → Ignition ON
false → Ignition OFF
NULL  → Unknown / Not Available
```

---

## 2. Nullable بودن

`ignition` باید Nullable باشد.

اگر Device یا Protocol اطلاعات Ignition را ارائه نکند:

```text
ignition = NULL
```

نباید به‌صورت خودکار:

```text
ignition = false
```

قرار داده شود.

تفاوت مهم:

```text
false → قطعاً خاموش است
NULL  → وضعیت مشخص نیست / اطلاعات وجود ندارد
```

---

## 3. منابع Ignition

Protocol Decoder باید اطلاعات مختلف دستگاه را به مقدار استاندارد SANA تبدیل کند.

منابع احتمالی:

```text
Digital Input
ACC
Protocol Flag
Device-specific ignition field
```

مثلاً:

```text
ACC = 1
    ↓
ignition = true
```

---

## 4. Ignition و Speed

`ignition` نباید صرفاً از روی `speed` ساخته شود.

این منطق غلط است:

```text
speed > 0 → ignition = true
speed = 0 → ignition = false
```

زیرا ممکن است:

```text
ignition = true
speed = 0
```

باشد؛ مثلاً خودرو روشن ولی متوقف است.

---

## 5. Ignition و Motion

ترکیب‌های مختلف معتبر هستند:

```text
ignition = false
motion   = false
```

خودرو خاموش و متوقف.

---

```text
ignition = true
motion   = false
```

خودرو روشن ولی متوقف.

---

```text
ignition = true
motion   = true
```

خودرو روشن و در حال حرکت.

---

```text
ignition = NULL
motion   = true
```

حرکت تشخیص داده شده ولی دستگاه اطلاعات Ignition ارائه نمی‌کند.

---

## 6. Ignition و Event

تغییر وضعیت Ignition می‌تواند Event تولید کند.

مثلاً:

```text
OFF → ON
```

می‌تواند تبدیل شود به:

```text
IGNITION_ON
```

و:

```text
ON → OFF
```

می‌تواند تبدیل شود به:

```text
IGNITION_OFF
```

اما `NormalizedTelemetry` فقط وضعیت فعلی را حمل می‌کند:

```text
ignition = true
```

تشخیص تغییر و تولید Event در لایه Event Detection انجام خواهد شد.

---

## 7. Ignition و Trip

Ignition به‌تنهایی تعریف‌کننده Trip نیست.

این منطق قطعی نیست:

```text
Ignition ON  → Trip Start
Ignition OFF → Trip End
```

Trip Engine در آینده باید از ترکیب مواردی مانند:

```text
motion
speed
ignition
GPS
time
```

استفاده کند.

بنابراین:

> Ignition یکی از ورودی‌های Trip Engine است، نه تعریف Trip.

---

## 8. Device بدون Ignition

اگر دستگاه فقط اطلاعاتی مانند:

```text
latitude
longitude
speed
```

ارائه کند و اطلاعات Ignition نداشته باشد:

```text
ignition = NULL
```

در UI نیز نباید وضعیت اشتباه نمایش داده شود.

مثلاً:

```text
سوئیچ: نامشخص
```

بهتر از:

```text
سوئیچ: خاموش
```

است.

---

## 9. قرارداد نهایی

```text
ignition
    Type: Boolean
    Nullable: Yes
    Unit: ندارد
```

معنی:

```text
true  = ON
false = OFF
NULL  = Unknown / Not Available
```

---

## 10. اصل معماری

Protocol Decoder وظیفه تبدیل اطلاعات مختلف Protocolها به `ignition` استاندارد SANA را دارد.

لایه‌های بعدی SANA نباید به نحوه گزارش Ignition در Protocol خاص وابسته باشند.

ساختار:

```text
Protocol Packet
      ↓
Protocol Decoder
      ↓
ProtocolMessage
      ↓
Normalizer
      ↓
NormalizedTelemetry
      ↓
ignition
```

---

## وضعیت

### قطعی شده

* Ignition یک وضعیت مستقل از Motion است.
* نوع آن Boolean است.
* Nullable است.
* `true` یعنی ON.
* `false` یعنی OFF.
* `NULL` یعنی Unknown / Not Available.
* نباید از Speed به‌صورت مستقیم استخراج شود.
* Ignition به‌تنهایی Trip را تعریف نمی‌کند.
* تغییر Ignition می‌تواند Event ایجاد کند.
* Event Detection مسئول تشخیص تغییر وضعیت خواهد بود.
* Protocol Decoder مسئول Normalization است.
* دستگاهی که Ignition ندارد نباید به‌صورت مصنوعی OFF فرض شود.


============================================================================
============================================================================


# SANA GPS — تصمیمات قطعی Battery Voltage و External Voltage

## 1. دو منبع ولتاژ مستقل

در `NormalizedTelemetry` دو فیلد مستقل داریم:

```text
battery_voltage
external_voltage
```

این دو نباید با یکدیگر ترکیب شوند.

---

## 2. external_voltage

نمایانگر ولتاژ منبع خارجی متصل به GPS Device است.

در اغلب کاربردهای خودرو:

```text
external_voltage
→ برق خودرو / ورودی خارجی Tracker
```

مثال:

```text
external_voltage = 13.72 V
```

### مشخصات

```text
Type: Decimal
Unit: Volt (V)
Nullable: Yes
```

اگر Device این مقدار را ارائه نکند:

```text
external_voltage = NULL
```

نباید به‌صورت مصنوعی `0` قرار داده شود.

---

## 3. battery_voltage

نمایانگر ولتاژ باتری داخلی یا Backup Battery خود GPS Device است، در صورتی که Device چنین باتری‌ای داشته باشد.

مثال:

```text
battery_voltage = 3.84 V
```

### مشخصات

```text
Type: Decimal
Unit: Volt (V)
Nullable: Yes
```

اگر Device باتری داخلی نداشته باشد یا اطلاعات آن را گزارش نکند:

```text
battery_voltage = NULL
```

نه `0`.

---

## 4. تفاوت Battery و External Voltage

مثلاً:

```text
external_voltage = 13.8 V
battery_voltage  = 3.92 V
```

یعنی:

```text
برق خارجی GPS → 13.8V
باتری داخلی GPS → 3.92V
```

و اگر:

```text
external_voltage = 0
battery_voltage  = 3.85V
```

می‌تواند نشان‌دهنده قطع برق خارجی و ادامه کار دستگاه با Backup Battery باشد.

اما این وضعیت هنوز به‌تنهایی Event قطعی محسوب نمی‌شود.

---

## 5. DeviceModel و Battery Threshold

محدوده ولتاژ Battery بین Deviceها یکسان نیست.

بنابراین SANA نباید یک Threshold سراسری برای تمام دستگاه‌ها داشته باشد.

مثلاً این منطق صحیح نیست:

```text
battery_voltage < 3.5
→ LOW_BATTERY
```

برای تمام Deviceها.

در آینده Thresholdهای مربوط به Battery می‌توانند بر اساس:

```text
DeviceModel
Configuration
```

تعیین شوند.

در `NormalizedTelemetry` فقط مقدار واقعی ولتاژ ذخیره می‌شود.

---

## 6. External Voltage و Power Cut

این منطق صحیح نیست:

```text
external_voltage = 0
→ POWER_CUT
```

زیرا یک Packet منفرد ممکن است به دلایل مختلف مقدار نامعتبر یا غیرمنتظره داشته باشد.

Event Detection باید استمرار و شرایط وضعیت را بررسی کند.

مثلاً:

```text
13.7V
13.6V
13.5V
0V
0V
0V
...
```

اطلاعات بیشتری برای تشخیص Power Cut فراهم می‌کند.

---

## 7. Telemetry در مقابل Event

`external_voltage` و `battery_voltage` داده Telemetry هستند.

خودشان Event نیستند.

به‌عنوان مثال:

```text
external_voltage = 0
```

فقط یک مقدار Telemetry است.

Event Engine بعداً می‌تواند بر اساس State و شرایط زمانی تشخیص دهد:

```text
POWER_CUT
POWER_RESTORED
```

به همین شکل:

```text
battery_voltage
```

می‌تواند در آینده منجر به:

```text
LOW_BATTERY
CRITICAL_BATTERY
```

شود.

اما Threshold و منطق این Eventها در Event/State Engine قرار می‌گیرد، نه Decoder.

---

## 8. Compression

ولتاژ بخشی از Telemetry است، اما هر تغییر جزئی الزاماً نباید یک رکورد دائمی در History ایجاد کند.

مثلاً:

```text
13.71
13.70
13.71
13.70
13.71
...
```

لزومی ندارد تمام این تغییرات برای همیشه ذخیره شوند.

Storage Engine باید هنگام طراحی Compression تصمیم بگیرد چه تغییر ولتاژی معنی‌دار محسوب می‌شود.

بنابراین فعلاً Resolution نهایی ذخیره‌سازی را قفل نمی‌کنیم.

---

## 9. قرارداد نهایی

```text
NormalizedTelemetry
├── battery_voltage
└── external_voltage
```

هر دو:

```text
Type: Decimal
Unit: Volt
Nullable: Yes
```

معنی:

```text
battery_voltage
→ Battery داخلی/Backup دستگاه

external_voltage
→ برق ورودی خارجی دستگاه
```

---

## 10. اصل معماری

Protocol Decoder فقط مقدار استاندارد Telemetry را تولید می‌کند:

```text
Protocol Packet
      ↓
Protocol Decoder
      ↓
battery_voltage
external_voltage
      ↓
NormalizedTelemetry
```

تشخیص Event در لایه جداگانه انجام می‌شود:

```text
NormalizedTelemetry
      ↓
State / Event Engine
      ↓
POWER_CUT
POWER_RESTORED
LOW_BATTERY
...
```

---

## وضعیت

### قطعی شده

* `battery_voltage` و `external_voltage` دو فیلد مستقل هستند.
* هر دو Decimal هستند.
* واحد استاندارد هر دو Volt است.
* هر دو Nullable هستند.
* `NULL` با `0` تفاوت معنایی دارد.
* Battery مربوط به باتری داخلی/Backup دستگاه است.
* External Voltage مربوط به منبع برق خارجی دستگاه است.
* محدوده Battery بین DeviceModelهای مختلف یکسان فرض نمی‌شود.
* Thresholdهای Battery در Decoder قرار نمی‌گیرند.
* `external_voltage = 0` به‌تنهایی Power Cut قطعی نیست.
* Battery و External Voltage داده Telemetry هستند، نه Event.
* Eventهایی مانند `POWER_CUT` و `LOW_BATTERY` توسط State/Event Engine تشخیص داده می‌شوند.
* تغییرات جزئی ولتاژ نباید الزاماً رکورد دائمی ایجاد کنند.
* Resolution نهایی Storage فعلاً باز گذاشته شده و هنگام طراحی Compression مشخص می‌شود.



============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry

## بخش: GSM Signal

### 1. هدف

`gsm_signal` قدرت سیگنال ارتباطی دستگاه GPS با شبکه موبایل را در یک مقدار استاندارد و قابل استفاده در کل SANA نمایش می‌دهد.

این فیلد بخشی از **Telemetry** است و به‌تنهایی نشان‌دهنده Online یا Offline بودن دستگاه نیست.

---

## 2. تعریف فیلد

```text
gsm_signal
Type: Decimal
Unit: dBm
Nullable: Yes
```

نمونه مقادیر:

```text
-65 dBm  → سیگنال قوی‌تر
-83 dBm  → متوسط
-101 dBm → ضعیف‌تر
```

به‌طور معمول هرچه مقدار dBm به صفر نزدیک‌تر باشد، سیگنال قوی‌تر است.

---

## 3. وظیفه Protocol Decoder

هر پروتکل ممکن است قدرت سیگنال را با فرمت متفاوتی گزارش کند، برای مثال:

```text
CSQ
RSSI
Signal Level
Percentage
Device-specific value
```

`Protocol Decoder` باید در صورت امکان مقدار پروتکل را به `dBm` استاندارد تبدیل کند.

مثلاً:

```text
Protocol Value
      ↓
Protocol Decoder
      ↓
Normalized gsm_signal
      ↓
dBm
```

اگر تبدیل معتبر و قابل اتکا وجود نداشته باشد، نباید مقدار حدسی تولید شود.

در این حالت:

```text
gsm_signal = NULL
```

---

## 4. Nullable بودن

`gsm_signal` می‌تواند `NULL` باشد.

موارد ممکن:

* پروتکل مقدار سیگنال را گزارش نمی‌کند.
* دستگاه اطلاعات GSM را ارسال نمی‌کند.
* مقدار دریافتی نامعتبر است.
* تبدیل مقدار پروتکل به dBm قابل اعتماد نیست.
* دستگاه در وضعیتی است که مقدار قابل استفاده‌ای وجود ندارد.

نباید برای مقدار ناموجود از `0` استفاده شود.

---

## 5. GSM Signal و وضعیت Offline

قدرت سیگنال GSM به‌تنهایی معیار Offline بودن دستگاه نیست.

مثلاً:

```text
gsm_signal = -105 dBm
```

به این معنی نیست که دستگاه حتماً Offline است.

همچنین ممکن است دستگاه:

```text
gsm_signal = -70 dBm
```

داشته باشد ولی مدتی هیچ دیتایی به SANA ارسال نکرده باشد.

بنابراین تشخیص وضعیت ارتباطی دستگاه باید بر اساس عواملی مانند:

```text
server_received_at
آخرین ارتباط معتبر
Timeout / Offline Policy
و وضعیت Session
```

انجام شود.

---

## 6. ارتباط GSM با GPS

`gsm_signal` مربوط به شبکه موبایل است و با وضعیت GPS تفاوت دارد.

ممکن است:

```text
GPS Fix = false
GSM Signal = خوب
```

یا:

```text
GPS Fix = true
GSM Signal = ضعیف
```

باشد.

بنابراین نباید یکی از این دو از روی دیگری نتیجه‌گیری شود.

---

## 7. Telemetry است، نه Event

تغییر `gsm_signal` به‌صورت عادی Event محسوب نمی‌شود.

مثلاً تغییر:

```text
-78 → -81 → -79 → -83
```

نباید باعث تولید Event دائمی شود.

در مرحله Storage/Compression بعداً مشخص می‌شود که تغییرات جزئی و تکراری چگونه ذخیره یا فشرده شوند.

---

## 8. فیلدهای پیشرفته‌تر

در آینده ممکن است بعضی تجهیزات اطلاعات دقیق‌تری ارائه کنند، مانند:

```text
RSRP
RSRQ
SINR
```

در این مرحله این موارد فیلد استاندارد اصلی Normalized Telemetry نیستند.

در صورت نیاز می‌توانند ابتدا در:

```text
attributes
```

ذخیره شوند و اگر در تعداد زیادی از دستگاه‌ها و پروتکل‌ها کاربرد عمومی پیدا کردند، در آینده به فیلدهای استاندارد تبدیل شوند.

---

## 9. تصمیم نهایی

قرارداد نهایی این بخش:

```text
gsm_signal
    Type: Decimal
    Unit: dBm
    Nullable: Yes
```

قواعد اصلی:

1. مقدار استاندارد SANA بر اساس `dBm` است.
2. Decoder مسئول Normalization مقدار پروتکل است.
3. اگر تبدیل معتبر نباشد، مقدار `NULL` می‌شود.
4. `0` به معنی Unknown استفاده نمی‌شود.
5. GSM Signal به‌تنهایی معیار Online/Offline نیست.
6. GSM و GPS مستقل از یکدیگر هستند.
7. تغییرات عادی GSM Signal مستقیماً Event ایجاد نمی‌کنند.
8. فیلدهای RSRP/RSRQ/SINR فعلاً در `attributes` قابل نگهداری هستند.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry

## بخش: Odometer

### 1. تعریف

`odometer` مقدار تجمعی مسافت طی‌شده است که **خود دستگاه GPS گزارش می‌کند**.

این مقدار با `speed` متفاوت است:

```text
speed
→ سرعت فعلی

odometer
→ مسافت تجمعی گزارش‌شده توسط دستگاه
```

---

## 2. تعریف فیلد

```text
odometer
Type: Decimal
Unit: km
Nullable: Yes
Source: Device
Meaning: Device-reported cumulative distance
```

مثال:

```text
odometer = 125430.7 km
```

---

## 3. تفاوت Device Odometer و SANA Calculated Distance

این دو مفهوم باید کاملاً جدا باشند.

### Device Odometer

مقداری که دستگاه گزارش می‌کند:

```text
GPS Device
    ↓
Protocol
    ↓
Decoder
    ↓
Device Odometer
```

### SANA Calculated Distance

مسافتی که SANA بر اساس Locationهای معتبر محاسبه می‌کند:

```text
Location A
    ↓
Location B
    ↓
Distance Calculation
    ↓
SANA Calculated Distance
```

این دو ممکن است به دلایل مختلف برابر نباشند، از جمله:

* دقت GPS
* فاصله زمانی بین نقاط
* فیلتر شدن نقاط نامعتبر
* الگوریتم محاسبه
* تنظیمات دستگاه
* Reset شدن Odometer دستگاه

بنابراین نباید این دو مقدار در یک فیلد یا با یک مفهوم ذخیره شوند.

---

## 4. Nullable بودن

اگر پروتکل یا دستگاه Odometer را گزارش نکند:

```text
odometer = NULL
```

معتبر است.

نباید برای داده ناموجود از `0` استفاده شود.

```text
0
→ مقدار واقعی صفر

NULL
→ مقدار موجود نیست / قابل استخراج نیست
```

---

## 5. Normalization واحد

واحد استاندارد SANA برای Odometer:

```text
km
```

است.

اگر پروتکل مقدار را با واحد دیگری مانند meter یا mile ارسال کند، `Protocol Decoder` باید در صورت امکان آن را به `km` تبدیل کند.

مثال:

```text
1254300 meters
        ↓
1254.3 km
```

---

## 6. تجمعی بودن

Odometer یک مقدار cumulative است.

مثلاً:

```text
10000
10005
10012
10020
10027
```

افزایش مقدار در طول زمان طبیعی است.

اما کاهش مقدار الزاماً به معنی حرکت معکوس خودرو نیست.

مثلاً:

```text
10020
10025
10030
15
20
25
```

می‌تواند ناشی از مواردی مانند:

* Reset شدن Odometer
* تغییر تنظیمات دستگاه
* تعویض دستگاه
* Rollover
* Packet خراب
* رفتار خاص Firmware

باشد.

بنابراین کاهش مقدار نباید مستقیماً به‌عنوان مسافت منفی یا حرکت معکوس تفسیر شود.

---

## 7. مسئولیت Protocol Decoder

`Protocol Decoder` فقط وظیفه دارد مقدار گزارش‌شده توسط پروتکل را به ساختار استاندارد SANA تبدیل کند.

```text
Protocol Data
      ↓
Protocol Decoder
      ↓
Normalized Telemetry
      ↓
odometer
```

تشخیص مواردی مانند Reset، Rollback، Rollover یا ناسازگاری مقدار باید در لایه بعدی:

```text
Telemetry Processing / Storage
```

انجام شود.

به این ترتیب Business Logic وارد Decoder نمی‌شود.

---

## 8. Device Replacement

Odometer به منبع گزارش‌دهنده یعنی Device وابستگی دارد.

مثلاً:

```text
Vehicle A
    ↓
Device 1001
    ↓
Odometer = 85000 km
```

بعد دستگاه تعویض می‌شود:

```text
Vehicle A
    ↓
Device 2002
    ↓
Odometer = 12000 km
```

نباید SANA این تغییر را به‌عنوان برگشت خودرو از:

```text
85000 → 12000
```

تفسیر کند.

تاریخچه مسافت Vehicle باید بتواند تاریخچه چند Device مختلف را که در طول زمان روی خودرو نصب شده‌اند، مستقل از Odometer هر Device مدیریت کند.

---

## 9. ارتباط با Trip

`Trip Engine` نباید فقط به Odometer وابسته باشد.

Trip می‌تواند از ترکیب داده‌هایی مانند:

```text
Location
Speed
Motion
Ignition
Timestamp
```

استفاده کند.

Odometer می‌تواند به‌عنوان اطلاعات کمکی و مرجع در Trip استفاده شود.

مثلاً:

```text
Trip Start
odometer = 120000 km

Trip End
odometer = 120035 km
```

اما خرابی یا Reset شدن Odometer نباید باعث از بین رفتن Trip شود.

---

## 10. ارتباط با SANA Calculated Distance

معماری به این صورت است:

```text
                    ┌── Device Odometer
GPS Device ─────────┤
                    │
                    └── Location
                           ↓
                     SANA Distance Engine
                           ↓
                     Calculated Distance
```

در نتیجه:

```text
Device Odometer
→ مقدار گزارش‌شده توسط دستگاه

SANA Calculated Distance
→ مقدار محاسبه‌شده توسط SANA
```

این دو می‌توانند در Reports و تحلیل‌های بعدی در کنار یکدیگر استفاده شوند، ولی جایگزین یکدیگر نیستند.

---

## 11. Resolution

فعلاً مقدار به‌صورت `Decimal` نگهداری می‌شود و محدودیت دقت دقیق آن در مرحله طراحی Storage مشخص خواهد شد.

نمونه:

```text
125430.7 km
```

یا:

```text
125430.73 km
```

اصل معماری این است که مقدار Odometer یک مقدار Decimal تجمعی بر حسب کیلومتر باشد.

---

# تصمیم نهایی

```text
odometer
Type: Decimal
Unit: km
Nullable: Yes
Source: Device
Meaning: Device-reported cumulative distance
```

قواعد نهایی:

1. Odometer یک مقدار تجمعی است.
2. واحد استاندارد `km` است.
3. مقدار `NULL` یعنی داده موجود نیست.
4. `0` با `NULL` متفاوت است.
5. Decoder مقدار پروتکل را Normalize می‌کند.
6. کاهش Odometer به‌تنهایی به معنی حرکت معکوس نیست.
7. Reset / Rollover / Device Replacement در لایه Processing بررسی می‌شوند.
8. Device Odometer با SANA Calculated Distance متفاوت است.
9. Trip نباید فقط به Odometer وابسته باشد.
10. تعویض Device نباید باعث خراب شدن تاریخچه مسافت Vehicle شود.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry

## بخش: Engine Hours

### 1. تعریف

`engine_hours` مقدار تجمعی مدت زمان کارکرد موتور است که **خود دستگاه GPS گزارش می‌کند**.

مثال:

```text
engine_hours = 4382.75 h
```

این فیلد با `speed`، `ignition` و مدت زمان اتصال GPS یکسان نیست.

---

## 2. تعریف فیلد

```text
engine_hours
Type: Decimal
Unit: hour
Nullable: Yes
Source: Device
Meaning: Device-reported cumulative engine running time
Owner: Device
```

---

## 3. تفاوت Engine Hours و Ignition

`ignition` وضعیت فعلی سیستم ignition را نشان می‌دهد:

```text
ignition = true
→ روشن

ignition = false
→ خاموش

ignition = NULL
→ نامشخص / در دسترس نیست
```

اما `engine_hours` یک **شمارنده تجمعی** است.

مثلاً:

```text
ignition = true
engine_hours = 4382.75
```

و چند دقیقه بعد:

```text
ignition = true
engine_hours = 4382.82
```

این دو فیلد باید مستقل باقی بمانند.

همچنین ممکن است دستگاه یکی از این اطلاعات را داشته باشد و دیگری را نداشته باشد.

---

## 4. Nullable بودن

اگر دستگاه یا پروتکل Engine Hours را گزارش نکند:

```text
engine_hours = NULL
```

معتبر است.

نباید برای داده ناموجود از `0` استفاده شود.

```text
0
→ مقدار واقعی صفر

NULL
→ داده موجود نیست / قابل استخراج نیست
```

---

## 5. واحد استاندارد

واحد استاندارد SANA برای `engine_hours`:

```text
hour
```

است.

اگر پروتکل مقدار را مثلاً بر حسب ثانیه یا دقیقه ارسال کند، `Protocol Decoder` باید آن را به ساعت تبدیل کند.

مثال:

```text
7200 seconds
      ↓
2 hours
```

---

## 6. Device Engine Hours و SANA Calculated Engine Hours

دو مفهوم مستقل خواهیم داشت.

### Device Engine Hours

مقداری که خود دستگاه گزارش می‌کند:

```text
GPS Device
    ↓
Protocol Decoder
    ↓
Normalized Telemetry
    ↓
engine_hours
```

### SANA Calculated Engine Hours

SANA می‌تواند در آینده با استفاده از داده‌هایی مانند:

```text
ignition
motion
device_time
```

مدت کارکرد موتور را خودش محاسبه کند.

مثلاً:

```text
08:00 → Ignition ON
09:30 → Ignition OFF

Calculated Engine Hours = 1.5 h
```

این مقدار باید یک مفهوم جدا از `engine_hours` دستگاه باشد.

نام مفهومی/فیلد محاسباتی SANA:

```text
calculated_engine_hours
```

این فیلد فعلاً در Normalized Telemetry الزامی نیست و در صورت نیاز در طراحی لایه محاسباتی SANA تعریف خواهد شد.

---

## 7. مالکیت مقدار

این اصل برای معماری SANA قطعی است:

> **مالک مقدار `engine_hours` خود Device است، نه SANA.**

یعنی اگر دستگاه مقدار زیر را گزارش کند:

```text
engine_hours = 4382.75
```

SANA این مقدار را:

1. دریافت می‌کند.
2. از پروتکل استخراج می‌کند.
3. در صورت نیاز واحد آن را Normalize می‌کند.
4. اعتبار فنی اولیه آن را بررسی می‌کند.
5. مقدار گزارش‌شده را بدون جایگزینی با محاسبات خودش نگهداری می‌کند.

جریان:

```text
GPS Device
     │
     │  engine_hours = 4382.75
     ▼
Protocol Decoder
     │
     │  Normalize
     ▼
Normalized Telemetry
     │
     │  engine_hours = 4382.75
     ▼
Telemetry Processing / Storage
```

SANA نباید صرفاً به دلیل اینکه مقدار محاسبه‌شده خودش متفاوت است، مقدار Device را تغییر دهد.

---

## 8. مالکیت مقادیر محاسباتی SANA

اگر SANA در آینده Engine Hours را خودش محاسبه کند، این مقدار **مالکیت SANA** را دارد و باید مفهوم مستقلی داشته باشد.

مثلاً:

```text
Device-reported:
engine_hours = 5200.0 h

SANA-calculated:
calculated_engine_hours = 5178.4 h
```

این دو مقدار نباید در یک فیلد قرار بگیرند.

قاعده کلی:

```text
Device-reported value
→ متعلق به Device

SANA-calculated value
→ متعلق به SANA
```

بنابراین SANA مقدار محاسباتی خودش را نباید روی مقدار گزارش‌شده Device بنویسد.

---

## 9. اعتبارسنجی با مالکیت مقدار متفاوت است

اگر Device مقداری غیرعادی گزارش کند:

```text
1002.8
↓
15.3
```

SANA می‌تواند این مقدار را بررسی کند و آن را به‌عنوان:

* Reset
* Rollover
* Rollback
* Packet مشکوک
* Device Replacement

علامت‌گذاری یا مدیریت کند.

اما این موضوع به معنی تغییر مالکیت مقدار نیست.

یعنی:

```text
Device → 15.3
```

همچنان مقدار گزارش‌شده توسط Device است.

اعتبارسنجی و تصمیم درباره استفاده از آن در محاسبات، در لایه:

```text
Telemetry Processing
```

انجام می‌شود.

---

## 10. علت جداسازی

ممکن است:

```text
Device Engine Hours
= 5200 h

SANA Calculated Engine Hours
= 5178.4 h
```

باشند.

این اختلاف الزاماً به معنی خرابی یکی از آنها نیست.

دلایل ممکن:

* دستگاه قبل از اتصال به SANA کار کرده است.
* بخشی از Telemetry به SANA نرسیده است.
* دستگاه Reset شده است.
* تنظیمات یا Firmware دستگاه تغییر کرده است.
* روش محاسبه دستگاه با روش SANA متفاوت است.
* داده‌های ignition کامل نیستند.

بنابراین این دو مقدار نباید به زور یکسان شوند.

---

## 11. Cumulative بودن

Engine Hours یک مقدار تجمعی است.

مثلاً:

```text
1000.2
1000.8
1001.4
1002.1
```

طبیعی است.

اما اگر مقدار کاهش پیدا کند:

```text
1002.1
1002.8
15.3
15.9
```

نباید فوراً آن را به‌عنوان خطا یا کارکرد منفی موتور تفسیر کرد.

احتمالات:

* Reset شدن دستگاه
* تعویض Device
* Reset شدن Counter
* Rollover
* Packet خراب
* رفتار خاص Firmware

بررسی این موارد در لایه:

```text
Telemetry Processing
```

انجام می‌شود.

---

## 12. مسئولیت Protocol Decoder

Decoder وظیفه دارد مقدار پروتکل را استخراج و Normalize کند:

```text
Protocol Data
      ↓
Protocol Decoder
      ↓
Normalized Telemetry
      ↓
engine_hours
```

تشخیص Reset، Rollback، Rollover و ناسازگاری مقدار، مسئولیت Decoder نیست و در لایه Processing انجام می‌شود.

---

## 13. Device Replacement

Engine Hours به Device وابسته است.

مثلاً:

```text
Vehicle A
Device 1001
Engine Hours = 8000 h
```

بعد دستگاه تعویض می‌شود:

```text
Vehicle A
Device 2002
Engine Hours = 1200 h
```

نباید SANA این تغییر را به‌عنوان کاهش کارکرد موتور خودرو تفسیر کند.

در آینده، در صورت نیاز تجاری، می‌توان یک مفهوم مستقل برای **Vehicle Total Engine Hours** طراحی کرد که مستقل از شمارنده هر Device باشد.

فعلاً این مفهوم وارد Normalized Telemetry نمی‌شود.

---

## 14. ارتباط با Trip

Engine Hours می‌تواند اطلاعات مفیدی برای Trip فراهم کند.

مثلاً:

```text
Trip Start
engine_hours = 4382.70

Trip End
engine_hours = 4383.45
```

اختلاف:

```text
0.75 hour
```

است.

اما Trip نباید فقط به Engine Hours وابسته باشد.

Trip Engine می‌تواند از ترکیب:

```text
Location
Speed
Motion
Ignition
Timestamp
Engine Hours
```

استفاده کند.

---

## 15. ارتباط با Ignition

در آینده می‌توان سازگاری بین Telemetryها را بررسی کرد.

مثلاً:

```text
ignition = OFF
engine_hours افزایش پیدا کند
```

این وضعیت می‌تواند نیازمند بررسی باشد.

اما نباید بدون درنظر گرفتن رفتار خاص Device و Protocol، فوراً به‌عنوان خطا یا Event قطعی ثبت شود.

این بررسی در:

```text
Telemetry Processing / Consistency Check
```

انجام خواهد شد.

---

## 16. Precision

نوع داده `Decimal` انتخاب می‌شود تا مقادیر اعشاری مانند:

```text
4382.75 h
```

قابل ذخیره باشند.

دقت دقیق Storage در مرحله طراحی Database مشخص خواهد شد.

---

## 17. مرز Storage و Presentation

اصل معماری:

> **Storage حقیقت فنی را نگه می‌دارد، API مقدار استاندارد را ارائه می‌کند و Frontend مسئول Presentation است.**

### Storage

مقدار Normalize‌شده و عددی ذخیره می‌شود:

```text
engine_hours = 4382.75
```

Storage نباید مقدار نمایشی مانند:

```text
"۴۳۸۲ ساعت و ۴۵ دقیقه"
```

را ذخیره کند.

واحد منطقی مقدار در Storage:

```text
hour
```

است.

### API

Backend مقدار استاندارد و عددی را ارائه می‌کند:

```json
{
  "engine_hours": 4382.75
}
```

API نباید مقدار را به متن مخصوص UI تبدیل کند.

### Frontend

Frontend مسئول تبدیل مقدار عددی به نمایش مناسب کاربر است.

مثلاً:

```text
4382.75
      ↓
۴٬۳۸۲٫۷۵ ساعت
```

یا در صفحه‌ای که خوانایی مهم‌تر است:

```text
۴٬۳۸۲ ساعت و ۴۵ دقیقه
```

تغییر زبان، قالب عدد یا نحوه نمایش نباید باعث تغییر Storage یا قرارداد API شود.

---

## 18. مرز Raw Packet، Normalized Telemetry و Presentation

این سه لایه باید از یکدیگر جدا باشند:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Normalized Telemetry
    ↓
Storage / Processing
    ↓
API
    ↓
Presentation
```

### Raw Packet

داده واقعی دریافتی از Device برای Debug، بررسی Protocol و عیب‌یابی نگهداری می‌شود.

مثلاً ممکن است دستگاه مقدار را به ثانیه ارسال کرده باشد.

### Normalized Telemetry

مقدار استاندارد SANA:

```text
engine_hours = 4382.75
unit = hour
```

### Presentation

مقداری که کاربر می‌بیند و توسط Frontend Format می‌شود:

```text
۴٬۳۸۲ ساعت و ۴۵ دقیقه
```

هیچ‌کدام نباید با دیگری مخلوط شوند.

---

# 19. نام‌گذاری‌های نهایی

نام‌گذاری این بخش از این لحظه ثابت است:

```text
engine_hours
```

برای:

> Device-reported cumulative engine running time

و:

```text
calculated_engine_hours
```

برای:

> SANA-calculated engine running time

این دو مفهوم نباید در یک فیلد ادغام شوند.

همچنین فعلاً این نام‌ها را وارد Normalized Telemetry نمی‌کنیم:

```text
vehicle_total_engine_hours
```

زیرا مجموع کارکرد خودرو در طول عمر آن، مستقل از Device، نیازمند طراحی جداگانه برای Device Replacement و Vehicle History است.

---

# 20. تصمیم نهایی

قرارداد نهایی:

```text
engine_hours
Type: Decimal
Unit: hour
Nullable: Yes
Source: Device
Meaning: Device-reported cumulative engine running time
Owner: Device
```

قواعد نهایی:

1. `engine_hours` یک مقدار تجمعی است.
2. واحد استاندارد `hour` است.
3. `NULL` یعنی داده موجود نیست.
4. `0` با `NULL` متفاوت است.
5. `ignition` و `engine_hours` مستقل هستند.
6. مالک مقدار `engine_hours` خود Device است.
7. SANA مقدار گزارش‌شده Device را با مقدار محاسباتی خودش جایگزین نمی‌کند.
8. SANA می‌تواند در آینده Engine Hours مستقل خودش را محاسبه کند.
9. `calculated_engine_hours` از `engine_hours` مستقل است.
10. اعتبارسنجی مقدار با مالکیت مقدار متفاوت است.
11. Reset / Rollover / Rollback در Telemetry Processing بررسی می‌شوند.
12. تعویض Device نباید باعث کاهش مصنوعی کارکرد موتور Vehicle شود.
13. Trip نباید فقط به Engine Hours وابسته باشد.
14. Protocol Decoder فقط وظیفه استخراج و Normalization مقدار را دارد.
15. هر مقدار محاسباتی SANA باید با مفهوم/فیلد مستقل از مقدار Device نگهداری شود.
16. Storage مقدار عددی Normalize‌شده را نگه می‌دارد.
17. API مقدار استاندارد عددی را ارائه می‌کند.
18. Frontend مسئول Format و نمایش خوانای مقدار است.
19. مقدار نمایشی نباید در Storage ذخیره شود.
20. Raw Packet، Normalized Telemetry و Presentation سه لایه مستقل هستند.
21. `vehicle_total_engine_hours` فعلاً در Normalized Telemetry تعریف نمی‌شود.
22. نام `engine_hours` فقط برای مقدار گزارش‌شده توسط Device استفاده می‌شود.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry

## بخش: Fuel Level

### 1. تعریف

`fuel_level` مقدار فعلی سوخت موجود در مخزن خودرو است.

هدف SANA از این فیلد فقط مشخص کردن مقدار سوخت موجود در خودرو در یک لحظه است.

مثال:

```text
fuel_level = 38.4 L
```

این فیلد با مصرف سوخت، مقدار سوخت مصرف‌شده، ولتاژ سنسور یا مقدار خام سنسور یکسان نیست.

---

## 2. نام فیلد نهایی

نام استاندارد این مفهوم در SANA:

```text
fuel_level
```

است.

از نام عمومی `fuel` استفاده نمی‌کنیم، چون `fuel` می‌تواند مفاهیم مختلفی مانند مصرف، مقدار مصرف‌شده یا سطح سوخت را شامل شود.

---

## 3. تعریف فیلد

```text
fuel_level
Type: Decimal
Unit: liter
Nullable: Yes
Source: Device / Sensor
Meaning: Current normalized fuel quantity
```

---

## 4. واحد استاندارد

واحد استاندارد SANA برای `fuel_level`:

```text
liter
```

است.

دلیل انتخاب لیتر این است که مقدار سوخت موجود برای کاربر نهایی، راننده و مسئول ناوگان به‌صورت حجم قابل فهم‌تر است.

مثلاً:

```text
38.4 L
```

به‌جای:

```text
64 %
```

نمایش داده می‌شود.

---

## 5. Device ممکن است داده را با واحدهای مختلف ارسال کند

دستگاه‌ها و پروتکل‌های مختلف ممکن است مقدار Fuel Level را به شکل‌های متفاوت ارسال کنند.

مثلاً:

```text
64 %
```

یا:

```text
38.4 L
```

یا مقدار خام سنسور.

این تفاوت در لایه Protocol Decoder و Fuel Normalization مدیریت می‌شود.

هدف خروجی Normalized Telemetry همیشه تولید:

```text
fuel_level
```

بر حسب:

```text
liter
```

است.

---

## 6. اگر Device مستقیماً لیتر گزارش کند

اگر دستگاه مقدار واقعی سوخت را بر حسب لیتر گزارش کند:

```text
Device
fuel = 38.4 L
```

Decoder مقدار را استخراج و در صورت نیاز Normalize می‌کند:

```text
Device
   ↓
Protocol Decoder
   ↓
fuel_level = 38.4 L
```

در این حالت نیازی به تبدیل با ظرفیت مخزن وجود ندارد.

---

## 7. اگر Device درصد گزارش کند

اگر دستگاه سطح سوخت را به‌صورت درصد گزارش کند:

```text
fuel = 64 %
```

SANA می‌تواند با استفاده از ظرفیت مخزن خودرو آن را به لیتر تبدیل کند.

مثلاً:

```text
Vehicle:
tank_capacity = 60 L

Device:
fuel = 64 %
```

محاسبه:

```text
64 × 60 / 100
= 38.4 L
```

نتیجه:

```text
fuel_level = 38.4 L
```

---

## 8. Tank Capacity متعلق به Vehicle است

ظرفیت مخزن مربوط به خودرو است، نه Device.

مثلاً:

```text
Vehicle A
tank_capacity = 60 L
```

اگر Device خودرو تعویض شود:

```text
Vehicle A
    ↓
Device 1001
```

و بعد:

```text
Vehicle A
    ↓
Device 2002
```

ظرفیت مخزن خودرو همچنان:

```text
60 L
```

است.

بنابراین:

```text
Vehicle
└── tank_capacity
```

و نه:

```text
Device
└── tank_capacity
```

---

## 9. منبع Tank Capacity

منبع اصلی `tank_capacity` اطلاعات ثبت‌شده در SANA برای خود Vehicle است.

این مقدار توسط کاربر مجاز سیستم و بر اساس اطلاعات واقعی خودرو/مخزن ثبت می‌شود.

مثلاً:

```text
Vehicle
└── tank_capacity = 60 L
```

دستگاه GPS منبع تعیین ظرفیت مخزن نیست.

اگر اطلاعات کارخانه‌ای خودرو ظرفیت مخزن را مشخص کرده باشد، می‌توان از همان مقدار به‌عنوان مبنای ثبت در SANA استفاده کرد.

اگر مخزن خودرو تعویض، اصلاح یا تغییر داده شود، مقدار جدید باید در SANA ثبت شود.

---

## 10. مدل زمانی Tank Capacity

`tank_capacity` باید دارای تاریخچه باشد و فقط به‌صورت یک مقدار فعلی بدون سابقه نگهداری نشود.

دلیل این تصمیم این است که ظرفیت مخزن ممکن است در طول عمر Vehicle تغییر کند.

مثلاً:

```text
Vehicle A

60 L
valid_from = 2026-01-01
valid_to   = 2026-06-15
```

و بعد:

```text
80 L
valid_from = 2026-06-15
valid_to   = NULL
```

`NULL` در `valid_to` یعنی این رکورد در حال حاضر معتبر است.

بنابراین از نظر مفهومی:

```text
Vehicle
    ↓
Tank Capacity History
    ├── 60 L
    │   ├── valid_from
    │   └── valid_to
    │
    └── 80 L
        ├── valid_from
        └── valid_to = NULL
```

---

## 11. ظرفیت معتبر در زمان Telemetry

برای تبدیل Fuel به لیتر، SANA نباید همیشه از ظرفیت فعلی Vehicle استفاده کند.

ظرفیت مورد استفاده باید ظرفیتی باشد که در زمان `device_time` آن Telemetry معتبر بوده است.

مثلاً:

```text
10:00
tank_capacity = 60 L
fuel = 50 %
```

پس:

```text
fuel_level = 30 L
```

بعداً در ساعت 12:00 ظرفیت مخزن تغییر می‌کند:

```text
tank_capacity = 80 L
```

Telemetry ساعت 10:00 نباید به‌صورت تاریخی تغییر کند و همچنان:

```text
fuel_level = 30 L
```

است.

---

## 12. رابطه Device Time با Tank Capacity

برای Telemetry تاریخی، مبنای انتخاب ظرفیت مخزن:

```text
device_time
```

است.

جریان:

```text
Device
   ↓
device_time
   ↓
Vehicle
   ↓
Tank Capacity History
   ↓
Capacity valid at device_time
   ↓
Fuel Normalization
```

بنابراین اگر:

```text
device_time = 2026-06-10 10:00
```

باشد، SANA ظرفیت مخزنی را انتخاب می‌کند که در آن زمان معتبر بوده است.

این موضوع باعث می‌شود گزارش‌های تاریخی بعداً با تغییر ظرفیت مخزن خراب نشوند.

---

## 13. قرارداد Tank Capacity

قرارداد مفهومی:

```text
tank_capacity
Type: Decimal
Unit: liter
Nullable: Yes
Owner: Vehicle
Source: Vehicle Configuration
Temporal: Yes
```

تاریخ اعتبار:

```text
valid_from
valid_to
```

است.

---

## 14. Nullable بودن Fuel Level

اگر دستگاه Fuel Level را گزارش نکند:

```text
fuel_level = NULL
```

معتبر است.

همچنین اگر Device مقدار خامی ارسال کند ولی SANA اطلاعات کافی برای تبدیل آن به لیتر نداشته باشد:

```text
fuel_level = NULL
```

است.

نباید مقدار تخمینی یا ساختگی تولید شود.

---

## 15. درصد بدون ظرفیت مخزن

مثلاً:

```text
Device → 64%
Vehicle → tank_capacity = NULL
```

در این حالت SANA نمی‌تواند مقدار واقعی لیتر را مشخص کند.

بنابراین:

```text
fuel_level = NULL
```

و نباید اشتباهاً این مقدار را ثبت کنیم:

```text
fuel_level = 64 L
```

زیرا 64 درصد و 64 لیتر دو مفهوم متفاوت هستند.

---

## 16. Raw Fuel و Normalized Fuel

داده خام و داده Normalize‌شده باید جدا باشند.

مثلاً Device ارسال می‌کند:

```text
fuel = 64%
```

داده خام:

```text
64%
```

بعد SANA با توجه به:

```text
tank_capacity = 60 L
```

محاسبه می‌کند:

```text
fuel_level = 38.4 L
```

بنابراین جریان:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Raw Fuel Value
    ↓
Fuel Normalization
    ↓
fuel_level
```

است.

---

## 17. اگر Device مقدار خام سنسور ارسال کند

ممکن است دستگاه به‌جای درصد یا لیتر، مقدار خام سنسور ارسال کند.

مثلاً:

```text
fuel_sensor = 2.73 V
```

یا:

```text
ADC = 1847
```

این مقدار به‌تنهایی الزاماً نشان‌دهنده مقدار لیتر نیست.

اگر SANA اطلاعات لازم برای تبدیل معتبر را نداشته باشد:

```text
fuel_level = NULL
```

می‌ماند.

مقدار خام برای اهداف فنی و Debug می‌تواند در Raw Packet یا Attributes نگهداری شود، اما به‌عنوان `fuel_level` ثبت نمی‌شود.

---

## 18. Fuel Calibration

در آینده می‌توان برای خودرو Fuel Calibration تعریف کرد.

این قابلیت زمانی اهمیت دارد که سنسور Fuel رفتار خطی نداشته باشد.

مثلاً:

```text
Sensor Value
     ↓
Calibration
     ↓
Fuel Quantity
```

Calibration متعلق به Vehicle/Sensor نصب‌شده روی خودرو است، نه Device GPS.

این قابلیت باید امکان تبدیل معتبر مقدار سنسور به لیتر را فراهم کند.

جزئیات ساختار Calibration در مرحله طراحی مستقل آن مشخص خواهد شد.

---

## 19. فقط Fuel Level

در این مرحله فقط مقدار سوخت موجود مورد نیاز SANA است.

بنابراین این مفاهیم فعلاً جزو Normalized Telemetry نیستند:

```text
fuel_percent
fuel_sensor_voltage
fuel_adc
fuel_consumption
fuel_used
```

مفهوم استاندارد فعلی فقط:

```text
fuel_level
```

است.

در آینده اگر نیاز واقعی وجود داشته باشد، مفاهیم دیگری می‌توانند به‌صورت مستقل طراحی شوند.

---

## 20. اگر Device چند مقدار مربوط به Fuel ارسال کند

ممکن است یک Device چند داده مختلف مربوط به سوخت ارسال کند.

مثلاً:

```text
fuel_percent
fuel_sensor
fuel_liters
```

SANA قرار نیست همه این مقادیر را به‌عنوان فیلدهای مستقل Normalized Telemetry ذخیره کند.

Decoder/Normalization باید بر اساس تعریف Protocol مشخص کند کدام مقدار نشان‌دهنده معتبرترین Fuel Level است و در نهایت یک خروجی استاندارد تولید کند:

```text
fuel_level
```

هدف:

```text
Device Data
      ↓
Fuel Normalization
      ↓
One Standard Value
      ↓
fuel_level = liter
```

---

## 21. مالکیت داده

داده اولیه Fuel توسط Device یا Sensor متصل به آن خودرو تولید می‌شود.

اما `fuel_level` مقدار Normalize‌شده SANA است.

مثلاً:

```text
Device / Sensor
    ↓
64%
    ↓
SANA
    ↓
38.4 L
```

بنابراین:

```text
Raw Fuel Value
→ Source: Device / Sensor

fuel_level
→ Normalized Value
→ Standardized by SANA
```

اگر Device مستقیماً لیتر گزارش کند، SANA فقط استخراج و Normalization واحد را انجام می‌دهد.

---

## 22. Fuel Level و Device Replacement

`fuel_level` مربوط به وضعیت سوخت خودرو در زمان Telemetry است.

تعویض Device نباید باعث ایجاد مخزن جدید برای Vehicle شود.

مثلاً:

```text
Vehicle A
Tank = 60 L

Device 1001
fuel_level = 40 L
```

بعد:

```text
Device 1001
    ↓
Device 2002
```

خودرو همچنان:

```text
Tank = 60 L
```

دارد.

Device صرفاً منبع دریافت Telemetry است.

---

## 23. Fuel Level و Vehicle History

چون ظرفیت مخزن متعلق به Vehicle است، تاریخچه سوخت نیز در تحلیل‌های آینده باید در ارتباط با تاریخچه Vehicle و Device در نظر گرفته شود.

تعویض Device نباید باعث شود SANA تصور کند که خودرو دارای مخزن یا Fuel History جدیدی شده است.

---

## 24. ارتباط با Alert

در آینده می‌توان Alertهایی مانند:

```text
Low Fuel
```

ایجاد کرد.

مثلاً:

```text
fuel_level < 10 L
```

اما منطق Alert در این مرحله طراحی نمی‌شود.

`fuel_level` فقط Telemetry است.

Event/Alert Engine بعداً از این مقدار استفاده خواهد کرد.

---

## 25. ارتباط با Trip و Reports

`fuel_level` می‌تواند در آینده در مواردی مانند:

```text
Trip Start Fuel
Trip End Fuel
Fuel Change
Fuel Report
```

استفاده شود.

اما این محاسبات بخشی از `NormalizedTelemetry` نیستند و در لایه‌های Trip / Reporting انجام خواهند شد.

---

## 26. مرز Storage و Presentation

اصل معماری:

> Storage حقیقت فنی را نگه می‌دارد، API مقدار استاندارد را ارائه می‌کند و Frontend مسئول Presentation است.

### Storage

مقدار عددی Normalize‌شده ذخیره می‌شود:

```text
fuel_level = 38.4
```

واحد منطقی:

```text
liter
```

است.

Storage نباید متن نمایشی مانند:

```text
"۳۸٫۴ لیتر"
```

ذخیره کند.

### API

Backend مقدار استاندارد عددی را ارائه می‌کند:

```json
{
  "fuel_level": 38.4
}
```

API نباید مقدار را به متن مخصوص UI تبدیل کند.

### Frontend

Frontend مسئول نمایش مقدار است:

```text
38.4
   ↓
۳۸٫۴ لیتر
```

فرمت عدد، زبان و نحوه نمایش نباید روی Storage یا قرارداد API اثر بگذارد.

---

## 27. مرز Raw Packet، Normalized Telemetry و Presentation

ساختار کلی:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Fuel Normalization
    ↓
Normalized Telemetry
    ↓
Storage / Processing
    ↓
API
    ↓
Frontend
    ↓
Presentation
```

### Raw Packet

داده واقعی دریافت‌شده از Device.

### Normalized Telemetry

مقدار استاندارد:

```text
fuel_level = 38.4 L
```

### Presentation

مقداری که کاربر می‌بیند:

```text
۳۸٫۴ لیتر
```

این سه لایه نباید با یکدیگر مخلوط شوند.

---

# 28. قرارداد نهایی

```text
fuel_level
Type: Decimal
Unit: liter
Nullable: Yes
Source: Device / Sensor
Meaning: Current normalized fuel quantity
```

در Vehicle:

```text
tank_capacity
Type: Decimal
Unit: liter
Nullable: Yes
Owner: Vehicle
Source: Vehicle Configuration
Temporal: Yes
```

مدل زمانی:

```text
tank_capacity_history
├── tank_capacity
├── valid_from
└── valid_to
```

قاعده انتخاب:

```text
Telemetry.device_time
        ↓
Tank Capacity valid at that time
        ↓
Fuel normalization
```

---

# 29. قواعد نهایی

1. نام استاندارد Fuel Level در SANA برابر `fuel_level` است.
2. واحد استاندارد `fuel_level` برابر `liter` است.
3. هدف فیلد، نمایش مقدار فعلی سوخت موجود در خودرو است.
4. `fuel_level` با Fuel Consumption و Fuel Used متفاوت است.
5. اگر Device مستقیماً لیتر بدهد، مقدار مستقیماً Normalize می‌شود.
6. اگر Device درصد بدهد، در صورت وجود ظرفیت مخزن، درصد به لیتر تبدیل می‌شود.
7. `tank_capacity` متعلق به Vehicle است، نه Device.
8. منبع اصلی `tank_capacity`، Vehicle Configuration در SANA است.
9. Device GPS منبع تعیین ظرفیت مخزن نیست.
10. `tank_capacity` یک مقدار زمانی است و باید تاریخچه تغییرات آن حفظ شود.
11. هر رکورد ظرفیت دارای `valid_from` و `valid_to` مفهومی است.
12. ظرفیت فعلی با `valid_to = NULL` مشخص می‌شود.
13. برای Telemetry تاریخی، ظرفیت مخزن بر اساس `device_time` انتخاب می‌شود.
14. تغییر ظرفیت مخزن نباید مقدار تاریخی `fuel_level` را تغییر دهد.
15. تعویض Device نباید ظرفیت مخزن Vehicle را تغییر دهد.
16. اگر درصد دریافت شود ولی ظرفیت معتبر برای زمان Telemetry وجود نداشته باشد، `fuel_level = NULL` خواهد بود.
17. اگر مقدار خام سنسور دریافت شود ولی اطلاعات کافی برای تبدیل وجود نداشته باشد، `fuel_level = NULL` خواهد بود.
18. نباید برای داده نامعتبر یا ناکافی مقدار تخمینی ساختگی تولید شود.
19. Raw Fuel Value با `fuel_level` یکسان نیست.
20. Protocol Decoder مسئول تشخیص معنی مقدار طبق Protocol و استخراج آن است.
21. Fuel Normalization مسئول تبدیل معتبر مقدار به واحد استاندارد لیتر است.
22. اگر Device چند مقدار مربوط به Fuel ارسال کند، خروجی استاندارد Normalized Telemetry فقط `fuel_level` خواهد بود.
23. `fuel_percent`، `fuel_sensor_voltage` و `fuel_adc` فعلاً فیلد استاندارد Normalized Telemetry نیستند.
24. Fuel Calibration در آینده قابل اضافه شدن است و متعلق به Vehicle/Sensor Configuration خواهد بود.
25. `fuel_level` یک Telemetry است، نه Event یا Alert.
26. منطق Low Fuel Alert در Alert Engine آینده پیاده‌سازی می‌شود.
27. Storage مقدار عددی Normalize‌شده را ذخیره می‌کند.
28. API مقدار استاندارد عددی را ارائه می‌کند.
29. Frontend مسئول Format و نمایش مقدار با واحد لیتر است.
30. مقدار نمایشی نباید در Storage ذخیره شود.
31. Raw Packet، Normalized Telemetry و Presentation سه لایه مستقل هستند.
32. نام `fuel` به‌عنوان فیلد استاندارد استفاده نمی‌شود؛ مفهوم دقیق استاندارد `fuel_level` است.
33. ظرفیت مخزن از Vehicle Configuration می‌آید و مالکیت آن با Vehicle است.
34. تاریخچه ظرفیت مخزن باید مستقل از Device نگهداری شود.
35. تعویض Device نباید تاریخچه یا ظرفیت مخزن Vehicle را reset کند.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry

## بخش: Temperature

### 1. تعریف

`temperature` دمایی است که توسط Device یا Sensor متصل به آن گزارش می‌شود.

SANA در سطح Normalized Telemetry فعلاً کاری به محل نصب سنسور ندارد.

ممکن است سنسور:

```text
روی موتور
داخل کابین
داخل محفظه بار
داخل یخچال
نزدیک باتری
یا هر محل دیگری
```

قرار گرفته باشد.

اما در این مرحله همه این موارد یک مفهوم عمومی دارند:

```text
temperature
```

هدف این فیلد، نگهداری مقدار دمای گزارش‌شده توسط Device/Sensor در یک لحظه است.

---

## 2. نام فیلد نهایی

نام استاندارد این مفهوم در SANA:

```text
temperature
```

است.

فعلاً از نام‌هایی مانند:

```text
engine_temperature
cabin_temperature
cargo_temperature
battery_temperature
```

به‌عنوان فیلدهای استاندارد Normalized Telemetry استفاده نمی‌کنیم.

---

## 3. قرارداد فیلد

```text
temperature
Type: Decimal
Unit: °C
Nullable: Yes
Source: Device / Sensor
Meaning: Current temperature reported by the device/sensor
```

---

## 4. واحد استاندارد

واحد استاندارد SANA برای Temperature:

```text
Celsius
```

است.

یعنی:

```text
°C
```

مثال:

```text
temperature = 24.6 °C
```

---

## 5. Device ممکن است دما را با واحدهای مختلف ارسال کند

Protocolهای مختلف ممکن است دما را با واحدهای متفاوت گزارش کنند.

مثلاً:

```text
24.6 °C
```

یا:

```text
76.28 °F
```

در صورتی که Device دما را با Fahrenheit ارسال کند، تبدیل به Celsius در مرحله Normalization انجام می‌شود.

هدف خروجی Normalized Telemetry همیشه:

```text
temperature = Celsius
```

است.

---

## 6. اگر Device مستقیماً Celsius گزارش کند

اگر Device مقدار دما را مستقیماً بر حسب Celsius ارسال کند:

```text
Device
temperature = 24.6 °C
```

Decoder مقدار را استخراج می‌کند و در صورت نیاز فقط Normalization لازم را انجام می‌دهد:

```text
Device
    ↓
Protocol Decoder
    ↓
Temperature Normalization
    ↓
temperature = 24.6 °C
```

---

## 7. اگر Device Fahrenheit گزارش کند

اگر Device دما را بر حسب Fahrenheit گزارش کند:

```text
Device
temperature = 76.28 °F
```

SANA آن را به Celsius تبدیل می‌کند.

فرمول:

```text
°C = (°F - 32) × 5 / 9
```

مثلاً:

```text
76.28 °F
≈ 24.6 °C
```

خروجی Normalized:

```text
temperature = 24.6 °C
```

---

## 8. اگر Device مقدار خام Sensor ارسال کند

ممکن است Device به‌جای دمای نهایی، مقدار خام سنسور را ارسال کند.

مثلاً:

```text
ADC = 1847
```

یا:

```text
Sensor Raw Value = 2.73 V
```

این مقدار به‌تنهایی الزاماً نشان‌دهنده دمای مشخصی نیست.

اگر اطلاعات لازم برای تبدیل معتبر به دما وجود نداشته باشد:

```text
temperature = NULL
```

می‌شود.

مقدار خام می‌تواند در Raw Packet یا Attributes برای اهداف فنی و Debug نگهداری شود.

نباید مقدار نامعتبر را به‌عنوان Temperature استاندارد ثبت کنیم.

---

## 9. اگر Device دما ارسال نکند

همه Deviceها الزاماً سنسور Temperature ندارند.

بنابراین اگر Device دما گزارش نکند:

```text
temperature = NULL
```

کاملاً معتبر است.

عدم وجود Temperature به معنی صفر درجه نیست.

بنابراین:

```text
NULL ≠ 0 °C
```

است.

---

## 10. صفر درجه

مقدار:

```text
temperature = 0 °C
```

یک مقدار واقعی و معتبر است.

بنابراین نباید `0` را به‌عنوان مقدار ناموجود تفسیر کنیم.

قاعده:

```text
NULL → Temperature unavailable
0    → Actual zero Celsius
```

---

## 11. مقادیر منفی

Temperature می‌تواند منفی باشد.

مثلاً:

```text
temperature = -12.5 °C
```

یک مقدار معتبر است، مشروط بر اینکه با محدوده قابل قبول Device/Sensor و Protocol سازگار باشد.

نباید منفی بودن مقدار به‌تنهایی باعث Invalid شدن آن شود.

---

## 12. محدوده اعتبار

محدوده فیزیکی Temperature به نوع سنسور و Device وابسته است.

بنابراین Normalized Telemetry نباید یک محدوده مصنوعی و عمومی برای همه Deviceها تعیین کند.

مثلاً یک سنسور ممکن است:

```text
-40°C تا +85°C
```

را پشتیبانی کند و سنسور دیگری محدوده متفاوتی داشته باشد.

محدودیت‌های سخت‌افزاری و Validation مربوط به Device/Sensor باید در لایه مناسب خودش بررسی شود.

---

## 13. Temperature عمومی است

در این مرحله SANA فقط یک مفهوم عمومی دارد:

```text
temperature
```

این مقدار می‌تواند از هر Sensor معتبر متصل به Device دریافت شود.

SANA فعلاً نمی‌گوید:

```text
این دما حتماً دمای موتور است
```

یا:

```text
این دما حتماً دمای کابین است
```

مگر اینکه در آینده Sensor Configuration چنین اطلاعاتی را تعریف کند.

---

## 14. محل نصب Sensor

محل نصب سنسور فعلاً بخشی از `NormalizedTelemetry.temperature` نیست.

مثلاً:

```text
Vehicle A
   └── GPS Device
         └── Temperature Sensor
```

ممکن است سنسور داخل کابین نصب شده باشد.

اما Normalized Telemetry فقط:

```text
temperature = 24.6 °C
```

را نگهداری می‌کند.

اطلاعاتی مانند:

```text
sensor_location
sensor_type
sensor_id
```

در این مرحله جزو قرارداد `temperature` نیستند.

---

## 15. چند Temperature در یک Device

در این مرحله فرض اصلی SANA این است که برای Normalized Telemetry یک مقدار استاندارد:

```text
temperature
```

داریم.

اگر یک Device چند سنسور دما داشته باشد، موضوع نحوه مدیریت چند Sensor در آینده و در طراحی Sensor Configuration بررسی می‌شود.

فعلاً نباید با اضافه کردن فیلدهایی مانند:

```text
temperature_1
temperature_2
temperature_3
```

مدل Normalized Telemetry را پیچیده کنیم.

---

## 16. Raw Temperature و Normalized Temperature

داده خام و مقدار Normalize‌شده جدا هستند.

مثلاً Device ارسال می‌کند:

```text
76.28 °F
```

داده خام:

```text
76.28 °F
```

بعد SANA آن را تبدیل می‌کند:

```text
temperature = 24.6 °C
```

بنابراین:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Raw Temperature
    ↓
Temperature Normalization
    ↓
temperature
```

است.

---

## 17. مالکیت داده

داده اولیه Temperature توسط:

```text
Device / Sensor
```

تولید می‌شود.

اما:

```text
temperature
```

یک مقدار Normalize‌شده و استانداردشده توسط SANA است.

مثلاً:

```text
Device / Sensor
    ↓
76.28 °F
    ↓
SANA
    ↓
24.6 °C
```

---

## 18. Temperature و Device Replacement

Temperature مربوط به Telemetry یک Device در یک زمان مشخص است.

تعویض Device باعث نمی‌شود SANA Temperature History خودرو را به‌صورت مفهومی از نو شروع کند.

Device صرفاً منبع دریافت Telemetry است.

در آینده برای گزارش تاریخی Vehicle، تاریخچه Deviceهای متصل به Vehicle باید در نظر گرفته شود.

---

## 19. Temperature و Vehicle History

Temperature می‌تواند در آینده در تاریخچه Telemetry خودرو قابل مشاهده باشد.

مثلاً:

```text
Vehicle A
   ↓
Device 1001
   ↓
Temperature History
```

بعد از تعویض Device:

```text
Vehicle A
   ↓
Device 2002
   ↓
Temperature History
```

در تحلیل Vehicle، این تاریخچه‌ها می‌توانند در کنار هم قرار گیرند.

---

## 20. Temperature و Alert

در آینده Temperature می‌تواند ورودی Alert Engine باشد.

مثلاً:

```text
temperature > threshold
```

یا:

```text
temperature < threshold
```

اما Threshold و منطق Alert در این مرحله طراحی نمی‌شود.

`temperature` خودش فقط Telemetry است.

---

## 21. Temperature و Trip / Reports

در آینده Temperature می‌تواند در گزارش‌ها استفاده شود.

مثلاً:

```text
Minimum Temperature
Maximum Temperature
Average Temperature
Temperature History
```

اما این محاسبات بخشی از Normalized Telemetry نیستند.

Normalized Telemetry فقط مقدار خام Normalize‌شده را ارائه می‌کند:

```text
temperature
```

---

## 22. Storage

در Storage مقدار عددی ذخیره می‌شود.

مثلاً:

```text
temperature = 24.6
```

واحد منطقی:

```text
°C
```

است.

نباید مقدار نمایشی ذخیره شود:

```text
"۲۴٫۶ درجه"
```

---

## 23. API

API مقدار استاندارد عددی را ارائه می‌کند.

مثلاً:

```json
{
  "temperature": 24.6
}
```

Backend نباید مقدار را به متن مخصوص Frontend تبدیل کند.

---

## 24. Presentation

Frontend مسئول نمایش Temperature است.

مثلاً:

```text
24.6
   ↓
۲۴٫۶ °C
```

فرمت عدد، زبان و نحوه نمایش متعلق به Presentation Layer است.

---

## 25. مرز Raw Packet، Normalized Telemetry و Presentation

جریان نهایی:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Temperature Normalization
    ↓
Normalized Telemetry
    ↓
Storage / Processing
    ↓
API
    ↓
Frontend
    ↓
Presentation
```

### Raw Packet

داده واقعی دریافت‌شده از Device.

### Normalized Telemetry

مقدار استاندارد:

```text
temperature = 24.6 °C
```

### Presentation

مقداری که کاربر می‌بیند:

```text
۲۴٫۶ °C
```

این سه لایه مستقل هستند.

---

# 26. قرارداد نهایی

```text
temperature
Type: Decimal
Unit: °C
Nullable: Yes
Source: Device / Sensor
Meaning: Current temperature reported by the device/sensor
```

---

# 27. قواعد نهایی

1. نام استاندارد Temperature در SANA برابر `temperature` است.
2. واحد استاندارد Temperature برابر Celsius (`°C`) است.
3. `temperature` یک مفهوم عمومی است.
4. محل نصب Sensor فعلاً بخشی از Normalized Telemetry نیست.
5. فعلاً فیلدهایی مانند `engine_temperature` و `cabin_temperature` نداریم.
6. اگر Device مستقیماً Celsius بدهد، مقدار Normalize می‌شود.
7. اگر Device Fahrenheit بدهد، به Celsius تبدیل می‌شود.
8. اگر Device مقدار خام Sensor بدهد و تبدیل معتبر ممکن نباشد، `temperature = NULL` است.
9. اگر Device Temperature ارسال نکند، `temperature = NULL` است.
10. `NULL` به معنی صفر درجه نیست.
11. `0 °C` یک مقدار واقعی و معتبر است.
12. Temperature می‌تواند مقدار منفی داشته باشد.
13. محدوده فیزیکی Sensor نباید به‌صورت یک محدوده مصنوعی و عمومی برای تمام Deviceها تعیین شود.
14. Protocol Decoder مسئول استخراج Temperature از Protocol است.
15. Temperature Normalization مسئول تبدیل معتبر به Celsius است.
16. Raw Temperature با Normalized Temperature یکسان نیست.
17. `temperature` یک Telemetry است، نه Event یا Alert.
18. Alert Engine آینده می‌تواند از Temperature استفاده کند.
19. Trip و Reporting می‌توانند در آینده از Temperature استفاده کنند.
20. Storage مقدار عددی را نگهداری می‌کند.
21. API مقدار استاندارد عددی را ارائه می‌کند.
22. Frontend مسئول Presentation و Format است.
23. مقدار نمایشی نباید در Storage ذخیره شود.
24. Raw Packet، Normalized Telemetry و Presentation سه لایه مستقل هستند.
25. فعلاً مدل Temperature را عمداً عمومی و ساده نگه می‌داریم.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry

## بخش: Digital Inputs

### 1. تعریف

دستگاه‌های GPS ممکن است چندین ورودی دیجیتال داشته باشند.

این ورودی‌ها معمولاً به‌صورت وضعیت:

```text
ON / OFF
true / false
```

گزارش می‌شوند.

مثلاً:

```text
Input 1 = ON
Input 2 = OFF
Input 3 = ON
```

اما معنی این ورودی‌ها بین Deviceها و Protocolهای مختلف یکسان نیست.

ممکن است:

```text
Input 1
```

در یک Device مربوط به Door باشد و در Device دیگر مربوط به Panic Button یا سنسور دیگری.

بنابراین ورودی دیجیتال عمومی به‌صورت یک مفهوم مستقل و ثابت در Normalized Telemetry تعریف نمی‌شود.

---

## 2. تصمیم نهایی

در SANA:

```text
digital_inputs
```

فعلاً **Standard Field** نیست.

ورودی‌های دیجیتال عمومی Device در:

```text
attributes
```

نگهداری می‌شوند.

---

## 3. Ignition استثنا است

`ignition` قبلاً به‌عنوان یک مفهوم استاندارد SANA تعریف شده است.

بنابراین اگر Device یکی از Digital Inputهای خود را به‌عنوان Ignition/ACC گزارش کند و Protocol Decoder بتواند معنی آن را به‌صورت معتبر تشخیص دهد:

```text
Digital Input / ACC
        ↓
Protocol Decoder
        ↓
Ignition Normalization
        ↓
ignition
```

خروجی استاندارد:

```text
ignition = true / false
```

خواهد بود.

در این حالت `ignition` با Digital Input عمومی یکی نیست.

---

## 4. چرا Digital Input استاندارد نیست؟

چون شماره Input به‌تنهایی معنی مشخصی ندارد.

مثلاً:

```text
Input 1
```

می‌تواند در Deviceهای مختلف معنی‌های متفاوتی داشته باشد:

```text
Door
Panic Button
External Sensor
ACC
Alarm
Temperature Sensor
```

بنابراین SANA نباید فرض کند:

```text
Input 1 = Door
```

یا:

```text
Input 2 = Panic
```

مگر اینکه Protocol و Configuration مربوط به آن Device چنین معنایی را مشخص کرده باشند.

---

## 5. محل نگهداری

Digital Inputهای Device-specific در:

```text
attributes
```

قرار می‌گیرند.

مثلاً:

```json
{
  "digital_inputs": {
    "input_1": true,
    "input_2": false,
    "input_3": true
  }
}
```

این داده بخشی از Normalized Telemetry است، اما یک Standard Field مستقل نیست.

---

## 6. Raw و Normalized

داده خام Device:

```text
Input 1 = 1
Input 2 = 0
```

ممکن است توسط Protocol Decoder به ساختار استاندارد داخلی تبدیل شود:

```json
{
  "digital_inputs": {
    "input_1": true,
    "input_2": false
  }
}
```

اما این داده هنوز یک مفهوم Device-specific است.

بنابراین:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Digital Input Normalization
    ↓
attributes.digital_inputs
```

---

## 7. تفاوت با Ignition

اگر:

```text
Input 1 = ACC
```

و Protocol مشخص می‌کند که این Input همان وضعیت Ignition است، SANA باید آن را به:

```text
ignition = true
```

یا:

```text
ignition = false
```

Normalize کند.

در نتیجه ممکن است یک Telemetry هم‌زمان شامل این دو باشد:

```json
{
  "ignition": true,
  "attributes": {
    "digital_inputs": {
      "input_1": true,
      "input_2": false
    }
  }
}
```

وجود `input_1` در attributes به معنی این نیست که باید آن را دوباره به‌عنوان یک فیلد استاندارد استفاده کنیم.

---

## 8. Unknown / Unmapped Inputs

اگر Digital Input وجود داشته باشد ولی SANA هنوز معنی آن را نشناسد:

```text
Input 3 = ON
```

می‌تواند در:

```text
attributes.digital_inputs.input_3
```

نگهداری شود.

نباید برای آن یک مفهوم ساختگی ایجاد کنیم.

---

## 9. Device Model Configuration

در آینده می‌توان برای هر Device Model مشخص کرد که Inputهای مختلف چه معنایی دارند.

مثلاً:

```text
Device Model X

Input 1 → Door
Input 2 → Panic
Input 3 → External Sensor
```

اما این موضوع مربوط به:

```text
Device / Sensor Configuration
```

است و بخشی از قرارداد فعلی `NormalizedTelemetry.digital_inputs` نیست.

---

## 10. تبدیل Digital Input به Event

Digital Input خودش فقط وضعیت Telemetry است.

مثلاً:

```text
input_1 = false
```

بعد:

```text
input_1 = true
```

در صورت داشتن Configuration مناسب می‌تواند در آینده باعث ایجاد Event شود.

مثلاً:

```text
Door Open
```

اما:

```text
Digital Input
```

و:

```text
Event
```

دو مفهوم متفاوت هستند.

Event Detection در لایه بعدی انجام می‌شود.

---

## 11. Alert

Digital Input خودش Alert نیست.

مثلاً:

```text
input_2 = true
```

صرفاً یک وضعیت است.

در آینده اگر مشخص شود:

```text
input_2 = Panic Button
```

می‌توان Event و سپس Alert مربوط به آن را ایجاد کرد.

این منطق در Alert/Event Engine قرار می‌گیرد.

---

## 12. Storage

Digital Inputهای عمومی به‌عنوان یک Standard Column مستقل در Telemetry Storage تعریف نمی‌شوند.

ساختار پیشنهادی:

```text
attributes
    └── digital_inputs
```

مثلاً:

```json
{
  "digital_inputs": {
    "input_1": true,
    "input_2": false
  }
}
```

---

## 13. API

API در صورت نیاز می‌تواند `attributes` را ارائه کند:

```json
{
  "ignition": true,
  "attributes": {
    "digital_inputs": {
      "input_1": true,
      "input_2": false
    }
  }
}
```

Frontend نباید معنی Input را بدون Configuration فرض کند.

---

## 14. Presentation

Frontend فقط زمانی می‌تواند عنوان قابل فهمی نمایش دهد که Mapping مربوط به Device/Sensor Configuration مشخص باشد.

مثلاً اگر Configuration بگوید:

```text
input_1 → Door
```

Frontend می‌تواند نمایش دهد:

```text
Door: ON
```

ولی اگر Mapping وجود نداشته باشد:

```text
Input 1: ON
```

نمایش داده می‌شود.

---

## 15. ارتباط با Device Replacement

Digital Inputها متعلق به Device و Configuration آن هستند.

بنابراین با تعویض Device:

```text
Device 1001
```

به:

```text
Device 2002
```

ممکن است معنی Inputها تغییر کند.

مثلاً:

```text
Device 1001
Input 1 → Door
```

و:

```text
Device 2002
Input 1 → Panic
```

بنابراین SANA نباید معنی Digital Input را به‌صورت دائمی به Vehicle نسبت دهد.

---

## 16. ارتباط با Vehicle

خود Vehicle مالک مفهوم:

```text
Input 1
```

نیست.

Vehicle فقط ممکن است از طریق Device و Sensor Configuration داده دریافت کند.

پس:

```text
Vehicle
    ↓
Device
    ↓
Digital Inputs
```

و نه:

```text
Vehicle
    ↓
Input 1
```

به‌صورت مستقیم.

---

## 17. مرز Standard Field و Attributes

اصل قطعی این بخش:

```text
Standard Meaning
        ↓
Normalized Telemetry Field
```

اما:

```text
Device-specific Meaning
        ↓
attributes
```

مثال:

```text
Ignition
    ↓
ignition
```

ولی:

```text
Input 1
Input 2
Input 3
    ↓
attributes.digital_inputs
```

---

## 18. مرز Raw Packet، Normalized Telemetry و Presentation

جریان کلی:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Digital Input Extraction
    ↓
attributes.digital_inputs
    ↓
Storage / Processing
    ↓
API
    ↓
Frontend
```

اگر یک Input معنی استانداردی مانند Ignition داشته باشد:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Semantic Mapping
    ↓
ignition
```

---

# 19. قرارداد نهایی

Digital Inputs:

```text
digital_inputs
Type: Object
Location: attributes
Standard Field: No
Source: Device / Sensor
Meaning: Device-specific digital input states
```

و:

```text
ignition
Type: Boolean
Standard Field: Yes
Source: Device / Sensor
Meaning: Normalized ignition state
```

---

# 20. قواعد نهایی

1. `digital_inputs` فعلاً Standard Field نیست.
2. Digital Inputهای عمومی در `attributes` نگهداری می‌شوند.
3. شماره Input به‌تنهایی معنی استاندارد ندارد.
4. `Input 1` در Deviceهای مختلف می‌تواند معنی متفاوت داشته باشد.
5. `ignition` یک Standard Field مستقل است.
6. اگر یک Digital Input همان Ignition/ACC باشد، به `ignition` Normalize می‌شود.
7. Digital Input خام و `ignition` یک مفهوم نیستند.
8. Inputهایی که معنی‌شان مشخص نیست، در `attributes` باقی می‌مانند.
9. SANA نباید برای Input ناشناخته معنی ساختگی ایجاد کند.
10. Mapping معنی Inputها در آینده می‌تواند در Device/Sensor Configuration تعریف شود.
11. Digital Input خودش Event نیست.
12. Digital Input خودش Alert نیست.
13. تغییر وضعیت Input می‌تواند در آینده توسط Event Engine به Event تبدیل شود.
14. Mapping Input به Event در لایه Event Engine انجام می‌شود.
15. Digital Inputها به‌صورت Column استاندارد مستقل در Storage ذخیره نمی‌شوند.
16. `attributes.digital_inputs` محل نگهداری وضعیت‌های عمومی Device-specific است.
17. Frontend نباید بدون Configuration معنی Input را حدس بزند.
18. با تعویض Device ممکن است Mapping Inputها تغییر کند.
19. معنی Digital Input به Vehicle وابسته نیست؛ به Device/Sensor Configuration وابسته است.
20. Standard Meaning باید Standard Field شود؛ Device-specific Meaning باید در `attributes` باقی بماند.
21. Raw Packet، Normalized Telemetry و Presentation همچنان سه لایه مستقل هستند.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry — Analog Inputs

## 1. تعریف Analog Inputs

بعضی GPS Trackerها چند ورودی آنالوگ دارند که می‌توانند یک مقدار عددی را از سخت‌افزار یا سنسور دریافت کنند.

نمونه:

```text
Analog Input 1 = 2.73 V
Analog Input 2 = 1847
```

اما عدد Analog Input به‌تنهایی معنای عمومی و استانداردی ندارد.

مثلاً:

```text
Input 1 = 2.73V
```

در یک دستگاه ممکن است سنسور سوخت باشد و در دستگاه دیگری سنسور دما، فشار یا ورودی دیگری.

بنابراین:

> `analog_inputs` یک مفهوم عمومی و استانداردشده در سطح Telemetry نیست.

---

# 2. تصمیم نهایی درباره Standard Field

فیلد استاندارد زیر ایجاد نمی‌شود:

```text
analog_inputs
```

یعنی در `NormalizedTelemetry` یک فیلد عمومی به نام `analog_inputs` نداریم.

در عوض، مقادیر Analog Inputهای دستگاه در بخش:

```text
attributes
```

نگهداری می‌شوند.

مثلاً:

```json
{
    "analog_inputs": {
        "input_1": 2.73,
        "input_2": 1847
    }
}
```

ساختار دقیق مقدار می‌تواند متناسب با Protocol/Device باشد؛ مثلاً در صورت نیاز می‌توان Unit یا اطلاعات تکمیلی را نیز نگه داشت.

---

# 3. چرا Analog Input استاندارد نیست؟

شماره ورودی به‌تنهایی معنای مشخصی ندارد.

مثلاً:

```text
Input 1
```

نمی‌تواند به‌صورت عمومی به معنی:

```text
Fuel
```

یا:

```text
Temperature
```

فرض شود.

بنابراین SANA نباید چنین فرضی داشته باشد:

```text
Input 1 → Fuel
Input 2 → Temperature
```

مگر اینکه این Mapping برای همان Device/Protocol مشخص شده باشد.

---

# 4. Source

مبدأ Analog Input معمولاً:

```text
Device / Sensor
```

است.

مسیر کلی:

```text
GPS Device
    ↓
Protocol Packet
    ↓
Protocol Decoder
    ↓
Analog Input Extraction
    ↓
attributes.analog_inputs
```

---

# 5. تفاوت مقدار خام و مقدار Normalized

Analog Input ممکن است به شکل‌های مختلف توسط دستگاه گزارش شود.

مثلاً:

```text
2.73
```

یا:

```text
2730
```

یا:

```text
ADC = 1847
```

این اعداد تا زمانی که Unit، Mapping و Conversion مشخص نباشد، معنای عمومی ندارند.

بنابراین Decoder نباید بدون داشتن اطلاعات معتبر، این مقدار را به یک Standard Field تبدیل کند.

---

# 6. مثال تبدیل Analog Input به Fuel Level

فرض کنیم دستگاه گزارش می‌کند:

```text
Analog Input 1 = 2.73 V
```

و Configuration دستگاه مشخص کرده:

```text
Input 1 → Fuel Sensor
```

و Calibration معتبر نیز وجود دارد:

```text
2.73 V → 38.4 L
```

در این حالت Decoder/Processing می‌تواند مقدار استاندارد را تولید کند:

```text
fuel_level = 38.4 L
```

و دیگر لازم نیست مقدار 2.73 به‌عنوان `fuel_level` ذخیره شود.

اما خود مقدار Analog Input می‌تواند برای Traceability/Debug در `attributes` باقی بماند.

---

# 7. اگر Calibration وجود نداشته باشد

اگر دستگاه مقدار زیر را ارسال کند:

```text
Analog Input 1 = 2.73 V
```

ولی SANA نداند این مقدار مربوط به چه چیزی است یا Calibration معتبر نداشته باشد:

```text
fuel_level = NULL
```

و مقدار Analog Input به‌عنوان داده Device-specific نگهداری می‌شود.

نباید SANA حدس بزند:

```text
2.73 V = X liters
```

---

# 8. مثال Temperature

فرض کنیم:

```text
Input 2 = 1.84 V
```

و Configuration مشخص کند:

```text
Input 2 → Temperature Sensor
```

اگر Calibration معتبر وجود داشته باشد:

```text
1.84 V → 27.5 °C
```

آنگاه:

```text
temperature = 27.5
```

به‌عنوان Standard Field تولید می‌شود.

بدون Mapping و Calibration معتبر:

```text
temperature = NULL
```

و مقدار Analog Input در `attributes` باقی می‌ماند.

---

# 9. دستگاهی که مقدار Semantic را مستقیماً ارسال می‌کند

اگر Protocol خودش مقدار معنی‌دار را ارسال کند، مثلاً:

```text
Fuel Level = 38.4 L
```

دیگر لازم نیست آن را به‌عنوان Analog Input ذخیره و دوباره تبدیل کنیم.

Decoder مستقیماً:

```text
fuel_level = 38.4
```

را تولید می‌کند.

بنابراین تفاوت مهم است:

```text
Raw Analog Value
        ↓
Mapping + Calibration
        ↓
Standard Field
```

در مقابل:

```text
Semantic Protocol Value
        ↓
Standard Field
```

---

# 10. Unit

Unit یک Analog Input عمومی و ثابت نیست.

ممکن است Protocol مقدار را به شکل:

```text
V
mV
ADC
raw
```

گزارش کند.

بنابراین SANA نباید برای همه Analog Inputها یک Unit ثابت فرض کند.

Unit و نحوه تبدیل باید از Protocol/Device Configuration مشخص شود.

---

# 11. چند Analog Input

یک Device می‌تواند چند Analog Input داشته باشد:

```text
Input 1
Input 2
Input 3
Input 4
...
```

هرکدام می‌توانند Mapping متفاوتی داشته باشند.

مثلاً:

```text
Input 1 → Fuel Sensor
Input 2 → Temperature Sensor
Input 3 → Pressure Sensor
Input 4 → Unknown
```

فقط مواردی که Mapping و Conversion معتبر دارند، می‌توانند به Standard Field تبدیل شوند.

---

# 12. Mapping متعلق به Device/Configuration است

معنای یک Analog Input به خود شماره Input وابسته نیست.

بنابراین این مفهوم:

```text
Input 1 = Fuel
```

نباید به‌صورت یک قانون عمومی در SANA تعریف شود.

بلکه باید در آینده بتوان آن را در Configuration مربوط به Device/Device Model/Sensor Configuration تعریف کرد.

---

# 13. Device Replacement

Mapping مربوط به Analog Input به Device وابسته است، نه Vehicle.

بنابراین در صورت تعویض GPS:

```text
Old Device
    ↓
Input 1 → Fuel Sensor
```

ممکن است Device جدید داشته باشد:

```text
Input 2 → Fuel Sensor
```

و SANA نباید فرض کند Mapping دستگاه قبلی برای دستگاه جدید نیز معتبر است.

---

# 14. ارتباط با Vehicle

Analog Input مستقیماً متعلق به Device است.

اما اگر Mapping آن به یک مفهوم مربوط به Vehicle انجام شود، نتیجه Normalized آن می‌تواند در سطح Vehicle استفاده شود.

مثلاً:

```text
Device
  Input 1
     ↓
Fuel Sensor
     ↓
Calibration
     ↓
fuel_level
     ↓
Vehicle
```

---

# 15. Analog Input و Event

خود Analog Input یک Event نیست.

مثلاً:

```text
Input 1 = 2.73 V
```

Telemetry است.

اما تغییر یا مقدار آن در آینده می‌تواند توسط Event Engine بررسی شود.

مثلاً:

```text
Analog Input
      ↓
Normalized Value
      ↓
Event Detection
      ↓
Fuel Level Low
      ↓
Alert
```

Event و Alert از خود Analog Input جدا هستند.

---

# 16. Analog Input و Alert

Analog Input مستقیماً Alert نیست.

مثلاً:

```text
Input 1 = 1.2 V
```

صرفاً یک مقدار Telemetry است.

اما اگر Configuration مشخص کند:

```text
Input 1 → Pressure Sensor
```

و Rule تعریف شده باشد:

```text
Pressure < Threshold
```

می‌توان در لایه Event/Alert آن را بررسی کرد.

---

# 17. Raw Packet

اگر مقدار Analog Input برای Debug یا بررسی Protocol مهم باشد، مقدار اصلی Packet همچنان در:

```text
Raw Packet
```

قابل نگهداری است.

بنابراین سه لایه از هم جدا هستند:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Normalized Telemetry
    ↓
Processing / Storage / Event
```

Analog Input در Normalized Telemetry فقط به‌عنوان داده Device-specific داخل:

```text
attributes
```

قرار می‌گیرد.

---

# 18. Storage

برای Analog Inputها فعلاً Column استاندارد جداگانه در جدول Telemetry ایجاد نمی‌شود.

یعنی:

```text
analog_input_1
analog_input_2
analog_input_3
...
```

در Database ساخته نمی‌شود.

مقادیر Device-specific در ساختار:

```text
attributes
```

قرار می‌گیرند.

---

# 19. API

API نیز Analog Input را به‌عنوان مجموعه‌ای از فیلدهای استاندارد ثابت تعریف نمی‌کند.

در صورت وجود:

```json
{
    "attributes": {
        "analog_inputs": {
            "input_1": 2.73,
            "input_2": 1847
        }
    }
}
```

Frontend می‌تواند آن را به‌عنوان داده Device-specific دریافت کند.

---

# 20. Frontend

Frontend نباید صرفاً بر اساس شماره Input برای آن معنی تعیین کند.

یعنی نباید به‌صورت ثابت نمایش دهد:

```text
Input 1 = Fuel
```

مگر اینکه Mapping معتبر از Backend/Configuration دریافت شده باشد.

در صورت وجود Mapping:

```text
Input 1 → Fuel Sensor
```

Frontend می‌تواند آن را با عنوان مناسب نمایش دهد.

---

# 21. تفکیک سه لایه

برای Analog Input نیز همان اصل کلی SANA حفظ می‌شود:

### Raw

داده واقعی Packet:

```text
2.73V
```

یا:

```text
ADC = 1847
```

### Normalized

اگر Mapping و Conversion معتبر وجود داشته باشد:

```text
fuel_level = 38.4 L
```

یا:

```text
temperature = 27.5 °C
```

### Presentation

Frontend مقدار Normalized را نمایش می‌دهد:

```text
۳۸٫۴ لیتر
```

یا:

```text
۲۷٫۵ درجه سانتی‌گراد
```

---

# 22. قانون مهم

SANA نباید از یک Analog Input ناشناخته، یک مفهوم استاندارد را حدس بزند.

یعنی:

```text
Analog Input
    ≠
Standard Field
```

مگر اینکه:

```text
Mapping معتبر
+
Conversion/Calibration معتبر
```

وجود داشته باشد.

---

# 23. نام‌گذاری قطعی

نام عمومی برای داده‌های Analog Input:

```text
attributes.analog_inputs
```

است.

اما:

```text
analog_inputs
```

Standard Field نیست.

---

# 24. ساختار مفهومی نهایی

```text
GPS Device
    │
    ▼
Raw Packet
    │
    ▼
Protocol Decoder
    │
    ├── Semantic Value
    │       ↓
    │   Standard Field
    │
    └── Raw Analog Input
            ↓
       attributes.analog_inputs
            │
            ▼
      Device Configuration
            │
            ▼
      Mapping / Calibration
            │
            ▼
       Standard Field
```

---

# 25. قواعد نهایی Analog Inputs

1. `analog_inputs` یک Standard Field نیست.
2. Analog Inputها در `attributes` قرار می‌گیرند.
3. شماره Input به‌تنهایی معنای عمومی ندارد.
4. Input 1 نباید به‌صورت پیش‌فرض Fuel، Temperature یا مفهوم دیگری فرض شود.
5. Unit مربوط به Analog Input عمومی و ثابت نیست.
6. مقدار Analog بدون Mapping معتبر نباید به Standard Field تبدیل شود.
7. Calibration برای تبدیل مقادیر خام به مقادیر فیزیکی لازم است.
8. در صورت نبود Calibration معتبر، مقدار Standard Field مربوطه باید `NULL` باشد.
9. مقدار خام Analog می‌تواند در `attributes` باقی بماند.
10. Raw Packet همچنان منبع اصلی برای Debug و Traceability است.
11. اگر Protocol مستقیماً مقدار Semantic بدهد، Decoder می‌تواند آن را مستقیماً به Standard Field تبدیل کند.
12. Mapping مربوط به Analog Input به Device/Device Configuration وابسته است.
13. Mapping یک Device نباید به Device دیگر تعمیم داده شود.
14. تعویض Device می‌تواند Mapping ورودی‌های Analog را تغییر دهد.
15. Analog Input خودش Event نیست.
16. Analog Input خودش Alert نیست.
17. Event Engine می‌تواند از مقدار Normalized آن برای تشخیص Event استفاده کند.
18. برای Analog Inputها فعلاً Column جداگانه در Database ایجاد نمی‌شود.
19. Frontend نباید برای Inputها معنی ثابت فرض کند.
20. Standard Field فقط زمانی تولید می‌شود که معنی، Unit و Conversion معتبر مشخص باشد.
21. تفکیک Raw / Normalized / Storage / API / Presentation باید حفظ شود.
22. `attributes.analog_inputs` محل نگهداری داده‌های Analog اختصاصی Device است.
23. در آینده Device/Sensor Configuration می‌تواند Mapping و Calibration را مدیریت کند.
24. `fuel_level`، `temperature` و سایر Standard Fieldها همچنان مستقل از `analog_inputs` هستند.
25. Analog Input یک مکانیزم ورودی داده است، نه یک مفهوم تجاری یا معنایی مستقل.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry — Digital Outputs

## 1. تعریف Digital Outputs

بعضی GPS Trackerها دارای خروجی دیجیتال هستند که معمولاً برای کنترل تجهیزات خارجی استفاده می‌شوند.

نمونه:

```text id="6c1r4s"
Output 1 = ON
Output 2 = OFF
```

کاربرد خروجی می‌تواند شامل مواردی مانند Relay، آژیر، قطع‌کننده یا تجهیزات دیگر باشد.

اما شماره خروجی به‌تنهایی معنای عمومی ندارد.

مثلاً:

```text id="m0xq9n"
Output 1
```

نمی‌تواند به‌صورت عمومی به معنی Relay یا Immobilizer فرض شود.

---

# 2. تصمیم نهایی درباره Standard Field

فیلد استاندارد زیر ایجاد نمی‌شود:

```text id="v5z3j1"
digital_outputs
```

و وضعیت خروجی‌های دیجیتال، در صورت گزارش شدن توسط Device، در:

```text id="g8m2wp"
attributes
```

قرار می‌گیرد.

مثلاً:

```json id="j4v7sk"
{
    "digital_outputs": {
        "output_1": true,
        "output_2": false
    }
}
```

---

# 3. تفاوت Output State و Output Command

دو مفهوم کاملاً متفاوت داریم.

### وضعیت خروجی

دستگاه گزارش می‌کند:

```text id="x0q8mz"
Output 1 = ON
```

این یک داده Telemetry است.

### فرمان خروجی

SANA به دستگاه می‌گوید:

```text id="c5n1fa"
Turn Output 1 ON
```

این Telemetry نیست.

این یک **Device Command** است.

---

# 4. معماری Command

فرمان خروجی باید از مسیر جداگانه‌ای عبور کند:

```text id="v1y7ds"
SANA Panel
    ↓
Command API
    ↓
Permission Check
    ↓
Command Validation
    ↓
Command Queue / Session
    ↓
sana-gps
    ↓
GPS Device
    ↓
ACK / Result
```

بنابراین Command نباید وارد `NormalizedTelemetry` شود.

---

# 5. وضعیت واقعی Output

اگر Device وضعیت Output را گزارش کند:

```text id="z3d4kr"
Output 1 = true
Output 2 = false
```

Decoder می‌تواند آن را به شکل:

```json id="f0u2xp"
{
    "attributes": {
        "digital_outputs": {
            "output_1": true,
            "output_2": false
        }
    }
}
```

تبدیل کند.

---

# 6. معنای Output

معنای Output وابسته به Device و Configuration است.

مثلاً در یک Device:

```text id="3v9qfw"
Output 1 → Relay
```

و در Device دیگر:

```text id="m2r5az"
Output 1 → Immobilizer
```

بنابراین SANA نباید بر اساس شماره خروجی، معنی ثابتی تعیین کند.

---

# 7. Device Configuration

در آینده می‌توان Mapping خروجی‌ها را در Device/Sensor Configuration تعریف کرد.

مثلاً:

```text id="2w7mke"
Output 1
    ↓
Relay
```

یا:

```text id="f5k8qp"
Output 1
    ↓
Immobilizer
```

Frontend نیز باید معنی خروجی را از Configuration دریافت کند، نه اینکه خودش حدس بزند.

---

# 8. Device Replacement

Mapping خروجی متعلق به Device است.

بنابراین:

```text id="c8q3rx"
Vehicle
   │
   ├── Old Device
   │      └── Output 1 → Relay
   │
   └── New Device
          └── Output 1 → Immobilizer
```

کاملاً ممکن است.

پس Mapping نباید صرفاً به Vehicle وابسته باشد.

---

# 9. Output و Event

وضعیت Output خودش Event نیست.

مثلاً:

```text id="p7x1vz"
Output 1 = ON
```

یک Telemetry/Device State است.

اما تغییر وضعیت می‌تواند بعداً Event تولید کند:

```text id="q6n4bt"
Output 1
   ↓
State Change
   ↓
Event Detection
   ↓
OUTPUT_CHANGED
```

---

# 10. Output و Alert

Output State خودش Alert نیست.

اما می‌توان در آینده Rule تعریف کرد:

```text id="u9k3se"
اگر Output 1 برخلاف وضعیت مورد انتظار باشد
        ↓
Event
        ↓
Alert
```

بنابراین:

```text id="g5r2md"
Telemetry
    ≠
Event
    ≠
Alert
```

---

# 11. ارتباط با Command Result

ممکن است بعد از ارسال Command، دستگاه نتیجه را گزارش کند.

مثلاً:

```text id="z6q8yc"
Command:
Output 1 → ON
```

سپس Device گزارش دهد:

```text id="a2m5nf"
Output 1 = ON
```

این گزارش دوم Telemetry/Device State است.

ACK مربوط به Command نیز نتیجه فنی Command است و نباید با Telemetry یکی شود.

---

# 12. Raw Packet

اگر وضعیت Output از Packet دریافت شود، مقدار اصلی Packet همچنان در Raw Packet قابل نگهداری است.

مسیر:

```text id="b7r4hx"
Raw Packet
    ↓
Protocol Decoder
    ↓
digital_outputs
    ↓
attributes
```

---

# 13. Storage

برای Outputهای دیجیتال فعلاً Column استاندارد جداگانه ایجاد نمی‌شود.

یعنی چنین ستون‌هایی ایجاد نمی‌کنیم:

```text id="q2m8sj"
output_1
output_2
output_3
...
```

داده در:

```text id="d4v6ky"
attributes.digital_outputs
```

قرار می‌گیرد.

---

# 14. API

API نیز Outputها را به‌عنوان مجموعه‌ای از Standard Fieldهای ثابت تعریف نمی‌کند.

مثلاً:

```json id="e1n7cs"
{
    "attributes": {
        "digital_outputs": {
            "output_1": true,
            "output_2": false
        }
    }
}
```

---

# 15. Frontend

Frontend نباید فرض کند:

```text id="h7k2qp"
Output 1 = Relay
```

مگر اینکه Backend/Device Configuration چنین Mappingی را ارائه کرده باشد.

در صورت وجود Mapping:

```text id="n3f8wx"
Output 1 → Immobilizer
```

Frontend می‌تواند به‌جای:

```text
Output 1
```

نمایش دهد:

```text
Immobilizer
```

---

# 16. Permission

ارسال Command به Digital Output از نظر امنیتی حساس است.

بنابراین در آینده Command API باید Permission مربوط به Device و Command را بررسی کند.

مثلاً:

```text id="k5z9mr"
User
  ↓
Can access Device?
  ↓
Can send command?
  ↓
Is this command allowed?
  ↓
Send
```

این Permission در `sana-backend` مدیریت می‌شود و نباید در `sana-gps` تصمیم‌گیری تجاری شود.

---

# 17. نقش sana-gps

`sana-gps` وظیفه دارد:

* Command را به Protocol مناسب تبدیل کند.
* آن را به Device ارسال کند.
* ACK/Response را دریافت کند.
* نتیجه فنی را گزارش کند.

اما نباید تصمیم بگیرد:

```text
آیا این User اجازه دارد؟
آیا این Customer اجازه دارد؟
آیا این Device متعلق به این Organization است؟
```

این‌ها مسئولیت `sana-backend` هستند.

---

# 18. Digital Outputs و Device State

وضعیت Output می‌تواند در آینده بخشی از Current State دستگاه باشد، اگر برای Live UI لازم باشد.

مثلاً:

```text id="w3p8kc"
Current State
├── last_seen
├── latitude
├── longitude
├── speed
├── ignition
├── battery
└── digital_outputs
```

اما این موضوع به نیاز Live Map و Device Detail بستگی دارد.

منبع اصلی همچنان Telemetry دریافتی از Device است.

---

# 19. Digital Outputs و Vehicle

Output مستقیماً متعلق به Device است.

بنابراین با تعویض Device، وضعیت و Mapping Output دستگاه جدید مستقل از Device قبلی است.

تاریخچه Vehicle می‌تواند از طریق تاریخچه Deviceهای نصب‌شده روی آن Vehicle ساخته شود.

---

# 20. نام‌گذاری قطعی

نام داده Device-specific:

```text id="s4c7qn"
attributes.digital_outputs
```

است.

اما:

```text id="f1y6pd"
digital_outputs
```

Standard Field نیست.

---

# 21. تفکیک Telemetry و Command

اصل مهم این بخش:

```text id="r8w2mv"
Device → SANA
Output State
        ↓
Telemetry
```

در مقابل:

```text id="b6k9tx"
SANA → Device
Output Command
        ↓
Command
```

این دو نباید در یک مدل یا جریان ادغام شوند.

---

# 22. قواعد نهایی Digital Outputs

1. `digital_outputs` یک Standard Field نیست.
2. وضعیت Digital Output در `attributes.digital_outputs` قرار می‌گیرد.
3. شماره Output به‌تنهایی معنای عمومی ندارد.
4. Output 1 نباید به‌صورت پیش‌فرض Relay، Immobilizer یا مفهوم دیگری فرض شود.
5. Mapping خروجی به Device/Device Configuration وابسته است.
6. Mapping یک Device نباید به Device دیگر تعمیم داده شود.
7. وضعیت Output گزارش‌شده توسط Device، Telemetry/Device State است.
8. Command برای تغییر Output، Telemetry نیست.
9. Command باید مسیر مستقل داشته باشد.
10. Permission مربوط به ارسال Command در `sana-backend` بررسی می‌شود.
11. `sana-gps` فقط مسئول اجرای فنی Command و ارتباط با Device است.
12. ACK مربوط به Command با Telemetry یکسان نیست.
13. تغییر وضعیت Output می‌تواند در آینده Event ایجاد کند.
14. Event می‌تواند در آینده مبنای Alert قرار گیرد.
15. برای Outputها فعلاً Column استاندارد جداگانه در Database ایجاد نمی‌شود.
16. Raw Packet همچنان منبع اصلی داده خام است.
17. Frontend نباید برای شماره Output معنی ثابت فرض کند.
18. Device Replacement می‌تواند Mapping Output را تغییر دهد.
19. وضعیت Output در صورت نیاز می‌تواند در Current State نیز قرار گیرد.
20. Digital Output مستقیماً متعلق به Device است.
21. `attributes.digital_outputs` برای داده‌های Device-specific استفاده می‌شود.
22. Output State و Output Command دو مفهوم مستقل هستند.
23. Telemetry مسیر Device → SANA دارد.
24. Command مسیر SANA → Device دارد.
25. تفکیک Raw / Normalized / Command / Event / Alert باید حفظ شود.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Alarm

## 1. تعریف Alarm

در SANA، Alarm یک رخداد یا وضعیت هشداردهنده است که:

* توسط GPS Device گزارش شده باشد؛ یا
* توسط SANA از روی Telemetry و شرایط مشخص تشخیص داده شود.

Alarm یک مفهوم مستقل است و با Telemetry، Event، Alert، Notification و Command یکسان نیست.

اصل معماری:

```text
Device
   ↓
Raw Packet
   ↓
Protocol Decoder
   ↓
Telemetry / Device State / Device Alarm
   ↓
Event Engine
   ↓
Event
   ↓
Alert Rule
   ↓
Alert
   ↓
Notification
```

---

# 2. تفاوت Alarm و Telemetry

Telemetry مقدار یا وضعیت اندازه‌گیری‌شده توسط Device است.

مثلاً:

```text
speed = 125
battery_voltage = 3.21
ignition = true
temperature = 27.5
```

Alarm رخداد یا وضعیت هشداردهنده است:

```text
OVERSPEED
LOW_BATTERY
POWER_CUT
SOS
```

بنابراین:

```text
Telemetry ≠ Alarm
```

---

# 3. تفاوت Alarm و Event

Alarm ممکن است توسط Device گزارش شود:

```text
Device
   ↓
SOS Alarm
```

یا SANA از Telemetry آن را تشخیص دهد.

Event مدل عمومی رخداد در SANA است.

مثلاً:

```text
Device Alarm
      ↓
Normalized Alarm
      ↓
Event
```

اما Event الزاماً از Alarm ایجاد نمی‌شود.

مثلاً:

```text
speed > configured_limit
      ↓
SANA
      ↓
OVERSPEED Event
```

پس:

```text
Alarm ≠ Event
```

---

# 4. تفاوت Alarm و Alert

Alarm یک رخداد فنی/سیستمی است.

Alert یک هشدار کاربردی است که بر اساس Rule برای User ایجاد می‌شود.

مثلاً:

```text
GPS Device
    ↓
POWER_CUT Alarm
    ↓
Event
    ↓
Alert Rule:
Power Cut > 2 minutes
    ↓
Alert
    ↓
SMS / Push / Panel
```

پس:

```text
Alarm ≠ Alert
```

---

# 5. تفاوت Alarm و Notification

Notification روش اطلاع‌رسانی Alert به User است.

مثلاً:

```text
Alarm
  ↓
Event
  ↓
Alert
  ↓
SMS
```

SMS خود Alarm نیست.

---

# 6. تفاوت Alarm و Command

Command مسیر SANA → Device دارد.

مثلاً:

```text
SANA
   ↓
Output 1 ON
   ↓
Device
```

Alarm مسیر Device → SANA یا تشخیص داخلی SANA دارد.

پس:

```text
Alarm ≠ Command
```

---

# 7. انواع منبع Alarm

Alarm دارای Source است.

مقادیر پایه:

```text
DEVICE
SANA
```

### DEVICE

خود GPS Alarm را گزارش کرده است.

مثلاً:

```text
Device → SOS
```

### SANA

SANA از Telemetry آن را تشخیص داده است.

مثلاً:

```text
speed = 130
limit = 80
        ↓
SANA → OVERSPEED
```

در آینده Sourceهای جدید در صورت نیاز قابل اضافه شدن هستند.

---

# 8. Alarm Type

Alarm دارای Type استاندارد است.

نمونه Typeهای پایه:

```text
SOS
TAMPER
VIBRATION
POWER_CUT
LOW_BATTERY
OVERSPEED
TOWING
JAMMING
CRASH
```

این مجموعه قابل توسعه است.

نباید با اضافه شدن یک Protocol جدید، Typeهای استاندارد SANA به Protocol خاص وابسته شوند.

---

# 9. Point Alarm و State Alarm

هر Alarm دارای Mode است:

```text
POINT
STATE
```

## POINT

رخداد در یک لحظه مشخص:

```text
SOS
CRASH
VIBRATION
```

## STATE

وضعیتی که شروع و پایان دارد:

```text
POWER_CUT
LOW_BATTERY
JAMMING
TOWING
OVERSPEED
```

این تفکیک برای Processing، Storage و Query اهمیت دارد.

---

# 10. Severity

Alarm دارای Severity است.

مقادیر پایه:

```text
INFO
WARNING
CRITICAL
```

Severity بیانگر شدت فنی/ذاتی Alarm است.

Severity مشخص نمی‌کند که حتماً چه Notificationای باید برای User ارسال شود.

Notification و سیاست اطلاع‌رسانی در لایه Alert/Notification تعیین می‌شوند.

---

# 11. Alarm Time

برای هر Alarm زمان Device باید حفظ شود.

فیلد:

```text
device_time
```

زمان گزارش‌شده توسط Device یا زمان رخداد از دید Device است.

همچنین:

```text
server_received_at
```

زمان دریافت Packet توسط SANA GPS است.

این دو زمان نباید با یکدیگر جایگزین شوند.

---

# 12. Occurred At

Alarm دارای:

```text
occurred_at
```

است.

برای Point Alarm:

```text
occurred_at = زمان رخداد
```

برای State Alarm:

```text
occurred_at = زمان شروع وضعیت
```

`device_time` همچنان زمان فنی گزارش‌شده توسط Device است و در Processing مرجع اصلی زمان رخداد محسوب می‌شود.

اگر Device Time نامعتبر باشد، نباید بدون قاعده آن را با Server Time جایگزین کرد.

---

# 13. Start و End

برای State Alarm:

```text
started_at
ended_at
```

وجود دارد.

مثلاً:

```text
POWER_CUT

started_at = 10:00
ended_at   = 10:17
```

برای Point Alarm:

```text
ended_at = NULL
```

و زمان `occurred_at` کافی است.

---

# 14. Location

Alarm در صورت وجود Location معتبر می‌تواند شامل:

```text
latitude
longitude
```

باشد.

مثلاً:

```text
SOS
latitude = ...
longitude = ...
```

اما اگر Alarm بدون Fix معتبر دریافت شود:

```text
gps_valid = false
latitude = NULL
longitude = NULL
```

نباید آخرین مختصات قبلی Device به‌عنوان محل Alarm ثبت شود.

---

# 15. GPS Valid

برای Location Alarm:

```text
gps_valid
```

نگهداری می‌شود.

نمونه:

```text
gps_valid = true
latitude = 35.xxxx
longitude = 51.xxxx
```

یا:

```text
gps_valid = false
latitude = NULL
longitude = NULL
```

---

# 16. Raw Code

Alarmهای Protocol-specific ممکن است دارای Code باشند.

مثلاً:

```text
raw_code = "0x07"
```

Decoder آن را به:

```text
type = SOS
```

تبدیل می‌کند.

Raw Code برای Debug، Traceability و توسعه Protocol Decoder حفظ می‌شود.

---

# 17. Raw Value

بعضی Alarmها علاوه بر Code دارای مقدار هستند.

مثلاً:

```text
OVERSPEED
raw_value = 128
```

یا:

```text
LOW_BATTERY
raw_value = 3.21
```

بنابراین Alarm می‌تواند:

```text
raw_value
```

داشته باشد.

نوع این مقدار باید انعطاف‌پذیر باشد، زیرا Protocolهای مختلف داده‌های متفاوتی دارند.

---

# 18. Attributes

اطلاعات اضافی و Protocol/Device-specific در:

```text
attributes
```

قرار می‌گیرند.

مثلاً:

```json
{
    "protocol_flag": "0x81",
    "sensor_id": 2,
    "raw_message_type": "ALARM"
}
```

اما فیلدهای اصلی مانند:

```text
type
source
severity
device_time
```

نباید صرفاً داخل Attributes مخفی شوند.

---

# 19. Telemetry Reference

Alarm ممکن است بر اساس یک Telemetry خاص ایجاد شده باشد.

بنابراین امکان Reference به Telemetry وجود دارد:

```text
telemetry_reference
```

مثلاً:

```text
Telemetry #829341
       ↓
OVERSPEED Alarm
```

این Reference برای Debug و Traceability مفید است.

---

# 20. Raw Packet Reference

در صورت نگهداری Raw Packet، Alarm می‌تواند به Packet اصلی نیز Reference داشته باشد:

```text
raw_packet_reference
```

در نتیجه زنجیره کامل قابل ردیابی است:

```text
Raw Packet
    ↓
Telemetry
    ↓
Alarm
```

---

# 21. Duplicate Handling

Alarmهای State نباید برای هر Packet تکراری به رکورد جدید تبدیل شوند.

مثلاً:

```text
POWER_CUT
10:00
10:00:05
10:00:10
10:00:15
```

باید به یک State Alarm تبدیل شود:

```text
POWER_CUT
started_at = 10:00
ended_at = ...
```

Processing باید بتواند Alarm فعال موجود را پیدا و Update کند.

---

# 22. پایان State Alarm

وقتی وضعیت پایان یافت:

```text
POWER_CUT
```

به‌صورت:

```text
ended_at = ...
```

بسته می‌شود.

بعداً Event Engine می‌تواند Event مربوط به پایان وضعیت را تولید کند:

```text
POWER_RESTORED
```

لازم نیست `POWER_RESTORED` یک Alarm مستقل باشد.

---

# 23. Point Alarm

Point Alarm فقط یک رخداد لحظه‌ای است.

مثلاً:

```text
SOS
CRASH
```

ساختار زمانی آن:

```text
occurred_at = ...
ended_at = NULL
```

است.

---

# 24. Device Ownership

Alarm مستقیماً متعلق به Device است:

```text
Alarm
  ↓
Device
```

نه مستقیماً Vehicle.

این تصمیم برای Device Replacement مهم است.

---

# 25. Vehicle Reference

در مدل پایه Alarm، `vehicle_id` به‌عنوان مالک مستقل Alarm ذخیره نمی‌شود.

Vehicle در زمان Query/Reporting از تاریخچه ارتباط Device و Vehicle قابل Resolve است.

دلیل این تصمیم جلوگیری از ناسازگاری تاریخی هنگام تعویض Device است.

---

# 26. Driver Reference

`driver_id` نیز در Alarm پایه ذخیره نمی‌شود.

Driver مربوط به زمان رخداد می‌تواند از:

```text
Device
+
Vehicle History
+
Driver Assignment History
```

Resolve شود.

---

# 27. Customer Reference

`customer_id` نیز در Alarm پایه لازم نیست.

Customer از زنجیره مالکیت SANA قابل Resolve است.

---

# 28. Device Replacement

Alarm به Device وابسته است.

مثلاً:

```text
Vehicle A
   │
   ├── Device 1
   │      └── Alarm #100
   │
   └── Device 2
          └── Alarm #500
```

هر Alarm متعلق به Device زمان خودش باقی می‌ماند.

---

# 29. Alarm Typeهای پایه

مجموعه اولیه:

```text
SOS
TAMPER
VIBRATION
POWER_CUT
LOW_BATTERY
OVERSPEED
TOWING
JAMMING
CRASH
```

این فهرست قابل توسعه است.

---

# 30. مواردی که Alarm نیستند

موارد زیر فعلاً Alarm مستقل محسوب نمی‌شوند:

```text
IGNITION
DOOR
GEOFENCE
DIGITAL_INPUT
DIGITAL_OUTPUT
IMMOBILIZER
HARSH_ACCELERATION
HARSH_BRAKING
POWER_RESTORED
```

این موارد در لایه‌های مناسب خودشان مانند Telemetry، Device State، Event یا Command مدیریت می‌شوند.

---

# 31. Ignition

`ignition` یک Standard Telemetry Field است.

مثلاً:

```text
ignition = ON
```

Alarm نیست.

تغییر:

```text
OFF → ON
```

می‌تواند در Event Model به:

```text
IGNITION_ON
```

تبدیل شود.

---

# 32. Geofence

Geofence Alarm استاندارد نیست.

در بخش Geofence و Event Model، رخدادهایی مانند:

```text
GEOFENCE_ENTER
GEOFENCE_EXIT
```

طراحی خواهند شد.

---

# 33. Digital Inputs / Outputs

Digital Input و Digital Output داده‌های Device-specific هستند.

محل آن‌ها:

```text
attributes.digital_inputs
attributes.digital_outputs
```

است.

تغییر وضعیت آن‌ها می‌تواند در Event Engine بررسی شود.

---

# 34. Towing

Towing می‌تواند:

```text
DEVICE
```

یا:

```text
SANA
```

تشخیص داده شود.

مثلاً SANA می‌تواند از ترکیب:

```text
ignition = OFF
speed > 0
motion = true
```

به Towing برسد.

تشخیص نهایی باید با Rule مناسب و شرایط پایدار انجام شود.

---

# 35. Jamming

`gsm_signal` پایین به‌تنهایی به معنی Jamming نیست.

مثلاً:

```text
gsm_signal = -110 dBm
```

نباید به‌تنهایی:

```text
JAMMING
```

تولید کند.

Jamming باید بر اساس Device Alarm یا Detection Rule معتبر تشخیص داده شود.

---

# 36. Power Cut

Power Cut یک State Alarm است:

```text
POWER_CUT
started_at
ended_at
```

تکرار Packetهای Power Cut نباید رکوردهای متعدد تولید کند.

---

# 37. Low Battery

Low Battery نیز State Alarm است.

شروع و پایان آن بر اساس Threshold و Recovery Rule تعیین می‌شود.

مثلاً:

```text
battery_voltage < threshold
```

شروع:

```text
LOW_BATTERY
```

و پس از عبور معتبر از Recovery Threshold:

```text
LOW_BATTERY ended
```

Thresholdها در آینده باید در Device Model/Configuration قابل تنظیم باشند.

---

# 38. Overspeed

Overspeed می‌تواند Device-originated یا SANA-derived باشد.

مثلاً:

```text
speed > configured_limit
```

باعث ایجاد:

```text
OVERSPEED
```

می‌شود.

Overspeed معمولاً به‌صورت State مدیریت می‌شود تا Packetهای متوالی یک Alarm واحد را تشکیل دهند.

---

# 39. Raw → Normalized

فرآیند کلی:

```text
Protocol Raw Alarm
       ↓
Protocol Decoder
       ↓
Normalized Alarm Type
       ↓
Alarm Processing
       ↓
Alarm Storage
```

مثلاً:

```text
GT06 raw_code = 0x07
       ↓
SOS
```

---

# 40. Alarm Model مفهومی نهایی

ساختار مفهومی Alarm:

```text
Alarm
├── id
├── device
├── type
├── source
├── severity
├── alarm_mode
├── occurred_at
├── device_time
├── server_received_at
├── started_at
├── ended_at
├── latitude
├── longitude
├── gps_valid
├── raw_code
├── raw_value
├── attributes
├── telemetry_reference
└── raw_packet_reference
```

این ساختار فعلاً Contract مفهومی است و Schema نهایی SQL در مرحله:

```text
Schema نهایی دیتابیس GPS
```

تعیین خواهد شد.

---

# 41. اصول قطعی Alarm

1. Alarm مستقل از Telemetry است.
2. Alarm مستقل از Event است.
3. Alarm مستقل از Alert است.
4. Alarm مستقل از Notification است.
5. Alarm مستقل از Command است.
6. هر Alarm متعلق به یک Device است.
7. Alarm دارای Type استاندارد است.
8. Typeها باید قابل توسعه باشند.
9. Alarm دارای Source است.
10. Source اولیه `DEVICE` یا `SANA` است.
11. Alarm دارای Severity است.
12. Alarm دارای Mode یعنی `POINT` یا `STATE` است.
13. Point Alarm زمان وقوع دارد.
14. State Alarm زمان شروع و پایان دارد.
15. `device_time` باید حفظ شود.
16. `server_received_at` باید حفظ شود.
17. `occurred_at` برای زمان منطقی رخداد استفاده می‌شود.
18. Location در صورت معتبر بودن ذخیره می‌شود.
19. مختصات قبلی Device نباید به‌عنوان Location Alarm بدون Fix استفاده شود.
20. `gps_valid` وضعیت اعتبار مختصات را مشخص می‌کند.
21. Raw Code برای Traceability نگهداری می‌شود.
22. Raw Value در صورت وجود نگهداری می‌شود.
23. داده‌های اضافی در `attributes` قرار می‌گیرند.
24. Alarm می‌تواند به Telemetry مربوط Reference داشته باشد.
25. Alarm می‌تواند به Raw Packet مربوط Reference داشته باشد.
26. State Alarmهای تکراری باید Deduplicate شوند.
27. State Alarm با `ended_at` بسته می‌شود.
28. Power Restored الزاماً Alarm مستقل نیست و می‌تواند پایان Power Cut باشد.
29. Vehicle ID در Alarm پایه لازم نیست.
30. Driver ID در Alarm پایه لازم نیست.
31. Customer ID در Alarm پایه لازم نیست.
32. Device Replacement مالکیت تاریخی Alarmهای قبلی را تغییر نمی‌دهد.
33. `gsm_signal` پایین به‌تنهایی Jamming محسوب نمی‌شود.
34. Ignition Alarm نیست و به‌عنوان Telemetry/بعداً Event مدیریت می‌شود.
35. Geofence Alarm پایه نیست و در Geofence/Event Model طراحی می‌شود.
36. Digital Inputs/Outputs Alarm پایه نیستند.
37. Commandهای مربوط به Output در Alarm ذخیره نمی‌شوند.
38. Alarmهای Device-specific باید توسط Decoder به Typeهای استاندارد تبدیل شوند.
39. Raw و Normalized باید از هم جدا بمانند.
40. Schema SQL نهایی Alarm در مرحله نهایی Database طراحی خواهد شد.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Normalized Telemetry — Attributes

## 1. هدف Attributes

`attributes` برای نگهداری داده‌های ساختاریافته، توسعه‌پذیر و وابسته به Device / Protocol / Sensor است که:

* هنوز Standard Field نشده‌اند.
* برای پردازش، تشخیص، گزارش‌گیری یا Debug ارزش دارند.
* معنای مشخص دارند.
* نباید باعث ایجاد ستون‌های متعدد و غیرضروری در Schema اصلی شوند.

`attributes` نباید به یک محل نامنظم برای ریختن تمام داده‌های دریافتی از GPS تبدیل شود.

---

## 2. قانون اصلی Standard Field در برابر Attribute

اگر یک مفهوم:

* عمومی باشد،
* در بسیاری از Deviceها وجود داشته باشد،
* معنای مشخص و قابل استانداردسازی داشته باشد،
* در Tracking / Report / Event / Alert اهمیت داشته باشد،

ترجیحاً باید **Standard Field** باشد.

اگر یک مفهوم:

* وابسته به Device یا Protocol باشد،
* فقط در برخی دستگاه‌ها وجود داشته باشد،
* یا هنوز نیاز به استانداردسازی نداشته باشد،

می‌تواند **Attribute** باشد.

اگر یک مقدار صرفاً برای Debug یا بازسازی Packet لازم باشد، مرجع اصلی آن **Raw Packet** است، نه Attributes.

---

# 3. ساختار Namespace

ساختار اصلی Attributes به صورت Namespace طراحی می‌شود:

```text
attributes
├── cellular
├── device
├── sensors
└── protocol
```

این Namespaceها برای جلوگیری از تبدیل شدن Attributes به یک JSON نامنظم ایجاد می‌شوند.

---

# 4. Cellular Attributes

اطلاعات مربوط به شبکه موبایل در:

```text
attributes.cellular
```

قرار می‌گیرد.

موارد اصلی:

```text
mcc
mnc
lac
tac
cell_id
network_type
operator_name
serving_network
home_network
roaming
rsrp
rsrq
sinr
```

نمونه:

```json
{
  "attributes": {
    "cellular": {
      "serving_network": {
        "mcc": "432",
        "mnc": "11"
      },
      "home_network": {
        "mcc": "432",
        "mnc": "11"
      },
      "roaming": false,
      "lac": "12345",
      "tac": "54321",
      "cell_id": "67890",
      "network_type": "LTE",
      "operator_name": "Example",
      "rsrp": -87,
      "rsrq": -10,
      "sinr": 18
    }
  }
}
```

---

## 5. MCC و MNC

MCC و MNC شناسه‌های شبکه هستند، نه مقادیر محاسباتی.

بنابراین در Attributes به صورت String نگهداری می‌شوند تا:

* صفرهای ابتدایی حفظ شوند.
* فرمت اصلی شناسه از بین نرود.
* با Identifier مانند عدد رفتار نشود.

مثلاً:

```json
{
  "mcc": "432",
  "mnc": "11"
}
```

---

# 6. LAC و TAC

این دو مفهوم از یکدیگر جدا هستند.

### LAC

`Location Area Code`

برای شبکه‌های نسل قدیمی‌تر مانند GSM/3G.

### TAC

`Tracking Area Code`

برای شبکه‌های جدیدتر مانند LTE.

هر دو در صورت وجود قابل ذخیره‌اند:

```json
{
  "lac": "12345",
  "tac": "54321"
}
```

نباید در صورت نبود مقدار، از روی `network_type` مقدار ساختگی تولید شود.

---

# 7. Cell ID

`cell_id` شناسه سلولی است که Device از آن استفاده می‌کند.

این مقدار Identifier است، نه مقدار محاسباتی؛ بنابراین به صورت String نگهداری می‌شود:

```json
{
  "cell_id": "67890"
}
```

نباید Cell ID را با شناسه داخلی Telemetry یا Device اشتباه گرفت.

---

# 8. Network Type

نوع شبکه در:

```text
attributes.cellular.network_type
```

قرار می‌گیرد.

معماری باید از ابتدا برای شبکه‌های مختلف قابل توسعه باشد، از جمله:

```text
GSM
GPRS
EDGE
UMTS
HSPA
LTE
LTE-M
NB-IoT
NR
```

این فهرست بسته و غیرقابل توسعه نیست.

---

# 9. Serving Network و Home Network

دو مفهوم باید از هم جدا باشند.

### Serving Network

شبکه‌ای که Device در حال حاضر به آن متصل است.

### Home Network

شبکه اصلی SIM.

در شرایط Roaming این دو می‌توانند متفاوت باشند.

ساختار:

```json
{
  "serving_network": {
    "mcc": "432",
    "mnc": "11"
  },
  "home_network": {
    "mcc": "432",
    "mnc": "35"
  }
}
```

اطلاعات Serving Network نباید با اپراتور مالک SIM اشتباه گرفته شود.

---

# 10. Roaming

اگر Device به صورت مستقیم وضعیت Roaming را گزارش کند، مقدار آن قابل استفاده است:

```json
{
  "roaming": true
}
```

اگر Home Network و Serving Network هر دو در دسترس باشند، مقایسه آنها می‌تواند برای تحلیل مفید باشد؛ اما SANA نباید بدون اطمینان از معنای مقادیر، وضعیت Roaming را حدس بزند.

وضعیت مفهومی Roaming سه‌حالته است:

```text
true
false
unknown
```

---

# 11. Operator Name

اگر Device نام اپراتور یا شبکه را گزارش کند:

```json
{
  "operator_name": "Example"
}
```

قابل ذخیره است.

اما `operator_name` منبع اصلی و قطعی تشخیص هویت شبکه نیست و نباید جای MCC/MNC یا اطلاعات رسمی SIM را بگیرد.

---

# 12. RSRP

RSRP یک معیار تخصصی قدرت سیگنال در شبکه‌های جدیدتر است.

مثال:

```json
{
  "rsrp": -87
}
```

واحد:

```text
dBm
```

RSRP نباید از `gsm_signal` محاسبه یا جعل شود.

اگر Device RSRP را گزارش نکند، مقدار باید NULL/غایب باشد.

---

# 13. RSRQ

RSRQ معیار کیفیت سیگنال است.

مثال:

```json
{
  "rsrq": -10
}
```

واحد:

```text
dB
```

RSRQ نیز فقط در صورت وجود مقدار معتبر از Device/Protocol ذخیره می‌شود.

---

# 14. SINR

SINR معیار کیفیت لینک رادیویی است.

مثال:

```json
{
  "sinr": 18
}
```

واحد:

```text
dB
```

SINR نیز نباید از سایر معیارهای سیگنال به صورت مصنوعی محاسبه شود.

---

# 15. تفاوت GSM Signal با RSRP/RSRQ/SINR

`gsm_signal` همچنان یک **Standard Field** است.

در مقابل:

```text
attributes.cellular.rsrp
attributes.cellular.rsrq
attributes.cellular.sinr
```

اطلاعات تخصصی‌تر شبکه هستند.

این مقادیر می‌توانند همزمان وجود داشته باشند و جایگزین یکدیگر نیستند.

نباید:

```text
gsm_signal = RSRP
```

در نظر گرفته شود.

---

# 16. Cell Information

ممکن است برخی Deviceها اطلاعات بیشتری مانند موارد زیر ارسال کنند:

```text
eNodeB ID
gNodeB ID
PCI
ARFCN
EARFCN
NR-ARFCN
```

این اطلاعات فعلاً Standard Field نیستند و در صورت نیاز می‌توانند در:

```text
attributes.cellular
```

قرار بگیرند.

این بخش در آینده قابل توسعه است.

---

# 17. GPS Location و Cell Location

Cellular Information نباید جایگزین GPS Location شود.

وجود:

```text
MCC
MNC
LAC/TAC
Cell ID
```

به معنی وجود مختصات GPS نیست.

اگر:

```text
gps_valid = true
```

باشد، مختصات GPS مرجع Location است.

اگر GPS Fix وجود نداشته باشد، SANA نباید صرفاً با استفاده از Cell ID مختصات ساختگی ایجاد کند.

Cell-based positioning در آینده، در صورت نیاز، باید به عنوان یک سیستم Positioning مستقل طراحی شود.

---

# 18. Device Attributes

اطلاعات تکمیلی خود Device در:

```text
attributes.device
```

قرار می‌گیرد.

موارد اولیه:

```text
serial_number
firmware_version
hardware_version
```

مثال:

```json
{
  "device": {
    "serial_number": "SN123456",
    "firmware_version": "1.2.8",
    "hardware_version": "REV-B"
  }
}
```

---

# 19. IMEI

IMEI از قبل شناسه اصلی Business Device در SANA است.

بنابراین IMEI نباید به صورت تکراری در:

```text
attributes.device.imei
```

ذخیره شود.

مرجع اصلی:

```text
Device.imei
```

است.

---

# 20. SIM Information

ICCID و IMSI ذاتاً به SIM مربوط هستند، نه Device.

از آنجا که SANA دارای Entity مستقل برای SIM است، اطلاعات اصلی SIM باید در مدل SIM نگهداری شوند.

بنابراین نباید این اطلاعات به صورت دائمی و تکراری در هر Telemetry قرار بگیرند.

اگر Packet این اطلاعات را گزارش کند، Decoder می‌تواند آنها را استخراج کند و Processing/Storage در صورت نیاز مدل SIM را به‌روزرسانی کند.

---

# 21. Sensor Attributes

اطلاعات Sensorهایی که هنوز Mapping استاندارد ندارند، می‌توانند در:

```text
attributes.sensors
```

قرار بگیرند.

به‌خصوص برای Sensorهای خارجی و BLE.

مثال:

```json
{
  "sensors": {
    "ble": [
      {
        "id": "AA:BB:CC:DD:EE:FF",
        "type": "temperature",
        "value": 24.5,
        "unit": "C"
      }
    ]
  }
}
```

Array استفاده می‌شود تا یک Device بتواند چند Sensor از یک نوع داشته باشد.

---

# 22. Sensor Data و Standard Fields

اگر یک Sensor مفهومی را گزارش کند که SANA برای آن Standard Field دارد، باید مقدار Normalized به Standard Field برود.

مثلاً اگر BLE Sensor مقدار Temperature معتبر بدهد:

```text
BLE Sensor
    ↓
temperature = 24.5
```

و نباید صرفاً در:

```text
attributes.sensors
```

باقی بماند.

Attributes برای مواردی است که هنوز Standard Mapping ندارند یا اطلاعات تکمیلی هستند.

---

# 23. Protocol Attributes

اطلاعات اضافی Protocol در:

```text
attributes.protocol
```

قرار می‌گیرد.

نمونه موارد قابل استفاده:

```text
message_type
message_id
sequence
protocol_version
vendor_specific
```

مثال:

```json
{
  "protocol": {
    "message_type": "location",
    "message_id": "123456",
    "sequence": 18291
  }
}
```

---

# 24. Protocol Name

نام Protocol مانند:

```text
teltonika
gt06
queclink
...
```

ممکن است برای Decoder و Session مهم باشد، اما لزوماً لازم نیست در هر Telemetry ذخیره شود.

اگر از روی Device/Session/Decoder همیشه قابل تشخیص باشد، می‌توان از تکرار آن در هر رکورد جلوگیری کرد.

---

# 25. Message Type / Message ID / Sequence

این اطلاعات در صورت داشتن کاربرد عملی برای:

* Debug
* Trace
* تشخیص Packet تکراری
* بررسی ترتیب Packetها
* تشخیص Packet گمشده

قابل نگهداری هستند.

اما:

```text
Protocol Message ID
```

با:

```text
Telemetry.id
```

یکی نیست.

---

# 26. Vendor-Specific Data

اگر Vendor مقدار خاصی ارسال کند که هنوز Standard Field نیست، در صورت داشتن Schema مشخص می‌تواند در:

```text
attributes.protocol.vendor
```

قرار گیرد.

مثال:

```json
{
  "protocol": {
    "vendor": {
      "driver_id": "D123",
      "fuel_sensor_raw": 742
    }
  }
}
```

Vendor Attribute باید معنای مشخص، نوع مشخص و در صورت نیاز واحد مشخص داشته باشد.

داده‌های نامفهوم مانند:

```text
x
y
z
```

بدون Schema معتبر نباید وارد Attributes شوند.

---

# 27. Raw Value در برابر Normalized Value

اگر Device مقدار خامی مانند:

```text
742
```

ارسال کند و Decoder آن را به:

```text
fuel_level = 53.7 liter
```

تبدیل کند، مقدار `53.7` باید در Standard Field قرار گیرد.

مقدار خام در صورت نیاز برای Debug باید در:

```text
Raw Packet
```

یا Attribute مشخص و مستند نگهداری شود.

Normalized Data و Raw Data نباید با یکدیگر مخلوط شوند.

---

# 28. Raw Packet جای Attributes نیست

اصل قطعی:

```text
Raw Packet
    ↓
تمام داده خام مورد نیاز برای Debug / Replay
```

در مقابل:

```text
Attributes
    ↓
داده اضافی، ساختاریافته و قابل استفاده
```

Attributes نباید نسخه دوم Raw Packet باشد.

---

# 29. Processing Metadata

اطلاعات داخلی SANA مانند:

```text
decoder_version
parser_version
normalized_by
```

فعلاً جزو Telemetry Attributes نیستند.

اینها در صورت نیاز آینده باید به عنوان Processing/Audit Metadata جداگانه طراحی شوند.

---

# 30. عدم تکرار Standard Fields

این موارد نباید دوباره داخل Attributes ذخیره شوند:

```text
device_time
server_received_at
latitude
longitude
gps_valid
speed
heading
altitude
motion
ignition
battery_voltage
external_voltage
gsm_signal
odometer
engine_hours
fuel_level
temperature
```

مثلاً این ساختار اشتباه است:

```json
{
  "speed": 80,
  "attributes": {
    "speed": 80
  }
}
```

اگر مقدار قابل Normalization است، Standard Field مرجع آن است.

---

# 31. Attributes قابل ارتقا است

قرار گرفتن یک مفهوم در Attributes به معنی دائمی بودن آن نیست.

اگر در آینده مفهومی مانند RSRP یا یک Sensor خاص آن‌قدر در SANA مهم شود که:

* در Dashboard استفاده شود،
* در Reports استفاده شود،
* Alert داشته باشد،
* Query زیادی روی آن انجام شود،
* یا Analytics روی آن انجام شود،

می‌توان آن را از Attribute به Standard Field ارتقا داد.

---

# 32. ساختار نهایی مفهومی

ساختار مورد تأیید Attributes:

```text
Normalized Telemetry
│
├── Standard Fields
│   ├── Location
│   ├── Speed
│   ├── Heading
│   ├── Altitude
│   ├── Motion
│   ├── Ignition
│   ├── Battery Voltage
│   ├── External Voltage
│   ├── GSM Signal
│   ├── Odometer
│   ├── Engine Hours
│   ├── Fuel Level
│   └── Temperature
│
└── attributes
    ├── cellular
    ├── device
    ├── sensors
    └── protocol
```

---

# 33. اصول قطعی Attributes

1. Attributes یک JSON Object ساختاریافته و Namespace-based است.
2. Attributes نباید به Data Dump تبدیل شود.
3. Standard Field نباید بدون دلیل داخل Attributes تکرار شود.
4. Raw Packet مرجع داده خام است.
5. اطلاعات Protocol فقط در صورت داشتن کاربرد مشخص ذخیره می‌شود.
6. اطلاعات Device غیرضروری می‌تواند Attribute باشد.
7. Sensorهای ناشناخته یا هنوز Mapping نشده می‌توانند Attribute باشند.
8. Sensorهایی که به Standard Field قابل تبدیل هستند باید Normalize شوند.
9. اطلاعات Cellular تخصصی در Namespace `cellular` قرار می‌گیرند.
10. MCC/MNC و سایر Identifierها به صورت String نگهداری می‌شوند.
11. LAC و TAC مفاهیم جدا هستند.
12. Cell ID با Location GPS یکی نیست.
13. Serving Network و Home Network باید از یکدیگر تفکیک شوند.
14. Roaming می‌تواند `true`، `false` یا `unknown` باشد.
15. RSRP، RSRQ و SINR نباید از `gsm_signal` جعل یا محاسبه شوند.
16. IMEI در مدل Device مرجع اصلی است و در Attributes تکرار نمی‌شود.
17. ICCID و IMSI متعلق به SIM هستند و باید در مدل SIM مدیریت شوند.
18. Vendor-specific data باید Schema و معنای مشخص داشته باشد.
19. Protocol Message ID با Telemetry ID یکی نیست.
20. Processing Metadata فعلاً جزو Telemetry Attributes نیست.
21. Attributes در آینده قابل ارتقا به Standard Field است.
22. طراحی Attributes باید بدون وابستگی به یک Vendor یا Protocol خاص باقی بماند.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Event و State Event Lifecycle

## 1. تعریف Event

`Event` یک رخداد معنادار است که از تغییر وضعیت، وضعیت، تحلیل Telemetry، وضعیت Device یا شرایط محیطی ایجاد می‌شود و ارزش ذخیره‌سازی تاریخی دارد.

Event با Telemetry، Alarm، Alert، Notification و Command یکسان نیست.

```text
Telemetry
   ↓
Event Engine
   ↓
Event
```

Event متعلق به `Device` است، نه مستقیماً Vehicle، Driver یا Customer.

دلیل: تاریخچه Event باید هویت واقعی Device را حفظ کند و در صورت جایگزینی Device، Eventهای گذشته به Device قبلی تعلق داشته باشند.

---

# 2. Point Event و State Event

Eventها از نظر چرخه عمر به دو نوع اصلی تقسیم می‌شوند.

### Point Event

رخدادی که در یک نقطه زمانی اتفاق می‌افتد و شروع و پایان مستقل ندارد.

نمونه‌ها:

```text
IGNITION_ON
IGNITION_OFF
GEOFENCE_ENTER
GEOFENCE_EXIT
CRASH
```

زمان اصلی Point Event:

```text
occurred_at
```

است.

### State Event

رخدادی که یک وضعیت را در یک بازه زمانی نشان می‌دهد.

نمونه‌ها:

```text
DEVICE_OFFLINE
OVERSPEED
MOTION
IDLE
```

State Event با **یک رکورد** ذخیره می‌شود:

```text
started_at
ended_at
```

در زمان فعال بودن:

```text
ended_at = NULL
```

پس State Event به دو رکورد START و END تقسیم نمی‌شود.

---

# 3. چرخه عمر State Event

چرخه عمر منطقی:

```text
INACTIVE
   │
   │ condition detected
   ▼
ACTIVE
   │
   │ condition continues
   │
   ├──────────────► ACTIVE
   │
   │ condition ended
   ▼
CLOSED
```

در زمان شروع:

```text
CREATE Event
started_at = ...
ended_at = NULL
```

تا زمانی که وضعیت ادامه دارد، همان رکورد به‌روزرسانی می‌شود.

در زمان پایان:

```text
UPDATE Event
ended_at = ...
```

هر occurrence مستقل است.

مثال:

```text
OVERSPEED #125
started_at = 10:01:20
ended_at   = 10:04:35
```

اگر بعداً دوباره Overspeed اتفاق بیفتد:

```text
OVERSPEED #126
started_at = 10:06:00
ended_at   = NULL
```

Event جدید ایجاد می‌شود.

---

# 4. جلوگیری از Eventهای تکراری

وقتی یک State Event فعال است، Packetهای بعدی نباید Event جدید بسازند.

مثلاً:

```text
10:01 → speed = 130
10:02 → speed = 135
10:03 → speed = 128
10:04 → speed = 140
```

باید فقط یک Event داشته باشیم:

```text
OVERSPEED
started_at = 10:01
ended_at   = NULL
```

اطلاعات تکمیلی مانند:

```text
max_speed
speed_limit
```

در صورت نیاز می‌توانند در `attributes` یا فیلدهای تخصصی آینده نگهداری شوند.

---

# 5. Active State Event

برای هر:

```text
Device + Event Type
```

حداکثر یک State Event فعال وجود دارد.

این حالت مجاز نیست:

```text
Device 25
 ├── OVERSPEED #125 active
 └── OVERSPEED #126 active
```

باید فقط یک Event فعال وجود داشته باشد.

در طراحی دیتابیس PostgreSQL می‌توان از Partial Unique Constraint استفاده کرد:

```text
device + event_type
WHERE ended_at IS NULL
```

---

# 6. Threshold

Event Engine نباید با هر تغییر کوچک Telemetry، Event ایجاد یا بسته کند.

برای هر State Event باید شرایط شروع و پایان مشخص باشد.

مثلاً:

```text
شروع:
speed > speed_limit

پایان:
speed <= speed_limit
```

این Ruleها در آینده باید قابل تنظیم باشند و نباید در منطق پایه سیستم Hard-code باقی بمانند.

---

# 7. Hysteresis و Debounce

برای جلوگیری از باز و بسته شدن مداوم Event در اطراف Threshold، Event Engine می‌تواند از Hysteresis استفاده کند.

مثال:

```text
شروع OVERSPEED:
speed >= 125

ادامه:
speed > 120

پایان:
speed <= 120
```

همچنین بعضی Eventها می‌توانند شرط حداقل مدت داشته باشند:

```text
speed > threshold
        ↓
حداقل 10 ثانیه
        ↓
OPEN EVENT
```

بنابراین یک افزایش سرعت بسیار کوتاه الزاماً Event ایجاد نمی‌کند.

مقادیر Threshold، Hysteresis و Debounce باید در آینده در قالب Event Rule / Configuration قابل تنظیم باشند.

---

# 8. DEVICE_OFFLINE

`DEVICE_OFFLINE` با Eventهای مبتنی بر Telemetry تفاوت دارد.

Offline از روی **عدم دریافت Packet** تشخیص داده می‌شود.

مثلاً:

```text
offline_timeout = 5 minutes
```

اگر آخرین Packet در:

```text
server_received_at = 12:00:03
```

دریافت شده باشد، SANA در:

```text
12:05:03
```

می‌تواند Offline را تشخیص دهد.

در نتیجه:

```text
DEVICE_OFFLINE
started_at = 12:05:03
ended_at   = NULL
```

---

# 9. پایان DEVICE_OFFLINE

وقتی اولین Packet بعدی دریافت شود، Offline پایان می‌یابد.

مثال:

```text
Offline detected:
12:05:03

Packet received:
12:17:03
```

نتیجه:

```text
DEVICE_OFFLINE
started_at = 12:05:03
ended_at   = 12:17:03
```

برای Offline:

* `started_at` بر اساس زمان تشخیص Server است.
* `ended_at` بر اساس زمان دریافت Packet جدید در Server است.

زیرا فقط Server می‌تواند زمان واقعی عدم دریافت ارتباط را اندازه‌گیری کند.

---

# 10. device_time و server_received_at

هر Telemetry دو زمان مستقل دارد:

```text
device_time
server_received_at
```

### device_time

زمان اعلام‌شده توسط خود Device است.

کاربرد اصلی:

```text
Telemetry History
Trip
Location History
Eventهای مبتنی بر Telemetry دستگاه
Reports
```

### server_received_at

زمان واقعی دریافت Packet توسط SANA است.

کاربرد اصلی:

```text
Communication Monitoring
Offline Detection
Latency Analysis
Server-side Processing
```

این دو زمان نباید جای یکدیگر قرار بگیرند.

---

# 11. زمان Event

برای Eventهای مختلف، زمان مرجع با ماهیت Event تعیین می‌شود.

### Event مبتنی بر Telemetry دستگاه

تا حد امکان زمان وقوع از:

```text
device_time
```

استفاده می‌کند.

مثلاً:

```text
ignition = ON
device_time = 12:00:10
server_received_at = 12:00:13
```

Event:

```text
IGNITION_ON
occurred_at = 12:00:10
```

است.

زمان دریافت Packet نیز حفظ می‌شود:

```text
server_received_at = 12:00:13
```

### Eventهای ارتباطی / Server-side

Eventهایی که خود Server از وضعیت ارتباط تشخیص می‌دهد، از Server Time استفاده می‌کنند.

مثلاً:

```text
DEVICE_OFFLINE
started_at = server detection time
ended_at   = server packet-receipt time
```

---

# 12. اختلاف Device Time و Server Time

اختلاف بین:

```text
device_time
server_received_at
```

طبیعی است.

مثلاً:

```text
device_time        = 12:00:00
server_received_at = 12:00:03
```

این اختلاف می‌تواند ناشی از latency ارتباط باشد.

SANA نباید یکی را به دیگری تبدیل کند یا اختلاف را پنهان کند.

این اختلاف در آینده می‌تواند برای تحلیل موارد زیر استفاده شود:

```text
Communication Latency
Device Clock Problems
Network Delay
Offline / Reconnect Analysis
```

---

# 13. Offline با GPS No-Fix متفاوت است

این قانون قطعی است:

```text
gps_valid = false
```

به معنی Offline نیست.

ممکن است Device آنلاین باشد و Packet ارسال کند، اما GPS Fix نداشته باشد.

مثال:

```text
Packet received
gps_valid = false
```

در این حالت:

```text
DEVICE_OFFLINE = false
```

است.

بنابراین:

```text
GPS No Fix ≠ Device Offline
```

---

# 14. Reboot

Reboot کوتاه‌مدت Device به‌تنهایی باعث ایجاد Offline Event نمی‌شود.

مثلاً:

```text
Packet
↓
5 second gap
↓
Packet
```

نباید Offline محسوب شود.

Offline فقط زمانی تشخیص داده می‌شود که مدت عدم دریافت Packet از `offline_timeout` عبور کند.

---

# 15. Telemetry Gap

اگر بین دو Packet فاصله زیادی وجود داشته باشد، SANA نباید علت آن را حدس بزند.

مثلاً:

```text
12:00 → Packet
12:01 → Packet
12:02 → Packet

...

13:30 → Packet
```

SANA می‌تواند بر اساس Rule خود Offline را تشخیص دهد، اما نباید از روی این فاصله نتیجه بگیرد که علت حتماً:

```text
Device خاموش بوده
SIM قطع بوده
آنتن نداشته
Reboot شده
Server مشکل داشته
```

است.

علت واقعی در صورت مشخص بودن باید از منبع مربوطه بیاید.

---

# 16. Device Replacement

Event به Device تعلق دارد.

مثلاً:

```text
Vehicle A
   │
   └── Device 100
```

بعد Device جایگزین می‌شود:

```text
Vehicle A
   │
   └── Device 200
```

Eventهای Device 100 همچنان متعلق به:

```text
Device 100
```

باقی می‌مانند.

نباید Eventهای تاریخی هنگام Replacement به Device جدید منتقل شوند.

---

# 17. مرز Event و Alert

این یکی از مهم‌ترین مرزهای معماری SANA است.

### Event

Event بیانگر یک **رخداد واقعی و تاریخی در سیستم** است.

سؤال Event:

> «چه اتفاق معناداری افتاد؟»

مثلاً:

```text
Device
   ↓
speed = 135
   ↓
Event Engine
   ↓
OVERSPEED Event
```

این Event باید در تاریخچه سیستم وجود داشته باشد، حتی اگر هیچ Alertی برای آن تعریف نشده باشد.

---

### Alert Rule

`Alert Rule` تعریف می‌کند که:

> «در چه شرایطی یک رخداد یا وضعیت برای کاربر/کسب‌وکار مهم محسوب شود و باید هشدار ایجاد شود؟»

مثلاً:

```text
اگر:
speed > 120
و حداقل 10 ثانیه ادامه داشت

→ Alert Rule Trigger
```

Rule متعلق به لایه هشداردهی است، نه Event History.

---

### Alert

`Alert` نتیجه Trigger شدن یک Alert Rule برای یک مورد مشخص است.

مثلاً:

```text
OVERSPEED Event
       ↓
Alert Rule:
speed > 120 for 10 sec
       ↓
Alert
```

Alert به معنی «رخداد جدید» نیست؛ بلکه **هشدار حاصل از یک Rule روی یک رخداد/وضعیت** است.

---

# 18. Event بدون Alert

ممکن است Event ایجاد شود ولی هیچ Alertی ایجاد نشود.

مثلاً:

```text
OVERSPEED Event
       ↓
هیچ Alert Rule فعالی وجود ندارد
       ↓
No Alert
```

بنابراین:

```text
Event وجود دارد
Alert وجود ندارد
```

کاملاً معتبر است.

**Alert نبودن به معنی رخ ندادن Event نیست.**

---

# 19. یک Event می‌تواند چند Alert ایجاد کند

رابطه Event و Alert الزاماً یک‌به‌یک نیست.

مثلاً یک Event:

```text
OVERSPEED
```

می‌تواند همزمان با چند Rule منطبق شود:

```text
Event
  ├── Alert Rule A → Alert A
  ├── Alert Rule B → Alert B
  └── Alert Rule C → Alert C
```

بنابراین نباید Event را مستقیماً معادل Alert دانست.

---

# 20. Alert وابسته به User و Business Context است

Event ذاتاً مستقل از User است.

مثلاً:

```text
Device 125
OVERSPEED
10:01 → 10:04
```

یک واقعیت تاریخی سیستم است.

اما Alert می‌تواند وابسته به:

```text
User
Organization
Branch
Vehicle
Device
Alert Rule
Severity
Schedule
Permissions
Notification Settings
```

باشد.

مثلاً:

```text
User A:
Overspeed > 120 → Alert

User B:
Overspeed > 140 → Alert
```

یک Event واحد می‌تواند برای A Alert ایجاد کند ولی برای B نکند.

بنابراین:

```text
Event ≠ User Preference
Event ≠ Permission
Event ≠ Notification Setting
```

---

# 21. Event نباید به Alert وابسته باشد

این معماری اشتباه است:

```text
Telemetry
   ↓
Alert
   ↓
History
```

چون در این حالت تاریخچه سیستم به Ruleهای هشدار وابسته می‌شود.

معماری صحیح:

```text
Telemetry
   ↓
Event Engine
   ↓
Event
   ↓
Alert Rule Engine
   ↓
Alert
   ↓
Notification
```

در نتیجه:

**Event منبع حقیقت تاریخی رخداد است؛ Alert تصمیم هشداردهی بر اساس آن رخداد است.**

اگر Alert Rule بعداً تغییر یا حذف شود، Event تاریخی نباید تغییر کند.

---

# 22. Event و Alarm

Event و Alarm دو Entity مستقل هستند.

یک وضعیت می‌تواند باعث ایجاد هر دو شود، ولی این دو مفهوم با هم ادغام نمی‌شوند.

مثلاً:

```text
Telemetry
   │
   ├── Event Engine
   │      ↓
   │   OVERSPEED Event
   │
   └── Alert Rule Engine
          ↓
        Alert
```

یا Device می‌تواند خودش Alarm ارسال کند:

```text
Device
   ↓
Alarm
OVERSPEED
source = DEVICE
```

بنابراین:

```text
Event ≠ Alarm
Event ≠ Alert
Alarm ≠ Alert
```

---

# 23. مرز Alert و Notification

`Alert` و `Notification` نیز یک مفهوم نیستند.

### Alert

می‌گوید:

> «یک Rule هشدار Trigger شده است.»

مثلاً:

```text
Alert
type = OVERSPEED
severity = WARNING
```

### Notification

می‌گوید:

> «این Alert از چه روشی و برای چه مخاطبی ارسال/نمایش داده شود.»

مثلاً:

```text
Alert
   ↓
Notification
   ├── Panel
   ├── Push
   ├── SMS
   └── Email
```

بنابراین ممکن است Alert ایجاد شود ولی Notification ارسال نشود؛ مثلاً:

* کانال Notification غیرفعال باشد.
* User آن کانال را فعال نکرده باشد.
* Notification قبلاً ارسال شده باشد.
* ارسال با خطا مواجه شده باشد.
* Rule فقط نمایش داخل Panel را مشخص کرده باشد.

در نتیجه:

```text
Alert ≠ Notification
```

---

# 24. زنجیره نهایی

مرز مفاهیم در معماری SANA به این شکل است:

```text
GPS Device
    ↓
Telemetry
    │
    │ «چه چیزی گزارش شد؟»
    ↓
Event Engine
    │
    │ «چه رخداد معناداری اتفاق افتاد؟»
    ↓
Event
    │
    │ «آیا این رخداد طبق Rule
    │  نیاز به هشدار دارد؟»
    ↓
Alert Rule Engine
    │
    ↓
Alert
    │
    │ «به چه کسی و از چه کانالی
    │  اطلاع داده شود؟»
    ↓
Notification
```

این چهار لایه باید از یکدیگر مستقل باقی بمانند:

```text
Telemetry
Event
Alert
Notification
```

---

# 25. مثال کامل

فرض کنیم:

```text
Speed Limit = 120 km/h
```

دستگاه گزارش می‌کند:

```text
12:00:00 → 125
12:00:05 → 130
12:00:10 → 135
12:00:15 → 128
12:00:20 → 118
```

Event Engine تشخیص می‌دهد:

```text
OVERSPEED
started_at = 12:00:00
ended_at   = 12:00:20
```

این Event مستقل از Alert است.

حالا Rule شرکت:

```text
اگر OVERSPEED
بیش از 10 ثانیه ادامه داشت
→ Alert
```

پس:

```text
Event
   ↓
Alert Rule matched
   ↓
Alert created
```

و اگر User تنظیم کرده باشد:

```text
SMS = ON
Push = ON
Email = OFF
```

ممکن است:

```text
Alert
   ├── Push Notification
   └── SMS Notification
```

ایجاد شود.

اگر هیچ Ruleای وجود نداشت:

```text
Event
   ↓
No Alert
   ↓
No Notification
```

اما Event همچنان در تاریخچه باقی می‌ماند.

---

# 26. Event Model

مدل مفهومی Event:

```text
Event
├── id
├── device
├── type
├── source
├── mode
├── occurred_at
├── started_at
├── ended_at
├── device_time
├── server_received_at
├── latitude
├── longitude
├── gps_valid
├── attributes
├── telemetry_reference
└── raw_packet_reference
```

### Source

منبع Event:

```text
DEVICE
SANA
SYSTEM
```

قابل توسعه است.

### Mode

```text
POINT
STATE
```

---

# 27. Event Location

اگر Event دارای موقعیت باشد:

```text
latitude
longitude
gps_valid
```

ذخیره می‌شود.

اگر GPS معتبر نباشد، SANA نباید آخرین مختصات معتبر قبلی را به‌عنوان محل Event استفاده کند.

یعنی:

```text
gps_valid = false
```

نباید با مختصات قدیمی همراه شود و وانمود شود که Event در آن مختصات اتفاق افتاده است.

---

# 28. Event References

در صورت وجود ارتباط مشخص، Event می‌تواند به منابع اصلی خود Reference داشته باشد:

```text
telemetry_reference
raw_packet_reference
```

این امکان برای موارد زیر مهم است:

```text
Debugging
Audit
Traceability
Protocol Investigation
```

---

# 29. Event Typeهای اولیه

Event Typeهای اولیه مفهومی:

```text
DEVICE_ONLINE
DEVICE_OFFLINE

IGNITION_ON
IGNITION_OFF

MOTION_STARTED
MOTION_STOPPED

TRIP_STARTED
TRIP_ENDED

OVERSPEED

GEOFENCE_ENTER
GEOFENCE_EXIT
```

Eventهای آینده می‌توانند شامل مواردی مانند:

```text
HARSH_ACCELERATION
HARSH_BRAKING
HARSH_CORNERING
IDLE_STARTED
IDLE_ENDED
```

باشند.

این فهرست نهایی و بسته نیست و با توسعه Event Engine قابل گسترش است.

---

# 30. قانون‌های نهایی طراحی Event

### قانون 1

> Telemetry واقعیت گزارش‌شده توسط Device را ثبت می‌کند.

### قانون 2

> Event رخداد معناداری است که از Telemetry، وضعیت Device، تحلیل SANA یا شرایط سیستم به‌وجود آمده و ارزش تاریخی دارد.

### قانون 3

> State Event با یک رکورد و با `started_at` و `ended_at` مدیریت می‌شود.

### قانون 4

> برای هر Device و Event Type حداکثر یک State Event فعال وجود دارد.

### قانون 5

> Event مستقل از Alert است.

### قانون 6

> Event باید حتی بدون وجود Alert Rule نیز ثبت شود.

### قانون 7

> Alert نتیجه Trigger شدن یک Alert Rule است، نه خود رخداد تاریخی.

### قانون 8

> Alert می‌تواند وابسته به User، Organization، Branch، Permission و Notification Settings باشد؛ Event نباید به این موارد وابسته باشد.

### قانون 9

> Notification روش تحویل/نمایش Alert است و با Alert یکی نیست.

### قانون 10

> Event تاریخی نباید با تغییر یا حذف Alert Rule تغییر کند.

### قانون 11

> Alarm نیز Entity مستقلی است و نباید با Event یا Alert ادغام شود.

### قانون 12

> `device_time` و `server_received_at` همیشه به‌صورت مستقل حفظ می‌شوند و بر اساس ماهیت Event، زمان مرجع انتخاب می‌شود.

---

## جمع‌بندی مفهومی نهایی

```text
Telemetry
    │
    │ Device reported data
    ▼
Event
    │
    │ Meaningful historical occurrence
    ▼
Alert Rule
    │
    │ Business/User condition
    ▼
Alert
    │
    │ Delivery decision
    ▼
Notification
```

و در کنار آن:

```text
Device
   │
   └── Alarm
```

که یک مفهوم مستقل از Event/Alert است.

**اصل نهایی:**

> Event می‌گوید «چه اتفاقی افتاد؟»
>
> Alert می‌گوید «آیا این اتفاق طبق یک Rule نیاز به هشدار دارد؟»
>
> Notification می‌گوید «این هشدار چگونه و به چه کسی اعلام شود؟»
>
> Alarm می‌گوید «یک وضعیت هشدار/خطر از Device یا SANA تشخیص داده شده است.»


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Alert، Alert Rule و Notification

## 1. هدف

این سند طراحی مفهومی و تصمیمات قطعی مربوط به:

* Alert Rule
* Alert
* Alert Lifecycle
* Permission-based Distribution
* Notification
* Notification Settings

را مشخص می‌کند.

این سند مرجع معماری SANA برای مرحله پیاده‌سازی Alert است.

---

# 2. مرزبندی مفاهیم

در SANA این مفاهیم از یکدیگر جدا هستند:

```text
Telemetry
   ↓
Event
   ↓
Alert Rule
   ↓
Alert
   ↓
Notification
```

و Alarm مسیر مستقل خود را دارد:

```text
Device / SANA
      ↓
    Alarm
```

Alarm نیز می‌تواند توسط Alert Rule به Alert تبدیل شود:

```text
Alarm
  ↓
Alert Rule
  ↓
Alert
```

### تعریف مفاهیم

**Telemetry**

داده‌ای که دستگاه گزارش کرده است.

**Event**

یک اتفاق معنادار و تاریخی که از Telemetry، Device یا Environment تشخیص داده شده است.

**Alarm**

یک وضعیت هشدار/خطر که توسط Device یا SANA گزارش یا تشخیص داده شده است.

**Alert Rule**

قانونی که مشخص می‌کند یک Event یا Alarm در چه شرایطی باید به Alert تبدیل شود.

**Alert**

نتیجه واقعی Trigger شدن یک Alert Rule برای یک Event یا Alarm مشخص.

**Notification**

مکانیزم اطلاع‌رسانی Alert به کاربران مجاز.

---

# 3. اصل مهم: Alert مستقل از Notification است

هر Alert یک رکورد تاریخی واقعی در سیستم است.

Notification فقط روش اطلاع‌رسانی آن Alert است.

بنابراین:

```text
Alert = Historical Record
Notification = Delivery Mechanism
```

اگر ارسال SMS شکست بخورد:

```text
Event       ✓
Alert       ✓
Notification ✓
SMS Delivery ✗
```

Alert نباید به دلیل شکست Notification حذف یا بی‌اعتبار شود.

همچنین چیزی به نام:

```text
Notification-only Alert
```

نداریم.

هر Alert ایجادشده در تاریخچه Alertها باقی می‌ماند.

---

# 4. Alert همیشه منبع Trigger دارد

هر Alert باید مشخص کند چرا ایجاد شده است.

منبع Alert یکی از این دو مورد است:

```text
EVENT
ALARM
```

مثلاً:

```text
Alert
 ├── source_type = EVENT
 └── event = OVERSPEED
```

یا:

```text
Alert
 ├── source_type = ALARM
 └── alarm = SOS
```

یک Alert نباید هم‌زمان Event و Alarm داشته باشد.

Backend باید این رابطه را Validation کند.

---

# 5. Alert بدون Event یا Alarm

در طراحی فعلی:

> Alert بدون Trigger Source ایجاد نمی‌شود.

بنابراین همیشه باید بتوانیم پاسخ دهیم:

> «این Alert به خاطر چه Event یا Alarm ایجاد شد؟»

---

# 6. Alert Rule

Alert Rule یک تعریف دائمی از یک سیاست هشدار است.

مثال:

```text
اگر Event = OVERSPEED
و سرعت >= 120 km/h
→ Alert ایجاد کن
```

Rule خودش Alert نیست.

یک Rule می‌تواند در طول زمان صدها یا هزاران Alert ایجاد کند.

```text
Alert Rule
   ├── Alert #1
   ├── Alert #2
   ├── Alert #3
   └── ...
```

---

# 7. Rule و Telemetry

Alert Rule مستقیماً جای Event Engine را نمی‌گیرد.

معماری اصلی:

```text
Telemetry
    ↓
Event Engine
    ↓
Event
    ↓
Alert Rule Engine
    ↓
Alert
```

بنابراین:

```text
Event = واقعیت سیستم
Rule  = سیاست کاربر/سیستم
Alert = نتیجه اجرای سیاست
```

Rule می‌تواند شرط تکمیلی داشته باشد، ولی Event Engine همچنان مسئول تشخیص Event است.

---

# 8. Trigger Type

Alert Rule در نسخه اولیه حداقل دو Trigger دارد:

```text
EVENT
ALARM
```

مثال:

```text
trigger_type = EVENT
event_type = OVERSPEED
```

یا:

```text
trigger_type = ALARM
alarm_type = SOS
```

در آینده امکان Triggerهای جدید وجود دارد، ولی نباید از ابتدا معماری را بیش از نیاز پیچیده کرد.

---

# 9. Scope Rule

Rule باید Scope داشته باشد.

Scopeهای اولیه:

```text
GLOBAL
ORGANIZATION
BRANCH
DEVICE
```

### GLOBAL

Rule سیستمی که می‌تواند در سطح کل سیستم تعریف شود.

### ORGANIZATION

Rule مربوط به یک Organization.

### BRANCH

Rule مربوط به یک Branch.

### DEVICE

Rule مربوط به یک Device مشخص.

---

# 10. Vehicle Scope

در نسخه اولیه Vehicle Scope ایجاد نمی‌شود.

دلیل:

Device ممکن است در طول زمان بین Vehicleهای مختلف جابه‌جا شود.

فعلاً Scope اصلی:

```text
Organization
Branch
Device
```

است.

در آینده، در صورت نیاز واقعی، امکان Scopeهای دیگری مانند:

```text
Vehicle
Driver
Device Group
```

قابل اضافه شدن است.

---

# 11. مالک Rule

هر Rule باید مالک یا Scope مشخص داشته باشد.

از نظر مفهومی:

```text
System Rule
Customer Rule
```

وجود دارد.

Ruleهای سازمانی توسط Organization مدیریت می‌شوند و Ruleهای شخصی در محدوده حساب شخصی کاربر قرار می‌گیرند.

جزئیات دقیق ارتباط با مدل Account در زمان پیاده‌سازی بر اساس مدل‌های موجود SANA تعیین می‌شود.

---

# 12. دسترسی ساخت و مدیریت Rule

سطح دسترسی باید با Roleهای SANA هماهنگ باشد.

### site_admin

امکان مدیریت Ruleهای سیستمی و Scopeهای مجاز.

### main_user

امکان ایجاد و مدیریت Ruleهای Organization خودش.

### branch_manager

امکان مدیریت Ruleهای Scopeهایی که اجازه مدیریت آن‌ها را دارد.

### personal_user

امکان ایجاد Rule برای محدوده حساب و Deviceهای خودش.

Permission مربوط به مدیریت Rule با Permission مربوط به مشاهده Device یکسان نیست.

---

# 13. فعال / غیرفعال بودن Rule

Rule دارای وضعیت:

```text
is_active
```

است.

وقتی Rule غیرفعال شود:

```text
Event → ایجاد می‌شود
Alert → ایجاد نمی‌شود
```

Ruleهای قبلی حذف نمی‌شوند.

Alertهای قبلی نیز تغییر نمی‌کنند.

---

# 14. Hard Delete Rule

Rule نباید به‌صورت عادی Hard Delete شود.

به‌جای حذف:

```text
is_active = false
```

می‌شود.

دلیل:

Alertهای تاریخی ممکن است به آن Rule وابسته باشند.

---

# 15. تغییر Rule و تاریخچه Alert

اگر Rule تغییر کند، Alertهای قبلی نباید تحت تأثیر قرار بگیرند.

مثلاً:

```text
Rule قدیمی:
Speed >= 120
```

بعداً تغییر کند به:

```text
Speed >= 110
```

Alert قبلی همچنان مربوط به شرط 120 است.

برای همین Alert علاوه بر `rule_id` باید Trigger Context/Snapshot را نگهداری کند.

---

# 16. Rule Versioning

در نسخه اولیه Rule Versioning کامل ایجاد نمی‌شود.

یعنی فعلاً:

```text
Rule
   ↓
Current Configuration
```

و در Alert:

```text
rule_id
trigger_snapshot
```

نگهداری می‌شود.

اگر در آینده نیاز جدی به Version History وجود داشت، Rule Versioning به معماری اضافه خواهد شد.

---

# 17. Trigger Snapshot

Alert باید اطلاعات مهم Rule در لحظه Trigger را Snapshot کند.

مثال مفهومی:

```json
{
  "rule_name": "Overspeed",
  "event_type": "OVERSPEED",
  "threshold": 120,
  "minimum_duration": 30,
  "severity": "WARNING"
}
```

هدف:

حتی اگر Rule بعداً تغییر کند، Alert تاریخی همچنان قابل تفسیر باشد.

---

# 18. Condition

Rule می‌تواند Condition داشته باشد.

مثال:

```text
Event = OVERSPEED
AND
Speed >= 120
AND
Duration >= 30 seconds
```

Condition باید قابلیت توسعه داشته باشد.

در سطح مفهومی می‌تواند ساختاری مشابه:

```json
{
  "operator": "AND",
  "conditions": [
    {
      "field": "speed",
      "operator": ">=",
      "value": 120
    },
    {
      "field": "duration",
      "operator": ">=",
      "value": 30
    }
  ]
}
```

داشته باشد.

ساختار نهایی JSON و Validation در مرحله پیاده‌سازی مشخص خواهد شد.

Backend نباید JSON دلخواه و بدون Validation را اجرا کند.

---

# 19. Minimum Duration

برای جلوگیری از Alertهای ناشی از تغییرات لحظه‌ای:

```text
minimum_duration
```

در نظر گرفته می‌شود.

مثلاً:

```text
Speed >= 120
for at least 30 seconds
```

در این حالت یک افزایش سرعت چندثانیه‌ای الزاماً Alert ایجاد نمی‌کند.

---

# 20. Hysteresis

برای State Alertها Hysteresis قابل استفاده است.

مثال:

```text
Start:  >= 120
Resolve: <= 115
```

در نتیجه:

```text
120 → شروع
119 → ادامه
118 → ادامه
116 → ادامه
115 → پایان
```

این مکانیزم از باز و بسته شدن مداوم Alert جلوگیری می‌کند.

---

# 21. Cooldown

Cooldown با Minimum Duration متفاوت است.

### Minimum Duration

قبل از ایجاد Alert:

> شرط باید حداقل مدت مشخصی برقرار باشد.

### Cooldown

بعد از ایجاد Alert:

> تا مدت مشخصی Alert مشابه جدید ایجاد نشود.

مثال:

```text
Cooldown = 30 minutes
```

Cooldown برای جلوگیری از Alertهای تکراری استفاده می‌شود.

---

# 22. Deduplication

یک Event نباید به‌وسیله یک Rule چند Alert مشابه تولید کند.

مثلاً:

```text
Rule A + Event 100
```

باید فقط یک Alert ایجاد کند.

اما:

```text
Rule A + Event 100
Rule B + Event 100
```

می‌تواند دو Alert ایجاد کند؛ چون دو Rule مستقل Trigger شده‌اند.

بنابراین رابطه منطقی Deduplication حداقل شامل:

```text
Rule + Trigger Source
```

است.

---

# 23. Schedule

Rule می‌تواند Schedule داشته باشد.

مثلاً:

```text
شنبه تا چهارشنبه
08:00 تا 18:00
```

یا:

```text
24/7
```

اگر Event خارج از Schedule رخ دهد:

```text
Event = ایجاد می‌شود
Alert = ایجاد نمی‌شود
```

Schedule نباید Event History را تحت تأثیر قرار دهد.

---

# 24. Timezone

Schedule باید Timezone-aware باشد.

زمان‌های اصلی سیستم و ذخیره‌سازی:

```text
UTC
```

هستند.

Schedule باید با Timezone مشخص تفسیر شود.

مثلاً:

```text
Asia/Tehran
```

در Frontend نیز نمایش زمان با منطق Presentation انجام می‌شود.

---

# 25. Severity

Severity متعلق به Alert است و Rule آن را تعیین می‌کند.

سطوح اولیه:

```text
INFO
WARNING
CRITICAL
```

Event ذاتاً Severity ندارد.

مثلاً:

```text
Event:
OVERSPEED
```

می‌تواند توسط یک Rule تبدیل شود به:

```text
WARNING
```

و توسط Rule دیگری:

```text
CRITICAL
```

---

# 26. Alert Mode

Alert می‌تواند:

```text
POINT
STATE
```

باشد.

### POINT

یک اتفاق لحظه‌ای.

مثال:

```text
SOS
CRASH
IGNITION_ON
```

### STATE

یک وضعیت دارای شروع و پایان.

مثال:

```text
OVERSPEED
DEVICE_OFFLINE
```

---

# 27. Alert Lifecycle

وضعیت Alert و وضعیت رسیدگی User از هم جدا هستند.

وضعیت خود Alert:

```text
ACTIVE
RESOLVED
CLOSED
```

### ACTIVE

شرط Alert برقرار است یا Alert هنوز بسته نشده است.

### RESOLVED

شرط/وضعیت مربوط به Alert دیگر برقرار نیست.

مثلاً:

```text
OVERSPEED
ACTIVE
   ↓
RESOLVED
```

### CLOSED

برای Alertهایی که نیاز به بسته شدن نهایی دارند، مانند بعضی Point Alertها.

---

# 28. Acknowledgement

Acknowledgement با Resolve یکی نیست.

مثال:

```text
Alert = ACTIVE
Acknowledged = YES
```

یعنی User هشدار را دیده/تأیید کرده، اما علت هشدار هنوز برقرار است.

پس:

```text
ACTIVE ≠ UNACKNOWLEDGED
```

و:

```text
ACKNOWLEDGED ≠ RESOLVED
```

---

# 29. Acknowledgement User-specific است

یک Alert ممکن است برای چند User ارسال شود.

مثلاً:

```text
Alert #1001

User A → Acknowledged
User B → Unacknowledged
User C → Acknowledged
```

بنابراین `acknowledged_by` نباید مستقیماً روی Alert قرار گیرد.

اطلاعات تعامل User با Alert باید User-specific باشد.

---

# 30. Read و Acknowledge

این دو نیز جدا هستند.

### Read

کاربر Notification/Alert را مشاهده کرده است.

### Acknowledge

کاربر هشدار را تأیید کرده است.

ممکن است:

```text
Read = YES
Acknowledge = NO
```

باشد.

---

# 31. Permission-based Alert Distribution

این یکی از تصمیمات قطعی SANA است:

> گیرنده Alert به‌صورت دستی در Rule تعریف نمی‌شود.

وقتی Alert ایجاد شد:

```text
Alert
   ↓
Permission Engine
   ↓
تمام Userهایی که در آن لحظه مجوز مشاهده Device را دارند
```

آن Userها گیرندگان Alert هستند.

مثلاً:

```text
Device 1001
   ↓
Alert
   ↓
Permission Check

User A ✓
User B ✓
User C ✗
User D ✓
```

Notification برای A، B و D ایجاد می‌شود.

---

# 32. Permission و Notification Settings

دو مفهوم کاملاً جدا هستند.

### Permission

مشخص می‌کند:

> چه کسی حق مشاهده/دریافت Alert مربوط به Device را دارد؟

### Notification Settings

مشخص می‌کند:

> User مجاز از چه کانالی Notification دریافت کند؟

مثلاً:

```text
User A
Permission = YES

Notification Settings:
IN_APP = YES
SMS = YES
EMAIL = NO
```

---

# 33. Recipient دستی وجود ندارد

در Alert Rule فیلدی مانند:

```text
recipients
recipient_users
```

وجود ندارد.

Rule فقط مشخص می‌کند:

```text
چه چیزی؟
برای چه Scope؟
با چه شرایطی؟
با چه Severity؟
```

گیرنده توسط Permission Engine تعیین می‌شود.

---

# 34. Permission در زمان ایجاد Alert

Permission در لحظه ایجاد Alert بررسی می‌شود.

اگر User در آن لحظه مجوز Device را داشته باشد، وارد فرآیند Notification می‌شود.

اگر بعداً Permission او حذف شود:

```text
Alert قبلی
```

حذف یا تغییر نمی‌کند.

اما Alertهای بعدی برای آن User ارسال نمی‌شوند.

---

# 35. User جدید و Alert قدیمی

اگر User بعد از ایجاد Alert مجوز Device را بگیرد:

```text
Alert ساعت 10:00
Permission ساعت 10:05
```

Alert ساعت 10:00 مجدداً برای User ارسال نمی‌شود.

User از آن لحظه Alertهای جدید را دریافت می‌کند.

---

# 36. Notification

Notification روش اطلاع‌رسانی Alert است.

یک Alert می‌تواند چند Notification داشته باشد.

مثلاً:

```text
Alert
 ├── IN_APP
 ├── SMS
 └── EMAIL
```

Notification خودش یک رکورد مستقل است و Lifecycle ارسال خودش را دارد.

---

# 37. Channel

Channelهای اولیه:

```text
IN_APP
SMS
EMAIL
```

Channelهای آینده:

```text
PUSH
WEBHOOK
...
```

قابل اضافه شدن هستند.

---

# 38. Notification Status

Notification می‌تواند وضعیت‌هایی مانند:

```text
PENDING
SENDING
SENT
DELIVERED
FAILED
CANCELLED
```

داشته باشد.

همه Channelها الزاماً تمام این وضعیت‌ها را پشتیبانی نمی‌کنند.

مثلاً Email یا SMS ممکن است Delivery Confirmation داشته باشد، ولی IN_APP منطق متفاوتی دارد.

---

# 39. Notification Failure

شکست Notification نباید Alert را تغییر دهد.

مثلاً:

```text
Alert = ACTIVE
SMS Notification = FAILED
```

Alert همچنان معتبر است.

---

# 40. Retry

برای Channelهایی که ارسال خارجی دارند، Notification می‌تواند Retry داشته باشد.

اطلاعات مفهومی:

```text
retry_count
next_retry_at
last_error
```

مثلاً:

```text
Attempt 1 → FAILED
Attempt 2 → FAILED
Attempt 3 → SENT
```

---

# 41. Notification Template

متن Notification نباید Hard-Code شود.

Template می‌تواند شامل اطلاعات Alert باشد:

```text
هشدار سرعت غیرمجاز
خودرو: {vehicle}
سرعت: {speed}
زمان: {time}
```

Template برای Channelهای مختلف می‌تواند متفاوت باشد.

مثلاً SMS متن کوتاه داشته باشد و Email قالب کامل‌تری.

---

# 42. Notification Settings

User می‌تواند برای Channelهای مجاز تنظیمات داشته باشد.

مثلاً:

```text
IN_APP = ON
SMS = ON
EMAIL = OFF
```

Permission مشخص می‌کند User مجاز است.

Notification Settings مشخص می‌کند از چه روش‌هایی اطلاع‌رسانی شود.

---

# 43. Notification Policy

در نسخه اولیه نیازی نیست Recipient داخل Notification Policy تعریف شود.

Policy در صورت نیاز می‌تواند تنظیمات مربوط به:

```text
Channel
Template
Schedule
Retry
Active/Inactive
```

را کنترل کند.

اما Recipient از Permission Engine می‌آید.

---

# 44. Notification Schedule

Schedule Notification از Schedule Rule مستقل است.

ممکن است:

```text
Alert Rule = 24/7
```

ولی:

```text
SMS Notification = فقط 08:00 تا 18:00
```

باشد.

در این حالت:

```text
Alert = ایجاد می‌شود
SMS = ایجاد نمی‌شود
```

ولی مثلاً IN_APP می‌تواند همچنان فعال باشد.

---

# 45. Alert Rule غیرفعال شود

اگر Rule غیرفعال شود:

```text
Event → همچنان ایجاد می‌شود
Alert جدید → ایجاد نمی‌شود
Alert قبلی → معتبر باقی می‌ماند
```

اگر Alert قبلی State باشد، غیرفعال شدن Rule به‌تنهایی آن را Resolve نمی‌کند.

Event باید Lifecycle طبیعی خودش را طی کند.

---

# 46. Permission حذف شود

اگر Permission یک User حذف شود:

```text
Alertهای قبلی → باقی می‌مانند
Notificationهای قبلی → باقی می‌مانند
Alertهای جدید → برای آن User ارسال نمی‌شوند
```

تاریخچه سیستم نباید با تغییر Permission بازنویسی شود.

---

# 47. Alertهای State

مثلاً:

```text
OVERSPEED
```

جریان:

```text
Event Started
    ↓
Alert ACTIVE
    ↓
Event Ended
    ↓
Alert RESOLVED
```

Alert نباید با هر Telemetry جدید دوباره ایجاد شود.

---

# 48. Alertهای Point

مثلاً:

```text
SOS
```

جریان:

```text
Alarm/Event
    ↓
Alert
    ↓
Notification
```

Alert یک اتفاق تاریخی را ثبت می‌کند و می‌تواند بعداً توسط فرآیند رسیدگی بسته شود.

---

# 49. Alert تکراری

اگر یک Event State مانند Overspeed چندین Telemetry داشته باشد:

```text
125
126
127
128
127
```

نباید چند Alert ایجاد شود.

باید یک Alert به همان Event متصل باشد:

```text
OVERSPEED Event
      ↓
ONE Alert
```

---

# 50. Alarm تکراری

اگر Device یک Alarm را چند بار ارسال کند، Alarm/Event Engine باید بتواند تکرارها را مدیریت کند.

Alert Engine نیز نباید صرفاً بر اساس تعداد Packetها Alertهای بی‌نهایت ایجاد کند.

Deduplication و Cooldown در این بخش نقش دارند.

---

# 51. Escalation

Escalation در معماری آینده قابل پشتیبانی است، ولی در MVP پیاده‌سازی نمی‌شود.

مثال آینده:

```text
Critical Alert
   ↓
5 minutes without acknowledgement
   ↓
Escalation
```

اما در نسخه اول Recipient جدید برای Escalation به‌صورت دستی تعریف نمی‌شود.

در صورت اضافه شدن Escalation، Permission و Roleهای مناسب نیز باید در نظر گرفته شوند.

---

# 52. مدل مفهومی Alert

```text
Alert
├── id
├── rule
├── source_type
├── event
├── alarm
├── mode
├── severity
├── status
├── triggered_at
├── started_at
├── resolved_at
├── closed_at
├── trigger_snapshot
└── attributes
```

قواعد:

```text
source_type = EVENT
→ event پر
→ alarm خالی

source_type = ALARM
→ alarm پر
→ event خالی
```

---

# 53. مدل مفهومی User تعامل با Alert

مفهوم User-specific:

```text
AlertUser
├── alert
├── user
├── read_at
├── acknowledged_at
└── ...
```

این موجودیت وضعیت مشاهده/رسیدگی هر User را نسبت به Alert نگه می‌دارد.

یک Alert می‌تواند برای چند User وجود داشته باشد.

---

# 54. مدل مفهومی Notification

```text
Notification
├── id
├── alert
├── user
├── channel
├── status
├── created_at
├── sent_at
├── delivered_at
├── read_at
├── retry_count
└── error
```

در صورت نیاز به تفکیک کامل Notification و Delivery:

```text
Notification
      ↓
NotificationDelivery
```

قابل استفاده است.

---

# 55. جریان کامل Alert

```text
GPS Device
     ↓
Telemetry
     ↓
Event / Alarm
     ↓
Alert Rule Engine
     ↓
Alert
     ↓
Permission Engine
     ↓
Users with Device Access
     ↓
Notification Settings
     ↓
Channel Selection
     ↓
Notification
     ↓
Delivery
```

---

# 56. اصول غیرقابل تغییر

1. Telemetry با Event یکی نیست.
2. Event با Alert یکی نیست.
3. Alert با Notification یکی نیست.
4. Alarm با Alert یکی نیست.
5. Rule با Alert یکی نیست.
6. Event History مستقل از Alert Rule است.
7. Alert History مستقل از Notification است.
8. شکست Notification نباید Alert را حذف کند.
9. تغییر Rule نباید Alertهای تاریخی را تغییر دهد.
10. تغییر Permission نباید Alertهای تاریخی را بازنویسی کند.
11. Recipient به‌صورت دستی در Rule تعریف نمی‌شود.
12. تمام Userهای دارای Permission مشاهده Device در زمان ایجاد Alert، وارد فرآیند دریافت Alert می‌شوند.
13. Notification Settings فقط روش دریافت را تعیین می‌کند.
14. Alert باید Trigger Source داشته باشد.
15. یک State Event نباید برای هر Telemetry یک Alert جدید ایجاد کند.
16. Alertهای Point و State Lifecycle متفاوت دارند.
17. Rule غیرفعال شدن به‌تنهایی Alert فعال قبلی را Resolve نمی‌کند.
18. Permission در `sana-backend` مدیریت می‌شود.
19. `sana-gps` مسئول Permission، User، Organization و Notification Business Logic نیست.
20. Escalation فعلاً خارج از MVP است ولی معماری باید امکان افزودن آن را حفظ کند.

---

# 57. معماری نهایی

```text
                         TELEMETRY
                             │
             ┌───────────────┴───────────────┐
             │                               │
             ▼                               ▼
           EVENT                           ALARM
             │                               │
             └───────────────┬───────────────┘
                             ▼
                       ALERT RULE
                             │
                             ▼
                           ALERT
                             │
                             ▼
                    PERMISSION ENGINE
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           USER A          USER B         USER C
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                  NOTIFICATION SETTINGS
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           IN_APP           SMS            EMAIL
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                         DELIVERY
```

این طراحی، مرز **Event → Alert Rule → Alert → Notification** را مشخص می‌کند و مبنای پیاده‌سازی Alert Engine و Notification در مراحل بعدی خواهد بود.


============================================================================
============================================================================

# SANA — یادداشت تصمیمات معماری GPS، نقشه زنده، داده دستگاه و Geofence

تاریخ: ۱۴۰۵/۰۷/۱۰

این یادداشت حاصل تصمیمات معماری بخش GPS، دریافت داده دستگاه‌ها، Telemetry، نقشه زنده، تاریخچه موقعیت، Trip، گزارش‌گیری، Event، Alert و Geofence است.

هدف اصلی:

**ساخت یک سیستم GPS قدرتمند، قابل توسعه و مقیاس‌پذیر، ولی تا حد امکان مینیمال و بدون پیچیدگی و پوشه‌بندی غیرضروری.**

---

# 1. ساختار کلی پروژه

پروژه SANA به سرویس‌ها/بخش‌های منطقی جدا تقسیم می‌شود:

```text
SANA/
├── sana-backend/      → Django، Business Logic، API، Auth و مدیریت سیستم
├── sana-gps/          → دریافت و پردازش داده GPS
├── sana-panel/        → پنل تحت وب
└── sana-mobile/       → در آینده، اپلیکیشن موبایل
```

اصل مهم:

تفکیک سرویس‌ها انجام می‌شود، ولی داخل هر سرویس از ایجاد پوشه‌ها و لایه‌های غیرضروری خودداری می‌شود.

---

# 2. مسئولیت sana-gps

sana-gps مسئول ارتباط مستقیم با دستگاه‌های GPS است.

وظایف:

* TCP
* UDP
* مدیریت Connection
* Session
* ACK
* تشخیص Protocol
* Parse کردن Protocol
* Normalization
* اعتبارسنجی فنی داده
* دریافت Raw Packet
* ذخیره/پردازش Telemetry
* Location
* Current State
* داده‌های مربوط به وضعیت GPS

اما مسئول موارد زیر نیست:

* User
* Permission
* Customer
* Organization
* Contract
* Subscription
* Driver
* Business Logic مربوط به Fleet
* Geofence Business Logic
* Alert Logic

اصل:

هر بخش وظیفه خودش را دارد، ولی ارتباطش را با سایر بخش‌ها حفظ می‌کند.

---

# 3. استفاده از ایده‌های Traccar و سایر سیستم‌ها

Traccar به‌عنوان یکی از مراجع مهم برای Protocol Decoderها بررسی شد.

ایده مورد قبول:

```text
GPS Device
→ Protocol
→ Decoder
→ Normalized Data
```

قرار نیست کل Traccar وارد SANA شود.

قرار است از معماری و تجربه پروژه‌های موفق مثل Traccar و Flespi استفاده شود و در صورت امکان Decoderهای مناسب نیز با رعایت License و شرایط استفاده بررسی شوند.

هدف:

عدم پیاده‌سازی دوباره صدها Protocol از صفر، در عین حال حفظ استقلال SANA.

---

# 4. Database

sana-gps مستقیماً به PostgreSQL فعلی SANA متصل می‌شود.

اما دسترسی منطقی آن محدود خواهد بود.

sana-gps:

* داده‌های GPS/Telemetry را می‌نویسد.
* اطلاعات لازم Device را می‌خواند.
* اطلاعات لازم DeviceModel/Protocol را می‌خواند.
* به Business Data غیرمرتبط دسترسی ندارد.

sana-gps نباید مستقیماً Business Logic سیستم را اجرا کند.

---

# 5. مقیاس هدف

هدف فعلی:

حداکثر حدود ۱۰٬۰۰۰ دستگاه

سقف احتمالی:

حدود ۱۵٬۰۰۰ دستگاه

بنابراین معماری باید از ابتدا برای این مقیاس قابل رشد باشد، ولی فعلاً نباید با ابزارهای سنگین و غیرضروری مثل Kafka/RabbitMQ و معماری Microservice پیچیده شروع شود.

---

# 6. معماری اولیه مقیاس‌پذیری

در شروع:

```text
GPS Devices
→ sana-gps
→ PostgreSQL
```

و در آینده، اگر حجم واقعاً نیاز داشت:

```text
sana-gps
→ Queue / Message Layer
→ Workers
→ Database
```

بنابراین معماری باید قابلیت اضافه کردن Queue در آینده را داشته باشد، ولی Queue از روز اول اجباری نیست.

همچنین sana-gps باید در آینده قابلیت اجرای چند Instance داشته باشد.

مثلاً:

```text
Load Balancer
→ sana-gps #1
→ sana-gps #2
```

ولی نسخه اول ساده خواهد بود.

---

# 7. IMEI

IMEI شناسه اصلی دستگاه در Gateway خواهد بود.

جریان:

```text
IMEI
→ Device
→ DeviceModel
→ Protocol
```

اما IMEI تنها مکانیزم امنیتی نخواهد بود.

معماری باید امکان اضافه شدن روش‌های دیگر Authentication را در آینده داشته باشد.

---

# 8. Unknown Device

اصل امنیتی:

دستگاه باید ابتدا در SANA ثبت شده باشد تا داده آن معتبر شناخته شود.

اگر IMEI ناشناس یا درخواست ناشناس از یک Port دریافت شود:

* داده معتبر تلقی نمی‌شود.
* پردازش کامل انجام نمی‌شود.
* درخواست‌های ناشناس باید تا حد امکان سریع رد شوند.

هدف:

جلوگیری از دریافت و پردازش حجم زیادی از TCP/UDP درخواست‌های نامعتبر.

در آینده در صورت نیاز می‌توان Unknown Device / Pending Device را اضافه کرد، ولی حالت پیش‌فرض:

**Device باید قبلاً در سیستم تعریف شده باشد.**

---

# 9. Protocol و Port

هر Protocol در حالت پایه Port مشخص و قابل تنظیم خودش را دارد.

مثلاً:

```text
Teltonika TCP → Port قابل تنظیم
Teltonika UDP → Port قابل تنظیم
GT06 TCP → Port قابل تنظیم
...
```

Portها از پنل Admin قابل تعریف/تنظیم خواهند بود.

معماری باید در آینده امکان Shared Port و Protocol Detection را هم داشته باشد.

اگر دستگاه Protocol را داخل Packet مشخص کند، امکان تشخیص Protocol از Packet نیز وجود داشته باشد.

---

# 10. Session

اگر یک IMEI همزمان چند Connection ایجاد کند، باید Session مدیریت شود.

اصل:

برای هر Device/IMEI یک Session فعال داشته باشیم.

در صورت ایجاد Connection جدید:

Connection جدید می‌تواند جایگزین Session قبلی شود.

هدف:

جلوگیری از چند Session متناقض برای یک دستگاه.

---

# 11. ACK

ACK کاملاً مسئولیت sana-gps است.

Django نباید در ACK دخالت کند.

مثلاً:

```text
Packet
→ Decoder
→ ACK
→ Normalized Telemetry
```

ACK بخشی از Protocol Handling است.

---

# 12. Offline

مدت زمان Offline قابل تنظیم است.

این مقدار از پنل Admin قابل تنظیم خواهد بود.

مثلاً:

```text
last_seen = X
```

اگر تا مدت مشخصی داده دریافت نشد:

```text
Device = Offline
```

این مقدار نباید Hard-Code شود.

Offline با GPS No Fix یا Geofence Exit یکی نیست.

---

# 13. Timestamp

هر Telemetry حداقل دو زمان دارد:

```text
device_time
server_received_at
```

`device_time`:

زمانی که خود دستگاه برای داده ثبت کرده.

`server_received_at`:

زمانی که SANA داده را دریافت کرده.

هر دو باید نگهداری شوند.

این موضوع برای:

* بررسی اختلاف ساعت دستگاه
* بررسی تأخیر شبکه
* Debug
* تحلیل مشکلات GPS
* گزارش‌گیری
* تشخیص Out-of-Order Data

مهم است.

زمان‌های داخلی و Database به‌صورت UTC نگهداری می‌شوند.

---

# 14. Raw Packet

Raw Packet برای همیشه نگهداری نمی‌شود.

دلیل احتمالی نگهداری:

* Debug
* بررسی مشکل Parser
* بررسی Packet غیرعادی
* توسعه Protocol
* امکان بررسی مجدد داده

ولی بعد از Parse موفق و ذخیره Normalized Data، معمولاً نیازی به نگهداری دائمی Raw نیست.

تصمیم:

Raw Packet دارای Retention قابل تنظیم باشد.

مدت نگهداری از پنل Admin قابل تنظیم باشد.

مثلاً:

```text
7 روز
30 روز
...
```

پس از پایان Retention، Raw Data حذف شود.

Normalized Data بلندمدت نگهداری شود.

---

# 15. ذخیره‌سازی هوشمند Location

قرار نیست هر Packet دریافتی برای همیشه به‌صورت یک رکورد مستقل ذخیره شود.

اصل مهم:

اگر خودرو در حال حرکت است یا وضعیتش تغییر می‌کند، داده‌ها باید با جزئیات مناسب ذخیره شوند.

اما اگر خودرو مدت زیادی ثابت بماند و داده‌های تکراری دریافت کند، نباید هزاران رکورد تکراری تولید شود.

مثلاً:

```text
08:00 → در حال حرکت
08:30 → پارک
12:30 → هنوز همان مکان
15:30 → هنوز همان وضعیت
18:00 → دوباره حرکت
```

لازم نیست تمام Packetهای یکسان بین 08:30 تا 15:30 به‌عنوان Location مستقل ذخیره شوند.

می‌توانیم وضعیت را به شکل یک بازه ذخیره کنیم:

```text
start_time
end_time
location
state
```

مثلاً:

```text
08:30 → 12:30
موقعیت X
Stopped
```

بعد با تغییر وضعیت رکورد جدید ایجاد شود.

هدف:

کاهش شدید افزونگی دیتابیس بدون از دست دادن اطلاعات تاریخی مهم.

---

# 16. GPS Fix نداشتن

ممکن است دستگاه برای چند ساعت GPS Fix نداشته باشد.

این وضعیت نیز نباید باعث ایجاد هزاران رکورد تکراری شود.

باید بتوانیم با بررسی دو رکورد بفهمیم:

```text
از ساعت X تا ساعت Y:
GPS Fix وجود نداشته است.
```

بنابراین وضعیت‌هایی مانند:

```text
GPS Fix
No GPS Fix
Stopped
Moving
...
```

باید قابلیت ذخیره به شکل Interval/State داشته باشند.

GPS No Fix به معنی Offline نیست.

---

# 17. Telemetry

Telemetry استاندارد شامل داده‌های عمومی خواهد بود.

نمونه:

```text
device
device_time
server_received_at
latitude
longitude
speed
heading
altitude
satellites
gps_valid
accuracy
ignition
battery_voltage
external_voltage
gsm_signal
odometer
engine_hours
fuel_level
temperature
motion
...
```

در کنار این‌ها:

```text
attributes
```

برای داده‌های اختصاصی Protocol/Device استفاده می‌شود.

---

# 18. داده‌های اختصاصی Device

هر Device ممکن است داده‌ای داشته باشد که Device دیگری ندارد.

بنابراین:

```text
Normalized Fields
+
attributes
```

مثلاً:

```text
speed
heading
ignition
```

فیلدهای استاندارد باشند.

و:

```text
temperature
door
custom_io
BLE sensors
cellular details
...
```

در attributes قرار بگیرند، در صورتی که فیلد عمومی استاندارد SANA برایشان تعریف نشده باشد.

مواردی که قبلاً به‌عنوان فیلد استاندارد قطعی شده‌اند، مانند `fuel_level`، `engine_hours` و `odometer`، به‌عنوان فیلد استاندارد خودشان باقی می‌مانند.

---

# 19. Location History

Location مستقیماً به Device متصل است.

نه Vehicle.

ساختار مفهومی:

```text
Device
→ Location History
```

نه:

```text
Vehicle
→ Location History
```

دلیل:

ممکن است Device A از Vehicle A جدا شود و Device B جایگزین آن شود.

تاریخچه Device A نباید جابه‌جا یا خراب شود.

---

# 20. ارتباط Device و Vehicle

Location:

```text
Location
→ Device
→ Vehicle فعلی/مرتبط
```

در گزارش Vehicle، در صورت نیاز تاریخچه Deviceهای مختلفی که در دوره‌های مختلف روی Vehicle بوده‌اند، ترکیب خواهد شد.

بنابراین تعویض دستگاه باعث از بین رفتن تاریخچه Vehicle نمی‌شود.

Assignment بین Device و Vehicle باید قابلیت Temporal History داشته باشد.

---

# 21. Current State

برای هر Device یک Current State خواهیم داشت.

Current State برای Live Map استفاده می‌شود.

حداقل اطلاعات:

```text
device
last_seen
latitude
longitude
speed
heading
ignition
gps_valid
accuracy
satellites
```

و در صورت وجود:

```text
battery
external_voltage
fuel
temperature
gsm_signal
...
```

Current State آخرین وضعیت دستگاه را نگه می‌دارد.

---

# 22. Live Map

Live Map مستقیماً از Current State استفاده می‌کند.

نه اینکه برای نمایش لحظه‌ای Map به Location History مراجعه کند.

ساختار:

```text
GPS
→ Current State
→ WebSocket
→ Authorized User
→ Map
```

---

# 23. WebSocket

WebSocket از همان ابتدا در معماری Live Map در نظر گرفته می‌شود.

هدف:

وقتی موقعیت/وضعیت Device تغییر کرد، اطلاعات جدید بدون Refresh صفحه به کاربران مجاز ارسال شود.

ساختار:

```text
GPS
→ Current State
→ WebSocket
→ Authorized Users
→ Map
```

---

# 24. Permission

sana-gps مسئول Permission نیست.

Permission در sana-backend مدیریت می‌شود.

ساختار:

```text
User
→ Permission
→ Accessible Devices / Vehicles
→ Current State
→ WebSocket
→ Map
```

کاربر نباید حتی مختصات Device غیرمجاز را از WebSocket دریافت کند.

یعنی مخفی کردن Marker در Frontend کافی نیست.

داده غیرمجاز اصلاً نباید به Browser ارسال شود.

---

# 25. Marker

در نسخه اول Marker اطلاعات زیر را نشان می‌دهد:

* خودرو
* راننده
* سرعت
* وضعیت
* آخرین Update

با کلیک روی Marker امکان توسعه به موارد زیر وجود دارد:

* جزئیات دستگاه
* مسیر امروز
* تاریخچه
* گزارش

فعلاً همین اطلاعات کافی است و بعداً بر اساس نیاز تغییر می‌کند.

---

# 26. Marker Clustering

برای تعداد زیاد Device از Marker Clustering استفاده می‌شود.

در Zoom Out:

```text
127
```

نشان داده شود.

با Zoom In:

```text
127
→ چند Cluster
→ Deviceهای جداگانه
```

این مورد برای تعداد زیاد دستگاه ضروری خواهد بود.

---

# 27. Current Map و History

دو مسیر داده جدا هستند:

Live:

```text
Current State
→ WebSocket
→ Map
```

History:

```text
Location History
→ Query
→ Polyline / Playback
```

Live Map نباید برای نمایش لحظه‌ای History را Query کند.

---

# 28. گزارش‌گیری

گزارش‌ها از داده‌های تاریخی و پردازش‌شده ساخته می‌شوند.

ساختار کلی:

```text
GPS
→ Location History
→ Trip / Event / Aggregation
→ Reports
```

گزارش‌ها باید قابلیت تعیین:

* تاریخ شروع
* تاریخ پایان
* ساعت شروع
* ساعت پایان

را داشته باشند.

یعنی کاربر بتواند یک محدوده دقیق زمانی تعیین کند و گزارش فقط برای همان بازه ساخته شود.

زمان ورودی کاربر بر اساس Timezone مربوطه به UTC تبدیل می‌شود و Query با UTC انجام خواهد شد.

---

# 29. Trip

Trip دو حالت دارد:

Current Trip:

برای Live UI و نمایش وضعیت سفر جاری.

Final Trip:

بعد از پایان سفر محاسبه و تکمیل می‌شود.

ساختار:

```text
GPS
→ Current Trip
```

بعد از پایان:

```text
Current Trip
→ Final Trip
```

Trip می‌تواند شامل:

* شروع
* پایان
* مبدأ
* مقصد
* مدت
* مسافت
* توقف‌ها
* سرعت‌ها

باشد.

Geofence مسئول محاسبه Trip نیست، ولی Geofence Eventها می‌توانند در گزارش Trip استفاده شوند.

---

# 30. Device Replacement و هم‌زمانی Device قدیمی و جدید

هر Vehicle در هر لحظه فقط یک Device فعال دارد.

Assignment دستگاه به Vehicle Temporal است:

```text
Device 1
start_at ───────── end_at

Device 2
                    start_at ─────────
```

در زمان تعویض:

* Device قدیمی پایان Assignment دارد.
* Device جدید Assignment جدید دارد.
* Device جدید Active Device فعلی Vehicle است.

اگر Device قدیمی بعد از تعویض همچنان Packet ارسال کند:

* Telemetry آن می‌تواند تحت Device قدیمی ذخیره شود.
* برای History/Debug قابل استفاده است.
* نباید Current State فعلی Vehicle را تغییر دهد.
* نباید Geofence State فعلی Vehicle را تغییر دهد.
* نباید Current Trip جدید Vehicle را تحت تأثیر قرار دهد.

State مربوط به Device قدیمی به Device جدید منتقل نمی‌شود.

Device جدید از یک Observation جدید شروع می‌کند:

```text
UNOBSERVED
→ اولین GPS معتبر
→ Evaluation
→ ENTER_PENDING / OUTSIDE / ...
```

اگر Packet قدیمی Device 1 بعداً دریافت شود، می‌تواند برای History استفاده شود ولی نباید State فعلی را Rollback کند.

Database باید تا حد امکان تضمین کند که یک Vehicle هم‌زمان دو Device Active نداشته باشد.

---

# 31. Restart / Crash شدن Geofence Engine

`VehicleGeofenceState` باید Persistent و در PostgreSQL ذخیره شود.

State فقط در RAM نگهداری نمی‌شود.

Stateهایی مانند:

```text
OUTSIDE
INSIDE
ENTER_PENDING
EXIT_PENDING
UNCERTAIN
UNOBSERVED
```

باید قابل بازیابی باشند.

اطلاعات Candidate نیز Persistent خواهد بود، مانند:

```text
candidate_state
candidate_started_at
```

بنابراین:

```text
Geofence Engine
→ Restart
→ Load State
→ Continue Processing
```

Restart به‌تنهایی نباید Event ایجاد کند.

اگر Engine وسط `ENTER_PENDING` خاموش شود، بعد از Restart باید بتواند با State ذخیره‌شده ادامه دهد.

از دست رفتن Telemetry در زمان Restart به‌تنهایی نباید باعث EXIT مصنوعی شود.

Idempotency نیز باید از ایجاد Event تکراری در اثر پردازش مجدد Packet جلوگیری کند.

---

# 32. قطع PostgreSQL و Recovery

PostgreSQL منبع اصلی Persistent State است.

اگر Database موقتاً در دسترس نباشد:

* State فقط در RAM تغییر داده نمی‌شود.
* Processing وابسته به Transaction Database متوقف یا Retry می‌شود.
* برای قطعی کوتاه می‌توان Buffer موقت و محدود داشت.
* Buffer جای Queue دائمی نیست.
* Queue واقعی در صورت نیاز در معماری آینده اضافه می‌شود.

بعد از Recovery:

* داده‌های موجود در Buffer دوباره پردازش می‌شوند.
* داده قدیمی نباید State جدیدتر را Rollback کند.
* Packet از دست‌رفته نباید باعث Event حدسی شود.
* Database outage نباید به‌عنوان Device Offline تفسیر شود.

سیاست دقیق Backpressure/Queue مربوط به طراحی فنی sana-gps خواهد بود و در MVP پیچیده نمی‌شود.

---

# 33. Timezone و مدیریت زمان

تمام زمان‌های داخلی و Database به‌صورت UTC ذخیره می‌شوند.

شامل:

```text
device_time
server_received_at
occurred_at
started_at
ended_at
start_at
end_at
```

Timezone برای نمایش و Query ورودی کاربر استفاده می‌شود.

Timezone با استاندارد IANA نگهداری می‌شود، مانند:

```text
Asia/Tehran
```

نه صرفاً Offset ثابت.

Device ممکن است ساعت نادرست یا Timezone نادرست داشته باشد.

SANA نباید `device_time` را خودکار اصلاح کند.

اختلاف:

```text
device_time
vs
server_received_at
```

می‌تواند برای تشخیص مشکل ساعت دستگاه و تحلیل تأخیر استفاده شود.

---

## Geofence Schedule

Scheduleهای Geofence بر اساس Timezone مالک/Scope مربوطه تفسیر می‌شوند.

در MVP برای هر Geofence Timezone مستقل تعریف نمی‌کنیم.

مثلاً:

```text
Organization
timezone = Asia/Tehran

Geofence
schedule = 08:00 - 18:00
```

به معنای 08:00 تا 18:00 به وقت همان Timezone است.

Assignmentهای Temporal در Database با UTC ذخیره می‌شوند.

---

# 34. مدل نهایی داده Geofence

مدل مفهومی:

```text
Geofence
   │
   ├── GeofenceVersion
   │
   ├── GeofenceAssignment
   │
   └── VehicleGeofenceState
              │
              └── Event
```

## Geofence

هویت و تنظیمات اصلی:

```text
id
name
description
ownership_type
organization
branch
personal_account
active
valid_from
valid_until
deleted_at
enter_delay
exit_delay
boundary_tolerance
max_acceptable_accuracy
dwell_enabled
dwell_duration
created_at
updated_at
```

Geometry مستقیماً به‌عنوان Geometry فعلی در Geofence نگهداری نمی‌شود؛ Geometry Versioned است.

---

## GeofenceVersion

هر تغییر واقعی Geometry یک Version جدید ایجاد می‌کند.

```text
GeofenceVersion
├── id
├── geofence
├── version_number
├── geometry_type
├── geometry
├── radius
├── valid_from
├── valid_until
├── created_at
└── ...
```

Circle:

```text
geometry = Point
radius = X meters
```

Polygon:

```text
geometry = Polygon
radius = NULL
```

Event به Version دقیق مربوط به زمان وقوع اشاره می‌کند.

---

## GeofenceAssignment

Assignment می‌تواند در سطح:

```text
Organization
Branch
Vehicle
```

باشد.

Assignmentها Temporal هستند:

```text
start_at
end_at
```

Assignmentها Include-only هستند و Negative Override/Exclusion در MVP ندارند.

اگر حداقل یک مسیر معتبر Assignment وجود داشته باشد، Geofence برای Vehicle قابل اعمال است.

---

## VehicleGeofenceState

برای هر:

```text
Vehicle + Geofence
```

یک State فعلی داریم.

این جدول History نیست.

وظیفه آن نگهداری وضعیت فعلی و اطلاعات لازم برای ادامه State Machine است.

اطلاعات مفهومی:

```text
vehicle
geofence
state
observed_with_device
last_telemetry
last_observed_at
candidate_started_at
candidate_state
active_version
...
```

در صورت نبود Device فعال، State می‌تواند:

```text
UNOBSERVED
```

باشد.

---

## Event

Geofence Event بخشی از Event Model عمومی SANA است.

نمونه‌ها:

```text
GEOFENCE_ENTER
GEOFENCE_EXIT
GEOFENCE_DWELL
```

Event می‌تواند شامل:

```text
device
vehicle/context
type
source
mode
occurred_at
started_at
ended_at
device_time
server_received_at
latitude
longitude
gps_valid
accuracy
attributes
telemetry_reference
raw_packet_reference
geofence
geofence_version
```

باشد.

در سطح معماری، Geofence Event یک Event عمومی با Context مربوط به Geofence است و الزاماً سیستم Event جداگانه‌ای ایجاد نمی‌کند.

---

# 35. قوانین قطعی Geofence

## 35.۱ Geometry

در MVP فقط:

```text
CIRCLE
POLYGON
```

پشتیبانی می‌شود.

LINE در MVP وجود ندارد.

Geometry با PostGIS ذخیره می‌شود.

---

## 35.۲ Lifecycle

Geofence دارای:

```text
active
valid_from
valid_until
deleted_at
```

است.

Engine فقط Geofence فعال و معتبر در بازه زمانی مربوطه را پردازش می‌کند.

Hard Delete برای Geofence ممنوع است؛ حذف به شکل Soft Delete انجام می‌شود.

---

## 35.۳ Geometry Versioning

تغییر Geometry یا Radius:

```text
New Geofence Version
```

ایجاد می‌کند.

Version قبلی حفظ می‌شود.

Event به Version دقیق مربوط به زمان خودش متصل می‌شود.

تغییرات Metadata مانند Name/Description الزاماً Version جدید ایجاد نمی‌کنند.

---

## ۳۵.۴ Ownership

مالکیت Geofence می‌تواند:

```text
SYSTEM / GLOBAL
ORGANIZATION
BRANCH
PERSONAL
```

باشد.

سطح دسترسی با ساختار Role/Permission SANA هماهنگ است.

---

## ۳۵.۵ Assignment

Assignment در سه سطح:

```text
ORGANIZATION
BRANCH
VEHICLE
```

است.

Assignmentها Temporal هستند.

Assignment تغییر کند، ولی این تغییر به‌تنهایی Physical GEOFENCE_EXIT ایجاد نمی‌کند.

---

## ۳۵.۶ Branch / Organization Movement

اگر Vehicle از Branch یا Organization خارج شود:

* اگر مسیر Assignment دیگری هنوز Geofence را معتبر کند، State تغییر نمی‌کند.
* اگر Applicability کاملاً از بین برود، State به حالت غیرقابل مشاهده/Inactive می‌رود.
* GEOFENCE_EXIT مصنوعی تولید نمی‌شود.

اگر دوباره Assignment برقرار شود:

* Evaluation جدید انجام می‌شود.
* State قبلی صرفاً به‌صورت خودکار بازیابی نمی‌شود.
* اگر Vehicle داخل Geofence باشد، ابتدا `ENTER_PENDING` و سپس در صورت تکمیل Delay، `GEOFENCE_ENTER` ایجاد می‌شود.

---

## ۳۵.۷ Device Replacement

Assignment Geofence به Vehicle وابسته است، نه Device.

بنابراین با تعویض Device:

* Geofence Assignment باقی می‌ماند.
* State Device قبلی منتقل نمی‌شود.
* Device جدید Evaluation مستقل خود را آغاز می‌کند.
* Device قدیمی نمی‌تواند State فعلی Vehicle را Rollback کند.

---

## ۳۵.۸ Event Types

در MVP:

```text
GEOFENCE_ENTER
GEOFENCE_EXIT
GEOFENCE_DWELL
```

وجود دارد.

`GEOFENCE_INSIDE` Event نداریم.

---

## ۳۵.۹ Debounce و Hysteresis

برای جلوگیری از Flapping:

```text
enter_delay
exit_delay
boundary_tolerance
```

در نظر گرفته می‌شود.

Debounce مربوط به زمان است.

Hysteresis مربوط به تحمل مکانی اطراف Boundary است.

System Default وجود دارد و برای هر Geofence امکان Override وجود دارد.

---

## ۳۵.۱۰ GPS Accuracy

اگر:

```text
gps_valid = false
```

باشد، تصمیم مکانی گرفته نمی‌شود.

`accuracy` بر حسب متر ذخیره می‌شود.

همچنین:

```text
max_acceptable_accuracy
```

در سطح System Default و در صورت نیاز Override در Geofence وجود دارد.

Poor Accuracy باعث تولید EXIT/ENTER مصنوعی نمی‌شود.

---

## ۳۵.۱۱ State Machine

Stateهای اصلی:

```text
OUTSIDE
INSIDE
ENTER_PENDING
EXIT_PENDING
UNCERTAIN
UNOBSERVED
```

Candidate Timer بر اساس **زمان معتبر Observation** کار می‌کند، نه تعداد Packet.

UNCERTAIN:

* Timer را متوقف می‌کند.
* Timer را از ابتدا Reset نمی‌کند.
* با Observation مخالف Candidate را Cancel می‌کند.

زمان Offline، No Fix یا Observation نامعتبر جزو Delay محسوب نمی‌شود.

---

## ۳۵.۱۲ GPS Gap / Offline / No Fix

این سه مفهوم جدا هستند:

```text
GPS No Fix
Telemetry Gap
Device Offline
```

هیچ‌کدام به‌تنهایی GEOFENCE_EXIT ایجاد نمی‌کنند.

بعد از بازگشت اولین GPS معتبر:

* State دوباره ارزیابی می‌شود.
* زمان از دست‌رفته به‌صورت مصنوعی محاسبه نمی‌شود.

---

## ۳۵.۱۳ Dwell

Dwell مستقل از Enter/Exit Event است.

Dwell فقط بعد از Confirmed Enter شروع می‌شود.

```text
ENTER
↓
Inside Episode
↓
Dwell Timer
↓
GEOFENCE_DWELL
```

در هر Inside Episode حداکثر یک Dwell ایجاد می‌شود.

اگر قبل از تکمیل Threshold خروج رخ دهد، Dwell ایجاد نمی‌شود.

---

## ۳۵.۱۴ Overlap

Vehicle می‌تواند هم‌زمان داخل چند Geofence باشد.

هر Geofence State مستقل دارد.

Overlap مجاز است.

هیچ Geofence اولویت ذاتی نسبت به دیگری ندارد.

یک Telemetry می‌تواند باعث ایجاد چند Event برای چند Geofence شود.

---

## ۳۵.۱۵ Multiple Assignment Paths

اگر یک Geofence از چند مسیر به Vehicle اعمال شود:

```text
Organization
+
Branch
+
Vehicle
```

باز هم فقط یک Effective Applicability ایجاد می‌شود.

نباید برای یک Geofence به دلیل چند مسیر Assignment، چند Event تولید شود.

---

## ۳۵.۱۶ Sparse GPS / High Speed

SANA زمان دقیق عبور بین دو نقطه را حدس نمی‌زند.

Event در اولین Observation معتبر که Transition را تأیید کند ثبت می‌شود.

اگر Vehicle بین دو Observation وارد و خارج شده باشد ولی هیچ Observation خارج از محدوده‌ای وجود نداشته باشد، Event مصنوعی ساخته نمی‌شود.

---

## ۳۵.۱۷ Device Clock و Out-of-Order

`device_time` زمان اصلی برای Chronology فیزیکی است.

`server_received_at` برای ترتیب دریافت و تحلیل ارتباط نگهداری می‌شود.

Packetهای Out-of-Order:

* الزاماً حذف نمی‌شوند.
* می‌توانند در History ذخیره شوند.
* نباید Current State را به عقب برگردانند.
* نباید Geofence State فعلی را Rollback کنند.

برای Real-Time Processing از Watermark مانند:

```text
last_processed_device_time
```

استفاده می‌شود.

Historical Replay در آینده می‌تواند فرآیند جداگانه‌ای داشته باشد.

---

## ۳۵.۱۸ Vehicle / Organization / Branch Temporal Context

Assignmentهای Vehicle، Device و Geofence باید قابلیت تاریخچه زمانی داشته باشند.

گزارش تاریخی باید Context مربوط به زمان همان Event را Resolve کند.

تغییرات فعلی نباید Eventهای تاریخی را Mutate کنند.

---

## ۳۵.۱۹ Restart / Recovery

Geofence State در PostgreSQL Persistent است.

Restart Engine:

```text
Restart
≠
ENTER
≠
EXIT
```

State و Candidate Timing از Database بازیابی می‌شوند.

پردازش مجدد Packet نباید Event تکراری ایجاد کند.

---

## ۳۵.۲۰ Database Failure

Database outage:

```text
≠
Device Offline
```

در قطعی کوتاه، Buffer موقت محدود قابل استفاده است.

داده از دست‌رفته نباید حدس زده شود.

State فقط بعد از Transaction موفق Database معتبر تلقی می‌شود.

---

## ۳۵.۲۱ Performance

Geofence Engine نباید هر GPS Point را با تمام Geofenceهای سیستم مقایسه کند.

ترتیب کلی:

```text
Telemetry
→ Effective Assignment Set
→ Active/Valid Filter
→ Spatial Candidate Filter
→ PostGIS Exact Check
→ State Machine
→ Event
```

از Spatial Index مانند GiST استفاده خواهد شد.

Effective Geofence Set می‌تواند Cache شود، ولی Database منبع اصلی حقیقت است.

Cache باید در صورت تغییر:

* Assignment
* Geofence
* Branch
* Organization

Invalidate یا Rebuild شود.

هدف:

برای ۱۰٬۰۰۰ Vehicle، پردازش `10,000 × همه Geofenceها` انجام نشود.

---

## ۳۵.۲۲ Long Stationary Vehicle

اگر Vehicle مدت زیادی داخل Geofence ثابت بماند:

* Event تکراری ایجاد نمی‌شود.
* State روی INSIDE باقی می‌ماند.
* GPS Jitter نباید Flapping ایجاد کند.
* Poor Accuracy باعث Exit نمی‌شود.
* No Fix State قبلی را حفظ می‌کند ولی ادعای موقعیت فعلی قطعی نمی‌شود.
* Offline باعث Exit نمی‌شود.
* Dwell حداکثر یک بار در هر Inside Episode ایجاد می‌شود.

Location Compression مستقل از Geofence Engine است.

---

## ۳۵.۲۳ History

Geofence History از Eventها ساخته می‌شود.

Location History مسیر واقعی را نگه می‌دارد.

در History Geofence باید در صورت وجود بتوان موارد زیر را دید:

* Vehicle
* Geofence
* Event Type
* Event Time
* Device Time
* Server Receive Time
* Position
* GPS Accuracy
* Device
* Geofence Version
* GPS Status
* Details

مدت حضور می‌تواند از:

```text
ENTER → EXIT
```

محاسبه شود.

اگر EXIT وجود نداشته باشد، Visit به‌عنوان Open Visit باقی می‌ماند.

---

## ۳۵.۲۴ Alert

Geofence مستقیماً Alert ایجاد نمی‌کند.

جریان:

```text
Geofence
→ Event
→ Alert Rule
→ Alert
→ Notification
```

Alert Rule می‌تواند:

* GEOFENCE_ENTER
* GEOFENCE_EXIT
* GEOFENCE_DWELL

را Trigger کند.

Rule می‌تواند Geofence مشخص یا مجموعه‌ای از Geofenceهای Scope خودش را هدف قرار دهد.

Alert تاریخچه Rule و Context لازم را به‌صورت Snapshot نگه می‌دارد.

---

## ۳۵.۲۵ Permission

Geofence Engine مسئول Permission نیست.

Permission در Backend مدیریت می‌شود.

Frontend نباید فقط Marker یا Event غیرمجاز را مخفی کند.

داده غیرمجاز نباید اصلاً به User ارسال شود.

---

# 36. مرز مسئولیت‌ها

## sana-gps

```text
Device
→ TCP / UDP
→ Protocol
→ Decoder
→ ACK
→ Normalized Telemetry
```

`sana-gps` درباره Geofence، Permission، Alert یا Business Assignment تصمیم نمی‌گیرد.

---

## Geofence Engine

```text
Normalized Telemetry
→ Device
→ Vehicle
→ Effective Geofence
→ Spatial Evaluation
→ State Machine
→ Event
```

Geofence Engine مسئول:

* Enter
* Exit
* Dwell
* State
* Debounce
* Hysteresis
* Accuracy
* Assignment Applicability
* Geometry Version
* Idempotency

است.

---

## Event

Event یک اتفاق معنادار ثبت‌شده در سیستم است.

مثلاً:

```text
GEOFENCE_ENTER
GEOFENCE_EXIT
GEOFENCE_DWELL
```

Event خودش Notification ارسال نمی‌کند.

---

## Alert Rule

Alert Rule روی Event/Alarm تصمیم می‌گیرد آیا اتفاق باید به Alert تبدیل شود یا خیر.

---

## Alert

Alert نتیجه اجرای Alert Rule است.

---

## Notification

Notification فقط Alert را از طریق Channelهایی مانند:

```text
IN_APP
SMS
EMAIL
```

به مقصد می‌رساند.

---

# 37. معماری نهایی Geofence

```text
                         GPS DEVICE
                             │
                             ▼
                       TCP / UDP
                             │
                             ▼
                         sana-gps
                             │
                             ▼
                    Protocol Decoder
                             │
                             ▼
                 Normalized Telemetry
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
         Current State   Location     Geofence
                         History       Engine
                                        │
                                        ▼
                              Effective Assignment
                                        │
                                        ▼
                              Vehicle + Geofence
                                        │
                                        ▼
                             State Machine
                                        │
                                        ▼
                                      Event
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                              ▼                   ▼
                         Alert Rule           History
                              │
                              ▼
                            Alert
                              │
                              ▼
                        Notification
```

اصل نهایی:

> **Telemetry واقعیت مشاهده‌شده توسط Device است؛ Geofence آن را به Event معنادار تبدیل می‌کند؛ Alert Rule تصمیم می‌گیرد کدام Event مهم است؛ Notification فقط آن Alert را منتقل می‌کند.**

---

# 38. تصمیمات نهایی Geofence

موارد زیر نهایی و تأیید شده‌اند:

[✓] Circle و Polygon در MVP
[✓] عدم پشتیبانی Line در MVP
[✓] استفاده از PostGIS
[✓] Geofence Lifecycle با Active و Validity
[✓] Soft Delete
[✓] Geometry Versioning
[✓] نگهداری Versionهای قدیمی
[✓] Assignment در سطح Organization / Branch / Vehicle
[✓] Assignmentهای Temporal
[✓] Include-only Assignment
[✓] عدم Negative Override در MVP
[✓] Ownership مستقل از Assignment
[✓] Vehicle به‌عنوان Business Target
[✓] Device به‌عنوان منبع Telemetry
[✓] Device Replacement بدون انتقال State
[✓] یک Device فعال برای هر Vehicle
[✓] ENTER / EXIT / DWELL
[✓] عدم وجود GEOFENCE_INSIDE Event
[✓] Debounce
[✓] Hysteresis
[✓] GPS Accuracy
[✓] max_acceptable_accuracy
[✓] State Machine
[✓] ENTER_PENDING / EXIT_PENDING
[✓] UNCERTAIN
[✓] UNOBSERVED
[✓] Dwell مستقل
[✓] یک Dwell در هر Inside Episode
[✓] Overlapping Geofences
[✓] State مستقل برای هر Vehicle + Geofence
[✓] جلوگیری از Event تکراری
[✓] Idempotency
[✓] Transaction / Locking
[✓] عدم Rollback State توسط Packet قدیمی
[✓] Device Clock بدون Auto Correction
[✓] Device Time + Server Receive Time
[✓] عدم حدس زمان عبور بین نقاط
[✓] عدم EXIT مصنوعی در Offline
[✓] عدم EXIT مصنوعی در GPS No Fix
[✓] عدم EXIT مصنوعی در Assignment Removal
[✓] عدم EXIT مصنوعی در Geometry Change
[✓] عدم انتقال State در Device Replacement
[✓] Persistent State در PostgreSQL
[✓] Recovery بعد از Restart
[✓] Buffer محدود در Database Failure
[✓] عدم تشخیص Database Outage به‌عنوان Offline
[✓] UTC برای زمان‌های داخلی
[✓] IANA Timezone
[✓] Schedule بر اساس Timezone مالک/Scope
[✓] History مستقل از Current State
[✓] Geofence Event به‌عنوان Event عمومی SANA
[✓] Geofence → Event → Alert Rule → Alert → Notification
[✓] Permission خارج از sana-gps
[✓] Spatial Index
[✓] Effective Geofence Set
[✓] جلوگیری از مقایسه همه Vehicleها با همه Geofenceها
[✓] طراحی برای مقیاس 10,000 تا 15,000 دستگاه

---

# 39. وضعیت طراحی

طراحی مفهومی بخش Geofence اکنون **کامل و نهایی شده است**.

مرحله بعدی این بخش:

```text
Conceptual Design
        ↓
Django / PostgreSQL Data Model
        ↓
Fields
        ↓
Relations
        ↓
Constraints
        ↓
Indexes
        ↓
Services / Processing
        ↓
Implementation
```

اما قبل از پیاده‌سازی، ابتدا سایر بخش‌های SANA نیز باید بررسی شوند تا معماری کلی پروژه کامل و بدون تناقض باشد.

**Geofence فعلاً وارد مرحله کدنویسی نمی‌شود و به‌عنوان یک بخش معماری نهایی‌شده ثبت می‌شود.**


============================================================================
============================================================================

# SANA GPS — قرارداد نهایی Attributes

## Normalized Telemetry

## 1. تعریف

`Attributes` محل نگهداری داده‌های معتبر و Normalize‌شده‌ای است که:

* در حال حاضر Standard Field نیستند،
* ساختارشان ممکن است بین Deviceها متفاوت باشد،
* یا برای توسعه آینده به انعطاف بیشتری نیاز دارند.

Attributes جایگزین Schema اصلی SANA نیست.

قاعده:

```text
Standard Field
→ مفهوم عمومی و پایدار SANA

Attributes
→ داده توسعه‌پذیر و غیرهسته‌ای

Specialized Model
→ داده پیچیده و دارای رفتار مستقل
```

---

## 2. Storage Format

Attributes با PostgreSQL `JSONB` ذخیره می‌شوند.

ساختار باید:

* Nested
* Namespaced
* lowercase
* snake_case

باشد.

نمونه:

```json
{
  "cell": {
    "mcc": 432,
    "mnc": 11,
    "lac": 12345,
    "cell_id": 987654
  },
  "ble": {
    "sensor_1": {
      "temperature": 23.4
    }
  },
  "io": {
    "input_1": true
  }
}
```

از Keyهای Flat مانند:

```text
cell.mcc
cell.mnc
sensor.temperature
```

به‌عنوان ساختار اصلی JSON استفاده نمی‌شود.

---

## 3. Namespaceهای پایه

Namespaceهای اولیه:

```text
cell
ble
io
sensor
protocol
device
custom
```

این فهرست بسته نیست و در آینده قابل توسعه است.

---

## 4. Typeهای مجاز

JSONB می‌تواند شامل:

```text
string
number
boolean
null
object
array
```

باشد.

اگر مقدار از نظر منطقی عددی است، نباید بدون دلیل به String تبدیل شود.

مثلاً:

```json
{
  "sensor": {
    "temperature": 23.4
  }
}
```

صحیح است، نه:

```json
{
  "sensor": {
    "temperature": "23.4"
  }
}
```

---

## 5. Validation Pipeline

جریان کلی:

```text
Raw Packet
    ↓
Parse
    ↓
Normalize
    ↓
Validate
    ↓
Normalized Telemetry
```

Validation شامل:

* Type validation
* Structure validation
* Size validation
* Naming validation
* Semantic validation
* Security validation

است.

---

## 6. محدودیت‌های امنیتی

Attributes دارای محدودیت‌های فنی خواهند بود:

```text
Maximum Size
Maximum Nesting Depth
Maximum Number of Keys
Allowed JSON Types
Allowed Key Format
```

مقادیر غیرمعتبر مانند:

```text
NaN
Infinity
```

نباید وارد Normalized Telemetry شوند.

وجود String به‌تنهایی خطر امنیتی محسوب نمی‌شود و Sanitization نباید محتوای معتبر را بی‌دلیل تغییر دهد.

Attributes هیچ قابلیت اجرایی ندارند و هرگز نباید به‌عنوان:

```text
SQL
Command
JavaScript
Executable Content
```

تفسیر یا اجرا شوند.

---

## 7. خطای Attribute

خرابی یک Attribute لزوماً نباید کل Telemetry را Reject کند.

مثلاً:

```text
Telemetry
├── Standard Fields ✓
├── Valid Attributes ✓
└── Invalid Attribute ✗
```

تا حد امکان فقط همان Attribute کنار گذاشته یا Invalid مدیریت می‌شود.

اما خرابی یک Standard Field حیاتی می‌تواند باعث نامعتبر شدن کل Telemetry شود.

---

# 8. محل نگهداری Attributes

## Normalized Telemetry

تمام Attributes معتبر در ساختار کامل Normalized Telemetry قابل دسترسی هستند.

```text
NormalizedTelemetry
└── attributes
```

---

## Current State

Current State فقط Attributes مجاز برای وضعیت فعلی را نگه می‌دارد.

```text
CurrentState
└── attributes
```

این مقدار:

> آخرین مقدار شناخته‌شده است، نه History.

اگر Attribute در Telemetry جدید وجود نداشته باشد، مقدار قبلی به‌صورت خودکار حذف نمی‌شود.

```text
Absent
≠
Deleted
≠
Invalid
```

---

## Location History

Location History فقط Attributes انتخاب‌شده طبق History Policy را نگه می‌دارد.

کل Attributes به‌صورت خودکار وارد History نمی‌شوند.

Storage:

```text
JSONB
```

است.

اگر یک Attribute دائماً برای Queryهای Business مورد استفاده قرار گیرد، باید Promotion آن بررسی شود.

---

## Event

Event دارای Snapshot مستقل از Attributes مرتبط با همان Event است.

تمام Attributes Telemetry کپی نمی‌شوند.

مثلاً:

```json
{
  "speed": 125,
  "speed_limit": 100
}
```

Event Snapshot:

* کوچک
* مرتبط
* Immutable

است.

Snapshot بعداً با تغییر Current State یا Telemetry تغییر نمی‌کند.

---

# 9. Namespace Policy

| Namespace  | Normalized Telemetry | Current State | Location History | Event              |
| ---------- | -------------------- | ------------- | ---------------- | ------------------ |
| `cell`     | کامل                 | بله           | خیر              | در صورت نیاز       |
| `ble`      | کامل                 | آخرین مقدار   | انتخابی          | در صورت نیاز       |
| `io`       | کامل                 | آخرین مقدار   | انتخابی          | در صورت مرتبط بودن |
| `sensor`   | کامل                 | آخرین مقدار   | انتخابی          | در صورت مرتبط بودن |
| `protocol` | کامل                 | خیر           | خیر              | فقط Event فنی      |
| `device`   | کامل                 | انتخابی       | خیر              | در صورت نیاز       |
| `custom`   | کامل                 | انتخابی       | خیر پیش‌فرض      | در صورت نیاز       |

در Location History، انتخاب Attributes می‌تواند حتی در سطح Path انجام شود؛ مثلاً یک Attribute خاص از `ble`، نه کل Namespace.

---

# 10. Attribute Registry

در MVP جدول مستقلی مانند:

```text
AttributeDefinition
```

ایجاد نمی‌کنیم.

Policy فعلاً در:

```text
Code / Configuration
```

تعریف می‌شود.

Policy مفهومی شامل:

```text
namespace
allowed_types
max_size
history_policy
current_state_policy
```

است.

در صورت افزایش پیچیدگی سیستم، این Policy در آینده می‌تواند به Registry دیتابیسی تبدیل شود.

---

# 11. Current State و Freshness

Current State آخرین مقدار شناخته‌شده Attribute را نگه می‌دارد.

عدم دریافت مقدار جدید به معنی حذف مقدار قبلی نیست.

همچنین:

```text
Value
```

از:

```text
Freshness
```

مستقل است.

نباید یک Timeout واحد برای تمام Attributes استفاده شود، زیرا Sensorهای مختلف می‌توانند Intervalهای متفاوتی داشته باشند.

در صورت اعلام صریح Device مبنی بر Invalid یا Unavailable بودن مقدار، این وضعیت می‌تواند به‌صورت مستقل مدیریت شود.

---

# 12. Event Snapshot

Event Snapshot فقط اطلاعات مرتبط با Event را ذخیره می‌کند.

تمام Telemetry کپی نمی‌شود.

ساختار مفهومی:

```text
Event
├── Standard Event Fields
├── attributes JSONB
├── telemetry_reference
└── raw_packet_reference
```

Snapshot پس از ایجاد Event:

```text
Immutable
```

است.

Current State هیچ نقشی در تغییر Snapshot تاریخی Event ندارد.

---

# 13. Indexing

در MVP روی `attributes` هیچ Generic Index سراسری ایجاد نمی‌کنیم.

یعنی به‌صورت پیش‌فرض:

```text
Normalized Telemetry → No Generic JSONB Index
Current State        → No Generic JSONB Index
Location History     → No Generic JSONB Index
Event                → No Generic JSONB Index
```

اگر یک Attribute خاص واقعاً زیاد Query شود:

```text
Targeted Index
```

قابل ایجاد است.

اما اگر یک Attribute به داده مهم و پرتکرار تبدیل شود، قبل از Index دائمی باید Promotion آن بررسی شود.

---

# 14. Attributes جایگزین Schema نیست

اگر داده‌ای به‌مرور:

* پرتکرار شود،
* Business Important شود،
* در گزارش‌ها استفاده شود،
* در Filterها استفاده شود،
* در Alertها استفاده شود،
* در Live Map استفاده شود،
* نیاز به Index دائمی پیدا کند،
* Validation پیچیده پیدا کند،

باید بررسی شود که آیا باید تبدیل شود به:

```text
Standard Field
```

یا:

```text
Specialized Model
```

---

# 15. Promotion Lifecycle

Attribute می‌تواند از این مسیر عبور کند:

```text
ACTIVE
   ↓
DEPRECATED
   ↓
PROMOTED
```

### ACTIVE

برای داده جدید قابل استفاده است.

### DEPRECATED

برای داده جدید توصیه نمی‌شود، ولی برای Compatibility ممکن است موقتاً پذیرفته شود.

### PROMOTED

مفهوم به Standard Field یا Specialized Model منتقل شده است.

در MVP برای این Lifecycle جدول مستقل ایجاد نمی‌کنیم.

---

# 16. Promotion و داده قدیمی

Promotion نباید باعث از بین رفتن History شود.

ممکن است:

```text
Old Data
→ Attribute
```

و از زمان Promotion:

```text
New Data
→ Standard Field
```

باشد.

در صورت نیاز، Migration/Backfill می‌تواند داده‌های تاریخی را منتقل کند.

اگر مدتی هر دو مقدار وجود داشته باشند، باید Source of Truth مشخص باشد.

پس از تکمیل Migration:

> Standard Field یا Specialized Model منبع اصلی خواهد بود و Attribute قدیمی نباید به‌عنوان مقدار مستقل جدید تولید شود.

---

# 17. Compatibility

تغییر Firmware یا Protocol نباید قرارداد داخلی SANA را بشکند.

معماری:

```text
Device / Firmware
        ↓
Protocol Decoder
        ↓
Normalization
        ↓
Stable SANA Contract
```

مثلاً تغییر:

```text
temp
```

به:

```text
temperature
```

اگر هر دو یک مفهوم باشند، Decoder باید آنها را به یک Attribute استاندارد داخلی Normalize کند.

---

# 18. Unit Compatibility

اگر Device مقدار را با Unit متفاوت بفرستد:

```text
°F
```

یا:

```text
°C
```

تبدیل باید در Normalizer انجام شود. Decoder فقط مقدار خام و واحد/نمایش Protocol را استخراج می‌کند.

Business Logic نباید وابسته به Unit یا Format داخلی Device باشد.

---

# 19. Type Compatibility

اگر Device یک مفهوم را یک بار:

```text
1
```

و بار دیگر:

```text
true
```

ارسال کند، در صورتی که مفهوم واقعی Boolean باشد، Normalization باید آن را به Type استاندارد تبدیل کند.

هدف:

```text
Different Device Formats
        ↓
Same SANA Meaning
```

است.

---

# 20. Unknown Attributes

Attribute جدید و ناشناخته لزوماً باعث Reject کل Telemetry نمی‌شود.

اگر:

* ساختار معتبر باشد،
* حجم مجاز باشد،
* Type مجاز باشد،
* محدودیت‌های امنیتی رعایت شود،

می‌تواند طبق Policy پذیرفته شود.

Unknown بودن به‌تنهایی دلیل Reject نیست.

---

# 21. Protocol Independence

Business Logic نباید بداند که یک Attribute از کدام Firmware یا Protocol آمده است.

Business Logic باید با مفهوم SANA کار کند:

```text
fuel_level
temperature
ignition
...
```

و نه:

```text
teltonika_flag_17
gt06_bit_4
protocol_x_value_83
```

Protocol-specific Details در Layer مربوط به Protocol باقی می‌مانند.

---

# 22. Raw Packet و Attributes

Attributes جایگزین Raw Packet نیست.

```text
Raw Packet
→ داده واقعی دریافتی

Attributes
→ داده Normalize‌شده و قابل استفاده داخلی
```

اگر اطلاعات خام Protocol برای Debug لازم باشد، مرجع اصلی آن Raw Packet است.

---

# 23. Attribute Source

مالکیت داده اولیه با Source متفاوت است.

مثلاً:

```text
Device / Sensor
        ↓
64%
        ↓
SANA Normalization
        ↓
fuel_level = 38.4 L
```

داده اولیه متعلق به Device/Sensor است، ولی مقدار Normalize‌شده بخشی از قرارداد داخلی SANA است.

این همان الگویی است که برای:

```text
engine_hours
fuel_level
```

نیز اعمال می‌شود.

---

# 24. اصل نهایی Attributes

Attributes باید:

```text
Flexible
Typed
Validated
Namespaced
Secure
Queryable when necessary
Protocol-independent after normalization
```

باشند.

اما نباید تبدیل شوند به:

```text
Unstructured Database
Business Logic Storage
Permanent Dumping Ground
Replacement for Schema Design
```

---

# 25. قرارداد نهایی

```text
Attributes
Type: JSONB
Structure: Nested / Namespaced
Naming: lowercase snake_case
Types:
  string
  number
  boolean
  null
  object
  array

Validation:
  type
  structure
  size
  depth
  key count
  naming
  semantic
  security

Indexing:
  No generic index by default
  Targeted indexes only when justified

Lifecycle:
  ACTIVE
  DEPRECATED
  PROMOTED
```

---

# 26. اصل معماری نهایی

> **Attributes محل انعطاف‌پذیری SANA است، نه محل فرار از طراحی Schema.**

هر داده‌ای که به یک مفهوم عمومی، مهم، پرتکرار و پایدار تبدیل شود، باید از Attributes خارج و به ساختار مناسب SANA منتقل شود.

در نتیجه:

```text
Device
   ↓
Protocol Decoder
   ↓
Normalization
   ↓
Standard Fields + Attributes
   ↓
Processing
   ↓
Current State / Location History / Event
   ↓
Trip / Geofence / Alert / Reports
```

**بخش Attributes از نظر معماری نهایی شد.**


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Location History

## 1. هدف

`LocationHistory` تاریخچه مکانی پردازش‌شده و Normalize‌شده Device را نگهداری می‌کند.

LocationHistory:

* Raw Packet نیست.
* Full Normalized Telemetry نیست.
* CurrentState نیست.
* Event نیست.
* Trip نیست.

هدف آن پاسخ به پرسش‌هایی مانند:

* Device کجا بوده؟
* در چه زمانی آنجا بوده؟
* با چه سرعتی حرکت می‌کرده؟
* جهت حرکت چه بوده؟
* GPS معتبر بوده یا خیر؟
* وضعیت Motion و Ignition چه بوده؟
* مسیر تاریخی Device چگونه بوده؟

است.

---

# 2. مالکیت History

LocationHistory مستقیماً متعلق به `Device` است.

```text
Device
   ↓
LocationHistory
```

نه:

```text
Vehicle
   ↓
LocationHistory
```

زیرا Device ممکن است بین Vehicleهای مختلف جابه‌جا شود.

در گزارش Vehicle، Backend در صورت نیاز تاریخچه Deviceهایی را که در بازه زمانی مربوط به Vehicle بوده‌اند، ترکیب می‌کند.

---

# 3. Location Point و State Event

LocationHistory ماهیت **Point-oriented** دارد.

هر رکورد LocationHistory یک نقطه تاریخی است.

برای وضعیت‌های دارای بازه زمانی مانند:

```text
MOTION_STOPPED
GPS_FIX_LOST
OVERSPEED
```

از:

```text
Event(mode=STATE)
```

استفاده می‌شود.

مدل جداگانه‌ای مانند `DeviceStateInterval` ایجاد نمی‌شود.

بنابراین:

```text
LocationHistory
→ Point History

Event
→ State/Interval History
```

---

# 4. Smart Sampling

هر Telemetry الزاماً یک LocationHistory ایجاد نمی‌کند.

LocationHistory در شرایط معنادار ایجاد می‌شود، مانند:

* اولین Location معتبر
* GPS Fix Restore
* تغییر معنادار موقعیت
* تغییر Motion
* تغییر Ignition
* تغییر معنادار Speed
* تغییر معنادار Heading
* عبور از Maximum Time Gap هنگام حرکت
* مرزهای مهم Event

Thresholdها قابل تنظیم هستند.

مفاهیم تنظیماتی:

```text
location_min_distance
location_max_interval
speed_change_threshold
heading_change_threshold
stationary_interval
accuracy_threshold
```

مقادیر نهایی این Thresholdها پس از مشاهده داده واقعی تعیین می‌شوند.

---

# 5. حالت توقف

در زمان توقف پایدار، LocationHistory به‌صورت دوره‌ای برای همان مختصات ایجاد نمی‌شود.

مثلاً:

```text
08:25 → LocationHistory Point

08:25 → 11:15
MOTION_STOPPED Event

11:15 → LocationHistory Point
```

GPS Drift کوچک در زمان توقف نباید باعث تولید بی‌رویه Point شود.

---

# 6. GPS Fix

اگر:

```text
gps_valid = false
```

باشد:

* مختصات جدید ذخیره نمی‌شود.
* مختصات قبلی در رکورد جدید کپی نمی‌شود.
* `geom` نیز `NULL` خواهد بود.
* Event مربوط به `GPS_FIX_LOST` می‌تواند ایجاد شود.

در زمان بازگشت GPS:

```text
GPS_FIX_LOST
      ↓
First Valid Location
      ↓
LocationHistory Boundary Point
```

اولین Location معتبر بعد از Recovery حتی اگر تغییر مکانی کمی داشته باشد، یک Boundary محسوب می‌شود.

---

# 7. GPS No-Fix با Offline متفاوت است

این دو مفهوم کاملاً مستقل هستند:

```text
GPS No Fix
≠
Device Offline
```

ممکن است Device آنلاین باشد و Packet ارسال کند ولی GPS Fix نداشته باشد.

Offline فقط بر اساس عدم دریافت Packet و `offline_timeout` تشخیص داده می‌شود.

---

# 8. GPS Drift و Accuracy

تغییر مختصات به‌تنهایی برای تشخیص حرکت واقعی کافی نیست.

Telemetry Processing می‌تواند از ترکیب:

```text
Distance
Accuracy
Speed
Motion
Ignition
Heading
Temporal Sequence
```

استفاده کند.

اگر Accuracy ضعیف باشد، Location الزاماً Invalid نیست، اما Confidence پایین‌تر خواهد بود.

---

# 9. Accuracy = NULL

سه وضعیت مفهومی داریم:

```text
gps_valid = false
→ Location Invalid

gps_valid = true
accuracy = NULL
→ Location Valid / Quality Unknown

gps_valid = true
accuracy != NULL
→ Location Valid / Quality Known
```

نباید Accuracy ساختگی تولید شود.

---

# 10. Out-of-Order Telemetry

ترتیب تاریخی اصلی:

```text
device_time
```

است.

`server_received_at` فقط زمان دریافت توسط Server است.

Packetهای Late و Out-of-Order پذیرفته می‌شوند.

آنها می‌توانند History گذشته را تکمیل کنند، ولی نباید:

```text
CurrentState
```

را به گذشته Rollback کنند.

برای Processing از مفهوم:

```text
Processing Window / Watermark
```

استفاده می‌شود.

---

# 11. Duplicate و Idempotency

GPS Ingestion و Processing باید Idempotent باشند.

اگر Protocol Sequence/Packet ID داشته باشد:

```text
Device + Protocol + Sequence
```

برای تشخیص Duplicate استفاده می‌شود.

اگر نداشته باشد، Fingerprint مناسب از Packet/Telemetry ایجاد می‌شود.

Duplicate نباید باعث ایجاد مجدد:

* LocationHistory
* Event
* Trip Update
* Alert
* Notification

شود.

ACK در صورت نیاز Protocol همچنان می‌تواند برای Duplicate ارسال شود.

---

# 12. Processing Pipeline

ترتیب اصلی:

```text
Raw Packet
    ↓
Decode
    ↓
Normalize
    ↓
Validate
    ↓
Deduplicate
    ↓
Historical Ordering
    ↓
DB Transaction
 ├── LocationHistory (if needed)
 ├── Event (if needed)
 └── CurrentState (only if newer)
    ↓
COMMIT
    ↓
Consumers
 ├── WebSocket
 ├── Trip
 ├── Geofence
 └── Alert
      ↓
 Notification
```

Side Effectهای خارجی بعد از Commit انجام می‌شوند.

---

# 13. CurrentState و LocationHistory

این دو Entity مستقل هستند.

```text
CurrentState
→ Latest Snapshot

LocationHistory
→ Historical Points
```

هر Telemetry می‌تواند CurrentState را به‌روزرسانی کند، ولی الزاماً LocationHistory ایجاد نمی‌کند.

---

# 14. مدل دقیق LocationHistory

```text
LocationHistory
├── id
├── device
├── device_time
├── server_received_at
├── latitude
├── longitude
├── geom
├── gps_valid
├── accuracy
├── speed
├── heading
├── altitude
├── motion
├── ignition
├── odometer
├── engine_hours
├── fuel_level
└── attributes
```

---

# 15. `id`

```text
Type: BIGINT
Primary Key
Django: BigAutoField
```

به دلیل حجم بالقوه زیاد LocationHistory، استفاده از BIGINT مناسب‌تر است.

---

# 16. `device`

```text
Type: ForeignKey(Device)
Nullable: No
On Delete: PROTECT
```

History با حذف Device نباید از بین برود.

---

# 17. `device_time`

```text
Type: DateTime
Nullable: No
Timezone: UTC
```

زمان گزارش‌شده توسط Device و معیار اصلی ترتیب تاریخی است.

---

# 18. `server_received_at`

```text
Type: DateTime
Nullable: No
Timezone: UTC
```

زمان دریافت Packet توسط SANA است.

برای:

* Network Latency
* Debug
* Late Packet
* Ingestion Analysis

استفاده می‌شود.

---

# 19. Latitude / Longitude

```text
latitude
Type: Decimal
Nullable: Yes
max_digits = 9
decimal_places = 6
```

```text
longitude
Type: Decimal
Nullable: Yes
max_digits = 9
decimal_places = 6
```

محدوده:

```text
-90 <= latitude <= 90
-180 <= longitude <= 180
```

---

# 20. `geom`

```text
Type: geometry(Point, 4326)
Nullable: Yes
```

`geom` از:

```text
latitude
longitude
```

ساخته می‌شود.

در PostGIS:

```text
POINT(longitude latitude)
```

است.

`latitude` و `longitude` Source of Truth هستند و `geom` نمایش Spatial همان مختصات است.

اگر GPS معتبر نباشد:

```text
geom = NULL
```

خواهد بود.

`geom` از ابتدا ذخیره می‌شود.

GiST Index فعلاً فقط در صورت نیاز واقعی به Spatial Query روی History ایجاد می‌شود.

---

# 21. `gps_valid`

```text
Type: Boolean
Nullable: No
```

وضعیت معتبر بودن GPS Fix را مشخص می‌کند.

---

# 22. `accuracy`

```text
Type: Decimal
Unit: meter
Nullable: Yes
```

مثلاً:

```text
accuracy = 7.4
```

و:

```text
accuracy = NULL
```

یعنی کیفیت Location مشخص نیست، نه اینکه الزاماً Location نامعتبر باشد.

---

# 23. `speed`

```text
Type: Decimal
Unit: km/h
Nullable: Yes
```

```text
0
→ Speed واقعی صفر

NULL
→ Speed در دسترس نیست
```

Speed مستقیماً معادل Motion نیست.

---

# 24. `heading`

```text
Type: Decimal
Unit: degree
Nullable: Yes
```

محدوده:

```text
0 <= heading < 360
```

---

# 25. `altitude`

```text
Type: Decimal
Unit: meter
Nullable: Yes
```

---

# 26. `motion`

```text
Type: Choice / Enum
Nullable: Yes
```

مقادیر:

```text
MOVING
STOPPED
UNKNOWN
```

Boolean نیست، زیرا Unknown باید قابل تشخیص باشد.

---

# 27. `ignition`

```text
Type: Boolean
Nullable: Yes
```

سه وضعیت:

```text
true
false
NULL
```

معادل:

```text
ON
OFF
UNKNOWN
```

---

# 28. `odometer`

```text
Type: Decimal
Unit: km
Nullable: Yes
```

این مقدار:

```text
Device-reported Odometer
```

است و با Distance محاسبه‌شده SANA متفاوت است.

---

# 29. `engine_hours`

```text
Type: Decimal
Unit: hour
Nullable: Yes
Source: Device
```

مقدار Device ذخیره می‌شود.

Engine Hours محاسبه‌شده SANA مفهوم جداگانه‌ای خواهد داشت.

---

# 30. `fuel_level`

```text
Type: Decimal
Unit: liter
Nullable: Yes
```

فقط Fuel Level Normalize‌شده معتبر ذخیره می‌شود.

اگر Device درصد ارسال کند، تبدیل به لیتر فقط در صورت وجود:

```text
Vehicle.tank_capacity
```

معتبر انجام می‌شود.

---

# 31. `attributes`

```text
Type: JSONB
Nullable: No
Default: {}
```

Attributes فقط شامل داده‌های انتخاب‌شده طبق History Policy هستند.

Full Telemetry Attributes، Raw Packet، Protocol Data و داده‌های فنی غیرضروری به‌صورت پیش‌فرض وارد LocationHistory نمی‌شوند.

Historical Attributes Snapshot هستند و بعداً با تغییر CurrentState تغییر نمی‌کنند.

---

# 32. Attribute Policy

به‌صورت پیش‌فرض:

```text
protocol
→ excluded

device
→ excluded

cell
→ excluded
```

و مواردی مانند:

```text
ble
io
sensor
custom
```

فقط در صورت نیاز History وارد می‌شوند.

Standard Fields در Attributes تکرار نمی‌شوند.

---

# 33. Constraints

Constraintهای ساختاری:

```text
-90 <= latitude <= 90
-180 <= longitude <= 180
speed >= 0
0 <= heading < 360
accuracy >= 0
odometer >= 0
engine_hours >= 0
fuel_level >= 0
```

این Constraintها فقط Validity فیزیکی/ساختاری را بررسی می‌کنند.

Reset، Rollback و Rollover در Telemetry Processing بررسی می‌شوند.

---

# 34. Partitioning

LocationHistory جدول High-Volume است.

از ابتدا:

```text
PARTITION BY RANGE(device_time)
```

استفاده می‌شود.

Partition پیشنهادی MVP:

```text
location_history_YYYY_MM
```

یعنی Partition ماهانه.

Partition بر اساس Device ایجاد نمی‌شود.

---

# 35. Index اصلی

Index اصلی:

```text
(device_id, device_time)
```

است.

برای Queryهایی مانند:

```text
Device X
From T1
To T2
```

استفاده می‌شود.

Indexهای اضافی روی:

```text
speed
heading
fuel_level
...
```

به‌صورت پیش‌فرض ایجاد نمی‌شوند.

---

# 36. Primary Key و Timestamp

روی:

```text
(device, device_time)
```

Unique Constraint قرار نمی‌دهیم.

ممکن است چند Packet مختلف دارای Timestamp یکسان باشند.

Idempotency با:

```text
Sequence / Packet ID / Fingerprint
```

مدیریت می‌شود.

---

# 37. Retention

LocationHistory داده Long-Term است، اما الزاماً Forever نیست.

Retention:

```text
Configurable
```

خواهد بود.

عدد نهایی فعلاً تعیین نمی‌شود.

مبنای Retention:

```text
device_time
```

است.

---

# 38. حذف History

به دلیل Partitioning، حذف داده منقضی‌شده با:

```text
DROP PARTITION
```

انجام خواهد شد، نه DELETE میلیون‌ها رکورد.

این کار:

* سریع‌تر است.
* WAL کمتری ایجاد می‌کند.
* Bloat کمتری دارد.
* Maintenance ساده‌تری دارد.

---

# 39. Raw Packet در برابر LocationHistory

```text
Raw Packet
→ Short Retention

LocationHistory
→ Long Retention
```

Retention این دو مستقل است.

فعلاً Archive Database جداگانه ایجاد نمی‌شود.

---

# 40. Trip

Trip کپی LocationHistory نیست.

Trip یک نتیجه پردازش‌شده است که می‌تواند از:

```text
LocationHistory
+
Event
```

استفاده کند.

Trip می‌تواند Snapshotهایی مانند:

```text
start_location
end_location
start_odometer
end_odometer
start_engine_hours
end_engine_hours
```

را نگهداری کند.

ولی تمام Location Points را داخل Trip کپی نمی‌کند.

---

# 41. Playback

Playback مستقیماً از LocationHistory استفاده می‌کند.

```text
User
 ↓
API
 ↓
LocationHistory
 ↓
Ordered Points
 ↓
Frontend Playback
```

ترتیب:

```text
device_time ASC
```

است.

Playback به Trip وابسته نیست.

---

# 42. Polyline

Polyline به‌عنوان Source of Truth ذخیره نمی‌شود.

ساختار اصلی:

```text
LocationHistory
→ Point
Point
Point
Point
```

و در صورت نیاز:

```text
Points
 ↓
Polyline
```

در لایه مناسب تولید می‌شود.

---

# 43. Map و Downsampling

Map نباید برای بازه‌های بزرگ تمام Location Pointها را بدون محدودیت دریافت کند.

API در آینده می‌تواند:

```text
Downsampling
Simplification
```

را برای Presentation انجام دهد.

این عملیات نباید LocationHistory اصلی را تغییر دهد.

---

# 44. Query استاندارد

Query اصلی:

```text
device
+
from
+
to
```

است.

مثلاً:

```text
Device = 125
From = T1
To = T2
```

Backend زمان را به UTC تبدیل می‌کند.

---

# 45. Ordering

Ordering تاریخی:

```text
device_time ASC
```

است.

برای Tie-break در صورت Timestamp یکسان:

```text
id
```

نیز می‌تواند استفاده شود.

بنابراین:

```text
ORDER BY device_time ASC, id ASC
```

قابل استفاده است.

---

# 46. Full History Query

API نباید بدون محدوده زمانی اجازه دریافت کل تاریخچه را بدهد.

Query باید دارای:

```text
from
to
```

باشد.

همچنین Maximum Query Range باید قابل تنظیم باشد.

عدد نهایی فعلاً تعیین نمی‌شود.

---

# 47. Pagination

برای History حجیم، Pagination استفاده می‌شود.

ترجیح معماری:

```text
Cursor / Keyset Pagination
```

به‌جای Offset Pagination.

Cursor می‌تواند بر اساس:

```text
device_time + id
```

باشد.

---

# 48. Spatial Query

در صورت نیاز به Query مکانی:

```text
geom
+
PostGIS
```

استفاده می‌شود.

نمونه:

```text
LocationHistory
→ داخل محدوده جغرافیایی
```

یا:

```text
Nearest Location
```

Spatial Query از Query معمول Device/Time جداست.

---

# 49. Permission

Permission قبل از Query اعمال می‌شود.

```text
User
 ↓
Permission
 ↓
Accessible Devices
 ↓
LocationHistory
```

کاربر نباید بتواند فقط با تغییر `device_id` به History Device غیرمجاز دسترسی پیدا کند.

---

# 50. Vehicle History

اگر کاربر History یک Vehicle را بخواهد:

```text
Vehicle
 ↓
Temporal Device Assignment
 ↓
Relevant Devices
 ↓
LocationHistory
 ↓
Merge by device_time
```

انجام می‌شود.

LocationHistory همچنان متعلق به Device باقی می‌ماند.

---

# 51. Timezone

Storage:

```text
UTC
```

API:

```text
UTC
```

Presentation:

```text
User Timezone
```

تبدیل می‌شود.

Timestamp اصلی هرگز با تغییر Timezone تغییر نمی‌کند.

---

# 52. API Presentation

API مقدار استاندارد را ارائه می‌کند.

مثلاً:

```json
{
  "latitude": 35.7219,
  "longitude": 51.3347,
  "speed": 72.5,
  "fuel_level": 38.4
}
```

Frontend مسئول نمایش:

```text
72.5 km/h
38.4 L
```

است.

API نباید مقدار مخصوص UI تولید کند.

---

# 53. معماری نهایی Location History

```text
GPS Device
    ↓
Raw Packet
    ↓
Decode
    ↓
Normalize
    ↓
Validate
    ↓
Deduplicate
    ↓
Historical Ordering
    ↓
Location Decision Engine
    │
    ├── STORE
    │      ↓
    │  LocationHistory
    │
    └── SKIP

LocationHistory
    │
    ├── Playback
    ├── Trip
    ├── Reports
    ├── Map History
    └── Spatial Analysis

Telemetry
    ↓
Event Engine
    ↓
State / Point Events
```

---

# 54. اصل نهایی

> **LocationHistory منبع حقیقت تاریخی مکانی پردازش‌شده Device است؛ CurrentState برای وضعیت فعلی است، Event برای رخدادها، Trip برای نتیجه پردازش سفر و Playback/Reports مصرف‌کننده History هستند.**

بنابراین:

```text
CurrentState
≠ LocationHistory

LocationHistory
≠ Event

LocationHistory
≠ Trip

LocationHistory
≠ Raw Packet
```

این تفکیک باید در:

* GPS Service
* Backend
* Database
* API
* Frontend

حفظ شود.

---

# وضعیت نهایی بخش Location History

تمام تصمیمات اصلی این بخش نهایی شدند:

```text
[✓] Nature of LocationHistory
[✓] Device Ownership
[✓] Point vs State
[✓] Smart Sampling
[✓] Stationary Handling
[✓] GPS Drift
[✓] Accuracy
[✓] GPS Fix Lost/Restored
[✓] Out-of-Order
[✓] Duplicate / Idempotency
[✓] Processing Transaction
[✓] CurrentState Boundary
[✓] CurrentState Freshness
[✓] CurrentState Attributes
[✓] Concurrency
[✓] LocationHistory Rule Set
[✓] History Attributes
[✓] Partitioning
[✓] geom
[✓] Retention
[✓] Database Model
[✓] Trip Boundary
[✓] Playback
[✓] Query / API
[✓] Pagination
[✓] Permission
[✓] Vehicle History
[✓] Timezone
```

**بخش Location History از نظر معماری بسته شد.**

مرحله بعد دیگر تصمیم‌گیری مفهومی این بخش نیست؛ می‌توانیم بر اساس همین قرارداد، وارد بخش بعدی معماری SANA شویم یا هنگام شروع پیاده‌سازی، همین تصمیمات را به مدل Django/PostgreSQL و Processing Pipeline تبدیل کنیم.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Trip

## وضعیت

**Trip Architecture — CLOSED**

این سند جمع‌بندی نهایی تصمیمات معماری Trip در SANA است.

---

# 1. تعریف Trip

`Trip` یک دوره معنادار و تأییدشده از حرکت Device است که دارای زمان شروع، پایان و Metrics مربوط به حرکت است.

Trip:

* جایگزین Location History نیست.
* کپی Telemetry نیست.
* Event نیست.
* Aggregate/Summary حاصل از داده‌های تاریخی است.

منبع اصلی Trip:

```text
LocationHistory
+
Event
+
Normalized Telemetry
+
Device Assignment History
        ↓
Trip Engine
        ↓
Trip
```

---

# 2. مالکیت Trip

Trip مستقیماً متعلق به:

```text
Device
```

است.

نه:

```text
Vehicle
Driver
Customer
Organization
```

دلیل:

Device هویت واقعی منبع GPS را حفظ می‌کند.

اگر Device تعویض شود، Tripهای قبلی همچنان متعلق به Device قبلی باقی می‌مانند.

نمایش Tripهای یک Vehicle از طریق تاریخچه زمانی:

```text
Device ↔ Vehicle Assignment
```

انجام می‌شود.

---

# 3. Current Trip و Final Trip

برای Current Trip و Final Trip دو جدول جدا ایجاد نمی‌شود.

هر Trip یک Entity واحد با Lifecycle مشخص است:

```text
ACTIVE
   ↓
COMPLETED
```

در زمان Active:

```text
ended_at = NULL
```

پس از پایان:

```text
status = COMPLETED
ended_at = ...
```

در MVP وضعیت‌های:

```text
CANCELLED
INVALID
RECALCULATING
FAILED
```

وجود ندارند.

---

# 4. Trip Detection

Trip فقط زمانی ایجاد می‌شود که **حرکت واقعی و معنادار** تأیید شود.

هیچ‌کدام به‌تنهایی برای ایجاد Trip کافی نیستند:

```text
Ignition ON
Speed > 0
Engine Hours Change
یک Speed Spike
```

Trip Engine بر اساس اطلاعات موجود تصمیم می‌گیرد:

```text
Speed
Motion
Location Change
Ignition
Time
Distance
Accuracy
```

اگر بعضی اطلاعات وجود نداشته باشند، Engine می‌تواند از اطلاعات موجود استفاده کند.

اما اگر فقط `ignition` وجود داشته باشد، در MVP از آن به‌تنهایی Trip ساخته نمی‌شود.

---

# 5. Trip Detection State Machine

Trip Engine از Stateهای داخلی استفاده می‌کند:

```text
NO_TRIP
    ↓
PENDING_START
    ↓
ACTIVE
    ↓
PENDING_END
    ↓
COMPLETED
```

`PENDING_START` و `PENDING_END` برای Debounce و تأیید حرکت/توقف هستند و الزاماً وضعیت دائمی Database نیستند.

---

# 6. Trip Start

شروع Trip زمانی ثبت می‌شود که حرکت واقعی تأیید شود.

مثلاً:

```text
Movement Detected
       ↓
Debounce / Minimum Condition
       ↓
Trip Start Confirmed
```

Ignition ON به‌تنهایی Trip Start نیست.

Speed Spike کوتاه نیز به‌تنهایی Trip Start نیست.

Thresholdها و مدت‌های لازم باید قابل تنظیم باشند.

---

# 7. Trip End

Trip زمانی پایان می‌یابد که پایان واقعی حرکت تأیید شود.

مثلاً:

```text
Movement
   ↓
Stop
   ↓
Stop Duration > Threshold
   ↓
Trip End
```

موارد زیر به‌تنهایی Trip را تمام نمی‌کنند:

```text
GPS Loss
Device Offline
TCP Disconnect
Device Reboot
Ignition OFF
```

مگر اینکه داده‌های موجود در کنار آن‌ها پایان واقعی حرکت را تأیید کنند.

---

# 8. Short Stop و Long Stop

توقف کوتاه داخل Trip باقی می‌ماند.

توقف طولانی می‌تواند باعث پایان Trip شود.

بنابراین:

```text
Short Stop
→ داخل Trip

Long Stop
→ احتمال پایان Trip
```

Thresholdها Configurable هستند.

---

# 9. Stop و Trip

`MOTION_STOPPED` یک Event مستقل است.

```text
MOTION_STOPPED ≠ TRIP_ENDED
```

یک Stop می‌تواند:

* داخل Trip اتفاق بیفتد.
* باعث پایان Trip شود.

Stopها مستقیماً داخل Trip به شکل:

```text
stops[]
```

ذخیره نمی‌شوند.

Stopها از Eventهای `MOTION_STOPPED` در محدوده زمانی Trip قابل استخراج هستند.

---

# 10. Trip و Network Lifecycle

Network Lifecycle مستقل از Movement Lifecycle است.

بنابراین:

```text
TCP Disconnect ≠ Trip End
TCP Reconnect ≠ Trip Start
Device Reboot ≠ Trip End
DEVICE_OFFLINE ≠ Trip End
```

اگر Device پس از Reconnect همچنان در حال حرکت باشد، Trip همان Trip قبلی باقی می‌ماند.

Network Events مستقل هستند:

```text
DEVICE_OFFLINE
DEVICE_ONLINE
```

---

# 11. Offline و Unknown Duration

اگر در وسط Trip برای مدتی Telemetry دریافت نشود:

```text
08:10 → Packet
08:10 ... 08:30 → No Data
08:30 → Packet
```

نباید فرض کنیم خودرو در این مدت:

```text
Moving
```

یا:

```text
Stopped
```

بوده است.

در صورت نیاز این بازه:

```text
unknown_duration
```

محاسبه می‌شود.

همچنین فاصله طی‌شده در این Gap نباید به‌صورت ساختگی تخمین زده شود.

---

# 12. Trip و Device Replacement

تعویض Device یک مرز Trip است.

مثلاً:

```text
Device A
   ↓
Device B
```

Trip مربوط به Device A باید بسته شود.

اگر Device B حرکت کند، Trip جدید متعلق به Device B ایجاد می‌شود.

Trip نباید از مرز Device Replacement عبور کند.

---

# 13. Trip و Vehicle Assignment

تغییر Assignment بین Device و Vehicle نیز مرز Trip است.

این تغییر:

```text
Business Boundary
```

است، نه الزاماً Event فیزیکی.

Trip مربوط به Assignment قبلی از Assignment جدید عبور نمی‌کند.

Vehicle Attribution با استفاده از تاریخچه زمانی Assignment انجام می‌شود.

---

# 14. Trip Model

مدل مفهومی نهایی MVP:

```text
Trip
├── id
├── number
├── device
├── status
│
├── started_at
├── ended_at
│
├── start_geom
├── end_geom
│
├── start_odometer
├── end_odometer
│
├── start_engine_hours
├── end_engine_hours
│
├── start_fuel_level
├── end_fuel_level
│
├── distance
├── max_speed
│
├── moving_duration
├── stopped_duration
├── unknown_duration
│
├── start_event
├── end_event
│
└── attributes
```

---

# 15. Trip ID

شناسه فنی:

```text
Trip.id
Type: BIGINT
Primary Key
```

UUID در MVP لازم نیست.

---

# 16. Trip Number

یک شماره نمایشی مستقل نیز داریم:

```text
Trip.number
```

ویژگی‌ها:

```text
Global
Unique
Immutable
Human-readable
```

شماره به Device یا Vehicle وابسته نیست.

Gap در Sequence مجاز است.

مثلاً:

```text
Trip #100
Trip #101
Trip #103
```

کاملاً معتبر است.

`Trip.id` و `Trip.number` دو مفهوم مستقل هستند.

---

# 17. Start و End Time

Trip دارای:

```text
started_at
ended_at
```

است.

این زمان‌ها بیانگر Boundary منطقی Trip هستند، نه الزاماً زمان اولین/آخرین Packet.

ممکن است Detection با تأخیر انجام شود و Trip Engine با استفاده از Location History، Boundary واقعی را Backtrack کند.

---

# 18. Start و End Location

مختصات شروع و پایان از:

```text
LocationHistory
```

انتخاب می‌شوند.

نه از CurrentState.

مدل:

```text
start_geom
end_geom
```

با:

```text
PostGIS Point
SRID 4326
```

در نظر گرفته می‌شود.

اگر Location معتبر در محدوده جستجوی مجاز وجود نداشته باشد:

```text
NULL
```

ذخیره می‌شود.

هیچ‌گاه مختصات قدیمی به‌عنوان Location جدید استفاده نمی‌شود.

Address در Trip ذخیره نمی‌شود.

Coordinate منبع اصلی حقیقت است.

---

# 19. Distance

```text
Trip.distance
```

مسافت محاسبه‌شده توسط SANA است.

منبع:

```text
LocationHistory
```

نه:

```text
Odometer
Polyline
Duration × Average Speed
```

محاسبه Distance باید:

* GPS Drift را فیلتر کند.
* Accuracy را در نظر بگیرد.
* Motion و Speed را در نظر بگیرد.
* ترتیب زمانی را رعایت کند.
* Segmentهای غیرممکن را حذف کند.
* Duplicate و Out-of-order را مدیریت کند.

Gap ناشی از GPS Loss نباید به‌صورت مصنوعی محاسبه شود.

---

# 20. Odometer

Odometer یک مقدار Device-reported است.

بنابراین:

```text
start_odometer
end_odometer
```

Snapshotهای Telemetry هستند.

آنها با:

```text
Trip.distance
```

یکی نیستند.

ممکن است اختلاف بین Odometer Delta و SANA Distance وجود داشته باشد.

---

# 21. Engine Hours

Snapshotهای:

```text
start_engine_hours
end_engine_hours
```

از Engine Hours گزارش‌شده توسط Device می‌آیند.

SANA نباید مقدار محاسباتی خودش را روی این Snapshotها بنویسد.

Reset/Rollover/Rollback باید قبل از استفاده در Delta بررسی شود.

در صورت نامعتبر بودن Delta:

```text
NULL
```

مجاز است، ولی Snapshotهای واقعی حفظ می‌شوند.

---

# 22. Fuel

در MVP فقط Snapshotهای:

```text
start_fuel_level
end_fuel_level
```

ذخیره می‌شوند.

فعلاً:

```text
fuel_consumed
```

به‌عنوان مقدار قطعی Trip تولید نمی‌شود.

اختلاف Fuel Level الزاماً مصرف واقعی نیست و می‌تواند تحت تأثیر:

* Refueling
* Sensor Noise
* Calibration
* شرایط خودرو

باشد.

---

# 23. Max Speed

```text
Trip.max_speed
```

از Speed معتبر گزارش‌شده توسط Device می‌آید.

اگر Device Speed نداشته باشد:

```text
max_speed = NULL
```

در MVP سرعت جعلی از:

```text
Distance / Time
```

برای Max Speed تولید نمی‌شود.

Calculated Speed فقط می‌تواند در Processing برای Validation استفاده شود.

---

# 24. Duration

Duration اصلی از Timestampهای Trip محاسبه می‌شود:

```text
duration = ended_at - started_at
```

این مقدار Derived است.

سه Duration مهم داریم:

```text
moving_duration
stopped_duration
unknown_duration
```

و:

```text
duration
```

می‌تواند از Timestampها محاسبه شود.

---

# 25. Moving Duration

زمانی که حرکت با اطمینان تشخیص داده شده:

```text
moving_duration
```

است.

Unknown یا GPS Gap به‌عنوان Moving محاسبه نمی‌شود.

---

# 26. Stopped Duration

زمان Stopهای تأییدشده داخل Trip:

```text
stopped_duration
```

است.

`Stopped` با:

```text
Idle
```

یکی نیست.

---

# 27. Unknown Duration

زمانی که به دلیل:

* GPS Loss
* Offline
* Data Gap
* Unknown Motion

نتوانیم وضعیت واقعی را تعیین کنیم:

```text
unknown_duration
```

است.

نباید Unknown را به Moving یا Stopped تبدیل کنیم.

---

# 28. Derived Metrics

در MVP این موارد Derived هستند:

```text
duration
average_speed
moving_average_speed
stop_count
```

مثلاً:

```text
average_speed
= distance / duration
```

و:

```text
moving_average_speed
= distance / moving_duration
```

این مقادیر الزاماً Storage Field نیستند.

---

# 29. Trip Finalization

پس از پایان:

```text
ACTIVE
   ↓
COMPLETED
```

Trip Finalization انجام می‌شود.

در Finalization:

* End Boundary مشخص می‌شود.
* End Location تعیین می‌شود.
* End Odometer تعیین می‌شود.
* End Engine Hours تعیین می‌شود.
* End Fuel تعیین می‌شود.
* Distance نهایی می‌شود.
* Max Speed نهایی می‌شود.
* Durationها جمع‌بندی می‌شوند.

Finalization باید Transactional باشد.

---

# 30. Completed Trip

پس از:

```text
status = COMPLETED
```

Trip در پردازش عادی دیگر تغییر نمی‌کند.

Late Packet ممکن است همچنان در:

```text
LocationHistory
```

ذخیره شود.

اما Completed Trip به‌صورت خودکار Recalculate نمی‌شود.

---

# 31. Late Packet

Late Packet دور ریخته نمی‌شود.

اگر Packet از نظر تاریخی معتبر باشد:

```text
LocationHistory
```

می‌تواند آن را دریافت کند.

اما:

```text
CurrentState
```

نباید به عقب برگردد.

و:

```text
Completed Trip
```

نیز نباید خودکار تغییر کند.

---

# 32. Recalculation

در آینده ممکن است:

```text
Recalculation Engine
```

اضافه شود.

مثلاً:

```text
LocationHistory
+
Event
+
New Algorithm
      ↓
Recalculate Trip
```

اما:

* Recalculation UI
* Versioning کامل
* Job Management

در MVP وجود ندارند.

---

# 33. Trip API

Endpointهای مفهومی:

```text
GET /trips/
GET /trips/{id}/
GET /trips/{id}/route/
GET /trips/{id}/stops/
GET /trips/{id}/events/
```

### List

Summary سبک:

```text
id
number
status
started_at
ended_at
distance
max_speed
durations
```

### Detail

اطلاعات کامل Trip و Snapshotها.

---

# 34. Route API

Route جدا از Trip Detail ارائه می‌شود.

منبع:

```text
LocationHistory
```

است.

ممکن است API برای کاهش حجم:

* Downsample
* Simplify

انجام دهد.

اما LocationHistory تغییر نمی‌کند.

Polyline منبع حقیقت نیست.

---

# 35. Stops API

Stopها از:

```text
MOTION_STOPPED Events
```

به دست می‌آیند.

می‌توان Endpoint مستقل داشت:

```text
GET /trips/{id}/stops/
```

---

# 36. Events API

Eventهای مرتبط با Trip از طریق:

```text
GET /trips/{id}/events/
```

قابل دریافت هستند.

مثلاً:

```text
OVERSPEED
MOTION_STOPPED
IGNITION_ON
IGNITION_OFF
GEOFENCE_ENTER
...
```

---

# 37. Permission

Permission باید قبل از Query اعمال شود.

```text
User
 ↓
Permission
 ↓
Accessible Device / Vehicle
 ↓
Trip
```

مخفی کردن Trip در Frontend کافی نیست.

کاربر نباید Trip غیرمجاز را از API دریافت کند.

---

# 38. Vehicle Trip View

وقتی کاربر Tripهای Vehicle را می‌خواهد:

```text
Vehicle
 ↓
Historical Device Assignment
 ↓
Device
 ↓
Trips
```

تاریخچه Assignment باید رعایت شود.

Tripهای قبل از اتصال Device به Vehicle نباید retroactively به Vehicle نسبت داده شوند.

---

# 39. Timezone

Database:

```text
UTC
```

API:

```text
UTC
```

Presentation:

```text
User Timezone
```

Frontend مسئول تبدیل و نمایش زمان محلی است.

---

# 40. Pagination و Filtering

Trip List باید Pagination داشته باشد.

ترجیحاً:

```text
Cursor / Keyset Pagination
```

و نه OFFSETهای عمیق.

Filterهای اصلی:

```text
device
vehicle
from
to
status
```

Queryهای تاریخی باید Range محدود داشته باشند.

---

# 41. Attributes

`Trip.attributes` برای اطلاعات تکمیلی و مرتبط با محاسبه/تاریخچه Trip است.

نباید تبدیل به محل ذخیره:

```text
Full Telemetry
Raw Packet
Protocol Dump
LocationHistory
```

شود.

---

# 42. Trip و Event

Trip و Event مستقل هستند.

```text
Event
→ meaningful occurrence

Trip
→ movement aggregate
```

Trip می‌تواند به Eventهای Start و End Reference داشته باشد:

```text
start_event
end_event
```

ولی مالک Event نیست.

---

# 43. Trip و LocationHistory

رابطه:

```text
LocationHistory
      ↓
Trip Engine
      ↓
Trip
```

Trip فقط Summary را نگه می‌دارد.

Full Location History داخل Trip ذخیره نمی‌شود.

---

# 44. اصل Source of Truth

برای هر Metric:

```text
Start/End Snapshot
→ Normalized Device Telemetry

Distance
→ LocationHistory

Max Speed
→ Device Speed

Start/End Event
→ Event Engine

Vehicle Attribution
→ Device↔Vehicle Assignment History
```

این تفکیک باید حفظ شود.

---

# 45. MVP

در MVP پیاده‌سازی می‌شود:

* Trip Detection
* Active / Completed
* Start / End
* Distance
* Max Speed
* Moving Duration
* Stopped Duration
* Unknown Duration
* Start / End Location
* Start / End Odometer
* Start / End Engine Hours
* Start / End Fuel
* Trip Number
* Trip API
* Route API
* Stops API
* Events API
* Historical Vehicle Attribution

---

# 46. Future Scope

فعلاً پیاده‌سازی نمی‌شود:

* Trip Recalculation UI
* Trip Versioning
* Fuel Consumption Engine
* Driver Behavior Scoring
* AI Trip Classification
* Traffic-aware Analysis
* ETA
* Route Matching
* Map Matching
* Advanced Trip Anomaly Detection

معماری فعلی باید امکان اضافه شدن این قابلیت‌ها را در آینده حفظ کند.

---

# 47. اصل نهایی Trip

> **Trip یک Summary قابل اتکا از یک دوره حرکت واقعی Device است که از LocationHistory و Event ساخته می‌شود؛ نه جایگزین تاریخچه GPS و نه یک کپی از Telemetry.**

معماری نهایی:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
Normalized Telemetry
    ↓
Location History
    +
Event
    ↓
Trip Engine
    ↓
Trip Summary
    ↓
Reports / API / UI
```

**Trip Architecture در این مرحله نهایی و بسته است.**


============================================================================
============================================================================

# SANA GPS — طراحی نهایی CurrentState Model

## 1. هدف

`CurrentState` آخرین وضعیت قابل استفاده و سریع هر Device را برای عملیات Real-Time نگهداری می‌کند.

CurrentState یک **Read Model / Snapshot** است و برای موارد زیر استفاده می‌شود:

* Live Map
* Device Current View
* WebSocket
* API سریع
* نمایش آخرین وضعیت Device

CurrentState منبع تاریخچه نیست.

منابع اصلی تاریخی SANA عبارت‌اند از:

```text
LocationHistory
Event
Trip
```

---

# 2. مالکیت

CurrentState مستقیماً متعلق به Device است.

رابطه:

```text
Device
   │
   └── CurrentState
```

هر Device دقیقاً یک CurrentState دارد.

CurrentState به Vehicle متصل نیست.

اگر Device بین Vehicleها جابه‌جا شود:

```text
Device A
   ↓
Vehicle 1
```

و بعد:

```text
Device A
   ↓
Vehicle 2
```

CurrentState همان Device باقی می‌ماند.

---

# 3. رابطه One-to-One

برای هر Device دقیقاً یک رکورد CurrentState وجود دارد.

CurrentState در همان Transaction ایجاد Device ساخته می‌شود.

بنابراین:

```text
Device 125
    ↓
CurrentState 125
```

First Telemetry باعث ایجاد CurrentState جدید نمی‌شود؛ همان رکورد موجود Update می‌شود.

---

# 4. CurrentState مدل تاریخی نیست

CurrentState فقط Snapshot فعلی است.

مثلاً:

```text
10:00
speed = 40

10:01
speed = 60

10:02
speed = 80
```

CurrentState فقط وضعیت آخر را نگه می‌دارد:

```text
speed = 80
```

تاریخچه مقادیر قبلی در CurrentState نگهداری نمی‌شود.

تاریخچه از:

```text
LocationHistory
Event
```

به دست می‌آید.

---

# 5. مدل نهایی

مدل مفهومی نهایی:

```text
CurrentState
├── id
├── device
│
├── device_time
├── server_received_at
├── last_seen
├── updated_at
│
├── latitude
├── longitude
├── geom
├── gps_valid
├── accuracy
│
├── last_valid_latitude
├── last_valid_longitude
├── last_valid_geom
├── last_valid_device_time
├── last_valid_server_received_at
├── last_valid_accuracy
│
├── speed
├── heading
├── altitude
├── motion
├── ignition
├── satellites
│
├── battery_voltage
├── external_voltage
├── gsm_signal
│
├── odometer
├── engine_hours
├── fuel_level
│
└── attributes
```

`connection_state` در Database ذخیره نمی‌شود.

---

# 6. Identity Fields

## id

شناسه داخلی CurrentState.

```text
Type: BigAutoField / BIGINT
Nullable: No
Source: SANA
```

برای ارتباط داخلی Database استفاده می‌شود.

---

## device

```text
Type: OneToOne / ForeignKey with UNIQUE
Nullable: No
Source: SANA
```

هر CurrentState متعلق به یک Device است.

پیشنهاد Django:

```python
device = models.OneToOneField(
    Device,
    on_delete=models.PROTECT,
    related_name="current_state",
)
```

حذف فیزیکی Device نیز در طراحی Lifecycle مجاز نیست.

---

# 7. تعریف دقیق Valid Packet

در SANA، هر Packet دریافتی الزاماً یک Packet معتبر محسوب نمی‌شود.

برای اهداف CurrentState، `Valid Packet` یعنی:

> **Packetی که از یک Device شناخته‌شده و مجاز آمده، Protocol آن به‌درستی Decode شده، ساختار و داده‌های لازم آن از نظر فنی قابل پردازش است، Duplicate/Replay همان Packet تشخیص داده نشده، و حداقل یک Telemetry معتبر قابل استخراج از آن وجود دارد.**

بنابراین Valid بودن Packet به معنی کامل بودن تمام فیلدهای Telemetry نیست.

یک Packet می‌تواند معتبر باشد ولی فقط چند Field داشته باشد.

مثلاً:

```text
IMEI       ✓
Protocol   ✓
Packet     ✓
device     ✓

latitude   ✓
longitude  ✓

battery    NULL
fuel       NULL
gsm        NULL
```

این Packet همچنان Valid است.

---

# 8. شرایط Valid Packet

برای CurrentState، Packet باید تمام شروط پایه زیر را داشته باشد:

### 8.1 Device قابل شناسایی باشد

Packet باید بتواند به یک Device ثبت‌شده در SANA نسبت داده شود.

مثلاً:

```text
IMEI
   ↓
Device
```

اگر Device ناشناس باشد:

```text
Unknown Device
→ Invalid for CurrentState
```

و:

```text
last_seen
→ تغییر نمی‌کند
```

---

### 8.2 Device مجاز باشد

Device باید در وضعیت Lifecycleای باشد که دریافت Telemetry از آن مجاز است.

Deviceای که طبق سیاست سیستم دیگر نباید Telemetry آن پذیرفته شود، نباید Packet معتبر برای CurrentState تولید کند.

---

### 8.3 Protocol قابل تشخیص باشد

Packet باید توسط Protocol مناسب قابل Decode باشد.

مثلاً:

```text
TCP Packet
   ↓
Protocol Decoder
   ↓
Decoded Message
```

اگر Packet:

* Protocol ناشناخته
* ساختار غیرقابل Decode
* ناقص به‌گونه‌ای که Message قابل تشخیص نباشد
* یا دارای Format غیرمعتبر

باشد:

```text
Invalid Packet
```

است.

---

### 8.4 Packet از نظر فنی قابل Parse باشد

Decoder باید بتواند Message را بدون خطای ساختاری جدی استخراج کند.

مثلاً:

```text
length
checksum
message structure
field boundaries
encoding
```

باید طبق Protocol قابل قبول باشند.

اگر Packet در سطح Protocol خراب باشد:

```text
Packet
   ↓
Decode Failed
```

به CurrentState وارد نمی‌شود.

---

### 8.5 حداقل یک Telemetry قابل استخراج وجود داشته باشد

Packet معتبر باید حداقل یک Telemetry/Message قابل پردازش تولید کند.

اما تمام Standard Fields لازم نیست موجود باشند.

مثلاً این Packet می‌تواند معتبر باشد:

```text
device_time = 12:10:00
ignition    = true
```

حتی اگر:

```text
latitude = NULL
longitude = NULL
fuel = NULL
battery = NULL
```

باشد.

---

# 9. Valid Packet به معنی Valid بودن همه Fieldها نیست

این نکته بسیار مهم است.

دو سطح Validation داریم:

```text
Packet Validation
        ↓
Telemetry / Field Validation
```

ممکن است Packet معتبر باشد اما یک Field داخل آن نامعتبر باشد.

مثلاً:

```text
Packet = Valid

latitude = 35.7        ✓
longitude = 51.4       ✓
speed = 85             ✓
fuel = -900             ✗
battery = NULL          ✓
```

در این حالت نباید کل Packet را لزوماً Drop کنیم.

اگر ساختار Packet معتبر باشد، Field نامعتبر می‌تواند طبق قواعد Normalization کنار گذاشته شود:

```text
fuel = NULL
```

ولی سایر داده‌های معتبر استفاده شوند.

---

# 10. Invalid Packet

نمونه‌های Invalid Packet:

```text
Unknown Device
Malformed Packet
Unsupported Protocol
Invalid Protocol Structure
Failed Decode
Corrupted Message
Unauthenticated Message
```

این Packetها نباید:

```text
CurrentState
last_seen
updated_at
```

را تغییر دهند.

و نباید Event یا Location معتبر بر اساس آنها ایجاد شود.

---

# 11. Duplicate Packet

Packetی که قبلاً با همان هویت دریافت و پردازش شده است:

```text
Duplicate
```

محسوب می‌شود.

تشخیص Duplicate در اولویت با اطلاعات خود Protocol است:

```text
sequence_number
packet_id
message_id
counter
```

و در صورت نبود آن‌ها، از Fingerprint مناسب استفاده می‌شود.

`device + device_time` به‌تنهایی هویت Packet نیست.

---

# 12. اثر Duplicate

Duplicate نباید Side Effect جدید ایجاد کند:

```text
Duplicate Packet
    ├── CurrentState → No new update
    ├── LocationHistory → No duplicate record
    ├── Event → No duplicate event
    └── last_seen → No replay-based update
```

یعنی Replay کردن یک Packet قدیمی نباید باعث شود سیستم تصور کند Device دوباره در همان لحظه Telemetry جدید فرستاده است.

---

# 13. Valid Packet و last_seen

فقط Packetی که شرایط Valid Packet را داشته باشد می‌تواند `last_seen` را جلو ببرد.

بنابراین:

```text
Valid Packet
    ↓
last_seen = server_received_at
```

اما:

```text
Invalid Packet
    ↓
last_seen unchanged
```

و:

```text
Duplicate Packet
    ↓
last_seen unchanged
```

---

# 14. Valid Packet و CurrentState Snapshot

Valid بودن Packet به‌تنهایی به معنی Update شدن CurrentState نیست.

دو مرحله جدا داریم:

```text
Packet Validity
       ↓
آیا Packet اجازه اثرگذاری دارد؟
       ↓
Snapshot Ordering
       ↓
آیا از CurrentState جدیدتر است؟
```

مثلاً:

```text
CurrentState.device_time = 12:10
```

و:

```text
Valid Packet.device_time = 12:05
```

Packet معتبر است، اما:

```text
CurrentState Snapshot
→ Update نمی‌شود
```

در عین حال `last_seen` می‌تواند بر اساس زمان دریافت واقعی Packet جلو برود.

---

# 15. Future / Suspicious Device Time

Packet ممکن است از نظر Protocol معتبر باشد ولی `device_time` آن مشکوک باشد.

مثلاً:

```text
server_received_at = 12:00
device_time        = 18:00
```

در این حالت:

```text
Packet Validity
≠
Timestamp Trustworthiness
```

است.

یعنی باید بین:

```text
Packet Structure Validity
```

و:

```text
Temporal Validity
```

تفاوت بگذاریم.

اگر `device_time` خارج از محدوده قابل قبول باشد، Telemetry Processing می‌تواند آن را:

```text
Suspicious / Temporal Anomaly
```

علامت‌گذاری کند.

اما نباید بدون Rule مشخص، `server_received_at` را جایگزین `device_time` کند.

---

# 16. Valid Packet و Partial Telemetry

Packet معتبر می‌تواند Partial باشد.

مثلاً:

```text
device_time = 12:10
ignition = true
speed = 20
```

ولی:

```text
GPS = unavailable
fuel = unavailable
battery = unavailable
```

این Packet برای CurrentState معتبر است.

در این حالت:

```text
ignition → Update
speed    → Update
GPS      → طبق gps_valid
fuel     → طبق Explicit NULL / Absent
```

هر Field Policy مستقل خودش را دارد.

---

# 17. Valid Packet و GPS No-Fix

Packetی که:

```text
gps_valid = false
```

دارد همچنان می‌تواند کاملاً معتبر باشد.

مثلاً:

```text
Packet
✓ Device valid
✓ Protocol valid
✓ Decode valid
✓ Timestamp valid
✓ Telemetry valid

gps_valid = false
```

نتیجه:

```text
Valid Packet
+
GPS No-Fix
```

است.

بنابراین:

```text
GPS No-Fix
≠
Invalid Packet
```

و:

```text
GPS No-Fix
≠
Offline
```

---

# 18. Valid Packet و Server Receipt

`server_received_at` فقط برای Packetی ثبت می‌شود که Server واقعاً آن را دریافت کرده است.

این زمان نباید از:

```text
device_time
```

ساخته شود.

بنابراین:

```text
Packet arrives
       ↓
server_received_at = Server Clock NOW
```

و سپس:

```text
last_seen = server_received_at
```

در صورت معتبر بودن Packet.

---

# 19. Packet Validation Pipeline

تعریف عملی Pipeline:

```text
Raw Packet
    ↓
Identify Device
    ↓
Identify Protocol
    ↓
Protocol Decode
    ↓
Structural Validation
    ↓
Telemetry Extraction
    ↓
Field Normalization
    ↓
Field Validation
    ↓
Packet Validity
    ↓
Deduplication
    ↓
Temporal Ordering
    ↓
Database Transaction
```

نکته مهم:

`Protocol Decoder` مسئول استخراج و Normalize کردن است؛ تصمیمات تاریخی و CurrentState در مراحل بعدی انجام می‌شوند.

---

# 20. Valid Packet و Authentication

اگر در آینده روش‌های Authentication بیشتری اضافه شود، اعتبار Packet باید شامل آن نیز باشد.

مثلاً:

```text
IMEI
+
Session
+
Authentication
+
Protocol Validation
```

در صورت شکست Authentication:

```text
Packet
→ Invalid
```

و CurrentState نباید تغییر کند.

---

# 21. Valid Packet و Unknown Device

Packetی که IMEI آن در SANA ثبت نشده:

```text
Unknown IMEI
```

برای CurrentState معتبر نیست.

جریان:

```text
Packet
   ↓
IMEI
   ↓
Device Lookup
   ↓
NOT FOUND
   ↓
Reject
```

و:

```text
last_seen
→ تغییر نمی‌کند
```

---

# 22. Valid Packet و Connection

Valid Packet نشان‌دهنده این است که Server توانسته یک پیام معتبر از Device دریافت و پردازش کند.

بنابراین:

```text
Valid Packet
→ Device Seen
```

اما:

```text
Valid Packet
≠
GPS Fix
```

و:

```text
Valid Packet
≠
Vehicle Moving
```

و:

```text
Valid Packet
≠
Ignition ON
```

این مفاهیم مستقل هستند.

---

# 23. تعریف نهایی Valid Packet

تعریف قطعی SANA:

> **Valid Packet یک Packet دریافتی از Device شناخته‌شده و مجاز است که Protocol و ساختار آن به‌درستی قابل تشخیص و Decode باشد و حداقل یک Telemetry قابل پردازش از آن استخراج شود. Valid بودن Packet مستقل از کامل بودن Telemetry، داشتن GPS Fix، روشن بودن خودرو، جدید بودن `device_time` یا حرکت خودرو است.**

بنابراین:

```text
Valid Packet
├── Known Device
├── Allowed Device
├── Recognized Protocol
├── Valid Structure
├── Successful Decode
└── At least one Processable Telemetry
```

و این موارد **شرط Valid Packet نیستند**:

```text
GPS Fix
Vehicle Moving
Ignition ON
Complete Telemetry
Newest device_time
```

---

# 24. تفاوت Valid / New / Duplicate

این سه مفهوم باید کاملاً جدا باشند:

### Valid

```text
Packet قابل اعتماد برای پردازش فنی است.
```

### New

```text
Packet قبلاً پردازش نشده و هویت جدیدی دارد.
```

### Newer

```text
device_time آن از Snapshot فعلی جدیدتر است.
```

بنابراین یک Packet می‌تواند:

```text
Valid
New
Old
```

باشد.

مثلاً:

```text
Valid = YES
New = YES
Newer = NO
```

در این حالت:

```text
last_seen → قابل Update
CurrentState Snapshot → بدون Rollback
```

---

# 25. جدول رفتار

| Packet                             |         Valid |   Duplicate | Newer than CurrentState |         `last_seen` |                 Snapshot |
| ---------------------------------- | ------------: | ----------: | ----------------------: | ------------------: | -----------------------: |
| Packet معتبر جدید                  |             ✓ |          No |                       ✓ |              Update |                   Update |
| Packet معتبر قدیمی                 |             ✓ |          No |                      No |              Update |               بدون تغییر |
| Packet معتبر با همان `device_time` |             ✓ | ممکن است No |             No/Conflict | Update طبق Identity |            بدون Rollback |
| Duplicate                          | ✓ قبلاً معتبر |         Yes |                       — |          بدون تغییر |               بدون تغییر |
| Unknown Device                     |            No |           — |                       — |          بدون تغییر |               بدون تغییر |
| Malformed Packet                   |            No |           — |                       — |          بدون تغییر |               بدون تغییر |
| Decode Failed                      |            No |           — |                       — |          بدون تغییر |               بدون تغییر |
| Valid Packet + GPS No-Fix          |             ✓ |          No |            بسته به زمان |              Update | Snapshot طبق سایر Fields |
| Valid Packet + Missing Fields      |             ✓ |          No |            بسته به زمان |              Update |   فقط Fields مجاز Update |

---

# 26. قواعد نهایی زمان و همزمانی

```text
device_time
    ↓
Historical / Snapshot Ordering

server_received_at
    ↓
Arrival / Communication Time

last_seen
    ↓
Last Valid Packet Receipt

updated_at
    ↓
Last Snapshot Modification
```

و:

```text
Packet Validity
    ↓
آیا Packet اجازه اثرگذاری دارد؟

Deduplication
    ↓
آیا قبلاً همین Packet پردازش شده؟

Temporal Ordering
    ↓
آیا Telemetry از Snapshot فعلی جدیدتر است؟

Atomic DB Update
    ↓
حفاظت در برابر Race Condition
```

---

# 27. اصل کلیدی

> **Valid بودن Packet، جدید بودن Packet و جدیدتر بودن Telemetry سه مفهوم مستقل هستند.**

به‌صورت دقیق:

```text
Valid
→ آیا Packet قابل پردازش است؟

New
→ آیا این Packet قبلاً پردازش نشده؟

Newer
→ آیا device_time آن از Snapshot فعلی جدیدتر است؟
```

این تفکیک از اشتباهات مهمی مانند:

```text
Old Packet → Drop کامل
GPS No-Fix → Invalid Packet
Duplicate → Update last_seen
Arrival Order → Snapshot Order
```

جلوگیری می‌کند.

---

# 28. CurrentState نهایی

مدل نهایی:

```text
CurrentState
│
├── id
├── device
│
├── device_time
├── server_received_at
├── last_seen
├── updated_at
│
├── latitude
├── longitude
├── geom
├── gps_valid
├── accuracy
│
├── last_valid_latitude
├── last_valid_longitude
├── last_valid_geom
├── last_valid_device_time
├── last_valid_server_received_at
├── last_valid_accuracy
│
├── speed
├── heading
├── altitude
├── motion
├── ignition
├── satellites
│
├── battery_voltage
├── external_voltage
├── gsm_signal
│
├── odometer
├── engine_hours
├── fuel_level
│
└── attributes
```

`connection_state`:

```text
Computed
→ Backend
→ not stored in CurrentState
```

---

# 29. اصل نهایی طراحی

> **CurrentState یک Read Model سریع، کوچک، قابل بازسازی و متعلق به Device است که آخرین وضعیت قابل استفاده آن Device را نگه می‌دارد؛ نه تاریخچه، نه Raw Data و نه Full Telemetry.**

و در لایه دریافت:

```text
Raw Packet
    ↓
Valid Packet?
    │
    ├── No  → Reject / Technical Handling
    │
    └── Yes
          ↓
      Deduplicate
          ↓
      Temporal Ordering
          ↓
      Atomic Transaction
          ↓
      CurrentState / History / Event
          ↓
      COMMIT
          ↓
      Consumers
```

**این تعریف، معیار رسمی `Valid Packet` برای معماری SANA است.**


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی Schema نهایی دیتابیس GPS

## بخش ۲ از نقشه راه معماری GPS

این سند جمع‌بندی تصمیمات نهایی طراحی Schema دیتابیس بخش GPS در SANA است.

هدف:

* استفاده از Entityهای اصلی SANA
* جلوگیری از Duplicate Data
* جداسازی داده تاریخی از وضعیت لحظه‌ای
* حفظ تاریخچه Device
* جلوگیری از Schema پیچیده و غیرضروری
* آماده بودن برای مقیاس حدود 10,000 تا حداکثر 15,000 دستگاه

---

# 1. استفاده از Device اصلی SANA

`Device` فقط یک Entity اصلی در SANA دارد.

`sana-gps` برای Device جدول Duplicate ایجاد نمی‌کند.

رابطه:

```text
sana-backend
     │
     ▼
Device
     ▲
     │
sana-gps
```

هر دو سرویس از همان `Device` اصلی PostgreSQL استفاده می‌کنند.

---

# 2. Entityهای دائمی GPS

Entityهای اصلی:

```text
Device
│
├── CurrentState
├── LocationHistory
├── Event
├── Trip
└── RawPacket
```

بخش Geofence:

```text
Geofence
├── GeofenceVersion
├── GeofenceAssignment
└── VehicleGeofenceState
```

---

# 3. CurrentState

برای هر Device حداکثر یک CurrentState وجود دارد.

رابطه:

```text
Device
   │
   └── 1 : 1
         │
         ▼
    CurrentState
```

ساختار:

```text
CurrentState
├── id
├── device_id
├── device_time
├── server_received_at
├── last_seen
├── updated_at
│
├── latitude
├── longitude
├── geom
├── gps_valid
│
├── last_valid_latitude
├── last_valid_longitude
├── last_valid_geom
├── last_valid_device_time
├── last_valid_server_received_at
├── last_valid_accuracy
│
├── accuracy
├── speed
├── heading
├── altitude
├── motion
├── ignition
├── satellites
├── battery_voltage
├── external_voltage
├── gsm_signal
├── odometer
├── engine_hours
├── fuel_level
└── attributes
```

`CurrentState` یک Read Model قابل بازسازی است، نه History.

رابطه با Device:

```text
ON DELETE CASCADE
```

---

# 4. LocationHistory

`LocationHistory` تاریخچه Point-based موقعیت Device است.

ساختار:

```text
LocationHistory
├── id
├── device_id
├── device_time
├── server_received_at
├── latitude
├── longitude
├── geom
├── gps_valid
├── accuracy
├── speed
├── heading
├── altitude
├── motion
├── ignition
├── odometer
├── engine_hours
├── fuel_level
└── attributes
```

اصول:

* Device-owned
* تاریخی
* `device_time` اجباری
* `server_received_at` اجباری
* latitude/longitude قابل NULL
* `geom` از نوع PostGIS Point با SRID 4326
* `gps_valid=false` → مختصات و geom فعلی NULL
* `device_id + device_time` Unique نیست
* `ON DELETE PROTECT`

Index اصلی:

```text
(device_id, device_time)
```

---

# 5. Event

`Event` رخداد معنادار سیستم است.

Event با Telemetry، Alarm، Alert، Notification و Command متفاوت است.

ساختار:

```text
Event
├── id
├── device_id
├── type
├── source
├── mode
│
├── occurred_at
├── started_at
├── ended_at
│
├── device_time
├── server_received_at
│
├── latitude
├── longitude
├── geom
├── gps_valid
│
├── attributes
├── telemetry_reference
└── raw_packet_reference
```

`mode`:

```text
POINT
STATE
```

`source`:

```text
DEVICE
SANA
SYSTEM
```

Event تاریخی است و:

```text
ON DELETE PROTECT
```

دارد.

برای State Event:

```text
Device + Event Type
```

حداکثر یک Event فعال وجود دارد.

یعنی:

```text
ended_at IS NULL
```

با Partial Unique Index کنترل می‌شود.

Indexهای اصلی:

```text
(device_id, occurred_at)
(device_id, type, started_at)
```

---

# 6. Trip

Trip یک Summary/Aggregate از یک سفر واقعی است و جایگزین LocationHistory نیست.

ساختار:

```text
Trip
├── id
├── number
├── device_id
├── status
│
├── started_at
├── ended_at
│
├── start_geom
├── end_geom
│
├── start_odometer
├── end_odometer
├── start_engine_hours
├── end_engine_hours
├── start_fuel_level
├── end_fuel_level
│
├── distance
├── max_speed
│
├── moving_duration
├── stopped_duration
├── unknown_duration
│
├── start_event_id
├── end_event_id
└── attributes
```

اصول:

* Device-owned
* تاریخی
* `number` Unique و Immutable
* `ACTIVE / COMPLETED`
* حداکثر یک Trip فعال برای هر Device
* `ON DELETE PROTECT`

Indexهای اصلی:

```text
(device_id, started_at)
UNIQUE(number)
```

و:

```text
UNIQUE(device_id)
WHERE status = ACTIVE
```

مسیر Trip از `LocationHistory` خوانده می‌شود.

Trip تمام نقاط مسیر را داخل خودش ذخیره نمی‌کند.

---

# 7. RawPacket

`RawPacket` یک Entity فنی و کوتاه‌عمر است.

کاربرد:

* Debug
* بررسی Protocol
* بررسی Packet غیرعادی
* توسعه Decoder
* Audit فنی محدود

ساختار:

```text
RawPacket
├── id
├── device_id
├── received_at
├── protocol
├── remote_ip
├── remote_port
├── transport
├── payload
├── payload_size
├── packet_hash
├── decoded
├── decode_status
├── attributes
└── expires_at
```

نوع Payload:

```text
BYTEA
```

تا Bytes اصلی Packet حفظ شود.

`device_id` می‌تواند NULL باشد تا Packetهای ناشناس نیز برای مدت Retention کوتاه قابل بررسی باشند.

رابطه:

```text
ON DELETE SET NULL
```

Indexهای اصلی:

```text
(device_id, received_at)
(expires_at)
```

`packet_hash` Unique نیست.

RawPacket منبع مستقیم:

```text
CurrentState
LocationHistory
Event
Trip
```

نیست.

---

# 8. NormalizedTelemetry

در MVP جدول مستقل:

```text
NormalizedTelemetry
```

نداریم.

NormalizedTelemetry یک Internal Data Contract است:

```text
Raw Packet
    ↓
Protocol Decoder
    ↓
NormalizedTelemetry
    ↓
Processing
```

و سپس:

```text
LocationHistory
CurrentState
Event
Trip
```

داده موردنیاز خودشان را ذخیره می‌کنند.

دلیل:

* جلوگیری از Duplicate Data
* کاهش Write
* کاهش Storage
* کاهش Index
* ساده ماندن Database
* عدم ایجاد History اضافی

---

# 9. Session / Connection

در MVP جدول دائمی:

```text
Session
Connection
```

نداریم.

Session در Runtime `sana-gps` مدیریت می‌شود.

برای هر Device حداکثر یک Session فعال وجود دارد.

Connection جدید می‌تواند Session قبلی را جایگزین کند.

رخدادهای مهم ارتباطی در صورت نیاز به Event تبدیل می‌شوند.

`last_seen` در CurrentState نگهداری می‌شود.

---

# 10. Geofence

Geofence مستقل از Device است.

ساختار:

```text
Geofence
├── id
├── name
├── owner_type
├── owner_id
├── type
├── active
├── valid_from
├── valid_until
└── deleted_at
```

Geometry مستقیماً در Geofence اصلی نگهداری نمی‌شود.

---

# 11. GeofenceVersion

Geometry نسخه‌بندی می‌شود:

```text
Geofence
   │
   └──< GeofenceVersion
```

ساختار:

```text
GeofenceVersion
├── id
├── geofence_id
├── version
├── geometry
└── created_at
```

Geometry با PostGIS:

```text
geometry(Point/Polygon/Circle representation as designed)
SRID = 4326
```

در MVP:

```text
CIRCLE
POLYGON
```

داریم.

`LINE` در MVP وجود ندارد.

تغییر Geometry باعث ایجاد Version جدید می‌شود.

---

# 12. GeofenceAssignment

تخصیص Geofence به‌صورت جداگانه نگهداری می‌شود.

Scopeهای MVP:

```text
ORGANIZATION
BRANCH
VEHICLE
```

و Assignment:

```text
INCLUDE
```

ساختار مفهومی:

```text
GeofenceAssignment
├── id
├── geofence_id
├── organization_id
├── branch_id
├── vehicle_id
├── valid_from
├── valid_until
└── active
```

Geofence مستقیماً به Device متصل نمی‌شود.

رابطه:

```text
Geofence
   ↓
Vehicle
   ↓
Active Device
```

---

# 13. VehicleGeofenceState

وضعیت فعلی پردازش Geofence در:

```text
VehicleGeofenceState
```

نگهداری می‌شود.

این جدول History نیست.

Stateهای اصلی:

```text
OUTSIDE
INSIDE
ENTER_PENDING
EXIT_PENDING
UNCERTAIN
UNOBSERVED
```

برای هر:

```text
Vehicle + Geofence
```

یک State فعلی وجود دارد.

Unique:

```text
(vehicle_id, geofence_id)
```

رخدادهای تاریخی Enter/Exit/Dwell در Event ذخیره می‌شوند.

---

# 14. Foreign Key و Delete Policy

اصل:

```text
Read Model / Rebuildable
        ↓
     CASCADE

Historical / Audit
        ↓
     PROTECT
```

بنابراین:

```text
CurrentState
→ Device
→ CASCADE

LocationHistory
→ Device
→ PROTECT

Event
→ Device
→ PROTECT

Trip
→ Device
→ PROTECT

RawPacket
→ Device
→ SET NULL
```

Device در حالت عادی نباید فیزیکی حذف شود و Lifecycle آن با وضعیت‌ها و Eventهای خودش مدیریت می‌شود.

---

# 15. Constraintهای اصلی

### CurrentState

```text
UNIQUE(device_id)
```

### LocationHistory

```text
(device_id, device_time)
```

Unique نیست.

### Event

برای State Event فعال:

```text
UNIQUE(device_id, type)
WHERE ended_at IS NULL
AND mode = STATE
```

### Trip

```text
UNIQUE(number)

UNIQUE(device_id)
WHERE status = ACTIVE
```

### VehicleGeofenceState

```text
UNIQUE(vehicle_id, geofence_id)
```

---

# 16. Check Constraintها

قواعد پایه در Database نیز تا حد امکان enforce می‌شوند.

Latitude:

```text
-90 <= latitude <= 90
```

Longitude:

```text
-180 <= longitude <= 180
```

Speed:

```text
speed >= 0
```

Accuracy:

```text
accuracy >= 0
```

Odometer:

```text
odometer >= 0
```

Engine Hours:

```text
engine_hours >= 0
```

Fuel:

```text
fuel_level >= 0
```

Heading:

```text
0 <= heading < 360
```

قواعد پیچیده مانند:

```text
Reset
Rollover
Trip Detection
Fuel Calibration
Overspeed
```

در Database Constraint پیاده نمی‌شوند و متعلق به Processing/Business Logic هستند.

---

# 17. Index Strategy

اصل:

> Index فقط برای Constraint واقعی یا Query واقعی ایجاد می‌شود.

Indexهای اصلی:

```text
CurrentState
→ UNIQUE(device_id)

LocationHistory
→ (device_id, device_time)

Event
→ (device_id, occurred_at)
→ (device_id, type, started_at)
→ Partial Unique Active State

Trip
→ (device_id, started_at)
→ UNIQUE(number)
→ Partial Unique Active Trip

RawPacket
→ (device_id, received_at)
→ (expires_at)

VehicleGeofenceState
→ UNIQUE(vehicle_id, geofence_id)

GeofenceVersion
→ GiST(geometry)
```

روی فیلدهای زیر Index عمومی ایجاد نمی‌شود مگر اینکه Query واقعی ایجاد شود:

```text
speed
heading
altitude
battery_voltage
external_voltage
gsm_signal
fuel_level
engine_hours
ignition
motion
attributes
```

به‌خصوص برای جداول Write-heavy مانند:

```text
LocationHistory
RawPacket
```

از Index اضافی پرهیز می‌شود.

---

# 18. اصل نهایی Schema

معماری Storage به این شکل است:

```text
Raw Packet
      ↓
Framer / Protocol Detection
      ↓
Protocol Decoder
      ↓
ProtocolMessage
      ↓
Normalizer
      ↓
NormalizedTelemetry
      ↓
Processing
      ├── CurrentState
      ├── LocationHistory
      ├── Event
      └── Trip
```

و Geofence:

```text
Geofence
   ↓
GeofenceVersion
   ↓
GeofenceAssignment
   ↓
Vehicle
   ↓
Active Device
   ↓
Telemetry
   ↓
VehicleGeofenceState
   ↓
Event
```

---

# 19. Entityهایی که عمداً Table مستقل نیستند

در MVP این موارد جدول مستقل PostgreSQL ندارند:

```text
NormalizedTelemetry
Session
Connection
```

زیرا:

* NormalizedTelemetry یک Internal Contract است.
* Session یک Runtime State است.
* Connection یک Runtime Resource است.

این تصمیم برای حفظ سادگی و جلوگیری از Data Duplication اتخاذ شده است.

---

# 20. وضعیت نهایی بخش Schema

موارد زیر قطعی شدند:

[✓] Device مشترک بین sana-backend و sana-gps
[✓] CurrentState به‌صورت One-to-One
[✓] LocationHistory به‌صورت تاریخی و Device-owned
[✓] Event به‌صورت تاریخی و Device-owned
[✓] Trip به‌صورت Summary و Device-owned
[✓] RawPacket به‌صورت کوتاه‌عمر و فنی
[✓] عدم ایجاد جدول مستقل NormalizedTelemetry
[✓] عدم ایجاد جدول دائمی Session/Connection
[✓] Geofence مستقل از Device
[✓] GeofenceVersion برای Versioning Geometry
[✓] GeofenceAssignment برای Scope
[✓] VehicleGeofenceState برای Current Processing State
[✓] سیاست مشخص CASCADE / PROTECT / SET NULL
[✓] Constraintهای اصلی
[✓] Indexهای اصلی
[✓] عدم Indexگذاری عمومی و غیرضروری
[✓] Check Constraintهای پایه
[✓] حفظ تاریخچه Device
[✓] جلوگیری از Duplicate Storage

---

# 21. اصل معماری نهایی

اصل نهایی Schema GPS:

> **هر داده باید فقط یک جای اصلی و منطقی برای نگهداری داشته باشد.**

بنابراین:

```text
Raw Packet
→ RawPacket

آخرین وضعیت
→ CurrentState

تاریخچه موقعیت
→ LocationHistory

رخداد معنادار
→ Event

خلاصه سفر
→ Trip

محدوده مکانی
→ Geofence

وضعیت پردازش Geofence
→ VehicleGeofenceState
```

و:

```text
NormalizedTelemetry
Session
Connection
```

به‌عنوان داده‌های Runtime/Internal باقی می‌مانند و بدون نیاز واقعی به Entity دائمی تبدیل نمی‌شوند.

**بخش ۲ — Schema نهایی دیتابیس GPS بسته شد.**


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی PostgreSQL Schema و DB Permissions

## بخش ۳ معماری GPS

این سند تصمیمات نهایی مربوط به مالکیت Database، Schema، Roleها، Permissionها، Transaction و Connection Pooling در `sana-gps` را مشخص می‌کند.

هدف:

> **تفکیک روشن مالکیت و دسترسی، حفظ امنیت Database، جلوگیری از وابستگی GPS به Business Logic و فراهم کردن امکان Scale در آینده بدون پیچیدگی غیرضروری.**

---

# 1. PostgreSQL Roles

چهار Role اصلی خواهیم داشت:

```text
sana_owner
sana_migrator
sana_backend
sana_gps
```

### sana_owner

مالک Database/Schema و Objectها.

مسئول:

* Ownership
* مالکیت Schema
* مالکیت Tableها
* مالکیت Sequence/Identity

این Role هرگز توسط Application Runtime استفاده نمی‌شود.

---

### sana_migrator

Role مخصوص:

* Django Migration
* DDL
* CREATE
* ALTER
* DROP
* CREATE INDEX
* GRANT / REVOKE
* تغییر Schema

Runtime Application از این Role استفاده نمی‌کند.

---

### sana_backend

Role مربوط به Django Backend و Business Logic.

مسئول:

* Business Data
* User
* Organization
* Vehicle
* Device Lifecycle
* Contract
* Geofence Management
* API

Backend Runtime نباید نویسنده Runtime داده‌های GPS باشد.

---

### sana_gps

Role مربوط به GPS Runtime.

مسئول:

* دریافت GPS
* Decode
* Normalize
* Telemetry Processing
* Current State
* Location History
* Event
* Trip
* Raw Packet
* Geofence State Processing

`sana-gps` مالک Database یا Schema نیست.

---

# 2. Schema Boundary

تمام داده‌های GPS در Schema مستقل:

```text
gps
```

قرار می‌گیرند.

داده‌های Business در Schema اصلی:

```text
public
```

قرار دارند.

### public

نمونه:

```text
accounts_user
organizations
vehicles
devices
device_model
...
```

### gps

```text
current_state
location_history
event
trip
raw_packet

geofence
geofence_version
geofence_assignment
vehicle_geofence_state
```

`gps` یک PostgreSQL Schema مستقل در همان Database است، نه Database جدا.

---

# 3. Device مالک مشترک SANA است

جدول:

```text
public.device
```

توسط SANA Backend/Business مدیریت می‌شود.

`sana-gps` فقط اطلاعات موردنیاز را می‌خواند.

```text
sana-gps
    ↓
SELECT
    ↓
public.device
```

ولی:

```text
INSERT ❌
UPDATE ❌
DELETE ❌
```

به Device ندارد.

---

# 4. Cross-Schema Foreign Keys

بین `public` و `gps` از Foreign Key واقعی PostgreSQL استفاده می‌شود.

مثلاً:

```text
gps.location_history.device_id
        ↓
public.device.id
```

و:

```text
gps.event.device_id
        ↓
public.device.id

gps.trip.device_id
        ↓
public.device.id
```

و سایر ارتباط‌های موردنیاز.

FK توسط Database تضمین می‌شود.

> Foreign Key با Permission یک مفهوم جداست.

---

# 5. Delete Policy

برای داده‌های تاریخی:

```text
LocationHistory
Event
Trip
```

از رفتار محافظتی استفاده می‌شود.

یعنی حذف Device نباید به‌صورت خودکار تاریخچه GPS را حذف کند.

### CurrentState

CurrentState یک Snapshot قابل بازسازی است و می‌تواند:

```text
ON DELETE CASCADE
```

داشته باشد.

### RawPacket

RawPacket داده فنی کوتاه‌مدت است و در صورت حذف Device:

```text
ON DELETE SET NULL
```

می‌تواند استفاده شود.

---

# 6. sana-gps — Permission Matrix

## public.device

```text
SELECT محدود
```

بدون:

```text
INSERT
UPDATE
DELETE
```

---

## public.device_model

فقط:

```text
SELECT
```

برای اطلاعات فنی موردنیاز Decoder.

---

## gps.current_state

```text
SELECT
INSERT
UPDATE
```

بدون:

```text
DELETE
```

---

## gps.location_history

```text
SELECT
INSERT
```

بدون:

```text
UPDATE
DELETE
```

Location History تاریخی و Immutable است.

---

## gps.event

```text
SELECT
INSERT
UPDATE
```

`UPDATE` فقط برای عملیات معنادار مانند بستن State Event استفاده می‌شود.

بدون:

```text
DELETE
```

---

## gps.trip

```text
SELECT
INSERT
UPDATE
```

بدون:

```text
DELETE
```

---

## gps.raw_packet

```text
SELECT
INSERT
```

بدون:

```text
UPDATE
DELETE
```

---

## Geofence

`sana-gps` فقط مصرف‌کننده تنظیمات Geofence است:

```text
gps.geofence
    SELECT

gps.geofence_version
    SELECT

gps.geofence_assignment
    SELECT
```

مدیریت این داده‌ها توسط Backend انجام می‌شود.

---

## VehicleGeofenceState

GPS Engine وضعیت Runtime مربوط به Geofence را مدیریت می‌کند:

```text
SELECT
INSERT
UPDATE
```

بدون Delete Runtime.

---

# 7. sana_backend — Permission Matrix

Backend روی داده‌های GPS عمدتاً Read-only است.

### CurrentState

```text
SELECT
```

### LocationHistory

```text
SELECT
```

### Event

```text
SELECT
```

### Trip

```text
SELECT
```

### RawPacket

به‌صورت پیش‌فرض:

```text
NO ACCESS
```

در آینده در صورت نیاز می‌توان دسترسی ویژه Admin/Debug طراحی کرد.

### Geofence

```text
CRUD
```

### GeofenceVersion

```text
CRUD
```

### GeofenceAssignment

```text
CRUD
```

### VehicleGeofenceState

```text
SELECT
```

Backend نویسنده Runtime داده‌های:

```text
CurrentState
LocationHistory
Event
Trip
```

نیست.

---

# 8. sana_migrator

تنها Role مخصوص Schema Changes:

```text
CREATE
ALTER
DROP
CREATE INDEX
GRANT
REVOKE
MIGRATION
```

است.

همه تغییرات ساختاری Database از طریق این Role انجام می‌شوند.

---

# 9. sana_owner

`sana_owner` مالک Objectهاست ولی Application Runtime نباید با آن به Database متصل شود.

اصل:

```text
Owner ≠ Runtime
```

مالکیت Database نباید به معنی دسترسی دائمی Application باشد.

---

# 10. Runtime DDL ممنوع

هیچ‌کدام از این دو Runtime Role اجازه DDL ندارند:

```text
sana_backend
sana-gps
```

بنابراین:

```text
CREATE       ❌
ALTER        ❌
DROP         ❌
CREATE INDEX ❌
TRUNCATE     ❌
```

برای Runtime ممنوع است.

---

# 11. Default Privileges

برای Objectهای آینده از PostgreSQL:

```text
DEFAULT PRIVILEGES
```

استفاده می‌شود.

اما Permissionها حداقلی خواهند بود.

نباید هر Table جدید GPS به‌صورت خودکار:

```text
FULL ACCESS
```

برای همه Roleها دریافت کند.

Permissionهای:

```text
SELECT
INSERT
UPDATE
```

بر اساس نیاز هر Table به‌صورت مشخص تعریف می‌شوند.

Sequence/Identityهایی که برای Insert لازم هستند نیز باید Permission لازم را داشته باشند.

---

# 12. ID Strategy

GPS Tableها از:

```text
BIGINT
```

استفاده می‌کنند.

با:

```text
PostgreSQL Identity / Sequence
```

مشابه Django `BigAutoField`.

`sana-gps` می‌تواند Sequence/Identity لازم برای Insert را مصرف کند، ولی اجازه:

```text
ALTER
DROP
```

آن را ندارد.

UUID برای Internal GPS IDs در MVP استفاده نمی‌شود.

---

# 13. Trip ID

Trip دو شناسه مستقل دارد:

```text
id
```

برای Internal Database:

```text
BIGINT
```

و:

```text
number
```

برای شناسه Human-readable.

`number`:

* Unique
* Immutable
* مستقل از `id`
* دارای امکان Gap

است.

---

# 14. Device Read Scope

`sana-gps` نباید تمام ستون‌های `Device` را بخواند.

فقط اطلاعات لازم برای:

* Device Identification
* IMEI
* Device Model
* Protocol Resolution
* Active/Allowed State
* Technical Configuration

خوانده می‌شود.

در Application نیز Repository/Query صریح برای این منظور استفاده می‌شود.

Column-level privilege در صورت عملی بودن قابل استفاده است، ولی نباید باعث پیچیدگی غیرضروری Django شود.

---

# 15. DeviceModel / Protocol Configuration

`sana-gps` فقط Configuration فنی موردنیاز Decoder را می‌خواند.

مثلاً:

```text
Device
   ↓
DeviceModel
   ↓
Protocol
```

اما:

```text
CREATE ❌
UPDATE ❌
DELETE ❌
```

ندارد.

DeviceModel Configuration است، نه Runtime State.

---

# 16. Protocol Definition

تعریف Protocol و منطق Decoder در Code باقی می‌ماند.

Database فقط مشخص می‌کند:

```text
این Device از چه Protocol/Model استفاده می‌کند؟
```

اما Code مشخص می‌کند:

```text
چگونه Packet را Decode کنیم؟
```

بنابراین:

```text
Database
→ Which Protocol?

Code
→ How to Decode?
```

---

# 17. Database Access در sana-gps

`sana-gps` از Django ORM برای Runtime Database Access استفاده نمی‌کند.

یک DB/Repository Layer سبک با PostgreSQL Driver استفاده می‌شود.

Repositoryهای مفهومی:

```text
DeviceRepository
CurrentStateRepository
LocationHistoryRepository
EventRepository
TripRepository
```

اما این ساختار نباید به Enterprise/Over-layering تبدیل شود.

Decoder و Telemetry Processing نباید مستقیماً SQL بنویسند.

---

# 18. Transaction / Atomicity

پردازش یک Packet معتبر و تغییرات وابسته به آن باید در یک PostgreSQL Transaction انجام شود.

مثلاً:

```text
Valid Packet
    ↓
Dedup / Identity
    ↓
BEGIN
    ├── LocationHistory
    ├── CurrentState
    ├── Event
    └── Trip
COMMIT
```

یا در صورت خطا:

```text
ROLLBACK
```

تمام تغییرات همان Packet با هم موفق یا ناموفق می‌شوند.

---

# 19. Consumers بعد از Commit

مواردی مانند:

```text
WebSocket
Geofence
Alert
Notification
```

نباید قبل از Commit موفق Database اجرا شوند.

اصل:

```text
Database Commit
      ↓
Consumers
```

نه:

```text
Consumers
      ↓
Database Commit
```

---

# 20. Concurrency

برای Race Condition از امکانات PostgreSQL استفاده می‌شود:

* Atomic Update
* Constraints
* Row Lock در موارد لازم

Isolation پیش‌فرض:

```text
READ COMMITTED
```

برای MVP کافی است.

فعلاً:

```text
SERIALIZABLE
```

به‌صورت عمومی استفاده نمی‌شود.

---

# 21. CurrentState Race Protection

CurrentState بر اساس:

```text
device_time
```

به‌صورت شرطی Update می‌شود.

مفهوم:

```sql
UPDATE gps.current_state
SET ...
WHERE device_id = ?
AND (
    device_time IS NULL
    OR device_time < incoming_device_time
);
```

در نتیجه Packet قدیمی نمی‌تواند Snapshot جدیدتر را Rollback کند.

این شرط در Database لایه نهایی محافظت در برابر Race است.

---

# 22. Connection Pooling

`sana-gps` از PostgreSQL Connection Pool استفاده می‌کند.

Connectionها:

```text
Per Application Instance / Worker
```

هستند، نه:

```text
Per Device
```

مثلاً Configuration اولیه می‌تواند حدود:

```text
min = 2
max = 10
```

باشد، ولی این مقدار Architecture ثابت نیست و قابل تنظیم است.

تنظیمات پیشنهادی:

```text
DB_POOL_MIN_SIZE
DB_POOL_MAX_SIZE
DB_CONNECTION_TIMEOUT
DB_IDLE_TIMEOUT
```

---

# 23. Connection Budget

در حالت چند Instance:

```text
Total DB Connections
=
Number of GPS Instances
×
Maximum Pool Size
```

بنابراین هنگام Scale کردن باید Connection Budget کل PostgreSQL نیز در نظر گرفته شود.

---

# 24. PgBouncer

در MVP نیازی به PgBouncer نداریم.

ابتدا:

```text
sana-gps instances
        ↓
PostgreSQL
```

مستقیم با Pool خود Application کار می‌کنند.

اگر در آینده تعداد Instanceها، Connectionها یا الگوی اتصال واقعاً نیاز ایجاد کند، PgBouncer قابل اضافه شدن است.

---

# 25. Connection Lifecycle

Connection باید:

```text
Acquire
   ↓
Transaction
   ↓
COMMIT / ROLLBACK
   ↓
Release
```

شود.

Connection نباید در حالت باز و بدون استفاده باقی بماند و Leak شدن Connection باید جلوگیری شود.

---

# 26. Permission Matrix نهایی

```text
┌────────────────────┬────────────────────────────────────┬─────────────┐
│ Role               │ Responsibility                    │ DDL         │
├────────────────────┼────────────────────────────────────┼─────────────┤
│ sana_owner         │ Ownership                          │ Owner       │
│ sana_migrator      │ Migration / Schema                 │ YES         │
│ sana_backend       │ Business + Geofence Management     │ NO          │
│ sana-gps           │ GPS Runtime Processing             │ NO          │
└────────────────────┴────────────────────────────────────┴─────────────┘
```

### sana-gps

```text
public.device              SELECT محدود
public.device_model        SELECT محدود

gps.current_state          SELECT / INSERT / UPDATE
gps.location_history       SELECT / INSERT
gps.event                  SELECT / INSERT / UPDATE
gps.trip                   SELECT / INSERT / UPDATE
gps.raw_packet             SELECT / INSERT

gps.geofence               SELECT
gps.geofence_version       SELECT
gps.geofence_assignment    SELECT

gps.vehicle_geofence_state SELECT / INSERT / UPDATE
```

### sana_backend

```text
gps.current_state          SELECT
gps.location_history       SELECT
gps.event                  SELECT
gps.trip                   SELECT

gps.raw_packet             NO ACCESS by default

gps.geofence               CRUD
gps.geofence_version       CRUD
gps.geofence_assignment    CRUD

gps.vehicle_geofence_state SELECT
```

### sana-gps / sana_backend

```text
CREATE       ❌
ALTER        ❌
DROP         ❌
TRUNCATE     ❌
CREATE INDEX ❌
```

---

# 27. اصل نهایی بخش PostgreSQL

معماری Database بر این اصل بنا می‌شود:

> **هر Role فقط به اندازه مسئولیت خودش دسترسی دارد.**

یعنی:

```text
Ownership
    ≠
Migration
    ≠
Business Runtime
    ≠
GPS Runtime
```

و:

```text
Database
    ↓
Second Line of Defense
```

حتی اگر در Application اشتباهی رخ دهد، PostgreSQL نباید اجازه دهد Runtime از مرز مسئولیت خود عبور کند.

---

# وضعیت نهایی بخش ۳

تمام تصمیمات این بخش نهایی و تأیید شده‌اند:

```text
[✓] PostgreSQL Roles
[✓] Schema Boundary
[✓] sana-gps Permissions
[✓] sana_backend Permissions
[✓] sana_migrator
[✓] Runtime DDL Protection
[✓] Default Privileges
[✓] Cross-Schema FKs
[✓] Device Read Scope
[✓] DeviceModel / Protocol Config
[✓] Protocol Definition Ownership
[✓] DB Access Layer
[✓] Transactions
[✓] Concurrency
[✓] ID Strategy
[✓] Connection Pooling
[✓] Final Permission Matrix
```

**بخش ۳ — PostgreSQL Schema / DB Permissions — CLOSED**


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Location Sampling و Compression

## 1. هدف

هدف Sampling در SANA این است که از میان Telemetryهای معتبر، فقط Location Pointهایی را که از نظر تاریخی و عملیاتی ارزش دارند در `LocationHistory` ذخیره کند.

Sampling نباید باعث از دست رفتن Telemetry، Event، CurrentState، Trip یا داده‌های مورد نیاز Geofence شود.

اصل:

```text
Telemetry
→ پردازش کامل
→ Sampling فقط برای LocationHistory
```

---

# 2. Sampling فقط روی LocationHistory اعمال می‌شود

تمام Telemetryهای معتبر وارد Pipeline پردازش می‌شوند.

Sampling فقط تصمیم می‌گیرد که آیا Location فعلی به `LocationHistory` اضافه شود یا خیر.

```text
GPS Packet
    ↓
Normalized Telemetry
    ↓
Event Processing
    ↓
CurrentState
    ↓
Trip / Geofence / ...
    ↓
Location Sampling
    ↓
LocationHistory
```

بنابراین حذف یک Location Point نباید باعث حذف یا نادیده گرفتن Event یا CurrentState شود.

---

# 3. معیارهای Sampling

Sampling بر اساس یک Threshold واحد انجام نمی‌شود.

پارامترهای اصلی:

```text
location_min_distance
location_max_interval
speed_change_threshold
heading_change_threshold
stationary_interval
accuracy_threshold
```

همراه با:

```text
Motion Boundary
Ignition Boundary
GPS Fix Boundary
```

استفاده می‌شوند.

مقادیر عددی اولیه مانند 20 متر یا 60 ثانیه صرفاً نمونه هستند و Configuration نهایی محسوب نمی‌شوند.

---

# 4. Stable Stop

وقتی Device وارد وضعیت پایدار:

```text
STOPPED
```

می‌شود:

1. یک Boundary Location ذخیره می‌شود.
2. Locationهای تکراری در زمان توقف ذخیره نمی‌شوند.
3. مدت توقف توسط State Event مشخص می‌شود.
4. GPS Drift در زمان توقف باعث تولید Locationهای تکراری نمی‌شود.

وقتی خودرو دوباره حرکت کند:

```text
STOPPED
    ↓
MOVING
```

یک Boundary Location جدید ذخیره می‌شود.

`speed = 0` به‌تنهایی معیار قطعی STOPPED نیست.

---

# 5. GPS Drift

GPS Drift با یک معیار واحد تشخیص داده نمی‌شود.

عوامل مورد استفاده:

```text
Distance
Accuracy
Speed
Motion
Ignition
Heading
Temporal Sequence
```

هستند.

مثلاً جابه‌جایی چند متری در حالت توقف می‌تواند Drift باشد، حتی اگر مختصات تغییر کرده باشد.

در MVP الگوریتم Drift:

```text
Rule-Based
```

خواهد بود و از Machine Learning یا الگوریتم آماری پیچیده استفاده نمی‌شود.

---

# 6. GPS No-Fix

وقتی:

```text
gps_valid = false
```

باشد:

* LocationHistory Point جدید ایجاد نمی‌شود.
* مختصات قبلی به‌عنوان موقعیت جدید تکرار نمی‌شوند.
* `latitude` و `longitude` برای موقعیت فعلی معتبر نیستند.
* `geom` جدید ساخته نمی‌شود.
* `GPS_FIX_LOST` به‌عنوان State Event ثبت می‌شود.

GPS No-Fix به معنی Offline نیست.

---

# 7. GPS Recovery

وقتی بعد از No-Fix اولین Location معتبر دریافت شود:

```text
gps_valid = true
```

این Point به‌عنوان Boundary Point ذخیره می‌شود، حتی اگر:

```text
location_min_distance
```

یا:

```text
location_max_interval
```

هنوز برقرار نشده باشند.

سپس:

```text
GPS_FIX_LOST
```

بسته می‌شود.

در زمان No-Fix هیچ Location ساختگی یا Interpolated ایجاد نمی‌شود.

---

# 8. Current Position و Last Valid Position

در زمان GPS No-Fix:

```text
Current Position
→ NULL
```

اما CurrentState می‌تواند آخرین موقعیت معتبر را جداگانه حفظ کند:

```text
last_valid_latitude
last_valid_longitude
last_valid_geom
...
```

آخرین موقعیت معتبر نباید به‌عنوان موقعیت فعلی نمایش داده شود.

---

# 9. GPS No-Fix و Offline مستقل هستند

ممکن است:

```text
GPS = No-Fix
Device = Online
```

باشد.

همچنین ممکن است:

```text
GPS = Valid
Device = Offline
```

باشد.

پس:

```text
GPS No-Fix ≠ Device Offline
```

---

# 10. Late Packet و Out-of-Order

`device_time` مرجع اصلی ترتیب تاریخی است.

`server_received_at` زمان واقعی دریافت Packet توسط Server است.

ممکن است ترتیب دریافت با ترتیب زمانی Device متفاوت باشد:

```text
device_time:
10:00
10:01
10:02
10:03

arrival:
10:00
10:02
10:01
10:03
```

Packet معتبر و دیررس حذف نمی‌شود.

اما Packet قدیمی نباید:

```text
CurrentState
```

را Rollback کند.

---

# 11. Historical Ordering

Sampling باید با:

```text
Device Timeline
```

کار کند، نه صرفاً آخرین Packet دریافت‌شده.

بنابراین:

```text
previous chronological point
```

مهم‌تر از:

```text
last inserted point
```

است.

LocationHistory بر اساس `device_time` قابل مرتب‌سازی خواهد بود.

---

# 12. Watermark

برای مدیریت Late Data مفهوم:

```text
Watermark
```

در Processing در نظر گرفته می‌شود.

Watermark نشان‌دهنده محدوده‌ای است که سیستم تا حد قابل قبول آن را از نظر تاریخی پردازش کرده است.

Packetهای Late می‌توانند وارد Historical Processing شوند، ولی در MVP ورود Packet قدیمی باعث:

```text
Re-sampling کل تاریخچه
Rebuild Trip
Rebuild Event
Rebuild Geofence
```

نخواهد شد.

---

# 13. Duplicate Packet

Duplicate قبل از Sampling تشخیص داده می‌شود.

جریان:

```text
Raw Packet
→ Decode
→ Normalize
→ Validate
→ Packet Identity
→ Deduplicate
→ Location Sampling
```

Packet Duplicate هیچ Side Effectی ایجاد نمی‌کند.

از جمله:

```text
CurrentState
LocationHistory
Event
Trip
Geofence
WebSocket
```

تغییر نمی‌کنند.

---

# 14. Packet Identity

اگر Protocol دارای:

```text
Sequence Number
Message ID
Packet ID
```

باشد، از آن برای تشخیص Duplicate استفاده می‌شود.

اگر Protocol چنین شناسه‌ای نداشته باشد، SANA می‌تواند از Fingerprint به‌عنوان Fallback استفاده کند.

`device_time` به‌تنهایی شناسه یکتای Packet نیست.

همچنین:

```text
Duplicate ≠ Old Packet
Duplicate ≠ Late Packet
```

---

# 15. Same device_time

دو Packet مختلف می‌توانند:

```text
device_time
```

یکسان داشته باشند.

بنابراین این Constraint مجاز نیست:

```text
UNIQUE(device_id, device_time)
```

Packet Identity باید مستقل از Timestamp باشد.

---

# 16. Sampling Configuration

Sampling Configuration به‌صورت سلسله‌مراتبی خواهد بود:

```text
Global Default
      ↓
DeviceModel Config
      ↓
Device Override
```

یعنی:

* Global تنظیم پایه را مشخص می‌کند.
* DeviceModel می‌تواند برای یک مدل خاص Override داشته باشد.
* Device خاص در صورت نیاز می‌تواند Override شود.

Configuration نباید در Code Hard-Code شود.

---

# 17. Configuration Change

تغییر Configuration فقط روی داده‌های آینده اعمال می‌شود.

مثلاً اگر:

```text
location_min_distance = 20m
```

به:

```text
location_min_distance = 50m
```

تغییر کند، LocationHistory قبلی دوباره Sampling نمی‌شود.

---

# 18. Configuration Audit

در MVP Configuration History کامل و Versioning ایجاد نمی‌شود.

فقط:

```text
updated_at
updated_by
```

در کنار Configuration فعلی نگهداری می‌شود.

در آینده اگر نیاز واقعی به Audit تاریخی دقیق یا Reprocessing ایجاد شود، Versioned Configuration می‌تواند مستقل اضافه شود.

---

# 19. Vehicle در Sampling دخالت مستقیم ندارد

Sampling مستقیماً بر اساس Vehicle تنظیم نمی‌شود.

چون:

```text
LocationHistory → Device
```

و نه:

```text
LocationHistory → Vehicle
```

است.

ساختار:

```text
Vehicle
   ↓
Device Assignment History
   ↓
Device
   ↓
Sampling
   ↓
LocationHistory
```

Vehicle در Trip، Reports و Business Views استفاده می‌شود.

اگر در آینده نیاز به Sampling متفاوت برای یک نوع عملیات وجود داشته باشد، این موضوع در قالب:

```text
Sampling / Processing Profile
```

طراحی خواهد شد، نه وابستگی مستقیم به Vehicle.

---

# 20. Sampling مستقل از Device Reporting Rate

Deviceها ممکن است نرخ ارسال متفاوت داشته باشند:

```text
5 sec
10 sec
30 sec
60 sec
...
```

Sampling بر اساس تعداد Packet تصمیم نمی‌گیرد.

این منطق ممنوع است:

```text
هر 10 Packet یک Location
```

معیار Sampling تغییر معنادار موقعیت و وضعیت است.

---

# 21. Sampling نمی‌تواند داده تولید کند

اگر Device هر 5 دقیقه Packet بفرستد، SANA نمی‌تواند Pointهای:

```text
10:01
10:02
10:03
10:04
```

را اختراع کند.

Sampling فقط می‌تواند:

```text
داده اضافی را حذف کند.
```

ولی نمی‌تواند:

```text
داده‌ای که Device گزارش نکرده را تولید کند.
```

Interpolation در LocationHistory MVP انجام نمی‌شود.

---

# 22. Speed و Heading Boundary

تغییر معنادار Speed یا Heading می‌تواند بدون رسیدن به:

```text
location_min_distance
```

یا:

```text
location_max_interval
```

باعث ذخیره Boundary Point شود.

اما تغییرات کوچک و نویزی نباید باعث ذخیره Point شوند.

Threshold و Drift Detection باید همزمان در نظر گرفته شوند.

مثلاً:

```text
40 → 42 km/h
```

الزاماً Point جدید ایجاد نمی‌کند.

اما:

```text
40 → 75 km/h
```

می‌تواند Boundary ایجاد کند.

همین اصل برای Heading نیز برقرار است.

---

# 23. Motion و Ignition Boundary

تغییر:

```text
MOVING → STOPPED
STOPPED → MOVING
```

Boundary مهم است.

تغییر:

```text
IGNITION ON
IGNITION OFF
```

نیز در صورت وجود GPS معتبر می‌تواند باعث ذخیره Boundary Location شود.

اگر GPS معتبر نباشد:

```text
Event
```

ثبت می‌شود، ولی مختصات ساختگی تولید نمی‌شود.

---

# 24. Compression

Sampling و Compression دو مفهوم جدا هستند.

### Sampling

تصمیم می‌گیرد:

```text
آیا Location ذخیره شود؟
```

### Compression

داده ذخیره‌شده را برای کاهش حجم فشرده می‌کند.

در MVP:

```text
Smart Sampling
✓
```

اما:

```text
Destructive Location Compression
✗
```

است.

---

# 25. LocationHistory به‌عنوان Source of Truth

بعد از ذخیره LocationHistory:

* Point حذف نمی‌شود.
* Point با Point دیگری ادغام نمی‌شود.
* مختصات تغییر نمی‌کند.
* مسیر تاریخی برای کاهش حجم تخریب نمی‌شود.

LocationHistory Source of Truth تاریخی باقی می‌ماند.

---

# 26. Map Downsampling

برای نمایش مسیر روی Map می‌توان از:

```text
Route Simplification
Downsampling
```

استفاده کرد.

مثلاً:

```text
20,000 historical points
        ↓
2,000 points
        ↓
Map
```

اما Database همچنان Pointهای اصلی را نگه می‌دارد.

پس:

```text
Map Representation
≠
Historical Source of Truth
```

---

# 27. Storage Compression

در MVP سیستم Compression سفارشی برای PostgreSQL ساخته نمی‌شود.

در صورت افزایش واقعی حجم، بعداً می‌توان درباره:

```text
Partition Retention
Archive
Storage Compression
Historical Storage
```

تصمیم گرفت.

---

# 28. LocationHistory Retention

LocationHistory برای همیشه و بدون محدودیت نگهداری نمی‌شود.

Retention:

```text
Configurable
Long-Term
```

خواهد بود.

مثلاً:

```text
12 months
24 months
36 months
...
```

مقادیر نهایی Configuration هستند.

---

# 29. Retention بر اساس device_time

مبنای Retention برای LocationHistory:

```text
device_time
```

است.

نه:

```text
server_received_at
```

زیرا LocationHistory داده تاریخی Device است.

---

# 30. حذف با Partition

LocationHistory به‌صورت:

```text
RANGE(device_time)
```

و Partitionهای ماهانه طراحی شده است.

پس در آینده حذف داده منقضی‌شده ترجیحاً با:

```text
DROP PARTITION
```

انجام می‌شود، نه DELETE میلیون‌ها رکورد.

---

# 31. Retention مستقل Entityها

LocationHistory، Event، Trip و RawPacket Retention مستقل دارند.

ممکن است:

```text
LocationHistory → 24 months
Trip             → 36 months
Event            → 36 months
RawPacket        → 7 days
```

باشند.

این اعداد صرفاً نمونه هستند.

---

# 32. Trip بعد از حذف LocationHistory

اگر LocationHistory قدیمی طبق Retention حذف شود ولی Trip باقی بماند:

```text
Trip
✓
```

اما ممکن است:

```text
Trip Route / Playback
✗
```

دیگر کامل قابل بازیابی نباشد.

وجود Trip به معنی نگهداری همیشگی تمام Route Points آن نیست.

---

# 33. RawPacket Retention

RawPacket Retention مستقل و کوتاه‌تر از LocationHistory است.

مبنای آن:

```text
server_received_at
```

است.

چون RawPacket برای Debug و بررسی فنی ارتباط استفاده می‌شود.

---

# 34. حذف RawPacket

حذف RawPacket نباید باعث حذف:

```text
LocationHistory
Event
Trip
CurrentState
```

شود.

Reference به RawPacket صرفاً برای Traceability است و وابستگی حیاتی ایجاد نمی‌کند.

---

# 35. RawPacket Processing Order

RawPacket باید ابتدا پردازش شود:

```text
Raw Packet
→ Decode
→ Normalize
→ Validate
→ Process
→ Commit
→ Retention
```

RawPacket قبل از تکمیل Processing حذف نمی‌شود.

---

# 36. Archive

در MVP برای:

```text
LocationHistory
RawPacket
```

Archive جداگانه نداریم.

ابتدا:

```text
PostgreSQL
+
Partitioning
+
Retention
```

کافی است.

Archive فقط در صورت نیاز واقعی آینده طراحی می‌شود.

---

# 37. معماری نهایی Sampling

```text
GPS Packet
      ↓
Normalized Telemetry
      ↓
Deduplication
      ↓
Historical Ordering
      ↓
┌───────────────────────────────┐
│ Event / CurrentState / Trip  │
│ Geofence / Alert Processing  │
└───────────────────────────────┘
      ↓
Location Sampling
      ↓
┌───────────────────────────────┐
│ Distance                      │
│ Time                          │
│ Speed Change                  │
│ Heading Change                │
│ Motion Boundary               │
│ Ignition Boundary             │
│ GPS Recovery                  │
│ Accuracy                      │
│ Drift Detection               │
└───────────────────────────────┘
      ↓
LocationHistory
      ↓
Retention / Partition Management
```

---

# 38. اصل نهایی Sampling

اصل نهایی SANA:

> **Sampling باید داده‌های تکراری و کم‌ارزش را حذف کند، نه اطلاعات معنادار تاریخی را.**

و:

> **Sampling می‌تواند داده را کم کند، ولی هرگز نباید داده‌ای را که Device گزارش نکرده، اختراع کند.**

و:

> **LocationHistory پس از ذخیره Source of Truth تاریخی است و Compression مخرب روی آن انجام نمی‌شود.**

---

# وضعیت

**Location Sampling & Compression — CLOSED ✓**

تمام Decisionهای این بخش تأیید شدند.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی طراحی Partitioning

## 1. هدف

هدف Partitioning در SANA مدیریت حجم بالای `LocationHistory`، بهبود Queryهای تاریخی و ساده‌سازی Retention است.

Partitioning جایگزین Sampling نیست.

معماری:

```text
Smart Sampling
      ↓
LocationHistory
      ↓
PostgreSQL Partitioning
      ↓
Retention Management
```

---

# 2. فقط LocationHistory Partition می‌شود

در MVP فقط:

```text
gps.location_history
```

Partition خواهد شد.

Partitioning برای:

```text
CurrentState
Event
Trip
RawPacket
```

فعلاً انجام نمی‌شود.

اگر حجم واقعی یا الگوی Query در آینده نیاز ایجاد کند، جداگانه بررسی خواهد شد.

---

# 3. نوع Partitioning

نوع Partitioning:

```text
RANGE
```

و کلید:

```text
device_time
```

است.

```text
gps.location_history
        │
        ├── location_history_2026_10
        ├── location_history_2026_11
        ├── location_history_2026_12
        └── ...
```

---

# 4. Partition بر اساس Device نیست

Partitioning بر اساس:

```text
device_id
```

انجام نمی‌شود.

ساختن هزاران Partition برای Deviceهای مختلف باعث افزایش پیچیدگی و هزینه مدیریت می‌شود.

بنابراین:

```text
RANGE(device_time)
```

انتخاب نهایی است.

---

# 5. Granularity

Partitionها به‌صورت ماهانه خواهند بود:

```text
location_history_YYYY_MM
```

مثلاً:

```text
location_history_2026_10
location_history_2026_11
location_history_2026_12
```

Partition روزانه برای MVP بیش از حد ریز است و Partition سالانه برای Retention و مدیریت حجم بیش از حد درشت است.

---

# 6. Parent Table

جدول اصلی:

```text
gps.location_history
```

به‌عنوان Parent Table تعریف می‌شود:

```text
PARTITION BY RANGE (device_time)
```

Application مستقیماً با Child Partitionها کار نمی‌کند.

`sana-gps` همیشه:

```text
INSERT INTO gps.location_history
```

انجام می‌دهد.

PostgreSQL خودش Partition مناسب را انتخاب می‌کند.

---

# 7. Django

Django Model فقط Parent Table را نمایندگی می‌کند.

Child Partitionها Modelهای مستقل Django نیستند.

بنابراین Application یک Entity به نام:

```text
LocationHistory
```

می‌شناسد، نه:

```text
LocationHistory2026October
LocationHistory2026November
...
```

Partition جزئیات PostgreSQL است.

---

# 8. sana-gps و Partition

`sana-gps` هیچ Partition-specific SQL اجرا نمی‌کند.

یعنی نباید مستقیماً با:

```text
location_history_2026_10
```

کار کند.

همچنین `sana-gps` اجازه اجرای:

```text
CREATE
ALTER
DROP
TRUNCATE
CREATE INDEX
```

برای مدیریت Partition را ندارد.

Partitioning برای GPS Runtime کاملاً Transparent است.

---

# 9. Partition Manager

مدیریت Partitionها توسط یک مکانیزم مستقل انجام می‌شود:

```text
Partition Manager / Maintenance
```

مسئولیت‌ها:

```text
Create future partitions
Verify required partitions
Drop expired partitions
Health Check
Logging
```

این بخش از GPS Packet Runtime جدا است.

---

# 10. ایجاد Partition آینده

سیستم باید حداقل Partition مربوط به:

```text
Current Month
Next Month
```

را داشته باشد.

Partition ماه آینده قبل از شروع ماه ایجاد می‌شود.

Maintenance باید بتواند Partitionهای Missing را نیز ایجاد کند.

---

# 11. Bootstrap

در زمان Bootstrap اولیه Database:

```text
Create Schema
    ↓
Create Parent Table
    ↓
Partition Manager
    ↓
Create Current + Next Month
```

Partitionهای موردنیاز ایجاد می‌شوند.

این کار توسط `sana-gps` انجام نمی‌شود.

---

# 12. نبود Partition

اگر Partition موردنیاز وجود نداشته باشد:

```text
INSERT
   ↓
PostgreSQL Error
   ↓
Transaction Failure
```

سیستم نباید در Runtime Partition بسازد.

خطا باید توسط Operational Monitoring تشخیص داده شود.

`sana-gps` نباید برای حل این مشکل DDL اجرا کند.

---

# 13. Default Partition

در MVP:

```text
DEFAULT PARTITION
```

نداریم.

دلیل:

Default Partition می‌تواند Missing Partition را پنهان کند و باعث شود داده به Partition نامشخص منتقل شود.

Missing Partition باید یک خطای قابل مشاهده باشد.

---

# 14. Late Packet

Partition مقصد همیشه بر اساس:

```text
device_time
```

تعیین می‌شود.

مثلاً:

```text
server_received_at = 2026-11-02
device_time        = 2026-10-31
```

Packet در:

```text
location_history_2026_10
```

قرار می‌گیرد.

نه Partition نوامبر.

---

# 15. Late Packet و CurrentState

Late Packet معتبر می‌تواند وارد LocationHistory شود، ولی:

```text
CurrentState Rollback
```

نمی‌کند.

همچنین باعث:

```text
Full Historical Re-sampling
Trip Rebuild
Event Rebuild
Geofence Rebuild
```

در MVP نمی‌شود.

---

# 16. Expired Partition

اگر Partition طبق Retention منقضی شده و حذف شده باشد، Packetی که بعداً مربوط به آن بازه برسد نباید باعث ایجاد مجدد Partition شود.

Retention یک Data Lifecycle Policy است.

داده منقضی‌شده در Historical Storage بازگردانده نمی‌شود.

---

# 17. Future-dated Packet

Timestamp غیرعادی آینده نباید باعث ایجاد Partition آینده شود.

مثلاً:

```text
server_received_at = 2026-10-06
device_time        = 2027-04-10
```

ابتدا در Telemetry Validation بررسی می‌شود.

Partition Manager نیز برای Timestampهای مشکوک Partition ایجاد نمی‌کند.

---

# 18. Index اصلی

Index اصلی هر Partition:

```text
(device_id, device_time)
```

است.

این Index برای Queryهای اصلی:

```text
Device + Time Range
```

استفاده می‌شود.

---

# 19. Indexهای اضافی

در MVP روی این فیلدها Index عمومی ایجاد نمی‌شود:

```text
speed
heading
altitude
battery_voltage
external_voltage
gsm_signal
odometer
engine_hours
fuel_level
ignition
motion
attributes
server_received_at
```

Index جدید فقط زمانی ایجاد می‌شود که Query واقعی و پرتکرار آن را توجیه کند.

---

# 20. Spatial Index

برای:

```text
geom
```

نیز Spatial Index از ابتدا صرفاً به‌صورت پیش‌فرض ایجاد نمی‌شود.

در صورت نیاز واقعی به Queryهای مکانی، GiST Index اضافه خواهد شد.

---

# 21. Unique Constraint

این Constraint وجود ندارد:

```text
UNIQUE(device_id, device_time)
```

چون دو Packet متفاوت می‌توانند Timestamp یکسان داشته باشند.

Packet Identity با:

```text
Sequence
Message ID
Packet ID
Fingerprint
```

مدیریت می‌شود.

---

# 22. Primary Key

هر LocationHistory رکورد همچنان دارای:

```text
id = BIGINT / BigAutoField
```

است.

`device_time` هویت رکورد نیست.

---

# 23. Partition Pruning

Queryهای دارای شرط زمانی باید از Partition Pruning PostgreSQL استفاده کنند.

مثلاً Query:

```text
device_id = 125
device_time BETWEEN X AND Y
```

نباید کل تاریخچه چندساله را بررسی کند.

PostgreSQL ابتدا Partitionهای مرتبط را انتخاب می‌کند و سپس Index:

```text
(device_id, device_time)
```

را استفاده می‌کند.

---

# 24. Retention

Retention `LocationHistory`:

```text
Configurable
Long-Term
```

است.

مبنای Retention:

```text
device_time
```

است.

Retention برای همیشه و بدون محدودیت نیست.

---

# 25. حذف Partition منقضی‌شده

به‌جای:

```text
DELETE میلیون‌ها Row
```

کل Partition منقضی‌شده حذف می‌شود.

مفهوم:

```text
Expired Partition
       ↓
DROP PARTITION
```

این روش سریع‌تر و کم‌هزینه‌تر از حذف Row-by-Row است.

---

# 26. Grace Period

برای جلوگیری از حذف ناگهانی، امکان Grace Period عملیاتی در نظر گرفته می‌شود.

مثلاً:

```text
Retention = 24 months
Grace = 7 days
```

مقدار نهایی Configuration است.

Partition تنها پس از خروج کامل از Retention و پایان Grace Period حذف می‌شود.

---

# 27. Retention مستقل Entityها

Retention موجودیت‌ها مستقل است.

مثلاً:

```text
LocationHistory → 24 months
Trip             → 36 months
Event            → 36 months
RawPacket        → 7 days
```

این اعداد نمونه‌اند و Configuration نهایی نیستند.

بنابراین حذف LocationHistory نباید Trip یا Event را حذف کند.

---

# 28. RawPacket

RawPacket Retention مستقل دارد.

مبنای آن:

```text
server_received_at
```

است.

LocationHistory بر اساس:

```text
device_time
```

مدیریت می‌شود.

---

# 29. RawPacket Dependency

حذف RawPacket نباید باعث حذف یا Invalid شدن:

```text
LocationHistory
Event
Trip
CurrentState
```

شود.

Reference به RawPacket صرفاً برای:

```text
Debug
Audit
Traceability
```

است.

---

# 30. Trip پس از حذف LocationHistory

ممکن است Trip همچنان وجود داشته باشد ولی Route کامل آن دیگر قابل Playback نباشد.

بنابراین:

```text
Trip
✓
```

لزومی ندارد به معنی:

```text
Trip Route
✓ forever
```

باشد.

---

# 31. Partition Safety

قبل از حذف Partition، Partition Manager باید بررسی کند:

```text
1. Partition متعلق به gps.location_history باشد.
2. Default Partition نباشد.
3. Bounds معتبر باشد.
4. کل بازه Partition خارج از Retention باشد.
5. Partition مربوط به Current/Future period نباشد.
6. Grace Period تمام شده باشد.
```

سپس عملیات DROP انجام شود.

---

# 32. Monitoring

Partition Health Check سبک خواهد بود.

موارد اصلی:

```text
Current Month Partition
Next Month Partition
Missing Partition
Expired Partition
Unexpected Partition
Partition Manager Status
```

---

# 33. Metrics

حداقل Metrics پیشنهادی:

```text
partition_manager_last_success
partition_manager_last_failure
location_history_partition_count
location_history_missing_partition
location_history_expired_partition_count
partition_manager_duration
```

---

# 34. Operational Alerts

حداقل خطاهای قابل مشاهده:

```text
Required Partition Missing
Partition Manager Failed
```

Partitionهای غیرمنتظره گزارش می‌شوند ولی خودکار حذف نمی‌شوند.

---

# 35. Startup

هنگام Startup `sana-gps`:

```text
Database Connectivity
Schema Accessibility
```

بررسی می‌شود.

اما:

```text
CREATE PARTITION
DROP PARTITION
ALTER TABLE
```

انجام نمی‌شود.

---

# 36. Partition Naming

الگوی نام:

```text
location_history_YYYY_MM
```

است.

مثلاً:

```text
location_history_2026_10
location_history_2026_11
```

---

# 37. اصل نهایی

Partitioning باید برای `sana-gps` کاملاً Transparent باشد.

از دید GPS Runtime:

```text
gps.location_history
```

یک جدول است.

PostgreSQL مسئول Partition Routing است.

Partition Manager مسئول Lifecycle است.

Monitoring مسئول تشخیص مشکل است.

---

# وضعیت

**Partitioning — CLOSED ✓**

تصمیمات نهایی:

* [✓] فقط LocationHistory Partition می‌شود.
* [✓] نوع RANGE.
* [✓] کلید `device_time`.
* [✓] Partition ماهانه.
* [✓] عدم Partition بر اساس Device.
* [✓] Parent Table واحد.
* [✓] Child Partitionها Model مستقل Django ندارند.
* [✓] `sana-gps` بدون DDL.
* [✓] Partition Manager مستقل.
* [✓] Current + Next Month.
* [✓] بدون Default Partition در MVP.
* [✓] Late Packet بر اساس `device_time`.
* [✓] عدم Rollback CurrentState.
* [✓] عدم Re-sampling کامل تاریخچه در MVP.
* [✓] Index اصلی `(device_id, device_time)`.
* [✓] بدون Unique روی `(device_id, device_time)`.
* [✓] Retention بر اساس `device_time`.
* [✓] حذف Partition به‌جای DELETE عظیم.
* [✓] Retention مستقل Entityها.
* [✓] RawPacket مستقل.
* [✓] Health Check و Monitoring.
* [✓] Partitioning کاملاً Transparent برای GPS Runtime.


============================================================================
============================================================================

# SANA GPS — Protocol Decoder Architecture

## 1. هدف

این سند معماری کامل بخش Protocol Handling در `sana-gps` را مشخص می‌کند.

هدف:

* دریافت TCP/UDP از GPS Device
* تشخیص Protocol
* Framing
* شناسایی Device
* Decode
* Normalization
* Validation
* Deduplication
* Temporal Ordering
* پردازش Bulk
* Persistence
* ACK/Response
* مدیریت Session
* Raw Packet
* Replay

بدون وارد کردن مسئولیت‌های غیرضروری به Protocol Layer.

اصل اصلی:

> **Minimal but Powerful**

معماری باید برای حدود ۱۰٬۰۰۰ دستگاه و رشد تا حدود ۱۵٬۰۰۰ دستگاه مناسب باشد، ولی در MVP از پیچیدگی‌هایی مانند Kafka، RabbitMQ، Redis و Microserviceهای اضافی استفاده نمی‌شود.

---

# 2. مرز sana-gps

`sana-gps` مسئول:

* TCP
* UDP
* Connection
* Session
* Protocol Detection
* Protocol Framing
* Device Identification
* Authentication فنی
* Protocol Decode
* Normalization
* Field Validation
* Deduplication
* Temporal Ordering
* Sampling Decision
* Raw Packet
* CurrentState
* LocationHistory
* Event
* Trip
* Geofence State Processing در صورت نیاز به GPS Processing
* PostgreSQL Persistence
* Protocol ACK/Response

است.

اما مسئول:

* User
* Permission
* Customer
* Organization
* Contract
* Subscription
* Driver Business Logic
* Notification Delivery
* WebSocket Delivery

نیست.

---

# 3. معماری کلی

```text
GPS Device
    ↓
TCP / UDP
    ↓
Connection / Session
    ↓
Protocol Detection
    ↓
Protocol Framing
    ↓
Minimal Identification
    ↓
Device Lookup / Authentication
    ↓
Session Binding
    ↓
Protocol Handler
    ↓
ProtocolMessage
    ↓
Normalization
    ↓
NormalizedTelemetry
    ↓
Field Validation
    ↓
Packet Validity
    ↓
Deduplication
    ↓
Temporal Ordering
    ↓
Sampling
    ↓
PostgreSQL Transaction
    ├── LocationHistory
    ├── CurrentState
    ├── Event
    └── Trip
    ↓ COMMIT
Post-Commit Consumers
    ├── PostgreSQL NOTIFY
    ├── Geofence
    └── Alert
```

---

# 4. Transport

Transport فقط مسئول ارتباط شبکه است.

```text
transport/
├── tcp.py
├── udp.py
└── listener.py
```

مسئولیت‌ها:

* Bind
* Accept
* Receive
* Send
* TCP Buffer
* UDP Datagram
* Connection Lifecycle

Transport نباید:

* Decode کند.
* Device Lookup انجام دهد.
* CurrentState را تغییر دهد.
* Event بسازد.
* Trip بسازد.

---

# 5. Listener

Listener یک Entity مستقل برای Network Ingress است.

مدل مفهومی:

```text
Listener
├── name
├── transport
├── bind_address
├── port
├── enabled
└── allowed_protocols
```

Transport:

```text
TCP
UDP
```

پیش‌فرض:

```text
bind_address = 0.0.0.0
```

Conflict بر اساس:

```text
transport + bind_address + port
```

کنترل می‌شود.

Shared Port از ابتدا قابل پشتیبانی است.

Listener به Device یا DeviceModel وابسته نیست.

---

# 6. Protocol Detection

Protocol Detection مستقل از Decoder است.

نتیجه:

```text
NO_MATCH
MATCH
NEED_MORE_DATA
```

Detection می‌تواند بر اساس:

* Header
* Magic
* Length
* Codec
* Message Structure
* Prefix
* Checksum

باشد.

Port فقط Routing Hint است، نه Authentication.

بعد از اینکه Session به Protocol متصل شد، Protocol برای هر Packet دوباره Detection نمی‌شود.

Protocol Detection نباید برای تشخیص Protocol تمام Decoderها را کامل اجرا کند.

---

# 7. Protocol Registry

Registry در Code قرار دارد.

```text
Protocol Registry
├── teltonika
│   └── TeltonikaHandler
├── gt06
│   └── GT06Handler
└── queclink
    └── QueclinkHandler
```

Database فقط:

```text
Protocol
├── id
├── code
├── name
└── enabled
```

را نگه می‌دارد.

Database هرگز نام Class را نگه نمی‌دارد.

مثلاً:

```text
handler_class =
"sana_gps.teltonika.TeltonikaHandler"
```

مجاز نیست.

Registry:

```text
teltonika
↓
TeltonikaHandler
```

را انجام می‌دهد.

---

# 8. Protocol / DeviceModel / Listener

این سه مفهوم مستقل هستند.

```text
Device
   ↓
DeviceModel
   ↓
Protocol
```

ولی:

```text
Listener
   ↓
Protocol(s)
```

نیز وجود دارد.

یک Protocol می‌تواند توسط چند DeviceModel استفاده شود.

هر DeviceModel قابل استفاده برای GPS باید دقیقاً یک Protocol داشته باشد.

```text
DeviceModel.protocol_id NOT NULL
```

Device خودش Protocol جداگانه ندارد.

Source of Truth:

```text
Device
→ DeviceModel
→ Protocol
```

---

# 9. Protocol Family / Codec / Version

Protocol Family از Codec/Version جداست.

مثلاً:

```text
Teltonika
├── Codec 8
├── Codec 8 Extended
└── Codec 12
```

Codec و Version در MVP Entity مستقل Database نیستند.

تا حد امکان Handler آن‌ها را از Packet تشخیص می‌دهد.

Firmware نیز مفهوم مستقلی است و نباید صرفاً به دلیل تغییر Firmware، Protocol جدید ایجاد شود.

---

# 10. Framing

TCP یک Byte Stream است.

بنابراین:

```text
recv()
```

لزوماً یک Message کامل نیست.

Framer مسئول تبدیل:

```text
bytes
↓
complete protocol frame
```

است.

UDP نیز Datagram را دریافت می‌کند، ولی ممکن است یک Datagram شامل چند Message باشد.

Framer نباید:

* Device Lookup
* Event
* Trip
* Business Logic

انجام دهد.

محدودیت‌های Transport:

```text
max_frame_size
max_buffer_size
frame_timeout
```

باید وجود داشته باشند.

Checksum/CRC نیز در لایه فنی Protocol بررسی می‌شود.

---

# 11. Device Identification

شناسایی Device قبل از Full Decode انجام می‌شود.

```text
Transport
↓
Detection
↓
Framing
↓
Minimal Identification
↓
IMEI / Device Identifier
↓
Device Lookup
↓
Device + Protocol Validation
↓
Full Decode
```

Device باید:

* وجود داشته باشد.
* مجاز/فعال باشد.
* Protocol مورد انتظارش با Protocol شناسایی‌شده یکی باشد.

Unknown Device وارد Full Decode نمی‌شود.

Unknown Device نباید:

* CurrentState
* LocationHistory
* Event
* Trip
* last_seen

را تغییر دهد.

Port احراز هویت نیست.

IMEI شناسه اصلی Gateway است.

---

# 12. Connection و Session

Connection و Session دو مفهوم متفاوت‌اند.

```text
Connection = Transport
Session    = Logical Device/Protocol Binding
```

Session State:

```text
UNIDENTIFIED
ACTIVE
CLOSING
CLOSED
```

یک Device حداکثر یک Session فعال دارد.

اگر Session معتبر جدید ایجاد شود:

```text
New Session
    ↓
Old Session CLOSING
    ↓
Old Connection Close
```

Session و Connection در MVP فقط Runtime هستند و در Database ذخیره نمی‌شوند.

Session Registry در Memory است.

Redis برای این کار در MVP اضافه نمی‌شود.

---

# 13. Session Activity و Device Telemetry

این دو نباید یکی شوند.

```text
last_activity
```

متعلق به Session Runtime است.

```text
last_seen
```

متعلق به CurrentState و وضعیت Telemetry معتبر Device است.

بنابراین ممکن است:

```text
Session = ACTIVE
Device = OFFLINE
```

باشند؛ مثلاً Device Heartbeat می‌فرستد ولی Telemetry ارسال نمی‌کند.

---

# 14. Protocol Handler

هر Protocol یک Handler دارد:

```text
TeltonikaHandler
├── Framer
├── Decoder
└── Normalizer
```

Handler نقطه اتصال اجزای Protocol است.

Protocol-based است، نه DeviceModel-based.

---

# 15. Decoder

Decoder:

```text
Protocol Frame
↓
ProtocolMessage
```

تولید می‌کند.

Decoder مستقیماً `NormalizedTelemetry` نمی‌سازد.

Decoder مسئول:

* Parse
* Decode
* Message Type
* Protocol Metadata

است.

Decoder نباید:

* Database
* CurrentState
* LocationHistory
* Event
* Trip
* Permission

را مدیریت کند.

---

# 16. DecodeResult

خروجی Decoder:

```text
DecodeResult
├── telemetry: list[NormalizedTelemetry]   # legacy conceptual name; actual output is ProtocolMessage list
├── response: ProtocolResponse | None
├── message_type: MessageType
└── metadata: DecodeMetadata
```

با توجه به تصمیم نهایی Decoder/Normalizer، خروجی واقعی Decoder از نظر معماری:

```text
ProtocolMessage[]
```

است و `NormalizedTelemetry` بعد از Normalizer تولید می‌شود.

`DecodeResult` می‌تواند شامل:

```text
ProtocolMessage[]
ProtocolResponse
MessageType
DecodeMetadata
```

باشد.

---

# 17. ProtocolMessage

`ProtocolMessage` یک ساختار داخلی موقت است و Database Entity نیست.

نمونه:

```text
TeltonikaPositionMessage
LoginMessage
HeartbeatMessage
CommandResponseMessage
```

ProtocolMessage می‌تواند:

* Type
* Structured Payload
* Metadata

داشته باشد.

از Dictionary عمومی و بدون Type مشخص به‌عنوان معماری اصلی استفاده نمی‌کنیم.

---

# 18. Non-Telemetry Messages

همه ProtocolMessageها Telemetry نیستند.

مثلاً:

```text
Login
Heartbeat
ACK
Command Response
```

ممکن است هیچ Telemetry نداشته باشند.

مسیر:

```text
ProtocolMessage
├── Telemetry-bearing
│      ↓
│   Normalizer
│      ↓
│   NormalizedTelemetry
│
└── Non-Telemetry
       ↓
    Session / Protocol Handling
```

Login می‌تواند Session را Bind کند.

Heartbeat می‌تواند `last_activity` را تغییر دهد.

Heartbeat معتبر همچنین می‌تواند طبق سیاست ارتباطی SANA، `last_seen` را جلو ببرد؛ اما به‌تنهایی:

* CurrentState telemetry snapshot
* LocationHistory
* Trip
* device_time
* server_received_at مربوط به آخرین Telemetry

را تغییر نمی‌دهد.

یک Message می‌تواند هم Telemetry و هم Response داشته باشد.

---

# 19. Normalizer

Normalizer:

```text
ProtocolMessage
↓
NormalizedTelemetry
```

است.

وظایف:

* Field Mapping
* Unit Conversion
* Representation Conversion
* Structure Conversion

مثلاً:

```text
Raw meters
↓
odometer = kilometers
```

یا:

```text
1 / ON / bit
↓
ignition = true
```

Normalizer مستقیماً Database را Query نمی‌کند.

در صورت نیاز، Context محدود و مشخص دریافت می‌کند:

* Device
* DeviceModel
* Protocol
* Vehicle configuration
* Tank Capacity
* Calibration
* Protocol configuration

---

# 20. NormalizedTelemetry

`NormalizedTelemetry` مدل موقت داخلی SANA است.

Database Entity نیست.

```text
NormalizedTelemetry
├── device_id
├── device_time
├── server_received_at
│
├── latitude
├── longitude
├── gps_valid
├── accuracy
├── altitude
├── satellites
│
├── speed
├── heading
├── motion
├── ignition
│
├── battery_voltage
├── external_voltage
├── gsm_signal
│
├── odometer
├── engine_hours
├── fuel_level
│
└── attributes
```

تمام فیلدها عموماً Nullable هستند.

عدم وجود یک Field به معنی Invalid بودن کل Telemetry نیست.

---

# 21. Standard Units

واحدهای استاندارد SANA:

```text
latitude          → degree
longitude         → degree
altitude          → meter
accuracy          → meter
speed             → km/h
heading           → degree
battery_voltage   → volt
external_voltage  → volt
gsm_signal        → dBm
odometer          → kilometer
engine_hours      → hour
fuel_level        → liter
```

Timestampها:

```text
UTC
```

Boolean و satellites واحد ندارند.

Unit داخل مقدار ذخیره نمی‌شود.

مثلاً:

```text
38.4
```

نه:

```text
"38.4 L"
```

---

# 22. Field Validation

سه مرحله:

```text
Protocol Validation
↓
Field Validation
↓
Packet Validity
```

محدوده‌های پایه:

```text
latitude        -90 .. 90
longitude       -180 .. 180
speed           >= 0
heading         0 <= x < 360
accuracy        >= 0
satellites      >= 0
battery_voltage >= 0
external_voltage >= 0
odometer        >= 0
engine_hours    >= 0
fuel_level      >= 0
```

Altitude می‌تواند منفی باشد.

کاهش Odometer یا Engine Hours به‌تنهایی Field Invalid نیست؛ در Processing بررسی می‌شود.

Overspeed نیز Validation نیست؛ Event Logic است.

---

# 23. Packet Validity

Packet زمانی Valid است که:

* Device شناخته شده باشد.
* Protocol معتبر باشد.
* ساختار صحیح باشد.
* Decode موفق باشد.
* حداقل یک Telemetry قابل پردازش باقی مانده باشد.

GPS No-Fix Packet همچنان می‌تواند Valid باشد.

Duplicate نیز Invalid نیست؛ فقط Side Effect ندارد.

---

# 24. Deduplication

Deduplication قبل از:

```text
Sampling
Event
Trip
Persistence
```

انجام می‌شود.

اولویت:

```text
Protocol Sequence
Message ID
Packet Identity
Protocol Fingerprint
```

`device_time` به‌تنهایی Duplicate Key نیست.

Duplicate هیچ Side Effect جدیدی ایجاد نمی‌کند:

```text
❌ LocationHistory
❌ CurrentState
❌ Event
❌ Trip
❌ last_seen
❌ WebSocket
❌ Geofence
❌ Alert
```

اما در صورت نیاز Protocol:

```text
ACK
```

هنوز می‌تواند ارسال شود.

---

# 25. Temporal Ordering

مرجع اصلی زمان تاریخی:

```text
device_time
```

است.

`server_received_at` زمان واقعی دریافت Packet است و همیشه حفظ می‌شود.

اگر Packet دیررس باشد:

```text
LocationHistory → قابل ثبت
last_seen → قابل به‌روزرسانی
CurrentState → فقط اگر از State فعلی جدیدتر باشد
```

CurrentState هیچ‌وقت Rollback نمی‌شود.

برای `device_time` مساوی، ابتدا Protocol Sequence/Message Identity و سپس `server_received_at` به‌عنوان Tie Breaker استفاده می‌شود.

---

# 26. Bulk / Batch Telemetry

یک Packet می‌تواند چند Message داشته باشد:

```text
Packet
├── Message 1
├── Message 2
├── Message 3
└── ...
```

بنابراین:

```text
1 Packet
→ N ProtocolMessage
→ N NormalizedTelemetry
```

هر Telemetry هویت و Timestamp خودش را دارد.

Telemetryهای Bulk:

* می‌توانند وارد LocationHistory شوند.
* می‌توانند Event تاریخی ایجاد کنند.
* می‌توانند Trip را تکمیل کنند.

اما داده قدیمی نباید CurrentState را Rollback کند.

Sampling فقط LocationHistory را تحت تأثیر قرار می‌دهد.

---

# 27. Bulk Ordering

Packet داخلی ممکن است ترتیب زمانی نداشته باشد:

```text
10:05
10:01
10:03
10:02
```

پس بعد از Deduplication:

```text
10:01
10:02
10:03
10:05
```

پردازش می‌شود.

---

# 28. Bulk Transaction

Batch کوچک می‌تواند یک Transaction باشد.

Batch بزرگ قابلیت Chunk شدن دارد:

```text
Bulk
↓
Chunk 1 → Transaction
Chunk 2 → Transaction
Chunk 3 → Transaction
```

هر Chunk یک واحد Atomic است.

Chunk Size در MVP عدد ثابتی ندارد و بعداً با Load Test تنظیم می‌شود.

---

# 29. CurrentState در Bulk

اگر Batch شامل:

```text
10:01
10:02
...
10:30
```

باشد، لازم نیست CurrentState سی بار Update شود.

Candidate نهایی:

```text
10:30
```

انتخاب می‌شود.

بعد از Commit فقط State نهایی جدید برای WebSocket Signal می‌شود.

---

# 30. ACK / Protocol Response

Decoder فقط Response را تولید می‌کند:

```text
ProtocolResponse
```

Session/Transport آن را ارسال می‌کند.

مثلاً:

```text
ProtocolResponse
├── ACK
├── LOGIN_RESPONSE
├── COMMAND_RESPONSE
└── ...
```

Decoder به Socket دسترسی ندارد.

زمان ارسال ACK به semantics همان Protocol وابسته است.

برای Teltonika در تصمیم نهایی SANA:

```text
Login ACK
→ بعد از پذیرش IMEI/Device معتبر

AVL ACK
→ بعد از موفقیت Transaction و COMMIT

Duplicate
→ در صورت نیاز Protocol می‌تواند ACK دریافت کند،
   ولی هیچ Side Effect جدیدی ایجاد نمی‌کند.
```

Session/Transport مسئول ارسال Response است.

---

# 31. Raw Packet

Raw Packet:

* Immutable
* دارای Retention
* دارای Size Limit
* دارای Rate Limit در شرایط لازم

است.

Raw Packet منبع Business Data نیست.

کاربرد:

```text
Debug
Audit
Protocol Investigation
Replay
```

برای Unknown Device به‌صورت پیش‌فرض ذخیره نمی‌شود.

برای Known Device با Decode Error می‌تواند ذخیره شود.

---

# 32. Replay

Replay در MVP فقط:

```text
RawPacket
↓
Decode
↓
Normalize
↓
Validate
↓
Replay Result
```

است.

Replay نباید:

```text
CurrentState
LocationHistory
Event
Trip
Alert
WebSocket
Session
ACK
```

را تغییر دهد.

Timestamp اصلی:

```text
device_time
server_received_at
```

حفظ می‌شود.

RawPacket در Replay هرگز تغییر نمی‌کند.

Reprocessing کامل Business Data به آینده موکول می‌شود.

---

# 33. Protocol Configuration

Configuration باید:

* Minimal
* Typed
* Explicit

باشد.

Generic Key/Value Configuration در MVP نداریم.

مثلاً:

```text
key = "speed_factor"
value = "0.1"
```

معماری مجاز نیست.

Protocol Mapping و Decode Logic در Code هستند.

Domain Configuration مانند:

```text
tank_capacity
fuel_calibration
```

در Entity/Configuration مربوط به Domain قرار می‌گیرد.

---

# 34. Configuration Precedence

در صورت نیاز واقعی:

```text
Protocol Default
↓
DeviceModel Configuration
↓
Device Override
```

اما این سلسله‌مراتب فقط برای Configurationهایی ساخته می‌شود که واقعاً نیاز داریم.

برای همه چیز از ابتدا Override ایجاد نمی‌کنیم.

---

# 35. Runtime Configuration

مواردی مانند:

```text
max_frame_size
max_buffer_size
frame_timeout
identification_timeout
log_level
```

Runtime Configuration هستند.

در Database Domain ذخیره نمی‌شوند.

---

# 36. Repository Layer

`sana-gps` از Django ORM استفاده نمی‌کند.

Persistence:

```text
Processing
↓
Repository
↓
PostgreSQL
```

Repositoryها سبک هستند:

```text
repositories/
├── device.py
├── current_state.py
├── location_history.py
├── event.py
├── trip.py
└── raw_packet.py
```

Repository نباید Protocol-specific باشد.

مثلاً:

```text
TeltonikaRepository
```

وجود ندارد.

---

# 37. Database

یک Connection Pool برای هر Instance از `sana-gps` داریم.

نه یک Connection برای هر Device.

مثلاً:

```text
sana-gps #1
└── PostgreSQL Pool
```

Transaction مربوط به یک Telemetry/Chunk باید عملیات مرتبط را Atomic نگه دارد.

---

# 38. Post-Commit

Consumerهایی که به Commit نیاز دارند بعد از Commit اجرا می‌شوند.

مثلاً:

```text
PostgreSQL COMMIT
       ↓
NOTIFY
       ↓
sana-backend
       ↓
WebSocket
```

NOTIFY خودش Source of Truth نیست.

CurrentState همچنان Source of Truth است.

---

# 39. WebSocket

WebSocket مستقیماً از `sana-gps` به Browser نمی‌رود.

```text
sana-gps
↓
PostgreSQL
↓
NOTIFY
↓
sana-backend
↓
Permission
↓
WebSocket
↓
sana-panel
```

Permission همیشه در Backend اعمال می‌شود.

`sana-gps` نباید Device غیرمجاز را به Browser ارسال کند، چون اصلاً مسئول Browser Delivery نیست.

---

# 40. ساختار داخلی MVP

ساختار پیشنهادی:

```text
sana-gps/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── transport/
│   │   ├── tcp.py
│   │   ├── udp.py
│   │   └── listener.py
│   │
│   ├── session/
│   │   └── manager.py
│   │
│   ├── protocols/
│   │   ├── base.py
│   │   ├── registry.py
│   │   │
│   │   ├── teltonika/
│   │   │   ├── handler.py
│   │   │   ├── framer.py
│   │   │   ├── decoder.py
│   │   │   └── normalizer.py
│   │   │
│   │   └── gt06/
│   │       ├── handler.py
│   │       ├── framer.py
│   │       ├── decoder.py
│   │       └── normalizer.py
│   │
│   ├── types/
│   │   ├── message.py
│   │   ├── telemetry.py
│   │   └── response.py
│   │
│   ├── processing/
│   │   ├── pipeline.py
│   │   ├── validation.py
│   │   ├── deduplication.py
│   │   ├── ordering.py
│   │   └── sampling.py
│   │
│   ├── repositories/
│   │   ├── device.py
│   │   ├── current_state.py
│   │   ├── location_history.py
│   │   ├── event.py
│   │   ├── trip.py
│   │   └── raw_packet.py
│   │
│   └── database/
│       ├── connection.py
│       └── transaction.py
│
├── tests/
├── requirements.txt
└── README.md
```

فایل یا Package جدید فقط وقتی اضافه می‌شود که Code واقعاً به آن نیاز داشته باشد.

---

# 41. اصول ممنوع

موارد زیر در معماری MVP ممنوع هستند مگر با تصمیم معماری جدید:

```text
❌ Generic Key/Value Protocol Mapping
❌ Protocol Class Name در Database
❌ DeviceModel-based Decoder برای هر Model
❌ Database Query داخل Decoder
❌ Database Query مستقیم از Normalizer
❌ Decoder → Socket
❌ Decoder → Event
❌ Decoder → Trip
❌ Decoder → CurrentState
❌ WebSocket مستقیم از sana-gps
❌ Django ORM در sana-gps
❌ Redis صرفاً برای Session در MVP
❌ Kafka/RabbitMQ بدون نیاز واقعی
❌ Replay با Side Effect
❌ Raw Packet قابل تغییر
❌ CurrentState Rollback
❌ استفاده از device_time به‌عنوان Dedup Key
```

---

# 42. Pipeline نهایی

```text
GPS Device
    ↓
TCP / UDP
    ↓
Connection
    ↓
Session
    ↓
Protocol Detection
    ↓
Framing
    ↓
Minimal Identification
    ↓
Device Lookup
    ↓
Protocol Validation
    ↓
Session Binding
    ↓
Protocol Handler
    ↓
Decoder
    ↓
ProtocolMessage
    ↓
Normalizer
    ↓
NormalizedTelemetry
    ↓
Field Validation
    ↓
Packet Validity
    ↓
Deduplication
    ↓
Temporal Ordering
    ↓
Sampling Decision
    ↓
PostgreSQL Transaction
    ├── LocationHistory
    ├── CurrentState
    ├── Event
    └── Trip
    ↓ COMMIT
    ↓
Post-Commit Consumers
    ├── NOTIFY
    ├── Geofence
    └── Alert
```

---

# 43. اصل نهایی معماری

سه لایه باید همیشه از یکدیگر جدا بمانند:

```text
Raw Protocol Data
        ↓
ProtocolMessage
        ↓
NormalizedTelemetry
        ↓
Domain Processing
        ↓
Persistent State
```

و مهم‌ترین مرز:

> **Protocol Layer فقط باید بداند Device چه چیزی فرستاده است؛ Domain Layer تصمیم می‌گیرد این داده در SANA چه معنایی دارد و چه State/Event/Tripای باید ایجاد یا تغییر کند.**

---

# 44. وضعیت نهایی

تمام تصمیم‌های معماری Protocol Decoder تا این مرحله:

```text
[✓] Decoder Boundary
[✓] Decoder Architecture
[✓] Framing
[✓] DecodeResult
[✓] Protocol Registry
[✓] Device Identification
[✓] Error Handling
[✓] ACK / Response
[✓] Session Lifecycle
[✓] Full Packet Pipeline
[✓] Protocol / DeviceModel / Port
[✓] Protocol Family / Codec / Version
[✓] Protocol Detection
[✓] Listener
[✓] Protocol Entity
[✓] DeviceModel → Protocol
[✓] Codec Configuration
[✓] Decoder vs Normalizer
[✓] ProtocolMessage
[✓] NormalizedTelemetry
[✓] Standard Units
[✓] Field Validation
[✓] Deduplication
[✓] Temporal Ordering
[✓] Normalization / Field Mapping
[✓] Non-Telemetry Messages
[✓] Batch / Bulk Telemetry
[✓] Protocol Configuration
[✓] Replay / Raw Packet
[✓] Internal sana-gps Structure
```

**Protocol Decoder Architecture در این مرحله کامل و آماده ورود به طراحی/پیاده‌سازی است.**


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی Offline Detector و Offline/Online Lifecycle

## 1. مبنای Offline

Offline بر اساس این دو مفهوم تعیین می‌شود:

```text
last_seen
offline_timeout
```

قاعده:

```text
now - last_seen > offline_timeout
→ Device Offline
```

`device_time` معیار Offline نیست.

---

## 2. connection_state

`connection_state` در Database ذخیره نمی‌شود.

Backend آن را محاسبه می‌کند:

```text
last_seen = NULL
→ NEVER_SEEN
```

```text
now - last_seen <= offline_timeout
→ ONLINE
```

```text
now - last_seen > offline_timeout
→ OFFLINE
```

در شرایط Recovery پس از خاموشی کامل Server، وضعیت بازه‌ای که Server در آن قابل مشاهده نبوده، قابل اثبات نیست و نباید به‌صورت Offline قطعی تفسیر شود.

---

## 3. Offline Detector

Offline Detector یک Scheduler مرکزی است.

برای هر Device Timer جداگانه ایجاد نمی‌شود.

ساختار:

```text
Offline Detector
      ↓
Find Candidates
      ↓
Conditional DB Transition
      ↓
DEVICE_OFFLINE Event
```

مثلاً:

```text
OFFLINE_CHECK_INTERVAL = 10 seconds
```

این مقدار قابل تنظیم است.

---

## 4. Batch Processing

Offline Candidateها به‌صورت Batch بررسی می‌شوند.

همه Deviceها در هر Cycle یک‌جا پردازش نمی‌شوند.

مثلاً:

```text
LIMIT 100
LIMIT 500
LIMIT 1000
```

بر اساس Load قابل تنظیم است.

---

## 5. DEVICE_OFFLINE Event

Offline یک State Event است.

مثلاً:

```text
DEVICE_OFFLINE
started_at = 12:05:07
ended_at   = NULL
```

تا زمانی که Device برنگشته، Event جدید ایجاد نمی‌شود.

برای یک Device در هر لحظه حداکثر یک:

```text
DEVICE_OFFLINE
```

فعال وجود دارد.

Partial Unique Constraint از این قانون محافظت می‌کند.

---

## 6. Offline Transition

Offline Detector فقط زمانی اجازه ایجاد Offline Event دارد که `last_seen` واقعاً از Timeout عبور کرده باشد.

مفهوم:

```sql
WHERE device_id = ?
AND last_seen < cutoff
```

اما تصمیم نهایی باید داخل Transaction و با State فعلی Database انجام شود تا Race Condition کنترل شود.

---

## 7. Race با Telemetry / Heartbeat

ممکن است Offline Detector و Communication Activity همزمان اجرا شوند.

مثلاً:

```text
Detector
→ Device appears Offline

همزمان

Heartbeat
→ last_seen = NOW
```

Database باید تضمین کند که نتیجه بر اساس آخرین State واقعی تعیین شود.

اگر Heartbeat/Telemetry ابتدا Commit شود:

```text
last_seen = NOW
```

Offline Detector دیگر نباید Offline Event ایجاد کند.

اگر Offline Transition ابتدا Commit شود، Communication بعدی باید Offline Event را ببندد.

---

## 8. ONLINE Transition

Communication معتبر بعدی باعث پایان Offline می‌شود.

مثلاً:

```text
DEVICE_OFFLINE
started_at = 12:05:07
ended_at   = 12:17:03
```

و در صورت فعال بودن Point Event:

```text
DEVICE_ONLINE
occurred_at = 12:17:03
```

ایجاد می‌شود.

`DEVICE_OFFLINE` و `DEVICE_ONLINE` از نظر مدل Event دو مفهوم مستقل‌اند:

```text
DEVICE_OFFLINE
→ State Event

DEVICE_ONLINE
→ Point Event
```

---

## 9. چه چیزهایی Device را Online می‌کنند؟

### Valid Telemetry

بله:

```text
Valid Telemetry
→ Communication Activity
→ last_seen
→ Online Transition
```

### Valid Heartbeat

بله:

```text
Valid Heartbeat
→ Communication Activity
→ last_seen
→ Online Transition
```

### Login

Login موفق می‌تواند Session را فعال کند و Communication Activity محسوب شود، ولی نباید الزاماً به‌عنوان Telemetry دارای `device_time` یا CurrentState Snapshot تلقی شود.

---

## 10. چه چیزهایی Device را Online نمی‌کنند؟

موارد زیر به‌تنهایی Online Transition ایجاد نمی‌کنند:

```text
Invalid Packet
Malformed Packet
CRC Error
Unknown Device
Unknown Protocol
Decode Failure
Duplicate Packet
ACK sent by Server
Session Close
```

به‌خصوص:

```text
ACK
```

چون ACK از Server به Device ارسال شده و نشان‌دهنده Communication ورودی جدید نیست.

---

## 11. Duplicate

Duplicate Packet نباید:

```text
last_seen
```

را جلو ببرد.

و نباید:

```text
DEVICE_ONLINE
```

ایجاد کند.

مثلاً:

```text
Offline Device
    ↓
Old Packet Replay
    ↓
DUPLICATE
```

نتیجه:

```text
No last_seen update
No Online Transition
```

---

## 12. Heartbeat

Heartbeat اگر Message جدید و معتبر باشد:

```text
Heartbeat
→ last_activity
→ last_seen
→ Online Transition
```

اما اگر همان Heartbeat دوباره Replay شود:

```text
Duplicate Heartbeat
→ No new side effect
```

---

## 13. Session و Offline مستقل هستند

Session:

```text
ACTIVE
FENCED
CLOSED
```

نشان‌دهنده ارتباط منطقی Device با sana-gps است.

اما Offline بر اساس:

```text
last_seen
```

تعیین می‌شود.

بنابراین:

```text
Session CLOSED
```

به‌تنهایی Offline Event ایجاد نمی‌کند.

همچنین:

```text
Session ACTIVE
```

به‌تنهایی تضمین نمی‌کند که Device Online است.

---

## 14. DEVICE_OFFLINE.started_at

زمان شروع Offline برابر زمان تشخیص Server است.

مثلاً:

```text
last_seen = 12:00:00
offline_timeout = 5m
detected_at = 12:05:07
```

پس:

```text
started_at = 12:05:07
```

نه:

```text
12:05:00
```

زیرا Event در زمان تشخیص Server ایجاد شده است.

---

## 15. DEVICE_OFFLINE.ended_at

زمان پایان Offline برابر اولین Communication Activity معتبر بعدی است.

مثلاً:

```text
Offline detected:
12:05:07

Heartbeat:
12:17:03
```

نتیجه:

```text
ended_at = 12:17:03
```

---

## 16. GPS No-Fix

GPS No-Fix با Offline متفاوت است.

```text
gps_valid = false
```

ممکن است در حالی رخ دهد که:

```text
last_seen
```

مرتباً در حال به‌روزرسانی است.

پس:

```text
GPS No-Fix
≠
DEVICE_OFFLINE
```

---

## 17. Server Downtime

اگر کل SANA Server خاموش باشد:

```text
12:00 → Server Down
13:00 → Server Up
```

SANA نمی‌تواند بفهمد Device در این بازه:

```text
Online
Offline
```

بوده است.

بنابراین نباید Offline Event جعلی ایجاد شود.

اصل:

> SANA فقط رخدادی را به‌عنوان Offline ثبت می‌کند که در زمانی که Server واقعاً در حال مشاهده سیستم بوده، بتواند آن را اثبات کند.

---

## 18. server_started_at

در Runtime زمان شروع Server نگهداری می‌شود:

```text
server_started_at
```

این مقدار برای جلوگیری از False Offline در Recovery استفاده می‌شود.

اگر:

```text
last_seen < server_started_at
```

باشد، صرفاً از روی این اختلاف نباید Offline Event ساخته شود.

---

## 19. Startup Recovery

بعد از Restart:

```text
Boot
 ↓
Database
 ↓
Listeners
 ↓
Session Manager
 ↓
Workers
 ↓
Offline Detector
```

Offline Detector نباید بلافاصله تمام Deviceهایی را که قبل از Shutdown دیده شده‌اند Offline کند.

ابتدا باید Communication جدید مشاهده شود.

بعد از آن Monitoring عادی ادامه پیدا می‌کند.

---

## 20. Online بعد از Server Restart

مثلاً:

```text
Server Down
12:00

Server Up
13:00

Device reconnect
13:05
```

می‌توانیم بگوییم:

```text
DEVICE_ONLINE
occurred_at = 13:05
```

اما نمی‌توانیم نتیجه بگیریم:

```text
Device Offline
12:00 → 13:05
```

زیرا وضعیت Device در زمان خاموشی Server قابل مشاهده نبوده است.

---

## 21. Timeout و Check Interval

این دو مقدار مستقل‌اند:

```text
offline_timeout
```

مدت لازم برای Offline شدن.

و:

```text
offline_check_interval
```

فاصله اجرای Detector.

مثلاً:

```text
offline_timeout = 5 minutes
offline_check_interval = 10 seconds
```

در این حالت Detection ممکن است چند ثانیه بعد از عبور Timeout انجام شود.

---

## 22. Offline Timeout Configuration

MVP می‌تواند این ساختار را داشته باشد:

```text
Global Default
       ↓
Device Override
```

مثلاً:

```text
Global = 5 min

Device A = 2 min
Device B = 10 min
```

نیازی به Rule Engine پیچیده برای این Configuration نیست.

---

## 23. Race Protection

Race Condition بین:

```text
Offline Detector
Heartbeat
Telemetry
```

با ترکیب موارد زیر کنترل می‌شود:

```text
PostgreSQL Transaction
Conditional Update
Row Lock where necessary
Partial Unique Constraint
```

PostgreSQL مرجع نهایی وضعیت است.

---

## 24. چند Instance

اگر چند Instance داشته باشیم:

```text
sana-gps #1
sana-gps #2
sana-gps #3
```

هرکدام می‌توانند Candidateهای Offline را بررسی کنند.

اما فقط یک Instance باید بتواند Transition را با موفقیت Commit کند.

Constraint:

```text
UNIQUE(device_id, event_type)
WHERE ended_at IS NULL
```

از ایجاد چند Offline Event فعال جلوگیری می‌کند.

نیازی به Leader Election یا Redis فقط برای Offline Detector در MVP نداریم.

---

## 25. Communication Activity

Communication Activity شامل پیام‌های معتبر ورودی است که نشان می‌دهند Device واقعاً با Server ارتباط داشته است.

نمونه:

```text
Heartbeat
Telemetry
Protocol Login
```

اما هر نوع Message باید بر اساس Protocol مشخص شود که آیا Communication Activity محسوب می‌شود یا خیر.

---

## 26. Telemetry Time و Communication Time

برای Telemetry:

```text
device_time
```

زمان داده از دید Device است.

برای Communication:

```text
server_received_at
```

زمان دریافت در SANA است.

Heartbeat ممکن است فقط:

```text
server_received_at
```

داشته باشد و `device_time` نداشته باشد.

---

## 27. ACK

ACK ارسالی توسط SANA:

```text
ACK
```

هیچ‌وقت به‌تنهایی باعث:

```text
last_seen
Online
```

نمی‌شود.

Online شدن فقط از Communication معتبر ورودی حاصل می‌شود.

---

## 28. اصل نهایی

```text
Session
→ Logical Device Connection

last_seen
→ Last Valid Communication Activity

connection_state
→ Computed

DEVICE_OFFLINE
→ Historical State Event

DEVICE_ONLINE
→ Historical Point Event

Server Downtime
→ Unknown Interval
```

و:

```text
Offline Detection
→ last_seen + timeout

Race Protection
→ PostgreSQL Transaction + Conditional Logic

Duplicate
→ No Communication Transition

Valid Heartbeat
→ Communication Activity

Valid Telemetry
→ Communication Activity

ACK
→ Not Communication Activity
```

# تصمیمات قطعی مرحله ۱۰

1. Offline بر اساس `last_seen` و `offline_timeout` است.
2. `connection_state` در Database ذخیره نمی‌شود.
3. Offline Detector مرکزی و Scheduler-based است.
4. برای هر Device Timer جدا نداریم.
5. Candidateها Batch پردازش می‌شوند.
6. چند Instance می‌توانند Detector داشته باشند.
7. PostgreSQL مرجع نهایی Race و Transition است.
8. فقط یک `DEVICE_OFFLINE` فعال برای هر Device مجاز است.
9. Valid Telemetry می‌تواند Device را Online کند.
10. Valid Heartbeat می‌تواند Device را Online کند.
11. Invalid Packet باعث Online شدن نمی‌شود.
12. Duplicate باعث Online شدن نمی‌شود.
13. ACK باعث Online شدن نمی‌شود.
14. Session Close باعث Offline شدن نمی‌شود.
15. `DEVICE_OFFLINE.started_at` زمان تشخیص Server است.
16. `DEVICE_OFFLINE.ended_at` زمان اولین Communication Activity معتبر بعدی است.
17. `DEVICE_ONLINE` در صورت نیاز Point Event مستقل است.
18. GPS No-Fix برابر Offline نیست.
19. Server Downtime باعث Offline Event جعلی نمی‌شود.
20. `server_started_at` برای جلوگیری از False Offline در Recovery استفاده می‌شود.
21. بعد از Server Restart، وضعیت Device در بازه خاموشی Server Unknown است.
22. Offline Timeout و Check Interval جدا هستند.
23. Offline Timeout می‌تواند Global Default + Device Override داشته باشد.
24. Session و Offline State مستقل هستند.
25. `last_seen` فقط با Communication معتبر جدید جلو می‌رود.
26. PostgreSQL با Transaction/Conditional Logic/Constraint از Race محافظت می‌کند.


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی WebSocket Notification Reliability

## 1. Source of Truth

منبع اصلی وضعیت Live:

```text
PostgreSQL
    ↓
gps.current_state
```

است.

موارد زیر Source of Truth نیستند:

```text
LISTEN / NOTIFY
WebSocket
Frontend Memory
Backend Local Memory
```

---

## 2. نقش LISTEN / NOTIFY

PostgreSQL `LISTEN / NOTIFY` فقط یک Signal است.

مثلاً:

```text
CurrentState changed
        ↓
NOTIFY
        ↓
sana-backend
        ↓
Read CurrentState
```

Notification نباید حامل Full State باشد.

---

## 3. NOTIFY Payload

Payload سبک خواهد بود، مثلاً:

```json
{
  "device_id": 125,
  "state_version": 48291
}
```

هدف Notification فقط اطلاع دادن از تغییر است.

---

## 4. state_version

برای CurrentState یک:

```text
state_version
```

خواهیم داشت.

هر بار که Snapshot واقعاً تغییر کند:

```text
state_version
→ افزایش
```

مثلاً:

```text
100
101
102
103
```

این مقدار Monotonic است.

Gap مجاز است:

```text
100
101
105
109
```

لازم نیست Sequence بدون Gap باشد.

---

## 5. State Version و CurrentState Update

CurrentState همچنان با `device_time` کنترل می‌شود.

مفهوم:

```sql
UPDATE gps.current_state
SET
    ...,
    state_version = nextval(...),
    updated_at = CURRENT_TIMESTAMP
WHERE device_id = ?
  AND (
      device_time IS NULL
      OR device_time < incoming_device_time
  );
```

اگر Update موفق باشد:

```text
Snapshot changed
```

و اگر صفر Row تغییر کند:

```text
Snapshot unchanged
```

---

## 6. NOTIFY فقط برای Snapshot واقعی

برای Packet قدیمی که CurrentState را تغییر نمی‌دهد:

```text
CurrentState
→ unchanged

NOTIFY
→ ارسال نمی‌شود
```

جریان صحیح:

```text
Telemetry
    ↓
Transaction
    ↓
CurrentState Update
    ↓
state_version
    ↓
COMMIT
    ↓
NOTIFY
```

---

## 7. NOTIFY قبل از Commit ممنوع

این ترتیب ممنوع است:

```text
CurrentState Update
    ↓
NOTIFY
    ↓
COMMIT
```

ترتیب صحیح:

```text
CurrentState Update
    ↓
COMMIT
    ↓
NOTIFY
```

زیرا Client نباید Stateای را دریافت کند که Transaction آن Rollback شده است.

---

## 8. Lost Notification

حتی اگر NOTIFY بعد از Commit ارسال شود، ممکن است Backend در همان لحظه:

```text
Restart
Connection Loss
Network Failure
```

داشته باشد.

بنابراین ممکن است:

```text
COMMIT
    ↓
NOTIFY lost
```

اتفاق بیفتد.

معماری نباید به تحویل قطعی NOTIFY وابسته باشد.

---

## 9. Reconciliation

Backend یک مکانیزم Reconciliation خواهد داشت.

مفهوم:

```text
Backend Cursor
      ↓
state_version
      ↓
Find newer CurrentState
```

مثلاً:

```sql
SELECT ...
FROM gps.current_state
WHERE state_version > ?
ORDER BY state_version;
```

هدف Reconciliation:

```text
Lost Notification
        ↓
Detect
        ↓
Read CurrentState
        ↓
WebSocket
```

---

## 10. NOTIFY و Reconciliation

دو مسیر داریم:

### Fast Path

```text
NOTIFY
    ↓
Read CurrentState
    ↓
Permission
    ↓
WebSocket
```

### Reliability Path

```text
Reconciliation
    ↓
Detect newer state
    ↓
Read CurrentState
    ↓
Permission
    ↓
WebSocket
```

بنابراین:

```text
NOTIFY
→ سریع

Reconciliation
→ اطمینان
```

---

## 11. Full CurrentState در WebSocket

WebSocket طبق تصمیم قبلی Full CurrentState ارسال می‌کند.

مثلاً:

```text
device_id
device_time
server_received_at
last_seen
connection_state
position
last_valid_position
speed
heading
motion
ignition
battery
voltage
fuel
engine_hours
...
```

NOTIFY شامل این اطلاعات کامل نیست.

---

## 12. Coalescing

اگر یک Device خیلی سریع چند بار تغییر کند:

```text
version 100
version 101
version 102
version 103
```

لازم نیست WebSocket همه چهار Update را ارسال کند.

Backend می‌تواند آنها را Coalesce کند و فقط:

```text
version 103
```

را ارسال کند.

این فقط مربوط به Live Delivery است.

---

## 13. Coalescing با History متفاوت است

Coalescing WebSocket به معنی حذف History نیست.

تاریخچه همچنان در:

```text
LocationHistory
Event
Trip
```

حفظ می‌شود.

بنابراین:

```text
WebSocket Coalescing
≠
Historical Compression
```

---

## 14. WebSocket Reconnect

اگر Browser قطع شود:

```text
WebSocket
    ↓
Disconnected
```

پس از اتصال مجدد:

```text
Authenticate
    ↓
Permission
    ↓
Subscription
    ↓
Initial CurrentState
```

ارسال می‌شود.

Notificationهای از دست‌رفته Replay نمی‌شوند.

Client فقط وضعیت فعلی را دریافت می‌کند.

---

## 15. WebSocket History Replay ندارد

اگر Client پنج دقیقه Offline بوده باشد و در این مدت صدها State Update اتفاق افتاده باشد، لازم نیست تمام آنها را دریافت کند.

Client فقط:

```text
CurrentState فعلی
```

را می‌گیرد.

اگر History لازم باشد:

```text
LocationHistory API
Event API
Trip API
```

به‌صورت مستقل استفاده می‌شوند.

---

## 16. Backend Restart

بعد از Restart:

```text
sana-backend
    ↓
LISTEN
    ↓
WebSocket Connections
    ↓
Reconnect
    ↓
Authentication
    ↓
Permission
    ↓
Initial State
```

نیازی به Replay کردن Notificationهای قبلی نیست.

---

## 17. Multi-Instance Backend

چند Instance مجاز هستند:

```text
sana-backend #1
sana-backend #2
sana-backend #3
```

هر Instance می‌تواند روی PostgreSQL:

```text
LISTEN gps_current_state_changed
```

داشته باشد.

هر Instance فقط WebSocket Clientهای خودش را مدیریت می‌کند.

---

## 18. Permission

قبل از ارسال CurrentState به Browser:

```text
NOTIFY
    ↓
CurrentState
    ↓
Authentication
    ↓
Permission
    ↓
Subscription
    ↓
WebSocket
```

Device غیرمجاز هرگز نباید ارسال شود.

مخفی کردن Marker در Frontend کافی نیست.

---

## 19. Subscription

WebSocket می‌تواند:

### All Authorized

```text
User
 ↓
All Authorized Devices
```

یا:

### Selected Devices

```text
User
 ↓
Selected Device IDs
```

را دریافت کند.

Permission همیشه بالاتر از Subscription است.

---

## 20. Race در Initial Snapshot

ممکن است هنگام Initial Snapshot:

```text
Backend
→ SELECT CurrentState
```

و همزمان:

```text
GPS
→ CurrentState Update
→ COMMIT
→ NOTIFY
```

اتفاق بیفتد.

این مشکل نیست.

در بدترین حالت:

```text
Initial State
+
New State Notification
```

دریافت می‌شود و Backend می‌تواند State جدید را Coalesce کند.

اگر Notification از دست برود:

```text
Reconciliation
```

آن را جبران می‌کند.

---

## 21. Notification Reliability

SANA تضمین نمی‌کند که هر Intermediate WebSocket Update دقیقاً یک‌بار تحویل شود.

هدف:

```text
Current State Eventually Correct
```

است.

یعنی:

> Client در نهایت باید وضعیت صحیح فعلی Device را داشته باشد، حتی اگر برخی Intermediate Updateها را از دست داده باشد.

---

## 22. Exactly Once

برای WebSocket چنین تضمینی نداریم:

```text
Exactly Once ❌
```

اما:

```text
Current State Convergence ✅
```

داریم.

این مدل برای Live Map مناسب‌تر و بسیار ساده‌تر است.

---

## 23. Database Failure

اگر PostgreSQL Commit نشود:

```text
CurrentState
→ تغییر نکرده
```

و:

```text
NOTIFY
→ ارسال نمی‌شود
```

بنابراین WebSocket نباید Stateای را دریافت کند که Database آن را Commit نکرده است.

---

## 24. History مستقل است

مسیرهای اصلی:

```text
NormalizedTelemetry
       │
       ├── CurrentState
       │
       ├── LocationHistory
       │
       └── Event / Trip
```

WebSocket فقط Projection زنده CurrentState را Delivery می‌کند.

---

# تصمیمات قطعی مرحله ۱۱

1. PostgreSQL CurrentState Source of Truth است.
2. `LISTEN/NOTIFY` فقط Signal است.
3. Full CurrentState داخل NOTIFY قرار نمی‌گیرد.
4. NOTIFY شامل Signal سبک مانند `device_id + state_version` است.
5. CurrentState دارای `state_version` خواهد بود.
6. `state_version` Monotonic است.
7. Gap در State Version مجاز است.
8. State Version فقط هنگام تغییر واقعی Snapshot افزایش می‌یابد.
9. NOTIFY فقط بعد از Commit ارسال می‌شود.
10. Lost Notification ممکن است و معماری باید آن را تحمل کند.
11. Backend مکانیزم Reconciliation دارد.
12. NOTIFY مسیر Fast Path است.
13. Reconciliation مسیر Reliability است.
14. WebSocket Full CurrentState ارسال می‌کند.
15. Updateهای سریع یک Device می‌توانند Coalesce شوند.
16. Coalescing فقط در WebSocket است و History را تغییر نمی‌دهد.
17. WebSocket History Replay ندارد.
18. پس از Reconnect، Initial CurrentState ارسال می‌شود.
19. Backend Restart نیاز به Notification Replay ندارد.
20. Multi-instance Backend پشتیبانی می‌شود.
21. Permission قبل از WebSocket Delivery اعمال می‌شود.
22. Subscription می‌تواند All Authorized یا Selected Devices باشد.
23. WebSocket Exactly-Once نیست.
24. هدف اصلی Current-State Convergence است.
25. Database همچنان مرجع نهایی است.
26. اگر Transaction Rollback شود، Notification نباید State جدیدی را منتشر کند.

# وضعیت

```text
[✓] WebSocket Notification Reliability
[✓] LISTEN / NOTIFY
[✓] state_version
[✓] Lost Notification Recovery
[✓] Reconciliation
[✓] WebSocket Coalescing
[✓] Reconnect
[✓] Multi-Instance Backend
[✓] Permission
[✓] Current-State Convergence

مرحله ۱۱ — CLOSED
```


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی Command Schema و Lifecycle

## 1. تعریف Command

`Command` یک درخواست صریح برای انجام عملیات توسط GPS Device است.

نمونه:

```text
REQUEST_POSITION
REBOOT
OUTPUT_ON
OUTPUT_OFF
SET_OUTPUT
SET_CONFIG
REQUEST_CONFIG
```

Command با موارد زیر متفاوت است:

```text
Telemetry
Event
Alarm
Alert
Notification
```

جریان اصلی:

```text
User / System
    ↓
sana-backend
    ↓
Command
    ↓
sana-gps
    ↓
Device
```

---

# 2. مالکیت Command

Command از نظر Business توسط:

```text
sana-backend
```

ایجاد می‌شود.

`sana-panel` مستقیماً با `sana-gps` ارتباط Commandی ندارد.

`sana-gps` مسئول اجرای فنی Command است، نه Authorization Business.

---

# 3. Permission

Backend قبل از ایجاد Command باید بررسی کند:

```text
User Permission
+
Device Permission
+
Command Permission
+
Business Rules
+
Payload Validation
```

صرفاً داشتن دسترسی مشاهده Device به معنی داشتن اجازه ارسال Command نیست.

---

# 4. sana-gps و Authorization

`sana-gps` تصمیم نمی‌گیرد که User اجازه انجام Command را دارد یا خیر.

این مسئولیت:

```text
sana-backend
```

است.

`sana-gps` فقط موارد فنی را بررسی می‌کند:

```text
Protocol Support
Session Availability
Command Encoding
Device/Protocol Compatibility
Payload Compatibility
```

---

# 5. Database Entity

Command در PostgreSQL ذخیره می‌شود.

جدول:

```text
gps.command
```

دلیل:

* Audit
* Debug
* History
* Recovery بعد از Restart
* وضعیت اجرای Command
* بررسی خطا
* Retry Control

Command Runtime-only نیست.

---

# 6. Command Schema

مدل MVP:

```text
Command
├── id
├── device_id
├── type
├── status
├── source
├── requested_by
├── payload
├── result
├── error_code
├── attempts
├── session_generation
├── created_at
├── updated_at
├── expires_at
├── sent_at
├── acknowledged_at
└── completed_at
```

---

# 7. ID

```text
id
Type: BIGINT
Source: SANA
```

شناسه داخلی Command است.

این شناسه با شناسه Command در Protocol Device یکی نیست.

```text
SANA Command ID
≠
Protocol Command Identity
```

---

# 8. Device

```text
device_id
```

Command مستقیماً به Device تعلق دارد.

رابطه:

```text
gps.command.device_id
        ↓
public.device.id
```

Device نباید در اثر حذف/تعویض Device دیگری به Command جدید تبدیل شود.

Commandهای تاریخی Device قبلی متعلق به همان Device باقی می‌مانند.

---

# 9. Delete Policy

Command History نباید با حذف یا Lifecycle تغییر Device از بین برود.

بنابراین رابطه Device با Command از نوع محافظتی خواهد بود:

```text
ON DELETE PROTECT
```

در عمل نیز حذف فیزیکی Device در Lifecycle اصلی SANA مجاز نیست.

---

# 10. Command Type

`type` یک Code مستقل از Protocol است.

مثلاً:

```text
REQUEST_POSITION
REBOOT
SET_OUTPUT
```

و نه:

```text
TELTONIKA_REBOOT
GT06_REBOOT
```

Backend فقط مفهوم SANA را می‌شناسد.

Protocol-specific encoding در sana-gps انجام می‌شود.

---

# 11. Protocol Translation

جریان:

```text
SANA Command
    ↓
Protocol Encoder
    ↓
Protocol-specific Bytes
    ↓
Session
    ↓
Transport
    ↓
Device
```

Backend نباید Raw Protocol Bytes تولید کند.

---

# 12. Command Payload

`payload` از نوع:

```text
JSONB
```

است.

مثلاً:

```json
{
  "output": 1,
  "value": true
}
```

Payload باید متناسب با Command Type باشد.

Backend مسئول Validation اولیه Payload است.

`sana-gps` نیز هنگام Encode کردن باید Compatibility فنی آن را بررسی کند.

---

# 13. Raw Protocol Data

Raw Protocol Bytes جزو قرارداد اصلی Command نیست.

Command باید Protocol-independent باقی بماند.

در صورت نیاز به Debug اطلاعات خام می‌تواند در مکانیزم‌های فنی جداگانه ثبت شود، اما `gps.command` تبدیل به Storage وابسته به Protocol نمی‌شود.

---

# 14. Result

`result` از نوع:

```text
JSONB
```

است.

برای نگهداری نتیجه یا Response ساختاریافته Device استفاده می‌شود.

مثلاً:

```json
{
  "device_result": "OK"
}
```

Result جایگزین:

```text
Telemetry
Event
```

نیست.

---

# 15. Error Code

خطای Command با Code استاندارد ذخیره می‌شود.

نمونه:

```text
DEVICE_OFFLINE
COMMAND_EXPIRED
COMMAND_CANCELLED
UNSUPPORTED_COMMAND
UNSUPPORTED_PROTOCOL
INVALID_PAYLOAD
SESSION_UNAVAILABLE
SEND_FAILED
ACK_TIMEOUT
DEVICE_REJECTED
PROTOCOL_ERROR
```

متن آزاد Error منبع اصلی تصمیم‌گیری نیست.

---

# 16. Source

منبع ایجاد Command:

```text
USER
SYSTEM
API
```

است.

مثلاً:

```text
source = USER
requested_by = 125
```

یا:

```text
source = SYSTEM
requested_by = NULL
```

---

# 17. requested_by

اگر Command توسط User ایجاد شده باشد:

```text
requested_by
```

برای Audit نگهداری می‌شود.

اگر Command سیستمی باشد:

```text
requested_by = NULL
```

و User مصنوعی ایجاد نمی‌شود.

---

# 18. State Machine

Statusهای اصلی:

```text
PENDING
QUEUED
SENDING
SENT
ACKNOWLEDGED
COMPLETED
FAILED
EXPIRED
CANCELLED
```

---

# 19. PENDING

Command توسط Backend ایجاد شده ولی هنوز توسط sana-gps به‌عنوان Runtime Command پذیرفته نشده است.

```text
PENDING
```

---

# 20. QUEUED

`sana-gps` Command را دریافت و معتبر تشخیص داده است، اما هنوز ارسال نشده است.

مثلاً Device Offline است یا Command دیگری در حال اجراست.

```text
PENDING
    ↓
QUEUED
```

---

# 21. SENDING

یک sana-gps Instance Command را به‌صورت Atomic Claim کرده و مسئول اجرای آن شده است.

```text
QUEUED
    ↓
SENDING
```

در این مرحله سایر Instanceها نباید همان Command را ارسال کنند.

---

# 22. SENT

Bytes با موفقیت به Transport/Socket تحویل داده شده‌اند.

```text
SENDING
    ↓
SENT
```

این وضعیت به معنی موفقیت Device نیست.

---

# 23. ACKNOWLEDGED

Device یک Response/ACK قابل شناسایی و مرتبط با Command ارسال کرده است.

```text
SENT
    ↓
ACKNOWLEDGED
```

ACKNOWLEDGED الزاماً به معنی اجرای کامل Command نیست.

---

# 24. COMPLETED

وقتی موفقیت واقعی عملیات از طریق Protocol Response یا Telemetry قابل اثبات باشد:

```text
ACKNOWLEDGED
    ↓
COMPLETED
```

اگر Protocol فقط ACK داشته باشد و مفهوم Completion نداشته باشد، `ACKNOWLEDGED` می‌تواند آخرین وضعیت قابل اثبات باشد و SANA نباید Completion خیالی ایجاد کند.

---

# 25. FAILED

Command در اثر خطای غیرقابل ادامه Failed می‌شود.

مثلاً:

```text
SEND_FAILED
DEVICE_REJECTED
UNSUPPORTED_COMMAND
PROTOCOL_ERROR
```

---

# 26. EXPIRED

اگر:

```text
now >= expires_at
```

و Command هنوز قابل اجرا نباشد:

```text
EXPIRED
```

می‌شود.

Command Expired دیگر نباید ارسال شود.

---

# 27. CANCELLED

Command قبل از ایجاد Side Effect می‌تواند Cancel شود.

مثلاً:

```text
PENDING
    ↓
CANCELLED
```

یا:

```text
QUEUED
    ↓
CANCELLED
```

Commandی که به Device ارسال شده است با تغییر ساده Status لغو نمی‌شود.

---

# 28. Retry

Retry وابسته به Command Type و Protocol است.

هر Command الزاماً قابل Retry نیست.

نمونه:

```text
REQUEST_POSITION
→ معمولاً Retryable

REBOOT
→ به‌صورت پیش‌فرض Auto Retry ندارد
```

دلیل:

Commandهای Side Effect دار ممکن است Device را واقعاً تحت تأثیر قرار داده باشند ولی ACK به SANA نرسیده باشد.

---

# 29. Attempts

```text
attempts
```

تعداد تلاش‌های ارسال Command را نشان می‌دهد.

مثلاً:

```text
attempts = 3
```

یعنی سه تلاش برای ارسال انجام شده است.

در MVP جدول جداگانه برای هر Attempt ایجاد نمی‌شود.

---

# 30. Retry Policy

Retry Policy در Code و بر اساس Command Type/Protocol تعریف می‌شود.

مثلاً:

```text
retryable
max_attempts
ack_timeout
```

این Policy بخشی از Business History نیست و در Database به‌عنوان Configuration پیچیده ذخیره نمی‌شود.

---

# 31. Session Generation

هنگام Claim Command:

```text
session_generation
```

Session فعلی ثبت می‌شود.

مثلاً:

```text
Command
generation = 42
```

اگر Session به:

```text
generation = 43
```

تغییر کند، Session قدیمی دیگر اجازه ارسال Command را ندارد.

---

# 32. Atomic Claim

Claim باید در PostgreSQL به‌صورت Atomic انجام شود.

مفهوم:

```sql
UPDATE gps.command
SET
    status = 'SENDING',
    attempts = attempts + 1,
    session_generation = ?
WHERE id = ?
  AND status = 'QUEUED'
  AND expires_at > CURRENT_TIMESTAMP;
```

اگر:

```text
rows = 1
```

Claim موفق است.

اگر:

```text
rows = 0
```

Instance مالک Command نیست.

---

# 33. Session Validation قبل از Send

حتی بعد از Claim باید Session دوباره بررسی شود.

چون ممکن است:

```text
Claim
    ↓
Session Fenced
    ↓
Send
```

رخ دهد.

اگر Session دیگر Current نباشد، Command نباید از Connection قدیمی ارسال شود.

---

# 34. One In-Flight Command

در MVP برای هر Device:

```text
Maximum 1 In-Flight Command
```

خواهیم داشت.

یعنی Commandهای زیر:

```text
SENDING
SENT
ACKNOWLEDGED
```

همزمان برای یک Device بیش از یکی نخواهند بود.

Commandهای بعدی در:

```text
QUEUED
```

می‌مانند.

---

# 35. دلیل Sequential بودن

برخی GPS Protocolها:

* Command ID ندارند.
* ACK ساده دارند.
* Correlation ضعیف دارند.
* چند Command همزمان را تضمین نمی‌کنند.

Sequential بودن MVP ریسک Correlation و Race را کاهش می‌دهد.

---

# 36. Offline Device

اگر Device Offline باشد:

```text
Command
    ↓
QUEUED
```

می‌ماند.

تا زمانی که:

```text
expires_at
```

نرسیده باشد.

وقتی Session فعال شود:

```text
QUEUED
    ↓
SENDING
```

---

# 37. Command Expiry

برای هر Command:

```text
expires_at
```

داریم.

Command Scheduler به‌صورت مرکزی Commandهای منقضی‌شده را پیدا می‌کند.

نیازی به Timer جداگانه برای هر Command نیست.

---

# 38. Cancellation

Cancellation فقط قبل از ایجاد Side Effect قابل انجام است.

```text
PENDING → CANCELLED
QUEUED  → CANCELLED
```

ولی:

```text
SENT → CANCELLED
```

مجاز نیست.

اگر Protocol قابلیت Cancel Command داشته باشد، آن یک Command مستقل خواهد بود.

---

# 39. Command Delivery از Backend به sana-gps

مسیر پیشنهادی:

```text
sana-backend
    ↓
INSERT gps.command
    ↓
COMMIT
    ↓
NOTIFY
    ↓
sana-gps
```

`NOTIFY` فقط Signal است.

Database همچنان Source of Truth است.

---

# 40. Command Reconciliation

اگر NOTIFY از دست برود:

```text
sana-gps
```

به‌صورت دوره‌ای Commandهای:

```text
PENDING
QUEUED
```

را بررسی می‌کند.

پس:

```text
NOTIFY
→ Fast Path

Reconciliation
→ Reliability Path
```

---

# 41. Command بعد از Restart

Commandهای Database باقی می‌مانند.

پس از Restart:

```text
sana-gps
    ↓
Command Reconciliation
    ↓
PENDING / QUEUED
```

بررسی می‌شوند.

اما وضعیت:

```text
SENDING
SENT
```

ممکن است در مرز Crash مبهم باشد و نباید کورکورانه دوباره اجرا شود.

---

# 42. Crash Ambiguity

ممکن است:

```text
DB:
SENT

Device:
Command را دریافت کرده

Server:
Crash
```

رخ دهد.

بعد از Restart، SANA نمی‌تواند همیشه تشخیص دهد که Command واقعاً اجرا شده یا نه.

بنابراین Auto Retry برای Commandهای Side Effect دار به‌صورت پیش‌فرض ممنوع است مگر Protocol قابلیت مناسب برای Retry/Idempotency داشته باشد.

---

# 43. Timestampها

Timestampهای Command:

```text
created_at
updated_at
expires_at
sent_at
acknowledged_at
completed_at
```

همگی:

```text
UTC
Server-side
```

هستند.

---

# 44. Device Replacement

Command به Device تعلق دارد.

اگر:

```text
Vehicle A
Device 100
```

تعویض شود با:

```text
Vehicle A
Device 200
```

Commandهای Device 100 به Device 200 منتقل نمی‌شوند.

---

# 45. Command و CurrentState

Command مستقیماً CurrentState را تغییر نمی‌دهد.

مثلاً:

```text
SET_OUTPUT ON
```

نباید باعث شود SANA فوراً:

```text
output = ON
```

را ثبت کند.

جریان صحیح:

```text
Command
    ↓
Device
    ↓
Response / Telemetry
    ↓
Normalization
    ↓
CurrentState / Event
```

---

# 46. Command و Event

این دو مستقل هستند.

مثلاً:

```text
Command:
REBOOT
```

ممکن است بعداً باعث:

```text
Event:
DEVICE_REBOOTED
```

شود.

ولی Command خودش Event نیست.

---

# 47. Command و Alert

Alert نیز Command نیست.

در آینده ممکن است:

```text
Event
    ↓
Alert Rule
    ↓
Alert
    ↓
Automation
    ↓
Command
```

ایجاد شود، ولی این‌ها Entityهای مستقل هستند.

---

# 48. Command Schema نهایی MVP

```text
gps.command
│
├── id                    BIGINT
├── device_id             BIGINT FK
├── type                  CODE
├── status                CODE
├── source                CODE
├── requested_by          BIGINT NULL
├── payload               JSONB
├── result                JSONB NULL
├── error_code            CODE NULL
├── attempts              INTEGER
├── session_generation    BIGINT NULL
│
├── created_at            TIMESTAMPTZ
├── updated_at            TIMESTAMPTZ
├── expires_at            TIMESTAMPTZ
├── sent_at               TIMESTAMPTZ NULL
├── acknowledged_at       TIMESTAMPTZ NULL
└── completed_at          TIMESTAMPTZ NULL
```

---

# 49. State Machine نهایی

```text
                 ┌──────────────┐
                 │   PENDING    │
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │    QUEUED    │
                 └──────┬───────┘
                        │
                  Atomic Claim
                        │
                        ▼
                 ┌──────────────┐
                 │   SENDING    │
                 └──────┬───────┘
                        │
                      send()
                        │
                        ▼
                 ┌──────────────┐
                 │     SENT     │
                 └──────┬───────┘
                        │
                       ACK
                        │
                        ▼
              ┌───────────────────┐
              │   ACKNOWLEDGED    │
              └─────────┬─────────┘
                        │
                   completion
                        │
                        ▼
                 ┌──────────────┐
                 │  COMPLETED   │
                 └──────────────┘
```

خطاها:

```text
PENDING ───────→ CANCELLED
QUEUED ────────→ CANCELLED
QUEUED ────────→ EXPIRED

SENDING ───────→ FAILED
SENT ──────────→ FAILED
SENT ──────────→ QUEUED       (Retry if allowed)

ACKNOWLEDGED ──→ FAILED
ACKNOWLEDGED ──→ COMPLETED
```

---

# 50. قواعد قطعی

1. Command یک Entity مستقل است.
2. Command مستقیماً به Device تعلق دارد.
3. Command توسط sana-backend ایجاد می‌شود.
4. Permission در Backend بررسی می‌شود.
5. sana-gps مسئول Authorization Business نیست.
6. Command در PostgreSQL ذخیره می‌شود.
7. Command History حذف نمی‌شود.
8. Command Type مستقل از Protocol است.
9. Protocol Encoding در sana-gps انجام می‌شود.
10. Payload و Result از نوع JSONB هستند.
11. Raw Protocol Bytes بخشی از Command Contract نیست.
12. `SENT` به معنی موفقیت Device نیست.
13. `ACKNOWLEDGED` با `COMPLETED` متفاوت است.
14. Completion فقط در صورت وجود شواهد معتبر ثبت می‌شود.
15. Command دارای `expires_at` است.
16. Command Claim به‌صورت Atomic انجام می‌شود.
17. Session Generation هنگام Claim و قبل از Send بررسی می‌شود.
18. در MVP حداکثر یک Command In-Flight برای هر Device داریم.
19. Retry وابسته به Command Type/Protocol است.
20. Side-effect Commandها به‌صورت پیش‌فرض Auto Retry نمی‌شوند.
21. Device Offline باعث حذف فوری Command نمی‌شود.
22. Command Expired هرگز ارسال نمی‌شود.
23. Cancellation بعد از ایجاد Side Effect مجاز نیست.
24. Command مستقیماً CurrentState را تغییر نمی‌دهد.
25. Command مستقیماً Event ایجاد نمی‌کند؛ Event در نتیجه واقعی Device ایجاد می‌شود.
26. Device Replacement Commandهای Device قبلی را منتقل نمی‌کند.
27. NOTIFY فقط Signal است.
28. Reconciliation برای Commandهای بدون Notification وجود دارد.
29. Timestampها UTC و Server-side هستند.
30. Crash در مرز Send/DB می‌تواند وضعیت Command را مبهم کند.
31. Retry نباید بدون توجه به Idempotency انجام شود.
32. Commandهای یک Device در MVP Sequential هستند.
33. `requested_by` برای Audit نگهداری می‌شود.
34. Commandهای System می‌توانند بدون User ایجاد شوند.

---

# وضعیت

```text
[✓] Command Entity
[✓] Command Schema
[✓] Command Type
[✓] Command Status
[✓] State Machine
[✓] Atomic Claim
[✓] Session Generation
[✓] Timeout / Expiry
[✓] Retry Policy
[✓] Offline Queue
[✓] Command Reconciliation
[✓] Crash Ambiguity
[✓] Audit
[✓] Device Replacement
[✓] CurrentState Separation

مرحله ۱۳ — CLOSED
```


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی Configuration Lifecycle

## 1. هدف

این سند محل نگهداری Configurationها، مالکیت آن‌ها، نحوه تغییر، Versioning، Audit و زمان اعمال Configuration در SANA GPS را مشخص می‌کند.

اصل کلی:

```text
Environment
→ زیرساخت و Secret

Code
→ منطق ثابت سیستم

Database
→ Configuration قابل مدیریت

Runtime
→ وضعیت لحظه‌ای
```

---

# 2. چهار لایه Configuration و State

SANA چهار مرز مشخص دارد:

```text
┌────────────────────────────┐
│ Environment / Secrets      │
│ .env / Secret Store        │
└──────────────┬─────────────┘
               │
┌──────────────▼─────────────┐
│ Code Configuration         │
│ Decoder / Protocol / CRC   │
└──────────────┬─────────────┘
               │
┌──────────────▼─────────────┐
│ Database Configuration     │
│ Listener / Rules / Timeout │
└──────────────┬─────────────┘
               │
┌──────────────▼─────────────┐
│ Runtime State               │
│ Session / CurrentState      │
└────────────────────────────┘
```

این چهار مفهوم نباید با یکدیگر مخلوط شوند.

---

# 3. Environment Configuration

`.env` فقط برای Configurationهای مربوط به Environment و Infrastructure استفاده می‌شود.

نمونه:

```text
DATABASE_URL
DATABASE_PASSWORD

APP_ENV
DEBUG

LOG_LEVEL

DB_POOL_MIN
DB_POOL_MAX

PROCESSING_WORKERS
MAX_PROCESSING_QUEUE

SECRET_KEY
```

مقادیر می‌توانند بین:

```text
Development
Staging
Production
```

متفاوت باشند.

---

# 4. Secretها

Secretهایی مانند:

```text
Database Password
JWT Secret
API Secret
Encryption Key
```

در PostgreSQL Business Configuration ذخیره نمی‌شوند.

در MVP:

```text
Environment / Secret Store
```

مرجع نگهداری Secretها است.

Secret نباید در:

```text
Log
Audit
Error Message
```

به‌صورت Plain Text ثبت شود.

---

# 5. Configurationهایی که نباید در .env باشند

Configuration مربوط به Device یا Business در `.env` قرار نمی‌گیرد.

مثلاً:

```text
DEVICE_1001_PROTOCOL
DEVICE_1002_PROTOCOL
OFFLINE_TIMEOUT_DEVICE_1001
DEVICE_1001_SAMPLING_INTERVAL
```

مجاز نیست.

این موارد باید در Configuration Layer مناسب خودشان مدیریت شوند.

---

# 6. Code Configuration

چیزهایی که بخشی از Logic نرم‌افزار هستند در Code قرار می‌گیرند.

مثلاً:

```text
Protocol Decoder
Framer
CRC Algorithm
Protocol Encoder
Normalizer
Unit Converter
Protocol Mapping
```

این موارد Business Configuration نیستند.

Admin Panel نباید بتواند منطق Decoder یا الگوریتم CRC را تغییر دهد.

---

# 7. Protocol Profile

Protocol Profileها در Code تعریف می‌شوند.

مثلاً:

```text
TELTONIKA_CODEC8_STANDARD_V1
TELTONIKA_CODEC8_FUEL_V2
GT06_STANDARD_V1
```

Database فقط Reference لازم را نگه می‌دارد:

```text
profile_code
profile_version
```

---

# 8. Profile Immutability

Profile موجود نباید Silent Mutation شود.

مثلاً اگر:

```text
Profile V1
```

امروز یک AVL ID را به:

```text
external_voltage
```

Map کند، نباید فردا همان V1 بدون Version جدید به مفهوم دیگری تغییر کند.

روش صحیح:

```text
Profile V1
Profile V2
```

است.

در نتیجه Telemetryهای تاریخی قابل Trace باقی می‌مانند.

---

# 9. Database Configuration

Configurationهایی که باید بدون تغییر Code قابل مدیریت باشند در Database قرار می‌گیرند.

نمونه:

```text
Listener Configuration
Offline Timeout
Sampling Rules
Event Thresholds
Alert Rules
Geofence Configuration
Raw Packet Retention
Device Overrides
```

این Configurationها از طریق Backend/Admin مدیریت می‌شوند.

---

# 10. Configuration Ownership

هر Configuration باید Owner مشخص داشته باشد.

مثلاً:

```text
Database Password
→ Environment / DevOps

Protocol Decoder
→ Code / Developer

Listener Port
→ System Admin

Device Protocol
→ Device Configuration

Offline Timeout
→ System Configuration

Tank Capacity
→ Vehicle Configuration
```

یک Configuration نباید مالکیت مبهم داشته باشد.

---

# 11. Configuration Scope

Configurationها می‌توانند Scope داشته باشند.

Scopeهای مجاز بسته به نوع Configuration:

```text
GLOBAL
DEVICE_MODEL
DEVICE
VEHICLE
ORGANIZATION
BRANCH
```

اما هر Configuration فقط Scopeهایی را که برای آن تعریف شده‌اند پشتیبانی می‌کند.

همه Configurationها نباید در همه Scopeها قابل Override باشند.

---

# 12. Configuration Precedence

برای Configurationهایی که Override دارند، ترتیب استاندارد:

```text
Global
   ↓
DeviceModel
   ↓
Device
```

است.

مقدار Scope پایین‌تر، مقدار Scope بالاتر را Override می‌کند.

مثال:

```text
Global:
sampling_interval = 30

DeviceModel:
sampling_interval = 15

Device:
sampling_interval = 10
```

Effective Value:

```text
10
```

---

# 13. Inherit / Explicit Disable / Explicit Value

این سه حالت باید از هم جدا باشند:

```text
INHERIT
DISABLED
VALUE
```

مثلاً:

```text
Global = 30 sec

Device = INHERIT
```

نتیجه:

```text
30 sec
```

ولی:

```text
Device = DISABLED
```

به معنی غیرفعال بودن است.

`NULL` نباید به‌صورت عمومی هم معنی Disable تلقی شود.

---

# 14. Configuration Version

Configurationهای مهم دارای Revision هستند.

مثلاً:

```text
revision = 17
```

و بعد:

```text
revision = 18
```

Runtime می‌تواند تشخیص دهد Configuration فعلی مربوط به کدام Revision است.

---

# 15. Configuration History

تغییر Configurationهای مهم باید قابل Audit باشند.

حداقل اطلاعات:

```text
configuration
old_value
new_value
changed_by
changed_at
revision
```

Secretها نباید با مقدار واقعی در Audit ذخیره شوند.

---

# 16. Apply Policy

هر Configuration مشخص می‌کند چه زمانی اعمال می‌شود.

سه حالت مفهومی:

```text
IMMEDIATE
RESTART_REQUIRED
DEPLOY_REQUIRED
```

---

# 17. Immediate

Configurationهایی که Runtime می‌تواند به‌صورت کنترل‌شده Reload کند.

مثلاً:

```text
Offline Timeout
Sampling Rules
Event Threshold
Alert Threshold
```

تغییر می‌کنند و Runtime می‌تواند Configuration جدید را دریافت کند.

---

# 18. Restart Required

Configurationهایی که به Resource یا Socket وابسته‌اند.

مثلاً:

```text
Listener Port
Bind Address
Transport
```

در MVP با:

```text
Database Change
↓
Restart sana-gps
↓
Load New Configuration
```

اعمال می‌شوند.

Hot Reload عمومی برای Listenerها در MVP وجود ندارد.

---

# 19. Deploy Required

Configurationهایی که بخشی از Code هستند:

```text
Decoder
Framer
CRC
Normalizer
Protocol Encoder
Profile Mapping
```

با:

```text
Code Change
↓
Build/Test
↓
Deploy
```

اعمال می‌شوند.

---

# 20. Configuration Validation

Configuration قبل از فعال شدن باید Validate شود.

مثلاً:

```text
Port:
1..65535

Timeout:
> 0

Sampling Distance:
>= 0

Profile:
must exist
```

Configuration نامعتبر نباید وارد Runtime شود.

---

# 21. Atomic Configuration Update

تغییر Configuration باید به‌صورت Atomic انجام شود.

جریان:

```text
New Configuration
       ↓
Validation
       ↓
Database Transaction
       ↓
COMMIT
       ↓
Runtime Apply
```

اگر Validation یا Commit شکست بخورد:

```text
Old Configuration
```

باقی می‌ماند.

---

# 22. Runtime Apply Failure

ممکن است Configuration در Database معتبر باشد ولی Runtime نتواند آن را Apply کند.

در این حالت:

```text
Database
→ New Configuration

Runtime
→ Apply Failed
```

نباید Runtime وارد State نامعلوم شود.

Runtime باید:

```text
Previous Applied Configuration
```

را حفظ کند و خطا را ثبت کند.

بنابراین ممکن است برای مدت کوتاهی:

```text
DB Configuration
≠
Runtime Applied Configuration
```

باشد.

---

# 23. Configuration Cache

Cache در صورت نیاز قابل استفاده است.

اما:

```text
Database
```

همیشه Source of Truth است.

Cache فقط برای:

```text
Performance
```

است.

در صورت از دست رفتن Cache:

```text
Database
↓
Reload
```

انجام می‌شود.

---

# 24. Multi-Instance Configuration

در آینده ممکن است:

```text
sana-gps #1
sana-gps #2
sana-gps #3
```

همزمان فعال باشند.

همه باید Configuration یکسان و قابل Trace داشته باشند.

بنابراین Configuration نباید فقط در Memory یک Instance ذخیره شود.

---

# 25. Configuration Change Notification

برای Configurationهای Runtime می‌توان از PostgreSQL:

```text
LISTEN / NOTIFY
```

استفاده کرد.

جریان:

```text
Admin
 ↓
Database Transaction
 ↓
COMMIT
 ↓
NOTIFY
 ↓
GPS Instances
 ↓
Reload
```

NOTIFY فقط Signal است.

اگر Notification از دست برود:

```text
Periodic Reconciliation
```

Configuration را دوباره بررسی می‌کند.

---

# 26. Configuration Revision

برای تشخیص تغییر Configuration می‌توان Revision داشت:

```text
revision 17
→ offline_timeout = 300

revision 18
→ offline_timeout = 600
```

Runtime Revision فعلی خود را می‌داند.

---

# 27. Listener Configuration

Listener در Database تعریف می‌شود:

```text
Listener
├── id
├── name
├── transport
├── bind_address
├── port
├── enabled
└── allowed_protocols
```

مثلاً:

```text
Teltonika TCP
0.0.0.0:5027
enabled
```

---

# 28. Listener Change

در MVP:

```text
Admin changes Listener
       ↓
Database
       ↓
Restart sana-gps
       ↓
New Listener Configuration
```

Hot Reload عمومی Listener فعلاً وجود ندارد.

---

# 29. Offline Timeout

`offline_timeout` یک Configuration مدیریتی است.

مثلاً:

```text
offline_timeout = 300 seconds
```

در Database نگهداری می‌شود.

Admin می‌تواند آن را تغییر دهد.

این مقدار در `.env` قرار نمی‌گیرد.

---

# 30. Offline Timeout Change

مثلاً:

```text
Old = 5 min
New = 10 min
```

بعد از Apply شدن:

```text
Offline Detection
→ از مقدار جدید استفاده می‌کند.
```

Eventهای تاریخی قبلی دوباره محاسبه نمی‌شوند.

---

# 31. Sampling Configuration

Sampling Configuration شامل مواردی مانند:

```text
min_distance
max_interval
speed_change
heading_change
```

است.

Precedence:

```text
Global
→ DeviceModel
→ Device
```

تغییر Sampling فقط روی Telemetry آینده اثر دارد.

LocationHistory قبلی دوباره Sampling نمی‌شود.

---

# 32. Raw Packet Retention

Raw Packet Retention نیز Configuration است.

مثلاً:

```text
raw_retention = 30 days
```

تغییر آن توسط Admin انجام می‌شود.

Retention Job داده‌های منقضی‌شده را حذف می‌کند.

`sana-gps` خودش مسئول اجرای DDL یا Partition Maintenance نیست.

---

# 33. Device Configuration

Configurationهای فنی Device در Database نگهداری می‌شوند.

مثلاً:

```text
Device
├── profile_code
├── profile_version
├── enabled
└── overrides
```

اما Runtime State با Configuration یکی نیست.

---

# 34. Runtime State ≠ Configuration

Runtime State:

```text
Session
CurrentState
last_seen
Connection State
```

Configuration:

```text
offline_timeout
sampling_rule
profile_code
listener
```

این دو نباید با هم ادغام شوند.

---

# 35. Configuration و Historical Data

تغییر Configuration نباید داده‌های تاریخی را به‌صورت خودکار بازتفسیر کند.

مثلاً:

```text
Profile V1
→ Telemetry گذشته

Profile V2
→ Telemetry آینده
```

Historical Data با Configuration زمان پردازش خودش باقی می‌ماند.

---

# 36. Configuration Traceability

برای Configurationهایی که روی Interpretation داده اثر دارند، امکان Trace Configuration/Version باید وجود داشته باشد.

مثلاً RawPacket:

```text
profile_code
profile_version
```

را نگه می‌دارد.

NormalizedTelemetry نباید با جزئیات غیرضروری Configuration آلوده شود.

---

# 37. Configuration و Device Replacement

Configuration اختصاصی Device با Device دیگری منتقل نمی‌شود مگر اینکه صراحتاً Business Rule مربوط به آن Configuration چنین چیزی را تعریف کند.

مثلاً:

```text
Device 100
sampling_override = 10 sec
```

با تعویض Device:

```text
Device 200
```

این Override به‌صورت خودکار منتقل نمی‌شود.

---

# 38. Generic Key/Value

یک Table عمومی:

```text
key
value
```

نباید محل نگهداری تمام Configurationهای SANA باشد.

برای Configurationهای مهم:

```text
Typed Tables
Typed Fields
```

ترجیح داده می‌شوند.

Generic Key/Value فقط برای موارد ساده و مشخص، در صورت نیاز، قابل استفاده است.

---

# 39. Configuration Security

Admin بودن به‌تنهایی نباید به معنی دسترسی نامحدود Configuration باشد.

در آینده Permissionهای مشخصی مانند:

```text
CONFIG_VIEW
CONFIG_EDIT
GPS_CONFIG_EDIT
PROTOCOL_CONFIG_EDIT
```

قابل تعریف هستند.

---

# 40. Configuration Lifecycle

چرخه کلی:

```text
CREATE
   ↓
VALIDATE
   ↓
ACTIVE
   ↓
UPDATE
   ↓
NEW REVISION
   ↓
ACTIVE
```

Configurationهای مهم History خود را حفظ می‌کنند.

---

# 41. Startup

در Startup:

```text
Environment
    ↓
Typed Settings
    ↓
Database
    ↓
Load Configuration
    ↓
Validate
    ↓
Apply
    ↓
Start Runtime
```

اگر Configuration ضروری Invalid باشد:

```text
Startup Failure
```

به اجرای ناقص ترجیح داده می‌شود.

---

# 42. Configuration Ownership Matrix

| Configuration         | محل                 | مالک تغییر    | Apply             |
| --------------------- | ------------------- | ------------- | ----------------- |
| DB Credentials        | Environment/Secret  | DevOps        | Restart           |
| App Secret            | Environment/Secret  | DevOps        | Restart           |
| Decoder               | Code                | Developer     | Deploy            |
| CRC                   | Code                | Developer     | Deploy            |
| Protocol Mapping      | Code                | Developer     | Deploy            |
| Listener              | DB                  | Admin         | Restart           |
| Offline Timeout       | DB                  | Admin         | Immediate         |
| Sampling              | DB                  | Admin         | Immediate         |
| Event Rules           | DB                  | Admin         | Immediate         |
| Raw Retention         | DB                  | Admin         | Scheduled Job     |
| Device Profile        | DB + Code Reference | Admin/Backend | Controlled Reload |
| Vehicle Tank Capacity | Business DB         | Backend/Admin | Immediate         |

---

# 43. قواعد نهایی

1. `.env` فقط برای Environment و Secret است.
2. Secret در Business Configuration ذخیره نمی‌شود.
3. Protocol Decoder و Logic در Code هستند.
4. Database محل Configurationهای مدیریتی است.
5. Runtime State با Configuration متفاوت است.
6. هر Configuration Owner مشخص دارد.
7. Scope هر Configuration از قبل مشخص می‌شود.
8. Override استاندارد در موارد مجاز: Global → DeviceModel → Device.
9. INHERIT، DISABLED و VALUE از هم جدا هستند.
10. Configurationهای مهم Revision دارند.
11. Configurationهای مهم Audit می‌شوند.
12. Secretها در Audit با مقدار واقعی ذخیره نمی‌شوند.
13. Configuration قبل از Apply Validation می‌شود.
14. تغییر Configuration Atomic است.
15. Runtime Apply Failure نباید Runtime را وارد State نامعلوم کند.
16. Database Source of Truth است.
17. Cache فقط Optimization است.
18. Multi-Instance باید Configuration مشترک داشته باشد.
19. NOTIFY فقط Signal است.
20. Reconciliation مسیر پشتیبان NOTIFY است.
21. Listener Change در MVP نیازمند Restart است.
22. Hot Reload عمومی Listener در MVP نداریم.
23. Configuration Code با Deploy تغییر می‌کند.
24. تغییر Configuration تاریخی را خودکار بازتفسیر نمی‌کند.
25. Profileهای Protocol Immutable هستند.
26. Generic Key/Value برای کل Configuration سیستم استفاده نمی‌شود.
27. Configuration Device به Device دیگری منتقل نمی‌شود مگر با Rule صریح.
28. Configurationهای Runtime قابل Trace و Audit هستند.

---

# وضعیت

```text
[✓] Environment / Secret Boundary
[✓] Code Configuration
[✓] Database Configuration
[✓] Runtime State Boundary
[✓] Configuration Ownership
[✓] Configuration Scope
[✓] Precedence
[✓] Version / Revision
[✓] Audit
[✓] Apply Policy
[✓] Validation
[✓] Atomic Update
[✓] Runtime Reload
[✓] Multi-Instance
[✓] NOTIFY / Reconciliation
[✓] Historical Traceability
[✓] Security Boundary

مرحله ۱۴ — CLOSED
```

**اصل نهایی:**

> `.env` برای Environment، Code برای Logic، PostgreSQL برای Configuration قابل مدیریت و Runtime برای State لحظه‌ای است؛ هیچ‌کدام نباید جای دیگری را بگیرد.`


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی Device Lifecycle و Provisioning

## 1. هدف

این سند چرخه عمر کامل Device در SANA را مشخص می‌کند؛ از ثبت و Provisioning تا فعال‌سازی، نصب روی Vehicle، تعمیر، تعویض و خروج دائمی.

اصل اصلی:

> **Device یک Entity مستقل با هویت مستقل است و Vehicle فقط یکی از ارتباط‌های زمانی آن با سیستم است.**

---

# 2. Device و Vehicle

Device با Vehicle یکی نیست.

```text
Device
   ↓
ممکن است روی Vehicle نصب باشد
```

و:

```text
Vehicle
   ↓
Active Device
```

یک رابطه زمانی/Business است.

Device می‌تواند:

```text
WAREHOUSE
ACTIVE
SUSPENDED
REPAIR
RETIRED
```

باشد، بدون اینکه هویت آن تغییر کند.

---

# 3. IMEI

IMEI شناسه اصلی فنی/Business Device است.

```text
IMEI
   ↓
Device
```

اما:

```text
Device.id
```

Primary Key داخلی Database باقی می‌ماند.

بنابراین:

```text
Device.id
≠
IMEI
```

IMEI باید در Database Unique باشد.

---

# 4. IMEI Immutable بودن

پس از Provision شدن Device، IMEI نباید توسط Runtime یا User عادی تغییر کند.

اصلاح IMEI اشتباه فقط از طریق عملیات مدیریتی کنترل‌شده و Audit‌شده مجاز است.

تغییر عادی Lifecycle نباید باعث تغییر IMEI شود.

---

# 5. Device Status

Status اصلی Business Device دقیقاً شامل این پنج وضعیت است:

```text
WAREHOUSE
ACTIVE
SUSPENDED
REPAIR
RETIRED
```

---

# 6. Connection State مستقل است

موارد زیر Device Status نیستند:

```text
ONLINE
OFFLINE
NEVER_SEEN
```

این‌ها Connection State هستند و از:

```text
last_seen
offline_timeout
```

محاسبه می‌شوند.

بنابراین:

```text
Device Lifecycle Status
≠
Connection State
```

---

# 7. GPS State نیز مستقل است

GPS State نیز با Lifecycle و Connection یکی نیست.

مثلاً کاملاً ممکن است:

```text
Device Status = ACTIVE
Connection     = ONLINE
GPS            = NO_FIX
```

باشد.

سه مفهوم مستقل هستند:

```text
Lifecycle
Connection
GPS
```

---

# 8. WAREHOUSE

Device ثبت‌شده ولی هنوز وارد عملیات فعال نشده است.

مثلاً:

```text
Device 1001
status = WAREHOUSE
```

Device در Warehouse:

```text
Active Vehicle Assignment
```

ندارد.

---

# 9. ACTIVE

Device در وضعیت عملیاتی قرار دارد.

Device فعال می‌تواند:

* Session داشته باشد.
* Telemetry دریافت کند.
* CurrentState داشته باشد.
* LocationHistory تولید کند.
* Event تولید کند.
* روی Vehicle نصب باشد.
* بدون Vehicle نیز موقتاً وجود داشته باشد.

بنابراین:

```text
ACTIVE
```

الزاماً به معنی نصب روی Vehicle نیست.

---

# 10. SUSPENDED

Device موقتاً از عملیات خارج شده است.

مثلاً:

```text
ACTIVE
   ↓
SUSPENDED
```

بعداً می‌تواند:

```text
SUSPENDED
   ↓
ACTIVE
```

شود.

---

# 11. REPAIR

Device برای تعمیر از چرخه عملیاتی خارج شده است.

```text
ACTIVE
   ↓
REPAIR
```

در این وضعیت:

* Device Operational نیست.
* Session فعال نباید باقی بماند.
* Assignment فعال باید بسته شود.
* History حفظ می‌شود.

بعد از تعمیر:

```text
REPAIR
   ↓
WAREHOUSE
```

---

# 12. RETIRED

Device دیگر وارد چرخه عملیاتی نمی‌شود.

```text
RETIRED
```

یک وضعیت نهایی است.

در MVP:

```text
RETIRED
→ Reactivation ندارد.
```

---

# 13. حذف فیزیکی Device

پس از ورود واقعی Device به SANA:

```text
DELETE
```

روش معمول Lifecycle نیست.

به‌جای آن:

```text
RETIRED
```

استفاده می‌شود.

هدف:

* حفظ LocationHistory
* حفظ Event
* حفظ Trip
* حفظ Command
* حفظ Audit
* حفظ هویت Device

---

# 14. Provisioning

Provisioning یعنی ثبت سخت‌افزار واقعی در SANA.

جریان:

```text
Physical Device
      ↓
Register
      ↓
IMEI
      ↓
DeviceModel
      ↓
Protocol/Profile
      ↓
Device
      ↓
WAREHOUSE
```

Unknown Device از طریق Packet به‌صورت خودکار Provision نمی‌شود.

---

# 15. Unknown Device

اگر IMEI در SANA ثبت نشده باشد:

```text
IMEI
 ↓
Device Lookup
 ↓
NOT FOUND
```

نتیجه:

```text
Auto Provisioning = NO
```

Packet نباید وارد Telemetry Processing عادی شود.

---

# 16. Device Registration

برای ثبت Device حداقل اطلاعات:

```text
IMEI
DeviceModel
Status
```

و Configuration فنی موردنیاز ذخیره می‌شود.

پس از ایجاد:

```text
status = WAREHOUSE
```

و Device آماده چرخه Provisioning است.

---

# 17. DeviceModel

DeviceModel نماینده خانواده سخت‌افزاری Device است.

مثلاً:

```text
Teltonika FMB920
GT06 Generic
```

DeviceModel می‌تواند به Protocol/Profile مناسب متصل شود.

جریان:

```text
Device
   ↓
DeviceModel
   ↓
Protocol
   ↓
Codec
   ↓
Profile
```

---

# 18. Activation

Provisioning و Activation یکی نیستند.

مثلاً:

```text
Register
   ↓
WAREHOUSE
   ↓
Vehicle Assignment
   ↓
ACTIVE
```

این تفکیک اجازه می‌دهد Device قبل از نصب یا استفاده در سیستم شناخته‌شده باشد.

---

# 19. DeviceVehicleAssignment

ارتباط Device و Vehicle باید تاریخی باشد.

مدل مفهومی:

```text
DeviceVehicleAssignment
├── id
├── device
├── vehicle
├── started_at
├── ended_at
├── source
└── metadata
```

این Entity تاریخچه نصب Device را نگه می‌دارد.

---

# 20. محدودیت Assignment همزمان

در هر لحظه:

```text
Device
→ حداکثر یک Vehicle
```

و:

```text
Vehicle
→ حداکثر یک Device
```

داریم.

بنابراین Assignmentهای زمانی نباید Overlap داشته باشند.

---

# 21. مثال Assignment

مثلاً:

```text
Device 100
Vehicle A
10:00 → 12:00
```

بعد:

```text
Device 100
Vehicle B
12:00 → 15:00
```

مجاز است.

اما:

```text
Device 100
Vehicle A
10:00 → 12:00

Device 100
Vehicle B
11:00 → 13:00
```

مجاز نیست.

---

# 22. تعویض Device روی Vehicle

مثلاً:

```text
Vehicle A
Device 100
```

تعویض می‌شود:

```text
Vehicle A
Device 200
```

باید:

```text
Assignment Device 100
→ ended_at = T
```

و:

```text
Assignment Device 200
→ started_at = T
```

ثبت شود.

History Device 100 هرگز به Device 200 منتقل نمی‌شود.

---

# 23. CurrentState و Assignment

CurrentState همیشه متعلق به Device است.

```text
Device 100
   ↓
CurrentState 100
```

با تغییر Vehicle:

```text
Device 100
Vehicle A → Vehicle B
```

CurrentState جابه‌جا نمی‌شود.

Vehicle Live View در زمان Query:

```text
Vehicle
   ↓
Active Device Assignment
   ↓
Device
   ↓
CurrentState
```

را Resolve می‌کند.

---

# 24. LocationHistory و Vehicle

LocationHistory نیز Device-owned است.

برای تاریخچه Vehicle:

```text
Vehicle
   ↓
Temporal Assignments
   ↓
Device History
```

ترکیب می‌شود.

بنابراین تعویض Device باعث از بین رفتن تاریخچه Vehicle نمی‌شود.

---

# 25. Device Replacement

Device Replacement یک عملیات مستقل Business است.

مثلاً:

```text
Vehicle A
Device 100
```

تبدیل شود به:

```text
Vehicle A
Device 200
```

اما Deviceهای 100 و 200 دو Entity مستقل باقی می‌مانند.

---

# 26. Return to Warehouse

اگر Device از Vehicle جدا شود و سالم باشد:

```text
ACTIVE
   ↓
WAREHOUSE
```

و Assignment فعال بسته می‌شود.

```text
ended_at = T
```

---

# 27. Return to Repair

اگر Device خراب باشد:

```text
ACTIVE
   ↓
REPAIR
```

Assignment بسته می‌شود.

پس از تعمیر:

```text
REPAIR
   ↓
WAREHOUSE
```

و بعداً می‌تواند دوباره استفاده شود.

---

# 28. Retire

Device می‌تواند از:

```text
WAREHOUSE
REPAIR
SUSPENDED
```

به:

```text
RETIRED
```

برود.

بعد از Retired:

```text
New Session        ❌
New Assignment     ❌
Normal Telemetry   ❌
```

---

# 29. Lifecycle Transition

Transitionهای اصلی:

```text
WAREHOUSE → ACTIVE
ACTIVE → SUSPENDED
SUSPENDED → ACTIVE
ACTIVE → REPAIR
REPAIR → WAREHOUSE

WAREHOUSE → RETIRED
REPAIR → RETIRED
SUSPENDED → RETIRED
```

و:

```text
RETIRED → ACTIVE
RETIRED → REPAIR
```

در MVP مجاز نیستند.

---

# 30. Session Fence

ورود Device به وضعیت غیرعملیاتی:

```text
SUSPENDED
REPAIR
RETIRED
```

باید Session فعلی را:

```text
FENCE
↓
CLOSE
```

کند.

این باعث می‌شود Connection قدیمی نتواند Runtime را ادامه دهد.

---

# 31. Telemetry Device غیرعملیاتی

اگر Device در:

```text
REPAIR
SUSPENDED
RETIRED
```

Packet ارسال کند:

```text
Known Device
but Not Allowed
```

نباید Telemetry عملیاتی ایجاد شود.

یعنی:

```text
CurrentState       ❌
LocationHistory    ❌
Event              ❌
Trip               ❌
```

Packet در صورت نیاز می‌تواند صرفاً برای Security/Debug با Retention مناسب ثبت شود.

---

# 32. Device Lifecycle Event

تاریخچه تغییر Status در Entity مستقل:

```text
DeviceLifecycleEvent
├── id
├── device
├── from_status
├── to_status
├── reason
├── changed_by
├── changed_at
└── metadata
```

ثبت می‌شود.

---

# 33. Lifecycle Event با GPS Event متفاوت است

مثلاً:

```text
Device
ACTIVE
 ↓
REPAIR
```

یک Business/Audit Event است.

بنابراین در:

```text
gps.event
```

قرار نمی‌گیرد.

بلکه:

```text
DeviceLifecycleEvent
```

ثبت می‌شود.

---

# 34. Provisioning Audit

عملیات‌های مهم باید قابل Audit باشند:

```text
Device Created
IMEI Registered
Model Assigned
Activated
Assigned to Vehicle
Removed from Vehicle
Returned to Warehouse
Sent to Repair
Retired
```

---

# 35. IMEI Conflict

Database باید Unique بودن IMEI را enforce کند.

مثلاً:

```text
Device 100 → IMEI A
Device 200 → IMEI A
```

مجاز نیست.

---

# 36. DeviceModel Change

تغییر DeviceModel در Device عملیاتی یک تغییر عادی نیست.

زیرا ممکن است:

```text
Protocol
Codec
Profile
Normalization
```

را تغییر دهد.

بنابراین تغییر DeviceModel باید:

```text
Controlled Administrative Operation
+
Validation
+
Audit
```

باشد.

---

# 37. Profile Change

تغییر Profile نیز باید قابل Trace باشد.

Telemetry تاریخی نباید با Profile جدید بازتفسیر شود.

```text
Profile V1
→ Historical Telemetry

Profile V2
→ Future Telemetry
```

---

# 38. Repair و Identity

Device تعمیرشده همان Device قبلی است.

مثلاً:

```text
Device 100
REPAIR
   ↓
WAREHOUSE
```

شناسه:

```text
Device.id
IMEI
```

تغییر نمی‌کند.

---

# 39. تعویض سخت‌افزار

اگر سخت‌افزار واقعاً تعویض شود و IMEI جدید داشته باشد:

```text
Old Device
IMEI A

New Device
IMEI B
```

این‌ها دو Device مستقل هستند.

حتی اگر هر دو در یک Vehicle استفاده


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی Device Lifecycle و Provisioning

## 1. هدف

این سند چرخه عمر کامل Device در SANA را مشخص می‌کند؛ از ثبت و Provisioning تا فعال‌سازی، نصب روی Vehicle، تعمیر، تعویض و خروج دائمی.

اصل اصلی:

> **Device یک Entity مستقل با هویت مستقل است و Vehicle فقط یکی از ارتباط‌های زمانی آن با سیستم است.**

---

# 2. Device و Vehicle

Device با Vehicle یکی نیست.

```text
Device
   ↓
ممکن است روی Vehicle نصب باشد
```

و:

```text
Vehicle
   ↓
Active Device
```

یک رابطه زمانی/Business است.

Device می‌تواند:

```text
WAREHOUSE
ACTIVE
SUSPENDED
REPAIR
RETIRED
```

باشد، بدون اینکه هویت آن تغییر کند.

---

# 3. IMEI

IMEI شناسه اصلی فنی/Business Device است.

```text
IMEI
   ↓
Device
```

اما:

```text
Device.id
```

Primary Key داخلی Database باقی می‌ماند.

بنابراین:

```text
Device.id
≠
IMEI
```

IMEI باید در Database Unique باشد.

---

# 4. IMEI Immutable بودن

پس از Provision شدن Device، IMEI نباید توسط Runtime یا User عادی تغییر کند.

اصلاح IMEI اشتباه فقط از طریق عملیات مدیریتی کنترل‌شده و Audit‌شده مجاز است.

تغییر عادی Lifecycle نباید باعث تغییر IMEI شود.

---

# 5. Device Status

Status اصلی Business Device دقیقاً شامل این پنج وضعیت است:

```text
WAREHOUSE
ACTIVE
SUSPENDED
REPAIR
RETIRED
```

---

# 6. Connection State مستقل است

موارد زیر Device Status نیستند:

```text
ONLINE
OFFLINE
NEVER_SEEN
```

این‌ها Connection State هستند و از:

```text
last_seen
offline_timeout
```

محاسبه می‌شوند.

بنابراین:

```text
Device Lifecycle Status
≠
Connection State
```

---

# 7. GPS State نیز مستقل است

GPS State نیز با Lifecycle و Connection یکی نیست.

مثلاً کاملاً ممکن است:

```text
Device Status = ACTIVE
Connection     = ONLINE
GPS            = NO_FIX
```

باشد.

سه مفهوم مستقل هستند:

```text
Lifecycle
Connection
GPS
```

---

# 8. WAREHOUSE

Device ثبت‌شده ولی هنوز وارد عملیات فعال نشده است.

مثلاً:

```text
Device 1001
status = WAREHOUSE
```

Device در Warehouse:

```text
Active Vehicle Assignment
```

ندارد.

---

# 9. ACTIVE

Device در وضعیت عملیاتی قرار دارد.

Device فعال می‌تواند:

* Session داشته باشد.
* Telemetry دریافت کند.
* CurrentState داشته باشد.
* LocationHistory تولید کند.
* Event تولید کند.
* روی Vehicle نصب باشد.
* بدون Vehicle نیز موقتاً وجود داشته باشد.

بنابراین:

```text
ACTIVE
```

الزاماً به معنی نصب روی Vehicle نیست.

---

# 10. SUSPENDED

Device موقتاً از عملیات خارج شده است.

مثلاً:

```text
ACTIVE
   ↓
SUSPENDED
```

بعداً می‌تواند:

```text
SUSPENDED
   ↓
ACTIVE
```

شود.

---

# 11. REPAIR

Device برای تعمیر از چرخه عملیاتی خارج شده است.

```text
ACTIVE
   ↓
REPAIR
```

در این وضعیت:

* Device Operational نیست.
* Session فعال نباید باقی بماند.
* Assignment فعال باید بسته شود.
* History حفظ می‌شود.

بعد از تعمیر:

```text
REPAIR
   ↓
WAREHOUSE
```

---

# 12. RETIRED

Device دیگر وارد چرخه عملیاتی نمی‌شود.

```text
RETIRED
```

یک وضعیت نهایی است.

در MVP:

```text
RETIRED
→ Reactivation ندارد.
```

---

# 13. حذف فیزیکی Device

پس از ورود واقعی Device به SANA:

```text
DELETE
```

روش معمول Lifecycle نیست.

به‌جای آن:

```text
RETIRED
```

استفاده می‌شود.

هدف:

* حفظ LocationHistory
* حفظ Event
* حفظ Trip
* حفظ Command
* حفظ Audit
* حفظ هویت Device

---

# 14. Provisioning

Provisioning یعنی ثبت سخت‌افزار واقعی در SANA.

جریان:

```text
Physical Device
      ↓
Register
      ↓
IMEI
      ↓
DeviceModel
      ↓
Protocol/Profile
      ↓
Device
      ↓
WAREHOUSE
```

Unknown Device از طریق Packet به‌صورت خودکار Provision نمی‌شود.

---

# 15. Unknown Device

اگر IMEI در SANA ثبت نشده باشد:

```text
IMEI
 ↓
Device Lookup
 ↓
NOT FOUND
```

نتیجه:

```text
Auto Provisioning = NO
```

Packet نباید وارد Telemetry Processing عادی شود.

---

# 16. Device Registration

برای ثبت Device حداقل اطلاعات:

```text
IMEI
DeviceModel
Status
```

و Configuration فنی موردنیاز ذخیره می‌شود.

پس از ایجاد:

```text
status = WAREHOUSE
```

و Device آماده چرخه Provisioning است.

---

# 17. DeviceModel

DeviceModel نماینده خانواده سخت‌افزاری Device است.

مثلاً:

```text
Teltonika FMB920
GT06 Generic
```

DeviceModel می‌تواند به Protocol/Profile مناسب متصل شود.

جریان:

```text
Device
   ↓
DeviceModel
   ↓
Protocol
   ↓
Codec
   ↓
Profile
```

---

# 18. Activation

Provisioning و Activation یکی نیستند.

مثلاً:

```text
Register
   ↓
WAREHOUSE
   ↓
Vehicle Assignment
   ↓
ACTIVE
```

این تفکیک اجازه می‌دهد Device قبل از نصب یا استفاده در سیستم شناخته‌شده باشد.

---

# 19. DeviceVehicleAssignment

ارتباط Device و Vehicle باید تاریخی باشد.

مدل مفهومی:

```text
DeviceVehicleAssignment
├── id
├── device
├── vehicle
├── started_at
├── ended_at
├── source
└── metadata
```

این Entity تاریخچه نصب Device را نگه می‌دارد.

---

# 20. محدودیت Assignment همزمان

در هر لحظه:

```text
Device
→ حداکثر یک Vehicle
```

و:

```text
Vehicle
→ حداکثر یک Device
```

داریم.

بنابراین Assignmentهای زمانی نباید Overlap داشته باشند.

---

# 21. مثال Assignment

مثلاً:

```text
Device 100
Vehicle A
10:00 → 12:00
```

بعد:

```text
Device 100
Vehicle B
12:00 → 15:00
```

مجاز است.

اما:

```text
Device 100
Vehicle A
10:00 → 12:00

Device 100
Vehicle B
11:00 → 13:00
```

مجاز نیست.

---

# 22. تعویض Device روی Vehicle

مثلاً:

```text
Vehicle A
Device 100
```

تعویض می‌شود:

```text
Vehicle A
Device 200
```

باید:

```text
Assignment Device 100
→ ended_at = T
```

و:

```text
Assignment Device 200
→ started_at = T
```

ثبت شود.

History Device 100 هرگز به Device 200 منتقل نمی‌شود.

---

# 23. CurrentState و Assignment

CurrentState همیشه متعلق به Device است.

```text
Device 100
   ↓
CurrentState 100
```

با تغییر Vehicle:

```text
Device 100
Vehicle A → Vehicle B
```

CurrentState جابه‌جا نمی‌شود.

Vehicle Live View در زمان Query:

```text
Vehicle
   ↓
Active Device Assignment
   ↓
Device
   ↓
CurrentState
```

را Resolve می‌کند.

---

# 24. LocationHistory و Vehicle

LocationHistory نیز Device-owned است.

برای تاریخچه Vehicle:

```text
Vehicle
   ↓
Temporal Assignments
   ↓
Device History
```

ترکیب می‌شود.

بنابراین تعویض Device باعث از بین رفتن تاریخچه Vehicle نمی‌شود.

---

# 25. Device Replacement

Device Replacement یک عملیات مستقل Business است.

مثلاً:

```text
Vehicle A
Device 100
```

تبدیل شود به:

```text
Vehicle A
Device 200
```

اما Deviceهای 100 و 200 دو Entity مستقل باقی می‌مانند.

---

# 26. Return to Warehouse

اگر Device از Vehicle جدا شود و سالم باشد:

```text
ACTIVE
   ↓
WAREHOUSE
```

و Assignment فعال بسته می‌شود.

```text
ended_at = T
```

---

# 27. Return to Repair

اگر Device خراب باشد:

```text
ACTIVE
   ↓
REPAIR
```

Assignment بسته می‌شود.

پس از تعمیر:

```text
REPAIR
   ↓
WAREHOUSE
```

و بعداً می‌تواند دوباره استفاده شود.

---

# 28. Retire

Device می‌تواند از:

```text
WAREHOUSE
REPAIR
SUSPENDED
```

به:

```text
RETIRED
```

برود.

بعد از Retired:

```text
New Session        ❌
New Assignment     ❌
Normal Telemetry   ❌
```

---

# 29. Lifecycle Transition

Transitionهای اصلی:

```text
WAREHOUSE → ACTIVE
ACTIVE → SUSPENDED
SUSPENDED → ACTIVE
ACTIVE → REPAIR
REPAIR → WAREHOUSE

WAREHOUSE → RETIRED
REPAIR → RETIRED
SUSPENDED → RETIRED
```

و:

```text
RETIRED → ACTIVE
RETIRED → REPAIR
```

در MVP مجاز نیستند.

---

# 30. Session Fence

ورود Device به وضعیت غیرعملیاتی:

```text
SUSPENDED
REPAIR
RETIRED
```

باید Session فعلی را:

```text
FENCE
↓
CLOSE
```

کند.

این باعث می‌شود Connection قدیمی نتواند Runtime را ادامه دهد.

---

# 31. Telemetry Device غیرعملیاتی

اگر Device در:

```text
REPAIR
SUSPENDED
RETIRED
```

Packet ارسال کند:

```text
Known Device
but Not Allowed
```

نباید Telemetry عملیاتی ایجاد شود.

یعنی:

```text
CurrentState       ❌
LocationHistory    ❌
Event              ❌
Trip               ❌
```

Packet در صورت نیاز می‌تواند صرفاً برای Security/Debug با Retention مناسب ثبت شود.

---

# 32. Device Lifecycle Event

تاریخچه تغییر Status در Entity مستقل:

```text
DeviceLifecycleEvent
├── id
├── device
├── from_status
├── to_status
├── reason
├── changed_by
├── changed_at
└── metadata
```

ثبت می‌شود.

---

# 33. Lifecycle Event با GPS Event متفاوت است

مثلاً:

```text
Device
ACTIVE
 ↓
REPAIR
```

یک Business/Audit Event است.

بنابراین در:

```text
gps.event
```

قرار نمی‌گیرد.

بلکه:

```text
DeviceLifecycleEvent
```

ثبت می‌شود.

---

# 34. Provisioning Audit

عملیات‌های مهم باید قابل Audit باشند:

```text
Device Created
IMEI Registered
Model Assigned
Activated
Assigned to Vehicle
Removed from Vehicle
Returned to Warehouse
Sent to Repair
Retired
```

---

# 35. IMEI Conflict

Database باید Unique بودن IMEI را enforce کند.

مثلاً:

```text
Device 100 → IMEI A
Device 200 → IMEI A
```

مجاز نیست.

---

# 36. DeviceModel Change

تغییر DeviceModel در Device عملیاتی یک تغییر عادی نیست.

زیرا ممکن است:

```text
Protocol
Codec
Profile
Normalization
```

را تغییر دهد.

بنابراین تغییر DeviceModel باید:

```text
Controlled Administrative Operation
+
Validation
+
Audit
```

باشد.

---

# 37. Profile Change

تغییر Profile نیز باید قابل Trace باشد.

Telemetry تاریخی نباید با Profile جدید بازتفسیر شود.

```text
Profile V1
→ Historical Telemetry

Profile V2
→ Future Telemetry
```

---

# 38. Repair و Identity

Device تعمیرشده همان Device قبلی است.

مثلاً:

```text
Device 100
REPAIR
   ↓
WAREHOUSE
```

شناسه:

```text
Device.id
IMEI
```

تغییر نمی‌کند.

---

# 39. تعویض سخت‌افزار

اگر سخت‌افزار واقعاً تعویض شود و IMEI جدید داشته باشد:

```text
Old Device
IMEI A

New Device
IMEI B
```

این‌ها دو Device مستقل هستند.

حتی اگر هر دو در یک Vehicle استفاده شده باشند، تاریخچه Assignment مرز آن‌ها را مشخص می‌کند.

---

# 40. Subscription و Device Lifecycle

Subscription مالک Lifecycle فیزیکی Device نیست.

Subscription و Device Lifecycle دو Domain مستقل‌اند.

```text
Subscription
→ Service / Commercial State

Device Lifecycle
→ Physical / Operational State
```

---

# 41. Warehouse و Subscription

Device می‌تواند در Warehouse باشد بدون اینکه Subscription فعال داشته باشد.

بعداً:

```text
Subscription
+
Vehicle
+
Device Assignment
```

می‌توانند در فرآیند فروش/فعال‌سازی به هم متصل شوند.

---

# 42. ACTIVE بدون Vehicle

وجود:

```text
ACTIVE
+
No Vehicle
```

مجاز است.

موارد کاربرد:

* Device تستی
* Device آماده نصب
* Device آزمایشی
* Device مستقل

Lifecycle Device نباید به Vehicle وابسته باشد.

---

# 43. WAREHOUSE و Assignment

Invariant:

```text
Device.status = WAREHOUSE
```

باید به معنی:

```text
No Active Vehicle Assignment
```

باشد.

---

# 44. Device Status و Assignment

برای:

```text
ACTIVE
```

وجود Vehicle الزامی نیست.

اما اگر Assignment فعال وجود داشته باشد:

```text
Device → max 1 Vehicle
Vehicle → max 1 Device
```

باید برقرار باشد.

---

# 45. State Machine

```text
                         ┌─────────────┐
                         │  WAREHOUSE  │
                         └──────┬──────┘
                                │
                           activate
                                │
                                ▼
                         ┌─────────────┐
              ┌──────────│    ACTIVE   │──────────┐
              │          └──────┬──────┘          │
              │                 │                 │
          suspend            repair           retire
              │                 │                 │
              ▼                 ▼                 ▼
       ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
       │  SUSPENDED  │   │    REPAIR   │   │   RETIRED   │
       └──────┬──────┘   └──────┬──────┘   └─────────────┘
              │                 │
            resume           repaired
              │                 │
              ▼                 ▼
           ACTIVE           WAREHOUSE
```

---

# 46. تفکیک سه State اصلی

SANA سه مفهوم مستقل دارد:

```text
Device Lifecycle
    ↓
WAREHOUSE / ACTIVE / ...

Connection State
    ↓
NEVER_SEEN / ONLINE / OFFLINE

GPS State
    ↓
VALID / NO_FIX
```

هیچ‌کدام جایگزین دیگری نیست.

---

# 47. مدل نهایی Device

```text
Device
├── id
├── imei
├── device_model
├── status
├── created_at
├── updated_at
└── ...
```

در کنار:

```text
DeviceLifecycleEvent
```

برای تاریخچه Status،

و:

```text
DeviceVehicleAssignment
```

برای تاریخچه نصب روی Vehicle.

---

# 48. قواعد نهایی

1. Device یک Entity مستقل است.
2. Vehicle مالک Device نیست.
3. IMEI شناسه اصلی فنی/Business Device است.
4. Device.id شناسه داخلی Database است.
5. IMEI Unique است.
6. IMEI در Lifecycle عادی تغییر نمی‌کند.
7. Device Status دقیقاً شامل WAREHOUSE، ACTIVE، SUSPENDED، REPAIR و RETIRED است.
8. ONLINE/OFFLINE/NEVER_SEEN جزء Device Status نیستند.
9. GPS State نیز مستقل از Device Status است.
10. Unknown Device خودکار Provision نمی‌شود.
11. Device بعد از ثبت فیزیکی Delete نمی‌شود و در صورت خروج RETIRED می‌شود.
12. WAREHOUSE فاقد Active Vehicle Assignment است.
13. ACTIVE می‌تواند بدون Vehicle باشد.
14. Device و Vehicle رابطه زمانی دارند.
15. Device در هر لحظه حداکثر یک Vehicle دارد.
16. Vehicle در هر لحظه حداکثر یک Device دارد.
17. Assignmentهای زمانی نباید Overlap داشته باشند.
18. Device Replacement تاریخچه Device قبلی را منتقل نمی‌کند.
19. CurrentState همیشه متعلق به Device باقی می‌ماند.
20. LocationHistory همیشه متعلق به Device باقی می‌ماند.
21. Lifecycle History در `DeviceLifecycleEvent` نگهداری می‌شود.
22. Lifecycle Event با GPS Event یکی نیست.
23. ورود به SUSPENDED/REPAIR/RETIRED باعث Fence/Close Session می‌شود.
24. Device غیرعملیاتی نباید Telemetry عملیاتی تولید کند.
25. DeviceModel Change باید کنترل‌شده و Audit‌شده باشد.
26. Profile Change باید Versioned و قابل Trace باشد.
27. Device تعمیرشده همان Device قبلی است.
28. سخت‌افزار جدید با IMEI جدید یک Device جدید است.
29. Subscription مالک Device Lifecycle نیست.
30. RETIRED در MVP وضعیت نهایی است.
31. RETIRED در MVP Reactivation ندارد.
32. Lifecycle Transitionها باید توسط Backend و Database قابل کنترل باشند.
33. Lifecycleهای مهم باید Audit شوند.

---

# وضعیت

```text
[✓] Device Identity
[✓] IMEI
[✓] Provisioning
[✓] Device Status
[✓] Connection State Separation
[✓] GPS State Separation
[✓] Warehouse
[✓] Activation
[✓] Suspension
[✓] Repair
[✓] Retirement
[✓] Unknown Device Policy
[✓] Device Replacement
[✓] Vehicle Assignment Boundary
[✓] Session Fencing
[✓] Lifecycle Audit
[✓] DeviceModel Change
[✓] Profile Change
[✓] Subscription Separation

مرحله ۱۵ — CLOSED
```

**اصل نهایی:**

> **Device هویت مستقل و تاریخی خود را حفظ می‌کند؛ Lifecycle، Connection و GPS State سه مفهوم مستقل‌اند؛ و هیچ تعویض Vehicle یا سخت‌افزار نباید باعث انتقال یا تخریب تاریخچه Device شود.**


============================================================================
============================================================================

# SANA GPS — طراحی نهایی PostgreSQL Schema

## مرحله ۱۷ — نقشه نهایی Schema بخش GPS

## 1. هدف

این سند ساختار نهایی Schema مربوط به GPS در PostgreSQL را مشخص می‌کند.

هدف:

* مشخص شدن Entityهای دائمی GPS
* مشخص شدن مالکیت هر جدول
* مشخص شدن FKها
* مشخص شدن `ON DELETE`
* مشخص شدن Indexها
* مشخص شدن Constraintها
* تفکیک Runtime از Historical Data
* مشخص شدن Partitioning
* جلوگیری از Duplicate Source of Truth
* آماده‌سازی برای Migration واقعی

اصل:

> **Schema باید حداقل ساختار لازم برای اجرای SANA GPS را داشته باشد، ولی از ابتدا باید Integrity و Scale موردنیاز را تضمین کند.**

---

# 2. Database مشترک

SANA در MVP یک PostgreSQL Database دارد:

```text
sana_db
```

ولی داده‌ها از نظر منطقی با Schema جدا می‌شوند.

```text
PostgreSQL
│
├── public
│   └── Business / Core Data
│
└── gps
    └── GPS Data
```

Database جدا برای `sana-gps` در MVP نداریم.

---

# 3. Schema اصلی GPS

Schema:

```text
gps
```

مالک آن:

```text
sana_owner
```

است.

Runtime Role:

```text
sana_gps
```

مالک Schema نیست.

---

# 4. Entityهای دائمی GPS

Entityهای اصلی:

```text
gps.current_state
gps.location_history

gps.event
gps.trip

gps.raw_packet

gps.geofence
gps.geofence_version
gps.geofence_assignment
gps.vehicle_geofence_state

gps.device_vehicle_assignment

gps.command
```

این‌ها داده‌هایی هستند که باید در Database باقی بمانند.

---

# 5. Runtime-only Data

موارد زیر در MVP جدول دائمی ندارند:

```text
Session
TCP Connection
UDP Connection
Listener Runtime
Worker
Processing Queue
Protocol Registry
Decoder Runtime State
```

این موارد در Runtime `sana-gps` مدیریت می‌شوند.

اگر در آینده نیاز واقعی ایجاد شود، برخی Runtime Stateها می‌توانند به Storage مستقل منتقل شوند.

---

# 6. Business Data در public

داده‌های اصلی Business در:

```text
public
```

باقی می‌مانند.

نمونه:

```text
public.device
public.device_model
public.vehicle
public.accounts_user
...
```

GPS به این Entityها Reference می‌دهد ولی مالک آن‌ها نیست.

---

# 7. Cross-Schema Foreign Key

FK واقعی PostgreSQL بین Schemaها استفاده می‌شود.

مثلاً:

```text
gps.current_state.device_id
        ↓
public.device.id
```

و:

```text
gps.location_history.device_id
        ↓
public.device.id
```

این FKها Database Integrity را تضمین می‌کنند.

---

# 8. DeviceVehicleAssignment

رابطه زمانی Device و Vehicle:

```text
gps.device_vehicle_assignment
```

است.

مدل:

```text
DeviceVehicleAssignment
├── id
├── device_id
├── vehicle_id
├── started_at
├── ended_at
├── source
├── changed_by_id
├── metadata
├── created_at
└── updated_at
```

---

# 9. Assignment Foreign Keys

```text
device_id
→ public.device.id
```

و:

```text
vehicle_id
→ public.vehicle.id
```

هر دو:

```text
ON DELETE RESTRICT / PROTECT
```

هستند.

Device یا Vehicle نباید با حذف فیزیکی، History را خراب کنند.

---

# 10. Assignment Temporal Constraint

بازه زمانی:

```text
[started_at, ended_at)
```

است.

قاعده:

```text
Same Device
→ No overlapping assignments

Same Vehicle
→ No overlapping assignments
```

PostgreSQL با:

```text
EXCLUDE USING GIST
```

این Integrity را enforce می‌کند.

---

# 11. Assignment Indexها

Indexهای اصلی:

```text
(device_id, started_at)
(vehicle_id, started_at)
```

و برای Assignment فعال:

```text
(device_id)
WHERE ended_at IS NULL
```

و:

```text
(vehicle_id)
WHERE ended_at IS NULL
```

---

# 12. CurrentState

جدول:

```text
gps.current_state
```

یک Read Model است.

رابطه:

```text
public.device
      │
      └── 1 : 1
           │
           ▼
    gps.current_state
```

---

# 13. CurrentState Schema

ساختار:

```text
current_state
├── id
├── device_id
│
├── device_time
├── server_received_at
├── last_seen
├── updated_at
│
├── latitude
├── longitude
├── geom
├── gps_valid
├── accuracy
│
├── last_valid_latitude
├── last_valid_longitude
├── last_valid_geom
├── last_valid_device_time
├── last_valid_server_received_at
├── last_valid_accuracy
│
├── speed
├── heading
├── altitude
├── motion
├── ignition
├── satellites
│
├── battery_voltage
├── external_voltage
├── gsm_signal
│
├── odometer
├── engine_hours
├── fuel_level
│
└── attributes
```

---

# 14. CurrentState Constraints

```text
device_id UNIQUE NOT NULL
```

و:

```text
FOREIGN KEY
→ public.device.id
ON DELETE CASCADE
```

CurrentState قابل Rebuild است، بنابراین Cascade در صورت حذف فیزیکی Device قابل قبول است؛ هرچند حذف عادی Device در Lifecycle انجام نمی‌شود.

---

# 15. CurrentState Spatial Data

موقعیت فعلی:

```text
latitude
longitude
geom
```

است.

`geom`:

```text
geometry(Point, 4326)
```

است.

`geom` از:

```text
latitude
longitude
```

تولید می‌شود و نباید منبع مستقل دیگری ایجاد کند.

---

# 16. CurrentState Last Valid Position

آخرین GPS معتبر:

```text
last_valid_latitude
last_valid_longitude
last_valid_geom
last_valid_device_time
last_valid_server_received_at
last_valid_accuracy
```

است.

این اطلاعات برای جلوگیری از Query دائمی History در Live View نگهداری می‌شوند.

---

# 17. CurrentState Attributes

```text
attributes JSONB NOT NULL DEFAULT '{}'
```

است.

فقط Attributeهای انتخاب‌شده و Allowlisted در این بخش قرار می‌گیرند.

CurrentState محل Full Telemetry یا Raw Protocol Data نیست.

---

# 18. CurrentState Indexها

حداقل:

```text
UNIQUE(device_id)
```

برای Lookup اصلی کافی است.

Index فضایی:

```text
GIST(geom)
```

فقط در صورت نیاز Queryهای Spatial روی CurrentState ایجاد می‌شود.

برای Live Map معمولاً Query اصلی بر اساس Device/Permission است، بنابراین از Indexگذاری غیرضروری خودداری می‌کنیم.

---

# 19. LocationHistory

جدول:

```text
gps.location_history
```

منبع تاریخی Location است.

هر رکورد یک Point تاریخی را نشان می‌دهد.

---

# 20. LocationHistory Schema

```text
location_history
├── id
├── device_id
├── device_time
├── server_received_at
├── latitude
├── longitude
├── geom
├── gps_valid
├── accuracy
├── speed
├── heading
├── altitude
├── motion
├── ignition
├── odometer
├── engine_hours
├── fuel_level
└── attributes
```

---

# 21. LocationHistory Ownership

```text
device_id
→ public.device.id
```

با:

```text
ON DELETE RESTRICT / PROTECT
```

است.

History نباید با حذف Device از بین برود.

---

# 22. LocationHistory Immutable

بعد از ثبت:

```text
LocationHistory
```

نباید Runtime آن را:

```text
UPDATE
DELETE
```

کند.

Role:

```text
sana_gps
```

فقط:

```text
SELECT
INSERT
```

دارد.

اصلاح تاریخی در MVP مسیر Runtime نیست.

---

# 23. LocationHistory Partitioning

LocationHistory تنها جدول Partition شده اصلی GPS است.

Partition:

```text
RANGE(device_time)
```

و دوره:

```text
MONTHLY
```

است.

مثلاً:

```text
location_history_2026_10
location_history_2026_11
location_history_2026_12
```

---

# 24. Parent Table

Parent:

```text
gps.location_history
```

است.

Partitionهای ماهانه زیر آن قرار می‌گیرند.

`sana-gps` همیشه به Parent می‌نویسد:

```text
INSERT INTO gps.location_history
```

و PostgreSQL رکورد را به Partition صحیح هدایت می‌کند.

---

# 25. Partition Maintenance

ساخت و حذف Partition توسط:

```text
Migration / Maintenance Job
```

انجام می‌شود.

`sana-gps` اجازه:

```text
CREATE PARTITION
DROP PARTITION
ALTER TABLE
```

ندارد.

---

# 26. LocationHistory Index

Index اصلی:

```text
(device_id, device_time)
```

است.

برای Queryهای Historical بسیار مهم است.

Index فضایی:

```text
GIST(geom)
```

در صورت نیاز Spatial Query ایجاد می‌شود.

---

# 27. LocationHistory Unique Constraint

این Constraint ایجاد نمی‌شود:

```text
UNIQUE(device_id, device_time)
```

چون:

* چند Telemetry ممکن است Timestamp یکسان داشته باشند.
* Resolution Device ممکن است پایین باشد.
* چند Record می‌تواند یک `device_time` داشته باشد.
* Packet Identity با Telemetry Identity متفاوت است.

---

# 28. Event

جدول:

```text
gps.event
```

برای رخدادهای معنادار GPS است.

---

# 29. Event Schema

```text
event
├── id
├── device_id
├── type
├── source
├── mode
├── occurred_at
├── started_at
├── ended_at
├── device_time
├── server_received_at
├── latitude
├── longitude
├── gps_valid
├── attributes
├── telemetry_reference
└── raw_packet_reference
```

---

# 30. Event Type

Event Type به‌صورت Code/Business Enum کنترل می‌شود.

نمونه:

```text
DEVICE_ONLINE
DEVICE_OFFLINE
IGNITION_ON
IGNITION_OFF
MOTION_STARTED
MOTION_STOPPED
TRIP_STARTED
TRIP_ENDED
OVERSPEED
GEOFENCE_ENTER
GEOFENCE_EXIT
```

Database نباید Protocol-specific Event Name دریافت کند.

---

# 31. Event Mode

```text
POINT
STATE
```

است.

Point Event:

```text
occurred_at
```

State Event:

```text
started_at
ended_at
```

---

# 32. Active State Event

برای هر:

```text
device + event_type
```

حداکثر یک State Event فعال داریم.

Constraint مفهومی:

```text
UNIQUE(device_id, type)
WHERE ended_at IS NULL
AND mode = STATE
```

---

# 33. Event Source

```text
DEVICE
SANA
SYSTEM
```

است.

این مشخص می‌کند Event از کجا ایجاد شده است.

---

# 34. Event Foreign Key

```text
device_id
→ public.device.id
ON DELETE RESTRICT
```

History Event باید باقی بماند.

---

# 35. Event References

`telemetry_reference` و `raw_packet_reference` برای Traceability هستند.

این Referenceها نباید باعث Coupling غیرضروری شوند.

اگر RawPacket به‌دلیل Retention حذف شود، Event نباید حذف شود.

بنابراین Reference به RawPacket در صورت نیاز می‌تواند nullable باشد.

---

# 36. Trip

جدول:

```text
gps.trip
```

برای سفرهای پردازش‌شده است.

---

# 37. Trip Schema

مدل مفهومی:

```text
trip
├── id
├── number
├── device_id
├── status
├── started_at
├── ended_at
├── start_latitude
├── start_longitude
├── start_geom
├── end_latitude
├── end_longitude
├── end_geom
├── distance
├── moving_duration
├── stopped_duration
├── unknown_duration
├── max_speed
├── start_odometer
├── end_odometer
├── start_engine_hours
├── end_engine_hours
├── start_fuel_level
├── end_fuel_level
├── attributes
├── created_at
└── updated_at
```

---

# 38. Trip Ownership

Trip متعلق به Device است:

```text
trip.device_id
→ public.device.id
```

با:

```text
ON DELETE RESTRICT
```

---

# 39. Trip Number

دو شناسه:

```text
id
number
```

داریم.

`id`:

```text
BIGINT
```

و `number`:

```text
UNIQUE
IMMUTABLE
Human-readable
```

است.

Gap در Number مجاز است.

---

# 40. Trip Status

در MVP:

```text
ACTIVE
COMPLETED
```

کافی است.

Stateهای Processing مثل:

```text
PENDING_START
PENDING_END
```

Runtime/Engine State هستند و الزاماً لازم نیست به‌عنوان Status دائمی Trip ذخیره شوند؛ در صورت نیاز Implementation می‌تواند آن‌ها را نگه دارد.

---

# 41. Completed Trip

Trip کامل‌شده در MVP:

```text
IMMUTABLE
```

است.

یعنی Runtime نباید Trip Completed را با Packet قدیمی دوباره باز کند یا Split/Merge کند.

---

# 42. RawPacket

جدول:

```text
gps.raw_packet
```

برای نگهداری موقت داده خام Protocol است.

---

# 43. RawPacket Schema

حداقل:

```text
raw_packet
├── id
├── device_id
├── received_at
├── raw_data
├── fingerprint
├── protocol
├── codec
├── profile_code
├── profile_version
└── metadata
```

---

# 44. RawPacket Ownership

```text
device_id
→ public.device.id
```

اما به دلیل Retention کوتاه‌مدت و ماهیت فنی، در طراحی Lifecycle می‌تواند:

```text
ON DELETE SET NULL
```

باشد.

---

# 45. RawPacket Immutable

RawPacket بعد از Insert:

```text
UPDATE ❌
DELETE توسط Runtime ❌
```

است.

Retention Job مسئول حذف آن است.

---

# 46. RawPacket Fingerprint

برای Deduplication:

```text
SHA-256
```

یا معادل امن آن استفاده می‌شود.

Fingerprint باید روی Representation استاندارد Raw Packet ساخته شود.

---

# 47. RawPacket Duplicate

برای تشخیص Duplicate:

```text
device_id
+
fingerprint
```

سیگنال اصلی است.

اما Constraint Unique دائمی الزاماً ایجاد نمی‌کنیم، چون Retention و Replay Lifecycle می‌تواند باعث نیاز به نگهداری مجدد Fingerprint شود.

Deduplication منطق Application + Database را با هم استفاده می‌کند.

---

# 48. Geofence

جداول:

```text
gps.geofence
gps.geofence_version
gps.geofence_assignment
gps.vehicle_geofence_state
```

هستند.

---

# 49. Geofence

`geofence` هویت Business Geofence را نگه می‌دارد.

مفهوم:

```text
Geofence
├── id
├── name
├── owner_scope
├── active
├── created_at
└── updated_at
```

Geometry داخل Version نگهداری می‌شود.

---

# 50. GeofenceVersion

Geometry تاریخی:

```text
gps.geofence_version
```

است.

مثلاً:

```text
Geofence A
Version 1
Version 2
Version 3
```

هر Version Immutable است.

---

# 51. Geometry

MVP:

```text
POLYGON
CIRCLE
```

پشتیبانی می‌شود.

Line Geofence در MVP نداریم.

Geometry با:

```text
PostGIS
SRID 4326
```

ذخیره می‌شود.

---

# 52. GeofenceAssignment

Assignment به:

```text
Vehicle
```

انجام می‌شود، نه Device.

```text
Vehicle
   ↓
GeofenceAssignment
   ↓
Geofence
```

در Runtime:

```text
Vehicle
   ↓
Active Device
```

Resolve می‌شود.

---

# 53. VehicleGeofenceState

Runtime State مربوط به Geofence:

```text
gps.vehicle_geofence_state
```

است.

این State برای جلوگیری از تولید Event تکراری ضروری است.

مثلاً:

```text
OUTSIDE
INSIDE
ENTER_PENDING
EXIT_PENDING
UNCERTAIN
UNOBSERVED
```

---

# 54. Command

Command نیز Entity دائمی GPS است:

```text
gps.command
```

اما مالکیت Business آن با Backend است.

`sana-backend` Command را ایجاد می‌کند.

`sana-gps` آن را اجرا می‌کند.

---

# 55. Command Schema

مدل:

```text
command
├── id
├── device_id
├── type
├── status
├── source
├── requested_by
├── payload
├── result
├── error_code
├── attempts
├── session_generation
├── created_at
├── updated_at
├── expires_at
├── sent_at
├── acknowledged_at
└── completed_at
```

---

# 56. Command Ownership

```text
device_id
→ public.device.id
ON DELETE RESTRICT
```

Command به Device تعلق دارد، نه Vehicle.

تعویض Device Commandهای قبلی را منتقل نمی‌کند.

---

# 57. Command Status

Stateهای اصلی:

```text
PENDING
QUEUED
SENDING
SENT
ACKNOWLEDGED
COMPLETED
FAILED
CANCELLED
EXPIRED
```

State Transition مطابق State Machine تأییدشده Stage 13 است.

---

# 58. Command Payload

```text
payload JSONB
```

است.

Payload باید توسط Backend بر اساس Command Type Validation شود.

Raw Protocol Bytes در Payload قرار نمی‌گیرد.

---

# 59. Command Result

```text
result JSONB
```

برای نتیجه Device/Protocol است.

Telemetry و Event همچنان Entityهای مستقل هستند.

---

# 60. Command Indexها

Indexهای اصلی:

```text
(device_id, status, created_at)
(status, expires_at)
(device_id, created_at)
(requested_by, created_at)
```

فقط در صورت تأیید Queryهای واقعی در Migration نهایی نگهداری می‌شوند.

---

# 61. DeviceLifecycleEvent

تاریخچه تغییر وضعیت Device:

```text
DeviceLifecycleEvent
```

از جنس Business/Audit است.

بهتر است در:

```text
public
```

یا Schema Business نگهداری شود، نه `gps.event`.

چون این Event از GPS Telemetry ایجاد نشده است.

در این مرحله:

```text
public.device_lifecycle_event
```

به‌عنوان محل مناسب در نظر گرفته می‌شود.

---

# 62. تفاوت DeviceLifecycleEvent و gps.event

```text
gps.event
→ GPS / Telemetry / Runtime Meaning

device_lifecycle_event
→ Business / Administrative History
```

این دو نباید ادغام شوند.

---

# 63. Tables نهایی GPS

پس Schema `gps` در MVP شامل:

```text
gps.current_state
gps.location_history
gps.event
gps.trip
gps.raw_packet

gps.device_vehicle_assignment

gps.geofence
gps.geofence_version
gps.geofence_assignment
gps.vehicle_geofence_state

gps.command
```

است.

---

# 64. Tables خارج از gps

Business Lifecycle:

```text
public.device
public.vehicle
public.device_model
public.device_lifecycle_event
```

و سایر Entityهای Business در:

```text
public
```

باقی می‌مانند.

---

# 65. FK Map

ساختار اصلی:

```text
public.device
    │
    ├──────────────► gps.current_state
    │
    ├──────────────► gps.location_history
    │
    ├──────────────► gps.event
    │
    ├──────────────► gps.trip
    │
    ├──────────────► gps.raw_packet
    │
    ├──────────────► gps.device_vehicle_assignment
    │
    └──────────────► gps.command
```

Vehicle:

```text
public.vehicle
    │
    ├──────────────► gps.device_vehicle_assignment
    │
    └──────────────► gps.geofence_assignment
```

Geofence:

```text
gps.geofence
    │
    ├──────────────► gps.geofence_version
    │
    └──────────────► gps.geofence_assignment
```

---

# 66. ON DELETE Policy

| Entity               | Parent   | Policy   |
| -------------------- | -------- | -------- |
| CurrentState         | Device   | CASCADE  |
| LocationHistory      | Device   | RESTRICT |
| Event                | Device   | RESTRICT |
| Trip                 | Device   | RESTRICT |
| RawPacket            | Device   | SET NULL |
| Command              | Device   | RESTRICT |
| Assignment           | Device   | RESTRICT |
| Assignment           | Vehicle  | RESTRICT |
| GeofenceVersion      | Geofence | RESTRICT |
| GeofenceAssignment   | Geofence | RESTRICT |
| GeofenceAssignment   | Vehicle  | RESTRICT |
| VehicleGeofenceState | Vehicle  | RESTRICT |

اصل:

> هر داده‌ای که Historical یا Audit است نباید با حذف Parent به‌صورت تصادفی از بین برود.

---

# 67. BIGINT Strategy

تمام Entityهای اصلی GPS از:

```text
BIGINT
```

با:

```text
GENERATED BY DEFAULT AS IDENTITY
```

یا معادل Django `BigAutoField` استفاده می‌کنند.

UUID در MVP برای Internal PK استفاده نمی‌شود.

---

# 68. Timestamp Strategy

Timestampهای Server:

```text
TIMESTAMPTZ
```

هستند.

تمام Timestampهای داخلی SANA:

```text
UTC
```

هستند.

نمایش Local Time فقط در API/Frontend انجام می‌شود.

---

# 69. JSONB Strategy

JSONB فقط برای اطلاعات واقعاً Dynamic:

```text
attributes
metadata
payload
result
```

است.

اطلاعات اصلی و قابل Query باید Typed Column باشند.

مثلاً:

```text
speed
latitude
device_time
status
```

نباید داخل JSONB قرار بگیرند.

---

# 70. Index Strategy

اصل:

> ابتدا Queryهای واقعی را مشخص می‌کنیم، سپس Index ایجاد می‌کنیم.

Indexهای قطعی اولیه:

```text
CurrentState:
UNIQUE(device_id)

LocationHistory:
(device_id, device_time)

Event:
(device_id, type, started_at)
(device_id, occurred_at)

Trip:
(device_id, started_at)

Assignment:
(device_id, started_at)
(vehicle_id, started_at)

RawPacket:
(device_id, received_at)
(device_id, fingerprint)

Command:
(device_id, status, created_at)
(status, expires_at)
```

Spatial Indexها:

```text
GIST(geom)
```

برای جداولی که واقعاً Spatial Query دارند.

---

# 71. Partition Strategy

فقط:

```text
gps.location_history
```

در MVP Partition می‌شود.

بر اساس:

```text
RANGE(device_time)
```

و:

```text
MONTHLY
```

---

# 72. چرا Event Partition نمی‌شود؟

Event حجم بسیار کمتری نسبت به LocationHistory دارد و Lifecycle آن بیشتر Event-centric است.

در MVP Partition کردن Event Complexity غیرضروری ایجاد می‌کند.

اگر حجم واقعی در آینده نشان دهد، Partitioning بعداً قابل اضافه شدن است.

---

# 73. چرا CurrentState Partition نمی‌شود؟

CurrentState:

```text
One Row Per Device
```

است.

بنابراین Partitioning برای آن هیچ مزیت معناداری در MVP ندارد.

---

# 74. چرا Trip Partition نمی‌شود؟

Trip نیز نسبت به LocationHistory کم‌حجم است.

Queryها معمولاً:

```text
Device
+
Time Range
```

هستند و Index معمولی کافی است.

---

# 75. RawPacket Retention

RawPacket دائمی نیست.

Retention توسط:

```text
received_at
```

مدیریت می‌شود.

مثلاً:

```text
7 days
30 days
```

بر اساس Configuration.

---

# 76. Historical Retention

LocationHistory، Event و Trip در MVP Retention کوتاه‌مدت ندارند.

این داده‌ها Historical Data اصلی SANA هستند.

Retention تجاری/قانونی آن‌ها بعداً به‌صورت مستقل تصمیم‌گیری می‌شود.

---

# 77. Runtime Permissions

`sana-gps`:

```text
CurrentState
→ SELECT / INSERT / UPDATE

LocationHistory
→ SELECT / INSERT

Event
→ SELECT / INSERT / UPDATE

Trip
→ SELECT / INSERT / UPDATE

RawPacket
→ SELECT / INSERT

Assignment
→ SELECT

Geofence
→ SELECT

Command
→ SELECT / UPDATE
```

برای Command، ایجاد Command توسط Backend انجام می‌شود؛ GPS فقط آن را Consume و State آن را Update می‌کند.

---

# 78. Backend Permissions

`sana-backend`:

```text
CurrentState
→ SELECT

LocationHistory
→ SELECT

Event
→ SELECT

Trip
→ SELECT

RawPacket
→ NO ACCESS by default

Assignment
→ CRUD

Geofence
→ CRUD

Command
→ INSERT / SELECT / UPDATE
```

Backend مالک Business Command است.

---

# 79. Migration Ownership

تمام:

```text
CREATE
ALTER
DROP
INDEX
CONSTRAINT
PARTITION
GRANT
```

توسط:

```text
sana_migrator
```

انجام می‌شود.

Runtime هیچ‌گونه DDL ندارد.

---

# 80. Final Architecture

```text
                         PostgreSQL
                              │
             ┌────────────────┴────────────────┐
             │                                 │
          public                              gps
             │                                 │
     ┌───────┼────────┐              ┌─────────┼─────────┐
     │       │        │              │         │         │
   Device  Vehicle  User       CurrentState  Event    Trip
     │       │                       │         │         │
     │       └───────┐               │         │         │
     │               │               │         │         │
     └───────────────┼───────────────┼─────────┼─────────┤
                     │               │
             DeviceVehicleAssignment │
                                     │
                              LocationHistory
```

و:

```text
gps
├── current_state
├── location_history
├── event
├── trip
├── raw_packet
├── device_vehicle_assignment
├── geofence
├── geofence_version
├── geofence_assignment
├── vehicle_geofence_state
└── command
```

---

# 81. Source of Truth نهایی

| مفهوم                  | Source of Truth                       |
| ---------------------- | ------------------------------------- |
| Device Identity        | `public.device`                       |
| Device Lifecycle       | `public.device` + Lifecycle Event     |
| Device ↔ Vehicle       | `gps.device_vehicle_assignment`       |
| Current Device State   | `gps.current_state`                   |
| Location History       | `gps.location_history`                |
| GPS Event              | `gps.event`                           |
| Trip                   | `gps.trip`                            |
| Raw Protocol Data      | `gps.raw_packet`                      |
| Geofence Definition    | `gps.geofence` + Version              |
| Geofence Assignment    | `gps.geofence_assignment`             |
| Geofence Runtime State | `gps.vehicle_geofence_state`          |
| Command                | `gps.command`                         |
| Connection State       | Computed from Runtime/`last_seen`     |
| Session                | Runtime Memory                        |
| Protocol Decoder       | Code                                  |
| Protocol Profile       | Code + Device Configuration Reference |

---

# 82. اصل مهم Schema

نباید یک مفهوم را در چند جدول به‌عنوان Source of Truth نگه داریم.

مثلاً:

```text
Device ↔ Vehicle
```

فقط:

```text
DeviceVehicleAssignment
```

مرجع رابطه است.

و:

```text
CurrentState
```

نباید یک `vehicle_id` مستقل به‌عنوان Source of Truth داشته باشد.

همچنین:

```text
LocationHistory
```

نباید Vehicle ID ذخیره کند.

---

# 83. وضعیت نهایی

```text
[✓] gps Schema
[✓] Business / GPS Boundary
[✓] CurrentState
[✓] LocationHistory
[✓] Event
[✓] Trip
[✓] RawPacket
[✓] DeviceVehicleAssignment
[✓] Geofence
[✓] GeofenceVersion
[✓] GeofenceAssignment
[✓] VehicleGeofenceState
[✓] Command
[✓] Cross-Schema FK
[✓] ON DELETE Policies
[✓] BIGINT / Identity
[✓] TIMESTAMPTZ / UTC
[✓] JSONB Boundary
[✓] Index Strategy
[✓] Partition Strategy
[✓] Retention Boundary
[✓] Runtime Permissions
[✓] Migration Ownership
[✓] Source of Truth
[✓] Runtime / Historical Separation

مرحله ۱۷ — CLOSED
```

## اصل نهایی

> **Schema `gps` باید داده‌های GPS را از Business Data جدا کند، ولی در همان PostgreSQL با Foreign Keyهای واقعی به Entityهای Business متصل بماند. هر مفهوم فقط یک Source of Truth دارد؛ Runtime ساده می‌ماند، Historical Data محافظت می‌شود و Partitioning فقط جایی استفاده می‌شود که واقعاً لازم است.**


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی Device Lifecycle ↔ GPS Runtime

## بخش ۱۹ معماری GPS

این سند مشخص می‌کند تغییر وضعیت تجاری و Lifecycle یک Device در SANA چه اثری روی:

* `sana-gps`
* Connection
* Session
* Telemetry
* CurrentState
* LocationHistory
* Event
* Command
* Device Assignment

دارد.

اصل بنیادی:

> **Device Lifecycle مالک Business است؛ sana-gps فقط از وضعیت Lifecycle برای تصمیم‌گیری درباره پذیرش یا رد Runtime Traffic استفاده می‌کند.**

---

# 1. دو مفهوم مستقل

در SANA دو وضعیت متفاوت داریم:

### Business Lifecycle

وضعیت واقعی Device در سیستم:

```text
WAREHOUSE
ACTIVE
SUSPENDED
REPAIR
RETURNED
RETIRED
```

این وضعیت توسط:

```text
sana-backend
```

مدیریت می‌شود.

---

### GPS Runtime State

وضعیت ارتباط Device با GPS Service:

```text
NO_SESSION
CONNECTED
ACTIVE_SESSION
FENCED
DISCONNECTED
```

این وضعیت Runtime است و توسط:

```text
sana-gps
```

مدیریت می‌شود.

این دو نباید با یکدیگر یکی شوند.

---

# 2. Source of Truth

برای Lifecycle:

```text
public.device
+
public.device_lifecycle_event
```

Source of Truth هستند.

برای Session:

```text
sana-gps Runtime Session Manager
```

Source of Truth است.

برای CurrentState:

```text
gps.current_state
```

Source of Truth Snapshot است.

بنابراین:

```text
Device Status
→ Business

Session Status
→ Runtime
```

---

# 3. Device Lifecycle Event

هر تغییر مهم Lifecycle باید در Business ثبت شود:

```text
public.device_lifecycle_event
```

مثلاً:

```text
WAREHOUSE
    ↓
ACTIVE
```

یا:

```text
ACTIVE
    ↓
REPAIR
```

GPS Runtime نباید خودش Lifecycle Event تجاری ایجاد کند.

---

# 4. sana-gps فقط Lifecycle را Consume می‌کند

جریان:

```text
sana-backend
      │
      │ Device Lifecycle Change
      ▼
public.device
      │
      ▼
sana-gps
```

`sana-gps` می‌تواند وضعیت فعلی Device را هنگام Login/Packet بررسی کند.

در آینده می‌توان Notification/Signal داخلی برای تغییر فوری Lifecycle اضافه کرد.

در MVP نیازی به Redis یا Message Broker نداریم.

---

# 5. WAREHOUSE

Device در Warehouse هنوز در اختیار سیستم است ولی برای Runtime عملیاتی نیست.

قاعده:

```text
Device Status = WAREHOUSE
```

نتیجه:

```text
GPS Connection
→ Reject
```

اگر Device به Port وصل شود:

```text
IMEI
   ↓
Device Lookup
   ↓
WAREHOUSE
   ↓
Reject
```

نباید Session فعال ایجاد شود.

---

# 6. WAREHOUSE و ACK

برای Device موجود در Warehouse:

```text
Valid Device
≠
Allowed Runtime Device
```

بنابراین:

```text
Login ACK
→ موفق ارسال نمی‌شود
```

و:

```text
AVL ACK
→ موفق ارسال نمی‌شود
```

زیرا Device مجاز به Runtime نیست.

---

# 7. ACTIVE

وضعیت اصلی عملیاتی:

```text
ACTIVE
```

است.

در این وضعیت Device اجازه دارد:

```text
Connect
Authenticate
Create Session
Send Telemetry
Receive Command
Update CurrentState
Write LocationHistory
Create Event
```

را انجام دهد.

---

# 8. SUSPENDED

Suspended به معنی غیرفعال شدن موقت عملیاتی Device است.

قاعده:

```text
SUSPENDED
→ No new active GPS Session
```

اگر Session فعال وجود داشته باشد:

```text
Lifecycle Change
      ↓
SUSPENDED
      ↓
Fence Current Session
      ↓
Close Connection
```

---

# 9. REPAIR

Device در Repair نباید Telemetry عملیاتی تولید کند.

قاعده:

```text
REPAIR
→ No Runtime Session
```

اگر Device قبل از Repair متصل بوده:

```text
ACTIVE Session
      ↓
REPAIR
      ↓
Fence
      ↓
Close
```

---

# 10. RETURNED

Returned یعنی Device دیگر در چرخه عملیاتی فعلی SANA قرار ندارد.

مثلاً:

```text
Customer
   ↓
Device
   ↓
Returned
```

در این وضعیت:

```text
New Session
→ Reject
```

و Session قبلی:

```text
Fence + Close
```

می‌شود.

---

# 11. RETIRED

Retired یک وضعیت دائمی/نهایی برای Device است.

قاعده:

```text
RETIRED
→ No Runtime
→ No New Session
→ No Telemetry Processing
→ No Command
```

تاریخچه قبلی باقی می‌ماند.

---

# 12. Lifecycle Matrix

| Device Lifecycle | New Connection | Existing Session | Telemetry | Command |
| ---------------- | -------------- | ---------------- | --------- | ------- |
| `WAREHOUSE`      | Reject         | None             | Reject    | No      |
| `ACTIVE`         | Allow          | Allow            | Allow     | Allow   |
| `SUSPENDED`      | Reject         | Fence/Close      | Reject    | No      |
| `REPAIR`         | Reject         | Fence/Close      | Reject    | No      |
| `RETURNED`       | Reject         | Fence/Close      | Reject    | No      |
| `RETIRED`        | Reject         | Fence/Close      | Reject    | No      |

---

# 13. ACTIVE شدن Device

وقتی Device از:

```text
WAREHOUSE
```

به:

```text
ACTIVE
```

تغییر می‌کند، SANA نباید خودش Session ایجاد کند.

یعنی:

```text
ACTIVE
≠
Connected
```

Device باید خودش:

```text
Connect
```

کند.

سپس:

```text
IMEI
→ Authentication
→ Session
```

ایجاد می‌شود.

---

# 14. SUSPENDED شدن Device

اگر Device در حالت:

```text
ACTIVE
```

باشد و Suspend شود:

```text
ACTIVE
   ↓
SUSPENDED
```

باید Session فعال آن Device Fence شود.

جریان:

```text
Lifecycle Change
       ↓
SUSPENDED
       ↓
Session Fence
       ↓
Connection Close
```

---

# 15. چرا فقط Reject Packet کافی نیست؟

اگر فقط Packetهای بعدی را Reject کنیم ولی Connection باز بماند:

```text
TCP Connection
   ↓
Device suspended
   ↓
Connection remains open
```

این باعث مصرف منابع و Sessionهای بی‌مصرف می‌شود.

بنابراین برای Lifecycleهای غیرعملیاتی:

```text
Fence
+
Close
```

ترجیح داده می‌شود.

---

# 16. Lifecycle Change و Race Condition

ممکن است همزمان:

```text
Packet
```

و:

```text
Device → SUSPENDED
```

رخ دهند.

بنابراین فقط بررسی Local Memory کافی نیست.

هر Telemetry باید قبل از Side Effectهای مهم وضعیت معتبر بودن Session و Device را داشته باشد.

مثلاً:

```text
Session Generation
+
Device Runtime Eligibility
```

بررسی می‌شود.

---

# 17. Session Generation

همان مکانیزم قبلی همچنان مرجع است:

```text
Device
   ↓
Session Generation
```

مثلاً:

```text
Generation 15
```

اگر Device Suspend شود:

```text
Generation 15
→ Fenced
```

هر Work Item قدیمی که:

```text
generation = 15
```

داشته باشد، دیگر اجازه Side Effect ندارد.

---

# 18. Lifecycle Fence

Fence باید جلوی این موارد را بگیرد:

```text
CurrentState Update
LocationHistory Insert
Event Creation
Trip Update
Command Send
last_seen Update
```

یعنی:

```text
Old Session
   ↓
Lifecycle no longer valid
   ↓
NO SIDE EFFECT
```

---

# 19. Packet در حال Processing

ممکن است Packet قبل از Suspend دریافت شده باشد ولی Worker هنوز آن را پردازش نکرده باشد.

مثلاً:

```text
10:00:00 Packet received
10:00:01 Device suspended
10:00:02 Worker starts
```

Worker نباید صرفاً چون Packet قبل از Suspend دریافت شده، بدون بررسی آن را پردازش کند.

Session/Runtime validity باید دوباره بررسی شود.

---

# 20. Transaction Boundary

برای جلوگیری از Race، تصمیم نهایی باید در Transaction Database نیز محافظت شود.

مثلاً:

```text
BEGIN
   ↓
Verify Device Runtime Eligibility
   ↓
Verify Session Generation
   ↓
Process Telemetry
   ↓
COMMIT
```

اگر Lifecycle در همین فاصله تغییر کرده باشد، Processing باید Fail/Abort شود.

---

# 21. Lifecycle و Historical Data

Suspend شدن Device نباید تاریخچه را حذف کند.

مثلاً:

```text
Device 100
ACTIVE
10:00 → Location A
10:05 → Location B

SUSPENDED
```

Location History قبلی:

```text
A
B
```

باقی می‌ماند.

---

# 22. CurrentState بعد از Suspend

CurrentState نباید حذف شود.

مثلاً:

```text
Device
CurrentState
last_valid_position = X
```

بعد:

```text
Device → SUSPENDED
```

CurrentState همچنان وجود دارد.

اما:

```text
connection_state
```

از روی `last_seen` و زمان جاری ممکن است:

```text
OFFLINE
```

محاسبه شود.

---

# 23. آیا Current Position پاک شود؟

خیر.

Suspend شدن Device به معنی:

```text
GPS Fix = false
```

نیست.

بنابراین SANA نباید صرفاً به دلیل Lifecycle:

```text
latitude = NULL
longitude = NULL
```

کند.

آخرین Snapshot واقعی باقی می‌ماند.

---

# 24. تفاوت Suspend و GPS No-Fix

این دو کاملاً متفاوت هستند:

```text
SUSPENDED
→ Business Lifecycle

GPS_NO_FIX
→ GPS State
```

بنابراین:

```text
SUSPENDED ≠ GPS_NO_FIX
```

---

# 25. تفاوت Suspend و Offline

همچنین:

```text
SUSPENDED ≠ OFFLINE
```

ممکن است Device Suspend شود و بلافاصله Connection بسته شود.

ولی علت:

```text
Lifecycle Change
```

است، نه الزاماً:

```text
Communication Timeout
```

بنابراین Event Engine نباید Suspend را به‌صورت خودکار `DEVICE_OFFLINE` تفسیر کند.

---

# 26. Lifecycle Event و GPS Event

مثلاً:

```text
Device
ACTIVE → SUSPENDED
```

این یک:

```text
DeviceLifecycleEvent
```

است.

نباید خودکار تبدیل شود به:

```text
gps.event = DEVICE_OFFLINE
```

مگر اینکه واقعاً Event ارتباطی Offline طبق Rule خودش رخ داده باشد.

---

# 27. Device Replacement

تعویض Device یک نقطه مهم Lifecycle/Assignment است.

مثلاً:

```text
Vehicle A
   ↓
Device 100
```

تعویض:

```text
Device 100
   ↓
Device 200
```

Device 100 نباید به Device 200 تبدیل شود.

بلکه:

```text
Device 100
→ Historical

Device 200
→ New Active Device
```

---

# 28. Session هنگام Replacement

برای Device قبلی:

```text
Fence Session
Close Connection
```

برای Device جدید:

```text
No automatic Session
```

Device جدید باید خودش:

```text
Connect
Authenticate
```

کند.

---

# 29. CurrentState در Replacement

CurrentState هر Device مستقل است.

بنابراین:

```text
Device 100
CurrentState = Position A
```

و:

```text
Device 200
CurrentState = NULL
```

تا اولین Telemetry.

نباید:

```text
Device 100 CurrentState
→ Device 200
```

Copy شود.

---

# 30. LocationHistory در Replacement

تاریخچه Device قبلی:

```text
Device 100
LocationHistory
```

باقی می‌ماند.

Device جدید:

```text
Device 200
LocationHistory
```

را از نقطه شروع خودش ایجاد می‌کند.

Vehicle History در آینده با:

```text
DeviceVehicleAssignment
+
Device LocationHistory
```

ساخته می‌شود.

---

# 31. Assignment و Lifecycle یکی نیستند

این دو مفهوم مستقل‌اند:

```text
DeviceVehicleAssignment
→ Device به کدام Vehicle متصل است؟

DeviceLifecycle
→ Device در چه وضعیت تجاری/عملیاتی است؟
```

ممکن است:

```text
Device = ACTIVE
Assignment = NULL
```

باشد.

مثلاً Device آماده نصب است.

همچنین:

```text
Device = SUSPENDED
Assignment = Vehicle A
```

نیز ممکن است وجود داشته باشد.

---

# 32. Active Device بدون Vehicle

Device می‌تواند:

```text
ACTIVE
```

باشد ولی هنوز به Vehicle تخصیص داده نشده باشد.

در این وضعیت:

```text
GPS Runtime
→ Allowed
```

ولی:

```text
Vehicle Live View
→ No Vehicle Mapping
```

خواهد داشت.

---

# 33. Assignment Change

تغییر Vehicle به‌تنهایی الزاماً Session را قطع نمی‌کند.

مثلاً:

```text
Device 100
Vehicle A
```

به:

```text
Device 100
Vehicle B
```

تغییر کند.

Session Device همچنان می‌تواند فعال بماند.

زیرا:

```text
Assignment
≠
Connection Identity
```

---

# 34. Lifecycle Change باید Session را کنترل کند

ولی تغییر Lifecycleهای غیرعملیاتی:

```text
SUSPENDED
REPAIR
RETURNED
RETIRED
```

باید Runtime را Fence کند.

پس:

```text
Assignment Change
→ معمولاً Session را قطع نمی‌کند

Lifecycle Operationality Change
→ می‌تواند Session را Fence کند
```

---

# 35. Command و Lifecycle

Command فقط برای Device عملیاتی مجاز است.

مثلاً:

```text
ACTIVE
→ Command allowed
```

اما:

```text
WAREHOUSE
SUSPENDED
REPAIR
RETURNED
RETIRED
```

نباید Command جدید دریافت کنند.

---

# 36. Commandهای قبلی هنگام Suspend

فرض کنیم:

```text
Command #100
status = QUEUED
```

و Device Suspend شود.

Command نباید ارسال شود.

در زمان Claim:

```text
Device Lifecycle
→ SUSPENDED
```

پس:

```text
Command
→ remain QUEUED
```

یا در صورت Rule مربوطه:

```text
CANCELLED
```

شود.

در MVP پیشنهاد می‌کنیم:

```text
Suspend
→ Command جدید ارسال نشود
→ Commandهای Queue شده تا Expiry باقی بمانند
```

ولی Commandهای expired طبق Scheduler:

```text
EXPIRED
```

می‌شوند.

---

# 37. Command در حال Sending

اگر Command همزمان با Suspend در حال ارسال باشد:

```text
SENDING
```

Race ممکن است رخ دهد.

بنابراین Session Generation و Device Runtime Check باید هنگام Claim/Send استفاده شوند.

اگر Send قبل از Fence واقعاً انجام شده باشد، ممکن است Device Command را دریافت کرده باشد.

SANA نباید ادعا کند:

```text
Command definitely not sent
```

مگر اینکه واقعاً نتیجه مشخص باشد.

---

# 38. Telemetry بعد از Suspend

اگر Device پس از Suspend هنوز Packet بفرستد:

```text
Device
→ SUSPENDED
```

Packet:

```text
Reject / Ignore Runtime Side Effects
```

می‌شود.

اما Raw Packet در صورت Policy نگهداری می‌تواند ثبت شود، چون Raw Packet برای Debug و Audit است.

نکته:

```text
Raw Packet
≠
Telemetry Accepted
```

---

# 39. Raw Packet برای Device غیرعملیاتی

اگر Device شناخته‌شده ولی:

```text
SUSPENDED
```

باشد، می‌توان Raw Packet را برای Debug/Audit ذخیره کرد، ولی:

```text
LocationHistory
CurrentState
Event
Trip
```

نباید از آن ساخته شود.

در صورت نیاز به کاهش Storage، این رفتار می‌تواند Configuration شود.

---

# 40. Unknown Device

Unknown Device با Device شناخته‌شده ولی غیرعملیاتی متفاوت است.

```text
UNKNOWN
→ No Device
```

پس:

```text
No Raw Packet persistence by default
No Session
No Telemetry
No ACK
```

زیرا نمی‌خواهیم مهاجم بتواند Storage را با IMEIهای جعلی پر کند.

---

# 41. DeviceModel / Protocol هنگام Lifecycle

Lifecycle روی Protocol Resolution نیز اثر دارد.

اما ترتیب همچنان:

```text
Identity
→ Device Lookup
→ Lifecycle Check
→ Protocol Resolution
→ Decode
```

است.

اگر Device:

```text
SUSPENDED
```

باشد، نباید برای آن Decode کامل و پرهزینه انجام شود.

---

# 42. Fast Reject

برای Deviceهای غیرمجاز/غیرعملیاتی:

```text
IMEI
 ↓
Device Lookup
 ↓
Lifecycle Check
 ↓
Reject
```

باید تا حد امکان سریع انجام شود.

این برای جلوگیری از مصرف CPU و Memory روی Traffic غیرمجاز مهم است.

---

# 43. Device Lifecycle و Session Registry

Session Manager باید بتواند:

```text
Fence(device_id)
```

انجام دهد.

مثلاً:

```text
Lifecycle Change
      ↓
SessionManager.fence(device_id)
      ↓
generation++
      ↓
close active connection
```

جزئیات اجرای آن در Runtime خواهد بود.

---

# 44. Lifecycle Event Propagation

در MVP لازم نیست Kafka/Redis داشته باشیم.

دو روش قابل قبول:

### هنگام Packet

```text
Device Lookup
→ Current Lifecycle
```

### Signal آینده

```text
Backend
→ PostgreSQL NOTIFY
→ sana-gps
→ Session Fence
```

در MVP می‌توانیم از ترکیب:

```text
DB state check
+
PostgreSQL NOTIFY برای کاهش تأخیر
```

استفاده کنیم.

NOTIFY فقط Signal است؛ Database همچنان Source of Truth است.

---

# 45. Restart sana-gps

اگر `sana-gps` Restart شود:

```text
Session Registry
→ Lost
```

Sessionهای قبلی معتبر نیستند.

Device باید دوباره:

```text
Connect
Authenticate
```

کند.

در Startup نباید Session قبلی را از Database Restore کنیم.

---

# 46. Restart و Lifecycle

بعد از Restart:

```text
Device Lifecycle
→ Database
```

دوباره خوانده می‌شود.

اگر:

```text
ACTIVE
```

باشد:

```text
Allow new connection
```

اگر:

```text
SUSPENDED
```

باشد:

```text
Reject
```

---

# 47. Lifecycle و CurrentState Recovery

CurrentState قابل Rebuild است.

اما Lifecycle از CurrentState استخراج نمی‌شود.

یعنی:

```text
CurrentState
≠
Device Lifecycle
```

Lifecycle همیشه از:

```text
public.device
```

خوانده می‌شود.

---

# 48. Lifecycle و Historical Reports

تغییر Lifecycle نباید تاریخچه Telemetry را حذف یا Rewrite کند.

مثلاً:

```text
Device
ACTIVE
Jan → Location History

REPAIR
Feb

ACTIVE
Mar → New Location History
```

تاریخچه January همچنان معتبر است.

---

# 49. Retired Device

Retired به معنی حذف تاریخی Device نیست.

بلکه:

```text
Runtime Disabled
+
Historical Preserved
```

است.

پس:

```text
Device
→ Retired
```

ولی:

```text
LocationHistory
Event
Trip
Lifecycle History
```

باقی می‌مانند.

---

# 50. Physical Delete

Device در طراحی SANA نباید به‌صورت عادی Physical Delete شود.

به‌جای:

```text
DELETE Device
```

از Lifecycle:

```text
RETIRED
```

استفاده می‌شود.

این موضوع برای حفظ:

```text
IMEI History
Telemetry
Event
Trip
Assignment
Audit
```

ضروری است.

---

# 51. Device ID Reuse

IMEI و Device Identity نباید بعد از Retire برای Device دیگری Reuse شود.

مثلاً:

```text
Device 100
IMEI 123456789
RETIRED
```

نباید:

```text
Device 200
IMEI 123456789
```

شود.

IMEI همچنان Identity تاریخی Device قبلی است.

---

# 52. Lifecycle State Machine

مدل مفهومی:

```text
                    ┌─────────────┐
                    │   WAREHOUSE │
                    └──────┬──────┘
                           │ activate
                           ▼
                    ┌─────────────┐
                    │    ACTIVE   │
                    └──┬─────┬────┘
                       │     │
                 suspend│     │repair
                       ▼     ▼
                 SUSPENDED  REPAIR
                       │     │
                       └──┬──┘
                          │
                          ▼
                      RETURNED
                          │
                          ▼
                       RETIRED
```

Transitions دقیق Business در Backend کنترل می‌شوند.

GPS فقط Runtime Effect آن‌ها را اجرا می‌کند.

---

# 53. Runtime State Machine

برای GPS:

```text
NO_SESSION
    │
    │ valid connection
    ▼
CONNECTED
    │
    │ authenticated
    ▼
ACTIVE_SESSION
    │
    ├── disconnect ───────► DISCONNECTED
    │
    ├── lifecycle change ─► FENCED
    │
    └── new session ──────► FENCED
```

و:

```text
FENCED
→ Connection Closed
→ No Side Effects
```

---

# 54. Business و Runtime Matrix

| Lifecycle | Session | Telemetry | CurrentState | History  | Command |
| --------- | ------- | --------- | ------------ | -------- | ------- |
| WAREHOUSE | Reject  | Reject    | Preserve     | Preserve | No      |
| ACTIVE    | Allow   | Allow     | Update       | Write    | Allow   |
| SUSPENDED | Fence   | Reject    | Preserve     | No new   | No      |
| REPAIR    | Fence   | Reject    | Preserve     | No new   | No      |
| RETURNED  | Fence   | Reject    | Preserve     | No new   | No      |
| RETIRED   | Fence   | Reject    | Preserve     | Preserve | No      |

---

# 55. نکته مهم درباره Preserve

`Preserve` به این معنی نیست که Snapshot یا History دوباره نوشته شود.

یعنی:

```text
Lifecycle Change
→ CurrentState Delete ❌
→ History Delete ❌
```

فقط Runtime Processing متوقف می‌شود.

---

# 56. Device فعال بدون اتصال

این حالت کاملاً معتبر است:

```text
Lifecycle = ACTIVE
Session = NO_SESSION
```

مثلاً:

* دستگاه خاموش است.
* اینترنت ندارد.
* هنوز نصب نشده.
* خارج از شبکه است.

پس:

```text
ACTIVE ≠ ONLINE
```

---

# 57. Device Suspended با Last Seen

این نیز معتبر است:

```text
Lifecycle = SUSPENDED
last_seen = 10:30
```

آخرین زمان ارتباط واقعی همچنان حفظ می‌شود.

Connection State فعلی ممکن است:

```text
OFFLINE
```

محاسبه شود، ولی علت قطع ارتباط:

```text
Lifecycle Suspension
```

است.

---

# 58. اصل Event

Lifecycle Event و GPS Event نباید ادغام شوند:

```text
public.device_lifecycle_event
→ Business Lifecycle

gps.event
→ Operational/Telemetry Event
```

این تفکیک برای Audit و گزارش‌گیری بسیار مهم است.

---

# 59. Source of Truth نهایی

```text
Device Lifecycle
→ public.device

Lifecycle History
→ public.device_lifecycle_event

Device ↔ Vehicle
→ gps.device_vehicle_assignment

GPS Session
→ sana-gps Runtime

Current Snapshot
→ gps.current_state

Location History
→ gps.location_history

GPS Events
→ gps.event

Commands
→ gps.command
```

هیچ Entity نباید Source of Truth Entity دیگری شود.

---

# 60. اصل نهایی مرحله ۱۹

> **Business Lifecycle تعیین می‌کند Device از نظر SANA مجاز به فعالیت GPS هست یا نه؛ Runtime Session تعیین می‌کند Device در حال حاضر چگونه به sana-gps متصل است. تغییر Lifecycleهای غیرعملیاتی باید Session را Fence و Connection را Close کند، اما نباید تاریخچه یا CurrentState را حذف کند. Assignment با Lifecycle مستقل است و تعویض Device باعث انتقال Session، CurrentState یا History بین Deviceها نمی‌شود.**

---

# 61. وضعیت مرحله

```text
[✓] Business Lifecycle vs Runtime State
[✓] WAREHOUSE
[✓] ACTIVE
[✓] SUSPENDED
[✓] REPAIR
[✓] RETURNED
[✓] RETIRED
[✓] Session Fencing
[✓] Session Generation
[✓] Telemetry Rejection
[✓] CurrentState Preservation
[✓] Historical Preservation
[✓] Device Replacement
[✓] Assignment Independence
[✓] Command Interaction
[✓] Unknown Device
[✓] Restart Behavior
[✓] Lifecycle/Session Race Protection
[✓] Physical Delete Policy
[✓] IMEI Identity Preservation

مرحله ۱۹ — CLOSED
```

### نتیجه معماری

```text
                 Business
                    │
                    ▼
             public.device
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
     Lifecycle           Assignment
          │                   │
          ▼                   ▼
      sana-gps            Vehicle View
          │
          ▼
       Session
          │
    ┌─────┴─────┐
    ▼           ▼
Telemetry     Command
    │
    ▼
┌──────────────────────────────┐
│ CurrentState                 │
│ LocationHistory              │
│ Event                        │
│ Trip                         │
└──────────────────────────────┘
```

**مرحله ۱۹ — Device Lifecycle ↔ GPS Runtime — CLOSED**


============================================================================
============================================================================

# SANA GPS — اصلاح نهایی تعارض Trip و DeviceVehicleAssignment

## 1. مسئله

در طراحی قبلی دو اصل داشتیم:

```text
Trip
→ متعلق به Device

DeviceVehicleAssignment
→ رابطه زمانی Device و Vehicle
```

همچنین تصمیم گرفته شده بود که تغییر Assignment می‌تواند مرز Trip باشد.

برای جلوگیری از ابهام، تعریف دقیق Trip نهایی می‌شود.

---

# 2. تعریف نهایی Trip

در SANA:

> **Trip یک سفر عملیاتی متعلق به Device است که در یک بازه زمانی مشخص و تحت یک Device↔Vehicle Assignment ثابت شکل می‌گیرد.**

بنابراین Trip همزمان دو Context دارد:

```text
Trip Identity
→ Device

Vehicle Context
→ Assignment در بازه Trip
```

Trip از نظر مالکیت به Vehicle وابسته نیست.

اما برای گزارش‌گیری Vehicle، Assignment زمانی Trip مشخص می‌کند که Trip در آن Vehicle انجام شده است.

---

# 3. Assignment یک Hard Boundary برای Trip است

اگر Assignment تغییر کند:

```text
Vehicle A
    ↓
Vehicle B
```

Trip فعال باید در زمان تغییر Assignment بسته شود.

یعنی:

```text
Assignment Change
        ↓
Trip Boundary
```

حتی اگر Device از نظر فیزیکی همچنان در حال حرکت باشد.

---

# 4. مثال

فرض کنیم:

```text
Device 100
Vehicle A
```

از:

```text
10:00
```

Trip شروع می‌شود.

در:

```text
10:30
```

Device بدون توقف به Vehicle B منتقل می‌شود.

و در:

```text
10:31
```

همچنان در حال حرکت است.

نتیجه:

```text
Trip #500
Device 100
Assignment → Vehicle A
started_at = 10:00
ended_at   = 10:30
status     = COMPLETED
```

و بعد:

```text
Trip #501
Device 100
Assignment → Vehicle B
started_at = 10:30
ended_at   = NULL
status     = ACTIVE
```

---

# 5. نکته بسیار مهم

این به معنی قطع شدن Telemetry نیست.

در این مثال:

```text
10:29
LocationHistory

10:30
LocationHistory

10:31
LocationHistory
```

همه همچنان متعلق به:

```text
Device 100
```

هستند.

بنابراین:

```text
Assignment Boundary
≠
Telemetry Gap
```

و:

```text
Assignment Boundary
≠
GPS Disconnect
```

---

# 6. Trip فیزیکی و Trip عملیاتی

باید بین این دو مفهوم تفاوت قائل شویم.

### Physical Movement

حرکت واقعی Device/خودرو:

```text
10:00 → 11:00
```

ممکن است کاملاً پیوسته باشد.

### Operational Trip

Trip در SANA:

```text
10:00 → 10:30
10:30 → 11:00
```

می‌تواند به دلیل تغییر Assignment به دو Trip تقسیم شود.

پس:

```text
Physical Movement
≠
Operational Trip
```

---

# 7. چرا Trip را در Assignment Change نمی‌توانیم باز نگه داریم؟

فرض کنیم Trip را نبندیم:

```text
Trip #500
10:00 → 11:00
Device 100
```

ولی:

```text
10:30
Vehicle A → Vehicle B
```

در این صورت یک Trip واحد همزمان در:

```text
Vehicle A
10:00 → 10:30

Vehicle B
10:30 → 11:00
```

قرار می‌گیرد.

این باعث می‌شود:

* گزارش Vehicle پیچیده شود.
* Ownership زمانی Trip مبهم شود.
* Start/End Context یک Trip تغییر کند.
* Permission تاریخی پیچیده‌تر شود.
* Aggregation Vehicle نیازمند Segment کردن Trip شود.

برای MVP این پیچیدگی را نمی‌پذیریم.

---

# 8. بنابراین Assignment Boundary قطعی است

قاعده:

```text
Trip Active
+
Assignment Ends
        ↓
Trip COMPLETED
```

و:

```text
New Assignment
+
Future Movement
        ↓
Potential New Trip
```

Trip جدید لزوماً در همان لحظه ایجاد نمی‌شود.

اگر Device بعد از Assignment جدید هنوز شرایط شروع Trip را نداشته باشد:

```text
NO_TRIP / PENDING_START
```

باقی می‌ماند.

---

# 9. Assignment Change به‌تنهایی Trip جدید نمی‌سازد

این نکته مهم است.

اگر:

```text
Vehicle A → Vehicle B
```

تغییر کند ولی Device:

```text
Stopped
```

باشد، نباید صرفاً به دلیل Assignment یک Trip جدید بسازیم.

در نتیجه:

```text
Assignment Change
→ پایان Trip فعلی

Assignment Change
≠
شروع قطعی Trip جدید
```

Trip جدید فقط وقتی شروع می‌شود که Ruleهای معمول Trip Start برقرار شوند.

---

# 10. اگر Trip فعال وجود نداشته باشد

اگر:

```text
Device
Assignment A
No Active Trip
```

و Assignment تغییر کند:

```text
A → B
```

هیچ Tripای بسته نمی‌شود.

فقط Context Assignment تغییر می‌کند.

سپس Telemetry آینده طبق Ruleهای معمول Trip بررسی می‌شود.

---

# 11. اگر Device در حال حرکت باشد

مثلاً:

```text
10:00 → MOVING
10:10 → MOVING
10:20 → MOVING
```

و در:

```text
10:20
Assignment Change
```

رخ دهد.

Trip قبلی:

```text
10:00 → 10:20
```

بسته می‌شود.

Trip جدید:

```text
10:20
```

به‌صورت خودکار ایجاد نمی‌شود؛ بلکه اولین Telemetry بعد از Assignment Change باید شرایط Start را داشته باشد.

---

# 12. Timestamp مرز Trip

Assignment Boundary با زمان دقیق:

```text
assignment_change_at
```

مشخص می‌شود.

این زمان باید همان زمان Commit تغییر Assignment در Server باشد، مگر اینکه Assignment به‌صورت Administrative Backdated ثبت شده باشد.

برای Assignment عادی Runtime:

```text
Trip End
=
Assignment End
```

است.

---

# 13. Backdated Assignment

اگر Admin یک Assignment را با تاریخ گذشته ثبت کند:

```text
Assignment
started_at = yesterday
```

این تغییر نباید در MVP باعث بازسازی خودکار Tripهای قبلی شود.

قاعده:

```text
Backdated Assignment
→ Historical Context Change

Automatic Trip Rebuild
→ خارج از MVP
```

اگر نیاز به Rebuild وجود داشته باشد، باید یک فرآیند صریح Recalculation/Backfill در آینده طراحی شود.

---

# 14. Device Replacement

Device Replacement نیز Assignment Boundary ایجاد می‌کند.

مثلاً:

```text
Vehicle A
Device 100
10:00 → 12:00
```

و:

```text
Vehicle A
Device 200
12:00 → ...
```

Trip فعال Device 100 در:

```text
12:00
```

بسته می‌شود.

Device 200 بعد از اولین Telemetry مناسب می‌تواند Trip جدید ایجاد کند.

---

# 15. Vehicle Context در Trip

Trip می‌تواند برای Query سریع یک Context مشتق‌شده داشته باشد، اما:

> **Assignment همچنان Source of Truth است.**

یعنی اگر در آینده در Trip چیزی مانند:

```text
vehicle_id
```

به‌صورت denormalized ذخیره شود، نباید Source of Truth رابطه محسوب شود.

در MVP ترجیح:

```text
Trip
→ device_id

Assignment
→ vehicle context
```

است.

---

# 16. Trip Historical Query

برای نمایش Tripهای یک Vehicle:

```text
Vehicle
   ↓
DeviceVehicleAssignment
   ↓
Trip
   ↓
Assignment overlap
   ↓
Vehicle Trips
```

چون Trip از ابتدا با Assignment Boundary ساخته شده، Query بسیار ساده‌تر و قابل اعتمادتر می‌شود.

---

# 17. Trip Distance

Assignment Boundary باعث حذف Telemetry نمی‌شود.

مثلاً:

```text
Trip #500
10:00 → 10:30
Distance = 42 km

Trip #501
10:30 → 11:00
Distance = 18 km
```

LocationHistory بین این دو Trip همچنان پیوسته است.

در صورت نیاز:

```text
Vehicle Total
= 42 + 18
= 60 km
```

محاسبه می‌شود.

---

# 18. Trip Engine

Trip Engine باید Assignment Boundary را به‌عنوان یکی از Inputهای خود داشته باشد:

```text
Telemetry
Assignment Context
Trip State
```

و منطق:

```text
Active Trip
      │
      ├── normal telemetry
      │       ↓
      │    continue
      │
      └── assignment ends
              ↓
          COMPLETE
```

---

# 19. Event نیز همان Boundary را رعایت می‌کند

State Eventهای فعال نیز در Assignment Boundary بسته می‌شوند.

مثلاً:

```text
OVERSPEED
10:20 → NULL
```

در:

```text
10:30 Assignment Change
```

به:

```text
OVERSPEED
10:20 → 10:30
```

تبدیل می‌شود.

اگر بعد از Assignment جدید دوباره Overspeed ادامه داشته باشد:

```text
OVERSPEED #2
10:31 → ...
```

ایجاد می‌شود.

---

# 20. Point Event

Point Event نیازی به بسته شدن ندارد.

مثلاً:

```text
IGNITION_ON
occurred_at = 10:30:05
```

Assignment در:

```text
10:30:00
```

تغییر کرده است.

این Event متعلق به:

```text
Device
```

است و در Historical Vehicle Query مربوط به Vehicle جدید دیده می‌شود.

---

# 21. CurrentState

Assignment Change هیچ CurrentState جدیدی ایجاد نمی‌کند.

مثلاً:

```text
Device 100
speed = 80
```

و سپس:

```text
Vehicle A → Vehicle B
```

CurrentState همچنان:

```text
speed = 80
```

باقی می‌ماند.

فقط:

```text
Current Vehicle Context
```

تغییر می‌کند.

---

# 22. WebSocket

Assignment Change باید بعد از Commit به Live Clients اطلاع داده شود.

اما این پیام:

```text
DEVICE_ASSIGNMENT_CHANGED
```

است، نه Telemetry Update.

بعد از آن، Client باید Context جدید را استفاده کند.

---

# 23. Live Map

قبل:

```text
Vehicle A
→ Device 100
→ CurrentState 100
```

بعد:

```text
Vehicle B
→ Device 100
→ CurrentState 100
```

CurrentState تغییر نکرده است.

فقط Vehicle Context تغییر کرده است.

---

# 24. اصل بسیار مهم

سه چیز نباید با هم اشتباه شوند:

```text
Device Identity
→ چه دستگاهی است؟

Assignment
→ در این لحظه متعلق به کدام Vehicle است؟

Trip
→ یک سفر عملیاتی در یک Assignment ثابت
```

این سه مفهوم مستقل هستند.

---

# 25. مثال نهایی کامل

```text
Device 100
```

### Assignment 1

```text
Vehicle A
10:00 → 10:30
```

### Trip 1

```text
10:00 → 10:30
42 km
```

### Assignment 2

```text
Vehicle B
10:30 → 11:00
```

### Trip 2

```text
10:30 → 11:00
18 km
```

LocationHistory:

```text
10:00
10:05
10:10
10:20
10:30
10:40
10:50
11:00
```

همه:

```text
device_id = 100
```

هستند.

پس:

```text
Trip
→ تقسیم شده

LocationHistory
→ تقسیم نشده

Device
→ همان Device

Session
→ قطع نشده

CurrentState
→ همان Snapshot

Assignment
→ Context تغییر کرده
```

---

# 26. قاعده نهایی Trip

```text
Trip belongs to Device.

Trip operates within one stable
DeviceVehicleAssignment interval.

Assignment End
→ Active Trip completes.

Assignment Start
→ Does NOT automatically start a Trip.

Future movement
→ may start a new Trip.

Telemetry/LocationHistory
→ continue independently.

Session
→ remains connected.

CurrentState
→ remains Device-owned.
```

---

# 27. اصلاح تصمیم قبلی

از این لحظه عبارت:

```text
"Assignment Change can be a Trip Boundary"
```

به شکل دقیق‌تر زیر ثبت می‌شود:

> **Assignment Change یک Hard Boundary برای Trip است. هر Trip فقط در محدوده یک DeviceVehicleAssignment قرار می‌گیرد. در نتیجه تغییر Assignment، Trip فعال را در همان لحظه Complete می‌کند، اما به‌تنهایی Trip جدید ایجاد نمی‌کند.**

این تصمیم با Device-owned بودن Trip، Vehicle Historical Reporting و Device-owned بودن LocationHistory کاملاً سازگار است.

---

# 28. وضعیت نهایی

```text
[✓] Trip belongs to Device
[✓] Assignment is temporal context
[✓] One Trip = one stable Assignment interval
[✓] Assignment End = Trip Hard Boundary
[✓] Assignment Start ≠ automatic Trip Start
[✓] Telemetry continues
[✓] LocationHistory continues
[✓] Session continues
[✓] CurrentState remains unchanged
[✓] Vehicle Historical Query remains deterministic
[✓] State Events close at Assignment Boundary
[✓] Point Events remain Device-owned
[✓] Device Replacement creates Assignment Boundary
[✓] Backdated Assignment does not auto-rebuild Trip in MVP

### تصمیم قطعی

Assignment Boundary
        ↓
Complete Active Trip
        ↓
Future Telemetry
        ↓
Normal Trip Start Rules
        ↓
Potential New Trip
```

**تعارض Trip و Assignment در SANA — CLOSED**


============================================================================
============================================================================

# SANA GPS — تصمیمات قطعی WebSocket و Live Map

## مرحله ۲۱ معماری GPS

هدف:

> **WebSocket فقط کانال Delivery برای CurrentStateهای Commit‌شده است؛ CurrentState و DeviceVehicleAssignment منابع داده هستند، Backend مسئول Permission و Delivery است و Frontend مسئول Presentation است.**

---

# 1. واژه‌های قطعی

برای جلوگیری از چندنامی، اصطلاحات زیر در کل SANA استاندارد هستند.

| اصطلاح                  | معنی قطعی                                                  |
| ----------------------- | ---------------------------------------------------------- |
| `CurrentState`          | آخرین وضعیت Snapshot یک Device                             |
| `CurrentState Snapshot` | محتوای فعلی `CurrentState` در یک لحظه                      |
| `state_version`         | شماره نسخه Snapshot مربوط به همان Device                   |
| `Snapshot Update`       | تغییر پذیرفته‌شده در CurrentState                          |
| `Delta`                 | پیام WebSocket که فقط تغییرات CurrentState را منتقل می‌کند |
| `Signal`                | اعلان غیرقابل‌اتکای تغییر برای شروع Read از Database       |
| `NOTIFY`                | مکانیزم PostgreSQL برای ارسال Signal                       |
| `Reconciliation`        | همگام‌سازی Backend با وضعیت فعلی Database                  |
| `Resync`                | همگام‌سازی Client با CurrentState فعلی                     |
| `Source of Truth`       | منبع اصلی و معتبر داده                                     |
| `Delivery`              | انتقال داده از Backend به Client                           |
| `Permission`            | کنترل دسترسی Server-side                                   |
| `Projection`            | مدل سبک مخصوص مصرف Live Map یا Client                      |
| `Connection State`      | وضعیت محاسبه‌شده ارتباط Device با Server                   |
| `Device Time`           | زمان گزارش‌شده توسط Device                                 |
| `Server Received Time`  | زمان دریافت Packet در Server                               |

---

# 2. مالکیت WebSocket

WebSocket متعلق به:

```text
sana-backend
```

است.

`sana-gps` مستقیماً با Browser ارتباط WebSocket ندارد.

```text
sana-gps
→ GPS Runtime

sana-backend
→ API
→ Permission
→ WebSocket
```

---

# 3. CurrentState منبع وضعیت لحظه‌ای

مسیر صحیح:

```text
Telemetry
   ↓
Database Transaction
   ↓
CurrentState
   ↓
COMMIT
   ↓
NOTIFY Signal
   ↓
Backend
   ↓
Read CurrentState
   ↓
Permission
   ↓
WebSocket Delivery
```

WebSocket فقط CurrentStateای را ارسال می‌کند که در Database Commit شده است.

---

# 4. PostgreSQL NOTIFY

در MVP از:

```text
PostgreSQL LISTEN / NOTIFY
```

به‌عنوان Signal سریع استفاده می‌کنیم.

مثلاً:

```json
{
  "device_id": 125
}
```

اما:

```text
NOTIFY ≠ Queue
NOTIFY ≠ Source of Truth
NOTIFY ≠ Durable Message
NOTIFY ≠ Event Log
NOTIFY ≠ WebSocket Message
```

وظیفه NOTIFY فقط این است:

> به Backend اطلاع دهد که احتمالاً State مربوط به یک Device تغییر کرده است.

Backend سپس CurrentState را از PostgreSQL می‌خواند.

---

# 5. NOTIFY قابل اتکا برای Delivery نیست

ممکن است Signal از دست برود.

```text
Backend disconnected
       ↓
CurrentState updated
       ↓
NOTIFY
       ↓
Backend did not receive Signal
```

اما:

```text
gps.current_state
```

در PostgreSQL باقی می‌ماند.

بنابراین:

```text
NOTIFY Loss
≠
CurrentState Loss
```

---

# 6. Reconciliation

`Reconciliation` مکانیزم Recovery داخلی Backend است.

تعریف قطعی:

> **Reconciliation یعنی مقایسه و همگام‌سازی وضعیت موردنیاز Backend با CurrentState موجود در PostgreSQL.**

---

# 7. Resync

`Resync` با `Reconciliation` متفاوت است.

### Reconciliation

Backend را با Database هماهنگ می‌کند:

```text
Backend
   ↓
PostgreSQL
   ↓
CurrentState
```

### Resync

Client را با CurrentState فعلی هماهنگ می‌کند:

```text
Client
   ↓
Backend
   ↓
CurrentState
   ↓
Client
```

بنابراین:

```text
Reconciliation ≠ Resync
```

---

# 8. Permission

Permission کاملاً Server-side است.

مدل صحیح:

```text
User
 ↓
Permission
 ↓
Allowed Devices / Vehicles
 ↓
WebSocket
 ↓
Authorized Data
```

Device غیرمجاز نباید به Browser ارسال شود.

Subscription هرگز Permission ایجاد نمی‌کند.

---

# 9. Subscription

Client می‌تواند درخواست Subscription بدهد:

```json
{
  "type": "SUBSCRIBE_DEVICES",
  "request_id": "req_123",
  "devices": [125, 126]
}
```

یا:

```json
{
  "type": "SUBSCRIBE_VEHICLES",
  "request_id": "req_124",
  "vehicles": [10, 20, 30]
}
```

Backend ابتدا Permission را بررسی می‌کند.

---

# 10. WebSocket Protocol Version

تمام Messageها دارای:

```text
protocol_version
```

هستند.

نسخه اولیه:

```text
protocol_version = 1
```

است.

این Version مربوط به **قرارداد WebSocket** است و با:

```text
state_version
profile_version
device_time
```

متفاوت است.

---

# 11. Message Envelope

تمام پیام‌های WebSocket از Envelope استاندارد استفاده می‌کنند.

ساختار:

```json
{
  "protocol_version": 1,
  "type": "MESSAGE_TYPE",
  "request_id": "req_123",
  "message_id": "msg_456",
  "server_timestamp": "2026-10-06T10:00:03.125Z",
  "data": {}
}
```

فیلدها:

| Field              |    Required | Meaning                         |
| ------------------ | ----------: | ------------------------------- |
| `protocol_version` |         Yes | نسخه قرارداد WebSocket          |
| `type`             |         Yes | نوع Message                     |
| `request_id`       | Conditional | شناسه Request مربوطه            |
| `message_id`       |         Yes | شناسه یکتای Message Server      |
| `server_timestamp` |         Yes | زمان تولید Message توسط Backend |
| `data`             |         Yes | Payload مخصوص Message           |

---

# 12. request_id

`request_id` توسط Client برای Requestهایی که نیاز به Response دارند تولید می‌شود.

مثلاً:

```json
{
  "protocol_version": 1,
  "type": "SUBSCRIBE_DEVICES",
  "request_id": "req_123",
  "data": {
    "devices": [125, 126]
  }
}
```

Backend Response همان:

```text
request_id = req_123
```

را برمی‌گرداند.

این باعث می‌شود Client بتواند Response را به Request مربوطه متصل کند.

---

# 13. message_id

هر Message صادرشده توسط Backend دارای:

```text
message_id
```

است.

این شناسه برای:

* Debug
* Logging
* Traceability
* Correlation

است.

`message_id` معیار Ordering State نیست.

Ordering State با:

```text
device_id + state_version
```

انجام می‌شود.

---

# 14. server_timestamp

```text
server_timestamp
```

زمان تولید Message توسط Backend است.

این مقدار:

```text
device_time
```

نیست.

مثلاً:

```json
{
  "server_timestamp": "2026-10-06T10:00:03Z"
}
```

فقط زمان Server را نشان می‌دهد.

تمام Timestampهای Protocol:

```text
UTC / ISO-8601
```

هستند.

---

# 15. Client → Server Messages

در MVP پیام‌های Client:

```text
AUTH
SUBSCRIBE_DEVICES
SUBSCRIBE_VEHICLES
UNSUBSCRIBE
RESYNC
SET_VIEWPORT
PING
```

هستند.

---

# 16. AUTH

اگر Authentication خارج از WebSocket انجام نشده باشد، Client می‌تواند Authentication را روی WebSocket انجام دهد.

```json
{
  "protocol_version": 1,
  "type": "AUTH",
  "request_id": "req_001",
  "data": {
    "token": "..."
  }
}
```

Response موفق:

```json
{
  "protocol_version": 1,
  "type": "AUTH_ACK",
  "request_id": "req_001",
  "data": {
    "authenticated": true
  }
}
```

Token واقعی نباید در Log ذخیره شود.

اگر Authentication شکست بخورد:

```text
ERROR
```

ارسال می‌شود و Connection می‌تواند بسته شود.

---

# 17. SUBSCRIBE_DEVICES

Request:

```json
{
  "protocol_version": 1,
  "type": "SUBSCRIBE_DEVICES",
  "request_id": "req_100",
  "data": {
    "device_ids": [125, 126, 127]
  }
}
```

Backend:

1. Authentication را بررسی می‌کند.
2. Permission را بررسی می‌کند.
3. Deviceهای مجاز را مشخص می‌کند.
4. Subscription را ثبت می‌کند.
5. CurrentState Snapshot را می‌خواند.
6. Snapshot اولیه را ارسال می‌کند.

---

# 18. SUBSCRIBE_DEVICES Response

```json
{
  "protocol_version": 1,
  "type": "SUBSCRIPTION_ACK",
  "request_id": "req_100",
  "data": {
    "scope": "DEVICES",
    "requested_device_ids": [125, 126, 127],
    "accepted_device_ids": [125, 126],
    "rejected_device_ids": [127]
  }
}
```

Device غیرمجاز در Response می‌تواند با دلیل عمومی:

```text
FORBIDDEN
```

مشخص شود.

نباید اطلاعات حساس درباره Device غیرمجاز افشا شود.

---

# 19. SUBSCRIBE_VEHICLES

Request:

```json
{
  "protocol_version": 1,
  "type": "SUBSCRIBE_VEHICLES",
  "request_id": "req_200",
  "data": {
    "vehicle_ids": [10, 20]
  }
}
```

Backend رابطه را از:

```text
DeviceVehicleAssignment
```

Resolve می‌کند.

سپس:

```text
Vehicle
   ↓
Active Device
   ↓
CurrentState
```

را پیدا می‌کند.

---

# 20. Subscription و Assignment

Subscription به Vehicle باید Dynamic باشد.

یعنی اگر:

```text
Vehicle 10
→ Device 125
```

و بعد:

```text
Vehicle 10
→ Device 200
```

شود، Subscription مربوط به Vehicle 10 باید Device فعال جدید را در نظر بگیرد.

Source of Truth همچنان:

```text
gps.device_vehicle_assignment
```

است.

---

# 21. UNSUBSCRIBE

Request:

```json
{
  "protocol_version": 1,
  "type": "UNSUBSCRIBE",
  "request_id": "req_300",
  "data": {
    "scope": "DEVICES",
    "ids": [125, 126]
  }
}
```

یا:

```json
{
  "protocol_version": 1,
  "type": "UNSUBSCRIBE",
  "request_id": "req_301",
  "data": {
    "scope": "VEHICLES",
    "ids": [10]
  }
}
```

Response:

```json
{
  "protocol_version": 1,
  "type": "SUBSCRIPTION_ACK",
  "request_id": "req_300",
  "data": {
    "action": "UNSUBSCRIBE"
  }
}
```

---

# 22. SET_VIEWPORT

برای کاهش Delivery غیرضروری در Live Map:

```json
{
  "protocol_version": 1,
  "type": "SET_VIEWPORT",
  "request_id": "req_400",
  "data": {
    "north": 35.80,
    "south": 35.60,
    "east": 51.60,
    "west": 51.20
  }
}
```

Viewport فقط یک Optimization برای Delivery است.

Viewport Permission را تغییر نمی‌دهد.

Backend هرگز نباید Device غیرمجاز را صرفاً به دلیل Viewport ارسال کند.

---

# 23. RESYNC

Client وقتی:

* Gap در `state_version` تشخیص دهد،
* Reconnect کند،
* احتمال از دست رفتن Message داشته باشد،

می‌تواند درخواست Resync بدهد.

Request:

```json
{
  "protocol_version": 1,
  "type": "RESYNC",
  "request_id": "req_500",
  "data": {
    "devices": [
      {
        "device_id": 125,
        "state_version": 104
      },
      {
        "device_id": 126,
        "state_version": 88
      }
    ]
  }
}
```

---

# 24. RESYNC Response

Backend فقط Deviceهای مجاز را بررسی می‌کند.

برای هر Device که Snapshot جدیدتر دارد:

```text
DEVICE_STATE
```

ارسال می‌شود.

اگر Version برابر باشد:

```text
No State Delivery
```

لازم نیست Snapshot دوباره ارسال شود، مگر Client صراحتاً Full Resync بخواهد.

---

# 25. Full Resync

Client می‌تواند:

```json
{
  "protocol_version": 1,
  "type": "RESYNC",
  "request_id": "req_501",
  "data": {
    "full": true,
    "device_ids": [125, 126]
  }
}
```

ارسال کند.

در این حالت Backend Snapshot فعلی را بدون توجه به Version محلی Client ارسال می‌کند.

---

# 26. PING

Client:

```json
{
  "protocol_version": 1,
  "type": "PING",
  "request_id": "req_600",
  "data": {}
}
```

Server:

```json
{
  "protocol_version": 1,
  "type": "PONG",
  "request_id": "req_600",
  "data": {}
}
```

PING مربوط به:

```text
WebSocket Connection
```

است و با Device Heartbeat ارتباطی ندارد.

---

# 27. Server → Client Messages

پیام‌های اصلی Server:

```text
AUTH_ACK
SUBSCRIPTION_ACK
DEVICE_STATE
DEVICE_STATE_DELTA
DEVICE_ASSIGNMENT_CHANGED
CONNECTION_STATE_CHANGED
ERROR
PONG
```

---

# 28. DEVICE_STATE

`DEVICE_STATE` یک Snapshot کامل از Projection موردنیاز Client است.

نمونه:

```json
{
  "protocol_version": 1,
  "type": "DEVICE_STATE",
  "message_id": "msg_1001",
  "server_timestamp": "2026-10-06T10:00:03Z",
  "data": {
    "device_id": 125,
    "state_version": 1043,
    "device_time": "2026-10-06T09:59:58Z",
    "server_received_at": "2026-10-06T10:00:03Z",
    "last_seen": "2026-10-06T10:00:03Z",
    "connection_state": "ONLINE",
    "position": {
      "latitude": 35.700000,
      "longitude": 51.400000,
      "gps_valid": true,
      "accuracy": 5.2
    },
    "speed": 82.4,
    "heading": 140.0,
    "motion": "MOVING",
    "ignition": true,
    "satellites": 14
  }
}
```

---

# 29. DEVICE_STATE Projection

Projection استاندارد MVP:

```text
device_id
vehicle_id
state_version

device_time
server_received_at
last_seen
connection_state

position
├── latitude
├── longitude
├── gps_valid
└── accuracy

speed
heading
motion
ignition
satellites

battery_voltage
external_voltage
gsm_signal

odometer
engine_hours
fuel_level

selected attributes
```

Backend می‌تواند در آینده Projectionهای مختلف داشته باشد، ولی Semantics CurrentState باید یکسان بماند.

---

# 30. Position Contract

اگر:

```text
gps_valid = true
```

باشد:

```json
{
  "position": {
    "latitude": 35.700000,
    "longitude": 51.400000,
    "gps_valid": true,
    "accuracy": 5.2
  }
}
```

اگر:

```text
gps_valid = false
```

باشد:

```json
{
  "position": {
    "latitude": null,
    "longitude": null,
    "gps_valid": false,
    "accuracy": null
  }
}
```

Last Valid Position در صورت نیاز به‌صورت مفهوم جداگانه ارائه می‌شود و نباید با Position فعلی مخلوط شود.

---

# 31. DEVICE_STATE_DELTA

Delta فقط تغییرات Projection را منتقل می‌کند.

نمونه:

```json
{
  "protocol_version": 1,
  "type": "DEVICE_STATE_DELTA",
  "message_id": "msg_1002",
  "server_timestamp": "2026-10-06T10:00:05Z",
  "data": {
    "device_id": 125,
    "state_version": 1044,
    "changed": {
      "speed": 90.0,
      "heading": 145.0
    }
  }
}
```

Client باید Delta را فقط روی Snapshot قبلی همان Device اعمال کند.

---

# 32. Delta بدون Snapshot معتبر

اگر Client Snapshot پایه را ندارد:

```text
DEVICE_STATE_DELTA
```

را نباید به‌صورت مستقل اعمال کند.

Client باید:

```text
RESYNC
```

درخواست کند.

---

# 33. Delta Version

اگر Client دارد:

```text
state_version = 1043
```

و Delta دریافت کند:

```text
state_version = 1044
```

مجاز است.

اما اگر:

```text
Client = 1043
Delta = 1046
```

باشد:

```text
Gap
```

وجود دارد و Client باید:

```text
RESYNC
```

کند.

---

# 34. Delta فقط برای CurrentState

Delta فقط برای:

```text
CurrentState Projection
```

است.

Delta برای:

```text
Event
Trip
Alert
Notification
Command
```

در MVP تعریف نمی‌شود.

---

# 35. DEVICE_ASSIGNMENT_CHANGED

این Message تغییر Context Device/Vehicle را اعلام می‌کند.

نمونه:

```json
{
  "protocol_version": 1,
  "type": "DEVICE_ASSIGNMENT_CHANGED",
  "message_id": "msg_2001",
  "server_timestamp": "2026-10-06T10:30:00Z",
  "data": {
    "device_id": 125,
    "previous_vehicle_id": 10,
    "current_vehicle_id": 20,
    "effective_at": "2026-10-06T10:30:00Z"
  }
}
```

این Message:

```text
state_version
```

ندارد.

زیرا Assignment Version با CurrentState Version یکی نیست.

---

# 36. Assignment Change و State

مثلاً:

```text
Device 125
state_version = 100
```

Assignment تغییر می‌کند.

پس از Assignment:

```text
state_version = 100
```

همچنان معتبر است.

اما:

```text
DEVICE_ASSIGNMENT_CHANGED
```

پیام جداگانه ارسال می‌شود.

---

# 37. CONNECTION_STATE_CHANGED

Connection State از:

```text
last_seen
+
offline_timeout
```

محاسبه می‌شود.

نمونه:

```json
{
  "protocol_version": 1,
  "type": "CONNECTION_STATE_CHANGED",
  "message_id": "msg_3001",
  "server_timestamp": "2026-10-06T10:35:00Z",
  "data": {
    "device_id": 125,
    "connection_state": "OFFLINE",
    "last_seen": "2026-10-06T10:29:00Z"
  }
}
```

این Message:

```text
state_version
```

ندارد.

---

# 38. Connection State Values

مقادیر:

```text
NEVER_SEEN
ONLINE
OFFLINE
```

هستند.

`connection_state` در Database ذخیره نمی‌شود.

---

# 39. ERROR

تمام خطاهای WebSocket از Contract مشخص استفاده می‌کنند.

نمونه:

```json
{
  "protocol_version": 1,
  "type": "ERROR",
  "request_id": "req_500",
  "message_id": "msg_error_1",
  "server_timestamp": "2026-10-06T10:40:00Z",
  "data": {
    "code": "FORBIDDEN",
    "message": "Access denied",
    "details": {}
  }
}
```

---

# 40. Error Codeهای اولیه

```text
AUTH_REQUIRED
AUTH_FAILED
INVALID_MESSAGE
UNSUPPORTED_PROTOCOL_VERSION
UNKNOWN_MESSAGE_TYPE

FORBIDDEN
DEVICE_NOT_FOUND
VEHICLE_NOT_FOUND

INVALID_SUBSCRIPTION
INVALID_DEVICE_ID
INVALID_VEHICLE_ID

INVALID_VIEWPORT

RESYNC_REQUIRED
RESYNC_FAILED

RATE_LIMITED
SERVER_UNAVAILABLE
INTERNAL_ERROR
```

پیام Error نباید اطلاعات داخلی Database، SQL، Stack Trace، Token یا Secret را افشا کند.

---

# 41. Error Handling

خطاهای Request-specific:

```text
request_id
```

دارند.

مثلاً:

```text
SUBSCRIBE_DEVICES
→ ERROR
→ همان request_id
```

خطاهای Connection-level ممکن است `request_id` نداشته باشند.

---

# 42. Unknown Message Type

اگر Client پیام ناشناخته بفرستد:

```json
{
  "type": "UNKNOWN_TYPE"
}
```

Backend:

```text
ERROR
code = UNKNOWN_MESSAGE_TYPE
```

ارسال می‌کند.

Connection لزوماً برای یک Message ناشناخته بسته نمی‌شود، مگر اینکه رفتار Client مخرب یا غیرقابل‌قبول باشد.

---

# 43. Unsupported Protocol Version

اگر:

```text
protocol_version
```

پشتیبانی نشود:

```text
ERROR
code = UNSUPPORTED_PROTOCOL_VERSION
```

ارسال می‌شود.

در صورت ناسازگاری بنیادی، Backend می‌تواند Connection را ببندد.

---

# 44. Message Size Limit

WebSocket Message دارای حداکثر اندازه مشخص خواهد بود.

Message بزرگ نباید باعث مصرف نامحدود Memory شود.

قاعده:

```text
MAX_WEBSOCKET_MESSAGE_SIZE
```

باید Configurable باشد.

Payloadهای غیرضروری و Attributes بزرگ نباید وارد Live Map Projection شوند.

---

# 45. Rate Limit

برای Clientها محدودیت منطقی روی Requestهای:

```text
SUBSCRIBE
RESYNC
SET_VIEWPORT
PING
```

اعمال می‌شود.

خصوصاً:

```text
RESYNC
```

نباید بتواند به‌صورت نامحدود Database Query ایجاد کند.

---

# 46. Subscription Limit

Client نباید بتواند بدون محدودیت:

```text
10000
20000
...
```

Subscription ایجاد کند.

حدود اولیه:

```text
MAX_SUBSCRIBED_DEVICES
MAX_SUBSCRIBED_VEHICLES
```

قابل تنظیم هستند.

مقدار دقیق در مرحله Performance/Load Test تعیین می‌شود.

---

# 47. WebSocket Backpressure

اگر Client کند باشد:

```text
Backend
   ↓
WebSocket Buffer
   ↓
Client Slow
```

Backend نباید بدون محدودیت پیام در Memory نگه دارد.

برای Live State:

> **آخرین State از Stateهای قدیمی مهم‌تر است.**

بنابراین در صورت فشار شدید می‌توان:

```text
Old Pending State Updates
```

را Coalesce کرد و آخرین Snapshot را نگه داشت.

---

# 48. Coalescing

مثلاً:

```text
state_version 100
state_version 101
state_version 102
state_version 103
```

در زمان کوتاه تولید شده‌اند.

اگر Client هنوز:

```text
100
```

است، Backend الزاماً نباید چهار Message جدا ارسال کند.

می‌تواند آخرین Snapshot:

```text
103
```

را ارسال کند.

Client پس از دریافت:

```text
103
```

در وضعیت صحیح قرار می‌گیرد.

اگر Delta Gap ایجاد شود:

```text
RESYNC
```

انجام می‌شود.

---

# 49. NOTIFY و Coalescing

ممکن است:

```text
NOTIFY
NOTIFY
NOTIFY
```

برای یک Device دریافت شود.

Backend می‌تواند آنها را Coalesce کند:

```text
Device 125
→ Read CurrentState once
```

و فقط آخرین State را برای Client ارسال کند.

---

# 50. Initial Snapshot Race

ترتیب قطعی:

```text
1. Authentication
2. Permission
3. Register Subscription
4. Read CurrentState
5. Send DEVICE_STATE
6. Deliver newer State Updates
```

اگر Update بین مرحله 4 و 5 رخ دهد، Backend باید با Version آن را تشخیص دهد.

Temporary Buffer می‌تواند برای عبور از این Race استفاده شود.

---

# 51. Temporary Buffer

Temporary Buffer:

* Durable نیست.
* Source of Truth نیست.
* History نیست.
* فقط برای Initial Snapshot Race است.

اگر Connection از بین برود:

```text
Buffer
→ Discard
```

Client بعد از Reconnect:

```text
RESYNC
```

می‌کند.

---

# 52. Client State Machine

برای هر Device، Client مفهوماً:

```text
UNKNOWN
   ↓
SNAPSHOT_RECEIVED
   ↓
LIVE
```

دارد.

اگر Gap تشخیص داده شود:

```text
LIVE
 ↓
RESYNC_REQUIRED
 ↓
SNAPSHOT_RECEIVED
 ↓
LIVE
```

اگر Connection قطع شود:

```text
LIVE
 ↓
DISCONNECTED
 ↓
RECONNECT
 ↓
RESYNC
 ↓
LIVE
```

---

# 53. Client Version Rule

Client برای هر Device آخرین:

```text
state_version
```

را نگه می‌دارد.

اگر پیام:

```text
incoming_version <= local_version
```

باشد:

```text
Ignore
```

اگر:

```text
incoming_version == local_version + 1
```

باشد:

```text
Accept
```

اگر:

```text
incoming_version > local_version + 1
```

باشد:

```text
RESYNC
```

---

# 54. Snapshot Acceptance

`DEVICE_STATE` یک Snapshot است.

اگر:

```text
incoming_version > local_version
```

باشد:

```text
Replace Local Snapshot
```

اگر:

```text
incoming_version < local_version
```

باشد:

```text
Ignore
```

Client نباید Snapshot قدیمی را روی Snapshot جدید بنویسد.

---

# 55. CurrentState Version اولیه

برای Device تازه ساخته‌شده:

```text
state_version = 0
```

است.

قبل از اولین Snapshot:

```text
device_time = NULL
last_seen = NULL
state_version = 0
```

بعد از اولین CurrentState Update:

```text
state_version = 1
```

---

# 56. Heartbeat

Heartbeat معمولی Device:

```text
last_seen
```

را ممکن است Update کند.

اما:

```text
state_version
```

را افزایش نمی‌دهد.

Heartbeat Device با:

```text
PING
PONG
```

WebSocket یکی نیست.

---

# 57. GPS No-Fix

اگر Telemetry جدیدتر باشد:

```text
gps_valid = false
```

CurrentState Snapshot Update می‌شود:

```text
latitude = NULL
longitude = NULL
gps_valid = false
```

و:

```text
state_version += 1
```

اما:

```text
last_valid_position
```

حفظ می‌شود.

---

# 58. Device Replacement

اگر Device تغییر کند:

```text
Vehicle A
→ Device 100
```

به:

```text
Vehicle A
→ Device 200
```

تبدیل شود:

```text
DEVICE_ASSIGNMENT_CHANGED
```

ارسال می‌شود.

CurrentState Device 200 مستقل است:

```text
state_version = 0
```

تا اولین Snapshot آن.

Version Device 100 هیچ ارتباطی با Device 200 ندارد.

---

# 59. Marker Clustering

Clustering در Frontend انجام می‌شود.

Backend فقط Stateهای مجاز را ارسال می‌کند.

Frontend بر اساس:

```text
Zoom
Viewport
Position
```

Cluster ایجاد می‌کند.

---

# 60. Historical Map

Historical Map مستقل از WebSocket است:

```text
LocationHistory
   ↓
REST API
   ↓
Polyline / Playback
```

Live Map:

```text
CurrentState
   ↓
WebSocket
```

---

# 61. WebSocket Business Logic ندارد

WebSocket نباید انجام دهد:

```text
Trip Detection
Event Detection
Geofence Detection
Fuel Calculation
```

وظیفه:

```text
CurrentState Read
→ Permission
→ Projection
→ Delivery
```

است.

---

# 62. Message Contract Summary

## Client → Server

| Type                 | `request_id` | Response                    | کاربرد              |
| -------------------- | -----------: | --------------------------- | ------------------- |
| `AUTH`               |          Yes | `AUTH_ACK` / `ERROR`        | Authentication      |
| `SUBSCRIBE_DEVICES`  |          Yes | `SUBSCRIPTION_ACK`          | Subscribe Device    |
| `SUBSCRIBE_VEHICLES` |          Yes | `SUBSCRIPTION_ACK`          | Subscribe Vehicle   |
| `UNSUBSCRIBE`        |          Yes | `SUBSCRIPTION_ACK`          | حذف Subscription    |
| `SET_VIEWPORT`       |          Yes | `SUBSCRIPTION_ACK` یا Error | بهینه‌سازی Delivery |
| `RESYNC`             |          Yes | `DEVICE_STATE` / Error      | Recovery Client     |
| `PING`               |          Yes | `PONG`                      | Connection Health   |

## Server → Client

| Type                        |   `request_id` | `state_version` | کاربرد                 |
| --------------------------- | -------------: | --------------: | ---------------------- |
| `AUTH_ACK`                  |            Yes |              No | Authentication Result  |
| `SUBSCRIPTION_ACK`          |            Yes |              No | Subscription Result    |
| `DEVICE_STATE`              | No/Conditional |             Yes | Snapshot               |
| `DEVICE_STATE_DELTA`        |             No |             Yes | State Delta            |
| `DEVICE_ASSIGNMENT_CHANGED` |             No |              No | Vehicle Context Change |
| `CONNECTION_STATE_CHANGED`  |             No |              No | Connection State       |
| `PONG`                      |            Yes |              No | Ping Response          |
| `ERROR`                     |    Conditional |              No | Error                  |

---

# 63. Contract نمونه کامل Live Flow

### مرحله ۱ — Subscribe

```json
{
  "protocol_version": 1,
  "type": "SUBSCRIBE_DEVICES",
  "request_id": "req_100",
  "data": {
    "device_ids": [125]
  }
}
```

### مرحله ۲ — ACK

```json
{
  "protocol_version": 1,
  "type": "SUBSCRIPTION_ACK",
  "request_id": "req_100",
  "message_id": "msg_1",
  "server_timestamp": "2026-10-06T10:00:00Z",
  "data": {
    "scope": "DEVICES",
    "accepted_device_ids": [125],
    "rejected_device_ids": []
  }
}
```

### مرحله ۳ — Initial Snapshot

```json
{
  "protocol_version": 1,
  "type": "DEVICE_STATE",
  "message_id": "msg_2",
  "server_timestamp": "2026-10-06T10:00:00Z",
  "data": {
    "device_id": 125,
    "state_version": 100,
    "device_time": "2026-10-06T09:59:58Z",
    "last_seen": "2026-10-06T10:00:00Z",
    "connection_state": "ONLINE",
    "position": {
      "latitude": 35.700000,
      "longitude": 51.400000,
      "gps_valid": true
    },
    "speed": 80,
    "heading": 140,
    "ignition": true,
    "motion": "MOVING"
  }
}
```

### مرحله ۴ — State Update

```json
{
  "protocol_version": 1,
  "type": "DEVICE_STATE_DELTA",
  "message_id": "msg_3",
  "server_timestamp": "2026-10-06T10:00:05Z",
  "data": {
    "device_id": 125,
    "state_version": 101,
    "changed": {
      "speed": 85
    }
  }
}
```

### مرحله ۵ — Assignment Change

```json
{
  "protocol_version": 1,
  "type": "DEVICE_ASSIGNMENT_CHANGED",
  "message_id": "msg_4",
  "server_timestamp": "2026-10-06T10:30:00Z",
  "data": {
    "device_id": 125,
    "previous_vehicle_id": 10,
    "current_vehicle_id": 20,
    "effective_at": "2026-10-06T10:30:00Z"
  }
}
```

### مرحله ۶ — Connection State

```json
{
  "protocol_version": 1,
  "type": "CONNECTION_STATE_CHANGED",
  "message_id": "msg_5",
  "server_timestamp": "2026-10-06T10:35:00Z",
  "data": {
    "device_id": 125,
    "connection_state": "OFFLINE",
    "last_seen": "2026-10-06T10:29:59Z"
  }
}
```

---

# 64. قواعد قطعی WebSocket

```text
[✓] WebSocket در sana-backend است
[✓] sana-gps مستقیماً WebSocket ندارد
[✓] CurrentState منبع وضعیت لحظه‌ای است
[✓] WebSocket فقط Stateهای Commit‌شده را Delivery می‌کند
[✓] NOTIFY فقط Signal است
[✓] Reconciliation برای Recovery Backend است
[✓] Resync برای Recovery Client است
[✓] Permission کاملاً Server-side است
[✓] Subscription منبع Permission نیست

[✓] protocol_version نسخه قرارداد WebSocket است
[✓] state_version نسخه CurrentState همان Device است
[✓] message_id شناسه Message است
[✓] request_id برای Correlation Request/Response است
[✓] server_timestamp زمان تولید Message توسط Backend است

[✓] DEVICE_STATE یک Snapshot است
[✓] DEVICE_STATE_DELTA فقط تغییرات Snapshot است
[✓] Delta بدون Snapshot معتبر قابل اعمال نیست
[✓] Gap باعث RESYNC می‌شود
[✓] Reconnect با Snapshot انجام می‌شود

[✓] state_version از 0 شروع می‌شود
[✓] اولین Snapshot Update باعث 0 → 1 می‌شود
[✓] state_version فقط با Snapshot Update افزایش می‌یابد
[✓] state_version هیچ‌گاه کاهش نمی‌یابد
[✓] Duplicate باعث افزایش state_version نمی‌شود
[✓] Heartbeat باعث افزایش state_version نمی‌شود
[✓] Assignment Change باعث افزایش state_version نمی‌شود
[✓] Connection State باعث افزایش state_version نمی‌شود

[✓] Assignment Change Message مستقل دارد
[✓] Connection State Message مستقل دارد
[✓] Historical Map مستقل از WebSocket است
[✓] Marker Clustering در Frontend است
[✓] WebSocket Business Logic ندارد

[✓] Message Size محدود است
[✓] Subscription محدود است
[✓] RESYNC محدود و کنترل‌شده است
[✓] Client کند نباید Memory نامحدود مصرف کند
[✓] Stateهای قدیمی در فشار شدید قابل Coalesce هستند
[✓] Temporary Buffer فقط برای Initial Snapshot Race است
[✓] Temporary Buffer Durable نیست
[✓] PostgreSQL Source of Truth باقی می‌ماند
```

---

# اصل نهایی

> **WebSocket در SANA یک Delivery Channel برای وضعیت لحظه‌ای است، نه Source of Truth و نه Event Stream. `DEVICE_STATE` Snapshot کامل و `DEVICE_STATE_DELTA` تغییرات Snapshot هستند. `state_version` فقط نسخه CurrentState همان Device است و از صفر شروع می‌شود. Client با Version Gap را تشخیص می‌دهد و در صورت نیاز `RESYNC` می‌کند. `NOTIFY` فقط Signal است، `Reconciliation` Backend را با PostgreSQL هماهنگ می‌کند و `Resync` Client را با CurrentState هماهنگ می‌کند.**

> **هیچ‌کدام از این مکانیزم‌ها در MVP مسئول Replay تاریخچه Event، Alert، Notification یا Deltaهای قدیمی نیستند. PostgreSQL و Entityهای اصلی SANA همچنان Source of Truth باقی می‌مانند.**

**قرارداد کامل WebSocket شامل Envelope، Message Typeها، Request/Response، Snapshot، Delta، Versioning، Permission، Subscription، Resync، Error، Backpressure و نمونه Flow به‌عنوان قرارداد رسمی مرحله ۲۱ ثبت شد.**


============================================================================
============================================================================

# SANA GPS — Stage 22

# طراحی نهایی Command Runtime

## وضعیت

```text
Stage: 22
Status: CLOSED
Scope: Command Runtime
```

هدف این بخش طراحی کامل مسیر اجرای Command از ایجاد توسط Backend تا ارسال به GPS Device و دریافت نتیجه است.

اصل اصلی:

> `sana-backend` مالک Business Command است و `sana-gps` فقط مسئول اجرای فنی Command روی Device است.

---

# 1. مرز مسئولیت

معماری:

```text
sana-backend
      ↓
gps.command
      ↓
sana-gps
      ↓
Active Session
      ↓
Protocol Encoder
      ↓
Transport
      ↓
GPS Device
```

### sana-backend

مسئول:

* Authentication
* Authorization
* Permission
* Business Validation
* ایجاد Command
* تعیین Device
* ثبت درخواست کاربر
* Cancel کردن Command در محدوده مجاز
* نمایش وضعیت Command

### sana-gps

مسئول:

* دریافت Command از Database
* Queue/Scheduler
* Claim
* بررسی Lifecycle و Session
* پیدا کردن Session مناسب
* Encoding
* ارسال Bytes
* دریافت ACK/Response
* تشخیص نتیجه فنی
* Retry فنی
* Timeout
* ثبت وضعیت اجرای Command

`sana-gps` نباید خودش تصمیم Business برای ایجاد Command بگیرد.

همچنین Backend هرگز مستقیماً به Socket دستگاه دسترسی ندارد.

---

# 2. Source of Truth

جدول:

```text
gps.command
```

Source of Truth دائمی Command است.

Runtime Memory فقط برای:

* Scheduling
* Session lookup
* In-flight execution
* Timeout handling
* Transport state

استفاده می‌شود.

اگر `sana-gps` Restart شود، وضعیت Command از PostgreSQL قابل بازیابی است.

---

# 3. مدل Command

مدل نهایی:

```text
gps.command
├── id
├── device_id
├── type
├── status
├── source
├── requested_by
├── payload
├── result
├── error_code
├── attempts
├── session_generation
├── created_at
├── updated_at
├── expires_at
├── sent_at
├── acknowledged_at
└── completed_at
```

---

# 4. مالکیت Command

Command همیشه متعلق به Device است.

```text
Command
   ↓
Device
```

اگر Command از UI مربوط به Vehicle ایجاد شود، Backend در لحظه ایجاد Command، Device فعال مربوط به Vehicle را Resolve می‌کند.

بعد از ایجاد:

```text
command.device_id
```

ثابت می‌ماند.

اگر بعداً Device خودرو عوض شود، Command به Device جدید منتقل نمی‌شود.

---

# 5. Command State Machine

چرخه اصلی:

```text
PENDING
   ↓
QUEUED
   ↓
SENDING
   ↓
SENT
   ↓
ACKNOWLEDGED
   ↓
COMPLETED
```

مسیرهای خطا:

```text
PENDING → CANCELLED

QUEUED → CANCELLED

QUEUED → EXPIRED

SENDING → FAILED

SENT → FAILED

SENT → QUEUED
```

و:

```text
ACKNOWLEDGED
      ↓
COMPLETED
```

یا در صورت عدم تکمیل:

```text
ACKNOWLEDGED
      ↓
FAILED
```

---

# 6. معنی Statusها

### PENDING

Backend Command را ایجاد کرده ولی Runtime هنوز آن را قبول نکرده است.

### QUEUED

`sana-gps` Command را برای اجرا پذیرفته و Command منتظر Session/Execution است.

### SENDING

Command توسط Worker به‌صورت Atomic Claim شده و اجرای آن در حال انجام است.

### SENT

Bytes با موفقیت به Transport تحویل داده شده‌اند.

این وضعیت به معنی اجرای موفق روی Device نیست.

### ACKNOWLEDGED

Device/Protocol پاسخ ACK معتبر داده است.

### COMPLETED

اجرای واقعی Command طبق قرارداد آن Command اثبات شده است.

### FAILED

اجرای Command شکست خورده است.

### CANCELLED

Command قبل از Execution لغو شده است.

### EXPIRED

مهلت اجرای Command تمام شده است.

---

# 7. ACK با Completion متفاوت است

این دو مفهوم یکی نیستند:

```text
ACK
→ Device دریافت Command را تأیید کرد.

COMPLETED
→ نتیجه اجرای Command مشخص و موفق است.
```

مثلاً:

```text
REBOOT
```

ممکن است ACK داشته باشد ولی اثبات اینکه Device واقعاً Reboot شده، از Telemetry/Response بعدی مشخص شود.

بنابراین:

```text
ACKNOWLEDGED ≠ COMPLETED
```

البته اگر Protocol فقط ACK داشته باشد و اطلاعات Completion ارائه نکند، بر اساس قرارداد Command می‌توان `ACKNOWLEDGED` را وضعیت نهایی موفق در نظر گرفت.

---

# 8. Command Type Registry

تعریف رفتار Commandها در Code انجام می‌شود.

Registry می‌تواند برای هر Command مشخص کند:

```text
side_effect
retry_policy
ack_required
completion_required
payload_schema
timeout
```

نمونه:

```text
REQUEST_POSITION
→ read-only
→ retryable

GET_STATUS
→ read-only
→ retryable

GET_CONFIGURATION
→ read-only
→ retryable

REBOOT
→ side-effect
→ no automatic retry by default

SET_OUTPUT
→ side-effect
→ no automatic retry by default
```

---

# 9. Commandهای اولیه

Command Typeهای اولیه:

```text
REQUEST_POSITION
GET_STATUS
GET_CONFIGURATION
REBOOT
SET_OUTPUT
```

این نام‌ها Domain-level هستند.

Protocol-specific encoding در `sana-gps` انجام می‌شود.

---

# 10. Payload

Payload آزاد و Arbitrary JSON نیست.

برای هر Command Schema مشخص وجود دارد.

### بدون Payload

```text
REQUEST_POSITION
GET_STATUS
GET_CONFIGURATION
REBOOT
```

مثلاً:

```json
{}
```

### SET_OUTPUT

```json
{
  "output": 1,
  "state": true
}
```

Backend مسئول Business Validation است.

`sana-gps` مسئول Technical/Protocol Validation است.

Raw Protocol Bytes هرگز نباید از Client وارد Payload شوند.

---

# 11. Payload و Result

### payload

Intent موردنظر است:

```text
چه کاری می‌خواهیم انجام شود؟
```

### result

نتیجه Normalize‌شده اجرای Command است:

```text
چه اتفاقی افتاد؟
```

Raw Protocol Response در صورت نیاز در `RawPacket` نگهداری می‌شود.

---

# 12. Permission

Authorization فقط در `sana-backend` انجام می‌شود.

جریان:

```text
User
 ↓
Authentication
 ↓
Device Access
 ↓
Command Permission
 ↓
Create Command
```

مثلاً:

```text
device.view
device.command
```

در MVP کافی هستند.

Commandهای حساس در آینده می‌توانند Permission اختصاصی داشته باشند.

---

# 13. sana-gps به Permission Business وابسته نیست

`sana-gps` نباید User Permission را محاسبه کند.

ولی به‌عنوان Second Line of Defense موارد زیر را بررسی می‌کند:

```text
Device Lifecycle
Session
Command Type
Payload
Protocol Capability
```

---

# 14. Lifecycle Gate

Device باید برای اجرای Command در وضعیت:

```text
ACTIVE
```

باشد.

در وضعیت:

```text
WAREHOUSE
SUSPENDED
REPAIR
RETURNED
RETIRED
```

Command نباید اجرا شود.

در این حالت Runtime می‌تواند Commandهای:

```text
PENDING
QUEUED
```

را طبق Policy به:

```text
CANCELLED
```

تبدیل کند.

این کار از اجرای Command قدیمی روی Device نامعتبر جلوگیری می‌کند.

---

# 15. Session Gate

Command فقط باید روی Session همان Device اجرا شود.

```text
command.device_id
==
session.device_id
```

باید برقرار باشد.

همچنین:

```text
command.session_generation
==
current_session.generation
```

باید برقرار باشد.

Session قدیمی نباید بتواند Command جدید را اجرا کند.

---

# 16. Session Generation

هر Session یک:

```text
generation
```

دارد.

وقتی Device دوباره Connect می‌شود:

```text
generation + 1
```

می‌شود.

مثلاً:

```text
Session 10
generation = 7
```

بعد reconnect:

```text
Session 11
generation = 8
```

Commandهای وابسته به Generation قدیمی نمی‌توانند روی Session جدید بدون Claim مجدد اجرا شوند.

---

# 17. Offline Device

Offline بودن Device به معنی Failure فوری Command نیست.

اگر Device Offline باشد:

```text
Command
→ QUEUED
```

باقی می‌ماند.

تا زمانی که:

```text
expires_at
```

نرسیده باشد، Scheduler می‌تواند پس از اتصال Device دوباره آن را اجرا کند.

بنابراین:

```text
Offline
≠
Failed
```

---

# 18. Command Expiration

هر Command دارای:

```text
expires_at
```

است.

اگر:

```text
now >= expires_at
```

باشد:

```text
PENDING / QUEUED
        ↓
EXPIRED
```

Command منقضی‌شده هرگز نباید ارسال شود.

---

# 19. Scheduler

Command Scheduler یک Loop مرکزی است.

Scheduler نباید برای هر Command یک Timer جداگانه ایجاد کند.

ساختار:

```text
PostgreSQL
    ↓
Scheduler
    ↓
Find Eligible Commands
    ↓
Atomic Claim
    ↓
Worker
```

---

# 20. PostgreSQL NOTIFY

Backend بعد از Commit Command می‌تواند:

```text
NOTIFY
```

ارسال کند.

اما:

> `NOTIFY` Source of Truth نیست.

NOTIFY فقط یک Signal سریع برای بیدار کردن Scheduler است.

اگر Notification از دست برود:

```text
Scheduler Reconciliation
```

دوباره PostgreSQL را بررسی می‌کند.

بنابراین:

```text
NOTIFY
≠ Queue
≠ Durable Message
```

---

# 21. Reconciliation

Scheduler باید به‌صورت دوره‌ای Commandهای واجد شرایط را دوباره از Database پیدا کند.

مثلاً:

```text
PENDING
QUEUED
Retryable
Expired
```

بنابراین اگر:

* NOTIFY از دست رفت
* sana-gps Restart شد
* Connection لحظه‌ای قطع شد

Command قابل بازیابی است.

---

# 22. Queueing

MVP از Queue جداگانه استفاده نمی‌کند.

یعنی:

```text
Kafka ❌
RabbitMQ ❌
Redis Queue ❌
Celery ❌
Disk Queue ❌
```

صف پایدار:

```text
gps.command
```

است.

در آینده اگر حجم نیاز داشته باشد:

```text
PostgreSQL
   ↓
Queue / Worker Layer
```

قابل اضافه شدن است.

Contract Command تغییر نمی‌کند.

---

# 23. Atomic Claim

Scheduler نباید Command را فقط در Memory Claim کند.

Claim باید در PostgreSQL به‌صورت Atomic باشد.

مفهوم:

```sql
UPDATE gps.command
SET
    status = 'SENDING',
    attempts = attempts + 1,
    session_generation = :generation
WHERE id = :command_id
  AND status = 'QUEUED'
  AND expires_at > CURRENT_TIMESTAMP;
```

اگر Update موفق باشد:

```text
Worker
→ Command را Claim کرده است.
```

اگر:

```text
0 rows updated
```

باشد:

```text
Command دیگر قابل Claim نیست.
```

این مکانیزم برای Multi-Instance شدن `sana-gps` ضروری است.

---

# 24. One In-Flight Command per Device

در MVP برای هر Device حداکثر یک Command در حال اجرای واقعی داریم.

مثلاً:

```text
Device 100
 └── SET_OUTPUT
```

تا زمانی که وضعیت آن مشخص نشده، Command بعدی اجرا نمی‌شود.

این قانون Matching ACK را بسیار ساده‌تر و امن‌تر می‌کند.

در آینده در صورت نیاز می‌توان Concurrency Policy پیشرفته‌تر اضافه کرد.

---

# 25. FIFO

در MVP Priority پیچیده نداریم.

Commandهای واجد شرایط برای یک Device بر اساس:

```text
created_at ASC
```

پردازش می‌شوند.

یعنی قدیمی‌ترین Command معتبر اول اجرا می‌شود.

Command منقضی‌شده از صف قابل اجرا حذف می‌شود.

---

# 26. Batch Size

Scheduler نباید تمام Commandهای Database را یک‌جا Load کند.

Batch محدود استفاده می‌شود.

مثلاً:

```text
LIMIT 50
```

مقدار اولیه قابل تنظیم است.

هدف:

* کنترل Memory
* کنترل DB Load
* جلوگیری از Burst
* امکان Scale

---

# 27. Retry

Retry بر اساس Command Type است.

### Query Command

مثل:

```text
REQUEST_POSITION
GET_STATUS
GET_CONFIGURATION
```

می‌تواند Retry شود.

### Side-effect Command

مثل:

```text
REBOOT
SET_OUTPUT
```

به‌صورت پیش‌فرض Auto Retry نمی‌شود.

دلیل:

اگر Bytes ارسال شده باشند ولی ACK نرسیده باشد، مشخص نیست Device Command را اجرا کرده یا نه.

Retry کورکورانه ممکن است Side Effect را دوباره اجرا کند.

---

# 28. Retry Backoff

Retry باید:

```text
bounded
```

باشد.

مثلاً:

```text
attempt 1
↓
short delay

attempt 2
↓
longer delay

attempt 3
↓
FAIL
```

Backoff و Jitter قابل تنظیم هستند.

Retry نامحدود ممنوع است.

---

# 29. Disconnect قبل از Send

اگر Session قبل از ارسال واقعی Command از بین برود:

```text
SENDING
   ↓
QUEUED
```

می‌تواند برگردد.

Command روی Session جدید دوباره Claim می‌شود.

---

# 30. Disconnect هنگام/بعد از Send

اگر Connection هنگام یا بعد از ارسال قطع شود، Delivery نامطمئن است.

یعنی:

```text
Command sent?
Device received?
Device executed?
```

ممکن است مشخص نباشد.

برای Query:

```text
Retry
```

می‌تواند مجاز باشد.

برای Side Effect:

```text
FAILED
```

به‌صورت محافظه‌کارانه ثبت می‌شود.

---

# 31. ACK Timeout

اگر ACK در زمان تعیین‌شده دریافت نشود:

### Query

```text
SENT
 ↓
ACK_TIMEOUT
 ↓
QUEUED
```

در صورت باقی بودن:

```text
expires_at
```

و Retry Policy.

### Side Effect

```text
SENT
 ↓
FAILED
error_code = ACK_TIMEOUT
```

---

# 32. Completion Timeout

اگر:

```text
ACKNOWLEDGED
```

شد ولی Completion مورد انتظار دریافت نشد:

```text
ACKNOWLEDGED
       ↓
COMPLETION_TIMEOUT
       ↓
FAILED
```

برای Side Effect نباید به‌صورت خودکار دوباره اجرا شود.

---

# 33. Crash بعد از Send

ممکن است Process بعد از:

```text
Transport.send()
```

و قبل از ثبت نتیجه Crash کند.

در این حالت:

```text
Delivery = UNKNOWN
```

است.

برای Side Effect:

```text
Automatic Retry ❌
```

برای Query طبق Retry Policy قابل بررسی است.

این یکی از دلایل اصلی محافظه‌کار بودن Command Runtime است.

---

# 34. Response Matching

اگر Protocol دارای:

```text
Command ID
Sequence
Correlation ID
```

باشد، برای Matching استفاده می‌شود.

اگر Protocol چنین قابلیتی نداشته باشد، قانون:

```text
One In-Flight Command per Device
```

Matching را ساده و قابل اعتماد می‌کند.

Telemetry معمولی نباید به‌صورت تصادفی ACK Command تلقی شود.

---

# 35. ACK و Telemetry مستقل

ممکن است Device بعد از Command هم:

```text
ACK
```

و هم:

```text
Telemetry
```

ارسال کند.

این دو Pipeline مستقل دارند:

```text
Command Response
→ Command Runtime

Telemetry
→ Telemetry Pipeline
```

Command مستقیماً CurrentState را تغییر نمی‌دهد.

اگر وضعیت واقعی Device تغییر کرده باشد، Telemetry/Response استانداردشده آن را مشخص می‌کند.

---

# 36. Command Encoder

مسیر:

```text
Domain Command
     ↓
Protocol Encoder
     ↓
Raw Bytes
```

Encoder مسئول:

* Protocol Encoding
* Validation فنی
* تولید Bytes

است.

Encoder نباید:

```text
Database Query
```

انجام دهد.

---

# 37. Session Manager

Session Manager مسئول پیدا کردن Session مناسب Device است.

```text
Command
   ↓
Session Manager
   ↓
Active Session
```

اگر Session وجود نداشته باشد:

```text
Command → QUEUED
```

می‌ماند.

---

# 38. Transport

Transport فقط مسئول Network است.

```text
Encoder
   ↓
Bytes
   ↓
Transport
   ↓
TCP / UDP
```

Transport نباید Business Logic Command را بداند.

---

# 39. Scheduler به Socket دست نمی‌زند

Scheduler فقط:

```text
Find
Claim
Schedule
```

می‌کند.

مسیر صحیح:

```text
Scheduler
 ↓
Worker
 ↓
Session Manager
 ↓
Encoder
 ↓
Transport
```

Scheduler مستقیماً با TCP Socket کار نمی‌کند.

---

# 40. Command Result

`result` باید Normalize‌شده و قابل استفاده توسط Backend باشد.

مثلاً:

```json
{
  "position": {
    "latitude": 35.7,
    "longitude": 51.4
  }
}
```

یا:

```json
{
  "status": "OK"
}
```

Raw Response در صورت نیاز در RawPacket قابل نگهداری است.

---

# 41. Error Codes

Error Codeهای استاندارد اولیه:

```text
DEVICE_OFFLINE
COMMAND_EXPIRED
COMMAND_CANCELLED
UNSUPPORTED_COMMAND
SESSION_UNAVAILABLE
SEND_FAILED
ACK_TIMEOUT
COMPLETION_TIMEOUT
DEVICE_REJECTED
PROTOCOL_ERROR
ENCODING_ERROR
LIFECYCLE_BLOCKED
SESSION_MISMATCH
SESSION_GENERATION_MISMATCH
```

---

# 42. Command Observability

`gps.command` خودش منبع Audit است.

اطلاعاتی مانند:

```text
status
source
requested_by
payload
result
error_code
attempts
session_generation
timestamps
```

برای Trace کافی است.

در MVP جدول جداگانه:

```text
command_attempt
command_state_history
```

نمی‌سازیم.

در آینده در صورت نیاز قابل اضافه شدن هستند.

---

# 43. Attempts

```text
attempts
```

تعداد تلاش‌های اجرای Command است.

`sent_at` زمان آخرین Send موفق را نگه می‌دارد.

اگر Attempt بدون Send واقعی شکست بخورد، بسته به تعریف دقیق Implementation باید شمارش آن با Policy نهایی هماهنگ شود؛ اصل این است که تعداد Execution Attempt قابل مشاهده باشد.

---

# 44. Traceability

برای Trace Command از این شناسه‌ها استفاده می‌شود:

```text
command_id
device_id
session_id
session_generation
```

`connection_id` Runtime/Log-level است و لزوماً در Database ذخیره نمی‌شود.

---

# 45. Logging

Transitionهای مهم باید Structured Log شوند:

```text
COMMAND_CREATED
COMMAND_QUEUED
COMMAND_CLAIMED
COMMAND_SENT
COMMAND_ACKNOWLEDGED
COMMAND_COMPLETED
COMMAND_FAILED
COMMAND_RETRY
COMMAND_EXPIRED
COMMAND_CANCELLED
```

نباید:

* Raw secrets
* Credential
* Token
* اطلاعات حساس غیرضروری

در Log ثبت شود.

---

# 46. Metrics

حداقل Metrics:

```text
commands_created
commands_queued
commands_sent
commands_acknowledged
commands_completed
commands_failed
commands_expired
commands_cancelled
commands_retried

command_ack_timeout
command_send_failure
command_encoding_failure
```

Latency:

```text
Create → Send
Send → ACK
ACK → Complete
Create → Complete
```

نیز باید قابل اندازه‌گیری باشد.

---

# 47. Scheduler Lifecycle

Scheduler باید:

```text
Startup
   ↓
Load Pending/Queued
   ↓
Reconcile
   ↓
Schedule
   ↓
Wait for NOTIFY / Poll
```

کار کند.

در Shutdown:

```text
Stop accepting new work
↓
Finish safe in-flight work
↓
Persist state
↓
Close
```

Commandهای ناتمام از PostgreSQL قابل بازیابی هستند.

---

# 48. Scheduler Reconciliation

در هر چرخه Scheduler باید بتواند:

```text
PENDING
QUEUED
Retryable
Expired
```

را بررسی کند.

بنابراین Restart باعث از بین رفتن Queue نمی‌شود.

---

# 49. Multi-Instance

معماری باید از ابتدا قابلیت:

```text
sana-gps #1
sana-gps #2
...
```

را داشته باشد.

هر Instance می‌تواند Scheduler داشته باشد.

Atomic Claim در PostgreSQL تضمین می‌کند که یک Command همزمان توسط دو Instance اجرا نشود.

---

# 50. Future Queue Layer

در صورت رشد سیستم:

```text
PostgreSQL
      ↓
Queue
      ↓
Workers
      ↓
Session Manager
```

قابل اضافه شدن است.

اما Domain Command و State Machine تغییر نمی‌کنند.

---

# 51. چیزهایی که در MVP نداریم

عمداً این موارد را اضافه نمی‌کنیم:

```text
Kafka
RabbitMQ
Redis Queue
Celery
Disk Queue
Complex Priority Queue
Command Attempt Table
Command State History Table
Distributed Lock Service
Per-device Timer
Per-command Timer
Complex Command Dependency Graph
```

هدف:

> Minimal but Reliable.

---

# 52. معماری نهایی

```text
                    sana-backend
                         │
                         │ Create Command
                         ▼
                  ┌──────────────┐
                  │ gps.command  │
                  └──────┬───────┘
                         │
                  NOTIFY / Poll
                         │
                         ▼
                ┌──────────────────┐
                │ Command Scheduler│
                └────────┬─────────┘
                         │
                    Atomic Claim
                         │
                         ▼
                  Command Worker
                         │
                         ▼
                  Session Manager
                         │
                         ▼
                  Protocol Encoder
                         │
                         ▼
                     Transport
                         │
                         ▼
                    GPS Device
                         │
                  ACK / Response
                         │
                         ▼
                  Command Runtime
                         │
                         ▼
                  gps.command
```

---

# 53. اصل نهایی Command Runtime

> **PostgreSQL صف پایدار و Source of Truth است؛ NOTIFY فقط Signal است؛ Scheduler مسئول پیدا کردن و Claim کردن Command است؛ Session Manager مسئول اتصال به Device است؛ Encoder مسئول تبدیل Command به Protocol Bytes است؛ Transport مسئول شبکه است؛ و نتیجه واقعی اجرای Command باید از ACK/Response/Telemetry معتبر مشخص شود.**

---

# 54. قواعد نهایی

1. `sana-backend` مالک Business Command است.
2. `sana-gps` مالک اجرای فنی Command است.
3. `gps.command` Source of Truth است.
4. Command همیشه Device-owned است.
5. Vehicle فقط در لحظه ایجاد Command برای Resolve کردن Device استفاده می‌شود.
6. Command بعد از ایجاد به Device دیگری منتقل نمی‌شود.
7. Permission فقط در Backend است.
8. Lifecycle و Session Safety در sana-gps نیز بررسی می‌شوند.
9. Device برای اجرای Command باید ACTIVE باشد.
10. Offline باعث Failure فوری Command نمی‌شود.
11. `expires_at` سقف عمر Command است.
12. Command منقضی‌شده ارسال نمی‌شود.
13. One In-Flight Command per Device در MVP برقرار است.
14. Commandهای یک Device به‌صورت FIFO اجرا می‌شوند.
15. Scheduler مرکزی است و Per-Command Timer نداریم.
16. NOTIFY فقط Signal است.
17. Reconciliation از Database Queue را قابل بازیابی می‌کند.
18. Claim باید Atomic باشد.
19. Multi-Instance با PostgreSQL قابل پشتیبانی است.
20. Query Commandها Retryable هستند.
21. Side-effect Commandها Auto Retry ندارند مگر Policy صریح.
22. ACK و Completion دو مفهوم مستقل‌اند.
23. Crash بعد از Send ممکن است Delivery را Unknown کند.
24. Side-effect در وضعیت Unknown خودکار Retry نمی‌شود.
25. Command مستقیماً CurrentState را تغییر نمی‌دهد.
26. ACK و Telemetry Pipeline مستقل دارند.
27. Encoder نباید Database Query انجام دهد.
28. Scheduler نباید مستقیماً Socket را مدیریت کند.
29. Raw Protocol Bytes از Client پذیرفته نمی‌شوند.
30. Error Codeها استاندارد و قابل Trace هستند.
31. `gps.command` منبع Audit اصلی Command است.
32. در MVP Command Attempt History جداگانه نداریم.
33. Retry bounded و دارای Backoff/Jitter است.
34. PostgreSQL Queue در MVP کافی است.
35. Kafka/RabbitMQ/Redis/Celery/Disk Queue در MVP نداریم.
36. معماری برای اضافه کردن Queue در آینده باز گذاشته شده است.

---

# 55. وضعیت Stage 22

```text
[✓] Command Ownership
[✓] Command State Machine
[✓] Command Types
[✓] Payload Contract
[✓] Permission Boundary
[✓] Lifecycle Gate
[✓] Session Generation
[✓] Offline Handling
[✓] Expiration
[✓] Retry Policy
[✓] ACK / Completion
[✓] Session Disconnect
[✓] Crash / Unknown Delivery
[✓] Command Encoding
[✓] Response Matching
[✓] Observability
[✓] Audit
[✓] Scheduler
[✓] PostgreSQL Queue
[✓] NOTIFY
[✓] Reconciliation
[✓] Atomic Claim
[✓] Multi-Instance Safety
[✓] FIFO
[✓] One In-Flight per Device
[✓] Future Queue Architecture
```

# Stage 22 — CLOSED

**Command Runtime از نظر معماری نهایی و آماده ورود به Implementation است.**


============================================================================
============================================================================

# SANA GPS

# Stage 23 تا Stage 26

# نهایی‌سازی طراحی، MVP Scope و Architecture Freeze

---

# وضعیت کلی

```text
Stage 23 — Telemetry Processing Pipeline     CLOSED
Stage 24 — Observability / Health             CLOSED
Stage 25 — Security / Authentication         CLOSED
Stage 26 — MVP Scope / Architecture Freeze  CLOSED
```

از پایان این سند:

> **فاز طراحی معماری SANA GPS بسته شده و Implementation می‌تواند شروع شود.**

---

# ============================================================

# Stage 23 — TELEMETRY PROCESSING PIPELINE

# ============================================================

## 1. هدف

Telemetry Pipeline مسیر کامل تبدیل Packet خام GPS به داده معتبر و قابل ذخیره SANA است.

مسیر نهایی:

```text
TCP / UDP
   ↓
Connection
   ↓
Session
   ↓
Framing
   ↓
Device Identification
   ↓
Device Lookup
   ↓
Protocol / Codec Resolution
   ↓
Decode
   ↓
Normalize
   ↓
Validate
   ↓
Deduplicate
   ↓
Ordering
   ↓
Sampling
   ↓
BEGIN TRANSACTION
   ├── LocationHistory
   ├── CurrentState
   ├── Event
   └── Trip
   ↓
COMMIT
   ↓
ACK
   ↓
NOTIFY
   ↓
Post-Commit Consumers
```

---

# 2. مرحله Connection

Transport فقط وظیفه Network دارد.

TCP:

```text
Byte Stream
```

UDP:

```text
Datagram
```

Transport نباید:

* Device را شناسایی کند.
* Protocol را Decode کند.
* Business Logic اجرا کند.
* Database را مستقیماً تغییر دهد.

---

# 3. Session

بعد از شناسایی معتبر Device:

```text
Connection
   ↓
Session
```

Session شامل:

```text
session_id
device_id
connection_id
protocol
generation
state
```

است.

هر Device حداکثر یک Session فعال دارد.

Session قدیمی با Session Generation فنس می‌شود.

---

# 4. Framing

Framer وظیفه تشخیص Message/Frame کامل را دارد.

برای TCP:

```text
partial frame
→ buffer
→ complete frame
```

و:

```text
multiple frames
→ split
```

برای UDP:

```text
datagram
→ one/multiple protocol messages
```

Framer نباید Semantic Telemetry را تفسیر کند.

---

# 5. Device Identification

قبل از Decode کامل:

```text
Identity
   ↓
Device Lookup
```

انجام می‌شود.

در MVP:

```text
IMEI
```

شناسه اصلی Gateway است.

Device ناشناس:

```text
No Session
No Telemetry
No ACK success
No Raw persistence by default
```

---

# 6. Protocol / Codec Resolution

مسیر:

```text
Device
 ↓
DeviceModel
 ↓
Protocol
 ↓
Codec
 ↓
Profile
```

Protocol و Codec در Code پیاده‌سازی می‌شوند.

Database فقط Configuration/Reference لازم را نگه می‌دارد.

Profile:

```text
Mapping / Normalization
```

را مشخص می‌کند.

Profile مسئول Framing نیست.

---

# 7. Decode

Decoder:

```text
Raw Frame
   ↓
Protocol Message
```

تبدیل می‌کند.

Decoder مسئول:

* Parse
* Structural Validation
* استخراج Protocol Fields
* استخراج ACK/Response

است.

Decoder نباید:

```text
Database Query
Business Logic
Vehicle Logic
Permission
Event Rule
```

انجام دهد.

---

# 8. Normalize

Normalizer:

```text
Protocol Message
      ↓
NormalizedTelemetry
```

تبدیل می‌کند.

خروجی استاندارد:

```text
device_id
device_time
server_received_at

latitude
longitude
gps_valid
accuracy
altitude
satellites

speed
heading
motion
ignition

battery_voltage
external_voltage
gsm_signal

odometer
engine_hours
fuel_level

attributes
```

تمام واحدها به واحد استاندارد SANA تبدیل می‌شوند.

---

# 9. Validate

Validation دو سطح دارد.

### Field Validation

اگر یک Field خراب باشد:

```text
Invalid Field
   ↓
NULL
```

مثلاً:

```text
invalid altitude
```

لزومی ندارد کل Telemetry حذف شود.

### Record Validation

اگر ساختار Record قابل استفاده نباشد:

```text
Invalid Record
```

می‌شود.

### Packet Validation

اگر Packet ساختاری/Protocolی خراب باشد:

```text
Packet Rejected
```

می‌شود.

---

# 10. Deduplication

Dedup قبل از Business Processing انجام می‌شود.

```text
Decode
 ↓
Normalize
 ↓
Validate
 ↓
Dedup
 ↓
Ordering
```

Exact duplicate:

```text
No LocationHistory duplicate
No Event duplicate
No Trip side effect
No CurrentState side effect
```

Fingerprint اصلی Raw Packet:

```text
SHA-256
```

است.

Dedup دائمی و بی‌نهایت نیست.

---

# 11. Ordering

ترتیب تاریخی Telemetry:

```text
device_time
```

است.

ترتیب رسیدن:

```text
server_received_at
```

است.

این دو هرگز یکی فرض نمی‌شوند.

Packet قدیمی:

```text
CurrentState → No Rollback
```

ولی:

```text
LocationHistory
```

ممکن است همچنان آن را بپذیرد.

---

# 12. Sampling

Sampling فقط برای:

```text
LocationHistory
```

است.

Sampling نباید باعث از بین رفتن:

```text
Event
Trip Boundary
CurrentState
Important State Changes
```

شود.

نمونه معیارها:

```text
minimum distance
maximum interval
speed change
heading change
state boundary
```

Location History نباید تبدیل به Packet History شود.

---

# 13. Transaction Boundary

بعد از اینکه Decode/Normalize/Validate/Dedup/Ordering/Sampling انجام شد:

```text
BEGIN
```

و داده‌های وابسته در یک Transaction پردازش می‌شوند:

```text
LocationHistory
CurrentState
Event
Trip
```

سپس:

```text
COMMIT
```

---

# 14. چرا Transaction بعد از Processing است؟

کارهای سنگین و غیر DB:

```text
Decode
Normalize
Validation
Dedup
Ordering
Sampling
```

نباید Connection Database را بی‌جهت اشغال کنند.

بنابراین:

```text
Processing
   ↓
Short DB Transaction
```

اصل است.

---

# 15. Transaction Failure

اگر Transaction شکست بخورد:

```text
LocationHistory
CurrentState
Event
Trip
```

نباید Partial Commit شوند.

نتیجه:

```text
ROLLBACK
```

و Packet در صورت خطای قابل Retry دوباره Processing می‌شود.

---

# 16. Retry Classification

### Transient Error

مانند:

```text
temporary DB failure
connection reset
deadlock
temporary timeout
```

→ Retry محدود.

### Permanent Error

مانند:

```text
invalid data
unsupported protocol
invalid profile
constraint violation ناشی از داده
```

→ Retry نامحدود ممنوع.

---

# 17. ACK

برای Protocolهایی مثل Teltonika:

> ACK موفق فقط بعد از Commit موفق Database ارسال می‌شود.

```text
Telemetry
 ↓
DB Transaction
 ↓
COMMIT
 ↓
ACK
```

اگر DB Commit نشود:

```text
Successful ACK ❌
```

Duplicateی که قبلاً Commit شده:

```text
No side effect
ACK allowed
```

---

# 18. Post-Commit Consumers

بعد از Commit:

```text
NOTIFY
WebSocket
Geofence
Alert
Notification
```

اجرا می‌شوند.

این Consumerها نباید داخل Transaction اصلی قرار بگیرند.

اصل:

```text
Commit
 ↓
Consumers
```

---

# 19. NOTIFY

PostgreSQL NOTIFY:

```text
Signal
```

است.

نه:

```text
Queue
Source of Truth
Durable Event Stream
WebSocket Message
```

اگر NOTIFY از دست برود:

```text
Reconciliation
```

باید وضعیت را از Database پیدا کند.

---

# 20. Batch

اگر Packet چند Telemetry Record داشته باشد:

```text
Packet
 ├── Record 1
 ├── Record 2
 ├── Record 3
 └── Record N
```

تمام Recordها:

```text
Decode
Normalize
Validate
Dedup
Ordering
```

می‌شوند.

در MVP:

```text
One valid batch
→ One PostgreSQL Transaction
```

است.

---

# 21. Huge Packet

Packet بزرگ‌تر از:

```text
MAX_FRAME_SIZE
```

پذیرفته نمی‌شود.

MVP آن را:

```text
Reject
```

می‌کند.

Silent Chunking نداریم.

---

# 22. Event Processing

Event Engine بعد از Dedup و Ordering قرار دارد.

```text
Telemetry
 ↓
Dedup
 ↓
Ordering
 ↓
Event
```

Eventهای Telemetry-based با:

```text
device_time
```

کار می‌کنند.

Eventهای Server-side مثل:

```text
DEVICE_OFFLINE
```

با Server Time کار می‌کنند.

Event Watermark مستقل از CurrentState است.

---

# 23. Trip Processing

Trip نیز بعد از:

```text
LocationHistory / Movement Processing
```

محاسبه می‌شود.

Trip:

```text
Device-owned
```

است.

Vehicle فقط از:

```text
DeviceVehicleAssignment
```

به Trip Context اضافه می‌شود.

---

# 24. CurrentState

CurrentState فقط Snapshot جدیدتر را می‌پذیرد:

```text
incoming.device_time
>
current.device_time
```

و Update آن:

```text
Atomic Conditional Update
```

است.

Packet قدیمی نمی‌تواند Snapshot را Rollback کند.

---

# 25. Last Seen

`last_seen` با:

```text
server_received_at
```

کار می‌کند.

بنابراین:

```text
Telemetry Ordering
≠
Communication Activity
```

است.

Heartbeat معتبر نیز می‌تواند Communication Activity را به‌روز کند، بدون اینکه Telemetry CurrentState را تغییر دهد.

---

# 26. GPS No-Fix

اگر:

```text
gps_valid = false
```

و Packet جدید باشد:

```text
Current Position
→ NULL
```

اما:

```text
Last Valid Position
→ حفظ می‌شود
```

GPS No-Fix برابر Offline نیست.

---

# 27. Pipeline Error Boundary

هر مرحله باید Error مشخص داشته باشد.

نمونه:

```text
UNKNOWN_DEVICE
UNKNOWN_PROTOCOL
UNKNOWN_CODEC
PROFILE_NOT_FOUND
PROFILE_INCOMPATIBLE

FRAME_ERROR
DECODE_ERROR
NORMALIZATION_ERROR
VALIDATION_ERROR
DUPLICATE_PACKET
ORDERING_REJECTED

DB_TRANSIENT_ERROR
DB_PERMANENT_ERROR
TRANSACTION_FAILED
```

خطا نباید باعث Crash کردن کل GPS Runtime شود.

---

# 28. Pipeline نهایی

```text
                 TCP / UDP
                     │
                     ▼
                Connection
                     │
                     ▼
                   Session
                     │
                     ▼
                  Framing
                     │
                     ▼
             Device Identification
                     │
                     ▼
               Device Lookup
                     │
                     ▼
            Protocol / Codec
                     │
                     ▼
                   Decode
                     │
                     ▼
                 Normalize
                     │
                     ▼
                 Validate
                     │
                     ▼
                Deduplicate
                     │
                     ▼
                  Ordering
                     │
                     ▼
                  Sampling
                     │
                     ▼
              ┌──────────────┐
              │ DB Transaction│
              └──────┬───────┘
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
 LocationHistory CurrentState    Event
                     │
                     ▼
                    Trip
                     │
                     ▼
                   COMMIT
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
        ACK       NOTIFY     Consumers
```

---

# ============================================================

# Stage 24 — OBSERVABILITY / LOGGING / METRICS / HEALTH

# ============================================================

## 29. اصل

GPS Runtime بدون Observability قابل Production نیست.

اما Observability نباید تبدیل به سیستم پیچیده جداگانه شود.

MVP:

```text
Structured Logs
Metrics
Health
Readiness
```

کافی است.

---

# 30. Structured Logging

Logها باید Machine-readable باشند.

حداقل Context:

```text
timestamp
level
service
event
device_id
session_id
protocol
codec
command_id
packet_fingerprint
error_code
```

هرکدام که مرتبط باشند.

---

# 31. Log Level

سطوح:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

### DEBUG

جزئیات Development/Protocol Debug.

### INFO

رویدادهای عادی مهم:

```text
startup
listener started
session created
session closed
command sent
```

### WARNING

شرایط غیرعادی ولی قابل ادامه:

```text
duplicate
old packet
retry
temporary DB failure
unknown optional field
```

### ERROR

Processing/operation failure.

### CRITICAL

Failureی که Service را نمی‌تواند به‌صورت صحیح ادامه دهد.

---

# 32. Raw Packet Logging

Raw Packet نباید در Log عادی Dump شود.

Raw Data فقط در:

```text
gps.raw_packet
```

و با Retention مشخص نگهداری می‌شود.

در Log:

```text
packet_id
fingerprint
device_id
protocol
```

کافی است.

---

# 33. Metrics

### Transport

```text
tcp_connections
udp_datagrams
connection_errors
bytes_received
bytes_sent
```

### Session

```text
sessions_active
sessions_created
sessions_closed
session_replacements
session_fenced
```

### Packet

```text
packets_received
packets_decoded
packets_rejected
packets_duplicate
packets_out_of_order
```

### Telemetry

```text
telemetry_records_received
telemetry_records_valid
telemetry_records_invalid
```

### Database

```text
db_transactions
db_transaction_success
db_transaction_failure
db_retry
db_latency
db_pool_in_use
db_pool_available
```

### ACK

```text
ack_sent
ack_suppressed
ack_failure
ack_latency
```

### Command

تمام Metrics تعریف‌شده Stage 22.

### Event/Trip

```text
events_created
events_closed
trips_started
trips_completed
```

---

# 34. Queue/Backpressure Metrics

در MVP منظور از Processing Queue فقط Queue محدود (bounded) و in-process داخل `sana-gps` است؛ این مفهوم به معنی Kafka، RabbitMQ، Redis، Celery یا Message Broker خارجی نیست.

```text
processing_queue_size
processing_queue_max
processing_queue_rejected
tcp_backpressure
udp_dropped
```

این Queue فقط برای کنترل backpressure و جداسازی کوتاه‌مدت مراحل پردازش استفاده می‌شود و Source of Truth محسوب نمی‌شود.

باید قابل مشاهده باشد.

# 35. Health

سه مفهوم:

```text
Liveness
Readiness
Health
```

### Liveness

آیا Process زنده است؟

### Readiness

آیا Service آماده دریافت Traffic است؟

### Health

آیا وابستگی‌های اصلی سالم هستند؟

---

# 36. Readiness

sana-gps فقط زمانی Ready است که:

```text
Configuration Loaded
DB Connected
Required Schema Available
Protocol Registry Ready
Session Manager Ready
Processing Pipeline Ready
Required Listeners Bound
```

باشد.

اگر DB قطع شود:

```text
Readiness
→ NOT READY
```

می‌تواند شود.

---

# 37. Liveness

DB Down نباید لزوماً باعث شود Process فوراً Crash کند.

Process می‌تواند:

```text
Alive
Not Ready
```

باشد و Recovery را انجام دهد.

---

# 38. Health Checks

حداقل:

```text
Database
PostgreSQL Pool
Listeners
Protocol Registry
Processing Queue
```

بررسی شوند.

---

# 39. Alerting Thresholds

در MVP Alerting خارجی پیچیده نمی‌سازیم.

ولی Metrics باید امکان تشخیص:

```text
DB failure spike
packet rejection spike
queue saturation
UDP drops
ACK failure spike
session explosion
memory pressure
```

را فراهم کنند.

---

# 40. Correlation

برای Trace کردن یک جریان:

```text
device_id
session_id
packet_id/fingerprint
command_id
```

استفاده می‌شود.

این شناسه‌ها باید در Logها در صورت وجود حفظ شوند.

---

# 41. No Sensitive Logging

در Log نباید:

```text
password
token
secret
API key
private credential
```

ثبت شود.

Payload Command نیز فقط در صورت امن و لازم بودن Log می‌شود؛ Source of Truth آن Database است.

---

# ============================================================

# Stage 25 — SECURITY / AUTHENTICATION

# ============================================================

# 42. Security Boundary

امنیت در دو لایه است:

```text
sana-backend
→ Business Authorization

sana-gps
→ Device/Protocol Technical Security
```

---

# 43. Device Identity

در Gateway:

```text
IMEI
```

شناسه اصلی Device است.

ولی IMEI به‌تنهایی Security کامل نیست.

Device باید:

```text
Registered
Allowed
Lifecycle = ACTIVE
```

باشد.

---

# 44. Unknown Device

Unknown Device:

```text
No Session
No Telemetry
No ACK success
No Command
No Raw persistence by default
```

و باید سریع Reject شود.

---

# 45. Lifecycle Security

برای Runtime:

```text
ACTIVE
```

شرط اصلی پذیرش Telemetry/Command است.

این وضعیت‌ها Block هستند:

```text
WAREHOUSE
SUSPENDED
REPAIR
RETURNED
RETIRED
```

Session قبلی نیز باید Fence شود.

---

# 46. Session Security

Session باید به:

```text
device_id
generation
protocol
```

متصل باشد.

هیچ Session نباید بتواند برای Device دیگر کار کند.

---

# 47. Old Session Protection

وقتی Session جدید معتبر ایجاد شد:

```text
generation++
```

و Session قبلی:

```text
FENCED
```

می‌شود.

Packet/Command/Heartbeat Session قدیمی نباید Side Effect ایجاد کند.

---

# 48. Protocol Security

Protocol Decoder نباید اعتماد کند که:

```text
port = protocol
```

است.

Port فقط Routing Hint است.

Protocol باید از:

```text
Device Configuration
Protocol Detection
Packet Structure
```

تعیین شود.

---

# 49. Input Validation

همه ورودی‌های Device:

```text
Untrusted Input
```

هستند.

بنابراین:

* Length محدود
* Frame محدود
* Field Validation
* Integer Range
* Decimal Range
* String Length
* JSON/Attribute محدود
* Payload محدود

باید اعمال شود.

---

# 50. Resource Protection

برای جلوگیری از Abuse:

```text
MAX_FRAME_SIZE
MAX_BUFFER_SIZE
MAX_PROCESSING_QUEUE
MAX_ATTRIBUTES_SIZE
MAX_COMMAND_PAYLOAD
MAX_BATCH_SIZE
```

تعریف می‌شوند.

MVP Rate Limit پیچیده روی تمام Protocolها ندارد، ولی Connection/Resource Limits الزامی هستند.

---

# 51. Database Security

Runtime Roleها:

```text
sana_gps
sana_backend
```

مالک Schema نیستند.

DDL ندارند.

`sana-gps` به Business Data دسترسی کامل ندارد.

PostgreSQL لایه دوم Security است.

---

# 52. Backend Authorization

کاربر:

```text
Authentication
 ↓
Device Permission
 ↓
Command Permission
 ↓
Create Command
```

می‌کند.

sana-gps نباید Permission User را دوباره پیاده‌سازی کند.

---

# 53. Command Security

Client فقط:

```text
Domain Command
```

می‌فرستد.

Raw Protocol Bytes ممنوع است.

Backend:

```text
Validate Payload
Authorize
Create Command
```

و sana-gps:

```text
Validate Technical Capability
Encode
Execute
```

می‌کند.

---

# 54. Secrets

Secrets از:

```text
Environment
Secret Management
```

می‌آیند.

در:

```text
Git
Logs
Source Code
Database Payload
```

قرار نمی‌گیرند مگر اینکه صراحتاً بخشی از یک Credential Configuration امن باشند.

---

# 55. Failure Mode

در صورت DB Failure:

```text
Authentication Fail-Open ❌
```

نباید اتفاق بیفتد.

اگر وضعیت Device قابل اطمینان نیست:

```text
Reject / Delay
```

امن‌تر از پذیرش کورکورانه است.

---

# 56. Security Principle

اصل:

> **Authentication/Authorization در Backend و Device/Protocol Validation در GPS Runtime است؛ هیچ‌کدام جای دیگری را نمی‌گیرد.**

---

# ============================================================

# Stage 26 — MVP SCOPE + ARCHITECTURE FREEZE

# ============================================================

# 57. هدف MVP

MVP باید بتواند یک GPS واقعی را:

```text
Connect
Identify
Decode
Normalize
Store
Track
```

کند.

بدون اینکه از همان ابتدا تمام قابلیت‌های Fleet Management را پیاده کنیم.

---

# 58. اولین Vertical Slice

اولین Slice:

```text
Teltonika Device
       ↓
TCP
       ↓
Session
       ↓
IMEI
       ↓
Device Lookup
       ↓
Codec 8 Framing
       ↓
Codec 8 Decode
       ↓
Normalize
       ↓
Validate
       ↓
Dedup
       ↓
Ordering
       ↓
PostgreSQL
       ↓
CurrentState
       ↓
LocationHistory
       ↓
Event
       ↓
ACK
```

این Slice باید با Device واقعی تست شود.

---

# 59. MVP Protocol

برای شروع:

```text
Teltonika TCP
Codec 8
```

پیاده‌سازی می‌شود.

GT06 و سایر Protocolها بعد از تثبیت Pipeline اضافه می‌شوند.

---

# 60. MVP Data

در MVP:

```text
Location
Speed
Heading
Altitude
Satellites
Ignition
Motion
Battery Voltage
External Voltage
GSM Signal
Odometer
Engine Hours
Fuel Level
```

طبق قابلیت Device/Protocol ذخیره می‌شوند.

---

# 61. MVP Historical Data

```text
LocationHistory
Event
```

فعال هستند.

Trip نیز طبق طراحی نهایی در MVP قرار دارد، ولی بعد از پایدار شدن Ingestion/History فعال می‌شود.

---

# 62. MVP CurrentState

از همان اولین Vertical Slice:

```text
CurrentState
```

باید ساخته شود.

هدف:

```text
Live Device State
```

---

# 63. MVP WebSocket

بعد از پایدار شدن Ingestion:

```text
CurrentState
 ↓
PostgreSQL NOTIFY
 ↓
sana-backend
 ↓
WebSocket
 ↓
sana-panel
```

پیاده‌سازی می‌شود.

`sana-gps` مستقیماً Browser WebSocket ندارد.

---

# 64. MVP Permission

WebSocket و REST باید Permission را Server-side اعمال کنند.

Device غیرمجاز نباید داده دریافت کند.

---

# 65. MVP Geofence

Geofence از نظر معماری طراحی شده، اما در اولین Vertical Slice اجرا نمی‌شود.

ترتیب Implementation:

```text
Ingestion
 ↓
CurrentState
 ↓
LocationHistory
 ↓
Event
 ↓
WebSocket
 ↓
Trip
 ↓
Geofence
```

---

# 66. MVP Alert

Alert Engine بعد از Event پایدار می‌شود.

در اولین Slice لازم نیست.

---

# 67. MVP Command

Command Runtime طراحی شده و در MVP معماری آن آماده است.

اما Implementation Command بعد از پایدار شدن:

```text
Session
Transport
Protocol Encoder
```

انجام می‌شود.

---

# 68. MVPهایی که عمداً نداریم

```text
Kafka
RabbitMQ
Redis
Celery
PgBouncer
Distributed Lock Service
Complex Queue
AI
Machine Learning
Traffic Analysis
ETA
Map Matching
Behavior Scoring
Advanced Fuel Analytics
Historical Full Replay
Automatic Historical Recalculation
```

---

# 69. Repository Structure

ساختار نهایی اولیه:

```text
SANA/
├── sana-backend/
├── sana-panel/
├── sana-gps/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   │
│   │   ├── transport/
│   │   ├── session/
│   │   ├── protocols/
│   │   ├── types/
│   │   ├── processing/
│   │   ├── repositories/
│   │   └── database/
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
│
├── telemetry.md
└── README.MD
```

از ایجاد Layer/Folder غیرضروری جلوگیری می‌شود.

---

# 70. Implementation Order

ترتیب رسمی کدنویسی:

```text
1. sana-gps Bootstrap
2. Config
3. PostgreSQL Pool
4. Database Schema / Migration Integration
5. Repository Layer
6. Transport TCP
7. Session Manager
8. Teltonika Framing
9. IMEI Identification
10. Device Lookup
11. Codec 8 Decoder
12. Normalizer
13. Validation
14. Deduplication
15. Ordering
16. LocationHistory
17. CurrentState
18. Event
19. ACK
20. Real Device Test
```

بعد:

```text
21. WebSocket
22. Live Map
23. Trip
24. Command Runtime
25. Geofence
26. Alert
```

---

# 71. Definition of Done — اولین Vertical Slice

اولین Slice زمانی Complete است که:

```text
[✓] Device واقعی وصل شود
[✓] IMEI شناسایی شود
[✓] Session ایجاد شود
[✓] Teltonika Frame درست Parse شود
[✓] Codec 8 Decode شود
[✓] Telemetry Normalize شود
[✓] Validation انجام شود
[✓] Duplicate کنترل شود
[✓] Out-of-order کنترل شود
[✓] LocationHistory ذخیره شود
[✓] CurrentState Update شود
[✓] Event ایجاد شود
[✓] ACK بعد از Commit ارسال شود
[✓] DB Failure باعث ACK موفق نشود
[✓] Duplicate باعث Side Effect دوباره نشود
[✓] Old Packet CurrentState را Rollback نکند
```

---

# 72. Definition of Done — Live System

بعد از Vertical Slice:

```text
[✓] چند Device همزمان
[✓] CurrentState
[✓] WebSocket
[✓] Permission
[✓] Live Map
[✓] Connection State
[✓] Offline
[✓] GPS No-Fix
[✓] Location History
[✓] Trip
```

تست می‌شوند.

---

# 73. Architecture Freeze

از این مرحله به بعد تصمیمات زیر Frozen هستند:

```text
Service Boundary
Database Boundary
PostgreSQL
gps Schema
CurrentState
LocationHistory
Event
Trip
DeviceVehicleAssignment
Device Lifecycle
Session
Protocol Architecture
Telemetry Pipeline
Command Runtime
WebSocket
Permission Boundary
PostgreSQL Roles
Connection Pooling
ACK Policy
Deduplication
Ordering
Sampling
```

تغییر این موارد فقط در صورت مشاهده مشکل واقعی در Implementation یا تست واقعی انجام می‌شود.

---

# 74. چیزهایی که دیگر نباید قبل از Coding دوباره طراحی شوند

تا زمانی که Implementation مشکل واقعی نشان نداده:

```text
❌ تغییر Database به NoSQL
❌ اضافه کردن Kafka
❌ اضافه کردن Redis
❌ اضافه کردن RabbitMQ
❌ تبدیل sana-gps به Django Service
❌ انتقال WebSocket به sana-gps
❌ انتقال Permission به sana-gps
❌ تغییر Device Ownership
❌ تبدیل CurrentState به History
❌ یکی کردن Event و Alert
❌ یکی کردن Alarm و Event
❌ یکی کردن Vehicle و Device History
```

---

# 75. اصل نهایی معماری SANA GPS

> **Minimal but Powerful**

یعنی:

```text
Simple Runtime
+
Strong Database Guarantees
+
Clear Ownership
+
Deterministic Processing
+
Safe Concurrency
+
Recoverable State
+
Real Device Testing
```

نه:

```text
Maximum Number of Services
```

---

# 76. معماری نهایی

```text
                       GPS DEVICES
                            │
                     TCP / UDP
                            │
                            ▼
                       sana-gps
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
          Session        Decoder       Processing
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                  Normalized Telemetry
                            │
                 ┌──────────┼──────────┐
                 │          │          │
                 ▼          ▼          ▼
          LocationHistory CurrentState Event
                 │          │          │
                 └──────────┼──────────┘
                            ▼
                           Trip

                            │
                            ▼
                        PostgreSQL
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
         sana-backend    WebSocket      Command
             │              │              │
             ▼              ▼              ▼
          REST API       Live Map       Device
```

---

# 77. وضعیت نهایی طراحی

```text
Stage 1   Architecture Foundation       CLOSED
Stage 2   Normalized Telemetry          CLOSED
Stage 3   PostgreSQL / Permissions      CLOSED
Stage 4   Protocol Architecture         CLOSED
Stage 5   Location History              CLOSED
Stage 6   CurrentState                  CLOSED
Stage 7   Event                         CLOSED
Stage 8   Batch / Dedup / Replay        CLOSED
Stage 9   Trip                          CLOSED
Stage 10  Device Assignment             CLOSED
Stage 11  Device Lifecycle              CLOSED
Stage 12  Geofence                      CLOSED
Stage 13  Alert                         CLOSED
Stage 14  Failure / Backpressure        CLOSED
Stage 15  Configuration                 CLOSED
Stage 16  Transport                     CLOSED
Stage 17  Concurrency                   CLOSED
Stage 18  WebSocket / Live Map          CLOSED
Stage 19  Command Runtime               CLOSED
Stage 20  Telemetry Pipeline            CLOSED
Stage 21  Observability                 CLOSED
Stage 22  Security                      CLOSED
Stage 23  MVP Scope / Freeze             CLOSED
```

شماره‌گذاری فوق صرفاً نمای کلی وضعیت فازهاست؛ در اسناد اجرایی، Stageهای اخیر با شماره‌های 23 تا 26 ثبت شده‌اند.

---

# 78. FINAL ARCHITECTURE FREEZE

در این نقطه:

```text
ARCHITECTURE = FROZEN
```

و:

```text
DESIGN PHASE = COMPLETE
```

است.

از اینجا به بعد:

```text
Design
   ↓
Implementation
   ↓
Real Device Test
   ↓
Bug / Reality Feedback
   ↓
Controlled Revision
```

خواهد بود.

تغییر معماری فقط بر اساس مشکل واقعی و مستند انجام می‌شود، نه بر اساس حدس یا پیچیده‌تر کردن سیستم.

---

# 79. اولین کار بعد از Freeze

Implementation با Repository واقعی SANA شروع می‌شود.

ابتدا وضعیت فعلی GitHub و Working Tree بررسی می‌شود، سپس:

```text
sana-gps/
```

ایجاد می‌شود.

بعد اولین Vertical Slice:

```text
Teltonika TCP
    ↓
Session
    ↓
IMEI
    ↓
Codec 8
    ↓
Normalize
    ↓
Validate
    ↓
Dedup
    ↓
Ordering
    ↓
PostgreSQL
    ↓
CurrentState
    ↓
LocationHistory
    ↓
Event
    ↓
ACK
```

پیاده‌سازی و با **دستگاه واقعی** تست خواهد شد.

---

# FINAL STATUS

```text
┌────────────────────────────────────────────┐
│                                            │
│       SANA GPS DESIGN PHASE COMPLETE      │
│                                            │
│              ARCHITECTURE FROZEN          │
│                                            │
│          READY FOR IMPLEMENTATION          │
│                                            │
└────────────────────────────────────────────┘
```

**فاز طراحی SANA GPS بسته شد.**

**مرحله بعد: شروع Implementation واقعی `sana-gps`.**


============================================================================
============================================================================



### طراحی شده، Implementation باقی مانده

* Protocol Decoder implementation
* Protocol Normalizer implementation
* Processing Pipeline implementation
* PostgreSQL Repository implementation
* Integration Tests با Packetهای واقعی
