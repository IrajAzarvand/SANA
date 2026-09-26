import { X } from 'lucide-react';
import { useEffect } from 'react';

export default function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* modal */}
      <div className={`relative w-full ${sizes[size]} bg-bg-elevated border border-border-base rounded-card shadow-2xl max-h-[90vh] flex flex-col`}>
        {/* header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-base">
          <h3 className="text-base font-semibold text-text-primary">{title}</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-field text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* body */}
        <div className="flex-1 overflow-y-auto p-5">
          {children}
        </div>

        {/* footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-border-base">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
