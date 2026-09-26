import { useState, useMemo, useCallback } from 'react';
import { Search, Plus, Users as UsersIcon, Pencil, Trash2, UserX, ChevronDown, ChevronLeft, Building2 } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Button from '../components/Button';
import Input from '../components/Input';
import Modal from '../components/Modal';
import ActionMenu from '../components/ActionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { useAuth } from '../context/AuthContext';
import { usersAPI } from '../api/services/fleet';
import { organizationsAPI } from '../api/services/organizations';
import { useApi } from '../hooks/useApi';

const roleMap = {
  site_admin:     { label: 'ادمین کل سایت', variant: 'danger' },
  main_user:      { label: 'مدیر شرکت',     variant: 'brand'  },
  branch_manager: { label: 'مدیر شعبه',     variant: 'info'   },
  personal_user:  { label: 'کاربر شخصی',    variant: 'muted'  },
};

export default function Users() {
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [showPersonal, setShowPersonal] = useState(false);

  const { isSiteAdmin, isMainUser } = useAuth();

  // دریافت کاربران از API
  const fetchUsers = useCallback(async () => {
    const result = await usersAPI.list();
    // DRF pagination ممکنه برگردونه { count, next, previous, results }
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const fetchOrgs = useCallback(async () => {
    try {
      const result = await organizationsAPI.list();
      return Array.isArray(result) ? result : result.results || [];
    } catch {
      return [];
    }
  }, []);

  const { data: users, loading: usersLoading, error: usersError, refetch: refetchUsers } =
    useApi(fetchUsers, []);

  const { data: organizations } = useApi(fetchOrgs, []);

  // گروه‌بندی کاربران سازمانی بر اساس organization
  const groupedCompanies = useMemo(() => {
    if (!users) return [];

    const orgUsers = users.filter((u) => u.account_type === 'organization');
    const map = new Map();

    orgUsers.forEach((u) => {
      const orgId = u.organization;
      const orgName = u.organization_name || 'بدون سازمان';
      if (!map.has(orgId)) {
        map.set(orgId, {
          id: orgId,
          name: orgName,
          users: [],
        });
      }
      map.get(orgId).users.push(u);
    });

    return Array.from(map.values());
  }, [users]);

  // کاربران شخصی
  const personalUsers = useMemo(() => {
    if (!users) return [];
    return users.filter((u) => u.account_type === 'personal');
  }, [users]);

  // فیلتر بر اساس جستجو
  const filteredCompanies = useMemo(() => {
    if (!search) return groupedCompanies;
    return groupedCompanies.filter((c) =>
      c.name.includes(search) ||
      c.users.some((u) =>
        `${u.first_name} ${u.last_name}`.includes(search) ||
        (u.email && u.email.includes(search)) ||
        (u.mobile && u.mobile.includes(search))
      )
    );
  }, [groupedCompanies, search]);

  const filteredPersonal = useMemo(() => {
    if (!search) return personalUsers;
    return personalUsers.filter((u) =>
      `${u.first_name} ${u.last_name}`.includes(search) ||
      (u.email && u.email.includes(search)) ||
      (u.mobile && u.mobile.includes(search))
    );
  }, [personalUsers, search]);

  const toggleCompany = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getUserMenu = (user) => {
    const items = [];

    if (isSiteAdmin || isMainUser) {
      items.push({
        label: 'ویرایش',
        icon: Pencil,
        onClick: () => console.log('Edit user:', user.id),
      });
      items.push({
        label: 'غیرفعال',
        icon: UserX,
        onClick: () => console.log('Disable user:', user.id),
      });
    }

    if (isSiteAdmin) {
      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => console.log('Delete user:', user.id),
      });
    }

    return items;
  };

  // Loading state
  if (usersLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={isSiteAdmin ? 'همه کاربران' : 'کاربران سازمان'}
          subtitle="در حال بارگذاری..."
        />
        <Card>
          <LoadingSpinner />
        </Card>
      </div>
    );
  }

  // Error state
  if (usersError) {
    return (
      <div className="space-y-6">
        <PageHeader
          title={isSiteAdmin ? 'همه کاربران' : 'کاربران سازمان'}
          subtitle="خطا در دریافت اطلاعات"
        />
        <Card>
          <ErrorState error={usersError} onRetry={refetchUsers} />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader
        title={isSiteAdmin ? 'همه کاربران' : 'کاربران سازمان'}
        subtitle={isSiteAdmin ? 'مدیریت کاربران به تفکیک شرکت' : 'مدیریت کاربران سازمان شما'}
        actions={
          <Button icon={Plus} onClick={() => setModalOpen(true)}>
            افزودن کاربر
          </Button>
        }
      />

      <Card>
        <Input
          icon={Search}
          placeholder="جستجوی نام، ایمیل یا نام شرکت..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Card>

      {/* شرکت‌ها با کاربران درختی */}
      {filteredCompanies.length === 0 && filteredPersonal.length === 0 ? (
        <Card>
          <div className="py-12 text-center">
            <UsersIcon size={40} className="text-text-muted mx-auto mb-3" />
            <p className="text-sm text-text-muted">کاربری یافت نشد</p>
          </div>
        </Card>
      ) : (
        <>
          <div className="space-y-3">
            {filteredCompanies.map((company) => {
              const isExpanded = expanded[company.id] !== false; // پیش‌فرض باز
              return (
                <Card key={company.id}>
                  <button
                    onClick={() => toggleCompany(company.id)}
                    className="w-full flex items-center justify-between gap-3 p-1 hover:bg-bg-hover rounded-field transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-field bg-brand-900/40 flex items-center justify-center">
                        <Building2 size={18} className="text-brand-400" />
                      </div>
                      <div className="text-right">
                        <div className="font-medium text-text-primary">{company.name}</div>
                        <div className="text-[10px] text-text-muted">شرکت</div>
                      </div>
                      <Badge variant="brand">{company.users.length} کاربر</Badge>
                    </div>
                    <div className="p-1 text-text-muted">
                      {isExpanded ? <ChevronDown size={18} /> : <ChevronLeft size={18} />}
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-border-base">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-border-base">
                              <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">نام</th>
                              <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">تماس</th>
                              <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">نقش</th>
                              <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">شعبه</th>
                              <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                              <th className="w-12"></th>
                            </tr>
                          </thead>
                          <tbody>
                            {company.users.map((u) => {
                              const role = roleMap[u.role] || roleMap.personal_user;
                              return (
                                <tr key={u.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                                  <td className="py-3 px-4">
                                    <div className="flex items-center gap-3">
                                      <div className="w-8 h-8 rounded-full bg-brand-900/40 flex items-center justify-center text-brand-400 font-bold text-xs">
                                        {u.first_name?.[0] || u.username[0]}
                                      </div>
                                      <div>
                                        <div className="font-medium text-text-primary text-xs">
                                          {u.full_name || u.username}
                                        </div>
                                        <div className="text-[10px] text-text-muted font-mono">{u.username}</div>
                                      </div>
                                    </div>
                                  </td>
                                  <td className="py-3 px-4 text-text-secondary font-mono text-xs">
                                    {u.mobile || '—'}
                                  </td>
                                  <td className="py-3 px-4">
                                    <Badge variant={role.variant}>{role.label}</Badge>
                                  </td>
                                  <td className="py-3 px-4 text-text-secondary text-xs">
                                    {u.branch_name || <span className="text-text-muted">—</span>}
                                  </td>
                                  <td className="py-3 px-4">
                                    <Badge variant={u.is_active ? 'success' : 'muted'}>
                                      {u.is_active ? 'فعال' : 'غیرفعال'}
                                    </Badge>
                                  </td>
                                  <td className="py-3 px-2">
                                    <ActionMenu items={getUserMenu(u)} />
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>

          {/* کاربران شخصی */}
          {filteredPersonal.length > 0 && (
            <Card>
              <button
                onClick={() => setShowPersonal(!showPersonal)}
                className="w-full flex items-center justify-between gap-3 p-1 hover:bg-bg-hover rounded-field transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-field bg-info/10 flex items-center justify-center">
                    <UsersIcon size={18} className="text-info" />
                  </div>
                  <div className="text-right">
                    <div className="font-medium text-text-primary">مشتریان شخصی</div>
                    <div className="text-[10px] text-text-muted">کاربران خارج از شرکت‌ها</div>
                  </div>
                  <Badge variant="info">{filteredPersonal.length} کاربر</Badge>
                </div>
                <div className="p-1 text-text-muted">
                  {showPersonal ? <ChevronDown size={18} /> : <ChevronLeft size={18} />}
                </div>
              </button>

              {showPersonal && (
                <div className="mt-4 pt-4 border-t border-border-base">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border-base">
                          <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">نام</th>
                          <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">تماس</th>
                          <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">نقش</th>
                          <th className="text-right py-2 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                          <th className="w-12"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredPersonal.map((u) => {
                          const role = roleMap[u.role];
                          return (
                            <tr key={u.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                              <td className="py-3 px-4">
                                <div className="flex items-center gap-3">
                                  <div className="w-8 h-8 rounded-full bg-info/20 flex items-center justify-center text-info font-bold text-xs">
                                    {u.first_name?.[0] || u.username[0]}
                                  </div>
                                  <div>
                                    <div className="font-medium text-text-primary text-xs">
                                      {u.full_name || u.username}
                                    </div>
                                    <div className="text-[10px] text-text-muted font-mono">{u.username}</div>
                                  </div>
                                </div>
                              </td>
                              <td className="py-3 px-4 text-text-secondary font-mono text-xs">
                                {u.mobile || '—'}
                              </td>
                              <td className="py-3 px-4"><Badge variant={role.variant}>{role.label}</Badge></td>
                              <td className="py-3 px-4">
                                <Badge variant={u.is_active ? 'success' : 'muted'}>
                                  {u.is_active ? 'فعال' : 'غیرفعال'}
                                </Badge>
                              </td>
                              <td className="py-3 px-2">
                                <ActionMenu items={getUserMenu(u)} />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Card>
          )}
        </>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="افزودن کاربر"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>انصراف</Button>
            <Button>ذخیره</Button>
          </>
        }
      >
        <div className="space-y-5">

          <div>
            <h4 className="text-xs font-medium text-text-muted mb-3">اطلاعات ورود</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="نام کاربری"
                placeholder="مثلاً etminan"
                autoComplete="off"
                required
              />
              <Input
                type="password"
                label="رمز عبور"
                placeholder="حداقل ۸ کاراکتر"
                autoComplete="new-password"
                required
              />
            </div>
          </div>

          <div className="border-t border-border-base" />

          <div>
            <h4 className="text-xs font-medium text-text-muted mb-3">اطلاعات شخصی</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input label="نام" />
              <Input label="نام خانوادگی" />
              <Input label="ایمیل" />
              <Input label="موبایل" />
            </div>
          </div>

          <div className="border-t border-border-base" />

          <div>
            <h4 className="text-xs font-medium text-text-muted mb-3">نقش و دسترسی</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-text-secondary mb-2">نقش</label>
                <select className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-brand-500">
                  <option value="branch_manager">مدیر شعبه</option>
                  {isSiteAdmin && <option value="main_user">مدیر شرکت</option>}
                  {isSiteAdmin && <option value="personal_user">کاربر شخصی</option>}
                </select>
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-2">شرکت</label>
                <select className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-brand-500">
                  {(organizations || []).map((o) => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

        </div>
      </Modal>

    </div>
  );
}