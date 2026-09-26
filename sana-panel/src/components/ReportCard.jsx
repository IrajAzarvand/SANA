import {
  Route, User, Truck, Fuel, AlertTriangle, Cpu, Wrench, Map as MapIcon,
  Download, Eye,
} from 'lucide-react';

const iconMap = {
  route: Route,
  user:  User,
  truck: Truck,
  fuel:  Fuel,
  alert: AlertTriangle,
  cpu:   Cpu,
  wrench: Wrench,
  map:   MapIcon,
};

const colorMap = {
  brand:   { bg: 'bg-brand-900/40', icon: 'text-brand-400' },
  success: { bg: 'bg-success/10',   icon: 'text-success'   },
  info:    { bg: 'bg-info/10',      icon: 'text-info'      },
  warning: { bg: 'bg-warning/10',   icon: 'text-warning'   },
  danger:  { bg: 'bg-danger/10',    icon: 'text-danger'    },
  muted:   { bg: 'bg-bg-hover',     icon: 'text-text-muted'},
};

export default function ReportCard({ report, onPreview }) {
  const Icon = iconMap[report.icon] || Route;
  const c = colorMap[report.color] || colorMap.brand;

  return (
    <div className="bg-bg-elevated border border-border-base rounded-card p-5 hover:border-border-strong transition-all group">

      <div className="flex items-start justify-between mb-4">
        <div className={`w-11 h-11 rounded-field ${c.bg} flex items-center justify-center`}>
          <Icon size={20} className={c.icon} />
        </div>
        <span className="text-[10px] text-text-muted bg-bg-base border border-border-base px-2 py-1 rounded-full">
          {report.category}
        </span>
      </div>

      <h3 className="text-base font-semibold text-text-primary mb-1.5">
        {report.title}
      </h3>
      <p className="text-xs text-text-muted leading-relaxed mb-4 min-h-[2.5rem]">
        {report.description}
      </p>

      <div className="flex flex-wrap items-center gap-1.5 mb-4">
        {report.format.map((f) => (
          <span
            key={f}
            className="text-[10px] text-text-secondary bg-bg-base border border-border-base px-2 py-0.5 rounded font-mono"
          >
            {f}
          </span>
        ))}
      </div>

      <div className="flex items-center gap-2 pt-4 border-t border-border-base">
        <button
          onClick={() => onPreview(report)}
          className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium
                     text-text-secondary hover:text-text-primary hover:bg-bg-hover
                     px-3 py-2 rounded-field transition-colors"
        >
          <Eye size={14} />
          پیش‌نمایش
        </button>
        <button
          className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs font-medium
                     text-brand-400 hover:text-brand-500 hover:bg-brand-900/30
                     px-3 py-2 rounded-field transition-colors"
        >
          <Download size={14} />
          دانلود
        </button>
      </div>

    </div>
  );
}
