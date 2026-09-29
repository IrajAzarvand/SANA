import { useState } from 'react';
import { Boxes } from 'lucide-react';
import Modal from './Modal';
import Button from './Button';
import Input from './Input';
import { deviceModelsAPI } from '../api/services/deviceModels';

export default function AddDeviceModelModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({
    manufacturer: '',
    name: '',
    code: '',
    protocol: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleClose = () => {
    if (saving) return;
    setError('');
    setForm({ manufacturer: '', name: '', code: '', protocol: '' });
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);

    try {
      const created = await deviceModelsAPI.create(form);
      setForm({ manufacturer: '', name: '', code: '', protocol: '' });
      if (onSuccess) onSuccess(created);
      onClose();
    } catch (err) {
      console.error('Error creating device model:', err);
      const errData = err.response?.data;
      if (errData) {
        const messages = Object.entries(errData)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value[0] : value}`)
          .join('\n');
        setError(messages);
      } else {
        setError('خطا در ذخیره مدل دستگاه. لطفاً دوباره تلاش کنید.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="افزودن مدل دستگاه"
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} disabled={saving}>
            انصراف
          </Button>
          <Button type="submit" form="add-device-model-form" disabled={saving}>
            {saving ? 'در حال ذخیره...' : 'ذخیره مدل'}
          </Button>
        </>
      }
    >
      <form id="add-device-model-form" onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="bg-danger/10 border border-danger/30 rounded-field p-3">
            <p className="text-xs text-danger whitespace-pre-line">{error}</p>
          </div>
        )}

        <div className="bg-info/10 border border-info/30 rounded-field p-3 flex items-start gap-2">
          <Boxes size={16} className="text-info flex-shrink-0 mt-0.5" />
          <p className="text-xs text-text-secondary leading-relaxed">
            مدل جدید بعد از ذخیره، بلافاصله در فهرست مدل‌های دستگاه قابل انتخاب خواهد بود.
          </p>
        </div>

        <Input
          label="سازنده"
          value={form.manufacturer}
          onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
          placeholder="مثلاً Teltonika"
          required
        />
        <Input
          label="نام مدل"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="مثلاً FMB920"
          required
        />
        <Input
          label="کد مدل"
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value })}
          placeholder="مثلاً FMB920"
        />
        <Input
          label="پروتکل"
          value={form.protocol}
          onChange={(e) => setForm({ ...form, protocol: e.target.value })}
          placeholder="مثلاً teltonika"
        />
      </form>
    </Modal>
  );
}
