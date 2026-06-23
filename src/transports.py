#!/usr/bin/env python3
# ============================================================
# transports.py — ASI Agent: Data Source Connectors
# ============================================================
# Each agency has ONE data source: UKG, SAP, or Oracle.
# The Agent uses this module to pull employee data directly
# from the configured source using the agency's own API key.
# ============================================================
import logging
from datetime import datetime

logger = logging.getLogger("asi-transports")


# ─── Transport Factory ────────────────────────────────────────
def get_transport(config: dict):
    """Return the appropriate transport for the configured source_type."""
    source_type = (config.get("source_type") or "").upper()

    transports = {
        "UKG": UKGTransport,
        "SAP": SAPTransport,
        "ORACLE": OracleTransport,
    }

    cls = transports.get(source_type)
    if not cls:
        raise ValueError(f"Unknown source_type: {source_type}. Use UKG, SAP, or ORACLE.")

    return cls(config)


# ─── UKG Pro Transport ────────────────────────────────────────
class UKGTransport:
    """Pull employee data from UKG Pro REST API."""

    def __init__(self, config: dict):
        self.base_url = config.get("source_url", "https://api.ultipro.com").rstrip("/")
        self.api_key = config.get("api_key")         # X-US-API-Key
        self.client_id = config.get("client_id")     # OAuth 2.0
        self.client_secret = config.get("client_secret")
        self.token = None

    def authenticate(self):
        """OAuth 2.0 Client Credentials grant."""
        import requests
        logger.info("UKG: Authenticating via OAuth 2.0...")
        resp = requests.post(
            f"{self.base_url}/auth/oauth/v2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        logger.info("UKG: Token obtained (expires in %ds)", resp.json().get("expires_in", 0))

    def fetch_employees(self) -> list[dict]:
        """Paginated fetch of all employees for this agency."""
        import requests

        self.authenticate()

        all_employees = []
        page = 1
        per_page = 1000

        while True:
            logger.info("UKG: Fetching page %d...", page)
            resp = requests.get(
                f"{self.base_url}/personnel/v1/employees",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "X-US-API-Key": self.api_key,
                    "Accept": "application/json",
                },
                params={"page": page, "per_page": per_page},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            employees = data.get("employees", [])
            all_employees.extend(employees)

            total = data.get("totalCount", 0)
            logger.info("UKG: Page %d → %d employees (total: %d)", page, len(employees), total)

            if len(all_employees) >= total or len(employees) == 0:
                break
            page += 1

        logger.info("UKG: Fetch complete — %d total employees", len(all_employees))
        return all_employees


# ─── SAP SuccessFactors Transport ──────────────────────────────
class SAPTransport:
    """Pull employee data from SAP SuccessFactors OData API."""

    def __init__(self, config: dict):
        self.base_url = config.get("source_url", "").rstrip("/")
        self.api_key = config.get("api_key")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.token = None

    def authenticate(self):
        """OAuth 2.0 for SAP SuccessFactors."""
        import requests
        logger.info("SAP: Authenticating via OAuth 2.0...")

        # SAP uses different token URL
        token_url = f"{self.base_url}/oauth/token"
        resp = requests.get(
            token_url,
            params={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        logger.info("SAP: Token obtained")

    def fetch_employees(self) -> list[dict]:
        """Fetch employees from SAP SuccessFactors EmpEmployment.

        No $select hardcoded — the API response defines the columns.
        The Agent discovers columns dynamically from whatever the
        agency's API endpoint returns.
        """
        import requests

        self.authenticate()

        all_employees = []
        skip = 0
        top = 1000

        while True:
            logger.info("SAP: Fetching offset=%d...", skip)
            resp = requests.get(
                f"{self.base_url}/odata/v2/EmpEmployment",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "APIKey": self.api_key,
                    "Accept": "application/json",
                },
                params={
                    "$top": top,
                    "$skip": skip,
                    "$format": "json",
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("d", {}).get("results", [])
            all_employees.extend(results)

            logger.info("SAP: offset=%d → %d employees", skip, len(results))

            if len(results) < top:
                break
            skip += top

        logger.info("SAP: Fetch complete — %d total employees", len(all_employees))
        return all_employees


# ─── Oracle HCM Transport ──────────────────────────────────────
class OracleTransport:
    """Pull employee data from Oracle HCM Cloud REST API."""

    def __init__(self, config: dict):
        self.base_url = config.get("source_url", "").rstrip("/")
        self.api_key = config.get("api_key")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.token = None

    def authenticate(self):
        """OAuth 2.0 for Oracle HCM."""
        import requests
        logger.info("Oracle: Authenticating via OAuth 2.0...")

        resp = requests.post(
            f"{self.base_url}/oauth2/v1/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        logger.info("Oracle: Token obtained")

    def fetch_employees(self) -> list[dict]:
        """Fetch workers from Oracle HCM.

        No hardcoded expand — the API response defines the columns.
        The Agent discovers columns dynamically from whatever the
        agency's Oracle HCM endpoint returns.
        """
        import requests

        self.authenticate()

        all_workers = []
        offset = 0
        limit = 1000

        while True:
            logger.info("Oracle: Fetching offset=%d...", offset)
            resp = requests.get(
                f"{self.base_url}/hcmRestApi/resources/latest/workers",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                },
                params={
                    "limit": limit,
                    "offset": offset,
                    "q": "AssignmentStatus='ACTIVE'",
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])
            all_workers.extend(items)

            logger.info("Oracle: offset=%d → %d workers", offset, len(items))

            if len(items) < limit:
                break
            offset += limit

        logger.info("Oracle: Fetch complete — %d total workers", len(all_workers))
        return all_workers
