#!/usr/bin/env bash
# ==============================================================================
# deploy.sh — 一课一练 Quiz App — One-click deployment script
# ==============================================================================
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# This script:
#   1. Checks Docker & Docker Compose are installed
#   2. Copies .env.production.example → .env if missing (then aborts for editing)
#   3. Builds the Docker image (backend + frontend in multi-stage)
#   4. Starts all services (backend + nginx)
#   5. Seeds the database with default subjects/chapters/questions
#   6. Shows status and access URLs
# ==============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  一课一练 · Quiz App — Deploy${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# ── 1. Prerequisites ──────────────────────
if ! command -v docker &>/dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Install: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo -e "${RED}Error: Docker Compose plugin is not available.${NC}"
    echo "Install: sudo apt-get install docker-compose-plugin"
    exit 1
fi

# ── 2. .env file ──────────────────────────
if [ ! -f .env ]; then
    echo -e "${YELLOW}No .env file found. Creating from template...${NC}"
    cp .env.production.example .env
    echo ""
    echo -e "${RED}⚠ ACTION REQUIRED: Edit .env with your real secrets!${NC}"
    echo "  nano .env"
    echo ""
    echo "Then run this script again."
    exit 0
fi

# Source DOMAIN for display
DOMAIN=$(grep -E '^DOMAIN=' .env 2>/dev/null | cut -d= -f2 || echo "localhost")

# ── 3. Build ─────────────────────────────
echo -e "${GREEN}[1/4] Building Docker image...${NC}"
docker compose build --pull

# ── 4. Start services ────────────────────
echo -e "${GREEN}[2/4] Starting services...${NC}"
docker compose up -d

# Wait for backend to be healthy
echo -e "${GREEN}[3/4] Waiting for backend to be ready...${NC}"
for i in $(seq 1 30); do
    if curl -sf http://localhost/api/health >/dev/null 2>&1; then
        echo -e "${GREEN}  Backend is healthy!${NC}"
        break
    fi
    sleep 2
done

# ── 5. Seed database ─────────────────────
echo -e "${GREEN}[4/4] Seeding database...${NC}"
docker compose exec -T backend python scripts/seed_data.py 2>/dev/null || echo "  Database already seeded (or seed script skipped)."

# ── 6. Done ──────────────────────────────
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  ✅ Deployment complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Local access:  http://localhost"
echo "  API health:    http://localhost/api/health"
echo "  Default login: admin / admin123"
echo ""
if [ "$DOMAIN" != "localhost" ] && [ "$DOMAIN" != "quiz.yourdomain.com" ]; then
    echo "  Public:        https://${DOMAIN}  (after SSL setup)"
    echo "  Setup SSL:     ./setup-ssl.sh"
fi
echo ""
echo "  View logs:     docker compose logs -f"
echo "  Stop:          docker compose down"
echo ""
