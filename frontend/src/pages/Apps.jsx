import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Apps() {
  const [apps, setApps] = useState([]);
  const [releases, setReleases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedApp, setSelectedApp] = useState(null);
  const [showAppForm, setShowAppForm] = useState(false);
  const [showRelForm, setShowRelForm] = useState(false);
  const [appForm, setAppForm] = useState({ app_key: '', display_name: '', artifact_type: 'ZIP' });
  const [relForm, setRelForm] = useState({ app_key: '', release_tag: '', version_semver: '', release_notes: '' });
  const [uploadFile, setUploadFile] = useState(null);

  const loadApps = () => api.getApps().then(setApps);
  const loadReleases = (appKey) => api.getReleases(appKey).then(setReleases);

  useEffect(() => { loadApps().finally(() => setLoading(false)); }, []);

  const handleAppCreate = async (e) => {
    e.preventDefault();
    await api.createApp(appForm);
    setAppForm({ app_key: '', display_name: '', artifact_type: 'ZIP' });
    setShowAppForm(false);
    loadApps();
  };

  const handleRelCreate = async (e) => {
    e.preventDefault();
    await api.createRelease({ ...relForm, app_key: selectedApp });
    setRelForm({ app_key: '', release_tag: '', version_semver: '', release_notes: '' });
    setShowRelForm(false);
    loadReleases(selectedApp);
  };

  const handleUpload = async (releaseId) => {
    if (!uploadFile) return;
    await api.uploadArtifact(releaseId, uploadFile);
    setUploadFile(null);
    loadReleases(selectedApp);
  };

  if (loading) return <div className="text-muted">Cargando...</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-2xl font-bold" style={{ color: 'var(--gov-navy)' }}>Apps & Releases</h2>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>{apps.length} aplicaciones</p>
        </div>
        <button onClick={() => setShowAppForm(!showAppForm)} className="px-4 py-2 rounded-lg text-white text-sm font-medium" style={{ background: 'var(--primary)' }}>
          + Nueva App
        </button>
      </div>

      {showAppForm && (
        <form onSubmit={handleAppCreate} className="mb-6 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
          <div className="grid grid-cols-3 gap-3">
            <input required placeholder="Key (ej: oatrh-portal)" value={appForm.app_key}
              onChange={e => setAppForm({ ...appForm, app_key: e.target.value })}
              className="p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }} />
            <input required placeholder="Nombre" value={appForm.display_name}
              onChange={e => setAppForm({ ...appForm, display_name: e.target.value })}
              className="p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }} />
            <select value={appForm.artifact_type} onChange={e => setAppForm({ ...appForm, artifact_type: e.target.value })}
              className="p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }}>
              <option value="ZIP">ZIP</option>
              <option value="DOCKER">Docker</option>
              <option value="SQL_SCRIPT">SQL Script</option>
              <option value="PYTHON_WHEEL">Python Wheel</option>
              <option value="DOTNET_PUBLISH">.NET Publish</option>
            </select>
          </div>
          <button type="submit" className="mt-3 px-4 py-2 rounded text-white text-sm" style={{ background: 'var(--success)' }}>
            Guardar
          </button>
        </form>
      )}

      {/* Apps grid */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {apps.map(app => (
          <button
            key={app.id}
            onClick={() => { setSelectedApp(app.app_key); loadReleases(app.app_key); }}
            className="p-4 rounded-lg border text-left transition-shadow hover:shadow-md"
            style={{
              borderColor: selectedApp === app.app_key ? 'var(--gold)' : 'var(--border)',
              background: selectedApp === app.app_key ? '#fffdf5' : '#fff',
            }}
          >
            <p className="font-bold text-sm" style={{ color: 'var(--gov-navy)' }}>{app.display_name}</p>
            <p className="text-xs font-mono" style={{ color: 'var(--muted)' }}>{app.app_key}</p>
            <span className="inline-block mt-2 px-2 py-0.5 rounded text-xs" style={{ background: 'var(--bg)' }}>
              {app.artifact_type}
            </span>
          </button>
        ))}
      </div>

      {/* Releases for selected app */}
      {selectedApp && (
        <div>
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-lg font-bold" style={{ color: 'var(--gov-navy)' }}>
              Releases: <span className="font-mono">{selectedApp}</span>
            </h3>
            <button onClick={() => setShowRelForm(!showRelForm)} className="px-3 py-1.5 rounded text-white text-xs font-medium" style={{ background: 'var(--primary)' }}>
              + Nueva Release
            </button>
          </div>

          {showRelForm && (
            <form onSubmit={handleRelCreate} className="mb-4 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: '#fff' }}>
              <div className="grid grid-cols-4 gap-3">
                <input required placeholder="Tag (ej: v1.2.3)" value={relForm.release_tag}
                  onChange={e => setRelForm({ ...relForm, release_tag: e.target.value })}
                  className="p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }} />
                <input placeholder="Semver (ej: 1.2.3)" value={relForm.version_semver}
                  onChange={e => setRelForm({ ...relForm, version_semver: e.target.value })}
                  className="p-2 border rounded text-sm" style={{ borderColor: 'var(--border)' }} />
                <input placeholder="Release notes" value={relForm.release_notes}
                  onChange={e => setRelForm({ ...relForm, release_notes: e.target.value })}
                  className="p-2 border rounded text-sm col-span-2" style={{ borderColor: 'var(--border)' }} />
              </div>
              <button type="submit" className="mt-3 px-4 py-2 rounded text-white text-sm" style={{ background: 'var(--success)' }}>
                Crear Release
              </button>
            </form>
          )}

          <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
            <table className="w-full text-sm">
              <thead style={{ background: 'var(--sidebar)', color: '#fff' }}>
                <tr>
                  <th className="text-left p-3">Tag</th>
                  <th className="text-left p-3">Version</th>
                  <th className="text-left p-3">Hash</th>
                  <th className="text-left p-3">Size</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">Upload</th>
                </tr>
              </thead>
              <tbody>
                {releases.map((r, i) => (
                  <tr key={r.id} style={{ background: i % 2 ? '#fff' : 'var(--bg)' }}>
                    <td className="p-3 font-mono text-xs">{r.release_tag}</td>
                    <td className="p-3 font-mono text-xs">{r.version_semver || '-'}</td>
                    <td className="p-3 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                      {r.artifact_hash ? r.artifact_hash.substring(0, 16) + '...' : '-'}
                    </td>
                    <td className="p-3 text-xs">{r.artifact_size ? `${(r.artifact_size / 1024).toFixed(1)} KB` : '-'}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        r.status === 'PUBLISHED' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                      }`}>{r.status}</span>
                    </td>
                    <td className="p-3">
                      {r.status === 'DRAFT' && (
                        <div className="flex gap-2">
                          <input type="file" onChange={e => setUploadFile(e.target.files[0])} className="text-xs" />
                          <button onClick={() => handleUpload(r.id)}
                            className="px-2 py-1 rounded text-white text-xs" style={{ background: 'var(--success)' }}>
                            Subir
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
