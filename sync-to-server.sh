#!/bin/bash
# ============================================================
# 同步本地代码到云服务器并重启
# 用法: bash sync-to-server.sh
# ============================================================

SERVER="ubuntu@43.139.179.58"
REMOTE_DIR="/home/ubuntu/quiz-app"
SSH_PASS="Aa@mingtiannihao"

echo "🔁 同步代码到服务器..."

# 同步 backend（排除 data 目录保护数据库！）
sshpass -p "$SSH_PASS" rsync -avz --delete \
    --exclude 'data/' \
    --exclude '*.db' \
    --exclude '*.db-shm' \
    --exclude '*.db-wal' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    backend/ "$SERVER:$REMOTE_DIR/backend/"

# 同步 frontend 源码（如果需要）
# sshpass -p "$SSH_PASS" rsync -avz --delete \
#     --exclude 'node_modules/' \
#     --exclude 'dist/' \
#     frontend/ "$SERVER:$REMOTE_DIR/frontend/"

echo ""
echo "🔄 重启后端服务..."

sshpass -p "$SSH_PASS" ssh "$SERVER" << 'ENDSSH'
    # 杀掉旧进程
    pkill -f "uvicorn app.main" 2>/dev/null
    sleep 2

    # 重新构建前端（如果需要）
    # cd ~/quiz-app/frontend && npm run build

    # 启动后端
    cd ~/quiz-app/backend
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/quiz.log 2>&1 &
    sleep 3

    # 验证
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/v1/health)
    echo "健康检查: HTTP $HTTP_CODE"

    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ 部署成功！https://quiz.312233.xyz"
    else
        echo "❌ 启动失败，查看日志: tail -50 /tmp/quiz.log"
        exit 1
    fi
ENDSSH
