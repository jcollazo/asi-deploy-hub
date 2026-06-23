#!/usr/bin/env python3
# ============================================================
# data_replica.py — FBIB Agent: SQLite Read-Only Data Replica
# ============================================================
# Downloads a SQLite database from the Hub, verifies SHA-256,
# replaces the existing replica atomically, and sets it
# read-only (chmod 444). The agency app reads via SELECT only.
#
# The Agent NEVER writes to this database. It only replaces
# the file with a fresh copy from the Hub.
# ============================================================
import hashlib
import logging
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("fbib-data-replica")

# ─── Config ───────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("FBIB_AGENT_DATA_DIR", "/opt/fbib-agent/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


class DataReplica:
    """Downloads and manages read-only SQLite data replicas from the Hub.

    The agency's app opens this file in read-only mode:
        conn = sqlite3.connect("file:/opt/fbib-agent/data/empleados.db?mode=ro", uri=True)
    """

    def __init__(self, agency_key: str, hub_url: str):
        self.agency_key = agency_key
        self.hub_url = hub_url.rstrip("/")

    def process_data_release(self, deploy: dict) -> dict:
        """Process a DATA type deployment from the Hub.

        deploy dict contains:
            - deployment_id: int
            - release_tag: str (e.g. 'data_20260622_v1')
            - artifact_path: str (relative path on hub)
            - artifact_hash: str (SHA-256)
            - pipeline_key: str (e.g. 'ukg_employee_import')
        """
        deployment_id = deploy["deployment_id"]
        release_tag = deploy["release_tag"]
        pipeline_key = deploy.get("pipeline_key", "data")
        artifact_hash = deploy.get("artifact_hash")

        logger.info("=" * 60)
        logger.info("Processing DATA REPLICA #%d: %s", deployment_id, release_tag)
        logger.info("=" * 60)

        log_lines = []
        try:
            # Step 1: Download SQLite from Hub
            logger.info("  [1/4] Downloading data replica (%s)...", pipeline_key)
            local_path = self._download(deployment_id)
            file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
            log_lines.append(f"[OK] Downloaded: {file_size_mb:.1f} MB")

            # Step 2: Verify SHA-256
            logger.info("  [2/4] Verifying SHA-256...")
            self._verify_checksum(local_path, artifact_hash)
            log_lines.append(f"[OK] SHA-256: {artifact_hash[:16]}...")

            # Step 3: Replace atomically + chmod 444
            logger.info("  [3/4] Installing replica (read-only)...")
            target = self._install_replica(local_path, pipeline_key)
            log_lines.append(f"[OK] Installed: {target} (chmod 444)")

            # Step 4: Verify readable
            logger.info("  [4/4] Verifying replica is readable...")
            row_count = self._verify_readable(target)
            log_lines.append(f"[OK] Readable: {row_count} rows")

            logger.info("Data replica #%d COMPLETE ✓", deployment_id)
            return {
                "status": "SUCCESS",
                "pipeline": pipeline_key,
                "file": str(target),
                "rows": row_count,
                "log": "\n".join(log_lines),
            }

        except Exception as e:
            logger.error("Data replica #%d FAILED: %s", deployment_id, e)
            log_lines.append(f"[FAIL] {e}")
            return {
                "status": "FAILED",
                "error": str(e),
                "log": "\n".join(log_lines),
            }

    def _download(self, deployment_id: int) -> str:
        """Download SQLite artifact from Hub."""
        import requests

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        resp = requests.get(
            f"{self.hub_url}/api/agent/artifact/{deployment_id}",
            stream=True,
            timeout=600,  # SQLite files can be large
        )
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=65536):
            tmp.write(chunk)
        tmp.close()
        return tmp.name

    def _verify_checksum(self, filepath: str, expected_hash: str):
        """Verify SHA-256 checksum of downloaded file."""
        if not expected_hash:
            logger.warning("  No artifact_hash provided — skipping verification")
            return

        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual = hasher.hexdigest()
        if actual != expected_hash:
            raise ValueError(
                f"SHA-256 mismatch!\n"
                f"  Expected: {expected_hash[:32]}...\n"
                f"  Got:      {actual[:32]}..."
            )

    def _install_replica(self, src_path: str, pipeline_key: str) -> Path:
        """Atomically replace the SQLite replica file and set read-only.

        1. Write to a temp name
        2. Enable WAL mode (readers can keep reading old file)
        3. chmod 444 (read-only for everyone)
        4. Atomic rename
        """
        target = DATA_DIR / f"{pipeline_key}.db"
        tmp_target = DATA_DIR / f".{pipeline_key}.db.tmp"

        # Enable WAL mode before placing
        conn = sqlite3.connect(src_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.close()

        # Copy to temp location, then set perms, then rename
        shutil.copy2(src_path, tmp_target)
        tmp_target.chmod(0o444)  # r--r--r--
        os.rename(tmp_target, target)

        # Cleanup
        try:
            os.unlink(src_path)
        except OSError:
            pass

        return target

    def _verify_readable(self, db_path: Path) -> int:
        """Open the SQLite in read-only mode and verify it has data."""
        # Use URI mode with ?mode=ro for explicit read-only
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)

        # Get table list and row count
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        total_rows = 0
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                count = cursor.fetchone()[0]
                total_rows += count
                logger.info("    %s: %d rows", table, count)
            except sqlite3.Error:
                pass

        conn.close()
        return total_rows


# ─── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="FBIB Data Replica — Test")
    parser.add_argument("--agency-key", required=True)
    parser.add_argument("--hub-url", required=True)
    parser.add_argument("--deployment-id", type=int, required=True)
    parser.add_argument("--pipeline-key", default="empleados")
    parser.add_argument("--release-tag", default="test")
    parser.add_argument("--artifact-hash")
    args = parser.parse_args()

    replica = DataReplica(args.agency_key, args.hub_url)
    result = replica.process_data_release({
        "deployment_id": args.deployment_id,
        "release_tag": args.release_tag,
        "pipeline_key": args.pipeline_key,
        "artifact_hash": args.artifact_hash,
    })

    print()
    print("=" * 60)
    print("  DATA REPLICA RESULT")
    print("=" * 60)
    print(f"  Status: {result['status']}")
    if result["status"] == "SUCCESS":
        print(f"  File:   {result['file']}")
        print(f"  Rows:   {result['rows']}")
    else:
        print(f"  Error:  {result.get('error', 'unknown')}")
    print("=" * 60)
