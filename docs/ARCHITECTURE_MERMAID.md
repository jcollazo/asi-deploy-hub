# ASI Architecture — Mermaid Diagrams

## System Overview

Cada agencia tiene **UNA** fuente. El Agent jala directo de UKG, SAP, u Oracle según lo configurado en el portal.

```mermaid
graph TB
    subgraph Portal["🖥️ Admin Portal (OGP)"]
        SRC["PUT /source → UKG|SAP|Oracle + API Key"]
        COL["PUT /columns → nombre, puesto..."]
    end

    subgraph Hub["🌐 ASI Deploy Hub API :8900"]
        CONFIG["GET /api/agent/{key}/config"]
    end

    subgraph Agencia1["🏛️ Agencia OGP"]
        AG1["🤖 ASI Agent"]
        SQL1[("📦 empleados.db<br/>chmod 444")]
        APP1["🖥️ App RH"]
    end

    subgraph Agencia2["🏛️ Agencia Hacienda"]
        AG2["🤖 ASI Agent"]
        SQL2[("📦 empleados.db<br/>chmod 444")]
        APP2["🖥️ App RH"]
    end

    subgraph Agencia3["🏛️ Agencia DTOP"]
        AG3["🤖 ASI Agent"]
        SQL3[("📦 empleados.db<br/>chmod 444")]
        APP3["🖥️ App RH"]
    end

    subgraph Sources["Fuentes de Datos"]
        UKG["🏢 UKG Pro<br/>REST API"]
        SAP["🏢 SAP SuccessFactors<br/>OData"]
        ORACLE["🏢 Oracle HCM<br/>REST API"]
    end

    SRC --> CONFIG
    COL --> CONFIG
    CONFIG -->|"source_type: UKG<br/>api_key: ***<br/>columns: [...]"| AG1
    CONFIG -->|"source_type: SAP<br/>api_key: ***<br/>columns: [...]"| AG2
    CONFIG -->|"source_type: ORACLE<br/>api_key: ***<br/>columns: [...]"| AG3

    AG1 -->|"OAuth 2.0 + pull"| UKG
    AG2 -->|"OAuth 2.0 + pull"| SAP
    AG3 -->|"OAuth 2.0 + pull"| ORACLE

    UKG -->|"JSON empleados"| AG1
    SAP -->|"JSON empleados"| AG2
    ORACLE -->|"JSON empleados"| AG3

    AG1 -->|"filter + SQLite + chmod 444"| SQL1
    AG2 -->|"filter + SQLite + chmod 444"| SQL2
    AG3 -->|"filter + SQLite + chmod 444"| SQL3

    SQL1 --> APP1
    SQL2 --> APP2
    SQL3 --> APP3

    style SRC fill:#0D6EFD,color:#fff
    style COL fill:#0D6EFD,color:#fff
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
    participant Agent as 🤖 Agent
    participant Source as 🏢 UKG/SAP/Oracle
    participant SQLite as 📦 Local
    participant App as 🖥️ App Agencia

    Note over Portal,App: ⚙️ Setup (una vez)

    Portal->>Hub: PUT /source → UKG + api_key + OAuth creds
    Portal->>Hub: PUT /columns → [nombre, puesto, status]
    Hub-->>Portal: ✅

    Note over Portal,App: 🔄 Cada 60s

    Agent->>Hub: GET /api/agent/{key}/config
    Hub-->>Agent: source_type, api_key, client_id, client_secret, columns

    alt source_type configurado
        Agent->>Source: OAuth 2.0 → access_token
        Source-->>Agent: token ✅

        Agent->>Source: GET employees (paginated)
        Source-->>Agent: JSON rows

        Agent->>Agent: Filtrar columnas seleccionadas
        Agent->>SQLite: INSERT batch 1000
        Agent->>SQLite: chmod 444 + atomic replace
        Agent->>Hub: Heartbeat (rows pulled: N)
    else sin source
        Agent->>Agent: skip
    end

    Note over Portal,App: 🌅 8:00 AM

    App->>SQLite: sqlite3 "file:...?mode=ro"
    App->>SQLite: SELECT * FROM empleados
    SQLite-->>App: rows → instantáneo
```

---

## Agent Internals

