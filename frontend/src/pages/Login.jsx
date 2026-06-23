import { useState } from 'react';

// ─── Boomi-inspired Login Page ──────────────────────────────
export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Simple auth — in production, call Hub API
      if (username && password) {
        await new Promise(r => setTimeout(r, 600)); // simulate
        onLogin({ username });
      } else {
        setError('Usuario y contraseña requeridos');
      }
    } catch {
      setError('Error de autenticación');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <style>{`
        .fbib-login-input:focus {
          border-color: #0D6EFD !important;
          box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.15) !important;
        }
        .fbib-login-input:hover {
          border-color: #ADB5BD !important;
        }
        .fbib-login-btn:hover {
          background: #0B5ED7 !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(13, 110, 253, 0.3);
        }
        .fbib-login-btn:active {
          transform: translateY(0);
        }
      `}</style>

      {/* ─── Left Panel: Brand ─────────────────────────── */}
      <div style={styles.leftPanel}>
        <div style={styles.brandContent}>
          <div style={styles.logoArea}>
            <div style={styles.logoIcon}>⬡</div>
            <h1 style={styles.brandName}>FBIB Deploy Hub</h1>
            <div style={styles.goldLine} />
            <p style={styles.brandSub}>Oficina de Gerencia y Presupuesto</p>
            <p style={styles.brandGov}>Gobierno de Puerto Rico</p>
          </div>

          <div style={styles.features}>
            <div style={styles.feature}>
              <span style={styles.featureIcon}>🔄</span>
              <span style={styles.featureText}>Despliegue automatizado</span>
            </div>
            <div style={styles.feature}>
              <span style={styles.featureIcon}>📦</span>
              <span style={styles.featureText}>Réplicas de datos SQLite</span>
            </div>
            <div style={styles.feature}>
              <span style={styles.featureIcon}>🔒</span>
              <span style={styles.featureText}>Read-only · SHA-256 · Ley 126</span>
            </div>
          </div>
        </div>

        <div style={styles.leftFooter}>
          <span style={styles.version}>v1.1 · Admin Portal</span>
        </div>
      </div>

      {/* ─── Right Panel: Login Form ────────────────────── */}
      <div style={styles.rightPanel}>
        <div style={styles.formCard}>
          <h2 style={styles.formTitle}>Iniciar Sesión</h2>
          <p style={styles.formSub}>
            Accede al panel de administración
          </p>

          <form onSubmit={handleSubmit} style={styles.form}>
            <div style={styles.fieldGroup}>
              <label style={styles.label}>Usuario</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin@ogp.pr.gov"
                className="fbib-login-input"
                style={styles.input}
                autoFocus
              />
            </div>

            <div style={styles.fieldGroup}>
              <label style={styles.label}>Contraseña</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="fbib-login-input"
                style={styles.input}
              />
            </div>

            {error && (
              <div style={styles.errorBox}>
                <span>⚠</span> {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className={`fbib-login-btn${loading ? ' fbib-login-btn-loading' : ''}`}
              style={{
                ...styles.submitBtn,
              }}
            >
              {loading ? 'Autenticando...' : 'Entrar'}
            </button>
          </form>

          <div style={styles.formFooter}>
            <span style={styles.formFooterText}>
              ¿Primera vez? Contacta a OGP — División de Tecnología
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Styles (Boomi-inspired + PRITS palette) ────────────────
const PRITS = {
  navy: '#12223A',
  navyLight: '#1C2854',
  gold: '#E5BD44',
  primary: '#0D6EFD',
  primaryHover: '#0B5ED7',
  bg: '#F8F9FB',
  white: '#FFFFFF',
  text: '#212529',
  muted: '#6C757D',
  border: '#DEE2E6',
  danger: '#DC3545',
  dangerBg: '#F8D7DA',
};

const styles = {
  container: {
    display: 'flex',
    minHeight: '100vh',
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
  },

  // ─── Left Panel ─────────────────────────────────
  leftPanel: {
    flex: '0 0 44%',
    background: `linear-gradient(160deg, ${PRITS.navy} 0%, ${PRITS.navyLight} 100%)`,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '60px 48px',
    position: 'relative',
    overflow: 'hidden',
  },

  brandContent: {
    textAlign: 'center',
    maxWidth: '400px',
  },

  logoArea: {
    marginBottom: '48px',
  },

  logoIcon: {
    fontSize: '48px',
    marginBottom: '16px',
    filter: 'drop-shadow(0 2px 8px rgba(229, 189, 68, 0.3))',
  },

  brandName: {
    fontSize: '32px',
    fontWeight: '700',
    color: PRITS.white,
    margin: '0 0 4px 0',
    letterSpacing: '-0.5px',
  },

  goldLine: {
    width: '48px',
    height: '3px',
    background: PRITS.gold,
    margin: '16px auto',
    borderRadius: '2px',
  },

  brandSub: {
    fontSize: '14px',
    color: PRITS.gold,
    margin: 0,
    fontWeight: '500',
    letterSpacing: '0.3px',
  },

  brandGov: {
    fontSize: '12px',
    color: '#AEC1E1',
    margin: '4px 0 0 0',
    fontWeight: '400',
  },

  features: {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
    marginTop: '32px',
  },

  feature: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '10px 16px',
    background: 'rgba(255, 255, 255, 0.06)',
    borderRadius: '8px',
    border: '1px solid rgba(255, 255, 255, 0.08)',
  },

  featureIcon: {
    fontSize: '20px',
    flexShrink: 0,
  },

  featureText: {
    fontSize: '13px',
    color: '#C8D6E5',
    fontWeight: '400',
  },

  leftFooter: {
    position: 'absolute',
    bottom: '24px',
    left: '48px',
  },

  version: {
    fontSize: '11px',
    color: '#6C7A8A',
  },

  // ─── Right Panel ─────────────────────────────────
  rightPanel: {
    flex: '1',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    background: PRITS.bg,
    padding: '40px',
  },

  formCard: {
    width: '100%',
    maxWidth: '400px',
  },

  formTitle: {
    fontSize: '26px',
    fontWeight: '600',
    color: PRITS.navy,
    margin: '0 0 4px 0',
  },

  formSub: {
    fontSize: '14px',
    color: PRITS.muted,
    margin: '0 0 32px 0',
  },

  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },

  fieldGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },

  label: {
    fontSize: '13px',
    fontWeight: '600',
    color: PRITS.text,
    letterSpacing: '0.3px',
  },

  input: {
    padding: '11px 14px',
    fontSize: '14px',
    border: `1.5px solid ${PRITS.border}`,
    borderRadius: '8px',
    outline: 'none',
    background: PRITS.white,
    color: PRITS.text,
    transition: 'border-color 0.15s, box-shadow 0.15s',
    fontFamily: 'inherit',
  },

  errorBox: {
    padding: '10px 14px',
    fontSize: '13px',
    color: PRITS.danger,
    background: PRITS.dangerBg,
    borderRadius: '6px',
    border: `1px solid #F5C6CB`,
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },

  submitBtn: {
    padding: '12px 24px',
    fontSize: '15px',
    fontWeight: '600',
    color: PRITS.white,
    background: PRITS.primary,
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'background 0.15s, transform 0.1s',
    fontFamily: 'inherit',
    marginTop: '4px',
  },

  submitBtnLoading: {
    opacity: 0.7,
    cursor: 'not-allowed',
  },

  formFooter: {
    marginTop: '32px',
    paddingTop: '20px',
    borderTop: `1px solid ${PRITS.border}`,
    textAlign: 'center',
  },

  formFooterText: {
    fontSize: '12px',
    color: PRITS.muted,
  },
};
