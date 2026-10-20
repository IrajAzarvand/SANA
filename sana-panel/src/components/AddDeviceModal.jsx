import { useEffect, useMemo, useState } from 'react';
import { Package, Hash, Phone } from 'lucide-react';
import Modal from './Modal';
import Button from './Button';
import Input from './Input';
import Select from './Select';
import { devicesAPI, deviceModelsAPI } from '../api/services/fleet';

/**
 * مودال افزودن دستگاه جدید به انبار.
 * برند و مدل فقط از کاتالوگ تأییدشده Traccar انتخاب می‌شوند.
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

  const filteredModels = useMemo(() => {
    return models
      .filter((model) => model.manufacturer === form.manufacturer)
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((model) => ({ value: String(model.id), label: model.name }));
  }, [models, form.manufacturer]);

  const selectedModel = models.find((model) => String(model.id) === form.device_model);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      const payload = {
        imei: form.imei.trim(),
        sim_number: form.sim_number.trim(),
        device_model: Number(form.device_model),
        management_status: 'warehouse',
      };

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
          <Button type="submit" form="add-device-modal-form" disabled={saving || loadingModels || !models.length}>
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

        <Select
          label="برند"
          value={form.manufacturer}
          onChange={(e) => setForm({ ...form, manufacturer: e.target.value, device_model: '' })}
          options={brandOptions}
          placeholder={loadingModels ? 'در حال دریافت فهرست...' : 'برند را انتخاب کنید'}
          required
          disabled={loadingModels || !brandOptions.length}
        />

        <Select
          label="مدل دستگاه"
          value={form.device_model}
          onChange={(e) => setForm({ ...form, device_model: e.target.value })}
          options={filteredModels}
          placeholder={!form.manufacturer ? 'ابتدا برند را انتخاب کنید' : 'مدل را انتخاب کنید'}
          required
          disabled={!form.manufacturer || loadingModels || !filteredModels.length}
        />

        {selectedModel && (
          <div className="rounded-field border border-border-base bg-bg-subtle p-3 space-y-1">
            <p className="text-sm text-text-primary">پورت پیش‌فرض Traccar: <strong>{selectedModel.port ?? 'نامشخص'}</strong></p>
            <p className="text-xs text-text-secondary">پروتکل کاتالوگ: {selectedModel.protocol} · نسخه بررسی‌شده: {selectedModel.traccar_version}</p>
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
            برند و مدل از کاتالوگ ثابت Traccar انتخاب می‌شوند. پروتکل واقعی دستگاه همچنان پس از اولین ارتباط معتبر توسط سرویس دریافت داده شناسایی می‌شود؛ انتخاب مدل به‌تنهایی پروتکل واقعی را تعیین نمی‌کند.
          </p>
        </div>
      </form>
    </Modal>
  );
}
