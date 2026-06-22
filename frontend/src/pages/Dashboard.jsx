import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Dashboard() {
  const [deployments, setDeployments] = useState([]);
  const [agencies, setAgencies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getDeployments(), api.getAgencies()])
      .then(([d, a]) => { setDeployments(d); setAgencies(a); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const stats = {
    totalAgencies: agencies.length,
    active: agencies.filter(a => a.is_active).length,
    recentDeploys: deployments.length,
    successDeploys: deployments.filter(d => d.status === 'COMPLETED').length,
  };

  if (loading) return <div className="text-muted">Cargando...</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-1" style={{ color: 'var(--gov-navy)' }}>Dashboard</h2>
      <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>Resumen del sistema de despliegue</p>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Agencias', value: stats.totalAgencies, color: '#0D6EFD' },
          { label: 'Activas', value: stats.active, color: '#198754' },
          { label: 'Deployments', value: stats.recentDeploys, color: '#E5BD44' },
          { label: 'Exitosos', value: stats.successDeploys, color: '#6C757D' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg p-4 border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
            <p className="text-3xl font-bold" style={{ color }}>{value}</p>
            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Recent deployments */}
      <h3 className="text-lg font-bold mb-3" style={{ color: 'var(--gov-navy)' }}>Deployments Recientes</h3>
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
        <table className="w-full text-sm">
          <thead style={{ background: 'var(--sidebar)', color: '#fff' }}>
            <tr>
              <th className="text-left p-3">Tag</th>
              <th className="text-left p-3">App</th>
              <th className="text-left p-3">Release</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Fecha</th>
            </tr>
          </thead>
          <tbody>
            {deployments.slice(0, 10).map((d, i) => (
              <tr key={d.id} style={{ background: i % 2 ? '#fff' : 'var(--bg)' }}>
                <td className="p-3 font-mono text-xs">{d.deployment_tag}</td>
                <td className="p-3">{d.app_name}</td>
                <td className="p-3 font-mono text-xs">{d.release_tag}</td>
                <td className="p-3">
                  <StatusBadge status={d.status} />
                </td>
                <td className="p-3 text-xs" style={{ color: 'var(--muted)' }}>
                  {d.created_at ? new Date(d.created_at).toLocaleDateString() : '-'}
                </td>
              </tr>
            ))}
            {deployments.length === 0 && (
              <tr><td colSpan={5} className="p-6 text-center" style={{ color: 'var(--muted)' }}>No hay deployments aún</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function StatusBadge({ status }) {
  const colors = {
    COMPLETED: { bg: '#d1fae5', text: '#065f46' },
    IN_PROGRESS: { bg: '#dbeafe', text: '#1e40af' },
    FAILED: { bg: '#fee2e2', text: '#991b1b' },
    ROLLED_BACK: { bg: '#fef3c7', text: '#92400e' },
    PENDING: { bg: '#f3f4f6', text: '#374151' },
  };
  const c = colors[status] || colors.PENDING;
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: c.bg, color: c.text }}>
      {status}
    </span>
  );
}
