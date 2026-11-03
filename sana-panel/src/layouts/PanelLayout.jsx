import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';

export default function PanelLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-dvh min-h-dvh flex-col overflow-hidden bg-bg-base">

      <Header onMenuClick={() => setSidebarOpen(true)} />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <main className="min-w-0 min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-y-contain p-3 sm:p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

    </div>
  );
}
