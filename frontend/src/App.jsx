import { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Agencies from './pages/Agencies';
import Apps from './pages/Apps';
import Deployments from './pages/Deployments';
import AgencyPortal from './pages/AgencyPortal';

// Simple client-side router — no react-router needed
function useRoute() {
  const [route, setRoute] = useState(() => {
    const path = window.location.pathname;
    if (path.startsWith('/agency/')) return { page: 'agency', key: path.split('/').pop() };
    return { page: 'dashboard' };
  });

  useEffect(() => {
    const handle = () => {
      const path = window.location.pathname;
      if (path.startsWith('/agency/')) {
        setRoute({ page: 'agency', key: path.split('/').pop() });
      }
    };
    window.addEventListener('popstate', handle);
    return () => window.removeEventListener('popstate', handle);
  }, []);

  const navigate = (page) => {
    window.history.pushState({}, '', page === 'dashboard' ? '/' : `/${page}`);
    setRoute({ page });
  };

  return [route, navigate];
}

const NAV = [
  { key: 'dashboard', label: 'Dashboard', icon: '📊' },
  { key: 'agencies', label: 'Agencias', icon: '🏛️' },
  { key: 'apps', label: 'Apps & Releases', icon: '📦' },
  { key: 'deployments', label: 'Deployments', icon: '🚀' },
];

function App() {
  const [route, navigate] = useRoute();

  // Agency Portal — completely different layout
  if (route.page === 'agency') {
    return <AgencyPortal agencyKey={route.key} />;
  }

  // Admin Portal — sidebar layout
  return (
    <div className="flex h-screen">
      <aside className="w-56 flex-shrink-0 flex flex-col" style={{ background: 'var(--sidebar)' }}>
        <div className="p-4 border-b" style={{ borderColor: 'var(--nav-active)' }}>
          <h1 className="text-sm font-bold tracking-wide" style={{ color: 'var(--gold)' }}>
            ASI Deploy Hub
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--nav-inactive)' }}>
            v1.0 · Admin
          </p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV.map(({ key, label, icon }) => (
            <button
              key={key}
              onClick={() => navigate(key)}
              className="w-full text-left px-3 py-2 rounded text-sm font-medium transition-colors"
              style={{
                color: route.page === key ? '#fff' : 'var(--nav-inactive)',
                background: route.page === key ? 'var(--nav-active)' : 'transparent',
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

      <main className="flex-1 overflow-auto p-6">
        {route.page === 'dashboard' && <Dashboard />}
        {route.page === 'agencies' && <Agencies />}
        {route.page === 'apps' && <Apps />}
        {route.page === 'deployments' && <Deployments />}
      </main>
    </div>
  );
}

export default App;
