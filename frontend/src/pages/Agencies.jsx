import { useState, useEffect } from 'react';
import { api } from '../api';
import { StatusBadge } from './Dashboard';

export default function Agencies() {
  const [agencies, setAgencies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ agency_key: '', display_name: '', hostname: '', os_type: 'LINUX' });

  const load = () => api.getAgencies().then(setAgencies).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    await api.createAgency(form);
    setForm({ agency_key: '', display_name: '', hostname: '', os_type: 'LINUX' });
    setShowForm(false);
    load();
  };

  if (loading) return <div className="text-muted">Cargando...</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: 'var(--gov-navy)' }}>Agencias</h2>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>{agencies.length} registradas</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 rounded-lg text-white text-sm font-medium"
          style={{ background: 'var(--primary)' }}
        >
          + Nueva Agencia
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
          <div className="grid grid-cols-4 gap-3">
            <input required placeholder="Key (ej: ogp)" value={form.agency_key}
              onChange={e => setForm({ ...form, agency_key: e.target.value })}
              className="p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }} />
            <input required placeholder="Nombre (ej: Oficina de Gerencia)" value={form.display_name}
              onChange={e => setForm({ ...form, display_name: e.target.value })}
              className="p-2 border rounded text-sm col-span-2" style={{ borderColor: 'var(--border)' }} />
            <select value={form.os_type} onChange={e => setForm({ ...form, os_type: e.target.value })}
              className="p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }}>
              <option value="LINUX">Linux</option>
              <option value="WINDOWS">Windows</option>
            </select>
          </div>
          <button type="submit" className="mt-3 px-4 py-2 rounded text-white text-sm" style={{ background: 'var(--success)' }}>
            Guardar
          </button>
        </form>
      )}

      <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
        <table className="w-full text-sm">
          <thead style={{ background: 'var(--sidebar)', color: '#fff' }}>
            <tr>
              <th className="text-left p-3">Key</th>
              <th className="text-left p-3">Agencia</th>
              <th className="text-left p-3">OS</th>
              <th className="text-left p-3">Agent</th>
              <th className="text-left p-3">Último ping</th>
              <th className="text-left p-3">Estado</th>
            </tr>
          </thead>
          <tbody>
            {agencies.map((a, i) => (
              <tr key={a.id} style={{ background: i % 2 ? '#fff' : 'var(--bg)' }}>
                <td className="p-3 font-mono text-xs">{a.agency_key}</td>
                <td className="p-3">{a.display_name}</td>
                <td className="p-3">
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: a.os_type === 'LINUX' ? '#fef3c7' : '#dbeafe' }}>
                    {a.os_type}
                  </span>
                </td>
                <td className="p-3 font-mono text-xs">{a.agent_version || '-'}</td>
                <td className="p-3 text-xs" style={{ color: 'var(--muted)' }}>
                  {a.last_seen_at ? new Date(a.last_seen_at).toLocaleString() : 'Nunca'}
                </td>
                <td className="p-3">
                  <span className={`inline-block w-2 h-2 rounded-full mr-1 ${a.is_active ? 'bg-green-500' : 'bg-gray-400'}`} />
                  {a.is_active ? 'Activa' : 'Inactiva'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
