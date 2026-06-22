# ASI Agent — Guía de Configuración para Agencias

> **Versión:** 1.1 (Modelo SQLite Replica Read-Only) | **Idioma:** Español | **SO:** Linux + Windows

---

## 1. ¿Qué es el ASI Agent?

El ASI Agent es el equivalente a un **Boomi Atom**, pero sin licencias, sin Java, y con **cero permisos de escritura** en tu base de datos.

```
┌─────────────────────────────────────────────────────────────────┐
│                         OGP CENTRAL                              │
│                                                                  │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────┐           │
│  │ SQL Srv  │   │ Hub API      │   │ PR Integ Hub   │           │
│  │ (master) │   │ :8900        │   │ (ETL)          │           │
│  └────┬─────┘   └──────┬───────┘   └───────┬────────┘           │
│       │                │                   │                     │
│       │    ┌───────────┴──────────┐        │                     │
│       │    │  POST generate-replicas│      │                     │
│       │    │  (cron diario)        │      │                     │
│       │    │                       │      │                     │
│       │    │  Genera SQLite por    │      │                     │
│       │    │  agencia (filtrado)   │      │                     │
│       │    └───────────┬──────────┘        │                     │
└───────┼────────────────┼───────────────────┼─────────────────────┘
        │                │                   │
        │                ▼                   │
        │     ┌──────────────────┐           │
        │     │  empleados.db    │           │
        │     │  (SHA-256)       │           │
        │     │  solo tu agencia │           │
        │     └────────┬─────────┘           │
        │              │                     │
        ▼              ▼                     │
┌───────────────────────────────────────────┼─────────────────────┐
│              TU AGENCIA                    │                     │
│                                            │                     │
│  ┌──────────────────────────────────────┐ │                     │
│  │  ASI Agent (8 MB ejecutable)         │ │                     │
│  │                                      │ │                     │
│  │  🔄 Cada 60s:                        │ │                     │
│  │  • ¿Nuevo release de mi app? → Instala│ │                     │
│  │  • ¿Nueva réplica de datos?          │ │                     │
│  │    → Download SQLite                 │ │                     │
│  │    → Verify SHA-256                  │ │                     │
│  │    → chmod 444 (read-only)           │ │                     │
│  │    → /opt/asi-agent/data/empleados.db│ │                     │
│  └──────────────────────────────────────┘ │                     │
│                                            │                     │
│  ┌──────────────────────────────────────┐ │                     │
│  │  TU APLICACIÓN (Sistema de RH)       │ │                     │
│  │                                      │ │                     │
│  │  🔍 Lee SQLite local (read-only):    │ │                     │
│  │  conn = sqlite3.connect("file:...?mode=ro")  │               │
│  │  cursor.execute("SELECT * FROM empleados")   │               │
│  │                                      │ │                     │
│  │  Funciona aunque el Hub esté caído   │ │                     │
│  └──────────────────────────────────────┘ │                     │
└─────────────────────────────────────────────────────────────────┘
```

**El Agent recibe un archivo SQLite diario con los datos de TU agencia.**
Tu aplicación lo lee. El archivo tiene permisos `r--r--r--` — imposible escribir.

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

## 5. Conectar tu Aplicación al SQLite Local

Tu aplicación lee los datos desde un archivo SQLite local que el Agent actualiza diariamente.
**El archivo está en modo read-only (chmod 444). Nadie puede escribir en él.**

### 5.1 Ubicación del archivo

```bash
/opt/asi-agent/data/empleados.db     ← Read-only (r--r--r--)
/opt/asi-agent/data/empleados.db-wal ← WAL journal (solo lectura)
```

### 5.2 Leer desde tu aplicación

```python
# Python — SQLite read-only mode
import sqlite3

# URI mode con ?mode=ro = IMPOSIBLE escribir
conn = sqlite3.connect("file:/opt/asi-agent/data/empleados.db?mode=ro", uri=True)
cursor = conn.cursor()

# Tus datos, filtrados para tu agencia
cursor.execute("SELECT * FROM empleados ORDER BY last_name")
for row in cursor:
    print(row["first_name"], row["last_name"], row["position_title"])

# Leer metadatos
cursor.execute("SELECT * FROM _asi_meta")
for key, val in cursor:
    print(f"{key}: {val}")
# agency_key: ogp
# generated_at: 2026-06-22T02:00:00Z
# total_rows: 1542
# access: READ-ONLY — SELECT only. No INSERT/UPDATE/DELETE.

conn.close()
```

