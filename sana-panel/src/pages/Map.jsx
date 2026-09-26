import { useState, useMemo, useEffect } from 'react';
import {
  Search, Navigation, MapPin, Gauge, Fuel,
  Route, Clock, Cpu, ChevronLeft, X,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Badge from '../components/Badge';
import Input from '../components/Input';
import LeafletMap from '../components/LeafletMap';
import {
  vehiclesOnMap,
  cityCenters,
  allIranCenter,
  mapStatusColors,
} from '../data/mapData';
import { getMarkerIcon } from '../data/markerIcons';
import { useAuth } from '../context/AuthContext';

const companiesList = [
  { value: '', label: 'همه شرکت‌ها' },
  { value: 'company-1', label: 'شرکت حمل و نقل نمونه' },
  { value: 'company-2', label: 'پخش مواد غذایی آریا' },
  { value: 'company-3', label: 'لجستیک پارس' },
];

const branchesList = [
  { value: '', label: 'همه شعبه‌ها' },
  { value: 'tehran', label: 'تهران' },
  { value: 'isfahan', label: 'اصفهان' },
  { value: 'shiraz', label: 'شیراز' },
  { value: 'tabriz', label: 'تبریز' },
];

export default function Map() {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [filterCompany, setFilterCompany] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [showPath, setShowPath] = useState(null);

  const { isSiteAdmin, isMainUser, isBranchManager, isPersonal, user } = useAuth();

  // منطق فیلترها بر اساس نقش:
  // - ادمین: فیلتر شرکت
  // - مدیر شرکت: فیلتر شعبه
  // - مدیر شعبه و شخصی: بدون فیلتر

  const mapView = useMemo(() => {
    // مدیر شرکت: اگه شعبه انتخاب شد، برو به اون شعبه
    if (isMainUser && filterBranch && cityCenters[filterBranch]) {
      const c = cityCenters[filterBranch];
      return { center: [c.lat, c.lng], zoom: c.zoom, fitAll: false };
    }
    // بقیه: همه ایران
    return {
      center: [allIranCenter.lat, allIranCenter.lng],
      zoom: allIranCenter.zoom,
      fitAll: false,
    };
  }, [isMainUser, filterBranch]);

  const filtered = useMemo(() => {
    let list = vehiclesOnMap;

    // مدیر شعبه: فقط خودروهای شعبه خودش
    if (isBranchManager && user?.branch) {
      const branchMap = {
        'تهران': 'tehran',
        'اصفهان': 'isfahan',
        'شیراز': 'shiraz',
        'تبریز': 'tabriz',
      };
      const bv = branchMap[user.branch.name] || '';
      list = list.filter((v) => v.branch === bv);
    }

    // مشتری شخصی: فقط خودروهای خودش
    if (isPersonal) {
      const personalPlates = ['۱۲ب۳۴۵۶۷', '۴۵ج۶۷۸۹۰'];
      list = list.filter((v) => personalPlates.includes(v.plate));
    }

    // فیلترهای دستی
    return list.filter((v) => {
      if (search && !v.plate.includes(search) && !v.driver.includes(search)) return false;
      if (filterStatus && v.status !== filterStatus) return false;
      if (isMainUser && filterBranch && v.branch !== filterBranch) return false;
      if (isSiteAdmin && filterCompany) {
        // mock: در آینده شرکت واقعی
      }
      return true;
    });
  }, [search, filterStatus, filterBranch, filterCompany, isSiteAdmin, isMainUser, isBranchManager, isPersonal, user]);

  const selected = useMemo(
    () => vehiclesOnMap.find((v) => v.id === selectedId),
    [selectedId]
  );

  const stats = useMemo(() => ({
    total:   filtered.length,
    moving:  filtered.filter((v) => v.status === 'moving').length,
    stopped: filtered.filter((v) => v.status === 'stopped').length,
    offline: filtered.filter((v) => v.status === 'offline').length,
  }), [filtered]);

  useEffect(() => {
    if (selectedId && !filtered.find((v) => v.id === selectedId)) {
      setSelectedId(null);
      setShowPath(null);
    }
  }, [filtered, selectedId]);

  useEffect(() => {
    const handleViewTrip = (e) => {
      const id = e.detail?.id;
      const vehicle = vehiclesOnMap.find((v) => v.id === id);
      if (vehicle && vehicle.todayPath && vehicle.todayPath.length >= 2) {
        setShowPath({
          id: vehicle.id,
          path: vehicle.todayPath,
          color: mapStatusColors[vehicle.status].color,
          vehicle,
        });
        setSelectedId(id);
      } else {
        console.warn('این خودرو مسیری برای نمایش ندارد');
      }
    };
    const handleViewDetail = (e) => {
      const id = e.detail?.id;
      setSelectedId(id);
    };

    window.addEventListener('sana:view-trip', handleViewTrip);
    window.addEventListener('sana:view-detail', handleViewDetail);

    return () => {
      window.removeEventListener('sana:view-trip', handleViewTrip);
      window.removeEventListener('sana:view-detail', handleViewDetail);
    };
  }, []);

  // تعداد فیلترها
  const filterCount = (isSiteAdmin ? 1 : 0) + (isMainUser ? 1 : 0) + 1;

  return (
    <div className="space-y-6">

      <PageHeader
        title="نقشه زنده"
        subtitle={
          isPersonal
            ? 'موقعیت خودروهای من'
            : isBranchManager
              ? `موقعیت خودروهای شعبه ${user?.branch?.name || ''}`
              : 'موقعیت لحظه‌ای خودروهای ناوگان'
        }
      />

      {/* آمار بالا */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatPill label="کل خودروها" value={stats.total}   color="text-text-primary" />
        <StatPill label="در حرکت"    value={stats.moving}  color="text-brand-400"    dot="bg-brand-500" />
        <StatPill label="متوقف"      value={stats.stopped} color="text-warning"      dot="bg-warning"   />
        <StatPill label="آفلاین"     value={stats.offline} color="text-text-muted"   dot="bg-text-muted"/>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 h-[600px]">

        {/* نقشه */}
        <div className="relative bg-bg-elevated border border-border-base rounded-card overflow-hidden">

          {/* پنل اطلاعات مسیر */}
          {showPath && (
            <div
              className="absolute top-4 left-4 right-4 md:right-auto md:w-80 flex items-center justify-between gap-3 bg-bg-elevated/95 backdrop-blur border border-border-base rounded-card px-4 py-3"
              style={{ zIndex: 9999 }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className="w-10 h-10 rounded-field flex items-center justify-center flex-shrink-0"
                  style={{ background: `${showPath.color}20` }}
                >
                  <img
                    src={getMarkerIcon(showPath.vehicle.status)}
                    alt={showPath.vehicle.status}
                    className="w-6 h-6 object-contain"
                  />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-text-primary font-mono truncate">
                    {showPath.vehicle.plate}
                  </div>
                  <div className="text-[10px] text-text-muted truncate">
                    مسیر امروز — {showPath.vehicle.todayDistance} km
                  </div>
                </div>
              </div>
              <button
                onClick={() => setShowPath(null)}
                className="p-1.5 rounded-field text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors flex-shrink-0"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {/* راهنمای رنگ‌ها پایین نقشه */}
          <div
            className="absolute bottom-4 right-4 flex items-center gap-3 bg-bg-elevated/95 backdrop-blur border border-border-base rounded-field px-3 py-2 pointer-events-none"
            style={{ zIndex: 9999 }}
          >
            {Object.entries(mapStatusColors).filter(([k]) => k !== 'alert').map(([key, { color, label }]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                <span className="text-[10px] text-text-secondary">{label}</span>
              </div>
            ))}
          </div>

          <LeafletMap
            vehicles={filtered}
            selectedId={selectedId}
            onSelect={setSelectedId}
            center={mapView.center}
            zoom={mapView.zoom}
            fitAll={mapView.fitAll}
            showPath={showPath}
            onPathClose={() => setShowPath(null)}
          />
        </div>

        {/* سایدبار لیست خودروها */}
        <div className="bg-bg-elevated border border-border-base rounded-card flex flex-col overflow-hidden">

          <div className="p-3 border-b border-border-base space-y-2">
            <Input
              icon={Search}
              placeholder="جستجو..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className={`grid gap-2 ${
              isSiteAdmin ? 'grid-cols-2' :
              isMainUser ? 'grid-cols-2' :
              'grid-cols-1'
            }`}>
              {/* ادمین: فیلتر شرکت */}
              {isSiteAdmin && (
                <select
                  value={filterCompany}
                  onChange={(e) => setFilterCompany(e.target.value)}
                  className="bg-bg-base border border-border-base rounded-field px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-brand-500"
                >
                  {companiesList.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              )}

              {/* مدیر شرکت: فیلتر شعبه */}
              {isMainUser && (
                <select
                  value={filterBranch}
                  onChange={(e) => setFilterBranch(e.target.value)}
                  className="bg-bg-base border border-border-base rounded-field px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-brand-500"
                >
                  {branchesList.map((b) => (
                    <option key={b.value} value={b.value}>{b.label}</option>
                  ))}
                </select>
              )}

              {/* فیلتر وضعیت — برای همه */}
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="bg-bg-base border border-border-base rounded-field px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-brand-500"
              >
                <option value="">همه وضعیت‌ها</option>
                <option value="moving">در حرکت</option>
                <option value="stopped">متوقف</option>
                <option value="offline">آفلاین</option>
              </select>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            {filtered.length === 0 ? (
              <div className="text-center py-12">
                <MapPin size={32} className="text-text-muted mx-auto mb-2" />
                <p className="text-xs text-text-muted">خودرویی یافت نشد</p>
              </div>
            ) : (
              <ul className="space-y-1">
                {filtered.map((v) => {
                  const statusColor = mapStatusColors[v.status];
                  const isSelected = v.id === selectedId;
                  return (
                    <li key={v.id}>
                      <button
                        onClick={() => setSelectedId(v.id)}
                        className={`w-full text-right p-3 rounded-field transition-all border
                          ${isSelected
                            ? 'bg-bg-hover border-brand-500/40'
                            : 'bg-transparent border-transparent hover:bg-bg-hover'
                          }`}
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className="w-10 h-10 rounded-field flex items-center justify-center flex-shrink-0"
                            style={{ background: `${statusColor.color}20` }}
                          >
                            <img
                              src={getMarkerIcon(v.status)}
                              alt={v.status}
                              className="w-6 h-6 object-contain"
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium text-text-primary font-mono">{v.plate}</span>
                              <span className="text-[10px] text-text-muted font-mono">
                                {v.status === 'moving' ? `${v.speed} km/h` : statusColor.label}
                              </span>
                            </div>
                            <div className="text-[10px] text-text-muted truncate mt-0.5">{v.driver}</div>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

        </div>

      </div>

      {/* پنل جزئیات خودرو انتخاب‌شده */}
      {selected && (
        <div className="bg-bg-elevated border border-border-base rounded-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div
                className="w-12 h-12 rounded-field flex items-center justify-center"
                style={{ background: `${mapStatusColors[selected.status].color}20` }}
              >
                <img
                  src={getMarkerIcon(selected.status)}
                  alt={selected.status}
                  className="w-7 h-7 object-contain"
                />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-text-primary font-mono">{selected.plate}</h3>
                  <Badge variant={
                    selected.status === 'moving' ? 'success'
                    : selected.status === 'stopped' ? 'warning'
                    : 'muted'
                  }>
                    {mapStatusColors[selected.status].label}
                  </Badge>
                </div>
                <p className="text-xs text-text-muted mt-0.5">{selected.driver}</p>
              </div>
            </div>
            <button
              onClick={() => setSelectedId(null)}
              className="p-2 rounded-field text-text-muted hover:bg-bg-hover hover:text-text-primary transition-colors"
            >
              <ChevronLeft size={18} className="rotate-180" />
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <DetailItem icon={Gauge}    label="سرعت فعلی"    value={selected.speed} unit="km/h" />
            <DetailItem icon={Route}    label="مسافت امروز"  value={selected.todayDistance} unit="km" />
            <DetailItem icon={Clock}    label="تعداد سفر"    value={selected.todayTrips} unit="سفر" />
            <DetailItem icon={Fuel}     label="سوخت"         value={selected.fuel} unit="%" />
            <DetailItem icon={MapPin}   label="آدرس"         value={selected.address} small />
            <DetailItem icon={Cpu}      label="IMEI"         value={selected.deviceImei} small />
          </div>

          <div className="mt-4 pt-4 border-t border-border-base flex items-center justify-between">
            <span className="text-[10px] text-text-muted">
              آخرین بروزرسانی: {selected.lastUpdate}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (selected.todayPath && selected.todayPath.length >= 2) {
                    setShowPath({
                      id: selected.id,
                      path: selected.todayPath,
                      color: mapStatusColors[selected.status].color,
                      vehicle: selected,
                    });
                  }
                }}
                className="text-xs text-text-secondary hover:text-text-primary px-3 py-1.5 rounded-field hover:bg-bg-hover transition-colors"
              >
                مسیر امروز
              </button>
              <button className="text-xs text-brand-400 hover:text-brand-500 px-3 py-1.5 rounded-field hover:bg-brand-900/30 transition-colors">
                جزئیات کامل
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

/* ============ کامپوننت‌های کمکی ============ */

function StatPill({ label, value, color, dot }) {
  return (
    <div className="bg-bg-elevated border border-border-base rounded-card px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-secondary">{label}</span>
        {dot && <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />}
      </div>
      <div className={`text-2xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  );
}

function DetailItem({ icon: Icon, label, value, unit, small }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="w-8 h-8 rounded-field bg-bg-base flex items-center justify-center flex-shrink-0">
        <Icon size={14} className="text-text-muted" />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] text-text-muted">{label}</div>
        <div className={`${small ? 'text-xs' : 'text-base font-bold font-mono'} text-text-primary mt-0.5 truncate`}>
          {value}
          {unit && <span className="text-[10px] text-text-muted font-normal mr-1">{unit}</span>}
        </div>
      </div>
    </div>
  );
}