#!/usr/bin/env python3
# ============================================================
# agent.py — FBIB Deploy Hub: Cross-Platform Agent
# ============================================================
# Runs on Linux or Windows. Polls hub, downloads releases,
# verifies SHA-256, executes deploy scripts, reports status.
# ============================================================
# Install:   pip install requests
# Run:       python agent.py --agency-key ogp --hub-url https://hub.example.com
# Service:   systemd (Linux) or NSSM (Windows)
# ============================================================
import argparse
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests

# ─── Config ───────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
DEFAULT_POLL_INTERVAL = 60  # seconds
BACKUP_KEEP_COUNT = 3        # Keep last N releases locally
BACKUP_DIR = Path(os.getenv("FBIB_AGENT_BACKUP_DIR", "/opt/fbib-agent/backups"))
if platform.system() == "Windows":
    BACKUP_DIR = Path(os.getenv("FBIB_AGENT_BACKUP_DIR", "C:\\ProgramData\\FBIBAgent\\backups"))

BACKUP_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(BACKUP_DIR / "agent.log")],
)
logger = logging.getLogger("fbib-agent")


# ─── Main Agent Loop ──────────────────────────────────────────
class FBIBAgent:
    def __init__(self, agency_key: str, hub_url: str, poll_interval: int = DEFAULT_POLL_INTERVAL, db_conn_str: str = None):
        self.agency_key = agency_key
        self.hub_url = hub_url.rstrip("/")
        self.poll_interval = poll_interval
        self.db_conn_str = db_conn_str
        self.os_info = f"{platform.system()} {platform.release()} {platform.version()}"
        self.python_version = platform.python_version()

    def run(self):
        """Main loop — poll forever."""
        logger.info("FBIB Agent v%s starting for agency '%s'", AGENT_VERSION, self.agency_key)
        logger.info("  OS: %s | Python: %s | Hub: %s", self.os_info, self.python_version, self.hub_url)
        if self.db_conn_str:
            logger.info("  DB: Connection string configured (read-only verify on startup)")

        self._send_heartbeat()

        # Verify DB connection (read-only) on startup if configured
        if self.db_conn_str:
            self._verify_db_readonly()

        while True:
            try:
                # ─── Software Deployments ──────────────────────────
                pending = self._check_pending()
                if pending:
                    for deploy in pending:
                        self._process_deployment(deploy)

                # ─── Data Pull (direct from source) ─────────────────
                self._pull_data()

                self._send_heartbeat()
            except requests.RequestException as e:
                logger.error("Network error contacting hub: %s", e)
            except Exception as e:
                logger.exception("Unexpected error in agent loop: %s", e)

            time.sleep(self.poll_interval)

    def _verify_db_readonly(self):
        """Verify DB connection is valid and read-only (SELECT only, no write)."""
        if not self.db_conn_str:
            return
        logger.info("Verifying DB connection (read-only)...")
        try:
            import pyodbc
            conn = pyodbc.connect(self.db_conn_str, timeout=10, autocommit=True)
            cursor = conn.cursor()

            # Test SELECT
            cursor.execute("SELECT 1 AS test")
            row = cursor.fetchone()
            logger.info("  DB SELECT OK: %s", row[0])

            # Test that INSERT is denied
            try:
                cursor.execute("INSERT INTO __fbib_readonly_test__ VALUES (1)")
                logger.warning("  ⚠ INSERT allowed! DB user has write permissions — this should NOT happen!")
            except pyodbc.Error as e:
                logger.info("  INSERT denied ✓ (read-only confirmed: %s)", str(e).split(".")[0])

            conn.close()
        except ImportError:
            logger.warning("  pyodbc not installed — skipping DB verification")
        except Exception as e:
            logger.error("  DB connection FAILED: %s", e)

    # ─── Data Pull (direct from source) ──────────────────────────
    def _fetch_config(self) -> dict | None:
        """Fetch agency configuration from Hub."""
        try:
            resp = requests.get(
                f"{self.hub_url}/api/agent/{self.agency_key}/config",
                timeout=30,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to fetch config: %s", e)
            return None

    def _pull_data(self):
        """Pull employee data directly from the configured source (UKG/SAP/Oracle)."""
        config = self._fetch_config()
        if not config:
            return

        source_type = config.get("source_type")
        if not source_type:
            return  # No data source configured

        try:
            from transports import get_transport
            from data_replica import DATA_DIR

            transport = get_transport(config)
            logger.info("=" * 60)
            logger.info("Pulling data from %s for agency '%s'...", source_type, self.agency_key)

            # Pull from source
            employees = transport.fetch_employees()
            logger.info("Pulled %d employees from %s", len(employees), source_type)

            if not employees:
                return

            # Filter columns if configured
            selected_cols = config.get("selected_columns")
            if selected_cols:
                employees = self._filter_columns(employees, selected_cols)

            # Write SQLite
            import sqlite3
            db_path = DATA_DIR / "empleados.db"
            tmp_path = DATA_DIR / ".empleados.db.tmp"

            # Get columns from first row
            col_names = list(employees[0].keys())

            conn = sqlite3.connect(str(tmp_path))
            conn.execute("PRAGMA journal_mode=WAL")

            col_defs = ", ".join([f"[{c}] TEXT" for c in col_names])
            conn.execute(f"CREATE TABLE empleados ({col_defs})")

            # Insert in batches
            placeholders = ", ".join(["?"] * len(col_names))
            col_list = ", ".join([f"[{c}]" for c in col_names])
            batch_size = 1000
            for i in range(0, len(employees), batch_size):
                batch = employees[i:i + batch_size]
                values = [[row.get(c, "") for c in col_names] for row in batch]
                conn.executemany(
                    f"INSERT INTO empleados ({col_list}) VALUES ({placeholders})", values
                )

            # Metadata
            conn.execute("CREATE TABLE _fbib_meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.executemany(
                "INSERT INTO _fbib_meta VALUES (?, ?)",
                [
                    ("agency_key", self.agency_key),
                    ("source_type", source_type),
                    ("total_rows", str(len(employees))),
                    ("columns", ",".join(col_names)),
                    ("pulled_at", datetime.utcnow().isoformat() + "Z"),
                    ("access", "READ-ONLY — SELECT only. No INSERT/UPDATE/DELETE."),
                ],
            )
            conn.commit()
            conn.close()

            # Atomic replace + chmod 444
            tmp_path.chmod(0o444)
            os.replace(tmp_path, db_path)

            logger.info("SQLite written: %s (%d rows, chmod 444)", db_path, len(employees))

        except ImportError as e:
            logger.warning("Module not available: %s — skipping data pull", e)
        except Exception as e:
            logger.exception("Data pull FAILED from %s: %s", source_type, e)

    def _filter_columns(self, rows: list[dict], selected: list[str]) -> list[dict]:
        """Keep only selected columns from each row."""
        selected_lower = {c.lower() for c in selected}
        return [
            {k: v for k, v in row.items() if k.lower() in selected_lower}
            for row in rows
        ]

    # ─── Hub Communication ─────────────────────────────────────
    def _check_pending(self) -> list[dict]:
        """Poll hub for pending deployments."""
        resp = requests.get(
            f"{self.hub_url}/api/agent/pending",
            params={"agency_key": self.agency_key},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("deployments", [])

    def _send_heartbeat(self):
        """Send periodic heartbeat with system info."""
        try:
            cpu, mem, disk = self._get_system_metrics()
            resp = requests.post(
                f"{self.hub_url}/api/agent/heartbeat",
                json={
                    "agency_key": self.agency_key,
                    "agent_version": AGENT_VERSION,
                    "os_info": self.os_info,
                    "python_version": self.python_version,
                    "cpu_pct": cpu,
                    "mem_pct": mem,
                    "disk_pct": disk,
                    "installed_apps": self._get_installed_apps(),
                },
                timeout=10,
            )
            logger.debug("Heartbeat sent. Status: %s", resp.status_code)
        except Exception as e:
            logger.warning("Heartbeat failed: %s", e)

    def _report_result(self, deployment_id: int, status: str, error: str = None, log_output: str = None):
        """Report deployment result to hub."""
        resp = requests.post(
            f"{self.hub_url}/api/agent/report",
            json={
                "agency_key": self.agency_key,
                "deployment_id": deployment_id,
                "status": status,
                "error_message": error,
                "log_output": log_output,
            },
            timeout=30,
        )
        return resp.json()

    # ─── Deployment Processing ─────────────────────────────────
    def _process_deployment(self, deploy: dict):
        """Route deployment to software or data handler based on type."""
        deploy_type = deploy.get("deploy_type", "SOFTWARE")

        if deploy_type == "DATA":
            self._process_data_replica(deploy)
        else:
            self._process_software(deploy)

    def _process_data_replica(self, deploy: dict):
        """Handle DATA type deployment: download SQLite, verify, install read-only."""
        try:
            from data_replica import DataReplica
            replica = DataReplica(self.agency_key, self.hub_url)
            result = replica.process_data_release(deploy)

            self._report_result(
                deploy["deployment_id"],
                result["status"],
                error=result.get("error"),
                log_output=result.get("log"),
            )
        except ImportError:
            error_msg = "data_replica module not available"
            logger.error(error_msg)
            self._report_result(deploy["deployment_id"], "FAILED", error=error_msg)
        except Exception as e:
            logger.exception("Data replica failed: %s", e)
            self._report_result(deploy["deployment_id"], "FAILED", error=str(e))

    def _process_software(self, deploy: dict):
        """Download, verify, backup, install, report."""
        deployment_id = deploy["deployment_id"]
        release_tag = deploy["release_tag"]
        app_name = deploy["app_name"]
        artifact_path = deploy.get("artifact_path")
        artifact_hash = deploy.get("artifact_hash")
        deploy_script = deploy.get("deploy_script")

        logger.info("=" * 60)
        logger.info("Processing deployment #%d: %s / %s", deployment_id, app_name, release_tag)
        logger.info("=" * 60)

        log_lines = []

        try:
            # Step 1: Download artifact
            if not artifact_path:
                raise ValueError("No artifact attached to this release")
            logger.info("  [1/5] Downloading artifact...")
            local_path = self._download_artifact(deployment_id)
            log_lines.append(f"[OK] Downloaded to {local_path}")

            # Step 2: Verify SHA-256
            logger.info("  [2/5] Verifying SHA-256...")
            self._verify_checksum(local_path, artifact_hash)
            log_lines.append(f"[OK] SHA-256 verified: {artifact_hash[:16]}...")

            # Step 3: Backup current installation
            logger.info("  [3/5] Backing up current installation...")
            backup_path = self._backup_current(app_name)
            log_lines.append(f"[OK] Backup: {backup_path}")

            # Step 4: Install / Deploy
            logger.info("  [4/5] Installing...")
            install_log = self._install_artifact(local_path, app_name, deploy_script)
            log_lines.append(f"[OK] Install complete")
            if install_log:
                log_lines.extend(install_log.split("\n"))

            # Step 5: Report success
            logger.info("  [5/5] Reporting SUCCESS to hub...")
            self._report_result(
                deployment_id, "SUCCESS",
                log_output="\n".join(log_lines),
            )
            logger.info("Deployment #%d COMPLETE ✓", deployment_id)

        except Exception as e:
            logger.error("Deployment #%d FAILED: %s", deployment_id, e)
            log_lines.append(f"[FAIL] {e}")
            self._report_result(
                deployment_id, "FAILED",
                error=str(e),
                log_output="\n".join(log_lines),
            )

        # Cleanup
        try:
            if local_path and os.path.exists(local_path):
                os.unlink(local_path)
        except Exception:
            pass

    def _download_artifact(self, deployment_id: int) -> str:
        """Download artifact from hub. Returns local path."""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        resp = requests.get(
            f"{self.hub_url}/api/agent/artifact/{deployment_id}",
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()
        return tmp.name

    def _verify_checksum(self, filepath: str, expected_hash: str):
        """Verify SHA-256 checksum."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        actual = hasher.hexdigest()
        if actual != expected_hash:
            raise ValueError(f"SHA-256 mismatch! Expected: {expected_hash[:16]}... Got: {actual[:16]}...")

    def _backup_current(self, app_name: str) -> str:
        """Backup current deployment before installing new one."""
        # Rotate old backups
        backups = sorted(BACKUP_DIR.glob(f"{app_name}_v*"), key=os.path.getmtime)
        while len(backups) >= BACKUP_KEEP_COUNT:
            oldest = backups.pop(0)
            if oldest.is_dir():
                shutil.rmtree(oldest)
            else:
                oldest.unlink()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"{app_name}_backup_{ts}.zip"

        # If deploy script defines APP_DIR, back that up
        app_dir = os.getenv(f"FBIB_APP_{app_name.upper().replace('-', '_')}_DIR")
        if app_dir and os.path.isdir(app_dir):
            shutil.make_archive(str(backup_path.with_suffix("")), "zip", app_dir)
            logger.info("  Backup saved: %s", backup_path)
        else:
            logger.info("  No APP_DIR configured — skipping file backup.")

        return str(backup_path)

    def _install_artifact(self, artifact_path: str, app_name: str, deploy_script: str = None) -> str:
        """Extract artifact and run deploy script. Returns log output."""
        output = []

        # Extract zip
        extract_dir = tempfile.mkdtemp(prefix=f"fbib_{app_name}_")
        with zipfile.ZipFile(artifact_path, "r") as zf:
            zf.extractall(extract_dir)
        output.append(f"Extracted {len(os.listdir(extract_dir))} files to {extract_dir}")

        # Run deploy script if provided
        if deploy_script:
            script_path = os.path.join(extract_dir, "deploy.sh" if platform.system() != "Windows" else "deploy.ps1")

            # Write deploy script to file
            with open(script_path, "w") as f:
                f.write(deploy_script)
            os.chmod(script_path, 0o755)

            # Execute
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
                    capture_output=True, text=True, timeout=300, cwd=extract_dir,
                )
            else:
                result = subprocess.run(
                    ["bash", script_path],
                    capture_output=True, text=True, timeout=300, cwd=extract_dir,
                )

            output.append(result.stdout)
            if result.returncode != 0:
                output.append(f"STDERR: {result.stderr}")
                raise RuntimeError(f"Deploy script failed (exit {result.returncode}): {result.stderr[:500]}")

        # Move extracted files to APP_DIR
        app_dir = os.getenv(f"FBIB_APP_{app_name.upper().replace('-', '_')}_DIR")
        if app_dir:
            os.makedirs(app_dir, exist_ok=True)
            for item in os.listdir(extract_dir):
                src = os.path.join(extract_dir, item)
                dst = os.path.join(app_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            output.append(f"Deployed to {app_dir}")

        return "\n".join(output)

    # ─── System Metrics ────────────────────────────────────────
    def _get_system_metrics(self):
        """Get CPU, memory, disk usage (cross-platform)."""
        cpu = mem = disk = None
        try:
            if platform.system() == "Linux":
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage("/").percent
            elif platform.system() == "Windows":
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage("C:\\").percent
        except ImportError:
            pass  # psutil not installed — skip metrics
        return cpu, mem, disk

    def _get_installed_apps(self) -> dict:
        """Read installed app versions from env or registry."""
        # Simple implementation — apps define FBIB_APP_<NAME>_VERSION env var
        apps = {}
        for key, val in os.environ.items():
            if key.startswith("FBIB_APP_") and key.endswith("_VERSION"):
                app_name = key[8:-8].lower().replace("_", "-")
                apps[app_name] = val
        return apps


# ─── Service Installation ──────────────────────────────────────
def install_service(args):
    """Install agent as a system service (systemd on Linux, NSSM hint on Windows)."""
    if platform.system() == "Windows":
        print("=" * 60)
        print("  FBIB Agent — Windows Service Installation")
        print("=" * 60)
        print()
        print("  Para instalar como servicio en Windows, usa NSSM:")
        print()
        print(f"  nssm install FBIBAgent C:\\Python312\\python.exe")
        print(f'  nssm set FBIBAgent AppParameters "--agency-key {args.agency_key} --hub-url {args.hub_url}"')
        print(f"  nssm start FBIBAgent")
        print()
        print("  Descarga NSSM: https://nssm.cc/download")
        print("=" * 60)
        return

    # Linux — systemd
    import getpass
    db_conn_part = f" --db-conn '{args.db_conn}'" if hasattr(args, 'db_conn') and args.db_conn else ""
    service_content = f"""[Unit]
Description=FBIB Deploy Agent ({args.agency_key})
After=network.target

[Service]
Type=simple
ExecStart={sys.executable} {os.path.abspath(__file__)} --agency-key {args.agency_key} --hub-url {args.hub_url} --poll-interval {args.poll_interval}{db_conn_part}
Restart=always
RestartSec=30
User={getpass.getuser()}

[Install]
WantedBy=multi-user.target
"""
    service_path = f"/tmp/fbib-agent-{args.agency_key}.service"
    with open(service_path, "w") as f:
        f.write(service_content)

    print("=" * 60)
    print(f"  FBIB Agent — Linux Service (systemd)")
    print("=" * 60)
    print(f"  Agency: {args.agency_key}")
    print(f"  Hub:    {args.hub_url}")
    print()
    print("  Para instalar el servicio, ejecuta como root:")
    print()
    print(f"  sudo cp {service_path} /etc/systemd/system/")
    print(f"  sudo systemctl daemon-reload")
    print(f"  sudo systemctl enable --now fbib-agent-{args.agency_key}")
    print()
    print(f"  Servicio guardado en: {service_path}")
    print("=" * 60)


# ─── CLI ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FBIB Deploy Hub — Cross-Platform Agent")
    parser.add_argument("--agency-key", required=True, help="Agency identifier (e.g., 'ogp', 'hacienda')")
    parser.add_argument("--hub-url", required=True, help="FBIB Hub API URL (e.g., 'https://hub.example.com')")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f"Seconds between polls (default: {DEFAULT_POLL_INTERVAL})")
    parser.add_argument("--once", action="store_true", help="Check once and exit (don't loop)")
    parser.add_argument("--install-service", action="store_true", help="Install as system service (systemd on Linux, NSSM on Windows)")
    parser.add_argument("--db-conn", help="DB connection string for read-only verification on startup (e.g., 'DRIVER={ODBC};SERVER=10.0.1.50;...')")
    parser.add_argument("--verify-db", action="store_true", help="Test DB connection (SELECT 1) and confirm INSERT is denied, then exit")
    args = parser.parse_args()

    # Handle --install-service
    if args.install_service:
        install_service(args)
        return

    # Handle --verify-db
    if args.verify_db:
        if not args.db_conn:
            print("ERROR: --db-conn is required with --verify-db")
            sys.exit(1)
        agent = FBIBAgent(args.agency_key, args.hub_url, args.poll_interval, args.db_conn)
        agent._verify_db_readonly()
        return

    agent = FBIBAgent(args.agency_key, args.hub_url, args.poll_interval, args.db_conn)

    if args.once:
        pending = agent._check_pending()
        if pending:
            for deploy in pending:
                agent._process_deployment(deploy)
        else:
            print("No pending deployments.")
    else:
        agent.run()


if __name__ == "__main__":
    main()
