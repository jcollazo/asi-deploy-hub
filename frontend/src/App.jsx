import { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Agencies from './pages/Agencies';
import Apps from './pages/Apps';
import Deployments from './pages/Deployments';

const NAV = [
  { key: 'dashboard', label: 'Dashboard', icon: '📊' },
  { key: 'agencies', label: 'Agencias', icon: '🏛️' },
  { key: 'apps', label: 'Apps & Releases', icon: '📦' },
  { key: 'deployments', label: 'Deployments', icon: '🚀' },
];

function App() {
  const [page, setPage] = useState('dashboard');

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col" style={{ background: 'var(--sidebar)' }}>
        <div className="p-4 border-b" style={{ borderColor: 'var(--nav-active)' }}>
          <h1 className="text-sm font-bold tracking-wide" style={{ color: 'var(--gold)' }}>
            ASI Deploy Hub
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--nav-inactive)' }}>
            v1.0 · Gobierno de PR
          </p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV.map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => setPage(key)}
              className="w-full text-left px-3 py-2 rounded text-sm font-medium transition-colors"
              style={{
                color: page === key ? '#fff' : 'var(--nav-inactive)',
                background: page === key ? 'var(--nav-active)' : 'transparent',
              }}
            >
              <span className="mr-2">{icon}</span>
              {label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t text-xs" style={{ borderColor: 'var(--nav-active)', color: 'var(--muted)' }}>
          Puerto Rico 🇵🇷
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto p-6">
        {page === 'dashboard' && <Dashboard />}
        {page === 'agencies' && <Agencies />}
        {page === 'apps' && <Apps />}
        {page === 'deployments' && <Deployments />}
      </main>
    </div>
  );
}

export default App;
