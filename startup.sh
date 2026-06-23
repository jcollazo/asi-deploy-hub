#!/bin/bash
# ============================================================
# startup.sh — Azure Web App entrypoint for ASI Deploy Hub
# ============================================================
# Azure asigna PORT dinámico. uvicorn lo lee del environment.
# La app sirve:
#   /          → React Admin Portal (frontend/dist/)
#   /api/*     → ASI Deploy Hub REST API
#   /docs      → Swagger (FastAPI auto)
#   /health    → Health check
# ============================================================
set -e

echo "🚀 ASI Deploy Hub starting..."
echo "   PORT: ${PORT:-8000}"
echo "   Python: $(python3 --version)"

# Verify frontend build exists
if [ -d "frontend/dist" ]; then
    echo "✅ Frontend build found: frontend/dist/"
else
    echo "⚠️  WARNING: frontend/dist/ not found — API-only mode"
fi

exec python3 -m uvicorn src.hub:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --log-level info
