import { Component } from 'react';
import { AlertTriangle, RefreshCw, ArrowRight, Copy, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

// ═══════════════════════════════════════════════
// ErrorBoundary باید Class Component باشه
// (چون React Hooks نمی‌تونن خطاها رو بگیرن)
// ═══════════════════════════════════════════════

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      copied: false,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });

    // لاگ کردن خطا توی کنسول
    console.error('🚨 ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, copied: false });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = '/panel/dashboard';
  };

  handleCopy = () => {
    const errorText = `
URL: ${window.location.href}
Time: ${new Date().toISOString()}

Error: ${this.state.error?.toString()}

Stack:
${this.state.error?.stack || '—'}

Component Stack:
${this.state.errorInfo?.componentStack || '—'}
    `.trim();

    navigator.clipboard.writeText(errorText);
    this.setState({ copied: true });
    setTimeout(() => this.setState({ copied: false }), 2000);
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen bg-bg-base flex items-center justify-center p-6">
        <div className="max-w-2xl w-full bg-bg-elevated border border-border-base rounded-card p-8">

          {/* آیکون */}
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-full bg-danger/10 flex items-center justify-center">
              <AlertTriangle size={32} className="text-danger" />
            </div>
          </div>

          {/* پیام اصلی */}
          <div className="text-center mb-6">
            <h1 className="text-xl font-bold text-text-primary mb-2">
              خطایی رخ داد
            </h1>
            <p className="text-sm text-text-muted leading-relaxed">
              متأسفانه در پردازش درخواست شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید.
              اگر مشکل ادامه داشت با پشتیبانی تماس بگیرید.
            </p>
          </div>

          {/* اطلاعات فنی — فقط برای ادمین */}
          {this.props.isAdmin && (
            <div className="bg-bg-base border border-danger/30 rounded-field p-4 mb-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-medium text-danger">
                  اطلاعات فنی (فقط ادمین)
                </h3>
                <button
                  onClick={this.handleCopy}
                  className="flex items-center gap-1.5 text-[10px] text-text-secondary hover:text-text-primary transition-colors"
                >
                  {this.state.copied ? (
                    <>
                      <Check size={12} /> کپی شد
                    </>
                  ) : (
                    <>
                      <Copy size={12} /> کپی
                    </>
                  )}
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <div className="text-[10px] text-text-muted mb-1">نشانی صفحه:</div>
                  <div className="text-[10px] text-text-secondary font-mono break-all">
                    {window.location.href}
                  </div>
                </div>

                <div>
                  <div className="text-[10px] text-text-muted mb-1">پیام خطا:</div>
                  <pre className="text-xs text-danger font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                    {this.state.error?.toString()}
                  </pre>
                </div>

                {this.state.error?.stack && (
                  <div>
                    <div className="text-[10px] text-text-muted mb-1">ردیابی خطا:</div>
                    <pre className="text-[10px] text-text-secondary font-mono whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                      {this.state.error.stack}
                    </pre>
                  </div>
                )}

                {this.state.errorInfo?.componentStack && (
                  <div>
                    <div className="text-[10px] text-text-muted mb-1">ردیابی مؤلفه:</div>
                    <pre className="text-[10px] text-text-secondary font-mono whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* دکمه‌ها */}
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={this.handleReset}
              className="flex items-center gap-2 px-4 py-2 bg-bg-hover hover:bg-bg-overlay text-text-primary rounded-field text-sm transition-colors"
            >
              <RefreshCw size={14} /> تلاش دوباره
            </button>
            <button
              onClick={this.handleGoHome}
              className="flex items-center gap-2 px-4 py-2 bg-brand-500 hover:bg-brand-400 text-bg-base rounded-field text-sm font-medium transition-colors"
            >
              بازگشت به داشبورد <ArrowRight size={14} />
            </button>
          </div>

        </div>
      </div>
    );
  }
}

// ═══════════════════════════════════════════════
// Wrapper که isAdmin رو از AuthContext می‌گیره
// ═══════════════════════════════════════════════

function ErrorBoundaryWrapper({ children }) {
  const { isSiteAdmin } = useAuth();
  return <ErrorBoundary isAdmin={isSiteAdmin}>{children}</ErrorBoundary>;
}

export default ErrorBoundaryWrapper;