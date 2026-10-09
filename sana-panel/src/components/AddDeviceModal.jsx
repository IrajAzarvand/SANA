import { useState } from 'react';
import { Package, Hash } from 'lucide-react';
import Modal from './Modal';
import Button from './Button';
import Input from './Input';
import { devicesAPI } from '../api/services/fleet';

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
  const [form, setForm] = useState({ imei: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      const payload = {
        imei: form.imei.trim(),
        management_status: 'warehouse',
      };

      const created = await devicesAPI.create(payload);

      // پاک کردن فرم
      setForm({ imei: '' });

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

        <div className="bg-info/10 border border-info/30 rounded-field p-3 flex items-start gap-2">
          <Package size={16} className="text-info flex-shrink-0 mt-0.5" />
          <p className="text-xs text-text-secondary leading-relaxed">
            دستگاه با همین IMEI به انبار سانا اضافه می‌شود. پروتکل پس از اولین ارتباط معتبر، در صورت پشتیبانی، به‌صورت خودکار شناسایی می‌شود.
          </p>
        </div>
      </form>

    </Modal>
  );
}