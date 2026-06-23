# FBIB Agent — Guía de Configuración para Agencias

> **Versión:** 2.0 (Modelo Pull Directo — Agent jala de UKG/SAP/Oracle) | **Idioma:** Español | **SO:** Linux + Windows

---

## 1. ¿Qué es el FBIB Agent?

El FBIB Agent es el equivalente a un **Boomi Atom**, pero sin licencias, sin Java, y con **cero permisos de escritura** en tu base de datos. A diferencia de Boomi, el Agent **jala los datos directo de tu fuente** (UKG, SAP, u Oracle) — no depende de un ETL central.

```
┌─────────────────────────────────────────────────────────────────┐
│                         OGP CENTRAL                              │
│                                                                  │
│  ┌──────────────────┐   ┌──────────────────────┐                 │
│  │  Admin Portal    │   │  Hub API :8900       │                 │
│  │  (React)         │   │                      │                 │
│  │                  │   │  Configura:          │                 │
│  │  PUT /source     │   │  • source_type       │                 │
│  │  PUT /columns    │   │  • api_key (agencia) │                 │
│  │  (filtro opcional)│   │  • selected_columns  │                 │
│  └────────┬─────────┘   └──────────┬───────────┘                 │
│           │                        │                             │
└───────────┼────────────────────────┼─────────────────────────────┘
            │                        │
            │                        ▼ GET /api/agent/{key}/config
            │               ┌──────────────────────────────────────┐
            │               │          TU AGENCIA                   │
            │               │                                      │
            │               │  ┌────────────────────────────────┐  │
            │               │  │  FBIB Agent (8 MB)              │  │
            │               │  │                                │  │
            │               │  │  🔄 Cada 60s:                  │  │
            │               │  │  1. GET /config → source, creds│  │
            │               │  │  2. OAuth 2.0 → UKG/SAP/Oracle │  │
            │               │  │  3. GET employees (paginated)  │  │
            │               │  │  4. Columnas = API response    │  │
            │               │  │  5. Filtrar (si configurado)   │  │
            │               │  │  6. SQLite + chmod 444         │  │
            │               │  └───────────────┬────────────────┘  │
            │               │                  │                    │
            │               │                  ▼                    │
            │               │  ┌────────────────────────────────┐  │
            │               │  │  empleados.db                  │  │
            │               │  │  /opt/fbib-agent/data/          │  │
            │               │  │  -r--r--r-- (read-only)        │  │
            │               │  └───────────────┬────────────────┘  │
            │               │                  │                    │
            │               │                  ▼                    │
            │               │  ┌────────────────────────────────┐  │
            │               │  │  TU APLICACIÓN (Sist. de RH)   │  │
            │               │  │                                │  │
            │               │  │  conn = sqlite3.connect(       │  │
            │               │  │    "file:...?mode=ro")         │  │
            │               │  │  SELECT * FROM empleados       │  │
            │               │  │  → Funciona sin internet       │  │
            │               │  └────────────────────────────────┘  │
            │               └──────────────────────────────────────┘
            │
            ▼
   ┌────────────────────────────────────────────────────────────┐
   │  🏢 TU FUENTE DE DATOS (UKG / SAP / Oracle)                │
   │                                                            │
   │  El Agent se autentica con TU API key.                     │
   │  Las columnas las define el API response —                 │
   │  cero hardcodeo en el Agent.                               │
   └────────────────────────────────────────────────────────────┘
```

**El Agent jala directo de tu fuente.** No pasa por un Hub central. Tu API key, tu conexión.

---

## 2. Descargar el Agent

### Linux (x86_64)
```bash
wget https://github.com/jcollazo/fbib-deploy-hub/releases/latest/download/fbib-agent-linux
chmod +x fbib-agent-linux
sudo mv fbib-agent-linux /usr/local/bin/
```

### Windows (x86_64)
```powershell
Invoke-WebRequest -Uri "https://github.com/jcollazo/fbib-deploy-hub/releases/latest/download/fbib-agent-windows.exe" -OutFile "C:\ProgramData\FBIBAgent\fbib-agent.exe"
```

**Tamaño:** ~8 MB | **Dependencias:** NINGUNA (ejecutable standalone)

---

## 3. Lo que OGP te entrega

Antes de configurar el Agent, OGP te proporciona:

| Dato | Ejemplo | Descripción |
|---|---|---|
| **Agency Key** | `ogp`, `hacienda`, `dtop` | Identificador único de tu agencia |
| **Hub URL** | `https://hub.pr.gov` | URL del FBIB Deploy Hub central (solo para config) |
| **Source Type** | `UKG`, `SAP`, `ORACLE` | Tu sistema de recursos humanos |
| **API Key** | `us-api-ogp-abc123...` | Tu API key para autenticarte contra UKG/SAP/Oracle |
| **Client ID / Secret** | OAuth 2.0 credentials | Credenciales OAuth de tu sistema |

