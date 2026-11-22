import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
const Login = lazy(() => import('./pages/Login'));
import PanelLayout from './layouts/PanelLayout';
import ProtectedRoute from './components/auth/ProtectedRoute';
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Map = lazy(() => import('./pages/Map'));
const Vehicles = lazy(() => import('./pages/Vehicles'));
const Drivers = lazy(() => import('./pages/Drivers'));
const Devices = lazy(() => import('./pages/Devices'));
const Reports = lazy(() => import('./pages/Reports'));
const DeviceTripReport = lazy(() => import('./pages/DeviceTripReport'));
const LiveLogs = lazy(() => import('./pages/LiveLogs'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Settings = lazy(() => import('./pages/Settings'));
const Companies = lazy(() => import('./pages/Companies'));
const Users = lazy(() => import('./pages/Users'));
const Branches = lazy(() => import('./pages/Branches'));
const Subscriptions = lazy(() => import('./pages/Subscriptions'));
const SubscriptionWizard = lazy(() => import('./pages/SubscriptionWizard'));
const SubscriptionDetail = lazy(() => import('./pages/SubscriptionDetail'));
const AIManagement = lazy(() => import('./pages/AIManagement'));

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Suspense fallback={<div className="p-4 text-center" role="status">در حال بارگذاری صفحه...</div>}>
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
            <Route path="reports/trips" element={<DeviceTripReport />} />
            <Route path="reports/live-logs" element={
              <ProtectedRoute allowRoles={['site_admin']}>
                <LiveLogs />
              </ProtectedRoute>
            } />
            <Route path="alerts"    element={<Alerts />} />
            <Route path="settings"  element={<Settings />} />

            {/* مدیریت هوش مصنوعی — فقط ادمین سایت */}
            <Route path="ai" element={
              <ProtectedRoute allowRoles={['site_admin']}>
                <AIManagement />
              </ProtectedRoute>
            } />

            {/* خودروها */}
            <Route path="vehicles" element={
              <ProtectedRoute allowRoles={['main_user', 'branch_manager']}>
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
              <ProtectedRoute allowRoles={['site_admin', 'main_user', 'personal_user']}>
                <Subscriptions />
              </ProtectedRoute>
            } />

            <Route path="subscriptions/new" element={
              <ProtectedRoute allowRoles={['site_admin']}>
                <SubscriptionWizard />
              </ProtectedRoute>
            } />

            <Route path="subscriptions/:id" element={
              <ProtectedRoute allowRoles={['site_admin', 'main_user', 'personal_user']}>
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
        </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
  );
}