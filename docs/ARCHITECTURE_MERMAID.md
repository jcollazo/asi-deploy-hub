# ASI Architecture — Mermaid Diagrams

## System Overview (CORREGIDO)

Cada agencia tiene **UNA** fuente de datos. El Agent jala directo de UKG, SAP, u Oracle según lo configurado en el portal.

```mermaid
graph TB
    subgraph Portal["🖥️ Admin Portal (OGP)"]
        CFG["⚙️ Configuración por agencia<br/>Fuente: UKG | SAP | Oracle<br/>Columnas: nombre, puesto...<br/>API Key: us-api-..."]
    end

    subgraph Hub["🌐 ASI Deploy Hub API"]
        CONFIG["GET /api/agent/{key}/config<br/>→ source_type, api_key, columns"]
    end

    subgraph Agencia1["🏛️ Agencia OGP"]
        AG1["🤖 ASI Agent"]
        SQL1[("📦 empleados.db<br/>chmod 444<br/>read-only")]
        APP1["🖥️ App RH OGP"]
    end

    subgraph Agencia2["🏛️ Agencia Hacienda"]
        AG2["🤖 ASI Agent"]
        SQL2[("📦 empleados.db<br/>chmod 444")]
        APP2["🖥️ App RH Hacienda"]
    end

    subgraph Agencia3["🏛️ Agencia DTOP"]
        AG3["🤖 ASI Agent"]
        SQL3[("📦 empleados.db<br/>chmod 444")]
        APP3["🖥️ App RH DTOP"]
    end

    subgraph Sources["Fuentes de Datos"]
        UKG["🏢 UKG Pro<br/>REST API"]
        SAP["🏢 SAP SuccessFactors<br/>OData"]
        ORACLE["🏢 Oracle HCM<br/>REST API"]
    end

    CFG -->|"guarda config"| CONFIG
    CONFIG -->|"lee config"| AG1
    CONFIG -->|"lee config"| AG2
    CONFIG -->|"lee config"| AG3

    AG1 -->|"OAuth 2.0 + API Key OGP"| UKG
    AG2 -->|"OAuth 2.0 + API Key Hacienda"| SAP
    AG3 -->|"OAuth 2.0 + API Key DTOP"| ORACLE

    UKG -->|"JSON empleados OGP"| AG1
    SAP -->|"JSON empleados Hacienda"| AG2
    ORACLE -->|"JSON empleados DTOP"| AG3

    AG1 -->|"escribe SQLite"| SQL1
    AG2 -->|"escribe SQLite"| SQL2
    AG3 -->|"escribe SQLite"| SQL3

    SQL1 -->|"SELECT * FROM empleados"| APP1
    SQL2 -->|"SELECT * FROM empleados"| APP2
    SQL3 -->|"SELECT * FROM empleados"| APP3

    style CFG fill:#0D6EFD,color:#fff
    style CONFIG fill:#E5BD44,color:#12223A
    style UKG fill:#12223A,color:#fff
    style SAP fill:#12223A,color:#fff
    style ORACLE fill:#12223A,color:#fff
    style AG1 fill:#16335C,color:#fff
    style AG2 fill:#16335C,color:#fff
    style AG3 fill:#16335C,color:#fff
    style SQL1 fill:#198754,color:#fff
    style SQL2 fill:#198754,color:#fff
    style SQL3 fill:#198754,color:#fff
```

---

## Data Flow — Diario (por agencia)

```mermaid
sequenceDiagram
    participant Portal as 🖥️ Admin Portal
    participant Hub as 🌐 Hub API
    participant Agent as 🤖 Agent (Agencia)
    participant Source as 🏢 UKG/SAP/Oracle
    participant SQLite as 📦 SQLite Local
    participant App as 🖥️ App Agencia

    Note over Portal,App: ⚙️ Configuración (una vez)

    Portal->>Hub: PUT /api/admin/agencies/ogp/columns
    Portal->>Hub: PUT /api/admin/agencies/ogp/source<br/>{type: "UKG", api_key: "us-api-..."}
    Hub-->>Portal: ✅ Config guardada

    Note over Portal,App: 🔄 Cada 60s — Agent poll

    Agent->>Hub: GET /api/agent/ogp/config
    Hub-->>Agent: {source: "UKG", api_key: "***", columns: [...]}

    Note over Portal,App: 🌅 2:00 AM — Pull de datos

    Agent->>Source: OAuth 2.0 token
    Source-->>Agent: access_token

    Agent->>Source: GET /personnel/v1/employees
    Source-->>Agent: JSON (3,300 empleados OGP)

    Agent->>Agent: Filtrar columnas configuradas
    Agent->>Agent: AES-256-GCM encrypt SSN
    Agent->>SQLite: Escribir empleados.db
    Agent->>SQLite: chmod 444

    Agent->>Hub: POST heartbeat (rows synced: 3300)

    Note over Portal,App: 🌅 8:00 AM — Agencia trabaja

    App->>SQLite: sqlite3.connect("file:...?mode=ro")
    App->>SQLite: SELECT * FROM empleados
    SQLite-->>App: 3,300 rows → instantáneo
```

