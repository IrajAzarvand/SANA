export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {Icon && (
        <div className="w-16 h-16 rounded-card bg-bg-hover flex items-center justify-center mb-4">
          <Icon size={28} className="text-text-muted" />
        </div>
      )}
      <h3 className="text-base font-semibold text-text-primary mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-text-muted mb-6 max-w-sm">{description}</p>
      )}
      {action}
    </div>
  );
}
