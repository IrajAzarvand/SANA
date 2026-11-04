import { useState, useEffect, useRef } from 'react';
import { Terminal, Pause, Play, Trash2, ShieldCheck, ChevronDown } from 'lucide-react';
import apiClient from '../api/client';
import { useAuth } from '../context/AuthContext';

const LOG_SOURCES = {
  service: {
    label: 'لاگ سرویس',
    description: 'لاگ زنده systemd، همگام‌سازی Traccar و خطاهای سرویس',
    command: 'journalctl -u sana-gps -f',
  },
  network: {
    label: 'پایش بسته‌های شبکه',
    description: 'خروجی ابزار ضبط بسته‌های شبکه روی سرور؛ نوع و پورت بسته‌ها به تنظیمات ابزار نصب‌شده بستگی دارد.',
    command: 'sudo /usr/local/sbin/sana-gps-network-capture',
  },
};

function LiveTerminal() {
  const [selectedStream, setSelectedStream] = useState('service');
  const source = LOG_SOURCES[selectedStream];
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
        const response = await fetch(`${apiClient.defaults.baseURL}/gps-monitor/logs/${selectedStream}/`, {
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
  }, [running, selectedStream]);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [lines]);

  const displayStatus = running ? status : 'paused';
  const statusLabel = displayStatus === 'live' ? 'زنده' : displayStatus === 'connecting' ? 'در حال اتصال' : displayStatus === 'paused' ? 'متوقف' : displayStatus === 'error' ? 'خطا' : 'قطع اتصال';

  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-border-base bg-bg-elevated shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-base p-3 sm:p-4">
        <div className="min-w-0 flex-1">
          <label htmlFor="live-log-source" className="mb-1.5 block text-xs font-medium text-text-secondary">منبع لاگ</label>
          <div className="relative max-w-xl">
            <select
              id="live-log-source"
              value={selectedStream}
              onChange={(event) => {
                setSelectedStream(event.target.value);
                setLines([]);
                setError('');
                setStatus('connecting');
                setRunning(true);
              }}
              className="w-full appearance-none rounded-lg border border-border-base bg-bg-base py-2 pl-9 pr-3 text-sm text-text-primary outline-none transition focus:border-brand-500"
            >
              {Object.entries(LOG_SOURCES).map(([key, item]) => (
                <option key={key} value={key}>{item.label}</option>
              ))}
            </select>
            <ChevronDown size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          </div>
          <p className="mt-1.5 text-xs leading-5 text-text-muted">{source.description}</p>
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
            <p className="mt-1 text-slate-600">$ {source.command}</p>
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

  return <LiveTerminal />;
}
