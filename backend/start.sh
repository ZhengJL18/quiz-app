#!/bin/bash
# Railway deployment startup script

echo "Starting Quiz App Backend..."

# Ensure data directory exists
mkdir -p /data

# Seed database on first run (if db file doesn't exist)
if [ ! -f /data/quiz.db ]; then
    echo "First run: seeding database..."
    python scripts/seed_data.py
fi

# Start server
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}
