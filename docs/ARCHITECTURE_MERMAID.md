# ASI Architecture — Mermaid Diagrams

## System Overview

```mermaid
graph TB
    subgraph Sources["Fuentes de Datos"]
        UKG["🏢 UKG Pro<br/>REST API"]
        SAP["🏢 SAP<br/>OData"]
        ORACLE["🏢 Oracle HCM<br/>REST API"]
    end

    subgraph Integration["PR Integration Hub"]
        ETL["🔄 ETL Engine<br/>Python data-driven"]
        CRYPTO["🔐 Crypto Utils<br/>AES-256-GCM"]
        STAGING["📥 Staging<br/>SQL Server"]
    end

    subgraph Hub["ASI Deploy Hub"]
        API["🌐 REST API<br/>FastAPI :8900"]
        ADMIN["🖥️ Admin Portal<br/>React + Login"]
        REPLICA["📦 Replica Generator<br/>SQL Server → SQLite"]
    end

    subgraph Agencies["19 Agencias"]
        AG1["🖥️ Agencia OGP<br/>Agent + SQLite RO"]
        AG2["🖥️ Agencia Hacienda<br/>Agent + SQLite RO"]
        AG3["🖥️ Agencia DTOP<br/>Agent + SQLite RO"]
    end

    UKG -->|"OAuth 2.0 + API Key"| ETL
    SAP -->|"OData + Basic Auth"| ETL
    ORACLE -->|"OAuth 2.0"| ETL
    ETL --> CRYPTO
    CRYPTO --> STAGING
    STAGING -->|MERGE atómico| API
    API --> ADMIN
    API -->|"POST generate-replicas"| REPLICA
    REPLICA -->|"empleados.db (chmod 444)"| AG1
    REPLICA -->|"empleados.db (chmod 444)"| AG2
    REPLICA -->|"empleados.db (chmod 444)"| AG3

    style UKG fill:#0D6EFD,color:#fff
    style SAP fill:#0D6EFD,color:#fff
    style ORACLE fill:#0D6EFD,color:#fff
    style ETL fill:#12223A,color:#fff
    style API fill:#E5BD44,color:#12223A
    style REPLICA fill:#198754,color:#fff
    style AG1 fill:#16335C,color:#fff
    style AG2 fill:#16335C,color:#fff
    style AG3 fill:#16335C,color:#fff
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
