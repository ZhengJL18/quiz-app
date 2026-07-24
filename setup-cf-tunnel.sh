#!/usr/bin/env bash
# ==============================================================================
# setup-cf-tunnel.sh — 一课一练 Quiz App — Cloudflare Tunnel setup
# ==============================================================================
# Alternative to nginx+Let's Encrypt. Uses Cloudflare Tunnel to expose the
# local Docker service to the internet with HTTPS (no open ports needed).
#
# Prerequisites:
#   - A Cloudflare account with your domain managed there
#   - cloudflared installed: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
#
# Usage:
#   chmod +x setup-cf-tunnel.sh
#   ./setup-cf-tunnel.sh
# ==============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DOMAIN=$(grep -E '^DOMAIN=' .env 2>/dev/null | cut -d= -f2 || echo "")

if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "quiz.yourdomain.com" ]; then
    echo -e "${RED}Error: DOMAIN is not set in .env or still using placeholder.${NC}"
    exit 1
fi

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Cloudflare Tunnel Setup for ${DOMAIN}${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# ── 1. Install cloudflared ──────────────
echo -e "${GREEN}[1/4] Installing cloudflared...${NC}"
if ! command -v cloudflared &>/dev/null; then
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /tmp/cloudflared
    sudo install /tmp/cloudflared /usr/local/bin/cloudflared
    rm /tmp/cloudflared
    echo "  cloudflared installed."
else
    echo "  cloudflared already installed: $(cloudflared version 2>&1 | head -1)"
fi

# ── 2. Login (one-time) ─────────────────
echo -e "${GREEN}[2/4] Authenticating with Cloudflare...${NC}"
echo -e "${YELLOW}  A browser window will open. Login to your Cloudflare account.${NC}"
cloudflared tunnel login

# ── 3. Create tunnel ────────────────────
echo -e "${GREEN}[3/4] Creating tunnel for ${DOMAIN}...${NC}"
TUNNEL_NAME="quiz-app-$(date +%s)"
TUNNEL_ID=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1 | grep -oP 'id \K[^\s]+' || echo "")

if [ -z "$TUNNEL_ID" ]; then
    echo -e "${YELLOW}  Tunnel may already exist. Trying to list...${NC}"
    cloudflared tunnel list
    echo ""
    echo "If a tunnel already exists, manually configure it with:"
    echo "  cloudflared tunnel route dns <TUNNEL_ID> ${DOMAIN}"
    exit 1
fi

# ── 4. Configure and route ──────────────
echo -e "${GREEN}[4/4] Configuring tunnel...${NC}"

# Write tunnel config
cat > "$SCRIPT_DIR/tunnel-config.yml" << EOF
tunnel: ${TUNNEL_ID}
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: ${DOMAIN}
    service: http://backend:8001
  - service: http_status:404
EOF

# Route DNS
cloudflared tunnel route dns "$TUNNEL_ID" "$DOMAIN"

# ── Start tunnel via Docker Compose override ─
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  ✅ Tunnel created!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Tunnel ID:  ${TUNNEL_ID}"
echo "  Domain:     https://${DOMAIN}"
echo ""
echo "  To start the tunnel alongside your app, add this service"
echo "  to docker-compose.yml or use a separate compose override:"
echo ""
echo "  --- docker-compose.cf-tunnel.yml ---"
echo "  services:"
echo "    cloudflared:"
echo "      image: cloudflare/cloudflared:latest"
echo "      command: tunnel run"
echo "      volumes:"
echo "        - ./tunnel-config.yml:/etc/cloudflared/config.yml:ro"
echo "        - ~/.cloudflared/${TUNNEL_ID}.json:/etc/cloudflared/${TUNNEL_ID}.json:ro"
echo "      restart: unless-stopped"
echo "      networks:"
echo "        - quiz-net"
echo "  ----------------------------------------"
echo ""
echo "  (A docker-compose.cf-tunnel.yml has been created for you.)"
echo ""

cat > "$SCRIPT_DIR/docker-compose.cf-tunnel.yml" << EOF
# Cloudflare Tunnel add-on for quiz-app
# Usage: docker compose -f docker-compose.yml -f docker-compose.cf-tunnel.yml up -d
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: quiz-tunnel
    command: tunnel run
    volumes:
      - ./tunnel-config.yml:/etc/cloudflared/config.yml:ro
      - ~/.cloudflared/${TUNNEL_ID}.json:/etc/cloudflared/${TUNNEL_ID}.json:ro
    restart: unless-stopped
    networks:
      - quiz-net
EOF

echo "  Created: docker-compose.cf-tunnel.yml"