> **IMPORTANTE:** El Agent usa TU API key. Los datos viajan directo de UKG/SAP/Oracle → tu servidor. Nadie más ve tus datos.

---

## 4. Configuración del Agent

### 4.1 Probar el Agent (modo manual)

```bash
# Linux
fbib-agent-linux \
  --agency-key ogp \
  --hub-url https://hub.pr.gov \
  --once

# Windows
C:\ProgramData\FBIBAgent\fbib-agent.exe ^
  --agency-key ogp ^
  --hub-url https://hub.pr.gov ^
  --once
```

**Salida esperada (con fuente configurada):**
```
2026-06-22 10:00:01 [INFO] FBIB Agent v1.0.0 starting for agency 'ogp'
2026-06-22 10:00:01 [INFO]   OS: Linux 6.8.0 | Python: 3.13 | Hub: https://hub.pr.gov
2026-06-22 10:00:02 [INFO] Heartbeat sent. Status: 200
2026-06-22 10:00:02 [INFO] Fetching config from Hub...
2026-06-22 10:00:02 [INFO] Pulling data from UKG for agency 'ogp'...
2026-06-22 10:00:02 [INFO] UKG: Authenticating via OAuth 2.0...
2026-06-22 10:00:03 [INFO] UKG: Token obtained (expires in 3600s)
2026-06-22 10:00:03 [INFO] UKG: Fetching page 1...
2026-06-22 10:00:04 [INFO] UKG: Page 1 → 1000 employees (total: 3300)
2026-06-22 10:00:05 [INFO] UKG: Page 2 → 1000 employees (total: 3300)
2026-06-22 10:00:05 [INFO] UKG: Page 3 → 1000 employees (total: 3300)
2026-06-22 10:00:06 [INFO] UKG: Page 4 → 300 employees (total: 3300)
2026-06-22 10:00:06 [INFO] UKG: Fetch complete — 3300 total employees
2026-06-22 10:00:06 [INFO] Filtering to 4 selected columns...
2026-06-22 10:00:06 [INFO] SQLite written: /opt/fbib-agent/data/empleados.db (3300 rows, chmod 444)
```

### 4.2 Instalar como Servicio (recomendado)

#### Linux (systemd)

```bash
# 1. Ejecutar el instalador
sudo fbib-agent-linux \
  --agency-key ogp \
  --hub-url https://hub.pr.gov \
  --install-service

# 2. Copiar el archivo de servicio generado
sudo cp /tmp/fbib-agent-ogp.service /etc/systemd/system/

# 3. Activar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable --now fbib-agent-ogp

# 4. Verificar
sudo systemctl status fbib-agent-ogp
sudo journalctl -u fbib-agent-ogp -f    # logs en tiempo real
```

El Agent se ejecuta como servicio. Si el servidor se reinicia, el Agent arranca automáticamente.

#### Windows (NSSM)

```powershell
# 1. Descargar NSSM (una sola vez)
# https://nssm.cc/download

# 2. Instalar el servicio
nssm install FBIBAgent C:\ProgramData\FBIBAgent\fbib-agent.exe
nssm set FBIBAgent AppParameters "--agency-key ogp --hub-url https://hub.pr.gov"
nssm set FBIBAgent DisplayName "FBIB Deploy Agent (OGP)"
nssm set FBIBAgent Start SERVICE_AUTO_START

# 3. Iniciar
nssm start FBIBAgent

# 4. Verificar estado
nssm status FBIBAgent
```

---

## 5. Columnas — El API de tu fuente las define

**El Agent no hardcodea columnas.** Cuando se autentica contra UKG/SAP/Oracle, el JSON response **define** qué columnas existen.

```python
# transports.py — cero $select, cero expand hardcodeado
resp = requests.get(
    f"{base_url}/personnel/v1/employees",  # UKG
    # f"{base_url}/odata/v2/EmpEmployment",  # SAP
    # f"{base_url}/hcmRestApi/.../workers",  # Oracle
    headers={"Authorization": f"Bearer {token}"},
    # SIN $select, SIN expand → API retorna todo
)
```

**Filtro opcional:** Si OGP configura `selected_columns` en el Portal, el Agent filtra SOLO esas columnas al escribir SQLite. Si no, conserva todas.

```python
# agent.py — filtro automático
if selected_cols:
    employees = self._filter_columns(employees, selected_cols)
```

---

## 6. Conectar tu Aplicación al SQLite Local

Tu aplicación lee los datos desde un archivo SQLite local que el Agent actualiza en cada ciclo.
**El archivo está en modo read-only (chmod 444). Nadie puede escribir en él.**

### 6.1 Ubicación del archivo

