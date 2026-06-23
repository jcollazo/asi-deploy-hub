-- ============================================================
-- 00_registry.sql — FBIB Deploy Hub: Registry Schema
-- ============================================================
-- Central registry for releases, agencies, and deployments.
-- ============================================================

-- ─── Agencies (destino del deployment + data source config) ───
IF OBJECT_ID('dbo.agencies', 'U') IS NULL
CREATE TABLE dbo.agencies (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    agency_key      NVARCHAR(50) NOT NULL UNIQUE,  -- 'ogp', 'hacienda', 'justicia'
    display_name    NVARCHAR(200) NOT NULL,        -- 'Oficina de Gerencia y Presupuesto'
    hostname        NVARCHAR(200),                  -- server hostname or IP
    os_type         NVARCHAR(20) DEFAULT 'LINUX',   -- 'LINUX', 'WINDOWS'
    agent_version   NVARCHAR(20),                   -- currently installed agent version
    last_seen_at    DATETIME2,
    is_active       BIT DEFAULT 1,
    source_type     NVARCHAR(20),                   -- 'UKG', 'SAP', 'ORACLE' | NULL = no data source
    api_key         NVARCHAR(500),                  -- Encrypted: X-US-API-Key or OAuth token
    client_id       NVARCHAR(500),                  -- Encrypted: OAuth 2.0 client_id
    client_secret   NVARCHAR(500),                  -- Encrypted: OAuth 2.0 client_secret
    source_url      NVARCHAR(500),                  -- Base URL: https://api.ultipro.com | https://sap.pr.gov
    selected_columns NVARCHAR(MAX),                 -- Comma-separated: 'eeid,first_name,last_name' | NULL=ALL
    metadata_json   NVARCHAR(MAX),                  -- JSON: tags, contact, notes
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);
GO

-- Migrations: add columns if table already exists
IF COL_LENGTH('dbo.agencies', 'selected_columns') IS NULL
    ALTER TABLE dbo.agencies ADD selected_columns NVARCHAR(MAX);
IF COL_LENGTH('dbo.agencies', 'source_type') IS NULL
    ALTER TABLE dbo.agencies ADD source_type NVARCHAR(20);
IF COL_LENGTH('dbo.agencies', 'api_key') IS NULL
    ALTER TABLE dbo.agencies ADD api_key NVARCHAR(500);
IF COL_LENGTH('dbo.agencies', 'client_id') IS NULL
    ALTER TABLE dbo.agencies ADD client_id NVARCHAR(500);
IF COL_LENGTH('dbo.agencies', 'client_secret') IS NULL
    ALTER TABLE dbo.agencies ADD client_secret NVARCHAR(500);
IF COL_LENGTH('dbo.agencies', 'source_url') IS NULL
    ALTER TABLE dbo.agencies ADD source_url NVARCHAR(500);
GO

-- ─── Applications (software projects to deploy) ─────────────
IF OBJECT_ID('dbo.applications', 'U') IS NULL
CREATE TABLE dbo.applications (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    app_key         NVARCHAR(50) NOT NULL UNIQUE,  -- 'oatrh-portal', 'pr-integration-hub'
    display_name    NVARCHAR(200) NOT NULL,
    description     NVARCHAR(500),
    repo_url        NVARCHAR(500),
    artifact_type   NVARCHAR(20) DEFAULT 'ZIP',     -- 'ZIP', 'DOCKER', 'SQL_SCRIPT', 'DOTNET_PUBLISH', 'PYTHON_WHEEL'
    is_active       BIT DEFAULT 1,
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);
GO

