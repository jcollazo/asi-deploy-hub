# ============================================================
# data_sync.py — FBIB Agent: Data Sync Module
# ============================================================
# Syncs data from Hub → Agency's local DB.
# Paginated pull, AES-256-GCM decrypt, INSERT/UPDATE local.
# ============================================================
import hashlib
import logging
import os
from datetime import datetime

logger = logging.getLogger("fbib-data-sync")


class DataSyncer:
    """Handles data synchronization from central Hub to agency's local DB."""

    def __init__(self, agency_key: str, hub_url: str, db_conn_str: str = None):
        self.agency_key = agency_key
        self.hub_url = hub_url.rstrip("/")
        self.db_conn_str = db_conn_str or os.getenv("AGENCY_DB_CONN")
        self.pipeline_keys = os.getenv("AGENCY_SYNC_PIPELINES", "ukg_employee_import").split(",")

    def run_once(self):
        """Check and sync all configured pipelines. Returns summary."""
        import requests

        results = []
        for pipeline_key in self.pipeline_keys:
            pipeline_key = pipeline_key.strip()
            if not pipeline_key:
                continue

            logger.info("Syncing pipeline: %s", pipeline_key)
            try:
                result = self._sync_pipeline(pipeline_key)
                results.append(result)
            except Exception as e:
                logger.exception("Sync failed for %s: %s", pipeline_key, e)
                results.append({"pipeline": pipeline_key, "status": "FAILED", "error": str(e)})

        return results

    def _sync_pipeline(self, pipeline_key: str) -> dict:
        """Sync a single pipeline — paginated pull + insert/update local."""
        import requests

        offset = 0
        limit = 1000
        total_synced = 0
        batch_id = None
        status = "UP_TO_DATE"

        while True:
            resp = requests.get(
                f"{self.hub_url}/api/agent/data/{self.agency_key}",
                params={"pipeline_key": pipeline_key, "offset": offset, "limit": limit},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            if data["status"] == "UP_TO_DATE":
                status = "UP_TO_DATE"
                break
            elif data["status"] == "NO_DATA":
                status = "NO_DATA"
                break

            batch_id = data["batch_id"]
            rows = data["rows"]
            columns = data.get("columns", [])

            if not rows:
                break

            # Insert into local DB
            synced = self._insert_local(rows, columns, pipeline_key)
            total_synced += synced
            logger.info("  Synced %d rows (offset %d, total %d)", synced, offset, total_synced)

            if not data.get("has_more"):
                break

            offset += limit

        # Report sync complete
        if batch_id:
            try:
                requests.post(
                    f"{self.hub_url}/api/agent/data/{self.agency_key}/synced",
                    params={
                        "pipeline_key": pipeline_key,
                        "batch_id": batch_id,
                        "rows_synced": total_synced,
                        "status": "SYNCED",
                    },
                    timeout=30,
                )
            except Exception as e:
                logger.warning("Failed to report sync: %s", e)

        logger.info("Pipeline %s complete: %d rows synced", pipeline_key, total_synced)
        return {"pipeline": pipeline_key, "status": status, "rows_synced": total_synced, "batch_id": batch_id}

    def _insert_local(self, rows: list[dict], columns: list[str], pipeline_key: str) -> int:
        """Insert rows into agency's local DB. Uses MERGE if possible."""
        if not self.db_conn_str:
            raise RuntimeError("AGENCY_DB_CONN not set. Cannot sync data to local DB.")

        import pyodbc

        conn = pyodbc.connect(self.db_conn_str, autocommit=True)
        cursor = conn.cursor()

        # Determine target table from pipeline
        table = self._target_table(pipeline_key)

        synced = 0
        for row in rows:
            try:
                # Decrypt ENCRYPT_AES256 fields
                processed = {}
                for col, val in row.items():
                    processed[col] = self._maybe_decrypt(col, val)

                # Build INSERT
                cols = ", ".join(processed.keys())
                placeholders = ", ".join(["?"] * len(processed))
                values = list(processed.values())

                # Try UPDATE first (by EEID or primary key), then INSERT
                eeid = processed.get("eeid") or processed.get("employee_id")
                if eeid:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE eeid=?", eeid
                    )
                    exists = cursor.fetchone()[0] > 0
                    if exists:
                        set_clause = ", ".join([f"{c}=?" for c in processed.keys()])
                        cursor.execute(
                            f"UPDATE {table} SET {set_clause} WHERE eeid=?",
                            values + [eeid],
                        )
                        synced += 1
                        continue

                cursor.execute(
                    f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", values
                )
                synced += 1
            except Exception as e:
                logger.error("Failed to insert row (EEID=%s): %s", row.get("eeid", "?"), e)

        conn.close()
        return synced

    def _target_table(self, pipeline_key: str) -> str:
        """Map pipeline to local target table."""
        mapping = {
            "ukg_employee_import": "empleados",
            "sap_payroll_import": "empleados",
            "oracle_fin_import": "transacciones",
        }
        return mapping.get(pipeline_key, f"import_{pipeline_key}")

    def _maybe_decrypt(self, column: str, value) -> str:
        """Decrypt AES-256-GCM field if needed."""
        if value is None:
            return None

        # Heuristic: if it looks like base64 and > 50 chars, try decrypt
        if isinstance(value, str) and len(value) > 50 and value.count("=") >= 1:
            try:
                from crypto_utils import decrypt
                return decrypt(value)
            except Exception:
                pass  # Not encrypted, return as-is
        return value


# ─── CLI test ─────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--agency-key", required=True)
    parser.add_argument("--hub-url", required=True)
    parser.add_argument("--db-conn", help="Local DB connection string")
    args = parser.parse_args()

    syncer = DataSyncer(args.agency_key, args.hub_url, args.db_conn)
    results = syncer.run_once()

    print()
    print("=" * 60)
    print("  DATA SYNC COMPLETE")
    print("=" * 60)
    for r in results:
        print(f"  {r['pipeline']:<30} {r['status']:<15} {r.get('rows_synced', 0)} rows")
    print("=" * 60)