```bash
/opt/fbib-agent/data/empleados.db     ← Read-only (r--r--r--)
/opt/fbib-agent/data/empleados.db-wal ← WAL journal (solo lectura)
```

### 6.2 Leer desde tu aplicación

```python
# Python — SQLite read-only mode
import sqlite3

# URI mode con ?mode=ro = IMPOSIBLE escribir
conn = sqlite3.connect("file:/opt/fbib-agent/data/empleados.db?mode=ro", uri=True)
cursor = conn.cursor()

# Tus datos, directo de tu fuente
cursor.execute("SELECT * FROM empleados ORDER BY last_name")
for row in cursor:
    print(row["first_name"], row["last_name"], row["position_title"])

# Leer metadatos
cursor.execute("SELECT * FROM _fbib_meta")
for key, val in cursor:
    print(f"{key}: {val}")
# agency_key: ogp
# source_type: UKG
# pulled_at: 2026-06-22T10:00:06Z
# total_rows: 3300
# columns: eeid,first_name,last_name,position_title
# access: READ-ONLY — SELECT only. No INSERT/UPDATE/DELETE.

conn.close()
```

```java
// Java — SQLite JDBC read-only
import java.sql.*;

Properties config = new Properties();
config.setProperty("open_mode", "1");  // read-only
Connection conn = DriverManager.getConnection(
    "jdbc:sqlite:/opt/fbib-agent/data/empleados.db", config
);
Statement stmt = conn.createStatement();
ResultSet rs = stmt.executeQuery("SELECT * FROM empleados");
while (rs.next()) {
    System.out.println(rs.getString("first_name"));
}
```

```csharp
// C# — SQLite read-only
using Microsoft.Data.Sqlite;

var conn = new SqliteConnection(
    "Data Source=/opt/fbib-agent/data/empleados.db;Mode=ReadOnly"
);
conn.Open();
var cmd = new SqlCommand("SELECT * FROM empleados", conn);
using var reader = cmd.ExecuteReader();
while (reader.Read()) {
    Console.WriteLine(reader["first_name"]);
}
```

```javascript
// Node.js — better-sqlite3 read-only
const Database = require('better-sqlite3');
const db = new Database('/opt/fbib-agent/data/empleados.db', {
    readonly: true,
    fileMustExist: true
});
const rows = db.prepare('SELECT * FROM empleados').all();
console.log(rows);
```

### 6.3 Intentar escribir → IMPOSIBLE

```python
# Esto tira EXCEPTION porque el archivo es chmod 444
conn = sqlite3.connect("file:/opt/fbib-agent/data/empleados.db?mode=ro", uri=True)
conn.execute("INSERT INTO empleados VALUES (...)")
# sqlite3.OperationalError: attempt to write a readonly database

# Y aunque cambiaras el mode=rw:
$ ls -la /opt/fbib-agent/data/empleados.db
# -r--r--r-- 1 root root 2.1M Jun 22 10:00 empleados.db
# ↑ Solo lectura a nivel de sistema operativo
```

### 6.4 ¿Qué pasa si UKG/SAP/Oracle está caído?

```
┌──────────────────────────────────────────────────────────┐
│  TU APLICACIÓN                                           │
│                                                          │
│  conn = sqlite3.connect("file:.../empleados.db?mode=ro") │
│  cursor.execute("SELECT * FROM empleados")               │
│  → FUNCIONA PERFECTO                                     │
│                                                          │
│  La última copia sigue en disco.                         │
│  Tus empleados pueden seguir trabajando.                 │
│  El Agent reintentará en el próximo ciclo.               │
└──────────────────────────────────────────────────────────┘
```

### 6.5 Metadatos de la réplica

Cada archivo SQLite incluye una tabla `_fbib_meta`:

```sql
SELECT * FROM _fbib_meta;
```

| key | value (ejemplo) |
|---|---|
| `agency_key` | `ogp` |
| `source_type` | `UKG` |
| `total_rows` | `3300` |
| `columns` | `eeid,first_name,last_name,position_title` |
| `pulled_at` | `2026-06-22T10:00:06Z` |
| `access` | `READ-ONLY — SELECT only. No INSERT/UPDATE/DELETE.` |

---

## 7. Verificación — Checklist

Después de configurar, verifica cada paso:

