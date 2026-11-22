import { useState, useMemo, useCallback } from 'react';

async function fetchAllPages(listFn, params = {}) {
  const results = [];
  let page = Number(params.page) || 1;
  const visitedPages = new Set();

  for (let pageCount = 0; pageCount < 1000; pageCount += 1) {
    if (visitedPages.has(page)) {
      throw new Error('Pagination loop detected while loading organization details');
    }
    visitedPages.add(page);

    const response = await listFn({ ...params, page });
    if (Array.isArray(response)) {
      results.push(...response);
      return results;
    }

    const pageResults = Array.isArray(response?.results) ? response.results : [];
    results.push(...pageResults);
    if (!response?.next) return results;

    let nextPage = page + 1;
    try {
      const nextUrl = new URL(response.next, window.location.origin);
      const parsedPage = Number(nextUrl.searchParams.get('page'));
      if (Number.isInteger(parsedPage) && parsedPage > 0) nextPage = parsedPage;
    } catch {
      // Fall back to sequential page numbers for an unparseable next link.
    }
    page = nextPage;
  }

  throw new Error('Organization details pagination exceeded the safety limit');
}
import { Search, Plus, Building2, Pencil, Trash2, Eye } from 'lucide-react';
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
import { organizationsAPI, branchesAPI } from '../api/services/organizations';
import { subscriptionsAPI } from '../api/services/subscriptions';
import { usersAPI, vehiclesAPI, devicesAPI } from '../api/services/fleet';
import { useApi } from '../hooks/useApi';

