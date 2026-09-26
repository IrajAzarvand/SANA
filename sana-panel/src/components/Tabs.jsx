export default function Tabs({ tabs, activeTab, onChange }) {
  return (
    <div className="flex items-center gap-1 border-b border-border-base">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={`relative px-4 py-3 text-sm font-medium transition-colors
                     ${activeTab === tab.value
                       ? 'text-brand-400'
                       : 'text-text-secondary hover:text-text-primary'
                     }`}
        >
          <span className="flex items-center gap-2">
            {tab.label}
            {tab.count !== undefined && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center
                               ${activeTab === tab.value
                                 ? 'bg-brand-900/60 text-brand-400'
                                 : 'bg-bg-hover text-text-muted'
                               }`}>
                {tab.count}
              </span>
            )}
          </span>
          {activeTab === tab.value && (
            <span className="absolute bottom-0 right-0 left-0 h-0.5 bg-brand-500" />
          )}
        </button>
      ))}
    </div>
  );
}
