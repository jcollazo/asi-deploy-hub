# ============================================================
# hub.py — ASI Deploy Hub: Central API Server
# ============================================================
import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyodbc
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

DB_CONN = os.getenv(
    "ASI_DEPLOY_DB",
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;"
    "DATABASE=ASIDeployHub;UID=sa;PWD=YourPassword;"
    "Encrypt=no;TrustServerCertificate=yes;",
)
ARTIFACT_STORE = Path(os.getenv("ASI_ARTIFACT_STORE", "/opt/data/asi-artifacts"))
ARTIFACT_STORE.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("asi-hub")

app = FastAPI(title="ASI Deploy Hub", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Models ───────────────────────────────────────────────────
class AgencyCreate(BaseModel):
    agency_key: str
    display_name: str
    hostname: Optional[str] = None
    os_type: str = "LINUX"
    metadata_json: Optional[dict] = None


class AppCreate(BaseModel):
    app_key: str
    display_name: str
    artifact_type: str = "ZIP"
    description: Optional[str] = None
    repo_url: Optional[str] = None


class ReleaseCreate(BaseModel):
    app_key: str
    release_tag: str
    version_semver: Optional[str] = None
    release_notes: Optional[str] = None
    deploy_script: Optional[str] = None


class DeploymentCreate(BaseModel):
    release_id: int
    agency_keys: list[str]
    strategy: str = "ALL_AT_ONCE"
    description: Optional[str] = None


class AgentHeartbeat(BaseModel):
    agency_key: str
    agent_version: str
    os_info: Optional[str] = None
    python_version: Optional[str] = None
    cpu_pct: Optional[float] = None
    mem_pct: Optional[float] = None
    disk_pct: Optional[float] = None
    installed_apps: Optional[dict] = None


class AgentReport(BaseModel):
    agency_key: str
    deployment_id: int
    status: str  # SUCCESS, FAILED
    error_message: Optional[str] = None
    log_output: Optional[str] = None


# ─── Agencies ─────────────────────────────────────────────────
@app.get("/api/agencies")
def list_agencies():
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute("SELECT * FROM dbo.agencies ORDER BY display_name")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@app.post("/api/agencies")
def create_agency(body: AgencyCreate):
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()
    meta = json.dumps(body.metadata_json) if body.metadata_json else None
    cur.execute(
        "INSERT INTO dbo.agencies (agency_key, display_name, hostname, os_type, metadata_json) "
        "VALUES (?, ?, ?, ?, ?)",
        body.agency_key, body.display_name, body.hostname, body.os_type, meta,
    )
    return {"status": "created", "agency_key": body.agency_key}


# ─── Applications ─────────────────────────────────────────────
@app.get("/api/apps")
def list_apps():
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute("SELECT * FROM dbo.applications ORDER BY display_name")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@app.post("/api/apps")
def create_app(body: AppCreate):
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dbo.applications (app_key, display_name, artifact_type, description, repo_url) "
        "VALUES (?, ?, ?, ?, ?)",
        body.app_key, body.display_name, body.artifact_type, body.description, body.repo_url,
    )
    return {"status": "created", "app_key": body.app_key}


# ─── Releases ─────────────────────────────────────────────────
@app.get("/api/releases")
def list_releases(app_key: Optional[str] = None):
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()
    if app_key:
        cur.execute(
            "SELECT r.*, a.display_name as app_name FROM dbo.releases r "
            "JOIN dbo.applications a ON r.app_id = a.id WHERE a.app_key=? ORDER BY r.created_at DESC",
            app_key,
        )
    else:
        cur.execute(
            "SELECT r.*, a.display_name as app_name FROM dbo.releases r "
            "JOIN dbo.applications a ON r.app_id = a.id ORDER BY r.created_at DESC"
        )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@app.post("/api/releases")
def create_release(body: ReleaseCreate):
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()
    cur.execute("SELECT id FROM dbo.applications WHERE app_key=?", body.app_key)
    app = cur.fetchone()
    if not app:
        raise HTTPException(404, f"App not found: {body.app_key}")
    cur.execute(
        "INSERT INTO dbo.releases (release_tag, app_id, version_semver, release_notes, deploy_script) "
        "VALUES (?, ?, ?, ?, ?)",
        body.release_tag, app[0], body.version_semver, body.release_notes, body.deploy_script,
    )
    return {"status": "created", "release_tag": body.release_tag}