| # | Verificación | Comando | Esperado |
|---|---|---|---|
| 1 | Agent instalado | `fbib-agent-linux --help` | Muestra ayuda |
| 2 | Agent conecta al Hub | `fbib-agent-linux --agency-key ogp --hub-url https://hub.pr.gov --once` | Logs de pull de datos |
| 3 | Servicio corriendo | `systemctl status fbib-agent-ogp` | `active (running)` |
| 4 | SQLite existe | `ls -la /opt/fbib-agent/data/empleados.db` | `-r--r--r--` (read-only) |
| 5 | SQLite legible | `sqlite3 /opt/fbib-agent/data/empleados.db "SELECT COUNT(*) FROM empleados"` | Número > 0 |
| 6 | SQLite NO escribible | `python3 -c "import sqlite3; sqlite3.connect('file:/opt/fbib-agent/data/empleados.db?mode=ro',uri=True).execute('CREATE TABLE x(y)')"` | **ERROR** |
| 7 | Metadatos correctos | `sqlite3 /opt/fbib-agent/data/empleados.db "SELECT * FROM _fbib_meta WHERE key='agency_key'"` | Tu agency key |
| 8 | Columnas dinámicas | `sqlite3 /opt/fbib-agent/data/empleados.db "SELECT value FROM _fbib_meta WHERE key='columns'"` | Columnas del API de tu fuente |

---

## 8. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Connection refused` | Hub URL mal o Hub caído | Verifica la URL con OGP. Prueba `curl https://hub.pr.gov/health` |
| `Agency not found` | Agency key incorrecta | Confirma tu agency key con OGP |
| `OAuth token failed` | API key o credenciales incorrectas | Verifica client_id/secret con OGP. Pide que regeneren. |
| `No source configured` | OGP no ha configurado tu fuente | Contacta a OGP para que haga `PUT /source` en el Portal |
| `INSERT permission denied` | **Está bien.** Es por diseño | No tienes permisos de escritura. Usa SELECT. |
| `Heartbeat failed` | Firewall bloquea salida | Abre puerto 443/TCP saliente hacia `hub.pr.gov` y tu fuente (UKG/SAP/Oracle) |
| Agent no arranca tras reboot | Servicio no enabled | `systemctl enable fbib-agent-ogp` |

---

## 9. Resumen — Lo que la Agencia Necesita Hacer

```
┌─────────────────────────────────────────────────────────────┐
│  PASO 1 — Descargar Agent (8 MB)                            │
│  wget https://github.com/.../fbib-agent-linux                │
│                                                              │
│  PASO 2 — Instalar como servicio                             │
│  fbib-agent-linux --agency-key ogp --hub-url ... --install    │
│  sudo cp /tmp/fbib-agent-ogp.service /etc/systemd/system/     │
│  sudo systemctl enable --now fbib-agent-ogp                  │
│                                                              │
│  PASO 3 — OGP configura tu fuente en el Portal              │
│  PUT /source → UKG + tu API key + OAuth creds               │
│  PUT /columns → [columnas a filtrar] (opcional)             │
│  El Agent jala automáticamente en el próximo ciclo.         │
│                                                              │
│  PASO 4 — Verificar primera carga                            │
│  ls -la /opt/fbib-agent/data/empleados.db                    │
│  → -r--r--r--  empleados.db                                 │
│  sqlite3 empleados.db "SELECT COUNT(*) FROM empleados"      │
│  → 3300 (o los que tenga tu fuente)                         │
│                                                              │
│  PASO 5 — Leer desde tu aplicación                           │
│  conn = sqlite3.connect("file:.../empleados.db?mode=ro",...) │
│  cursor.execute("SELECT * FROM empleados")                  │
│                                                              │
│  PASO 6 — Verificar read-only                                │
│  Intentar INSERT → PERMISSION DENIED ✓                      │
│  systemctl status fbib-agent-ogp → active (running)          │
│                                                              │
│  ✅ Columnas dinámicas — API de tu fuente las define        │
│  ✅ Cero dependencias externas                               │
│  ✅ Funciona sin internet                                    │
│  ✅ Imposible escribir datos                                 │
│  ✅ $0 por agencia                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🆚 Comparativa: FBIB Agent vs Boomi Atom

| | Boomi Atom | FBIB Agent |
|---|---|---|
| **Descargar** | Java 11+ JDK + Atom installer (~500 MB) | 1 ejecutable (~8 MB) |
| **Instalar** | Wizard gráfico o script complejo | 1 comando |
| **Servicio** | Configuración manual | `--install-service` automático (systemd / NSSM) |
| **Tiempo de setup** | 30-60 min (con IT) | **3 minutos** |
| **Licencia** | $550/mes por agencia | **$0** |
| **Conexión a fuente** | Atom → Boomi Cloud → fuente | Agent → **directo a UKG/SAP/Oracle** |
| **Columnas** | Hardcodeadas en Integration Process | **Dinámicas** — API response define |
| **Escribe en DB** | INSERT / UPDATE / DELETE | **NUNCA escribe** (SQLite chmod 444) |
| **Actualizar** | Download manual + re-run wizard | Reemplazar ejecutable |
| **Firewall** | Múltiples puertos (HTTP, JDBC, etc.) | 1 puerto: 443/TCP saliente |

---

> **¿Preguntas?** Contacta a la Oficina de Gerencia de Presupuesto — División de Tecnología
