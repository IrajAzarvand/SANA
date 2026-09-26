export default function Input({
  label,
  icon: Icon,
  error,
  className = '',
  required = false,
  ...props
}) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm text-text-secondary mb-2">
          {label}
          {required && <span className="text-danger mr-1">*</span>}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">
            <Icon size={18} />
          </div>
        )}
        <input
          {...props}
          className={`w-full bg-bg-base border rounded-field
                     ${Icon ? 'pr-11' : 'pr-4'} pl-4 py-2.5 text-sm
                     text-text-primary placeholder:text-text-muted
                     focus:outline-none focus:ring-2 transition-all
                     ${error
                       ? 'border-danger focus:border-danger focus:ring-danger/20'
                       : 'border-border-base focus:border-brand-500 focus:ring-brand-500/20'
                     }`}
        />
      </div>
      {error && <p className="text-xs text-danger mt-1.5">{error}</p>}
    </div>
  );
}