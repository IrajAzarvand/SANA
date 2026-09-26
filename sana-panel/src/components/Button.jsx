export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  ...props
}) {
  const variants = {
    primary:   'bg-brand-500 hover:bg-brand-400 active:bg-brand-600 text-bg-base font-medium',
    secondary: 'bg-bg-hover hover:bg-bg-overlay text-text-primary border border-border-base',
    ghost:     'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
    danger:    'bg-danger/10 hover:bg-danger/20 text-danger border border-danger/30',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  };

  return (
    <button
      {...props}
      className={`inline-flex items-center gap-2 rounded-field transition-colors
                  disabled:opacity-50 disabled:cursor-not-allowed
                  ${variants[variant]} ${sizes[size]}`}
    >
      {Icon && <Icon size={size === 'sm' ? 14 : 16} />}
      {children}
    </button>
  );
}