```mermaid
stateDiagram-v2
    [*] --> POLLING: Agent arranca

    state POLLING {
        [*] --> CHECK_DEPLOY: ¿pending deployments?
        CHECK_DEPLOY --> DEPLOY_SOFTWARE: sí
        CHECK_DEPLOY --> CHECK_CONFIG: no
        CHECK_CONFIG --> PULL_DATA: source_type != null
        CHECK_CONFIG --> HEARTBEAT: source_type == null
    }

    DEPLOY_SOFTWARE --> HEARTBEAT
    PULL_DATA --> AUTH: transports.get_transport()
    AUTH --> FETCH: OAuth 2.0
    FETCH --> FILTER: paginated GET
    FILTER --> WRITE: _filter_columns()
    WRITE --> CHMOD: SQLite batch 1000
    CHMOD --> HEARTBEAT: chmod 444 + atomic replace
    HEARTBEAT --> POLLING: sleep 60s

    note right of PULL_DATA: UKG → UKGTransport<br/>SAP → SAPTransport<br/>Oracle → OracleTransport
    note right of WRITE: SOLO SQLite local.<br/>NUNCA INSERT/UPDATE<br/>en DB externa.
```

---

## Portal Admin — Endpoints

```mermaid
graph LR
    subgraph Portal["🖥️ Admin Portal (React)"]
        LOGIN["🔐 Login<br/>Boomi-style"]
        DASH["📊 Dashboard"]
        AGENCIES["🏛️ Agencias"]
        DEPLOY["🚀 Deployments"]
    end

    subgraph API["🌐 Hub API (FastAPI :8900)"]
        E1["PUT /source"]
        E2["PUT /columns"]
        E3["GET /config"]
        E4["GET /pending"]
        E5["POST /heartbeat"]
    end

    subgraph DB[("SQL Server")]
        AG[("agencies")]
        REL[("releases")]
        DEP[("deployments")]
    end

    LOGIN --> DASH
    DASH --> AGENCIES
    DASH --> DEPLOY

    AGENCIES --> E1
    AGENCIES --> E2
    E1 --> AG
    E2 --> AG

    E4 --> DEP
    E4 --> REL

    style LOGIN fill:#0D6EFD,color:#fff
    style DASH fill:#0D6EFD,color:#fff
    style AGENCIES fill:#12223A,color:#fff
    style DEPLOY fill:#12223A,color:#fff
    style E1 fill:#E5BD44,color:#12223A
    style E2 fill:#E5BD44,color:#12223A
    style E3 fill:#E5BD44,color:#12223A
    style AG fill:#198754,color:#fff
```

---

## Configuración por Agencia

```mermaid
graph LR
    subgraph Portal["🖥️ Admin Portal"]
        P1["OGP<br/>━━━━━━<br/>UKG ✓<br/>6/22 cols"]
        P2["Hacienda<br/>━━━━━━<br/>SAP ✓<br/>22/22 cols"]
        P3["DTOP<br/>━━━━━━<br/>Oracle ✓<br/>10/22 cols"]
    end

    subgraph Transport["transports.py"]
        T1["UKGTransport<br/>OAuth 2.0<br/>GET employees"]
        T2["SAPTransport<br/>OAuth 2.0<br/>OData EmpEmployment"]
        T3["OracleTransport<br/>OAuth 2.0<br/>GET workers"]
    end

    subgraph Agents["Agent"]
        A1["OGP → empleados.db"]
        A2["Hacienda → empleados.db"]
        A3["DTOP → empleados.db"]
    end

    P1 --> T1 --> A1
    P2 --> T2 --> A2
    P3 --> T3 --> A3

    style P1 fill:#0D6EFD,color:#fff
    style P2 fill:#0D6EFD,color:#fff
    style P3 fill:#0D6EFD,color:#fff
    style T1 fill:#12223A,color:#fff
    style T2 fill:#12223A,color:#fff
    style T3 fill:#12223A,color:#fff
    style A1 fill:#198754,color:#fff
    style A2 fill:#198754,color:#fff
    style A3 fill:#198754,color:#fff
```

---

## Login Flow

```mermaid
sequenceDiagram
    participant U as Usuario
    participant L as Login Page
    participant A as App.jsx
    participant S as sessionStorage

    U->>L: Abre portal
    L-->>U: Split-screen (Boomi-style)

    U->>L: Usuario + Contraseña
    L->>A: onLogin({username})
    A->>S: Guarda sesión
    A-->>U: Dashboard + Sidebar

    U->>A: Cerrar sesión
    A->>S: Borra sesión
    A-->>U: Login Page
```

---

## Agent Deployment Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: OGP crea deployment
    PENDING --> DOWNLOADING: Agent detecta
    DOWNLOADING --> VERIFYING: Download OK
    VERIFYING --> INSTALLING: SHA-256 ✅
    VERIFYING --> FAILED: SHA-256 ❌
    INSTALLING --> SUCCESS: Deploy OK
    INSTALLING --> FAILED: Error

    SUCCESS --> [*]: Report SUCCESS
    FAILED --> [*]: Report FAILED
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
