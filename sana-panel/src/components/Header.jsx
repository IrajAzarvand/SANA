import { useState } from 'react';
import { Search, Bell, Menu, ChevronDown, LogOut, User, Settings } from 'lucide-react';
import SanaLogo from './SanaLogo';
import { useAuth } from '../context/AuthContext';

export default function Header({ onMenuClick }) {
  const [profileOpen, setProfileOpen] = useState(false);
  const { user, logout } = useAuth();

  return (
    <header className="h-16 bg-bg-elevated border-b border-border-base flex items-center justify-between px-4 gap-4 sticky top-0 z-30">

      {/* سمت راست: منو + لوگو */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 rounded-field text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
        >
          <Menu size={20} />
        </button>

        <div className="hidden lg:block">
          <SanaLogo size="sm" />
        </div>
      </div>

      {/* وسط: جستجو */}
      <div className="hidden md:flex flex-1 max-w-md relative">
        <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">
          <Search size={18} />
        </div>
        <input
          type="text"
          placeholder="جستجوی خودرو، راننده، دستگاه..."
          className="w-full bg-bg-base border border-border-base rounded-field
                     pr-11 pl-4 py-2 text-sm text-text-primary placeholder:text-text-muted
                     focus:outline-none focus:border-brand-500 focus:ring-2
                     focus:ring-brand-500/20 transition-all"
        />
      </div>

      {/* سمت چپ: اعلان + پروفایل */}
      <div className="flex items-center gap-2">

        {/* زنگ اعلان */}
        <button className="relative p-2 rounded-field text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors">
          <Bell size={20} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-danger rounded-full"></span>
        </button>

        {/* پروفایل */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2 p-1 pl-2 rounded-field hover:bg-bg-hover transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-bg-base font-bold text-sm">
              ا
            </div>
            <div className="hidden md:flex flex-col items-start text-right">
              <span className="text-sm text-text-primary leading-tight">{user?.name || 'کاربر'}</span>
              <span className="text-[10px] text-text-muted leading-tight">
                {user?.role === 'site_admin' && 'ادمین کل سایت'}
                {user?.role === 'main_user' && 'مدیر شرکت'}
                {user?.role === 'branch_manager' && `مدیر شعبه ${user.branch?.name || ''}`}
                {user?.role === 'personal_user' && 'کاربر شخصی'}
              </span>
            </div>
            <ChevronDown size={16} className="hidden md:block text-text-muted" />
          </button>

          {profileOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setProfileOpen(false)}
              />
              <div className="absolute left-0 top-full mt-2 w-48 bg-bg-overlay border border-border-base rounded-field shadow-xl z-20 overflow-hidden">
                <button className="w-full flex items-center gap-3 px-4 py-3 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors">
                  <User size={16} />
                  <span>پروفایل من</span>
                </button>
                <button className="w-full flex items-center gap-3 px-4 py-3 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors">
                  <Settings size={16} />
                  <span>تنظیمات</span>
                </button>
                <div className="border-t border-border-base" />
                <button
                  onClick={() => {
                    logout();
                    window.location.href = '/login';
                  }}
                  className="w-full flex items-center gap-3 px-4 py-3 text-sm text-danger hover:bg-danger/10 transition-colors"
                >
                  <LogOut size={16} />
                  <span>خروج</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>

    </header>
  );
}