@app.post("/api/releases/{release_id}/upload")
async def upload_artifact(release_id: int, file: UploadFile = File(...)):
    """Upload artifact file and compute SHA-256 hash."""
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()
    cur.execute("SELECT id, app_id FROM dbo.releases WHERE id=?", release_id)
    rel = cur.fetchone()
    if not rel:
        raise HTTPException(404, "Release not found")

    # Save artifact
    ext = Path(file.filename).suffix
    store_path = ARTIFACT_STORE / f"{release_id}_{file.filename}"

    hasher = hashlib.sha256()
    with open(store_path, "wb") as f:
        while chunk := await file.read(8192):
            f.write(chunk)
            hasher.update(chunk)

    artifact_hash = hasher.hexdigest()
    artifact_size = store_path.stat().st_size

    cur.execute(
        "UPDATE dbo.releases SET artifact_path=?, artifact_hash=?, artifact_size=?, status='PUBLISHED', published_at=SYSUTCDATETIME() "
        "WHERE id=?",
        str(store_path), artifact_hash, artifact_size, release_id,
    )

    # Audit
    _audit_event(cur, release_id, "PUBLISHED", f"Artifact uploaded: {file.filename}, SHA-256: {artifact_hash}")

    return {
        "status": "published",
        "release_id": release_id,
        "artifact_hash": artifact_hash,
        "artifact_size": artifact_size,
    }


# ─── Deployments ──────────────────────────────────────────────
@app.get("/api/deployments")
def list_deployments(limit: int = 20):
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute(
        f"SELECT TOP {limit} d.*, r.release_tag, a.display_name as app_name "
        "FROM dbo.deployments d "
        "JOIN dbo.releases r ON d.release_id = r.id "
        "JOIN dbo.applications a ON r.app_id = a.id "
        "ORDER BY d.created_at DESC"
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@app.post("/api/deployments")
def create_deployment(body: DeploymentCreate):
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()

    # Verify release exists
    cur.execute("SELECT id, release_tag FROM dbo.releases WHERE id=?", body.release_id)
    rel = cur.fetchone()
    if not rel:
        raise HTTPException(404, "Release not found")

    # Create deployment
    deploy_tag = f"{rel[1]}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    cur.execute(
        "INSERT INTO dbo.deployments (deployment_tag, release_id, strategy, description, status, "
        "started_at, created_by) VALUES (?, ?, ?, ?, 'IN_PROGRESS', SYSUTCDATETIME(), ?)",
        deploy_tag, body.release_id, body.strategy, body.description or f"Deploy {rel[1]}",
        body.description or "admin",
    )
    cur.execute("SELECT SCOPE_IDENTITY()")
    deployment_id = int(cur.fetchone()[0])

    # Assign agencies
    for akey in body.agency_keys:
        cur.execute("SELECT id FROM dbo.agencies WHERE agency_key=?", akey)
        ag = cur.fetchone()
        if ag:
            cur.execute(
                "INSERT INTO dbo.deployment_agencies (deployment_id, agency_id) VALUES (?, ?)",
                deployment_id, ag[0],
            )

    _audit_event(cur, deployment_id, "DEPLOYMENT_CREATED",
                 f"Release: {rel[1]}, Agencies: {body.agency_keys}, Strategy: {body.strategy}")

    return {
        "status": "in_progress",
        "deployment_id": deployment_id,
        "deployment_tag": deploy_tag,
        "agency_count": len(body.agency_keys),
    }


