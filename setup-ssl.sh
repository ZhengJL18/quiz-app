#!/usr/bin/env bash
# ==============================================================================
# setup-ssl.sh — 一课一练 Quiz App — Let's Encrypt SSL setup
# ==============================================================================
# Prerequisites:
#   - Domain DNS A record pointing to this server's public IP
#   - Ports 80 & 443 open in firewall / security group
#   - DOMAIN set in .env file
#
# Usage:
#   chmod +x setup-ssl.sh
#   ./setup-ssl.sh
# ==============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DOMAIN=$(grep -E '^DOMAIN=' .env 2>/dev/null | cut -d= -f2 || echo "")
ADMIN_EMAIL="admin@${DOMAIN}"

if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "quiz.yourdomain.com" ]; then
    echo -e "${RED}Error: DOMAIN is not set in .env or still using placeholder.${NC}"
    echo "Edit .env and set DOMAIN=your-actual-domain.com"
    exit 1
fi

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  SSL Setup for ${DOMAIN}${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# ── 1. Install certbot ──────────────────
echo -e "${GREEN}[1/5] Installing certbot...${NC}"
if ! command -v certbot &>/dev/null; then
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq certbot
    elif command -v yum &>/dev/null; then
        sudo yum install -y certbot
    else
        echo -e "${RED}Cannot auto-install certbot. Please install manually.${NC}"
        exit 1
    fi
fi

# ── 2. Ensure nginx is running (port 80) ─
echo -e "${GREEN}[2/5] Verifying nginx is running on port 80...${NC}"
docker compose up -d nginx
sleep 2

# ── 3. Get certificate ──────────────────
echo -e "${GREEN}[3/5] Requesting Let's Encrypt certificate for ${DOMAIN}...${NC}"
sudo certbot certonly --webroot \
    -w "$SCRIPT_DIR/certbot-www" \
    -d "$DOMAIN" \
    --email "$ADMIN_EMAIL" \
    --agree-tos \
    --non-interactive

# ── 4. Replace nginx config with SSL version ─
echo -e "${GREEN}[4/5] Enabling HTTPS in nginx config...${NC}"
sed "s/\${DOMAIN}/${DOMAIN}/g" nginx-ssl.conf.template > nginx.conf
docker compose exec nginx nginx -s reload 2>/dev/null || docker compose restart nginx

# ── 5. Auto-renewal cron ────────────────
echo -e "${GREEN}[5/5] Setting up auto-renewal...${NC}"
RENEW_CMD="0 3 * * * sudo certbot renew --quiet --deploy-hook 'docker compose -f ${SCRIPT_DIR}/docker-compose.yml exec -T nginx nginx -s reload'"
if ! (crontab -l 2>/dev/null | grep -q "certbot renew"); then
    (crontab -l 2>/dev/null; echo "$RENEW_CMD") | crontab -
    echo "  Cron job added for daily renewal check at 3 AM."
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  ✅ SSL enabled!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Visit: https://${DOMAIN}"
echo ""
