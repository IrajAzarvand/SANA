import { ChevronDown } from 'lucide-react';

export default function Select({
  label,
  options = [],
  value,
  onChange,
  placeholder,
  required = false,
  disabled = false,
}) {
  return (
    <div>
      {label && (
        <label className="block text-sm text-text-secondary mb-2">
          {label}
          {required && <span className="text-danger mr-1">*</span>}
        </label>
      )}
      <div className="relative">
        <select
          value={value}
          onChange={onChange}
          disabled={disabled}
          className="w-full appearance-none bg-bg-base border border-border-base
                     rounded-field pr-4 pl-10 py-2.5 text-sm text-text-primary
                     focus:outline-none focus:border-brand-500 focus:ring-2
                     focus:ring-brand-500/20 transition-all cursor-pointer
                     disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none"
        />
      </div>
    </div>
  );
}