@app.get("/api/deployments/{deployment_id}/status")
def deployment_status(deployment_id: int):
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute(
        "SELECT da.agency_id, ag.display_name, ag.agency_key, da.status, da.error_message, "
        "da.started_at, da.completed_at "
        "FROM dbo.deployment_agencies da "
        "JOIN dbo.agencies ag ON da.agency_id = ag.id "
        "WHERE da.deployment_id=?", deployment_id
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


@app.post("/api/deployments/{deployment_id}/rollback")
def rollback_deployment(deployment_id: int):
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()
    cur.execute(
        "UPDATE dbo.deployments SET status='ROLLED_BACK', completed_at=SYSUTCDATETIME() WHERE id=?",
        deployment_id,
    )
    cur.execute(
        "UPDATE dbo.deployment_agencies SET status='ROLLED_BACK' WHERE deployment_id=?",
        deployment_id,
    )
    _audit_event(cur, deployment_id, "ROLLED_BACK", f"Deployment {deployment_id} rolled back")
    return {"status": "rolled_back", "deployment_id": deployment_id}


# ─── Agent API (called by agents in the field) ─────────────────
@app.get("/api/agent/pending")
def agent_pending_deployments(agency_key: str):
    """Agent polls this to check for pending deployments."""
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute(
        "SELECT d.id as deployment_id, d.deploy_type, d.release_tag, r.artifact_path, "
        "r.artifact_hash, r.artifact_size, r.deploy_script, "
        "COALESCE(a.display_name, 'Data Replica') as app_name, "
        "da.id as assignment_id "
        "FROM dbo.deployment_agencies da "
        "JOIN dbo.deployments d ON da.deployment_id = d.id "
        "JOIN dbo.releases r ON d.release_id = r.id "
        "LEFT JOIN dbo.applications a ON r.app_id = a.id "
        "JOIN dbo.agencies ag ON da.agency_id = ag.id "
        "WHERE ag.agency_key=? AND da.status='PENDING' "
        "ORDER BY d.created_at",
        agency_key,
    )
    cols = [c[0] for c in cur.description]
    pending = [dict(zip(cols, r)) for r in cur.fetchall()]

    # For DATA deployments, extract pipeline_key from release_tag (data_{pipeline}_{ts})
    for d in pending:
        if d.get("deploy_type") == "DATA":
            tag = d.get("release_tag", "")
            parts = tag.split("_")
            if len(parts) >= 2:
                d["pipeline_key"] = parts[1]

    conn.close()
    return {"agency_key": agency_key, "pending_count": len(pending), "deployments": pending}


@app.get("/api/agent/artifact/{release_id}")
def download_artifact(release_id: int):
    """Agent downloads the artifact file."""
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()
    cur.execute("SELECT artifact_path, artifact_hash FROM dbo.releases WHERE id=?", release_id)
    rel = cur.fetchone()
    conn.close()
    if not rel or not rel[0]:
        raise HTTPException(404, "Artifact not found")
    return FileResponse(rel[0], filename=Path(rel[0]).name)


@app.post("/api/agent/heartbeat")
def agent_heartbeat(body: AgentHeartbeat):
    """Agent sends periodic heartbeat with system info."""
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()
    cur.execute("SELECT id FROM dbo.agencies WHERE agency_key=?", body.agency_key)
    ag = cur.fetchone()
    if not ag:
        raise HTTPException(404, f"Agency not found: {body.agency_key}")

    installed = json.dumps(body.installed_apps) if body.installed_apps else None
    cur.execute(
        "INSERT INTO dbo.agent_heartbeats (agency_id, agent_version, os_info, python_version, "
        "cpu_pct, mem_pct, disk_pct, installed_apps) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ag[0], body.agent_version, body.os_info, body.python_version,
        body.cpu_pct, body.mem_pct, body.disk_pct, installed,
    )

    # Update last_seen
    cur.execute(
        "UPDATE dbo.agencies SET agent_version=?, last_seen_at=SYSUTCDATETIME() WHERE id=?",
        body.agent_version, ag[0],
    )
    return {"status": "ok", "agency_key": body.agency_key}


@app.post("/api/agent/report")
def agent_report(body: AgentReport):
    """Agent reports deployment result."""
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()

    cur.execute("SELECT id FROM dbo.agencies WHERE agency_key=?", body.agency_key)
    ag = cur.fetchone()
    if not ag:
        raise HTTPException(404, f"Agency not found: {body.agency_key}")

    cur.execute(
        "UPDATE dbo.deployment_agencies SET status=?, error_message=?, log_output=?, "
        "completed_at=SYSUTCDATETIME() WHERE deployment_id=? AND agency_id=?",
        body.status, body.error_message, body.log_output, body.deployment_id, ag[0],
    )

    _audit_event(cur, body.deployment_id, body.status,
                 f"Agency: {body.agency_key}, Error: {body.error_message or 'None'}")

    # Check if all agencies done
    cur.execute(
        "SELECT COUNT(*) FROM dbo.deployment_agencies WHERE deployment_id=? AND status='PENDING'",
        body.deployment_id,
    )
    pending = cur.fetchone()[0]
    if pending == 0:
        cur.execute(
            "UPDATE dbo.deployments SET status='COMPLETED', completed_at=SYSUTCDATETIME() WHERE id=?",
            body.deployment_id,
        )

    return {"status": "reported", "agency_key": body.agency_key, "deployment_id": body.deployment_id}


# ─── Health ───────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ─── Audit Helper ─────────────────────────────────────────────
def _audit_event(cursor, deployment_id: int, event_type: str, detail: str):
    event_hash = hashlib.sha256(f"{deployment_id}:{event_type}:{detail}:{datetime.now().isoformat()}".encode()).hexdigest()

    cursor.execute(
        "SELECT TOP 1 chain_hash FROM dbo.deployment_audit WHERE deployment_id=? ORDER BY id DESC",
        deployment_id,
    )
    prev = cursor.fetchone()
    prev_hash = prev[0] if prev else ""

    chain_hash = hashlib.sha256(f"{prev_hash}{event_hash}".encode()).hexdigest()

    cursor.execute(
        "INSERT INTO dbo.deployment_audit (deployment_id, event_type, event_detail, event_hash, chain_hash) "
        "VALUES (?, ?, ?, ?, ?)",
        deployment_id, event_type, detail, event_hash, chain_hash,
    )


# ─── Agency Portal API (read-only, filtered by agency_key) ─────
@app.get("/api/agency/{agency_key}/dashboard")
def agency_dashboard(agency_key: str):
    """Read-only dashboard for a specific agency."""
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()

    # Agency info
    cur.execute(
        "SELECT id, agency_key, display_name, hostname, os_type, agent_version, last_seen_at, is_active "
        "FROM dbo.agencies WHERE agency_key=?", agency_key
    )
    ag_cols = [c[0] for c in cur.description]
    ag_row = cur.fetchone()
    if not ag_row:
        raise HTTPException(404, f"Agency not found: {agency_key}")
    agency = dict(zip(ag_cols, ag_row))

    # Recent deployments for this agency
    cur.execute(
        "SELECT TOP 10 d.deployment_tag, r.release_tag, a.display_name as app_name, "
        "da.status, da.error_message, da.completed_at "
        "FROM dbo.deployment_agencies da "
        "JOIN dbo.deployments d ON da.deployment_id = d.id "
        "JOIN dbo.releases r ON d.release_id = r.id "
        "JOIN dbo.applications a ON r.app_id = a.id "
        "WHERE da.agency_id=? "
        "ORDER BY da.id DESC", agency["id"]
    )
    dep_cols = [c[0] for c in cur.description]
    deployments = [dict(zip(dep_cols, r)) for r in cur.fetchall()]

    # Latest heartbeat (system health)
    cur.execute(
        "SELECT TOP 1 cpu_pct, mem_pct, disk_pct, os_info, agent_version, installed_apps, created_at "
        "FROM dbo.agent_heartbeats WHERE agency_id=? ORDER BY id DESC", agency["id"]
    )
    hb_cols = [c[0] for c in cur.description]
    hb_row = cur.fetchone()
    heartbeat = dict(zip(hb_cols, hb_row)) if hb_row else None

    conn.close()

    return {
        "agency": agency,
        "deployments": deployments,
        "heartbeat": heartbeat,
    }


# ─── Data Sync API (Agent pulls data for agency's local DB) ────
@app.get("/api/agent/data/{agency_key}")
def agent_pull_data(
    agency_key: str,
    pipeline_key: str = Query(..., description="Pipeline to sync (e.g., 'ukg_employee_import')"),
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
):
    """Agent pulls paginated data from central DB for sync to agency's local DB.

    Returns rows from the most recent COMPLETED batch that this agency hasn't synced yet.
    """
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()

    # Resolve agency
    cur.execute("SELECT id FROM dbo.agencies WHERE agency_key=?", agency_key)
    ag = cur.fetchone()
    if not ag:
        raise HTTPException(404, f"Agency not found: {agency_key}")
    agency_id = ag[0]

    # Resolve pipeline
    cur.execute("SELECT id FROM dbo.integration_pipelines WHERE pipeline_key=?", pipeline_key)
    pipe = cur.fetchone()
    if not pipe:
        raise HTTPException(404, f"Pipeline not found: {pipeline_key}")
    pipeline_id = pipe[0]

    # Get last sync state
    cur.execute(
        "SELECT last_batch_id, last_sync_at FROM dbo.sync_state "
        "WHERE agency_id=? AND pipeline_id=?", agency_id, pipeline_id
    )
    sync = cur.fetchone()
    last_batch_id = sync[0] if sync else None

    # Find the latest COMPLETED batch
    cur.execute(
        "SELECT TOP 1 batch_id, total_rows FROM dbo.import_log "
        "WHERE pipeline_id=? AND status='COMPLETED' "
        "ORDER BY completed_at DESC", pipeline_id
    )
    latest = cur.fetchone()
    if not latest:
        return {"agency_key": agency_key, "pipeline_key": pipeline_key, "status": "NO_DATA", "rows": []}

    latest_batch_id = str(latest[0])

    # If this agency already synced the latest batch, nothing new
    if last_batch_id and str(last_batch_id) == latest_batch_id:
        return {
            "agency_key": agency_key,
            "pipeline_key": pipeline_key,
            "status": "UP_TO_DATE",
            "batch_id": latest_batch_id,
            "rows": [],
            "total_rows": latest[1],
        }

    # Get staging table for this pipeline
    cur.execute(
        "SELECT table_name FROM dbo.staging_registry WHERE pipeline_id=? AND is_active=1", pipeline_id
    )
    staging = cur.fetchone()
    staging_table = staging[0] if staging else "dbo.import_staging"

    # Get field mappings (source → target column names)
    cur.execute(
        "SELECT source_field, target_column, transform FROM dbo.field_mappings "
        "WHERE pipeline_id=? ORDER BY id", pipeline_id
    )
    mappings = [(m[0], m[1], m[2]) for m in cur.fetchall()]
    target_cols = [m[1] for m in mappings]

    # Pull paginated rows
    col_list = ", ".join(target_cols)
    cur.execute(
        f"SELECT {col_list} FROM {staging_table} "
        f"WHERE batch_id=? "
        f"ORDER BY id "
        f"OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY",
        latest_batch_id,
    )
    col_names = [c[0] for c in cur.description]
    rows = [dict(zip(col_names, r)) for r in cur.fetchall()]

    conn.close()

    return {
        "agency_key": agency_key,
        "pipeline_key": pipeline_key,
        "status": "DATA_AVAILABLE",
        "batch_id": latest_batch_id,
        "total_rows": latest[1],
        "offset": offset,
        "limit": limit,
        "rows": rows,
        "columns": col_names,
        "has_more": len(rows) == limit,
    }


@app.post("/api/agent/data/{agency_key}/synced")
def agent_report_sync(
    agency_key: str,
    pipeline_key: str = Query(...),
    batch_id: str = Query(...),
    rows_synced: int = Query(0),
    status: str = Query("SYNCED"),
):
    """Agent reports that a batch has been synced to the agency's local DB."""
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()

    cur.execute("SELECT id FROM dbo.agencies WHERE agency_key=?", agency_key)
    ag = cur.fetchone()
    if not ag:
        raise HTTPException(404, f"Agency not found: {agency_key}")
    agency_id = ag[0]

    cur.execute("SELECT id FROM dbo.integration_pipelines WHERE pipeline_key=?", pipeline_key)
    pipe = cur.fetchone()
    if not pipe:
        raise HTTPException(404, f"Pipeline not found: {pipeline_key}")
    pipeline_id = pipe[0]

    cur.execute(
        "MERGE INTO dbo.sync_state AS target "
        "USING (SELECT ? AS agency_id, ? AS pipeline_id) AS source "
        "ON target.agency_id = source.agency_id AND target.pipeline_id = source.pipeline_id "
        "WHEN MATCHED THEN UPDATE SET last_batch_id=?, last_sync_at=SYSUTCDATETIME(), "
        "  rows_synced=rows_synced+?, status=?, error_message=NULL, updated_at=SYSUTCDATETIME() "
        "WHEN NOT MATCHED THEN INSERT (agency_id, pipeline_id, last_batch_id, last_sync_at, rows_synced, status) "
        "  VALUES (source.agency_id, source.pipeline_id, ?, SYSUTCDATETIME(), ?, ?);",
        agency_id, pipeline_id, batch_id, rows_synced, status,
        batch_id, rows_synced, status,
    )

    return {"status": "ok", "agency_key": agency_key, "pipeline_key": pipeline_key, "batch_id": batch_id}


# ─── Data Replica Generation ──────────────────────────────────
class ReplicaRequest(BaseModel):
    pipeline_key: str = "ukg_employee_import"
    agency_keys: Optional[list[str]] = None  # None = all agencies

@app.post("/api/admin/generate-replicas")
def generate_replicas(req: ReplicaRequest):
    """Generate SQLite replicas for agencies. Called via cron daily.
    
    For each agency, queries SQL Server for their filtered data,
    writes a SQLite file, stores as artifact, creates DATA deployment.
    """
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()

    # Get agencies
    if req.agency_keys:
        placeholders = ",".join(["?"] * len(req.agency_keys))
        cur.execute(f"SELECT id, agency_key, display_name FROM dbo.agencies WHERE agency_key IN ({placeholders})", *req.agency_keys)
    else:
        cur.execute("SELECT id, agency_key, display_name FROM dbo.agencies WHERE status='ACTIVE'")
    agencies = cur.fetchall()

    # Get pipeline
    cur.execute("SELECT id, pipeline_key, target_table FROM dbo.integration_pipelines WHERE pipeline_key=?", req.pipeline_key)
    pipe = cur.fetchone()
    if not pipe:
        conn.close()
        raise HTTPException(404, f"Pipeline not found: {req.pipeline_key}")
    pipeline_id, pipeline_key, target_table = pipe

    results = []
    for agency_id, agency_key, display_name in agencies:
        try:
            # Get agency's selected columns
            cur.execute(
                "SELECT selected_columns FROM dbo.agencies WHERE id=?", agency_id
            )
            cols_row = cur.fetchone()
            selected_cols = None
            if cols_row and cols_row[0]:
                selected_cols = [c.strip() for c in cols_row[0].split(",") if c.strip()]

            replica_path = _build_sqlite_replica(cur, agency_key, target_table, pipeline_key, selected_cols)
            artifact_hash = _sha256_file(replica_path)
            artifact_size = os.path.getsize(replica_path)

            # Store artifact
            artifact_path = f"replicas/{agency_key}/{pipeline_key}.db"
            dest = ARTIFACT_STORE / artifact_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(replica_path, dest)

            # Create release for this data replica
            ts = datetime.utcnow()
            release_tag = f"data_{pipeline_key}_{ts.strftime('%Y%m%d_%H%M%S')}"

            cur.execute(
                "INSERT INTO dbo.releases (app_key, release_tag, artifact_path, artifact_hash, artifact_size, release_notes) "
                "OUTPUT INSERTED.id VALUES ('data_replica', ?, ?, ?, ?, ?)",
                release_tag, artifact_path, artifact_hash, artifact_size,
                f"Data replica for {agency_key} — {pipeline_key}",
            )
            release_id = cur.fetchone()[0]

            # Create deployment for this agency
            cur.execute(
                "INSERT INTO dbo.deployments (release_id, app_key, release_tag, deploy_type, status, created_at) "
                "VALUES (?, 'data_replica', ?, 'DATA', 'PENDING', SYSUTCDATETIME())",
                release_id, release_tag,
            )

            # Assign deployment to agency
            cur.execute(
                "INSERT INTO dbo.deployment_agencies (deployment_id, agency_id, status, created_at) "
                "VALUES ((SELECT MAX(id) FROM dbo.deployments), ?, 'PENDING', SYSUTCDATETIME())",
                agency_id,
            )

            # Cleanup temp file
            os.unlink(replica_path)

            results.append({
                "agency_key": agency_key,
                "status": "OK",
                "rows": _count_rows(replica_path) if os.path.exists(replica_path) else 0,
                "artifact_hash": artifact_hash,
                "size_kb": artifact_size // 1024,
            })
            logger.info("Replica OK: %s — %d KB, SHA-256: %s...", agency_key, artifact_size // 1024, artifact_hash[:16])

        except Exception as e:
            logger.exception("Replica FAILED for %s: %s", agency_key, e)
            results.append({"agency_key": agency_key, "status": "FAILED", "error": str(e)})

    conn.close()
    return {"pipeline_key": pipeline_key, "agencies_processed": len(agencies), "results": results}


def _build_sqlite_replica(cur, agency_key: str, table: str, pipeline_key: str, selected_cols: list[str] | None = None) -> str:
    """Query SQL Server for agency's data, filter columns if selected, export to SQLite file."""
    import sqlite3

    # Query data filtered by agency
    agency_col = _agency_column(pipeline_key)

    # Get all columns from SQL Server first
    cur.execute(f"SELECT TOP 0 * FROM dbo.{table}")
    all_col_names = [c[0] for c in cur.description]

    # Determine which columns to include
    if selected_cols:
        # Only include selected columns (case-insensitive match)
        selected_lower = {c.lower() for c in selected_cols}
        # Always include agency column and eeid
        selected_lower.add(agency_col.lower())
        selected_lower.add("eeid")
        col_names = [c for c in all_col_names if c.lower() in selected_lower]
    else:
        col_names = all_col_names

    col_str = ", ".join([f"[{c}]" for c in col_names])
    query = f"SELECT {col_str} FROM dbo.{table} WHERE {agency_col}=?"
    cur.execute(query, agency_key)
    rows = cur.fetchall()

    # Write to temp SQLite
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp_path = tmp.name
    tmp.close()

    sql_conn = sqlite3.connect(tmp_path)
    sql_conn.execute(f"PRAGMA journal_mode=WAL")
    sql_conn.execute(f"PRAGMA application_id = 0x41534901")  # 'ASI\x01' magic

    # Create table
    col_defs = ", ".join([f"[{c}] TEXT" for c in col_names])
    sql_conn.execute(f"CREATE TABLE [{table}] ({col_defs})")

    # Insert data in batches
    placeholders = ", ".join(["?"] * len(col_names))
    col_list = ", ".join([f"[{c}]" for c in col_names])
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        sql_conn.executemany(
            f"INSERT INTO [{table}] ({col_list}) VALUES ({placeholders})", batch
        )

    # Create index on agency column
    sql_conn.execute(f"CREATE INDEX idx_agency ON [{table}]([{agency_col}])")

    # Add metadata table
    sql_conn.execute(
        "CREATE TABLE _asi_meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    sql_conn.executemany(
        "INSERT INTO _asi_meta VALUES (?, ?)",
        [
            ("agency_key", agency_key),
            ("pipeline_key", pipeline_key),
            ("generated_at", datetime.utcnow().isoformat() + "Z"),
            ("total_rows", str(len(rows))),
            ("columns", ",".join(col_names)),
            ("columns_count", str(len(col_names))),
            ("filtered", "yes" if selected_cols else "no"),
            ("source", "PR Integration Hub — SQL Server"),
            ("access", "READ-ONLY — SELECT only. No INSERT/UPDATE/DELETE."),
        ],
    )

    sql_conn.commit()
    sql_conn.close()

    return tmp_path


def _agency_column(pipeline_key: str) -> str:
    """Map pipeline to agency filter column."""
    mapping = {
        "ukg_employee_import": "agency",
        "sap_payroll_import": "agency",
        "oracle_fin_import": "agency_code",
    }
    return mapping.get(pipeline_key, "agency")


def _sha256_file(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _count_rows(filepath: str) -> int:
    """Count rows in SQLite file."""
    import sqlite3
    conn = sqlite3.connect(f"file:{filepath}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT value FROM _asi_meta WHERE key='total_rows'")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 0


# ─── Column Selection (per agency) ─────────────────────────────
class ColumnSelectionRequest(BaseModel):
    columns: list[str]  # ['eeid', 'first_name', 'last_name'] | [] = ALL

@app.get("/api/admin/pipelines/{pipeline_key}/columns")
def get_available_columns(pipeline_key: str):
    """Get available columns for a pipeline (from field_mappings)."""
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM dbo.integration_pipelines WHERE pipeline_key=?",
        pipeline_key,
    )
    pipe = cur.fetchone()
    if not pipe:
        conn.close()
        raise HTTPException(404, f"Pipeline not found: {pipeline_key}")

    cur.execute(
        "SELECT source_field, target_column, data_type, is_required "
        "FROM dbo.field_mappings WHERE pipeline_id=? ORDER BY id",
        pipe[0],
    )
    columns = [
        {
            "source_field": r[0],
            "target_column": r[1],
            "data_type": r[2],
            "is_required": bool(r[3]),
        }
        for r in cur.fetchall()
    ]
    conn.close()

    return {
        "pipeline_key": pipeline_key,
        "total_columns": len(columns),
        "columns": columns,
    }


@app.get("/api/agent/{agency_key}/config")
def agent_get_config(agency_key: str):
    """Agent fetches its configuration (selected columns, pipelines, etc.)."""
    conn = pyodbc.connect(DB_CONN)
    cur = conn.cursor()

    cur.execute(
        "SELECT agency_key, display_name, selected_columns, os_type, hostname "
        "FROM dbo.agencies WHERE agency_key=? AND is_active=1",
        agency_key,
    )
    ag = cur.fetchone()
    conn.close()

    if not ag:
        raise HTTPException(404, f"Agency not found: {agency_key}")

    selected = ag[2]
    columns = [c.strip() for c in selected.split(",") if c.strip()] if selected else None

    return {
        "agency_key": ag[0],
        "display_name": ag[1],
        "selected_columns": columns,  # null = ALL, [] = ALL, ['eeid','last_name'] = filtered
        "os_type": ag[3],
        "hostname": ag[4],
    }


@app.put("/api/admin/agencies/{agency_key}/columns")
def set_agency_columns(agency_key: str, req: ColumnSelectionRequest):
    """Configure which columns an agency receives in its data replica.
    
    Pass [] or null to receive ALL columns.
    Pass ['eeid', 'first_name', 'last_name'] to receive only those.
    """
    conn = pyodbc.connect(DB_CONN, autocommit=True)
    cur = conn.cursor()

    cur.execute("SELECT id, display_name FROM dbo.agencies WHERE agency_key=?", agency_key)
    ag = cur.fetchone()
    if not ag:
        conn.close()
        raise HTTPException(404, f"Agency not found: {agency_key}")

    # Validate columns exist
    valid = set()
    cur.execute(
        "SELECT target_column FROM dbo.field_mappings m "
        "JOIN dbo.integration_pipelines p ON m.pipeline_id = p.id "
        "WHERE p.pipeline_key='ukg_employee_import'"
    )
    for r in cur.fetchall():
        valid.add(r[0].lower())

    for col in req.columns:
        if col.lower() not in valid:
            conn.close()
            raise HTTPException(400, f"Unknown column: {col}. Available: {sorted(valid)}")

    selected_str = ",".join(req.columns) if req.columns else None

    cur.execute(
        "UPDATE dbo.agencies SET selected_columns=?, updated_at=SYSUTCDATETIME() WHERE agency_key=?",
        selected_str, agency_key,
    )

    conn.close()
    return {
        "agency_key": agency_key,
        "selected_columns": req.columns if req.columns else "ALL",
        "status": "updated",
    }


# ─── Static (React admin portal) ──────────────────────────────
frontend = Path(__file__).parent.parent / "frontend" / "dist"
if frontend.exists():
    app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8900)
