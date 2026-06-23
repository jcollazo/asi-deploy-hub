#!/bin/bash
# ============================================================
# start_portal.sh — Inicia el Portal FBIB en producción (:80)
# ============================================================
# Requisitos: Python 3, frontend/dist/ build
# Uso: ./start_portal.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 FBIB Deploy Hub — Iniciando Portal"

# 1. Verificar build del frontend
if [ ! -f "frontend/dist/index.html" ]; then
    echo "📦 Build del frontend no encontrado. Ejecutando npm run build..."
    cd frontend
    npm install --silent
    npm run build
    cd ..
fi

# 2. Iniciar el servidor del portal
echo "🌐 Portal → http://0.0.0.0:80"
echo "   Static: $SCRIPT_DIR/frontend/dist"
echo "   API proxy → http://127.0.0.1:8900 (si está corriendo)"
echo ""
exec python3 portal_server.py
