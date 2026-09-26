import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Lock, Eye, EyeOff, AlertCircle } from 'lucide-react';
import SanaLogo from '../components/SanaLogo';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ username: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!form.username || !form.password) {
      setError('نام کاربری و رمز عبور را وارد کنید');
      return;
    }

    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate('/panel/dashboard');
    } catch (err) {
      console.error('Login error:', err);

      if (err.response?.status === 401) {
        setError('نام کاربری یا رمز عبور اشتباه است');
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else if (err.code === 'ERR_NETWORK') {
        setError('ارتباط با سرور برقرار نشد. اتصال اینترنت یا سرور را بررسی کنید.');
      } else {
        setError('خطا در ورود. لطفاً دوباره تلاش کنید.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-bg-base overflow-hidden">

      <div
        className="absolute -top-40 -right-40 w-[500px] h-[500px] rounded-full opacity-[0.07] blur-3xl pointer-events-none"
        style={{ background: 'radial-gradient(circle, #14B8A6 0%, transparent 70%)' }}
      />
      <div
        className="absolute -bottom-40 -left-40 w-[500px] h-[500px] rounded-full opacity-[0.05] blur-3xl pointer-events-none"
        style={{ background: 'radial-gradient(circle, #F59E0B 0%, transparent 70%)' }}
      />

      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(#9BA8C4 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />

      <div className="relative z-10 w-full max-w-[400px] mx-4">

        <div className="bg-bg-elevated border border-border-base rounded-card p-10 shadow-2xl shadow-black/40">

          <div className="flex justify-center mb-8">
            <SanaLogo size="md" showSubtitle />
          </div>

          <div className="text-center mb-8">
            <h1 className="text-xl font-semibold text-text-primary mb-1">
              ورود به پنل
            </h1>
            <p className="text-sm text-text-muted">
              برای ادامه، اطلاعات حساب خود را وارد کنید
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">

            <div>
              <label className="block text-sm text-text-secondary mb-2">
                نام کاربری
              </label>
              <div className="relative">
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">
                  <User size={18} />
                </div>
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  placeholder="نام کاربری خود را وارد کنید"
                  className="w-full bg-bg-base border border-border-base rounded-field
                             pr-11 pl-4 py-3 text-text-primary placeholder:text-text-muted
                             focus:outline-none focus:border-brand-500 focus:ring-2
                             focus:ring-brand-500/20 transition-all duration-200"
                  autoComplete="username"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-text-secondary mb-2">
                رمز عبور
              </label>
              <div className="relative">
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none">
                  <Lock size={18} />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="رمز عبور خود را وارد کنید"
                  className="w-full bg-bg-base border border-border-base rounded-field
                             pr-11 pl-11 py-3 text-text-primary placeholder:text-text-muted
                             focus:outline-none focus:border-brand-500 focus:ring-2
                             focus:ring-brand-500/20 transition-all duration-200"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted
                             hover:text-text-secondary transition-colors"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="w-4 h-4 rounded border-border-base bg-bg-base
                             text-brand-500 focus:ring-brand-500/20 focus:ring-2
                             cursor-pointer accent-brand-500"
                />
                <span className="text-sm text-text-secondary">مرا به خاطر بسپار</span>
              </label>

              <a href="#" className="text-sm text-text-secondary hover:text-brand-400 transition-colors">
                رمز را فراموش کرده‌اید؟
              </a>
            </div>

            {error && (
              <div className="bg-danger/10 border border-danger/30 rounded-field px-4 py-3 flex items-start gap-2">
                <AlertCircle size={16} className="text-danger flex-shrink-0 mt-0.5" />
                <p className="text-sm text-danger">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brand-500 hover:bg-brand-400 active:bg-brand-600
                         disabled:opacity-60 disabled:cursor-not-allowed
                         text-bg-base font-semibold py-3 rounded-field
                         transition-all duration-200 shadow-lg shadow-brand-500/20
                         hover:shadow-brand-500/30"
            >
              {loading ? 'در حال ورود...' : 'ورود'}
            </button>

          </form>

        </div>

        <p className="text-center text-xs text-text-muted mt-6">
          © ۱۴۰۴ سانا — تمامی حقوق محفوظ است
        </p>

      </div>
    </div>
  );
}