---

## Agent Internals

```mermaid
stateDiagram-v2
    [*] --> POLLING: Agent arranca
    POLLING --> FETCH_CONFIG: Cada 60s
    FETCH_CONFIG --> CHECK_SOURCE: GET /api/agent/{key}/config
    CHECK_SOURCE --> PULL_DATA: source_type configurado
    CHECK_SOURCE --> POLLING: sin source configurado
    PULL_DATA --> AUTH: OAuth 2.0
    AUTH --> FETCH: GET employees (paginated)
    FETCH --> FILTER: Filtrar columnas
    FILTER --> ENCRYPT: AES-256-GCM SSN
    ENCRYPT --> WRITE_SQLITE: INSERT batch 1000
    WRITE_SQLITE --> CHMOD: chmod 444
    CHMOD --> REPORT: Heartbeat al Hub
    REPORT --> POLLING: Esperar 60s

    note right of PULL_DATA: UKG → REST API<br/>SAP → OData<br/>Oracle → REST API
    note right of WRITE_SQLITE: NUNCA INSERT/UPDATE<br/>en DB externa.<br/>Solo SQLite local.
```

---

## Configuración por Agencia (Portal Admin)

```mermaid
graph LR
    subgraph Portal["🖥️ Admin Portal"]
        P1["Agencia OGP<br/>━━━━━━━━━━<br/>Fuente: UKG ✓<br/>API Key: us-api-ogp-...<br/>Columnas: 6/22"]
        P2["Agencia Hacienda<br/>━━━━━━━━━━<br/>Fuente: SAP ✓<br/>API Key: sap-api-hac-...<br/>Columnas: 22/22"]
        P3["Agencia DTOP<br/>━━━━━━━━━━<br/>Fuente: Oracle ✓<br/>API Key: ora-api-dtop-...<br/>Columnas: 10/22"]
    end

    subgraph Agents["Agents"]
        A1["🤖 Agent OGP"]
        A2["🤖 Agent Hacienda"]
        A3["🤖 Agent DTOP"]
    end

    subgraph Sources["Fuentes"]
        UKG["🏢 UKG Pro"]
        SAP["🏢 SAP"]
        ORACLE["🏢 Oracle HCM"]
    end

    P1 -->|config| A1
    P2 -->|config| A2
    P3 -->|config| A3

    A1 -->|pull| UKG
    A2 -->|pull| SAP
    A3 -->|pull| ORACLE

    style P1 fill:#0D6EFD,color:#fff
    style P2 fill:#0D6EFD,color:#fff
    style P3 fill:#0D6EFD,color:#fff
    style A1 fill:#16335C,color:#fff
    style A2 fill:#16335C,color:#fff
    style A3 fill:#16335C,color:#fff
    style UKG fill:#12223A,color:#fff
    style SAP fill:#12223A,color:#fff
    style ORACLE fill:#12223A,color:#fff
```

---

## Comparativa Boomi vs ASI

```mermaid
graph TB
    subgraph Boomi["❌ Boomi — ~$200K/año"]
        B1["Boomi Integration<br/>$17K conn"]
        B2["Boomi Data Hub<br/>$20K-$40K"]
        B3["Atoms ×19<br/>$125K/año"]
        B4["DB Connectors<br/>$5K-$17K c/u"]
        B5["🔴 INSERT/UPDATE<br/>en DB agencia"]
    end

    subgraph ASI["✅ ASI — ~$240/año"]
        A1["Admin Portal<br/>Config por agencia"]
        A2["Agent ×19<br/>Pull directo de fuente"]
        A3["SQLite local<br/>chmod 444"]
        A4["🟢 READ-ONLY<br/>Cero escritura"]
    end

    B1 --> B2 --> B3 --> B4 --> B5
    A1 --> A2 --> A3 --> A4

    style B5 fill:#DC3545,color:#fff
    style A4 fill:#198754,color:#fff
```

---

