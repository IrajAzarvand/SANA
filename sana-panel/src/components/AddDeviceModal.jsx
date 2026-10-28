import { useEffect, useMemo, useState } from 'react';
import { Package, Hash, Phone, ChevronDown, Search } from 'lucide-react';
import Modal from './Modal';
import Button from './Button';
import Input from './Input';
import { devicesAPI, deviceModelsAPI } from '../api/services/fleet';

export function SearchablePicker({
  label, value, options, onChange, placeholder, disabled = false, required = false,
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const selected = options.find((option) => String(option.value) === String(value));

  useEffect(() => {
    if (!isEditing) setQuery(selected?.label || '');
  }, [selected?.value, selected?.label, isEditing]);

  const filteredOptions = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized || normalized === selected?.label?.toLocaleLowerCase()) return options;
    return options.filter((option) =>
      option.label.toLocaleLowerCase().includes(normalized)
    );
  }, [options, query, selected?.label]);

  return (
    <div className="relative">
      {label && (
        <label className="block text-sm text-text-secondary mb-2">
          {label}
          {required && <span className="text-danger mr-1">*</span>}
        </label>
      )}
      <div className="relative">
        <Search size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          value={query}
          onChange={(event) => {
            const nextQuery = event.target.value;
            setQuery(nextQuery);
            setIsEditing(true);
            if (selected && nextQuery !== selected.label) onChange('');
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setOpen(false);
            if (event.key === 'Enter' && open && filteredOptions.length) {
              event.preventDefault();
              setIsEditing(false);
              onChange(String(filteredOptions[0].value));
              setQuery(filteredOptions[0].label);
              setOpen(false);
            }
          }}
          disabled={disabled}
          required={required}
          placeholder={placeholder}
          className="w-full bg-bg-base border border-border-base rounded-field pr-9 pl-10 py-2.5 text-sm text-text-primary focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 disabled:opacity-60 disabled:cursor-not-allowed"
        />
        <ChevronDown size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
      </div>
      {open && !disabled && (
        <div
          role="listbox"
          className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto rounded-field border border-border-base bg-bg-base shadow-lg"
        >
          {filteredOptions.length ? filteredOptions.slice(0, 250).map((option) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={String(option.value) === String(value)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                setIsEditing(false);
                onChange(String(option.value));
                setQuery(option.label);
                setOpen(false);
              }}
              className={`block w-full px-3 py-2 text-right text-sm hover:bg-bg-subtle focus:bg-bg-subtle focus:outline-none ${String(option.value) === String(value) ? 'bg-bg-subtle font-semibold' : ''}`}
            >
              {option.label}
            </button>
          )) : (
            <p className="px-3 py-3 text-sm text-text-muted">موردی با این عبارت پیدا نشد.</p>
          )}
          {filteredOptions.length > 250 && (
            <p className="px-3 py-2 text-xs text-text-muted">برای محدودتر کردن نتایج، عبارت دقیق‌تری بنویسید.</p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Add a device to inventory. Manufacturer and model can be selected or searched by typing.
 */
export default function AddDeviceModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({ imei: '', sim_number: '', manufacturer: '', device_model: '' });
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingModels(true);
    deviceModelsAPI.list()
      .then((data) => {
        if (!cancelled) setModels(Array.isArray(data) ? data : (data.results || []));
      })
      .catch(() => {
        if (!cancelled) setError('دریافت فهرست برندها و مدل‌های Traccar ناموفق بود.');
      })
      .finally(() => {
        if (!cancelled) setLoadingModels(false);
      });
    return () => { cancelled = true; };
  }, [open]);

  const brandOptions = useMemo(() => {
    return [...new Set(models.map((model) => model.manufacturer))]
      .sort((a, b) => a.localeCompare(b))
      .map((manufacturer) => ({ value: manufacturer, label: manufacturer }));
  }, [models]);

  // With a brand selected, limit models to that brand; otherwise show every model
  // so the user can pick by model name first and have the brand filled in.
  const filteredModels = useMemo(() => {
    const list = form.manufacturer
      ? models.filter((model) => model.manufacturer === form.manufacturer)
      : models;
    return list
      .sort((a, b) => {
        const byName = a.name.localeCompare(b.name);
        return byName !== 0 ? byName : a.manufacturer.localeCompare(b.manufacturer);
      })
      .map((model) => ({
        value: String(model.id),
        label: form.manufacturer ? model.name : `${model.name} — ${model.manufacturer}`,
      }));
  }, [models, form.manufacturer]);

  const selectedModel = models.find((model) => String(model.id) === form.device_model);

  const handleBrandChange = (manufacturer) => {
    setForm((prev) => {
      const current = models.find((model) => String(model.id) === prev.device_model);
      const keepModel = current && (!manufacturer || current.manufacturer === manufacturer);
      return {
        ...prev,
        manufacturer,
        device_model: keepModel ? prev.device_model : '',
      };
    });
  };

  const handleModelChange = (device_model) => {
    const model = models.find((item) => String(item.id) === String(device_model));
    setForm((prev) => ({
      ...prev,
      device_model,
      manufacturer: model?.manufacturer || prev.manufacturer,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      const payload = {
        imei: form.imei.trim(),
        sim_number: form.sim_number.trim(),
        management_status: 'warehouse',
      };
      if (form.device_model) payload.device_model = Number(form.device_model);

      const created = await devicesAPI.create(payload);
      setForm({ imei: '', sim_number: '', manufacturer: '', device_model: '' });
      if (onSuccess) onSuccess(created);
      onClose();
    } catch (err) {
      console.error('Error creating device:', err);
      const errData = err.response?.data;
      if (errData) {
        const messages = Object.entries(errData)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v[0] : v}`)
          .join('\n');
        setError(messages);
      } else {
        setError('خطا در ذخیره دستگاه. لطفاً دوباره تلاش کنید.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="افزودن دستگاه به انبار"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            انصراف
          </Button>
          <Button type="submit" form="add-device-modal-form" disabled={saving}>
            {saving ? 'در حال ذخیره...' : 'ذخیره'}
          </Button>
        </>
      }
    >
      <form id="add-device-modal-form" onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-danger/10 border border-danger/30 rounded-field p-3">
            <p className="text-xs text-danger whitespace-pre-line">{error}</p>
          </div>
        )}

        <Input
          label="شناسه دستگاه (IMEI)"
          value={form.imei}
          onChange={(e) => setForm({ ...form, imei: e.target.value })}
          placeholder="IMEI دستگاه"
          icon={Hash}
          required
        />

        <SearchablePicker
          label="برند"
          value={form.manufacturer}
          onChange={handleBrandChange}
          options={brandOptions}
          placeholder={loadingModels ? 'در حال دریافت فهرست...' : 'برای جستجو، نام برند را بنویسید یا از فهرست انتخاب کنید'}
          disabled={loadingModels || !brandOptions.length}
        />

        <SearchablePicker
          label="مدل دستگاه"
          value={form.device_model}
          onChange={handleModelChange}
          options={filteredModels}
          placeholder={loadingModels ? 'در حال دریافت فهرست...' : 'برای جستجو، نام مدل را بنویسید یا از فهرست انتخاب کنید'}
          disabled={loadingModels || !models.length}
        />

        {selectedModel && (
          <div className="rounded-field border border-border-base bg-bg-subtle p-3 space-y-1">
            <p className="text-sm text-text-primary">پورت پیش‌فرض Traccar: <strong>{selectedModel.port ?? 'نامشخص'}</strong></p>
            <p className="text-xs text-text-secondary">پروتکل کاتالوگ: {selectedModel.protocol} · منبع: فهرست رسمی Traccar</p>
            <p className="text-xs text-text-secondary">این پورت، مقدار پیش‌فرض مستندشده است و ممکن است با تنظیمات سرور متفاوت باشد.</p>
          </div>
        )}

        <Input
          label="شماره سیم‌کارت (اختیاری)"
          value={form.sim_number}
          onChange={(e) => setForm({ ...form, sim_number: e.target.value })}
          placeholder="شماره سیم‌کارت را وارد کنید"
          icon={Phone}
          inputMode="tel"
        />

        <div className="bg-info/10 border border-info/30 rounded-field p-3 flex items-start gap-2">
          <Package size={16} className="text-info flex-shrink-0 mt-0.5" />
          <p className="text-xs text-text-secondary leading-relaxed">
            فقط شناسه دستگاه (IMEI) برای ثبت اجباری است. برند و مدل اختیاری‌اند؛ پس از ثبت و زمانی که Traccar مدل معتبر و قابل تطبیقی گزارش کند، سانا آن را تکمیل می‌کند. اگر Traccar مدل را گزارش نکند یا تطبیق مطمئن نباشد، اطلاعات خالی می‌ماند و حدس زده نمی‌شود.
          </p>
        </div>
      </form>
    </Modal>
  );
}
