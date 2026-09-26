import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import SanaLogo from '../SanaLogo';

export default function ProtectedRoute({ children, allowRoles = null }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-base flex flex-col items-center justify-center gap-6">
        <SanaLogo size="md" showSubtitle />
        <div className="flex items-center gap-2 text-text-muted text-sm">
          <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          در حال بارگذاری...
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowRoles && !allowRoles.includes(user.role)) {
    return <Navigate to="/panel/dashboard" replace />;
  }

  return children;
}