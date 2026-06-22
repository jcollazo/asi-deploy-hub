# ============================================================
# hub.py — ASI Deploy Hub: Central API Server
# ============================================================
import hashlib
import json
import os
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
        "SELECT d.id as deployment_id, d.deployment_tag, r.release_tag, r.artifact_path, "
        "r.artifact_hash, r.artifact_size, r.deploy_script, a.display_name as app_name, "
        "da.id as assignment_id "
        "FROM dbo.deployment_agencies da "
        "JOIN dbo.deployments d ON da.deployment_id = d.id "
        "JOIN dbo.releases r ON d.release_id = r.id "
        "JOIN dbo.applications a ON r.app_id = a.id "
        "JOIN dbo.agencies ag ON da.agency_id = ag.id "
        "WHERE ag.agency_key=? AND da.status='PENDING' AND r.status='PUBLISHED' "
        "ORDER BY d.created_at",
        agency_key,
    )
    cols = [c[0] for c in cur.description]
    pending = [dict(zip(cols, r)) for r in cur.fetchall()]
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


# ─── Static (React admin portal) ──────────────────────────────
frontend = Path(__file__).parent.parent / "frontend" / "dist"
if frontend.exists():
    app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8900)