```java
// Java — SQLite JDBC read-only
import java.sql.*;

Properties config = new Properties();
config.setProperty("open_mode", "1");  // read-only
Connection conn = DriverManager.getConnection(
    "jdbc:sqlite:/opt/asi-agent/data/empleados.db", config
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
    "Data Source=/opt/asi-agent/data/empleados.db;Mode=ReadOnly"
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
const db = new Database('/opt/asi-agent/data/empleados.db', {
    readonly: true,
    fileMustExist: true
});
const rows = db.prepare('SELECT * FROM empleados').all();
console.log(rows);
```

### 5.3 Intentar escribir → IMPOSIBLE

```python
# Esto tira EXCEPTION porque el archivo es chmod 444
conn = sqlite3.connect("file:/opt/asi-agent/data/empleados.db?mode=ro", uri=True)
conn.execute("INSERT INTO empleados VALUES (...)")
# sqlite3.OperationalError: attempt to write a readonly database

# Y aunque cambiaras el mode=rw:
$ ls -la /opt/asi-agent/data/empleados.db
# -r--r--r-- 1 root root 2.1M Jun 22 02:00 empleados.db
# ↑ Solo lectura a nivel de sistema operativo
```

### 5.4 ¿Qué pasa si el Hub está caído?

```
┌──────────────────────────────────────────────────────────┐
│  TU APLICACIÓN                                           │
│                                                          │
│  conn = sqlite3.connect("file:.../empleados.db?mode=ro") │
│  cursor.execute("SELECT * FROM empleados")               │
│  → FUNCIONA PERFECTO                                     │
│                                                          │
│  La última réplica sigue en disco.                       │
│  Tus empleados pueden seguir trabajando.                 │
└──────────────────────────────────────────────────────────┘
```

### 5.5 Metadatos de la réplica

Cada archivo SQLite incluye una tabla `_asi_meta`:

```sql
SELECT * FROM _asi_meta;
```

| key | value (ejemplo) |
|---|---|
| `agency_key` | `ogp` |
| `pipeline_key` | `ukg_employee_import` |
| `generated_at` | `2026-06-22T02:00:00Z` |
| `total_rows` | `1542` |
| `source` | `PR Integration Hub — SQL Server` |
| `access` | `READ-ONLY — SELECT only. No INSERT/UPDATE/DELETE.` |

---

## 6. Verificación — Checklist

Después de configurar, verifica cada paso:

| # | Verificación | Comando | Esperado |
|---|---|---|---|
| 1 | Agent instalado | `asi-agent-linux --help` | Muestra ayuda |
| 2 | Agent conecta al Hub | `asi-agent-linux --agency-key ogp --hub-url https://hub.pr.gov --once` | "No pending deployments" |
| 3 | Servicio corriendo | `systemctl status asi-agent-ogp` | `active (running)` |
| 4 | Réplica SQLite existe | `ls -la /opt/asi-agent/data/empleados.db` | `-r--r--r--` (read-only) |
| 5 | SQLite legible | `sqlite3 /opt/asi-agent/data/empleados.db "SELECT COUNT(*) FROM empleados"` | Número > 0 |
| 6 | SQLite NO escribible | `python3 -c "import sqlite3; sqlite3.connect('file:/opt/asi-agent/data/empleados.db?mode=ro',uri=True).execute('CREATE TABLE x(y)')"` | **ERROR** |
| 7 | Metadatos correctos | `sqlite3 /opt/asi-agent/data/empleados.db "SELECT * FROM _asi_meta WHERE key='agency_key'"` | Tu agency key |

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
│  PASO 3 — Esperar primera réplica (OGP la genera diario)    │
│  ls -la /opt/asi-agent/data/empleados.db                    │
│  → -r--r--r--  empleados.db                                 │
│                                                              │
│  PASO 4 — Leer desde tu aplicación                           │
│  conn = sqlite3.connect("file:.../empleados.db?mode=ro",...) │
│  cursor.execute("SELECT * FROM empleados")                  │
│                                                              │
│  PASO 5 — Verificar                                         │
│  systemctl status asi-agent-ogp → active (running)          │
│  sqlite3 empleados.db "SELECT COUNT(*) FROM empleados" → >0 │
│  Intentar INSERT → PERMISSION DENIED ✓                      │
│                                                              │
│  ✅ Cero dependencias externas                               │
│  ✅ Funciona sin internet                                    │
│  ✅ Imposible escribir datos                                 │
│  ✅ $0 por agencia                                           │
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
