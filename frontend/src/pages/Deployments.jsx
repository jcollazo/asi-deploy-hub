import { useState, useEffect } from 'react';
import { api } from '../api';
import { StatusBadge } from './Dashboard';

export default function Deployments() {
  const [deployments, setDeployments] = useState([]);
  const [agencies, setAgencies] = useState([]);
  const [releases, setReleases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [selectedRelease, setSelectedRelease] = useState('');
  const [selectedAgencies, setSelectedAgencies] = useState([]);
  const [strategy, setStrategy] = useState('ALL_AT_ONCE');
  const [statusMap, setStatusMap] = useState({});
  const [viewingDeployment, setViewingDeployment] = useState(null);

  const load = async () => {
    const [d, a, r] = await Promise.all([api.getDeployments(), api.getAgencies(), api.getReleases()]);
    setDeployments(d);
    setAgencies(a);
    setReleases(r.filter(r => r.status === 'PUBLISHED'));
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const toggleAgency = (key) => {
    setSelectedAgencies(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  };

  const handleDeploy = async (e) => {
    e.preventDefault();
    if (!selectedRelease || selectedAgencies.length === 0) return;
    const release = releases.find(r => r.id === parseInt(selectedRelease));
    await api.createDeployment({
      release_id: parseInt(selectedRelease),
      agency_keys: selectedAgencies,
      strategy,
      description: `Deploy ${release?.release_tag} to ${selectedAgencies.length} agencies`,
    });
    setShowForm(false);
    setSelectedAgencies([]);
    load();
  };

  const handleRollback = async (id) => {
    if (!confirm('¿Rollback de este deployment?')) return;
    await api.rollbackDeployment(id);
    load();
  };

  const viewStatus = async (id) => {
    const status = await api.getDeploymentStatus(id);
    setStatusMap(status);
    setViewingDeployment(id);
  };

  if (loading) return <div className="text-muted">Cargando...</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: 'var(--gov-navy)' }}>Deployments</h2>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>{deployments.length} despliegues</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="px-4 py-2 rounded-lg text-white text-sm font-medium" style={{ background: 'var(--primary)' }}>
          + Nuevo Deployment
        </button>
      </div>

      {/* New deployment form */}
      {showForm && (
        <form onSubmit={handleDeploy} className="mb-6 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold mb-1">Release</label>
              <select required value={selectedRelease} onChange={e => setSelectedRelease(e.target.value)}
                className="w-full p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }}>
                <option value="">Seleccionar release...</option>
                {releases.map(r => (
                  <option key={r.id} value={r.id}>{r.app_name} — {r.release_tag}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold mb-1">Estrategia</label>
              <select value={strategy} onChange={e => setStrategy(e.target.value)}
                className="w-full p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }}>
                <option value="ALL_AT_ONCE">Todo de una vez</option>
                <option value="CANARY">Canary (1 agencia primero)</option>
                <option value="ROLLING">Rolling (una por una)</option>
                <option value="MANUAL">Manual</option>
              </select>
            </div>
          </div>

          <label className="block text-xs font-bold mt-4 mb-2">Agencias destino</label>
          <div className="grid grid-cols-4 gap-2 max-h-40 overflow-y-auto">
            {agencies.filter(a => a.is_active).map(a => (
              <label key={a.agency_key} className={`flex items-center gap-2 p-2 rounded border text-sm cursor-pointer ${
                selectedAgencies.includes(a.agency_key) ? 'border-gold bg-yellow-50' : ''
              }`} style={{ borderColor: selectedAgencies.includes(a.agency_key) ? 'var(--gold)' : 'var(--border)' }}>
                <input type="checkbox" checked={selectedAgencies.includes(a.agency_key)}
                  onChange={() => toggleAgency(a.agency_key)} />
                <span className="font-mono text-xs">{a.agency_key}</span>
                <span className="text-xs" style={{ color: 'var(--muted)' }}>{a.display_name}</span>
              </label>
            ))}
          </div>

          <button type="submit" disabled={!selectedRelease || selectedAgencies.length === 0}
            className="mt-4 px-6 py-2 rounded text-white text-sm font-bold disabled:opacity-50"
            style={{ background: 'var(--danger)' }}>
            🚀 Lanzar Deployment
          </button>
        </form>
      )}

      {/* Deployment status viewer */}
      {viewingDeployment && statusMap.length > 0 && (
        <div className="mb-6 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-sm">Estado del Deployment #{viewingDeployment}</h3>
            <button onClick={() => setViewingDeployment(null)} className="text-xs" style={{ color: 'var(--muted)' }}>✕</button>
          </div>
          <div className="space-y-2">
            {statusMap.map(s => (
              <div key={s.agency_id} className="flex justify-between items-center p-2 rounded text-sm" style={{ background: 'var(--bg)' }}>
                <span className="font-mono text-xs">{s.agency_key}</span>
                <span>{s.display_name}</span>
                <StatusBadge status={s.status} />
                {s.error_message && <span className="text-xs text-red-600">{s.error_message}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deployments table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
        <table className="w-full text-sm">
          <thead style={{ background: 'var(--sidebar)', color: '#fff' }}>
            <tr>
              <th className="text-left p-3">Tag</th>
              <th className="text-left p-3">App</th>
              <th className="text-left p-3">Release</th>
              <th className="text-left p-3">Estrategia</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Fecha</th>
              <th className="text-left p-3">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {deployments.map((d, i) => (
              <tr key={d.id} style={{ background: i % 2 ? '#fff' : 'var(--bg)' }}>
                <td className="p-3 font-mono text-xs">{d.deployment_tag}</td>
                <td className="p-3">{d.app_name}</td>
                <td className="p-3 font-mono text-xs">{d.release_tag}</td>
                <td className="p-3 text-xs">{d.strategy}</td>
                <td className="p-3"><StatusBadge status={d.status} /></td>
                <td className="p-3 text-xs" style={{ color: 'var(--muted)' }}>
                  {d.created_at ? new Date(d.created_at).toLocaleString() : '-'}
                </td>
                <td className="p-3 flex gap-2">
                  <button onClick={() => viewStatus(d.id)} className="text-xs underline" style={{ color: 'var(--primary)' }}>
                    Ver
                  </button>
                  {d.status !== 'ROLLED_BACK' && d.status !== 'COMPLETED' && (
                    <button onClick={() => handleRollback(d.id)} className="text-xs underline" style={{ color: 'var(--danger)' }}>
                      Rollback
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
