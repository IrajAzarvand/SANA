import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import Login from './pages/Login';
import PanelLayout from './layouts/PanelLayout';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import Map from './pages/Map';
import Vehicles from './pages/Vehicles';
import Drivers from './pages/Drivers';
import Devices from './pages/Devices';
import Reports from './pages/Reports';
import Alerts from './pages/Alerts';
import Settings from './pages/Settings';
import Companies from './pages/Companies';
import Users from './pages/Users';
import Branches from './pages/Branches';
import Subscriptions from './pages/Subscriptions';
import SubscriptionWizard from './pages/SubscriptionWizard';
import SubscriptionDetail from './pages/SubscriptionDetail';

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/panel" element={
            <ProtectedRoute>
              <PanelLayout />
            </ProtectedRoute>
          }>
            <Route index element={<Navigate to="/panel/dashboard" replace />} />

            <Route path="dashboard" element={<Dashboard />} />
            <Route path="map"       element={<Map />} />
            <Route path="devices"   element={<Devices />} />
            <Route path="reports"   element={<Reports />} />
            <Route path="alerts"    element={<Alerts />} />
            <Route path="settings"  element={<Settings />} />

            {/* خودروها */}
            <Route path="vehicles" element={
              <ProtectedRoute allowRoles={['main_user', 'branch_manager', 'personal_user']}>
                <Vehicles />
              </ProtectedRoute>
            } />

            {/* رانندگان */}
            <Route path="drivers" element={
              <ProtectedRoute allowRoles={['main_user', 'branch_manager']}>
                <Drivers />
              </ProtectedRoute>
            } />

            {/* قراردادها */}
            <Route path="subscriptions" element={
              <ProtectedRoute allowRoles={['site_admin']}>
                <Subscriptions />
              </ProtectedRoute>
            } />

            <Route path="subscriptions/new" element={
              <ProtectedRoute allowRoles={['site_admin']}>
                <SubscriptionWizard />
              </ProtectedRoute>
            } />

            <Route path="subscriptions/:id" element={
              <ProtectedRoute allowRoles={['site_admin']}>
                <SubscriptionDetail />
              </ProtectedRoute>
            } />

            {/* شرکت‌ها */}
            <Route path="companies" element={
              <ProtectedRoute allowRoles={['site_admin']}>
                <Companies />
              </ProtectedRoute>
            } />

            {/* کاربران */}
            <Route path="users" element={
              <ProtectedRoute allowRoles={['site_admin', 'main_user']}>
                <Users />
              </ProtectedRoute>
            } />

            {/* شعبه‌ها */}
            <Route path="branches" element={
              <ProtectedRoute allowRoles={['site_admin', 'main_user']}>
                <Branches />
              </ProtectedRoute>
            } />
          </Route>

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
}