## Data Flow — Diario

```mermaid
sequenceDiagram
    participant UKG as UKG Pro Cloud
    participant Hub as PR Integration Hub
    participant SQL as SQL Server Central
    participant ASI as ASI Deploy Hub
    participant Agent as Agent (Agencia)
    participant App as App Agencia

    Note over UKG,App: 🌅 1:00 AM — ETL Diario

    UKG->>Hub: GET /personnel/v1/employees
    Hub->>Hub: Validar + AES-256-GCM encrypt SSN
    Hub->>SQL: MERGE atómico (staging → target)
    SQL-->>Hub: ✅ 500K rows merged

    Note over UKG,App: 🌅 2:00 AM — Generar Réplicas

    ASI->>SQL: SELECT * WHERE agency=X (×19)
    SQL-->>ASI: 19 result sets
    ASI->>ASI: Build SQLite + SHA-256 + chmod 444
    ASI-->>Agent: DATA deployment creado

    Note over UKG,App: 🌅 3:00 AM — Agents descargan

    Agent->>ASI: GET /api/agent/artifact/{id}
    ASI-->>Agent: Stream empleados.db
    Agent->>Agent: SHA-256 verify + chmod 444
    Agent-->>ASI: Report SUCCESS

    Note over UKG,App: 🌅 8:00 AM — Agencias abren

    App->>App: sqlite3.connect("file:empleados.db?mode=ro")
    App->>App: SELECT * FROM empleados → instantáneo
```

---

## Login Flow

```mermaid
sequenceDiagram
    participant U as Usuario
    participant L as Login Page
    participant A as App.jsx
    participant S as sessionStorage

    U->>L: Abre http://localhost:5173
    L-->>U: Split-screen login (Boomi-style)

    U->>L: Usuario + Contraseña
    L->>A: onLogin({username})
    A->>S: Guarda sesión
    A-->>U: Admin Portal (sidebar + dashboard)

    U->>A: Click "Cerrar sesión"
    A->>S: Borra sesión
    A-->>U: Login Page
```

---

## Column Selection

```mermaid
graph LR
    subgraph Admin["🖥️ Admin Portal"]
        CFG["PUT /api/admin/agencies/ogp/columns<br/>{columns: ['nombre','puesto','status']}"]
    end

    subgraph Hub["ASI Deploy Hub"]
        DB[("dbo.agencies<br/>selected_columns")]
        GEN["generate-replicas"]
    end

    subgraph Agency["Agencia OGP"]
        SQLite[("empleados.db<br/>3 columnas · 4 MB")]
    end

    CFG -->|"guarda selección"| DB
    DB -->|"lee columnas"| GEN
    GEN -->|"SELECT nombre,puesto,status<br/>WHERE agency='OGP'"| SQLite

    style CFG fill:#0D6EFD,color:#fff
    style DB fill:#12223A,color:#fff
    style GEN fill:#E5BD44,color:#12223A
    style SQLite fill:#198754,color:#fff
```

---

## Agent Deployment Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: OGP crea deployment
    PENDING --> DOWNLOADING: Agent detecta
    DOWNLOADING --> VERIFYING: Download completo
    VERIFYING --> INSTALLING: SHA-256 ✅
    VERIFYING --> FAILED: SHA-256 ❌
    INSTALLING --> SUCCESS: Deploy OK
    INSTALLING --> FAILED: Error en deploy

    SUCCESS --> [*]: Report al Hub
    FAILED --> [*]: Report al Hub (con error)
```

---

## Comparativa Boomi vs ASI

```mermaid
graph TB
    subgraph Boomi["❌ Boomi — ~$200K/año"]
        B1["Boomi Integration<br/>$17K conn"]
        B2["Boomi Data Hub<br/>$20K-$40K"]
        B3["Atoms ×19<br/>$125K/año"]
        B4["DB Connectors<br/>$5K-$17K c/u"]
        B5["🔴 INSERT/UPDATE<br/>en DB agencia"]
    end

    subgraph ASI["✅ ASI — ~$240/año"]
        A1["PR Integration Hub<br/>$0"]
        A2["ASI Deploy Hub<br/>$0"]
        A3["Agents ×19<br/>$0"]
        A4["SQLite replicas<br/>$0"]
        A5["🟢 chmod 444<br/>read-only"]
    end

    B1 --> B2 --> B3 --> B4 --> B5
    A1 --> A2 --> A3 --> A4 --> A5

    style B5 fill:#DC3545,color:#fff
    style A5 fill:#198754,color:#fff
```
