# FBIB Deploy Hub

**Sistema de despliegue remoto para gobierno. Push updates a múltiples agencias. Linux + Windows. SHA-256 audit chain. Rollback automático.**

```
┌─────────────────────────────────────────────────────────────┐
│                    FBIB DEPLOY HUB                            │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ADMIN PORTAL (React)                                │    │
│  │  • Crear releases, subir artifacts                   │    │
│  │  • Seleccionar agencias, lanzar deployment           │    │
│  │  • Dashboard: estado en tiempo real                  │    │
│  │  • Rollback con un click                             │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────┐    │
│  │  HUB API (FastAPI :8900)                             │    │
│  │  • Registry: apps, releases, agencies, deployments   │    │
│  │  • Artifact storage + SHA-256 verification           │    │
│  │  • Agent endpoints: pending, download, report         │    │
│  │  • Audit chain: SHA-256 per deployment (Ley 126)     │    │
│  └──────────┬──────────────────────┬───────────────────┘    │
│             │                      │                         │
│    ┌────────▼────────┐    ┌───────▼────────┐                │
│    │  AGENT (Linux)  │    │ AGENT (Windows)│   ← Agencias   │
│    │  • Poll pending │    │  • Poll pending │                │
│    │  • Download +   │    │  • Download +   │                │
│    │    verify SHA   │    │    verify SHA   │                │
│    │  • Backup prev  │    │  • Backup prev  │                │
│    │  • Install +    │    │  • Install +    │                │
│    │    run script   │    │    run script   │                │
│    │  • Report back  │    │  • Report back  │                │
│    └─────────────────┘    └────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏛️ Para Agencias — Descargar y Ejecutar (1 minuto)

### Linux

```bash
# 1. Descargar el ejecutable (no necesita Python ni nada)
wget https://github.com/jcollazo/fbib-deploy-hub/releases/latest/download/fbib-agent-linux
chmod +x fbib-agent-linux

# 2. Ejecutar (reemplaza 'ogp' con tu key)
./fbib-agent-linux --agency-key ogp --hub-url https://hub.pr.gov

# 3. (Opcional) Instalar como servicio para que corra siempre
sudo ./fbib-agent-linux --agency-key ogp --hub-url https://hub.pr.gov --install-service
```

### Windows

```powershell
# 1. Descargar el ejecutable
Invoke-WebRequest -Uri "https://github.com/jcollazo/fbib-deploy-hub/releases/latest/download/fbib-agent-windows.exe" -OutFile "fbib-agent.exe"

# 2. Ejecutar (doble click o desde terminal)
.\fbib-agent.exe --agency-key hacienda --hub-url https://hub.pr.gov

# 3. (Opcional) Instalar como servicio Windows
.\fbib-agent.exe --agency-key hacienda --hub-url https://hub.pr.gov --install-service
```

> ⚡ **Cero dependencias.** El ejecutable incluye Python, requests, y todo lo necesario. ~8 MB.

### Ver tu portal

Después de que el Agent esté corriendo, visita:
```
https://hub.pr.gov/agency/tu-key
```
Ejemplos: `/agency/ogp`, `/agency/hacienda`, `/agency/justicia`

### Sincronizar datos a la DB local de la agencia

Si la agencia necesita los datos en su propia base de datos:

```bash
# 1. La agencia crea un usuario en su DB
#    (SQL Server, Oracle, o PostgreSQL)
CREATE USER fbib_sync WITH PASSWORD='***';
GRANT INSERT, UPDATE ON empleados TO fbib_sync;

# 2. Ejecutar el Agent con --db-conn
./fbib-agent-linux \
  --agency-key ogp \
  --hub-url https://hub.pr.gov \
  --db-conn "DRIVER={ODBC Driver 18 for SQL Server};SERVER=10.0.1.50;DATABASE=HR;UID=fbib_sync;PWD=***"

# El Agent ahora:
# → Cada 60s: revisa si hay software nuevo → despliega
# → Cada 60s: revisa si hay datos nuevos → sincroniza a DB local
# → Cero intervención humana
```

---

## 🚀 Quick Start (OGP Admin)

### 1. Hub Server (Central)

```bash
# Configurar base de datos
export FBIB_DEPLOY_DB="DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=FBIBDeployHub;..."

# Crear tablas
sqlcmd -S localhost -d FBIBDeployHub -i sql/00_registry.sql

# Instalar dependencias
pip install -r requirements.txt

# Iniciar hub
python src/hub.py
# → http://localhost:8900
# → API docs: http://localhost:8900/docs
```

### 2. Registrar aplicación y release

```bash
# Registrar app
curl -X POST localhost:8900/api/apps \
  -H "Content-Type: application/json" \
  -d '{"app_key":"oatrh-portal","display_name":"Portal OATRH","artifact_type":"ZIP"}'

# Crear release
curl -X POST localhost:8900/api/releases \
  -H "Content-Type: application/json" \
  -d '{"app_key":"oatrh-portal","release_tag":"v2.1.0","version_semver":"2.1.0"}'

# Subir artifact
curl -X POST localhost:8900/api/releases/1/upload \
  -F "file=@/path/to/oatrh-portal-v2.1.0.zip"
```

### 3. Agente en cada agencia (Linux)

```bash
# Instalar
pip install requests

# Ejecutar (systemd o manual)
python src/agent.py \
  --agency-key ogp \
  --hub-url https://hub.pr.gov \
  --poll-interval 60

# Systemd service (Linux)
sudo tee /etc/systemd/system/fbib-agent.service << 'EOF'
[Unit]
Description=FBIB Deploy Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/fbib-agent/agent.py --agency-key ogp --hub-url https://hub.pr.gov
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now fbib-agent
```

### 4. Agente en Windows

```powershell
# Instalar Python 3.12+ + requests
pip install requests

# Ejecutar (NSSM para servicio)
python src/agent.py --agency-key hacienda --hub-url https://hub.pr.gov

# O instalar como servicio Windows con NSSM
nssm install FBIBAgent "C:\Python312\python.exe" "C:\fbib-agent\agent.py --agency-key hacienda --hub-url https://hub.pr.gov"
nssm start FBIBAgent
```

---

## 🔄 Flujo de un Deployment

```
1. Admin sube release + artifact al Hub
2. Admin crea deployment → selecciona agencias
3. Agents en cada agencia hacen polling → detectan PENDING
4. Agent descarga artifact → verifica SHA-256
5. Agent hace backup de la versión actual (últimos 3)
6. Agent extrae + ejecuta deploy script (bash o PowerShell)
7. Agent reporta SUCCESS o FAILED al Hub
8. Hub registra en audit chain SHA-256
9. Si algo falla → Admin hace rollback desde el portal
```

---

## 🛡️ Seguridad

| Capa | Protección |
|---|---|
| **Agent ↔ Hub** | HTTPS (TLS 1.3) |
| **Artifact** | SHA-256 verification antes de instalar |
| **Backup** | 3 versiones anteriores guardadas localmente |
| **Rollback** | Restaurar backup con un comando/click |
| **Audit** | SHA-256 hash chain por deployment (Ley 126-2012) |
| **Agent identity** | Agency key + IP allowlist (futuro: mTLS) |

---

## 📁 Estructura

```
fbib-deploy-hub/
├── src/
│   ├── hub.py           # Central API server (FastAPI)
│   └── agent.py         # Cross-platform agent (Linux + Windows)
├── sql/
│   └── 00_registry.sql  # Database schema
├── requirements.txt
└── README.md
```

---

## 📝 Licencia

Internal — Gobierno de Puerto Rico
