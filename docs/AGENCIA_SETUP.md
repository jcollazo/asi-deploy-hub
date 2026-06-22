# ASI Agent — Guía de Configuración para Agencias

> **Versión:** 1.0 | **Idioma:** Español | **Sistema Operativo:** Linux + Windows

---

## 1. ¿Qué es el ASI Agent?

El ASI Agent es el equivalente a un **Boomi Atom**, pero sin licencias, sin Java, y sin permisos de escritura en tu base de datos.

```
┌─────────────────────────────────────────────────────────┐
│                    OGP CENTRAL                           │
│                                                          │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────┐   │
│  │ SQL Srv  │   │ Hub API      │   │ PR Integ Hub   │   │
│  │ (master) │   │ :8900        │   │ (ETL)          │   │
│  └────┬─────┘   └──────┬───────┘   └───────┬────────┘   │
│       │                │                   │             │
│       │    ┌───────────┴──────────┐        │             │
│       │    │  API read-only       │        │             │
│       │    │  GET /api/data/{key} │        │             │
│       │    └───────────┬──────────┘        │             │
└───────┼────────────────┼───────────────────┼─────────────┘
        │                │                   │
        ▼                ▼                   │
┌───────────────────────────────────────────┼─────────────┐
│              TU AGENCIA                    │             │
│                                            │             │
│  ┌──────────────────────────────────────┐ │             │
│  │  ASI Agent (8 MB ejecutable)         │ │             │
│  │                                      │ │             │
│  │  🔄 Cada 60s:                        │ │             │
│  │  • ¿Nuevo release de mi app? → Instala│ │             │
│  │  • ¿Hub está vivo? → Heartbeat       │ │             │
│  │  • NUNCA escribe en tu DB            │ │             │
│  └──────────────────────────────────────┘ │             │
│                                            │             │
│  ┌──────────────────────────────────────┐ │             │
│  │  TU APLICACIÓN (Sistema de RH, etc.) │ │             │
│  │                                      │ │             │
│  │  🔍 Lee datos del Hub:               │ │             │
│  │  • SELECT * FROM empleados (read-only)│ │             │
│  │  • GET /api/data (REST API)          │ │             │
│  └──────────────────────────────────────┘ │             │
└────────────────────────────────────────────┘             │
```

**El Agent solo despliega software. NO escribe en tu base de datos.**

---

## 2. Descargar el Agent

### Linux (x86_64)
```bash
wget https://github.com/jcollazo/asi-deploy-hub/releases/latest/download/asi-agent-linux
chmod +x asi-agent-linux
sudo mv asi-agent-linux /usr/local/bin/
```

### Windows (x86_64)
```powershell
Invoke-WebRequest -Uri "https://github.com/jcollazo/asi-deploy-hub/releases/latest/download/asi-agent-windows.exe" -OutFile "C:\ProgramData\ASIAgent\asi-agent.exe"
```

**Tamaño:** ~8 MB | **Dependencias:** NINGUNA (ejecutable standalone)

---

## 3. Lo que OGP te entrega

Antes de configurar el Agent, OGP te proporciona:

| Dato | Ejemplo | Descripción |
|---|---|---|
| **Agency Key** | `ogp`, `hacienda`, `dtop` | Identificador único de tu agencia |
| **Hub URL** | `https://hub.pr.gov` | URL del ASI Deploy Hub central |
| **DB Connection String** | `DRIVER={ODBC...};SERVER=10.0.1.50;...` | String de conexión a SQL Server (solo SELECT) |
| **API Key** | `asi_live_abc123...` | Key para autenticación REST (si usas API) |

> **IMPORTANTE:** El usuario de base de datos que OGP te entrega tiene SOLO permisos de SELECT (lectura).
> No puede hacer INSERT, UPDATE, ni DELETE. Tus datos están protegidos.

---

## 4. Configuración del Agent

### 4.1 Probar el Agent (modo manual)

```bash
# Linux
asi-agent-linux \
  --agency-key ogp \
  --hub-url https://hub.pr.gov \
  --once

# Windows
C:\ProgramData\ASIAgent\asi-agent.exe ^
  --agency-key ogp ^
  --hub-url https://hub.pr.gov ^
  --once
```

