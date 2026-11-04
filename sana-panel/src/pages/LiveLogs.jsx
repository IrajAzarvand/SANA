import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Terminal, Pause, Play, Trash2, ShieldCheck, RadioTower,
  CircleStop, Wifi, Server, Database, Activity,
} from 'lucide-react';
import apiClient from '../api/client';
import { useAuth } from '../context/AuthContext';

const LOG_SOURCES = {
  gps: {
    label: 'سرویس GPS سانا',
    description: 'لاگ systemd سرویس GPS، همگام‌سازی و ارتباطات مرتبط با Traccar',
    icon: RadioTower,
  },
  traccar: {
    label: 'Traccar',
    description: 'اتصال دستگاه‌ها، دریافت بسته‌ها، تشخیص پروتکل و خطاهای پردازش Traccar',
    icon: Activity,
  },
  backend: {
    label: 'بک‌اند سانا',
    description: 'خطاهای Django، API، احراز هویت و ارتباط بک‌اند با سرویس‌های دیگر',
    icon: Server,
  },
  postgres: {
    label: 'PostgreSQL',
    description: 'رویدادها و خطاهایی که سرویس PostgreSQL در systemd journal ثبت می‌کند',
    icon: Database,
  },
  system: {
    label: 'هشدارهای سرور',
    description: 'هشدارها و خطاهای سطح سیستم از systemd journal',
    icon: Terminal,
  },
  network: {
    label: 'ترافیک پورت Traccar',
    description: 'مشاهده خلاصه بسته‌های ورودی و خروجی TCP/UDP روی پورت انتخابی؛ بدون ذخیره در فایل',
    icon: Wifi,
  },
};

const MAX_LINES_PER_SOURCE = 500;

