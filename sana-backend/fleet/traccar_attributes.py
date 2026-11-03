"""
Central metadata for Traccar position attributes used by SANA.

This module contains presentation metadata only. Traccar remains the source of
truth for all position values. Do not persist position/attribute values here.

The static registry is based on the attribute keys declared by Traccar's
Position model. Actual availability and value formats depend on the device,
protocol decoder, server-side processing, and configured computed attributes.

Unknown/custom attributes must remain visible with their original key.
"""

from typing import Any


# Metadata only; keys must match Traccar's case-sensitive attribute names.
#
# Optional fields:
#   label:      Persian display name
#   unit:       Unit only where Traccar defines it consistently
#   category:   Suggested group in position details
#   value_type: A safe presentation hint, not a validation rule
#   description: Short clarification for ambiguous/common fields
#
# Do not add per-position values. Some units vary by protocol/device; for
# those attributes, omit "unit" rather than displaying a possibly false unit.
TRACCAR_ATTRIBUTES: dict[str, dict[str, Any]] = {
    # Raw message and position quality
    "raw": {"label": "داده خام پیام", "category": "technical", "value_type": "text"},
    "index": {"label": "شماره ترتیب پیام", "category": "technical", "value_type": "number"},
    "hdop": {"label": "دقت افقی GPS (HDOP)", "category": "gps", "value_type": "number"},
    "vdop": {"label": "دقت عمودی GPS (VDOP)", "category": "gps", "value_type": "number"},
    "pdop": {"label": "شاخص دقت موقعیت (PDOP)", "category": "gps", "value_type": "number"},
    "sat": {"label": "تعداد ماهواره‌های GPS", "category": "gps", "value_type": "number"},
    "satVisible": {"label": "تعداد ماهواره‌های قابل مشاهده", "category": "gps", "value_type": "number"},
    "rssi": {"label": "قدرت سیگنال", "category": "network", "value_type": "number"},
    "gps": {"label": "وضعیت GPS", "category": "gps"},
    "roaming": {"label": "وضعیت رومینگ سیم‌کارت", "category": "network"},
    "approximate": {"label": "موقعیت تقریبی", "category": "gps"},
    
    # Events and status
    "event": {"label": "کد رویداد", "category": "events"},
    "alarm": {"label": "هشدار", "category": "events"},
    "status": {"label": "وضعیت دستگاه", "category": "status"},
    "result": {"label": "نتیجه عملیات یا فرمان", "category": "events"},
    "type": {"label": "نوع پیام یا داده", "category": "technical"},
    "archive": {"label": "پیام آرشیوی", "category": "technical"},
    
    # Odometer, distance and operating time
    "odometer": {"label": "کیلومترشمار", "unit": "m", "category": "vehicle", "value_type": "number"},
    "serviceOdometer": {"label": "کیلومترشمار سرویس", "unit": "m", "category": "maintenance", "value_type": "number"},
    "tripOdometer": {"label": "مسافت‌سنج سفر", "unit": "m", "category": "vehicle", "value_type": "number"},
    "distance": {"label": "مسافت", "unit": "m", "category": "vehicle", "value_type": "number"},
    "totalDistance": {"label": "مسافت کل", "unit": "m", "category": "vehicle", "value_type": "number"},
    "hours": {"label": "مدت کارکرد", "unit": "ms", "category": "vehicle", "value_type": "number"},
    "drivingTime": {"label": "مدت رانندگی", "category": "vehicle", "value_type": "number"},
    "steps": {"label": "تعداد گام‌ها", "category": "activity", "value_type": "number"},
    
    # Driver and identification
    "driverUniqueId": {"label": "شناسه اختصاصی راننده", "category": "driver"},
    "card": {"label": "شماره کارت راننده", "category": "driver"},
    "operator": {"label": "اپراتور", "category": "device"},
    "phone": {"label": "شماره تلفن", "category": "device"},
    "iccid": {"label": "شناسه ICCID سیم‌کارت", "category": "device"},
    "vin": {"label": "شماره شاسی (VIN)", "category": "vehicle"},
    
    # Vehicle / engine
    "ignition": {"label": "وضعیت سوئیچ", "category": "vehicle", "value_type": "boolean"},
    "motion": {"label": "وضعیت حرکت", "category": "vehicle", "value_type": "boolean"},
    "armed": {"label": "وضعیت فعال بودن دزدگیر", "category": "security", "value_type": "boolean"},
    "rpm": {"label": "دور موتور", "unit": "rpm", "category": "vehicle", "value_type": "number"},
    "obdSpeed": {"label": "سرعت از OBD", "unit": "km/h", "category": "vehicle", "value_type": "number"},
    "obdOdometer": {"label": "کیلومترشمار OBD", "unit": "m", "category": "vehicle", "value_type": "number"},
    "throttle": {"label": "موقعیت دریچه گاز", "category": "vehicle", "value_type": "number"},
    "engineLoad": {"label": "بار موتور", "category": "vehicle", "value_type": "number"},
    "engineTemp": {"label": "دمای موتور", "category": "vehicle", "value_type": "number"},
    "coolantTemp": {"label": "دمای مایع خنک‌کننده", "unit": "°C", "category": "vehicle", "value_type": "number"},
    "speedLimit": {"label": "حداکثر سرعت مجاز", "category": "vehicle", "value_type": "number"},
    "business": {"label": "وضعیت کاری", "category": "vehicle"},
    
    # Power, battery, fuel and energy
    "power": {"label": "ولتاژ برق ورودی", "category": "power", "value_type": "number", "description": "واحد در بعضی پروتکل‌ها متفاوت است."},
    "battery": {"label": "ولتاژ باتری", "category": "power", "value_type": "number", "description": "واحد در بعضی پروتکل‌ها متفاوت است."},
    "batteryLevel": {"label": "درصد شارژ باتری", "unit": "%", "category": "power", "value_type": "number"},
    "charge": {"label": "وضعیت شارژ", "category": "power"},
    "fuel": {"label": "مقدار سوخت", "category": "fuel", "value_type": "number", "description": "واحد ممکن است با توجه به پروتکل متفاوت باشد."},
    "fuelUsed": {"label": "سوخت مصرف‌شده", "category": "fuel", "value_type": "number", "description": "واحد ممکن است با توجه به پروتکل متفاوت باشد."},
    "fuelConsumption": {"label": "نرخ مصرف سوخت", "category": "fuel", "value_type": "number", "description": "واحد ممکن است با توجه به پروتکل متفاوت باشد."},
    "fuelLevel": {"label": "سطح سوخت", "category": "fuel", "value_type": "number", "description": "واحد ممکن است با توجه به پروتکل متفاوت باشد."},
    "energy": {"label": "انرژی مصرف‌شده", "unit": "kWh", "category": "power", "value_type": "number"},
    "energyLevel": {"label": "سطح انرژی", "unit": "%", "category": "power", "value_type": "number"},
    
    # Inputs, outputs and sensors
    "input": {"label": "وضعیت ورودی‌ها", "category": "io"},
    "output": {"label": "وضعیت خروجی‌ها", "category": "io"},
    "humidity": {"label": "رطوبت", "category": "sensors", "value_type": "number"},
    "deviceTemp": {"label": "دمای دستگاه", "unit": "°C", "category": "sensors", "value_type": "number"},
    "acceleration": {"label": "شتاب", "category": "sensors", "value_type": "number"},
    "gSensor": {"label": "داده حسگر شتاب‌سنج", "category": "sensors"},
    "axleWeight": {"label": "وزن محور", "category": "vehicle", "value_type": "number"},
    "heartRate": {"label": "ضربان قلب", "category": "sensors", "value_type": "number"},
    
    # Device information and connectivity
    "versionFw": {"label": "نسخه Firmware", "category": "device"},
    "versionHw": {"label": "نسخه سخت‌افزار", "category": "device"},
    "antenna": {"label": "وضعیت آنتن", "category": "device"},
    "ip": {"label": "آدرس IP", "category": "network"},
    "flags": {"label": "بیت‌فلگ‌ها", "category": "technical"},
    "command": {"label": "اطلاعات فرمان", "category": "technical"},
    "blocked": {"label": "وضعیت مسدود بودن", "category": "security"},
    "lock": {"label": "وضعیت قفل", "category": "vehicle"},
    "door": {"label": "وضعیت درب‌ها", "category": "vehicle"},
    "geofence": {"label": "اطلاعات محدوده جغرافیایی", "category": "geofence"},
    "dtcs": {"label": "کدهای خطای خودرو (DTC)", "category": "vehicle"},
    
    # Media references
    "image": {"label": "تصویر", "category": "media"},
    "video": {"label": "ویدئو", "category": "media"},
    "audio": {"label": "صوت", "category": "media"},
}


