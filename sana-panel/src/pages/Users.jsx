import { useState, useMemo, useCallback } from 'react';
import { Search, Plus, Users as UsersIcon, Pencil, UserX, ChevronDown, ChevronLeft, Building2 } from 'lucide-react';
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
import { organizationsAPI, branchesAPI } from '../api/services/organizations';
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
  const [showArchived, setShowArchived] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formError, setFormError] = useState('');
  const emptyForm = { username: '', password: '', first_name: '', last_name: '', email: '', mobile: '', role: 'branch_manager', account_type: 'organization', organization: '', branch: '' };
  const [form, setForm] = useState(emptyForm);

  const { user: currentUser, isSiteAdmin, isMainUser } = useAuth();
  const canManageUsers = isSiteAdmin || isMainUser;

  // دریافت کاربران از API
  const fetchUsers = useCallback(async () => {
    const result = await usersAPI.list(showArchived ? { archived: true } : { archived: false });
    // DRF pagination ممکنه برگردونه { count, next, previous, results }
    return Array.isArray(result) ? result : result.results || [];
  }, [showArchived]);

  const fetchOrgs = useCallback(async () => {
    try {
      const result = await organizationsAPI.list();
      return Array.isArray(result) ? result : result.results || [];
    } catch {
      return [];
    }
  }, []);

  const { data: users, loading: usersLoading, error: usersError, refetch: refetchUsers } =
    useApi(fetchUsers, [showArchived]);

  const { data: organizations } = useApi(fetchOrgs, []);
  const fetchBranches = useCallback(async () => {
    const result = await branchesAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);
  const { data: branches } = useApi(fetchBranches, []);

  // گروه‌بندی کاربران سازمانی بر اساس organization
  const groupedCompanies = useMemo(() => {
    if (!users) return [];

    const orgUsers = users.filter((u) => u.account_type === 'organization');
    const map = new Map();
    const branchById = new Map((branches || []).map((branch) => [branch.id, branch]));

    orgUsers.forEach((u) => {
      // Older branch-manager accounts may have a null organization_id while
      // their branch still provides an authoritative organization link.
      const branch = branchById.get(u.branch);
      const orgId = u.organization || branch?.organization || `legacy-branch-${u.branch || u.id}`;
      const orgName = u.organization_name || branch?.organization_name || 'بدون سازمان';
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
  }, [users, branches]);

  // حساب‌های مدیریتی سایت (فقط برای مدیر سایت)
  const adminUsers = useMemo(() => {
    if (!isSiteAdmin || !users) return [];
    return users.filter((u) => u.account_type === 'admin');
  }, [users, isSiteAdmin]);

  const filteredAdmins = useMemo(() => {
    if (!search) return adminUsers;
    return adminUsers.filter((u) =>
      `${u.first_name} ${u.last_name}`.includes(search) ||
      u.username.includes(search) ||
      (u.mobile && u.mobile.includes(search))
    );
  }, [adminUsers, search]);

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
      if (!user.archived_at) {
        items.push({
          label: 'ویرایش',
          icon: Pencil,
          onClick: () => { setEditingUser(user); setForm({ ...emptyForm, ...user, password: '', organization: user.organization || '', branch: user.branch || '' }); setFormError(''); setModalOpen(true); },
        });
      }
      if (user.id === currentUser?.id) return items;
      if (user.archived_at) {
        items.push({
          label: 'بازیابی کاربر',
          icon: UserX,
          onClick: async () => { try { await usersAPI.restore(user.id); await refetchUsers(); } catch (error) { window.alert(error?.response?.data?.detail || 'بازیابی انجام نشد.'); } },
        });
      } else {
        items.push({
          label: user.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی',
          icon: UserX,
          onClick: async () => { try { await usersAPI.update(user.id, { is_active: !user.is_active }); await refetchUsers(); } catch (error) { window.alert(error?.response?.data?.detail || 'تغییر وضعیت انجام نشد.'); } },
        });
        items.push({
          label: 'بایگانی کاربر',
          icon: UserX,
          onClick: async () => { if (!window.confirm('این کاربر بایگانی شود؟ دسترسی ورود او قطع می‌شود، اما سوابقش باقی می‌ماند.')) return; try { await usersAPI.archive(user.id); await refetchUsers(); } catch (error) { window.alert(error?.response?.data?.detail || 'بایگانی انجام نشد.'); } },
        });
      }
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
        actions={canManageUsers ? <Button icon={Plus} onClick={() => { setEditingUser(null); setForm(emptyForm); setFormError(''); setModalOpen(true); }}>افزودن کاربر</Button> : null}
      />

      {canManageUsers && <div className="flex justify-end"><Button size="sm" variant="secondary" onClick={() => setShowArchived((value) => !value)}>{showArchived ? 'نمایش کاربران فعال' : 'نمایش کاربران بایگانی‌شده'}</Button></div>}

      <Card>
        <Input
          icon={Search}
          placeholder="جستجوی نام، ایمیل یا نام شرکت..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Card>

      {/* شرکت‌ها با کاربران درختی */}
      {filteredCompanies.length === 0 && filteredPersonal.length === 0 && filteredAdmins.length === 0 ? (
        <Card>
          <div className="py-12 text-center">
            <UsersIcon size={40} className="text-text-muted mx-auto mb-3" />
            <p className="text-sm text-text-muted">کاربری یافت نشد</p>
          </div>
        </Card>
      ) : (
        <>
          {filteredAdmins.length > 0 && (
            <Card title="ادمین‌های سایت">
              <div className="divide-y divide-border-base">
                {filteredAdmins.map((u) => (
                  <div key={u.id} className="flex items-center justify-between gap-3 py-3">
                    <div>
                      <div className="text-sm font-medium text-text-primary">{u.full_name || u.username}</div>
                      <div className="mt-1 font-mono text-[10px] text-text-muted">{u.username}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant={u.is_active ? 'success' : 'muted'}>{u.is_active ? 'فعال' : 'غیرفعال'}</Badge>
                      <ActionMenu items={getUserMenu(u)} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
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
                      <div className="grid grid-cols-1 gap-3 sm:hidden">
                        {company.users.map((u) => {
                          const role = roleMap[u.role] || roleMap.personal_user;
                          return (
                            <article key={u.id} className="rounded-card border border-border-base bg-bg-base p-3">
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="font-medium text-text-primary">{u.full_name || u.username}</div>
                                  <div className="mt-1 font-mono text-xs text-text-muted">{u.username}</div>
                                </div>
                                <ActionMenu items={getUserMenu(u)} />
                              </div>
                              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-border-base pt-3 text-xs">
                                <div><div className="text-text-muted">تماس</div><div className="mt-1 font-mono text-text-primary">{u.mobile || '—'}</div></div>
                                <div><div className="text-text-muted">نقش</div><div className="mt-1"><Badge variant={role.variant}>{role.label}</Badge></div></div>
                                <div><div className="text-text-muted">شعبه</div><div className="mt-1 text-text-primary">{u.branch_name || '—'}</div></div>
                                <div><div className="text-text-muted">وضعیت</div><div className="mt-1"><Badge variant={u.is_active ? 'success' : 'muted'}>{u.is_active ? 'فعال' : 'غیرفعال'}</Badge></div></div>
                              </div>
                            </article>
                          );
                        })}
                      </div>
                      <div className="hidden overflow-x-auto sm:block">
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
                  <div className="grid grid-cols-1 gap-3 sm:hidden">
                    {filteredPersonal.map((u) => {
                      const role = roleMap[u.role] || roleMap.personal_user;
                      return (
                        <article key={u.id} className="rounded-card border border-border-base bg-bg-base p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="font-medium text-text-primary">{u.full_name || u.username}</div>
                              <div className="mt-1 font-mono text-xs text-text-muted">{u.username}</div>
                            </div>
                            <ActionMenu items={getUserMenu(u)} />
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-3 border-t border-border-base pt-3 text-xs">
                            <div><div className="text-text-muted">تماس</div><div className="mt-1 font-mono text-text-primary">{u.mobile || '—'}</div></div>
                            <div><div className="text-text-muted">نقش</div><div className="mt-1"><Badge variant={role.variant}>{role.label}</Badge></div></div>
                            <div><div className="text-text-muted">وضعیت</div><div className="mt-1"><Badge variant={u.is_active ? 'success' : 'muted'}>{u.is_active ? 'فعال' : 'غیرفعال'}</Badge></div></div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                  <div className="hidden overflow-x-auto sm:block">
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
        onClose={() => { setModalOpen(false); setEditingUser(null); }}
        title={editingUser ? 'ویرایش کاربر' : 'افزودن کاربر'}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => { setModalOpen(false); setEditingUser(null); }}>انصراف</Button>
            <Button onClick={async () => {
              setFormError('');
              try {
                const payload = {
                  ...(editingUser ? {} : { username: form.username, password: form.password }),
                  first_name: form.first_name,
                  last_name: form.last_name,
                  email: form.email,
                  mobile: form.mobile,
                  branch: form.branch ? Number(form.branch) : null,
                };
                if (!editingUser) {
                  payload.role = isSiteAdmin ? form.role : 'branch_manager';
                  payload.account_type = isSiteAdmin ? (form.role === 'site_admin' ? 'admin' : form.role === 'personal_user' ? 'personal' : 'organization') : 'organization';
                  if (isSiteAdmin) payload.organization = form.organization ? Number(form.organization) : null;
                } else if (isSiteAdmin) {
                  payload.role = form.role;
                  payload.account_type = form.role === 'site_admin' ? 'admin' : form.role === 'personal_user' ? 'personal' : 'organization';
                  payload.organization = form.organization ? Number(form.organization) : null;
                }
                if (editingUser) await usersAPI.update(editingUser.id, payload);
                else await usersAPI.create(payload);
                setModalOpen(false);
                setEditingUser(null);
                await refetchUsers();
              } catch (error) {
                const data = error?.response?.data;
                setFormError(data ? Object.values(data).flat().join(' ') : 'ذخیره اطلاعات انجام نشد.');
              }
            }}>ذخیره</Button>
          </>
        }
      >
        <div className="space-y-5">
          {formError && <div className="rounded-field border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{formError}</div>}
          {!editingUser && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input label="نام کاربری" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} required />
              <Input type="password" label="رمز عبور" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} required />
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="نام" value={form.first_name || ''} onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))} />
            <Input label="نام خانوادگی" value={form.last_name || ''} onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))} />
            <Input label="ایمیل" value={form.email || ''} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            <Input label="موبایل" value={form.mobile || ''} onChange={(e) => setForm((f) => ({ ...f, mobile: e.target.value }))} />
          </div>
          {isSiteAdmin && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-text-secondary mb-2">نقش</label>
                <select value={form.role || 'branch_manager'} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value, account_type: e.target.value === 'site_admin' ? 'admin' : e.target.value === 'personal_user' ? 'personal' : 'organization', organization: e.target.value === 'personal_user' || e.target.value === 'site_admin' ? '' : f.organization, branch: '' }))} className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary">
                  <option value="site_admin">ادمین کل سایت</option>
                  <option value="main_user">مدیر شرکت</option>
                  <option value="branch_manager">مدیر شعبه</option>
                  <option value="personal_user">کاربر شخصی</option>
                </select>
              </div>
              {form.role !== 'site_admin' && form.role !== 'personal_user' && (
                <div>
                  <label className="block text-sm text-text-secondary mb-2">شرکت</label>
                  <select value={form.organization || ''} onChange={(e) => setForm((f) => ({ ...f, organization: e.target.value, branch: '' }))} className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary">
                    <option value="">انتخاب شرکت</option>
                    {(organizations || []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                  </select>
                </div>
              )}
            </div>
          )}
          {(form.role === 'branch_manager' || (!isSiteAdmin && !editingUser)) && (
            <div>
              <label className="block text-sm text-text-secondary mb-2">شعبه</label>
              <select value={form.branch || ''} onChange={(e) => setForm((f) => ({ ...f, branch: e.target.value }))} className="w-full bg-bg-base border border-border-base rounded-field px-4 py-2.5 text-sm text-text-primary">
                <option value="">انتخاب شعبه</option>
                {(branches || []).filter((b) => !form.organization || String(b.organization) === String(form.organization)).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
          )}
        </div>
      </Modal>

    </div>
  );
}