function LiveTerminal() {
  const [selectedSource, setSelectedSource] = useState('all');
  const [lines, setLines] = useState([]);
  const [statuses, setStatuses] = useState({});
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [error, setError] = useState('');
  const [following, setFollowing] = useState(true);
  const [capturePort, setCapturePort] = useState('');
  const [captureProtocol, setCaptureProtocol] = useState('both');
  const [activeCapture, setActiveCapture] = useState(null);
  const bodyRef = useRef(null);
  const lineIdRef = useRef(0);

  const visibleLines = useMemo(
    () => selectedSource === 'all'
      ? lines
      : lines.filter((item) => item.source === selectedSource),
    [lines, selectedSource],
  );

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    const connect = async () => {
      setConnectionStatus('connecting');
      setError('');
      setStatuses(
        Object.fromEntries(Object.keys(LOG_SOURCES).filter((key) => key !== 'network')
          .map((key) => [key, 'connecting'])),
      );

      try {
        const token = localStorage.getItem('sana_access_token');
        const params = new URLSearchParams();
        if (activeCapture) {
          params.set('capture_port', String(activeCapture.port));
          params.set('capture_protocol', activeCapture.protocol);
        }
        const query = params.toString();
        const endpoint = `${apiClient.defaults.baseURL}/gps-monitor/logs/${query ? `?${query}` : ''}`;
        const response = await fetch(endpoint, {
          headers: token
            ? { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' }
            : { Accept: 'text/event-stream' },
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

        setConnectionStatus('live');
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
              if (payload.kind === 'status' && payload.source) {
                setStatuses((previous) => ({
                  ...previous,
                  [payload.source]: payload.status,
                }));
                if (payload.message) {
                  setLines((previous) => [
                    ...previous,
                    {
                      id: ++lineIdRef.current,
                      source: payload.source,
                      text: `[وضعیت] ${payload.message}`,
                    },
                  ].slice(-MAX_LINES_PER_SOURCE * Object.keys(LOG_SOURCES).length));
                }
              } else if (payload.kind === 'line' && payload.source && payload.line) {
                const item = {
                  id: ++lineIdRef.current,
                  source: payload.source,
                  text: payload.line,
                };
                setLines((previous) => {
                  const next = [...previous, item];
                  const sourceIndexes = [];
                  next.forEach((line, index) => {
                    if (line.source === item.source) sourceIndexes.push(index);
                  });
                  if (sourceIndexes.length > MAX_LINES_PER_SOURCE) {
                    const removeIndex = sourceIndexes[0];
                    next.splice(removeIndex, 1);
                  }
                  return next.slice(-MAX_LINES_PER_SOURCE * Object.keys(LOG_SOURCES).length);
                });
              }
            } catch {
              // Ignore malformed or incomplete server-sent events.
            }
          }
        }

        if (!cancelled) setConnectionStatus('disconnected');
      } catch (err) {
        if (err.name !== 'AbortError' && !cancelled) {
          setError(err.message || 'اتصال برقرار نشد.');
          setConnectionStatus('error');
        }
      }
    };

    connect();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [activeCapture]);

  useEffect(() => {
    if (following && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [visibleLines, following]);

  const handleCaptureToggle = () => {
    if (activeCapture) {
      setActiveCapture(null);
      setStatuses((previous) => ({ ...previous, network: 'stopped' }));
      return;
    }
    const parsedPort = Number(capturePort);
    if (!Number.isInteger(parsedPort) || parsedPort < 1024 || parsedPort > 65535) {
      setError('شماره پورت باید بین 1024 تا 65535 و مربوط به یکی از listenerهای Traccar باشد.');
      return;
    }
    setError('');
    setActiveCapture({ port: parsedPort, protocol: captureProtocol });
    setStatuses((previous) => ({ ...previous, network: 'connecting' }));
  };

  const statusText = (status) => ({
    live: 'زنده',
    connecting: 'در حال اتصال',
    error: 'خطا',
    stopped: 'متوقف',
  }[status] || 'آماده');

  const currentSource = LOG_SOURCES[selectedSource];

  return (
    <section className="w-full min-w-0 space-y-3">
      <div className="rounded-2xl border border-border-base bg-bg-elevated p-3 shadow-sm sm:p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(220px,0.7fr)] xl:items-end">
          <div className="min-w-0">
            <label htmlFor="live-log-source" className="mb-1.5 block text-xs font-medium text-text-secondary">
              نمایش منبع
            </label>
            <select
              id="live-log-source"
              value={selectedSource}
              onChange={(event) => setSelectedSource(event.target.value)}
              className="w-full rounded-lg border border-border-base bg-bg-base px-3 py-2.5 text-sm text-text-primary outline-none focus:border-brand-500"
            >
              <option value="all">همه منابع (نمایش ترکیبی)</option>
              {Object.entries(LOG_SOURCES).map(([key, source]) => (
                <option key={key} value={key}>{source.label}</option>
              ))}
            </select>
            <p className="mt-1.5 text-xs leading-5 text-text-muted">
              {selectedSource === 'all'
                ? 'تمام منابع عادی به‌صورت هم‌زمان دریافت می‌شوند؛ تغییر این فهرست اتصال را قطع نمی‌کند.'
                : currentSource.description}
            </p>
          </div>

          <div className="flex min-w-0 items-center justify-between gap-2 rounded-lg bg-bg-base px-3 py-2.5">
            <div className="flex min-w-0 items-center gap-2">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${connectionStatus === 'live' ? 'animate-pulse bg-emerald-500' : connectionStatus === 'error' ? 'bg-danger' : 'bg-amber-500'}`} />
              <span className="truncate text-sm font-medium text-text-primary">
                {connectionStatus === 'live' ? 'اتصال مرکزی برقرار است' : connectionStatus === 'connecting' ? 'در حال اتصال به منابع...' : connectionStatus === 'error' ? 'خطا در اتصال' : 'اتصال قطع شده'}
              </span>
            </div>
            <span className="shrink-0 text-[11px] text-text-muted">
              {activeCapture ? `پایش ${activeCapture.port} فعال` : 'پایش شبکه خاموش'}
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
          {Object.entries(LOG_SOURCES).filter(([key]) => key !== 'network').map(([key, source]) => {
            const Icon = source.icon;
            const status = statuses[key] || 'connecting';
            return (
              <div key={key} className="flex min-w-0 items-center gap-2 rounded-lg border border-border-base px-2.5 py-2">
                <Icon size={15} className="shrink-0 text-text-muted" />
                <span className="min-w-0 flex-1 truncate text-xs text-text-secondary">{source.label}</span>
                <span className={`h-2 w-2 shrink-0 rounded-full ${status === 'live' ? 'bg-emerald-500' : status === 'error' ? 'bg-danger' : 'bg-amber-500'}`} title={statusText(status)} />
              </div>
            );
          })}
        </div>

        {selectedSource === 'network' && (
          <div className="mt-4 rounded-xl border border-border-base bg-bg-base p-3 sm:p-4">
            <div className="mb-3 flex items-start gap-2">
              <Wifi size={17} className="mt-0.5 shrink-0 text-text-secondary" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-primary">پایش ترافیک پورت Traccar</p>
                <p className="mt-1 text-xs leading-5 text-text-muted">
                  فقط هنگام شروع پایش اجرا می‌شود. خروجی خلاصه بسته‌ها را نشان می‌دهد و در فایل ذخیره نمی‌شود.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(120px,0.8fr)_minmax(150px,1fr)_auto] sm:items-end">
              <div className="min-w-0">
                <label htmlFor="capture-port" className="mb-1 block text-xs text-text-secondary">شماره پورت</label>
                <input
                  id="capture-port"
                  type="number"
                  min="1024"
                  max="65535"
                  inputMode="numeric"
                  value={capturePort}
                  onChange={(event) => setCapturePort(event.target.value)}
                  disabled={Boolean(activeCapture)}
                  placeholder="مثلاً 5027"
                  className="w-full rounded-lg border border-border-base bg-bg-elevated px-3 py-2.5 text-sm text-text-primary outline-none focus:border-brand-500 disabled:opacity-60"
                />
              </div>
              <div className="min-w-0">
                <label htmlFor="capture-protocol" className="mb-1 block text-xs text-text-secondary">پروتکل</label>
                <select
                  id="capture-protocol"
                  value={captureProtocol}
                  onChange={(event) => setCaptureProtocol(event.target.value)}
                  disabled={Boolean(activeCapture)}
                  className="w-full rounded-lg border border-border-base bg-bg-elevated px-3 py-2.5 text-sm text-text-primary outline-none focus:border-brand-500 disabled:opacity-60"
                >
                  <option value="both">TCP و UDP</option>
                  <option value="tcp">فقط TCP</option>
                  <option value="udp">فقط UDP</option>
                </select>
              </div>
              <button
                type="button"
                onClick={handleCaptureToggle}
                className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition ${activeCapture ? 'bg-danger hover:opacity-90' : 'bg-brand-600 hover:bg-brand-700'}`}
              >
                {activeCapture ? <CircleStop size={16} /> : <Play size={16} />}
                {activeCapture ? 'توقف پایش' : 'شروع پایش'}
              </button>
            </div>
            {activeCapture && (
              <p className="mt-2 text-xs text-emerald-600">
                پایش پورت {activeCapture.port} ({activeCapture.protocol.toUpperCase()}) · وضعیت: {statusText(statuses.network || 'connecting')}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="min-w-0 overflow-hidden rounded-2xl border border-border-base bg-[#0b1220] shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 bg-[#111827] px-3 py-2.5 sm:px-4">
          <div className="flex min-w-0 items-center gap-2 text-[11px] text-slate-400">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-red-400/90" />
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-400/90" />
            <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-400/90" />
            <span className="truncate font-mono">sana@server:~ / live-monitor</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setLines([])}
              title="پاک کردن نمایش"
              className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white"
            >
              <Trash2 size={15} />
            </button>
            <button
              type="button"
              onClick={() => setFollowing((value) => !value)}
              title={following ? 'توقف اسکرول خودکار' : 'ادامه اسکرول خودکار'}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-2.5 py-2 text-xs text-slate-100 hover:bg-white/15"
            >
              {following ? <Pause size={13} /> : <Play size={13} />}
              <span>{following ? 'توقف اسکرول' : 'دنبال‌کردن'}</span>
            </button>
          </div>
        </div>

        <div
          ref={bodyRef}
          aria-live="polite"
          dir="ltr"
          className="h-[55vh] min-h-72 max-h-[72vh] overflow-auto overscroll-contain p-3 font-mono text-[11px] leading-5 text-emerald-300 sm:p-4 sm:text-xs"
        >
          {error && <p className="mb-3 whitespace-pre-wrap break-words text-rose-300">Connection error: {error}</p>}
          {visibleLines.length === 0 && !error && (
            <div className="text-slate-500">
              <p>{connectionStatus === 'connecting' ? 'Connecting to live sources...' : 'Waiting for log events...'}</p>
              {selectedSource === 'network' && !activeCapture && (
                <p className="mt-1 text-amber-300">Enter a Traccar port and start packet monitoring to receive network events.</p>
              )}
            </div>
          )}
          {visibleLines.map((line) => (
            <div key={line.id} className="grid min-w-0 grid-cols-[minmax(74px,auto)_minmax(0,1fr)] gap-2 border-b border-white/[0.035] py-0.5">
              <span className="select-none break-words text-sky-400/80">[{LOG_SOURCES[line.source]?.label || line.source}]</span>
              <span className="min-w-0 whitespace-pre-wrap break-all text-slate-200">{line.text}</span>
            </div>
          ))}
          {connectionStatus === 'live' && <span className="mt-1 inline-block h-3.5 w-1.5 animate-pulse bg-emerald-400 align-middle" />}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-3 py-2 text-[11px] text-slate-400 sm:px-4">
          <span>{visibleLines.length.toLocaleString('fa-IR')} خط در نمایش · حداکثر {MAX_LINES_PER_SOURCE} خط برای هر منبع</span>
          <span className="inline-flex items-center gap-1"><ShieldCheck size={12} /> فقط خواندنی · بدون فایل لاگ جدید</span>
        </div>
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
