# SANA Map

ماژول مستقل نمایش نقشه در پروژه SANA. این پوشه فقط مسئول نمایش نقشه و نشانگرهای موقعیت است؛ دریافت داده و مجوزها در sana-backend و polling/auth در sana-panel باقی می‌مانند.

## ساختار فعلی

- `src/LiveDeviceMap.jsx`: نقطه ورود عمومی نقشه و انتخاب provider
- `src/config.js`: provider پیش‌فرض و تنظیمات نقشه
- `src/providers/NeshanLeafletMap.jsx`: آداپتور Leaflet SDK نشان

## تنظیمات

در فایل محیطی محلی `sana-panel/.env` مقدار `VITE_NESHAN_API_KEY` را تنظیم کنید. این کلید برای SDK سمت مرورگر است؛ کلیدهای وب‌سرویس‌های خصوصی نشان را در مرورگر قرار ندهید.

`VITE_MAP_PROVIDER=neshan-leaflet` provider پیش‌فرض فعلی است. قرارداد ورودی `LiveDeviceMap` مستقل از ارائه‌دهنده می‌ماند تا provider دیگری بعداً بدون تغییر API موقعیت و منطق ناوگان اضافه شود.

## قرارداد موقعیت

هر موقعیت باید دست‌کم شامل `device_id`, `imei`, `latitude`, `longitude`, `last_seen`, `status` باشد. `vehicle_plate`، `speed`، `heading` و `position_is_current` برای جزئیات اختیاری/تکمیلی‌اند.

هیچ داده نمونه‌ای در این ماژول وجود ندارد؛ مختصات از API احراز هویت‌شده سانا دریافت می‌شوند.
