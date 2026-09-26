import { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Calendar, ChevronRight, ChevronLeft } from 'lucide-react';
import {
  toJalali,
  toGregorian,
  toJalaaliNum,
  getJalaliMonthName,
  getJalaliMonthDays,
  todayJalali,
  JALALI_WEEKDAYS,
} from '../utils/dateUtils';

function getFirstWeekdayOfMonth(jy, jm) {
  const g = toGregorian(`${jy}/${String(jm).padStart(2, '0')}/01`);
  const date = new Date(g);
  const jsDay = date.getDay();
  return (jsDay + 1) % 7;
}


/**
 * تبدیل رشته میلادی (YYYY-MM-DD) به شمسی (1405/06/26)
 * برای مقایسه با minDate
 */
function jalaliCompare(dateStr, minDateStr) {
  if (!dateStr || !minDateStr) return true;
  // مقایسه‌ی ساده‌ی رشته‌ای کار می‌کنه چون فرمت YYYY-MM-DD هست
  return dateStr >= minDateStr;
}

export default function JalaliDatePicker({
  value,
  onChange,
  label,
  placeholder = '1405/06/26',
  required = false,
  error,
  className = '',
  minDate = null,       // ← حداقل تاریخ (میلادی YYYY-MM-DD)
}) {
  const [open, setOpen] = useState(false);
  const [displayValue, setDisplayValue] = useState('');
  const [popupPos, setPopupPos] = useState({ top: 0, left: 0 });

  const today = useMemo(() => todayJalali(), []);
  const [viewYear, setViewYear] = useState(today.jy);
  const [viewMonth, setViewMonth] = useState(today.jm);

  const selected = useMemo(() => {
    if (!value) return null;
    try {
      const d = new Date(value);
      if (isNaN(d.getTime())) return null;
      const j = toJalaaliNum(d.getFullYear(), d.getMonth() + 1, d.getDate());
      return { jy: j.jy, jm: j.jm, jd: j.jd };
    } catch {
      return null;
    }
  }, [value]);

  const containerRef = useRef(null);
  const inputRef = useRef(null);
  const popupRef = useRef(null);

  useEffect(() => {
    if (value) setDisplayValue(toJalali(value));
    else setDisplayValue('');
  }, [value]);

  useEffect(() => {
    if (open && selected) {
      setViewYear(selected.jy);
      setViewMonth(selected.jm);
    }
  }, [open, selected]);

  // محاسبه موقعیت پاپ‌آپ
  useEffect(() => {
    if (!open || !inputRef.current) return;

    const updatePosition = () => {
      const rect = inputRef.current.getBoundingClientRect();
      const popupWidth = 300;
      const popupHeight = 380;

      // موقعیت افقی: راست‌چین
      let left = rect.right - popupWidth;
      if (left < 8) left = 8;
      if (left + popupWidth > window.innerWidth - 8) {
        left = window.innerWidth - popupWidth - 8;
      }

      // موقعیت عمودی: زیر input
      let top = rect.bottom + 8;
      // اگه فضای پایین نبود، بالا نشون بده
      if (top + popupHeight > window.innerHeight - 8) {
        const above = rect.top - popupHeight - 8;
        if (above > 8) top = above;
      }

      setPopupPos({ top, left });
    };

    updatePosition();

    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);

    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [open]);

  // بستن با کلیک بیرون
  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (e) => {
      if (
        popupRef.current && !popupRef.current.contains(e.target) &&
        containerRef.current && !containerRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };

    const handleEsc = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEsc);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEsc);
    };
  }, [open]);

  const handleInputChange = (e) => {
    let input = e.target.value.replace(/[^0-9/]/g, '');
    setDisplayValue(input);

    if (input.length === 10) {
      const g = toGregorian(input);
      if (g) onChange(g);
    } else if (input === '') {
      onChange('');
    }
  };

  const handleDaySelect = (day) => {
    const jalaliStr = `${viewYear}/${String(viewMonth).padStart(2, '0')}/${String(day).padStart(2, '0')}`;
    const g = toGregorian(jalaliStr);
    if (g) {
      // چک: تاریخ انتخاب‌شده باید >= minDate باشه
      if (minDate && !jalaliCompare(g, minDate)) {
        return; // نادیده بگیر
      }
      onChange(g);
      setOpen(false);
    }
  };

  const handleToday = () => {
    const g = toGregorian(`${today.jy}/${String(today.jm).padStart(2, '0')}/${String(today.jd).padStart(2, '0')}`);
    if (g) {
      if (minDate && !jalaliCompare(g, minDate)) {
        return; // امروز قبل از minDate هست، نادیده بگیر
      }
      onChange(g);
      setOpen(false);
    }
  };

  const prevMonth = () => {
    if (viewMonth === 1) { setViewYear(viewYear - 1); setViewMonth(12); }
    else setViewMonth(viewMonth - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 12) { setViewYear(viewYear + 1); setViewMonth(1); }
    else setViewMonth(viewMonth + 1);
  };
  const prevYear = () => setViewYear(viewYear - 1);
  const nextYear = () => setViewYear(viewYear + 1);

  const daysInMonth = getJalaliMonthDays(viewYear, viewMonth);
  const firstWeekday = getFirstWeekdayOfMonth(viewYear, viewMonth);

  const days = [];
  for (let i = 0; i < firstWeekday; i++) days.push(null);
  for (let i = 1; i <= daysInMonth; i++) days.push(i);

  const todayStr = `${today.jy}/${today.jm}/${today.jd}`;

  // محتوای پاپ‌آپ (با Portal رندر می‌شه)
  const popupContent = open ? createPortal(
    <div
      ref={popupRef}
      className="fixed bg-bg-elevated border border-border-base rounded-card shadow-2xl p-3 w-[300px]"
      style={{ top: popupPos.top, left: popupPos.left, zIndex: 99999 }}
      dir="rtl"
    >
      {/* هدر */}
      <div className="flex items-center justify-between mb-3">
        <button
          type="button"
          onClick={prevYear}
          className="p-1.5 rounded-field text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors"
        >
          <ChevronRight size={16} />
        </button>
        <button
          type="button"
          onClick={prevMonth}
          className="p-1.5 rounded-field text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors"
        >
          <ChevronRight size={16} />
        </button>

        <div className="flex-1 text-center">
          <span className="text-sm font-semibold text-text-primary">
            {getJalaliMonthName(viewMonth)} {viewYear}
          </span>
        </div>

        <button
          type="button"
          onClick={nextMonth}
          className="p-1.5 rounded-field text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          type="button"
          onClick={nextYear}
          className="p-1.5 rounded-field text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* روزهای هفته */}
      <div className="grid grid-cols-7 gap-1 mb-2">
        {JALALI_WEEKDAYS.map((day, i) => (
          <div
            key={i}
            className={`text-center text-[10px] font-medium py-1 ${
              i === 6 ? 'text-danger' : 'text-text-muted'
            }`}
          >
            {day}
          </div>
        ))}
      </div>

      {/* روزها */}
      <div className="grid grid-cols-7 gap-1">
        {days.map((day, i) => {
          if (day === null) {
            return <div key={`empty-${i}`} className="aspect-square" />;
          }

              const dayStr = `${viewYear}/${viewMonth}/${day}`;
              const isToday = dayStr === todayStr;
              const isSelected = selected &&
                selected.jy === viewYear &&
                selected.jm === viewMonth &&
                selected.jd === day;
              const isFriday = (i % 7) === 6;

              // چک: آیا این روز مجاز به انتخاب هست؟
              const gregorianDay = toGregorian(
                `${viewYear}/${String(viewMonth).padStart(2, '0')}/${String(day).padStart(2, '0')}`
              );
              const isDisabled = minDate && gregorianDay && !jalaliCompare(gregorianDay, minDate);

              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => !isDisabled && handleDaySelect(day)}
                  disabled={isDisabled}
                  className={`aspect-square rounded-field text-xs font-medium transition-all
                    ${isDisabled
                      ? 'text-text-muted opacity-30 cursor-not-allowed'
                      : isSelected
                        ? 'bg-brand-500 text-bg-base font-bold'
                        : isToday
                          ? 'bg-brand-500/20 text-brand-400 ring-1 ring-brand-500'
                          : isFriday
                            ? 'text-danger hover:bg-bg-hover'
                            : 'text-text-primary hover:bg-bg-hover'
                    }
                  `}
                >
                  {day}
                </button>
              );
        })}
      </div>

      {/* فوتر */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border-base">
        <button
          type="button"
          onClick={handleToday}
          className="text-xs text-brand-400 hover:text-brand-500 transition-colors px-2 py-1"
        >
          امروز
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-xs text-text-muted hover:text-text-primary transition-colors px-2 py-1"
        >
          بستن
        </button>
      </div>
    </div>,
    document.body
  ) : null;

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {label && (
        <label className="block text-sm text-text-secondary mb-2">
          {label}
          {required && <span className="text-danger mr-1">*</span>}
        </label>
      )}

      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-brand-400 transition-colors z-10"
        >
          <Calendar size={18} />
        </button>
        <input
          ref={inputRef}
          type="text"
          value={displayValue}
          onChange={handleInputChange}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          maxLength={10}
          dir="ltr"
          className="w-full bg-bg-base border border-border-base rounded-field
                     pr-11 pl-4 py-2.5 text-sm text-text-primary
                     placeholder:text-text-muted
                     focus:outline-none focus:border-brand-500 focus:ring-2
                     focus:ring-brand-500/20 transition-all font-mono text-left"
        />
      </div>

      {popupContent}

      {error && <p className="text-xs text-danger mt-1.5">{error}</p>}
    </div>
  );
}