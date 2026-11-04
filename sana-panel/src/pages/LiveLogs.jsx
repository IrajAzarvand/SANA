import { useState, useEffect, useRef } from 'react';
import { Terminal, Radio, Pause, Play, Trash2, ShieldCheck } from 'lucide-react';
import apiClient from '../api/client';
import { useAuth } from '../context/AuthContext';

function LiveTerminal({ streamName, title, description, icon: Icon, accent }) {
  const [running, setRunning] = useState(true);
  const [status, setStatus] = useState('connecting');
  const [lines, setLines] = useState([]);
  const [error, setError] = useState('');
  const bodyRef = useRef(null);

  useEffect(() => {
    if (!running) return undefined;
    const controller = new AbortController();
    let cancelled = false;
    const connect = async () => {
      try {
        const token = localStorage.getItem('sana_access_token');
        const response = await fetch(`${apiClient.defaults.baseURL}/gps-monitor/logs/${streamName}/`, {
          headers: token ? { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' } : { Accept: 'text/event-stream' },
          signal: controller.signal,
        });
        if (!response.ok) {
          const detail = response.status === 403
            ? 'دسترسی فقط برای ادمین کل سایت مجاز است.'
            : response.status === 401
              ? 'نشست شما منقضی شده است؛ دوباره وارد شوید.'
              : `خطای سرور: ${response.status}`;
          throw new Error(detail);
        }
        if (!response.body) throw new Error('مرورگر از دریافت زنده پشتیبانی نمی‌کند.');
        setStatus('live');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const event of events) {
            const dataLine = event.split('\n').find((line) => line.startsWith('data: '));
            if (!dataLine) continue;
            try {
              const payload = JSON.parse(dataLine.slice(6));
              if (payload.line) {
                setLines((previous) => [...previous, { id: `${Date.now()}-${Math.random()}`, text: payload.line }].slice(-250));
              }
            } catch {
              // Ignore incomplete or malformed server-sent events.
            }
          }
        }
        if (!cancelled) setStatus('disconnected');
      } catch (err) {
        if (err.name !== 'AbortError' && !cancelled) {
          setError(err.message || 'اتصال برقرار نشد.');
          setStatus('error');
        }
      }
    };
    connect();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [running, streamName]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [lines]);

  const displayStatus = running ? status : 'paused';
  const statusLabel = displayStatus === 'live' ? 'زنده' : displayStatus === 'connecting' ? 'در حال اتصال' : displayStatus === 'paused' ? 'متوقف' : displayStatus === 'error' ? 'خطا' : 'قطع اتصال';

  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border-base p-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${accent}`}>
            <Icon size={19} />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-text-primary">{title}</h3>
            <p className="mt-1 text-xs leading-5 text-text-muted">{description}</p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${displayStatus === 'live' ? 'bg-emerald-500/10 text-emerald-600' : displayStatus === 'error' ? 'bg-danger/10 text-danger' : 'bg-bg-base text-text-muted'}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${displayStatus === 'live' ? 'animate-pulse bg-emerald-500' : displayStatus === 'error' ? 'bg-danger' : 'bg-text-muted'}`} />
          {statusLabel}
        </span>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 bg-[#111827] px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400/90" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/90" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/90" />
          <span className="mr-2 font-mono">sana@server:~</span>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setLines([])} title="پاک کردن نمایش" className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white"><Trash2 size={15} /></button>
          <button type="button" onClick={() => {
            if (running) {
              setRunning(false);
            } else {
              setStatus('connecting');
              setError('');
              setRunning(true);
            }
          }} title={running ? 'توقف نمایش زنده' : 'ادامه نمایش زنده'} className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-2.5 py-1.5 text-xs text-slate-100 hover:bg-white/15">
            {running ? <Pause size={13} /> : <Play size={13} />}
            {running ? 'توقف' : 'ادامه'}
          </button>
        </div>
      </div>
      <div ref={bodyRef} aria-live="polite" className="h-72 overflow-auto bg-[#0b1220] p-4 font-mono text-[11px] leading-5 text-emerald-300 sm:h-80 sm:text-xs">
        {lines.length === 0 && !error && (
          <div className="text-slate-500">
            <p>{running ? 'در انتظار دریافت لاگ...' : 'نمایش متوقف شده است.'}</p>
            <p className="mt-1 text-slate-600">$ {streamName === 'service' ? 'journalctl -u sana-gps -f' : 'sudo /usr/local/sbin/sana-gps-network-capture'}</p>
          </div>
        )}
        {error && <p className="mb-2 whitespace-pre-wrap text-rose-300">خطا: {error}</p>}
        {lines.map((line) => (
          <div key={line.id} className="grid grid-cols-[auto_1fr] gap-2 break-words">
            <span className="select-none text-slate-600">$</span>
            <span className="whitespace-pre-wrap">{line.text}</span>
          </div>
        ))}
        {displayStatus === 'live' && <span className="inline-block h-3.5 w-1.5 animate-pulse bg-emerald-400 align-middle" />}
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-border-base px-4 py-2 text-[11px] text-text-muted">
        <span>{lines.length} خط اخیر در نمایش</span>
        <span className="inline-flex items-center gap-1"><ShieldCheck size={12} /> فقط خواندنی</span>
      </div>
    </section>
  );
}

function AdminGPSMonitor() {
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-brand-500/20 bg-brand-500/5 px-3 py-1 text-xs font-medium text-brand-600">
            <ShieldCheck size={14} /> ویژه ادمین کل سایت
          </div>
          <h2 className="text-base font-semibold text-text-primary sm:text-lg">مانیتورینگ زنده GPS</h2>
          <p className="mt-0.5 max-w-2xl text-[11px] leading-5 text-text-muted sm:text-xs">لاگ سرویس و ترافیک شبکه را از یک صفحه بررسی کن. این بخش فقط خواندنی است و هیچ دستوری برای تغییر تنظیمات یا وضعیت دستگاه اجرا نمی‌کند.</p>
        </div>
        
      </div>
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <LiveTerminal streamName="service" title="لاگ زنده سرویس sana-gps" description="رویدادهای systemd، همگام‌سازی Traccar و خطاهای سرویس" icon={Terminal} accent="bg-sky-500/10 text-sky-500" />
        <LiveTerminal streamName="network" title="ترافیک زنده شبکه" description="نمایش ترافیک شبکه از طریق ابزار تشخیصی محدودشده سرور" icon={Radio} accent="bg-emerald-500/10 text-emerald-500" />
      </div>
    </section>
  );
}

export default function LiveLogs() {
  const { isSiteAdmin } = useAuth();

  if (!isSiteAdmin) {
    return (
      <div className="space-y-2">
        <h1 className="text-base font-semibold text-text-primary sm:text-lg">لاگ زنده</h1>
        <p className="text-sm text-text-muted">این بخش فقط برای ادمین کل سایت در دسترس است.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-base font-semibold text-text-primary sm:text-lg">لاگ زنده</h1>
        <p className="mt-0.5 text-[11px] text-text-muted sm:text-xs">مانیتورینگ زنده سرویس GPS و ترافیک شبکه</p>
      </header>
      <AdminGPSMonitor />
    </div>
  );
}
