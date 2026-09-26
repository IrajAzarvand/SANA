import { User, Shield, Building2, GitBranch, Users, Bell, Globe } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function SettingsNav({ active, onChange }) {
  const { isSiteAdmin, isMainUser, isBranchManager, isPersonal } = useAuth();

  // لیست آیتم‌ها بر اساس نقش
  const items = [
    { id: 'profile',       label: 'پروفایل من',      icon: User,      show: true },
    { id: 'security',      label: 'امنیت',            icon: Shield,    show: true },
    { id: 'organization',  label: 'اطلاعات سازمان',   icon: Building2, show: isSiteAdmin || isMainUser },
    { id: 'branches',      label: 'شعبه‌ها',           icon: GitBranch, show: isSiteAdmin || isMainUser },
    { id: 'users',         label: 'کاربران',          icon: Users,     show: isSiteAdmin || isMainUser },
    { id: 'notifications', label: 'اعلان‌ها',          icon: Bell,      show: true },
    { id: 'system',        label: 'تنظیمات سامانه',   icon: Globe,     show: isSiteAdmin },
  ].filter((item) => item.show);

  return (
    <nav className="bg-bg-elevated border border-border-base rounded-card p-2 h-fit">
      <ul className="space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <li key={item.id}>
              <button
                onClick={() => onChange(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-field text-sm transition-all relative
                  ${isActive
                    ? 'bg-bg-hover text-text-primary font-medium'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                  }`}
              >
                {isActive && (
                  <span className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-brand-500 rounded-l" />
                )}
                <Icon
                  size={18}
                  className={isActive ? 'text-brand-500' : 'text-text-muted'}
                />
                <span>{item.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}