"""DDNS: Auto-update Cloudflare DNS A record for quiz.312233.xyz.

Run this periodically (e.g., every 5 minutes via Windows Task Scheduler)
to keep the domain pointing to this PC's public IP.

One-time setup:
1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Create token: Zone:DNS:Edit, Zone:312233.xyz
3. Copy token, run: python ddns_update.py --token YOUR_TOKEN
   (This saves the token to .env for future runs)
"""

import os
import sys
import json
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"

# ── Config ──
ZONE_NAME = "312233.xyz"
RECORD_NAME = "quiz.312233.xyz"
API_BASE = "https://api.cloudflare.com/client/v4"


def get_public_ip():
    resp = requests.get("https://api.ipify.org", timeout=10)
    return resp.text.strip()


def get_token():
    # Try env var first
    token = os.environ.get("CF_API_TOKEN", "")
    if token:
        return token
    # Try .env file
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("CF_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def save_token(token):
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith("CF_API_TOKEN="):
            lines[i] = f"CF_API_TOKEN={token}"
            found = True
    if not found:
        lines.append("\nCF_API_TOKEN=" + token)
    ENV_FILE.write_text("\n".join(lines))
    print(f"Token saved to {ENV_FILE}")


def get_zone_id(token, zone_name):
    resp = requests.get(
        f"{API_BASE}/zones",
        params={"name": zone_name},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    zones = resp.json()["result"]
    if not zones:
        raise SystemExit(f"Zone {zone_name} not found")
    return zones[0]["id"]


def get_record(token, zone_id, record_name):
    resp = requests.get(
        f"{API_BASE}/zones/{zone_id}/dns_records",
        params={"name": record_name, "type": "A"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json()["result"]
    return records[0] if records else None


def update_record(token, zone_id, record_id, record_name, ip):
    resp = requests.patch(
        f"{API_BASE}/zones/{zone_id}/dns_records/{record_id}",
        json={"type": "A", "name": record_name, "content": ip, "ttl": 120, "proxied": False},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    # Handle --token
    if len(sys.argv) > 2 and sys.argv[1] == "--token":
        save_token(sys.argv[2])
        print("Token saved. Now run without arguments.")
        return

    token = get_token()
    if not token:
        print("ERROR: No Cloudflare API token found.")
        print("  Get one at: https://dash.cloudflare.com/profile/api-tokens")
        print("  Then run: python ddns_update.py --token YOUR_TOKEN")
        sys.exit(1)

    public_ip = get_public_ip()
    print(f"Public IP: {public_ip}")

    zone_id = get_zone_id(token, ZONE_NAME)
    print(f"Zone ID: {zone_id}")

    record = get_record(token, zone_id, RECORD_NAME)
    if not record:
        print(f"ERROR: A record {RECORD_NAME} not found. Create it in Cloudflare dashboard first.")
        sys.exit(1)

    current_ip = record["content"]
    print(f"DNS A record: {current_ip}")

    if current_ip == public_ip:
        print("IP unchanged, nothing to do.")
    else:
        update_record(token, zone_id, record["id"], RECORD_NAME, public_ip)
        print(f"Updated: {current_ip} → {public_ip}")


if __name__ == "__main__":
    main()