-- ─── Releases (versioned artifacts) ──────────────────────────
IF OBJECT_ID('dbo.releases', 'U') IS NULL
CREATE TABLE dbo.releases (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    release_tag     NVARCHAR(50) NOT NULL,          -- 'v1.2.3', '2026-06-15-hotfix'
    app_id          INT NOT NULL REFERENCES dbo.applications(id),
    version_semver  NVARCHAR(20),                   -- '1.2.3' (semantic version)
    release_notes   NVARCHAR(MAX),
    artifact_path   NVARCHAR(500),                  -- Path in artifact store
    artifact_hash   NVARCHAR(64),                   -- SHA-256 of artifact
    artifact_size   BIGINT,                         -- Bytes
    deploy_script   NVARCHAR(MAX),                  -- Pre/post deploy script (optional)
    status          NVARCHAR(20) DEFAULT 'DRAFT',   -- 'DRAFT', 'PUBLISHED', 'ROLLED_BACK', 'DEPRECATED'
    published_at    DATETIME2,
    created_by      NVARCHAR(100),
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE UNIQUE INDEX IX_releases_tag_app ON dbo.releases(app_id, release_tag);
GO

-- ─── Deployment Targets (which agencies get which release) ───
IF OBJECT_ID('dbo.deployments', 'U') IS NULL
CREATE TABLE dbo.deployments (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    deployment_tag  NVARCHAR(100) NOT NULL,         -- Human-friendly: '2026-06-15-ukg-hotfix'
    release_id      INT NOT NULL REFERENCES dbo.releases(id),
    description     NVARCHAR(500),
    strategy        NVARCHAR(20) DEFAULT 'CANARY',  -- 'CANARY', 'ROLLING', 'ALL_AT_ONCE', 'MANUAL'
    status          NVARCHAR(20) DEFAULT 'PENDING', -- 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'ROLLED_BACK'
    started_at      DATETIME2,
    completed_at    DATETIME2,
    created_by      NVARCHAR(100),
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);
GO

-- ─── Deployment → Agency (many-to-many) ──────────────────────
IF OBJECT_ID('dbo.deployment_agencies', 'U') IS NULL
CREATE TABLE dbo.deployment_agencies (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    deployment_id   BIGINT NOT NULL REFERENCES dbo.deployments(id),
    agency_id       INT NOT NULL REFERENCES dbo.agencies(id),
    status          NVARCHAR(20) DEFAULT 'PENDING', -- 'PENDING', 'DOWNLOADING', 'DOWNLOADED', 'INSTALLING', 'SUCCESS', 'FAILED', 'ROLLED_BACK'
    error_message   NVARCHAR(MAX),
    started_at      DATETIME2,
    completed_at    DATETIME2,
    agent_version   NVARCHAR(20),
    log_output      NVARCHAR(MAX),
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE UNIQUE INDEX IX_deployment_agency ON dbo.deployment_agencies(deployment_id, agency_id);
GO

-- ─── Audit Log (SHA-256 chain per deployment — Ley 126-2012) ─
IF OBJECT_ID('dbo.deployment_audit', 'U') IS NULL
CREATE TABLE dbo.deployment_audit (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    deployment_id   BIGINT NOT NULL REFERENCES dbo.deployments(id),
    event_type      NVARCHAR(50) NOT NULL,          -- 'PUBLISHED', 'DOWNLOADED', 'INSTALLED', 'VERIFIED', 'ROLLED_BACK'
    event_detail    NVARCHAR(MAX),
    event_hash      NVARCHAR(64),                   -- SHA-256 of this event
    chain_hash      NVARCHAR(64),                   -- SHA-256(prev_chain_hash + event_hash)
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE INDEX IX_audit_deployment ON dbo.deployment_audit(deployment_id);
GO

-- ─── Agent Registry (agent instances reporting in) ───────────
IF OBJECT_ID('dbo.agent_heartbeats', 'U') IS NULL
CREATE TABLE dbo.agent_heartbeats (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    agency_id       INT NOT NULL REFERENCES dbo.agencies(id),
    agent_version   NVARCHAR(20),
    os_info         NVARCHAR(500),                  -- 'Linux 6.8.0-124-generic' or 'Windows Server 2022'
    python_version  NVARCHAR(20),
    cpu_pct         DECIMAL(5,2),
    mem_pct         DECIMAL(5,2),
    disk_pct        DECIMAL(5,2),
    installed_apps  NVARCHAR(MAX),                  -- JSON: {app_key: version}
    created_at      DATETIME2 DEFAULT SYSUTCDATETIME()
);

CREATE INDEX IX_heartbeats_agency ON dbo.agent_heartbeats(agency_id, created_at DESC);
GO

PRINT '✅ FBIB Deploy Hub — Registry schema created';
GO

-- ─── Sync State (per agency, per pipeline — tracks last sync) ─
IF OBJECT_ID('dbo.sync_state', 'U') IS NULL
CREATE TABLE dbo.sync_state (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    agency_id       INT NOT NULL REFERENCES dbo.agencies(id),
    pipeline_id     INT NOT NULL REFERENCES dbo.integration_pipelines(id),
    last_sync_at    DATETIME2,
    last_batch_id   UNIQUEIDENTIFIER,
    rows_synced     BIGINT DEFAULT 0,
    status          NVARCHAR(20) DEFAULT 'NEVER',  -- 'NEVER', 'SYNCING', 'SYNCED', 'FAILED'
    error_message   NVARCHAR(MAX),
    updated_at      DATETIME2 DEFAULT SYSUTCDATETIME(),

    CONSTRAINT UQ_sync_agency_pipeline UNIQUE (agency_id, pipeline_id)
);
GO

PRINT '✅ Sync state table created';
