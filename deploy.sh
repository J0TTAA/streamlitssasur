#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Despliegue de DocRef Dashboard en VM
# =============================================================================
# Uso:
#   Primera vez:  bash deploy.sh
#   Actualizar:   bash deploy.sh update
# =============================================================================
set -euo pipefail

COMPOSE="docker compose"
ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

# ── Colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✗${NC} $*"; exit 1; }
info() { echo -e "${BLUE}→${NC} $*"; }

echo ""
echo "=================================================="
echo "  DocRef Dashboard — Script de Despliegue"
echo "=================================================="
echo ""

# ── 1. Verificar dependencias ─────────────────────────────────────────────────
info "Verificando dependencias..."
command -v docker  >/dev/null 2>&1 || err "Docker no está instalado."
command -v git     >/dev/null 2>&1 || err "Git no está instalado."
docker compose version >/dev/null 2>&1 || err "Docker Compose plugin no encontrado."
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"

# ── 2. Verificar o crear .env ─────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        warn ".env creado desde .env.example"
        warn "IMPORTANTE: Edita .env con tu contraseña de base de datos antes de continuar."
        echo ""
        echo "  nano .env   (o el editor de tu preferencia)"
        echo ""
        read -rp "¿Ya editaste .env y quieres continuar? [s/N]: " confirm
        [[ "$confirm" =~ ^[sS]$ ]] || { warn "Despliegue cancelado."; exit 0; }
    else
        err ".env.example no encontrado. Asegúrate de estar en el directorio del proyecto."
    fi
else
    ok ".env encontrado"
fi

# ── 3. Actualizar código desde git (si se indica) ────────────────────────────
MODE="${1:-}"
if [ "$MODE" = "update" ]; then
    info "Actualizando código desde git..."
    git pull --ff-only || warn "No se pudo hacer git pull (puede haber cambios locales)"
    ok "Código actualizado"
fi

# ── 4. Verificar que existan los archivos de datos ───────────────────────────
if [ ! -d "data" ] || [ -z "$(ls -A data/*.json 2>/dev/null)" ]; then
    warn "No se encontraron archivos JSON en ./data/"
    warn "La API arrancará sin datos. Copia tus .json en la carpeta data/ y reinicia."
fi

# ── 5. Construir imágenes y levantar servicios ────────────────────────────────
info "Construyendo imágenes Docker..."
$COMPOSE build --parallel

info "Levantando servicios..."
$COMPOSE up -d

# ── 6. Esperar a que la API esté sana ────────────────────────────────────────
info "Esperando que la API esté lista..."
TRIES=0; MAX=30
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
    TRIES=$((TRIES+1))
    [ $TRIES -ge $MAX ] && err "La API no respondió después de ${MAX} intentos."
    echo -n "."
    sleep 3
done
echo ""
ok "API lista"

# ── 7. Verificar nginx ────────────────────────────────────────────────────────
info "Verificando nginx..."
sleep 2
if curl -sf http://localhost/ >/dev/null 2>&1; then
    ok "Nginx respondiendo en :80"
else
    warn "Nginx no responde aún. Revisa: docker compose logs nginx"
fi

# ── 8. Resumen ────────────────────────────────────────────────────────────────
echo ""
echo "=================================================="
echo -e "  ${GREEN}Despliegue completado${NC}"
echo "=================================================="
echo ""
echo "  Panel de auditoría:  http://$(hostname -I | awk '{print $1}'):80"
echo "  API (docs):          http://$(hostname -I | awk '{print $1}'):80/docs"
echo ""
echo "  Comandos útiles:"
echo "    docker compose logs -f          # ver logs en vivo"
echo "    docker compose logs -f api      # solo API"
echo "    docker compose logs -f nginx    # solo nginx"
echo "    docker compose ps               # estado de contenedores"
echo "    docker compose down             # apagar"
echo "    docker compose down -v          # apagar + borrar DB"
echo "    bash deploy.sh update           # actualizar desde git"
echo ""