# Traccar also defines numbered attribute families. Their suffix and exact
# meaning depend on the device decoder; keep the original key in the label.
_NUMBERED_ATTRIBUTE_PREFIXES: dict[str, tuple[str, str]] = {
    "temp": ("دمای حسگر", "sensors"),
    "adc": ("ورودی آنالوگ", "io"),
    "io": ("ورودی/خروجی", "io"),
    "count": ("شمارنده", "io"),
    "in": ("ورودی", "io"),
    "out": ("خروجی", "io"),
}


def get_attribute_metadata(attribute_key: str) -> dict[str, Any]:
    """
    Return presentation metadata for a known Traccar attribute.

    Unknown/custom attributes are never discarded: their original key is
    returned as the label. Numbered Traccar attribute families receive a
    readable generic label without assuming a unit or data type.
    """
    metadata = TRACCAR_ATTRIBUTES.get(attribute_key)

    if metadata is not None:
        return {
            **metadata,
            "key": attribute_key,
            "label": metadata.get("label") or attribute_key,
            "known": True,
        }

    for prefix, (prefix_label, category) in _NUMBERED_ATTRIBUTE_PREFIXES.items():
        suffix = attribute_key[len(prefix):] if attribute_key.startswith(prefix) else ""
        if suffix.isdigit() and int(suffix) >= 1:
            return {
                "key": attribute_key,
                "label": f"{prefix_label} {suffix} ({attribute_key})",
                "category": category,
                "known": True,
            }

    return {
        "key": attribute_key,
        "label": attribute_key,
        "known": False,
    }
