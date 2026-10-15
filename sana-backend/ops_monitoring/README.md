# مانیتورینگ عملیاتی GPS

این پوشه اپ مستقل بک‌اند برای ابزارهای مانیتورینگ مدیر کل سانا است تا با اپ‌های دامنه‌ای مثل `accounts` و `fleet` قاطی نشود.

## مسیرها

- `GET /api/gps-monitor/logs/service/`: جریان زنده `journalctl -u sana-gps.service`
- `GET /api/gps-monitor/logs/network/`: جریان زنده `tcpdump` محدود به TCP/9000 و UDP/9001
- `GET /api/gps-monitor/queue/?status=all|pending|matched`: ۵۰ رکورد آخر صف موقت `public.fleet_unknowngpsdata`

## امنیت

- همه endpointها در بک‌اند به `site_admin` محدود هستند؛ پنهان کردن بخش در React صرفاً لایه رابط کاربری است و مرز امنیتی اصلی نیست.
- فرمان‌ها و فیلتر شبکه ثابت‌اند؛ ورودی درخواست به shell منتقل نمی‌شود.
- ابزارهای لاگ فقط‌خواندنی‌اند. `tcpdump` در صورتی کار می‌کند که نصب باشد و کاربر اجرای Django مجوز capture شبکه داشته باشد. برای خطای permission، به‌جای اعطای sudo عمومی، مجوز حداقلی و متناسب با سرویس را روی سرور تنظیم کنید.
- خروجی صف فقط ۶۴ بایت اول هر payload را به صورت hex برمی‌گرداند و هیچ داده‌ای را تغییر نمی‌دهد.
- هیچ migration یا مدل دیتابیسی جدیدی در این اپ وجود ندارد؛ جدول صف توسط migrationهای اپ `fleet` مدیریت می‌شود.

## آزمون

```bash
cd ~/Desktop/SANA/sana-backend
source venv/bin/activate
python manage.py check
python manage.py test ops_monitoring
```