**Salida esperada:**
```
2026-06-22 10:00:01 [INFO] ASI Agent v1.0.0 starting for agency 'ogp'
2026-06-22 10:00:01 [INFO]   OS: Linux 6.8.0 | Python: 3.13 | Hub: https://hub.pr.gov
2026-06-22 10:00:02 [INFO] Heartbeat sent. Status: 200
No pending deployments.
```

### 4.2 Instalar como Servicio (recomendado)

#### Linux (systemd)

```bash
# 1. Ejecutar el instalador
sudo asi-agent-linux \
  --agency-key ogp \
  --hub-url https://hub.pr.gov \
  --install-service

# 2. Copiar el archivo de servicio generado
sudo cp /tmp/asi-agent-ogp.service /etc/systemd/system/

# 3. Activar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable --now asi-agent-ogp

# 4. Verificar
sudo systemctl status asi-agent-ogp
sudo journalctl -u asi-agent-ogp -f    # logs en tiempo real
```

El Agent se ejecuta como servicio. Si el servidor se reinicia, el Agent arranca automáticamente.

#### Windows (NSSM)

```powershell
# 1. Descargar NSSM (una sola vez)
# https://nssm.cc/download

# 2. Instalar el servicio
nssm install ASIAgent C:\ProgramData\ASIAgent\asi-agent.exe
nssm set ASIAgent AppParameters "--agency-key ogp --hub-url https://hub.pr.gov"
nssm set ASIAgent DisplayName "ASI Deploy Agent (OGP)"
nssm set ASIAgent Start SERVICE_AUTO_START

# 3. Iniciar
nssm start ASIAgent

# 4. Verificar estado
nssm status ASIAgent
```

---

## 5. Conectar tu Aplicación a los Datos (Read-Only)

Tu aplicación necesita leer datos desde el SQL Server central de OGP. **Dos opciones:**

### Opción A — Connection String Directo (más rápido)

OGP te entrega un connection string con un usuario que solo tiene `GRANT SELECT`.

```python
# Ejemplo en Python
import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=hub.pr.gov,1433;"
    "DATABASE=CentralDB;"
    "UID=agencia_ogp;"
    "PWD=tuPasswordSegura;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM empleados WHERE agencia='OGP'")
for row in cursor:
    print(row)
```

```java
// Ejemplo en Java (JDBC)
String url = "jdbc:sqlserver://hub.pr.gov:1433;database=CentralDB;user=agencia_ogp;password=***;encrypt=true";
Connection conn = DriverManager.getConnection(url);
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery("SELECT * FROM empleados WHERE agencia='OGP'");
```

```csharp
// Ejemplo en C# (.NET)
using var conn = new SqlConnection(
    "Server=hub.pr.gov,1433;Database=CentralDB;User Id=agencia_ogp;Password=***;Encrypt=True;"
);
conn.Open();
using var cmd = new SqlCommand("SELECT * FROM empleados WHERE agencia='OGP'", conn);
using var reader = cmd.ExecuteReader();
```

**Qué NO puedes hacer con este usuario:**
```
❌ INSERT INTO empleados ...
❌ UPDATE empleados SET ...
❌ DELETE FROM empleados ...
❌ DROP TABLE ...
❌ CREATE TABLE ...

✅ SELECT * FROM empleados ...
✅ SELECT COUNT(*) FROM empleados ...
✅ JOIN entre tablas permitidas
```

### Opción B — REST API (más seguro, sin acceso directo a DB)

OGP te entrega una API Key. Tu aplicación consume datos vía HTTP.

```bash
# Ejemplo con curl
curl -H "Authorization: Bearer asi_live_abc123..." \
     "https://hub.pr.gov/api/data/empleados?agencia=ogp"
```

```python
# Ejemplo en Python
import requests

headers = {"Authorization": "Bearer asi_live_abc123..."}
resp = requests.get(
    "https://hub.pr.gov/api/data/empleados",
    params={"agencia": "ogp"},
    headers=headers,
)
data = resp.json()
for emp in data["empleados"]:
    print(emp["first_name"], emp["last_name"])
```

```javascript
// Ejemplo en JavaScript (React, Node)
const resp = await fetch(
  "https://hub.pr.gov/api/data/empleados?agencia=ogp",
  { headers: { Authorization: "Bearer asi_live_abc123..." } }
);
const data = await resp.json();
```

