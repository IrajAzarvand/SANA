import { useEffect, useState } from 'react';
import { Command, Bell, Menu, ChevronDown, LogOut, User, Settings } from 'lucide-react';
import SanaLogo from './SanaLogo';
import CommandPalette from './CommandPalette';
import NotificationCenter from './NotificationCenter';
import { useAuth } from '../context/AuthContext';

export default function Header({ onMenuClick }) {
  const [profileOpen, setProfileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { user, logout } = useAuth();
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim()
    || user?.full_name
    || user?.username
    || 'کاربر';
  const avatarInitial = (user?.first_name || user?.full_name || user?.username || 'ک').trim().charAt(0);
  const roleLabel = {
    site_admin: 'ادمین کل سایت',
    main_user: 'مدیر شرکت',
    branch_manager: `مدیر شعبه ${user?.branch?.name || ''}`,
    personal_user: 'مشتری شخصی',
  }[user?.role] || '';

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, []);

  return (
    <>
      <header className="h-16 min-h-16 shrink-0 bg-bg-elevated border-b border-border-base flex items-center justify-between px-2 sm:px-4 gap-2 sm:gap-4 sticky top-0 z-30">
        {/* سمت راست: منو + لوگو */}
        <div className="flex items-center gap-3">
          <button onClick={onMenuClick} className="lg:hidden flex min-h-11 min-w-11 items-center justify-center rounded-field text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors" aria-label="باز کردن منو">
            <Menu size={20} />
          </button>
          <div className="hidden lg:block"><SanaLogo size="sm" /></div>
        </div>

        {/* دستیار دسترسی سریع */}
        <button type="button" onClick={() => setPaletteOpen(true)} className="flex min-w-0 flex-1 max-w-md items-center gap-2 rounded-field border border-border-base bg-bg-base px-3 py-2 text-text-muted transition-colors hover:border-brand-500/60 hover:bg-bg-hover" aria-label="دستیار دسترسی سریع">
          <Command size={17} className="shrink-0" />
          <span className="truncate text-sm">دستیار دسترسی سریع</span>
          <span className="mr-auto hidden sm:inline-flex rounded border border-border-base bg-bg-elevated px-1.5 py-0.5 text-[10px] text-text-muted" dir="ltr">Ctrl K</span>
        </button>

        {/* سمت چپ: اعلان + پروفایل */}
        <div className="flex min-w-0 items-center gap-1 sm:gap-2">
          <NotificationCenter />
          <div className="relative">
            <button onClick={() => setProfileOpen(!profileOpen)} className="flex min-h-11 items-center gap-2 p-1 pl-2 rounded-field hover:bg-bg-hover transition-colors" aria-expanded={profileOpen} aria-label="منوی کاربر">
              <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-bg-base font-bold text-sm">{avatarInitial}</div>
              <div className="hidden md:flex flex-col items-start text-right">
                <span className="text-sm text-text-primary leading-tight">{fullName}</span>
                <span className="text-[10px] text-text-muted leading-tight">{roleLabel}</span>
              </div>
              <ChevronDown size={16} className="hidden md:block text-text-muted" />
            </button>
            {profileOpen && <>
              <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
              <div className="absolute left-0 top-full mt-2 w-48 bg-bg-overlay border border-border-base rounded-field shadow-xl z-20 overflow-hidden">
                <button className="w-full flex items-center gap-3 px-4 py-3 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"><User size={16} /><span>پروفایل من</span></button>
                <button className="w-full flex items-center gap-3 px-4 py-3 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"><Settings size={16} /><span>تنظیمات</span></button>
                <div className="border-t border-border-base" />
                <button onClick={() => logout()} className="w-full flex items-center gap-3 px-4 py-3 text-sm text-danger hover:bg-danger/10 transition-colors"><LogOut size={16} /><span>خروج</span></button>
              </div>
            </>}
          </div>
        </div>
      </header>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
}
