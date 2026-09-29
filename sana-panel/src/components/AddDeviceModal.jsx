import { useState, useEffect } from 'react';
import { Plus, Package, Hash, Phone, Boxes } from 'lucide-react';
import Modal from './Modal';
import Button from './Button';
import Input from './Input';
import Select from './Select';
import { devicesAPI, deviceModelsAPI } from '../api/services/fleet';
import AddDeviceModelModal from './AddDeviceModelModal';

/**
 * مودال افزودن دستگاه جدید به انبار
 * - هم توی Devices.jsx استفاده می‌شه
 * - هم توی SubscriptionWizard.jsx (Step 4)
 *
 * @param {boolean} open
 * @param {Function} onClose
 * @param {Function} onSuccess - callback با device جدید
 */
export default function AddDeviceModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({
    imei: '',
    device_model: '',
    sim_number: '',
  });
  const [models, setModels] = useState([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [addModelModalOpen, setAddModelModalOpen] = useState(false);

  // لود مدل‌ها وقتی Modal باز می‌شه
  useEffect(() => {
    if (!open) return;

    const fetchModels = async () => {
      setModelsLoading(true);
      try {
        const result = await deviceModelsAPI.list();
        const list = Array.isArray(result) ? result : result.results || [];
        setModels(list);
      } catch (e) {
        console.error('Error fetching models:', e);
      } finally {
        setModelsLoading(false);
      }
    };

    fetchModels();
  }, [open]);

  const handleModelCreated = (createdModel) => {
    setModels((current) => [...current, createdModel]);
    setForm((current) => ({
      ...current,
      device_model: createdModel.id,
    }));
  };

  const modelOptions = models.map((m) => ({
    value: m.id,
    label: `${m.manufacturer} ${m.name}`,
  }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      const payload = {
        imei: form.imei,
        device_model: form.device_model || null,
        sim_number: form.sim_number,
        management_status: 'warehouse',
      };

      const created = await devicesAPI.create(payload);

      // پاک کردن فرم
      setForm({ imei: '', device_model: '', sim_number: '' });

      // کال بک موفقیت
      if (onSuccess) onSuccess(created);

      // بستن Modal
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
          label="IMEI"
          value={form.imei}
          onChange={(e) => setForm({ ...form, imei: e.target.value })}
          placeholder="۱۵ رقم"
          icon={Hash}
          required
        />

        <div>
          <Select
            label="مدل دستگاه"
            placeholder={modelsLoading ? 'در حال بارگذاری...' : 'انتخاب کنید...'}
            value={form.device_model}
            onChange={(e) => setForm({ ...form, device_model: e.target.value })}
            options={modelOptions}
            disabled={modelsLoading}
          />
          <div className="flex items-center justify-between gap-3 mt-2">
            {models.length === 0 && !modelsLoading ? (
              <p className="text-[10px] text-warning">
                هنوز مدلی تعریف نشده است.
              </p>
            ) : (
              <span />
            )}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={Plus}
              onClick={() => setAddModelModalOpen(true)}
            >
              افزودن مدل جدید
            </Button>
          </div>
        </div>

        <Input
          label="شماره SIM"
          value={form.sim_number}
          onChange={(e) => setForm({ ...form, sim_number: e.target.value })}
          placeholder="۰۹xxxxxxxxx"
          icon={Phone}
        />

        <div className="bg-info/10 border border-info/30 rounded-field p-3 flex items-start gap-2">
          <Package size={16} className="text-info flex-shrink-0 mt-0.5" />
          <p className="text-xs text-text-secondary leading-relaxed">
            دستگاه به انبار سانا اضافه می‌شود. بعد از ذخیره، در لیست دستگاه‌های موجود نمایش داده می‌شود.
          </p>
        </div>
      </form>

      <AddDeviceModelModal
        open={addModelModalOpen}
        onClose={() => setAddModelModalOpen(false)}
        onSuccess={handleModelCreated}
      />
    </Modal>
  );
}