# ASI Architecture — Mermaid Diagrams

## System Overview

El Agent se autentica directo contra UKG/SAP/Oracle. Las columnas las define el API response de la agencia — el Portal solo configura qué columnas **filtrar** al final.

```mermaid
graph TB
    subgraph Portal["🖥️ Admin Portal (OGP)"]
        SRC["PUT /source → UKG|SAP|Oracle + API Key"]
        COL["PUT /columns → filtrar columnas<br/>(opcional — API define las disponibles)"]
    end

    subgraph Hub["🌐 ASI Deploy Hub API :8900"]
        CONFIG["GET /api/agent/{key}/config<br/>→ source_type, creds, selected_columns"]
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
        UKG["🏢 UKG Pro<br/>REST API<br/>┃ columnas dinámicas"]
        SAP["🏢 SAP SuccessFactors<br/>OData<br/>┃ columnas dinámicas"]
        ORACLE["🏢 Oracle HCM<br/>REST API<br/>┃ columnas dinámicas"]
    end

    SRC --> CONFIG
    COL --> CONFIG
    CONFIG -->|"source: UKG + creds<br/>selected_columns (filtro)"| AG1
    CONFIG -->|"source: SAP + creds<br/>selected_columns (filtro)"| AG2
    CONFIG -->|"source: ORACLE + creds<br/>selected_columns (filtro)"| AG3

    AG1 -->|"OAuth 2.0 → pull"| UKG
    AG2 -->|"OAuth 2.0 → pull"| SAP
    AG3 -->|"OAuth 2.0 → pull"| ORACLE

    UKG -->|"JSON (todas las columnas)"| AG1
    SAP -->|"JSON (todas las columnas)"| AG2
    ORACLE -->|"JSON (todas las columnas)"| AG3

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

El Agent no hardcodea columnas. El API response de UKG/SAP/Oracle **define** qué columnas existen. El `selected_columns` del Portal solo filtra al final.

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
    Portal->>Hub: PUT /columns → [nombre, puesto, status] (filtro opcional)
    Hub-->>Portal: ✅

    Note over Portal,App: 🔄 Cada 60s

    Agent->>Hub: GET /api/agent/{key}/config
    Hub-->>Agent: source_type, creds, selected_columns

    alt source_type configurado
        Agent->>Source: OAuth 2.0 → access_token
        Source-->>Agent: token ✅

        Agent->>Source: GET employees (sin $select/expand hardcoded)
        Source-->>Agent: JSON — TODAS las columnas del API

        Note over Agent: Columnas = keys del JSON response.<br/>Cero hardcodeo. El API manda.

        alt selected_columns configurado
            Agent->>Agent: _filter_columns(rows, selected)
            Note over Agent: Solo conserva las columnas<br/>que la agencia eligió
        else sin filtro
            Agent->>Agent: Conserva TODAS las columnas
        end

        Agent->>SQLite: INSERT batch 1000
        Agent->>SQLite: chmod 444 + atomic replace
        Agent->>Hub: Heartbeat (rows pulled: N, cols: M)
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
    FETCH --> DISCOVER: API response → columnas dinámicas
    DISCOVER --> FILTER: _filter_columns() solo si selected_columns
    FILTER --> WRITE: SQLite batch 1000
    WRITE --> CHMOD: chmod 444 + atomic replace
    CHMOD --> HEARTBEAT: sleep 60s
    HEARTBEAT --> POLLING

    note right of FETCH: UKG → /personnel/v1/employees<br/>SAP → /odata/v2/EmpEmployment<br/>Oracle → /hcmRestApi/.../workers<br/><br/>SIN $select NI expand hardcoded
    note right of DISCOVER: Columnas = keys del JSON.<br/>El API de la agencia<br/>define las columnas.
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
        E1["PUT /source<br/>UKG|SAP|Oracle"]
        E2["PUT /columns<br/>filtro (API define disponibles)"]
        E3["GET /config<br/>creds + selected_columns"]
        E4["GET /pending"]
        E5["POST /heartbeat"]
    end

    subgraph DB[("SQL Server")]
        AG[("agencies<br/>source_type, creds,<br/>selected_columns")]
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

Cada agencia tiene su propia API key. El Agent se autentica y el API response define las columnas disponibles. El Portal solo filtra.

```mermaid
graph LR
    subgraph Portal["🖥️ Admin Portal"]
        P1["OGP → UKG<br/>━━━━━━<br/>API key propia<br/>Filtro: 4 cols"]
        P2["Hacienda → SAP<br/>━━━━━━<br/>API key propia<br/>Sin filtro (todas)"]
        P3["DTOP → Oracle<br/>━━━━━━<br/>API key propia<br/>Filtro: 10 cols"]
    end

    subgraph Transport["transports.py"]
        T1["UKGTransport<br/>OAuth 2.0<br/>GET employees<br/>┃ 0 columnas hardcodeadas"]
        T2["SAPTransport<br/>OAuth 2.0<br/>OData EmpEmployment<br/>┃ 0 columnas hardcodeadas"]
        T3["OracleTransport<br/>OAuth 2.0<br/>GET workers<br/>┃ 0 columnas hardcodeadas"]
    end

    subgraph Agents["Agent → SQLite"]
        A1["OGP → empleados.db<br/>Columnas: API response<br/>Filtradas: 4"]
        A2["Hacienda → empleados.db<br/>Columnas: API response<br/>Todas"]
        A3["DTOP → empleados.db<br/>Columnas: API response<br/>Filtradas: 10"]
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
        A2["Agent ×19<br/>Pull directo de UKG/SAP/Oracle<br/>Columnas dinámicas del API"]
        A3["SQLite local<br/>chmod 444"]
        A4["🟢 READ-ONLY<br/>Cero escritura"]
    end

    B1 --> B2 --> B3 --> B4 --> B5
    A1 --> A2 --> A3 --> A4

    style B5 fill:#DC3545,color:#fff
    style A4 fill:#198754,color:#fff
```
