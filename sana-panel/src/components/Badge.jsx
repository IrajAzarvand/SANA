export default function Badge({ children, variant = 'neutral' }) {
  const variants = {
    neutral:  'bg-bg-hover text-text-secondary border-border-base',
    success:  'bg-success/10 text-success border-success/30',
    warning:  'bg-warning/10 text-warning border-warning/30',
    danger:   'bg-danger/10 text-danger border-danger/30',
    info:     'bg-info/10 text-info border-info/30',
    brand:    'bg-brand-900/40 text-brand-400 border-brand-500/30',
  };

  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${variants[variant]}`}>
      {children}
    </span>
  );
}
