#!/bin/bash
# =============================================================================
#  mc-chunk-map — setup.sh
#  Genera el proyecto completo del servicio de mapa de chunks Minecraft
#  Uso: bash setup.sh [ruta_al_mundo]
#  Ejemplo: bash setup.sh /opt/minecraft/world
# =============================================================================

set -e

WORLD_PATH="${1:-/opt/minecraft/world}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${CYAN}[setup]${NC} $1"; }
ok()   { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
err()  { echo -e "${RED}[error]${NC} $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   mc-chunk-map  ·  v3.1.0                ║"
echo "╚══════════════════════════════════════════╝"
echo ""
log "Ruta del mundo: $WORLD_PATH"
echo ""

# ──────────────────────────────────────────────
# 1. Comprobar dependencias del sistema
# ──────────────────────────────────────────────
log "Comprobando dependencias..."

command -v python3 >/dev/null 2>&1 || err "Python3 no encontrado. Instálalo con: apt install python3"
command -v pip3   >/dev/null 2>&1 || err "pip3 no encontrado. Instálalo con: apt install python3-pip"

PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python $PYTHON_VER encontrado"

# Comprobar directorio del mundo
if [ ! -d "$WORLD_PATH/region" ]; then
    warn "No se encontró $WORLD_PATH/region"
    warn "Asegúrate de montar el mundo antes de iniciar el servicio."
    warn "El servicio arrancará igualmente."
fi

# ──────────────────────────────────────────────
# 2. Entorno virtual Python
# ──────────────────────────────────────────────
log "Creando entorno virtual..."
cd "$PROJECT_DIR/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Virtualenv creado"
else
    ok "Virtualenv ya existe"
fi

source venv/bin/activate

log "Instalando dependencias Python..."
pip install --quiet --upgrade pip
pip install --quiet     fastapi     "uvicorn[standard]"

ok "Dependencias instaladas"
deactivate

# ──────────────────────────────────────────────
# 3. Crear archivo .env
# ──────────────────────────────────────────────
log "Generando .env..."
cat > "$PROJECT_DIR/backend/.env" << ENVEOF
WORLD_PATH=$WORLD_PATH
HOST=0.0.0.0
PORT=8200
CACHE_TTL=120
LOG_LEVEL=info
ENVEOF
ok ".env generado"

# ──────────────────────────────────────────────
# 4. Systemd service
# ──────────────────────────────────────────────
log "Generando mc-chunk-map.service..."
cat > "$PROJECT_DIR/mc-chunk-map.service" << SVCEOF
[Unit]
Description=Minecraft Chunk Map Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR/backend
EnvironmentFile=$PROJECT_DIR/backend/.env
ExecStart=$PROJECT_DIR/backend/venv/bin/uvicorn main:app --host \${HOST} --port \${PORT} --log-level \${LOG_LEVEL}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF
ok "Service file generado: mc-chunk-map.service"

# ──────────────────────────────────────────────
# 5. Resumen final
# ──────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Setup completado               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo -e "  ${CYAN}Iniciar en desarrollo:${NC}"
echo "    cd backend && source venv/bin/activate"
echo "    uvicorn main:app --reload --port 8200"
echo ""
echo -e "  ${CYAN}Instalar como servicio systemd:${NC}"
echo "    sudo cp mc-chunk-map.service /etc/systemd/system/"
echo "    sudo systemctl daemon-reload"
echo "    sudo systemctl enable --now mc-chunk-map"
echo ""
echo -e "  ${CYAN}Acceder al mapa:${NC}"
echo "    http://localhost:8200"
echo ""
echo -e "  ${CYAN}API de chunks:${NC}"
echo "    http://localhost:8200/api/chunks"
echo "    http://localhost:8200/api/stats"
echo ""
echo -e "  ${CYAN}Caché persistente:${NC}"
echo "    backend/chunk_cache.json (generado automáticamente)"
echo "    Solo se reparsean chunks nuevos — el resto se carga del caché."
echo ""
