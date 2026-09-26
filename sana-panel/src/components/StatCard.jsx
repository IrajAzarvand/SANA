export default function StatCard({ title, value, icon: Icon, color = 'brand', trend }) {
  const colorMap = {
    brand:   { bg: 'bg-brand-900/30',   icon: 'text-brand-400',   accent: 'bg-brand-500' },
    success: { bg: 'bg-success/10',     icon: 'text-success',     accent: 'bg-success' },
    warning: { bg: 'bg-warning/10',     icon: 'text-warning',     accent: 'bg-warning' },
    danger:  { bg: 'bg-danger/10',      icon: 'text-danger',      accent: 'bg-danger' },
    info:    { bg: 'bg-info/10',        icon: 'text-info',        accent: 'bg-info' },
    muted:   { bg: 'bg-bg-hover',       icon: 'text-text-muted',  accent: 'bg-text-muted' },
  };

  const c = colorMap[color] || colorMap.brand;

  return (
    <div className="bg-bg-elevated border border-border-base rounded-card overflow-hidden relative">
      {/* نوار رنگی بالای کارت */}
      <div className={`h-1 ${c.accent}`} />

      <div className="p-5">
        <div className="flex items-start justify-between mb-3">
          <span className="text-sm text-text-secondary">{title}</span>
          {Icon && (
            <div className={`w-10 h-10 rounded-field ${c.bg} flex items-center justify-center`}>
              <Icon size={20} className={c.icon} />
            </div>
          )}
        </div>

        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-text-primary font-mono">{value}</span>
          {trend && (
            <span className={`text-xs font-medium ${trend > 0 ? 'text-success' : 'text-danger'}`}>
              {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