**Ventajas de la API:**
- Tu aplicación nunca toca la base de datos
- Rate limiting (100 req/min por agencia)
- Logs de acceso por API key
- Sin necesidad de instalar ODBC/JDBC drivers

---

## 6. Verificación — Checklist

Después de configurar, verifica cada paso:

| # | Verificación | Comando | Esperado |
|---|---|---|---|
| 1 | Agent instalado | `asi-agent-linux --help` | Muestra ayuda |
| 2 | Agent conecta al Hub | `asi-agent-linux --agency-key ogp --hub-url https://hub.pr.gov --once` | "No pending deployments" |
| 3 | Servicio corriendo | `systemctl status asi-agent-ogp` | `active (running)` |
| 4 | Heartbeat en Hub | Pregunta a OGP | "Last heartbeat: hace 1 min" |
| 5 | Conexión DB (SELECT) | `sqlcmd -S hub.pr.gov -U agencia_ogp -P *** -Q "SELECT 1"` | `1` |
| 6 | Conexión DB (INSERT) | `sqlcmd -S hub.pr.gov -U agencia_ogp -P *** -Q "INSERT INTO test VALUES(1)"` | **ERROR** (permiso denegado) |
| 7 | API responde | `curl -H "Authorization: Bearer KEY" https://hub.pr.gov/api/data/empleados?agencia=ogp` | JSON con empleados |

---

## 7. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Connection refused` | Hub URL mal o Hub caído | Verifica la URL con OGP. Prueba `curl https://hub.pr.gov/health` |
| `Agency not found` | Agency key incorrecta | Confirma tu agency key con OGP |
| `Login failed for user` | Connection string mal | Verifica usuario/contraseña. Pide a OGP que regenere credenciales |
| `INSERT permission denied` | **Está bien.** Es por diseño | No tienes permisos de escritura. Usa SELECT. |
| `Heartbeat failed` | Firewall bloquea salida | Abre puerto 443/TCP saliente hacia `hub.pr.gov` |
| Agent no arranca tras reboot | Servicio no enabled | `systemctl enable asi-agent-ogp` |
| `No module named pyodbc` | Tu app necesita ODBC driver | Instala ODBC Driver 18 for SQL Server |

---

## 8. Resumen — Lo que la Agencia Necesita Hacer

```
┌─────────────────────────────────────────────────────────────┐
│  PASO 1 — Descargar Agent (8 MB)                            │
│  wget https://github.com/.../asi-agent-linux                │
│                                                              │
│  PASO 2 — Instalar como servicio                             │
│  asi-agent-linux --agency-key ogp --hub-url ... --install    │
│  sudo cp /tmp/asi-agent-ogp.service /etc/systemd/system/     │
│  sudo systemctl enable --now asi-agent-ogp                  │
│                                                              │
│  PASO 3 — Conectar tu aplicación a los datos                 │
│  Opción A: Connection string SELECT-only                    │
│  Opción B: REST API con API key                             │
│                                                              │
│  PASO 4 — Verificar                                         │
│  systemctl status asi-agent-ogp → active (running)          │
│  SELECT * FROM empleados → datos                            │
│  INSERT INTO empleados → PERMISSION DENIED ✓                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🆚 Comparativa: ASI Agent vs Boomi Atom

| | Boomi Atom | ASI Agent |
|---|---|---|
| **Descargar** | Java 11+ JDK + Atom installer (~500 MB) | 1 ejecutable (~8 MB) |
| **Instalar** | Wizard gráfico o script complejo | 1 comando |
| **Servicio** | Configuración manual | `--install-service` automático (systemd / NSSM) |
| **Tiempo de setup** | 30-60 min (con IT) | **3 minutos** |
| **Licencia** | $550/mes por agencia | **$0** |
| **Escribe en DB** | INSERT / UPDATE / DELETE | **NUNCA escribe** (solo despliega software) |
| **Actualizar** | Download manual + re-run wizard | Reemplazar ejecutable |
| **Firewall** | Múltiples puertos (HTTP, JDBC, etc.) | 1 puerto: 443/TCP saliente |

---

> **¿Preguntas?** Contacta a la Oficina de Gerencia de Presupuesto — División de Tecnología