export default function Companies() {
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingOrganization, setEditingOrganization] = useState(null);
  const [detailOrganization, setDetailOrganization] = useState(null);
  const [detailBranches, setDetailBranches] = useState([]);
  const [detailSubscriptions, setDetailSubscriptions] = useState([]);
  const [detailUsers, setDetailUsers] = useState([]);
  const [detailVehicles, setDetailVehicles] = useState([]);
  const [detailDevices, setDetailDevices] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deleteOrganization, setDeleteOrganization] = useState(null);
  const [deleteName, setDeleteName] = useState('');
  const [form, setForm] = useState({
    name: '', code: '', registration_number: '', economy_code: '',
    phone: '', email: '', address: '', status: 'active',
  });
  const [saving, setSaving] = useState(false);

  const { isSiteAdmin } = useAuth();

  // دریافت سازمان‌ها از API
  const fetchOrganizations = useCallback(async () => {
    const result = await organizationsAPI.list();
    return Array.isArray(result) ? result : result.results || [];
  }, []);

  const { data: organizations, loading, error, refetch } =
    useApi(fetchOrganizations, []);

  // فیلتر
  const filtered = useMemo(() => {
    if (!organizations) return [];
    if (!search) return organizations;
    return organizations.filter((o) =>
      o.name.includes(search) ||
      o.code.includes(search) ||
      (o.phone && o.phone.includes(search))
    );
  }, [organizations, search]);

  const closeCompanyModal = () => {
    setModalOpen(false);
    setEditingOrganization(null);
    setForm({ name: '', code: '', registration_number: '', economy_code: '', phone: '', email: '', address: '', status: 'active' });
  };

  // افزودن سازمان
  const handleAdd = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editingOrganization) {
        await organizationsAPI.update(editingOrganization.id, form);
      } else {
        await organizationsAPI.create(form);
      }
      setModalOpen(false);
      setEditingOrganization(null);
      setForm({
        name: '', code: '', registration_number: '', economy_code: '',
        phone: '', email: '', address: '', status: 'active',
      });
      refetch();
    } catch (err) {
      console.error('Error adding organization:', err);
      alert('خطا در افزودن شرکت: ' + (err.response?.data?.code?.[0] || 'لطفاً دوباره تلاش کنید'));
    } finally {
      setSaving(false);
    }
  };

  // حذف سازمان با تأیید آگاهانه
  const handleDelete = async (org) => {
    setDeleteName('');
    try {
      const details = await organizationsAPI.get(org.id);
      setDeleteOrganization(details);
    } catch (err) {
      console.error('Unable to load organization deletion details:', err);
      setDeleteOrganization(null);
      alert('دریافت اطلاعات وابستگی‌های شرکت ناموفق بود. برای جلوگیری از حذف با اطلاعات ناقص، حذف انجام نشد. لطفاً دوباره تلاش کنید.');
    }
  };

  const confirmDeleteOrganization = async () => {
    if (!deleteOrganization || deleteName.trim() !== deleteOrganization.name) return;
    try {
      await organizationsAPI.delete(deleteOrganization.id);
      setDeleteOrganization(null);
      setDeleteName('');
      refetch();
    } catch (err) {
      console.error('Error deleting organization:', err);
      alert('خطا در حذف شرکت. ممکن است وابستگی‌ها یا مجوزها مانع حذف شده باشند.');
    }
  };

  const handleViewOrganization = async (org) => {
    setDetailOrganization(org);
    setDetailLoading(true);
    setDetailBranches([]);
    setDetailSubscriptions([]);
    setDetailUsers([]);
    setDetailVehicles([]);
    setDetailDevices([]);
    try {
      const [details, branchList, subscriptionList, userList, vehicleList, deviceList] = await Promise.all([
        organizationsAPI.get(org.id),
        fetchAllPages(branchesAPI.list, { organization: org.id }),
        fetchAllPages(subscriptionsAPI.list, { organization: org.id }),
        fetchAllPages(usersAPI.list, { organization: org.id }),
        fetchAllPages(vehiclesAPI.list, { organization: org.id }),
        fetchAllPages(devicesAPI.list, { organization: org.id }),
      ]);
      setDetailOrganization(details);
      setDetailBranches(branchList.filter((branch) => Number(branch.organization) === Number(org.id)));
      setDetailSubscriptions(subscriptionList);
      setDetailUsers(userList);
      setDetailVehicles(vehicleList);
      setDetailDevices(deviceList);
    } catch (err) {
      console.error('Error loading organization details:', err);
      alert('دریافت جزئیات شرکت ناموفق بود.');
    } finally {
      setDetailLoading(false);
    }
  };

  const getMenuItems = (org) => {
    const items = [];

    if (isSiteAdmin) {
      items.push({
        label: 'ویرایش',
        icon: Pencil,
        onClick: () => {
          setEditingOrganization(org);
          setForm({
            name: org.name || '',
            code: org.code || '',
            registration_number: org.registration_number || '',
            economy_code: org.economy_code || '',
            phone: org.phone || '',
            email: org.email || '',
            address: org.address || '',
            status: org.status || 'active',
          });
          setModalOpen(true);
        },
      });
      items.push({
        label: 'جزئیات',
        icon: Eye,
        onClick: () => handleViewOrganization(org),
      });
      items.push({
        label: 'حذف',
        icon: Trash2,
        variant: 'danger',
        onClick: () => handleDelete(org),
      });
    } else {
      items.push({
        label: 'مشاهده جزئیات',
        icon: Eye,
        onClick: () => handleViewOrganization(org),
      });
    }

    return items;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="شرکت‌ها" subtitle="در حال بارگذاری..." />
        <Card><LoadingSpinner /></Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <PageHeader title="شرکت‌ها" subtitle="خطا در دریافت اطلاعات" />
        <Card><ErrorState error={error} onRetry={refetch} /></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">

      <PageHeader
        title="شرکت‌ها"
        subtitle={`مدیریت شرکت‌های مشتری سامانه سانا — ${filtered.length} شرکت`}
        actions={
          isSiteAdmin ? (
            <Button icon={Plus} onClick={() => {
                setEditingOrganization(null);
                setForm({ name: '', code: '', registration_number: '', economy_code: '', phone: '', email: '', address: '', status: 'active' });
                setModalOpen(true);
              }}>
              افزودن شرکت
            </Button>
          ) : null
        }
      />

      <Card>
        <Input
          icon={Search}
          placeholder="جستجوی نام، کد یا تلفن شرکت..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Card>

      <Card>
        {filtered.length === 0 ? (
          <div className="py-12 text-center">
            <Building2 size={40} className="text-text-muted mx-auto mb-3" />
            <p className="text-sm text-text-muted">شرکتی یافت نشد</p>
          </div>
        ) : (
          <>
          <div className="grid grid-cols-1 gap-3 sm:hidden">
            {filtered.map((c) => (
              <article key={c.id} className="rounded-card border border-border-base bg-bg-base p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-field bg-brand-900/40"><Building2 size={16} className="text-brand-400" /></div>
                    <div className="min-w-0"><div className="font-medium text-text-primary break-words">{c.name}</div><div className="mt-1 font-mono text-xs text-text-muted">{c.code}</div></div>
                  </div>
                  <ActionMenu items={getMenuItems(c)} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 border-t border-border-base pt-3 text-xs">
                  <div><div className="text-text-muted">تلفن</div><div className="mt-1 font-mono text-text-primary">{c.phone || '—'}</div></div>
                  <div><div className="text-text-muted">وضعیت</div><div className="mt-1"><Badge variant={c.status === 'active' ? 'success' : 'muted'}>{c.status === 'active' ? 'فعال' : 'غیرفعال'}</Badge></div></div>
                  <div className="col-span-2"><div className="text-text-muted">منابع</div><div className="mt-1 flex flex-wrap gap-3 text-text-secondary"><span>🏢 {c.branches_count || 0} شعبه</span><span>🚗 {c.vehicles_count || 0} خودرو</span><span>📡 {c.devices_count || 0} دستگاه</span></div></div>
                </div>
              </article>
            ))}
          </div>
          <div className="hidden overflow-x-auto -m-5 sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-base">
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">نام شرکت</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">کد</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">تلفن</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">منابع</th>
                  <th className="text-right py-3 px-4 text-xs font-medium text-text-muted">وضعیت</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id} className="border-b border-border-base last:border-0 hover:bg-bg-hover transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-field bg-brand-900/40 flex items-center justify-center">
                          <Building2 size={16} className="text-brand-400" />
                        </div>
                        <span className="font-medium text-text-primary">{c.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{c.code}</td>
                    <td className="py-3 px-4 text-text-secondary font-mono text-xs">{c.phone || '—'}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3 text-[10px] text-text-muted">
                        <span>🏢 {c.branches_count || 0}</span>
                        <span>🚗 {c.vehicles_count || 0}</span>
                        <span>📡 {c.devices_count || 0}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={c.status === 'active' ? 'success' : 'muted'}>
                        {c.status === 'active' ? 'فعال' : 'غیرفعال'}
                      </Badge>
                    </td>
                    <td className="py-3 px-2">
                      <ActionMenu items={getMenuItems(c)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </Card>

      {/* جزئیات شرکت */}
      <Modal open={Boolean(detailOrganization)} onClose={() => setDetailOrganization(null)} title={detailOrganization ? `جزئیات شرکت: ${detailOrganization.name}` : 'جزئیات شرکت'} size="lg">
        {detailLoading ? <LoadingSpinner /> : detailOrganization && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                ['کد شرکت', detailOrganization.code],
                ['شماره ثبت', detailOrganization.registration_number],
                ['کد اقتصادی', detailOrganization.economy_code],
                ['تلفن', detailOrganization.phone],
                ['ایمیل', detailOrganization.email],
                ['وضعیت', detailOrganization.status === 'active' ? 'فعال' : 'غیرفعال'],
                ['آدرس', detailOrganization.address],
              ].map(([label, value]) => <div key={label} className="rounded-lg border border-border-base p-3"><div className="text-xs text-text-muted">{label}</div><div className="mt-1 text-text-primary break-words">{value || '—'}</div></div>)}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
              {[['شعبه', detailOrganization.branches_count], ['کاربر', detailOrganization.users_count], ['قرارداد', detailOrganization.subscriptions_count], ['خودرو', detailOrganization.vehicles_count], ['دستگاه', detailOrganization.devices_count], ['راننده', detailOrganization.drivers_count], ['نوع خودرو', detailOrganization.vehicle_types_count]].map(([label, count]) => <div key={label} className="rounded-lg bg-bg-base border border-border-base p-3 text-center"><div className="text-text-muted text-xs">{label}</div><div className="mt-1 font-semibold text-text-primary">{count ?? 0}</div></div>)}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-lg border border-border-base p-3">
                <h4 className="font-medium mb-2">کاربران شرکت ({detailOrganization.users_count ?? detailUsers.length}) — نمایش {detailUsers.length} مورد</h4>
                {detailUsers.length ? <ul className="space-y-1 max-h-52 overflow-y-auto">{detailUsers.map((user) => <li key={user.id} className="flex flex-wrap justify-between gap-2 border-b last:border-0 border-border-base py-1"><span>{user.full_name || user.username}</span><span className="text-text-muted">{user.branch_name || user.role || '—'}</span></li>)}</ul> : <p className="text-text-muted">کاربری ثبت نشده است.</p>}
              </div>
              <div className="rounded-lg border border-border-base p-3">
                <h4 className="font-medium mb-2">خودروها ({detailOrganization.vehicles_count ?? detailVehicles.length}) — نمایش {detailVehicles.length} مورد</h4>
                {detailVehicles.length ? <ul className="space-y-1 max-h-52 overflow-y-auto">{detailVehicles.map((vehicle) => <li key={vehicle.id} className="flex flex-wrap justify-between gap-2 border-b last:border-0 border-border-base py-1"><span>{vehicle.plate}</span><span className="text-text-muted">{vehicle.vehicle_type_name || vehicle.branch_name || '—'}</span></li>)}</ul> : <p className="text-text-muted">خودرویی ثبت نشده است.</p>}
              </div>
              <div className="rounded-lg border border-border-base p-3 md:col-span-2">
                <h4 className="font-medium mb-2">دستگاه‌ها ({detailOrganization.devices_count ?? detailDevices.length}) — نمایش {detailDevices.length} مورد</h4>
                {detailDevices.length ? <ul className="space-y-1 max-h-52 overflow-y-auto">{detailDevices.map((device) => <li key={device.id} className="flex flex-wrap justify-between gap-2 border-b last:border-0 border-border-base py-1"><span className="font-mono">{device.imei}</span><span className="text-text-muted">{device.device_model_name || device.device_model_manufacturer || device.vehicle_plate || '—'}</span></li>)}</ul> : <p className="text-text-muted">دستگاهی ثبت نشده است.</p>}
              </div>
            </div>
            <div className="rounded-lg border border-border-base p-3">
              <h4 className="font-medium mb-2">قراردادهای شرکت ({detailOrganization.subscriptions_count ?? detailSubscriptions.length}) — نمایش {detailSubscriptions.length} مورد</h4>
              {detailSubscriptions.length ? <ul className="space-y-1">{detailSubscriptions.map((subscription) => <li key={subscription.id} className="flex flex-wrap justify-between gap-2 border-b last:border-0 border-border-base py-2"><span>{subscription.contract_number}</span><span className="text-text-muted">{subscription.status} · {subscription.end_date || '—'}</span></li>)}</ul> : <p className="text-text-muted">قراردادی ثبت نشده است.</p>}
            </div>
            <div className="rounded-lg border border-border-base p-3">
              <h4 className="font-medium mb-2">شعب شرکت ({detailOrganization.branches_count ?? detailBranches.length}) — نمایش {detailBranches.length} مورد</h4>
              {detailBranches.length ? <ul className="space-y-1">{detailBranches.map((branch) => <li key={branch.id} className="flex justify-between gap-2 border-b last:border-0 border-border-base py-1"><span>{branch.name}</span><span className="text-text-muted">{branch.code}</span></li>)}</ul> : <p className="text-text-muted">شعبه‌ای ثبت نشده است.</p>}
            </div>
            <p className="text-xs text-text-muted">قراردادها و ارتباطات وابسته نیز در صورت حذف شرکت، مطابق روابط دیتابیس تحت تأثیر قرار می‌گیرند.</p>
          </div>
        )}
      </Modal>

      {/* تأیید حذف شرکت */}
      <Modal open={Boolean(deleteOrganization)} onClose={() => { setDeleteOrganization(null); setDeleteName(''); }} title="تأیید حذف فیزیکی شرکت" size="lg">
        {deleteOrganization && (
          <div className="space-y-4">
            <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-sm">
              <p className="font-semibold text-red-500">این عملیات برگشت‌پذیر نیست.</p>
              <p className="mt-2">با حذف «{deleteOrganization.name}»، شعب، قراردادهای سازمانی، خودروها، دستگاه‌ها، انواع خودرو و رانندگان وابسته حذف می‌شوند. کاربران حذف نمی‌شوند، اما ارتباط سازمانی آن‌ها قطع می‌شود. برخی سوابق وابسته نیز حذف یا از ارتباط با شرکت جدا خواهند شد. این عملیات برگشت‌پذیر نیست.</p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-center text-sm">
              {[['شعبه', deleteOrganization.branches_count], ['قرارداد', deleteOrganization.subscriptions_count], ['خودرو', deleteOrganization.vehicles_count], ['دستگاه', deleteOrganization.devices_count], ['راننده', deleteOrganization.drivers_count], ['نوع خودرو', deleteOrganization.vehicle_types_count], ['کاربر', deleteOrganization.users_count]].map(([label, count]) => <div key={label} className="rounded-lg border border-border-base p-3"><div className="text-xs text-text-muted">{label}</div><div className="mt-1 font-semibold">{count ?? '—'}</div></div>)}
            </div>
            <p className="text-sm">برای تأیید، نام شرکت را دقیقاً وارد کنید:</p>
            <Input value={deleteName} onChange={(e) => setDeleteName(e.target.value)} placeholder={deleteOrganization.name} />
          </div>
        )}
        <div className="flex justify-end gap-2 pt-4">
          <Button variant="secondary" onClick={() => { setDeleteOrganization(null); setDeleteName(''); }}>انصراف</Button>
          <Button variant="danger" disabled={!deleteOrganization || deleteName.trim() !== deleteOrganization.name} onClick={confirmDeleteOrganization}>حذف فیزیکی شرکت</Button>
        </div>
      </Modal>

      {/* مودال افزودن */}
      {isSiteAdmin && (
        <Modal
          open={modalOpen}
          onClose={closeCompanyModal}
          title={editingOrganization ? 'ویرایش شرکت' : 'افزودن شرکت'}
          size="lg"
          footer={
            <>
              <Button variant="secondary" onClick={closeCompanyModal} disabled={saving}>
                انصراف
              </Button>
              <Button type="submit" form="add-company-form" disabled={saving}>
                {saving ? 'در حال ذخیره...' : (editingOrganization ? 'ذخیره تغییرات' : 'ذخیره')}
              </Button>
            </>
          }
        >
          <form id="add-company-form" onSubmit={handleAdd} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="نام شرکت"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="نام کامل شرکت"
                required
              />
              <Input
                label="کد شرکت"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="مثلاً SMP-001"
                required
              />
              <Input
                label="شماره ثبت"
                value={form.registration_number}
                onChange={(e) => setForm({ ...form, registration_number: e.target.value })}
              />
              <Input
                label="کد اقتصادی"
                value={form.economy_code}
                onChange={(e) => setForm({ ...form, economy_code: e.target.value })}
              />
              <Input
                label="تلفن"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="۰۲۱-xxxxxxxx"
              />
              <Input
                label="ایمیل"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="info@example.com"
              />
            </div>
            <Input
              label="آدرس"
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="آدرس کامل"
            />
          </form>
        </Modal>
      )}

    </div>
  );
}