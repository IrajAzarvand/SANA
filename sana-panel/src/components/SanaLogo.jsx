export default function SanaLogo({ size = 'md', showSubtitle = false }) {
  const sizes = {
    sm: { text: 'text-2xl', sub: 'text-[10px]', icon: 20 },
    md: { text: 'text-3xl', sub: 'text-xs',    icon: 28 },
    lg: { text: 'text-4xl', sub: 'text-sm',    icon: 36 },
  };
  const s = sizes[size];

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex items-center gap-2">
        <svg
          width={s.icon}
          height={s.icon}
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="16" cy="16" r="14" stroke="#14B8A6" strokeWidth="1.5" opacity="0.3" />
          <circle cx="16" cy="16" r="9" stroke="#14B8A6" strokeWidth="1.5" opacity="0.6" />
          <circle cx="16" cy="16" r="4" fill="#14B8A6" />
          <line x1="16" y1="1" x2="16" y2="5" stroke="#14B8A6" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="16" y1="27" x2="16" y2="31" stroke="#14B8A6" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="1" y1="16" x2="5" y2="16" stroke="#14B8A6" strokeWidth="1.5" strokeLinecap="round" />
          <line x1="27" y1="16" x2="31" y2="16" stroke="#14B8A6" strokeWidth="1.5" strokeLinecap="round" />
        </svg>

        <span className={`${s.text} font-bold text-brand-500 tracking-tight`}>
          سانا
        </span>
      </div>

      {showSubtitle && (
        <span className={`${s.sub} text-text-muted`}>
          سامانه اتوماسیون ناوگان ایران
        </span>
      )}
    </div>
  );
}
