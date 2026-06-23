import { useState, useEffect } from 'react';
import Login from './pages/Login';
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
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('asi_user'));
    } catch { return null; }
  });

  const handleLogin = (userData) => {
    setUser(userData);
    sessionStorage.setItem('asi_user', JSON.stringify(userData));
  };

  const handleLogout = () => {
    setUser(null);
    sessionStorage.removeItem('asi_user');
  };

  // Agency Portal — public, no login needed
  if (route.page === 'agency') {
    return <AgencyPortal agencyKey={route.key} />;
  }

  // Login screen — Boomi-inspired
  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  // Admin Portal — sidebar layout (authenticated)
  return (
    <div className="flex h-screen">
      <aside className="w-56 flex-shrink-0 flex flex-col" style={{ background: 'var(--sidebar)' }}>
        <div className="p-4 border-b" style={{ borderColor: 'var(--nav-active)' }}>
          <h1 className="text-sm font-bold tracking-wide" style={{ color: 'var(--gold)' }}>
            ASI Deploy Hub
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--nav-inactive)' }}>
            v1.1 · Admin
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
        <div className="p-3 border-t space-y-2" style={{ borderColor: 'var(--nav-active)' }}>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>
            👤 {user?.username || 'Admin'}
          </div>
          <button
            onClick={handleLogout}
            className="text-xs underline"
            style={{ color: 'var(--nav-inactive)' }}
          >
            Cerrar sesión
          </button>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>
            Puerto Rico 🇵🇷
          </div>
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
