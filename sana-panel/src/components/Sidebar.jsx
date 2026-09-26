import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Map as MapIcon, Truck, Users, Cpu, BarChart3,
  AlertTriangle, Settings, ChevronDown, Building2, Car, Shield, Globe,
  FileText,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar({ isOpen, onClose }) {
  const { user, isSiteAdmin, isOrganization, isBranchManager, isMainUser, isPersonal } = useAuth();

  // منوی ادمین — بدون «خودروها» و «رانندگان»
  const adminMenu = [
    { path: '/panel/dashboard',      icon: LayoutDashboard, label: 'داشبورد' },
    { path: '/panel/map',            icon: MapIcon,          label: 'نقشه زنده' },
    { path: '/panel/subscriptions',  icon: FileText,         label: 'قراردادها' },
    { path: '/panel/devices',        icon: Cpu,              label: 'همه دستگاه‌ها' },
    { path: '/panel/reports',        icon: BarChart3,        label: 'گزارش‌ها' },
    { path: '/panel/alerts',         icon: AlertTriangle,    label: 'هشدارها', badge: 8 },
    { path: '/panel/settings',       icon: Settings,         label: 'تنظیمات سایت' },
  ];

  const companyMenu = [
    { path: '/panel/dashboard',  icon: LayoutDashboard, label: 'داشبورد' },
    { path: '/panel/map',        icon: MapIcon,          label: 'نقشه زنده' },
    { path: '/panel/vehicles',   icon: Truck,            label: 'خودروها' },
    { path: '/panel/drivers',    icon: Users,            label: 'رانندگان' },
    { path: '/panel/devices',    icon: Cpu,              label: 'دستگاه‌ها' },
    ...(isMainUser ? [{ path: '/panel/branches', icon: Building2, label: 'شعبه‌ها' }] : []),
    ...(isMainUser ? [{ path: '/panel/users', icon: Shield, label: 'کاربران' }] : []),
    { path: '/panel/reports',    icon: BarChart3,        label: 'گزارش‌ها' },
    { path: '/panel/alerts',     icon: AlertTriangle,    label: 'هشدارها', badge: 3 },
    { path: '/panel/settings',   icon: Settings,         label: 'تنظیمات' },
  ];

  const personalMenu = [
    { path: '/panel/dashboard',  icon: LayoutDashboard, label: 'داشبورد' },
    { path: '/panel/map',        icon: MapIcon,          label: 'نقشه' },
    { path: '/panel/vehicles',   icon: Car,              label: 'خودروهای من' },
    { path: '/panel/devices',    icon: Cpu,              label: 'دستگاه‌های من' },
    { path: '/panel/reports',    icon: BarChart3,        label: 'گزارش‌ها' },
    { path: '/panel/alerts',     icon: AlertTriangle,    label: 'هشدارها', badge: 3 },
    { path: '/panel/settings',   icon: Settings,         label: 'تنظیمات' },
  ];

  const menuItems = isSiteAdmin ? adminMenu : isPersonal ? personalMenu : companyMenu;

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={onClose} />
      )}

      <aside
        className={`
          fixed lg:static inset-y-0 right-0 z-50
          w-60 bg-bg-elevated border-l border-border-base
          flex flex-col
          transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'}
        `}
      >
        <div className="lg:hidden h-16 flex items-center px-4 border-b border-border-base">
          <span className="text-2xl font-bold text-brand-500">سانا</span>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-3">
          <ul className="space-y-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `group flex items-center gap-3 px-3 py-2.5 rounded-field text-sm transition-all relative
                       ${isActive
                         ? 'bg-bg-hover text-text-primary font-medium'
                         : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                       }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-brand-500 rounded-l" />
                        )}
                        <Icon size={18} className={isActive ? 'text-brand-500' : 'text-text-muted group-hover:text-text-secondary'} />
                        <span className="flex-1">{item.label}</span>
                        {item.badge && (
                          <span className="bg-danger text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>

        {isSiteAdmin && (
          <div className="p-3 border-t border-border-base">
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-field bg-danger/10 border border-danger/30">
              <div className="w-8 h-8 rounded-field bg-danger/20 flex items-center justify-center">
                <Globe size={16} className="text-danger" />
              </div>
              <div className="flex-1">
                <div className="text-[10px] text-danger/80 leading-tight">حالت</div>
                <div className="text-sm text-danger font-medium leading-tight">ادمین کل سایت</div>
              </div>
            </div>
          </div>
        )}

        {isOrganization && (
          <div className="p-3 border-t border-border-base">
            <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-field bg-bg-base border border-border-base hover:border-border-strong transition-colors text-right">
              <div className="w-8 h-8 rounded-field bg-brand-900 flex items-center justify-center">
                <Building2 size={16} className="text-brand-400" />
              </div>
              <div className="flex-1">
                <div className="text-[10px] text-text-muted leading-tight">
                  {isBranchManager ? 'شعبه' : 'شعبه فعال'}
                </div>
                <div className="text-sm text-text-primary leading-tight">
                  {isBranchManager ? user.branch?.name : 'همه شعب'}
                </div>
              </div>
              {isMainUser && <ChevronDown size={16} className="text-text-muted" />}
            </button>
          </div>
        )}

        {isPersonal && (
          <div className="p-3 border-t border-border-base">
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-field bg-bg-base border border-border-base">
              <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-bg-base font-bold text-sm">
                {user?.name?.[0] || 'ا'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-text-primary truncate">{user?.name}</div>
                <div className="text-[10px] text-text-muted leading-tight">حساب شخصی</div>
              </div>
            </div>
          </div>
        )}

      </aside>
    </>
  );
}