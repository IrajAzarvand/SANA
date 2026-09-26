import { useState, useEffect, useRef, useMemo } from 'react';
import { User as UserIcon, ChevronDown, Check, X } from 'lucide-react';
import { usersAPI } from '../api/services/fleet';

/**
 * ComboBox انتخاب کاربر
 * - همه‌ی کاربران رو یه بار از سرور می‌گیره
 * - توی Frontend با startsWith فیلتر می‌کنه
 * - با انتخاب، اطلاعات کامل کاربر برمی‌گرده
 */
export default function UserComboBox({
  value = '',
  onChange,
  onSelectUser,
  onClearUser,
  selectedUserId = null,
  accountType = 'organization',
  label = 'نام کاربری',
  placeholder = 'تایپ کنید یا انتخاب کنید...',
  required = false,
  error,
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState(value);
  const [allUsers, setAllUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // sync search با value وقتی از بیرون عوض می‌شه
  useEffect(() => {
    setSearch(value);
  }, [value]);

  // گرفتن همه‌ی کاربران (یه بار)
  useEffect(() => {
    if (!open) return;
    if (allUsers.length > 0) return;

    const fetchUsers = async () => {
      setLoading(true);
      try {
        const result = await usersAPI.list({
          account_type: accountType,
        });
        const list = Array.isArray(result) ? result : result.results || [];
        setAllUsers(list);
      } catch (e) {
        console.error('Error fetching users:', e);
        setAllUsers([]);
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, [open, accountType, allUsers.length]);

  // فیلتر توی Frontend
  const filteredUsers = useMemo(() => {
    if (!search || search.trim().length === 0) {
      return allUsers.slice(0, 20); // ۲۰ تای اول
    }

    const q = search.trim().toLowerCase();

    // اول: startsWith با username
    const startsWith = allUsers.filter((u) =>
      u.username.toLowerCase().startsWith(q)
    );

    // دوم: includes با username (اگه startsWith نبود)
    if (startsWith.length === 0) {
      return allUsers
        .filter((u) => u.username.toLowerCase().includes(q))
        .slice(0, 20);
    }

    return startsWith.slice(0, 20);
  }, [allUsers, search]);

  // بستن با کلیک بیرون
  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleSelect = (user) => {
    console.log('Selected user:', user);
    console.log('Organization data:', user.organization_data);
    setSearch(user.username);
    onChange(user.username);
    if (onSelectUser) onSelectUser(user);
    setOpen(false);
  };

  const handleClear = () => {
    setSearch('');
    onChange('');
    if (onClearUser) onClearUser();
    if (inputRef.current) inputRef.current.focus();
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setSearch(val);
    onChange(val);

    if (selectedUserId && onClearUser) {
      onClearUser();
    }

    if (!open) setOpen(true);
  };

  const matchedUser = allUsers.find((u) => u.id === selectedUserId);

  return (
    <div ref={containerRef} className="relative">
      {label && (
        <label className="block text-sm text-text-secondary mb-2">
          {label}
          {required && <span className="text-danger mr-1">*</span>}
        </label>
      )}

      <div className="relative">
        <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none z-10">
          <UserIcon size={18} />
        </div>

        <input
          ref={inputRef}
          type="text"
          value={search}
          onChange={handleInputChange}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className={`w-full bg-bg-base border rounded-field
                     pr-11 pl-10 py-2.5 text-sm
                     text-text-primary placeholder:text-text-muted
                     focus:outline-none focus:ring-2 transition-all
                     ${error
                       ? 'border-danger focus:border-danger focus:ring-danger/20'
                       : 'border-border-base focus:border-brand-500 focus:ring-brand-500/20'
                     }`}
        />

        <div className="absolute left-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {search && (
            <button
              type="button"
              onClick={handleClear}
              className="text-text-muted hover:text-text-primary transition-colors"
            >
              <X size={14} />
            </button>
          )}
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="text-text-muted hover:text-text-primary transition-colors"
          >
            <ChevronDown size={16} />
          </button>
        </div>
      </div>

      {selectedUserId && matchedUser && (
        <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-brand-400">
          <Check size={12} />
          <span>کاربر موجود: {matchedUser.full_name || matchedUser.username}</span>
        </div>
      )}

      {open && (
        <div
          className="absolute z-[9999] mt-2 bg-bg-elevated border border-border-base rounded-card shadow-2xl max-h-64 overflow-y-auto"
          style={{ top: '100%', right: 0, left: 0 }}
        >
          {loading ? (
            <div className="p-3 text-center text-xs text-text-muted">
              در حال بارگذاری...
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="p-3 text-center text-xs text-text-muted">
              کاربری یافت نشد — «{search}» به عنوان کاربر جدید ثبت می‌شود
            </div>
          ) : (
            <div className="p-1">
              {filteredUsers.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => handleSelect(u)}
                  className={`w-full text-right p-2.5 rounded-field transition-colors flex items-center gap-3
                    ${u.id === selectedUserId ? 'bg-brand-500/10' : 'hover:bg-bg-hover'}`}
                >
                  <div className="w-8 h-8 rounded-full bg-brand-900/40 flex items-center justify-center text-brand-400 font-bold text-xs flex-shrink-0">
                    {u.first_name?.[0] || u.username[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-text-primary truncate">
                      {u.full_name || u.username}
                    </div>
                    <div className="text-[10px] text-text-muted font-mono truncate">
                      {u.username} {u.mobile ? `— ${u.mobile}` : ''}
                    </div>
                  </div>
                  {u.id === selectedUserId && (
                    <Check size={14} className="text-brand-400 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <p className="text-xs text-danger mt-1.5">{error}</p>}
    </div>
  );
}