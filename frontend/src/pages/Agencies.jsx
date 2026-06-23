import { useState, useEffect } from 'react';
import { api } from '../api';
import { StatusBadge } from './Dashboard';

const SOURCE_TYPES = [
  { value: '', label: '— Sin fuente —' },
  { value: 'UKG', label: 'UKG Pro' },
  { value: 'SAP', label: 'SAP SuccessFactors' },
  { value: 'ORACLE', label: 'Oracle HCM' },
];

const CONNECTION_TYPES = [
  { value: 'API_KEY', label: 'API Key (RICE Reports)' },
  { value: 'USER_PASS', label: 'Username / Password (OAuth 2.0)' },
];

export default function Agencies() {
  const [agencies, setAgencies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ agency_key: '', display_name: '', hostname: '', os_type: 'LINUX' });

  // Source configuration modal
  const [sourceModal, setSourceModal] = useState(null); // agency object
  const [sourceForm, setSourceForm] = useState({});
  const [saving, setSaving] = useState(false);

  const load = () => api.getAgencies().then(setAgencies).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    await api.createAgency(form);
    setForm({ agency_key: '', display_name: '', hostname: '', os_type: 'LINUX' });
    setShowForm(false);
    load();
  };

  const openSourceModal = (agency) => {
    setSourceModal(agency);
    setSourceForm({
      source_type: agency.source_type || '',
      connection_type: agency.connection_type || 'USER_PASS',
      api_key: agency.api_key || '',
      client_id: agency.client_id || '',
      client_secret: agency.client_secret || '',
      source_url: agency.source_url || '',
      rice_ids: agency.rice_ids || '',
    });
  };

  const handleSaveSource = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const riceArray = sourceForm.rice_ids
        ? sourceForm.rice_ids.split(',').map(r => r.trim()).filter(Boolean)
        : [];
      await api.configureSource(sourceModal.agency_key, {
        source_type: sourceForm.source_type,
        connection_type: sourceForm.source_type === 'UKG' ? sourceForm.connection_type : null,
        api_key: sourceForm.api_key,
        client_id: sourceForm.client_id || null,
        client_secret: sourceForm.client_secret || null,
        source_url: sourceForm.source_url || null,
        rice_ids: sourceForm.source_type === 'UKG' && sourceForm.connection_type === 'API_KEY' ? riceArray : null,
      });
      setSourceModal(null);
      load();
    } catch (err) {
      alert('Error: ' + err.message);
    }
    setSaving(false);
  };

  const sourceLabel = (a) => {
    if (!a.source_type) return <span style={{ color: 'var(--muted)' }}>—</span>;
    let label = a.source_type;
    if (a.source_type === 'UKG' && a.connection_type) {
      label += ` · ${a.connection_type === 'API_KEY' ? '🔑 API Key' : '🔐 OAuth2'}`;
    }
    return <span className="text-xs font-medium px-2 py-0.5 rounded" 
      style={{ background: '#fef3c7', color: '#92400e' }}>{label}</span>;
  };

  const riceBadge = (a) => {
    if (!a.rice_ids) return <span style={{ color: 'var(--muted)' }}>—</span>;
    const ids = a.rice_ids.split(',').filter(Boolean);
    return (
      <span className="text-xs font-mono" style={{ color: 'var(--gov-navy)' }}>
        {ids.map((id, i) => (
          <span key={id} className="inline-block px-1.5 py-0.5 mr-1 rounded" 
            style={{ background: '#e0e7ff' }}>
            {id.trim()}
          </span>
        ))}
      </span>
    );
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
            <input required placeholder="Nombre" value={form.display_name}
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

      <div className="rounded-lg border overflow-x-auto" style={{ borderColor: 'var(--border)' }}>
        <table className="w-full text-sm">
          <thead style={{ background: 'var(--sidebar)', color: '#fff' }}>
            <tr>
              <th className="text-left p-3">Key</th>
              <th className="text-left p-3">Agencia</th>
              <th className="text-left p-3">OS</th>
              <th className="text-left p-3">Source</th>
              <th className="text-left p-3">Conexión</th>
              <th className="text-left p-3">RICE Reports</th>
              <th className="text-left p-3">Agent</th>
              <th className="text-left p-3">Último ping</th>
              <th className="text-left p-3">Estado</th>
              <th className="text-left p-3">Acción</th>
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
                <td className="p-3">{sourceLabel(a)}</td>
                <td className="p-3 text-xs">
                  {a.connection_type ? (
                    <span className="px-2 py-0.5 rounded" style={{ 
                      background: a.connection_type === 'API_KEY' ? '#fef3c7' : '#dbeafe',
                      color: a.connection_type === 'API_KEY' ? '#92400e' : '#1e40af' 
                    }}>
                      {a.connection_type === 'API_KEY' ? 'API Key' : 'User/Pass'}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--muted)' }}>—</span>
                  )}
                </td>
                <td className="p-3">{riceBadge(a)}</td>
                <td className="p-3 font-mono text-xs">{a.agent_version || '-'}</td>
                <td className="p-3 text-xs" style={{ color: 'var(--muted)' }}>
                  {a.last_seen_at ? new Date(a.last_seen_at).toLocaleString() : 'Nunca'}
                </td>
                <td className="p-3">
                  <span className={`inline-block w-2 h-2 rounded-full mr-1 ${a.is_active ? 'bg-green-500' : 'bg-gray-400'}`} />
                  {a.is_active ? 'Activa' : 'Inactiva'}
                </td>
                <td className="p-3">
                  <button
                    onClick={() => openSourceModal(a)}
                    className="px-3 py-1 rounded text-xs font-medium text-white"
                    style={{ background: 'var(--gov-navy)' }}
                  >
                    ⚙️ Source
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Source Configuration Modal */}
      {sourceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="rounded-xl shadow-2xl p-6 w-full max-w-lg" style={{ background: '#fff' }}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold" style={{ color: 'var(--gov-navy)' }}>
                ⚙️ Configurar Source — {sourceModal.agency_key}
              </h3>
              <button onClick={() => setSourceModal(null)} className="text-xl" style={{ color: 'var(--muted)' }}>✕</button>
            </div>

            <form onSubmit={handleSaveSource} className="space-y-3">
              {/* Source Type */}
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--dark)' }}>Data Source</label>
                <select value={sourceForm.source_type}
                  onChange={e => setSourceForm({ ...sourceForm, source_type: e.target.value })}
                  className="w-full p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }}>
                  {SOURCE_TYPES.map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>

              {/* Connection Type (only for UKG) */}
              {sourceForm.source_type === 'UKG' && (
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: 'var(--dark)' }}>Tipo de Conexión</label>
                  <select value={sourceForm.connection_type}
                    onChange={e => setSourceForm({ ...sourceForm, connection_type: e.target.value })}
                    className="w-full p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }}>
                    {CONNECTION_TYPES.map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* API Key (always shown) */}
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--dark)' }}>
                  {sourceForm.source_type === 'UKG' && sourceForm.connection_type === 'API_KEY' ? 'X-US-API-Key' : 'API Key / Tenant Key'}
                </label>
                <input type="text" value={sourceForm.api_key}
                  onChange={e => setSourceForm({ ...sourceForm, api_key: e.target.value })}
                  placeholder="us-api-key-ogp-abc123..."
                  className="w-full p-2 border rounded text-sm font-mono" style={{ borderColor: 'var(--border)' }} />
              </div>

              {/* OAuth2 fields (USER_PASS mode or non-UKG) */}
              {(sourceForm.source_type !== 'UKG' || sourceForm.connection_type === 'USER_PASS') && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--dark)' }}>Client ID</label>
                      <input type="text" value={sourceForm.client_id}
                        onChange={e => setSourceForm({ ...sourceForm, client_id: e.target.value })}
                        placeholder="abc123..."
                        className="w-full p-2 border rounded text-sm font-mono" style={{ borderColor: 'var(--border)' }} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--dark)' }}>Client Secret</label>
                      <input type="password" value={sourceForm.client_secret}
                        onChange={e => setSourceForm({ ...sourceForm, client_secret: e.target.value })}
                        placeholder="••••••••"
                        className="w-full p-2 border rounded text-sm font-mono" style={{ borderColor: 'var(--border)' }} />
                    </div>
                  </div>
                </>
              )}

              {/* Base URL */}
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--dark)' }}>Base URL</label>
                <input type="text" value={sourceForm.source_url}
                  onChange={e => setSourceForm({ ...sourceForm, source_url: e.target.value })}
                  placeholder="https://api.ultipro.com"
                  className="w-full p-2 border rounded text-sm font-mono" style={{ borderColor: 'var(--border)' }} />
              </div>

              {/* RICE IDs (only UKG + API_KEY) */}
              {sourceForm.source_type === 'UKG' && sourceForm.connection_type === 'API_KEY' && (
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: 'var(--dark)' }}>
                    RICE Report IDs
                    <span className="ml-1" style={{ color: 'var(--muted)' }}>(separados por coma)</span>
                  </label>
                  <input type="text" value={sourceForm.rice_ids}
                    onChange={e => setSourceForm({ ...sourceForm, rice_ids: e.target.value })}
                    placeholder="RPT001, RPT002, RPT003"
                    className="w-full p-2 border rounded text-sm font-mono" style={{ borderColor: 'var(--border)' }} />
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button type="submit" disabled={saving}
                  className="px-4 py-2 rounded text-white text-sm font-medium flex-1"
                  style={{ background: 'var(--primary)' }}>
                  {saving ? 'Guardando...' : '💾 Guardar Configuración'}
                </button>
                <button type="button" onClick={() => setSourceModal(null)}
                  className="px-4 py-2 rounded text-sm border" style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
