import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MoreVertical } from 'lucide-react';

export default function ActionMenu({ items }) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const buttonRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (e) => {
      if (
        menuRef.current && !menuRef.current.contains(e.target) &&
        buttonRef.current && !buttonRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };

    const handleScroll = () => setOpen(false);
    const handleResize = () => setOpen(false);

    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', handleResize);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('scroll', handleScroll, true);
      window.removeEventListener('resize', handleResize);
    };
  }, [open]);

  const handleToggle = () => {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const menuWidth = 176; // w-44 = 176px
      const menuHeight = items.length * 36 + 8;

      // محاسبه موقعیت
      let left = rect.left + rect.width / 2 - menuWidth / 2;

      // اگه منو از سمت راست صفحه بیرون بزنه
      if (left < 8) left = 8;
      if (left + menuWidth > window.innerWidth - 8) {
        left = window.innerWidth - menuWidth - 8;
      }

      // اگه فضای پایین کافی نیست، به بالا باز کن
      let top = rect.bottom + 4;
      if (top + menuHeight > window.innerHeight - 8) {
        top = rect.top - menuHeight - 4;
      }

      setCoords({ top, left });
    }
    setOpen(!open);
  };

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleToggle}
        className="p-1.5 rounded-field text-text-muted hover:bg-bg-base hover:text-text-primary transition-colors"
      >
        <MoreVertical size={16} />
      </button>

      {open && createPortal(
        <div
          ref={menuRef}
          dir="rtl"
          style={{ position: 'fixed', top: coords.top, left: coords.left, zIndex: 99999 }}
          className="w-44 bg-bg-overlay border border-border-base rounded-field shadow-2xl overflow-hidden animate-fadeIn"
        >
          {items.map((item, idx) => {
            const Icon = item.icon;
            return (
              <button
                key={idx}
                onClick={() => {
                  setOpen(false);
                  item.onClick?.();
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs transition-colors ${
                  item.variant === 'danger'
                    ? 'text-danger hover:bg-danger/10'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
              >
                {Icon && <Icon size={14} />}
                {item.label}
              </button>
            );
          })}
        </div>,
        document.body
      )}
    </>
  );
}
