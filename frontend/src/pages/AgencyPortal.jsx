import { useState, useEffect } from 'react';
import { api } from '../api';
import { StatusBadge } from './Dashboard';

export default function AgencyPortal({ agencyKey: propKey }) {
  // Extract agency key from URL or prop
  const pathKey = window.location.pathname.split('/').pop();
  const agencyKey = propKey || pathKey;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!agencyKey) return;
    fetch(`/api/agency/${agencyKey}/dashboard`)
      .then(r => { if (!r.ok) throw new Error('Agencia no encontrada'); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [agencyKey]);

  if (loading) return <AgencyShell agencyKey={agencyKey}><p className="p-8 text-center" style={{ color: 'var(--muted)' }}>Cargando...</p></AgencyShell>;
  if (error) return <AgencyShell agencyKey={agencyKey}><p className="p-8 text-center text-red-600">⚠️ {error}</p></AgencyShell>;
  if (!data) return null;

  const { agency, deployments, heartbeat } = data;
  const installedApps = heartbeat?.installed_apps ? JSON.parse(heartbeat.installed_apps) : {};

  return (
    <AgencyShell agencyKey={agencyKey} agencyName={agency.display_name}>
      {/* Status Bar */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <StatCard label="Agente" value={agency.agent_version || 'No instalado'}
          color={agency.agent_version ? '#198754' : '#DC3545'}
          sub={agency.is_active ? '🟢 Online' : '🔴 Offline'} />
        <StatCard label="Último ping" value={agency.last_seen_at ? new Date(agency.last_seen_at).toLocaleTimeString() : 'Nunca'}
          color="var(--primary)" />
        <StatCard label="CPU" value={heartbeat?.cpu_pct != null ? `${heartbeat.cpu_pct}%` : '—'}
          color={heartbeat?.cpu_pct > 80 ? '#DC3545' : '#198754'} />
        <StatCard label="Apps instaladas" value={Object.keys(installedApps).length}
          color="var(--gov-navy)" />
      </div>

      {/* System Health */}
      {heartbeat && (
        <div className="mb-6 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
          <h3 className="font-bold text-sm mb-3" style={{ color: 'var(--gov-navy)' }}>💻 Salud del Sistema</h3>
          <div className="grid grid-cols-5 gap-4 text-sm">
            <div><span style={{ color: 'var(--muted)' }}>OS:</span> <span className="font-mono text-xs">{heartbeat.os_info || '—'}</span></div>
            <div><span style={{ color: 'var(--muted)' }}>Agent:</span> <span className="font-mono text-xs">{heartbeat.agent_version || '—'}</span></div>
            <div><span style={{ color: 'var(--muted)' }}>CPU:</span> <span className="font-bold">{heartbeat.cpu_pct != null ? `${heartbeat.cpu_pct}%` : '—'}</span></div>
            <div><span style={{ color: 'var(--muted)' }}>RAM:</span> <span className="font-bold">{heartbeat.mem_pct != null ? `${heartbeat.mem_pct}%` : '—'}</span></div>
            <div><span style={{ color: 'var(--muted)' }}>Disco:</span> <span className="font-bold">{heartbeat.disk_pct != null ? `${heartbeat.disk_pct}%` : '—'}</span></div>
          </div>
        </div>
      )}

      {/* Installed Apps */}
      <div className="mb-6 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
        <h3 className="font-bold text-sm mb-3" style={{ color: 'var(--gov-navy)' }}>📦 Aplicaciones Instaladas</h3>
        {Object.keys(installedApps).length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--muted)' }}>No hay aplicaciones registradas aún</p>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(installedApps).map(([app, version]) => (
              <div key={app} className="p-3 rounded border" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
                <p className="font-mono font-bold text-sm">{app}</p>
                <p className="text-xs" style={{ color: 'var(--muted)' }}>v{version}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Deployment History */}
      <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
        <h3 className="font-bold text-sm mb-3" style={{ color: 'var(--gov-navy)' }}>📋 Historial de Deployments</h3>
        <div className="rounded border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
          <table className="w-full text-sm">
            <thead style={{ background: 'var(--sidebar)', color: '#fff' }}>
              <tr>
                <th className="text-left p-2">App</th>
                <th className="text-left p-2">Release</th>
                <th className="text-left p-2">Deployment</th>
                <th className="text-left p-2">Estado</th>
                <th className="text-left p-2">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((d, i) => (
                <tr key={i} style={{ background: i % 2 ? '#fff' : 'var(--bg)' }}>
                  <td className="p-2">{d.app_name}</td>
                  <td className="p-2 font-mono text-xs">{d.release_tag}</td>
                  <td className="p-2 font-mono text-xs" style={{ color: 'var(--muted)' }}>{d.deployment_tag}</td>
                  <td className="p-2"><StatusBadge status={d.status} /></td>
                  <td className="p-2 text-xs" style={{ color: 'var(--muted)' }}>
                    {d.completed_at ? new Date(d.completed_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
              {deployments.length === 0 && (
                <tr><td colSpan={5} className="p-6 text-center" style={{ color: 'var(--muted)' }}>Sin deployments</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AgencyShell>
  );
}

function AgencyShell({ agencyKey, agencyName, children }) {
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* Minimal header */}
      <header className="flex items-center justify-between px-6 py-3 border-b" style={{ background: '#fff', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3">
          <div className="font-bold text-sm" style={{ color: 'var(--gov-navy)' }}>🏛️ FBIB Hub</div>
          <span style={{ color: 'var(--muted)' }}>·</span>
          <span className="text-sm font-mono font-bold" style={{ color: 'var(--gold)' }}>{agencyKey?.toUpperCase()}</span>
          {agencyName && <span className="text-sm" style={{ color: 'var(--muted)' }}>— {agencyName}</span>}
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--muted)' }}>
          <span>🇵🇷</span>
          <span>Gobierno de Puerto Rico</span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto p-6">
        {children}
      </main>
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="rounded-lg p-4 border text-center" style={{ borderColor: 'var(--border)', background: '#fff' }}>
      <p className="text-2xl font-bold" style={{ color }}>{value}</p>
      <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{label}</p>
      {sub && <p className="text-xs mt-0.5">{sub}</p>}
    </div>
  );
}
