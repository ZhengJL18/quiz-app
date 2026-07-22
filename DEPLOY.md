# 🚀 一课一练 · Quiz App — 部署指南

> 支持阿里云/腾讯云 ECS 等国内云服务器，一键 Docker Compose 部署。

---

## 1. 服务器要求

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 1 核 | 2 核 |
| 内存 | 1 GB | 2 GB |
| 磁盘 | 10 GB | 20 GB（题库 + 备份） |
| 系统 | Ubuntu 22.04 / CentOS 7+ | Ubuntu 22.04 LTS |
| 软件 | Docker + Docker Compose | — |

---

## 2. 快速开始（5 步）

### Step 1：安装 Docker

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER  # 重新登录生效
```

国内服务器可使用阿里云镜像加速：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": ["https://registry.cn-hangzhou.aliyuncs.com"]
}
EOF
sudo systemctl restart docker
```

### Step 2：克隆项目

```bash
git clone <你的仓库地址> quiz-app
cd quiz-app
```

### Step 3：配置密钥

```bash
cp .env.production.example .env
nano .env   # 填入真实的 DEEPSEEK_API_KEY 和 JWT_SECRET
```

**必须修改的项目：**

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（https://platform.deepseek.com/api_keys） |
| `JWT_SECRET` | 随机字符串（`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`） |
| `DOMAIN` | 你的域名（如 `quiz.example.com`） |

### Step 4：部署

```bash
chmod +x *.sh
./deploy.sh
```

### Step 5：访问

打开浏览器访问 `http://你的服务器IP`，默认账户 `admin` / `admin123`。

---

## 3. 配置 HTTPS

### 方案 A：Nginx + Let's Encrypt（推荐）

**前提**：域名 DNS 已指向服务器 IP，端口 80/443 在安全组中开放。

```bash
./setup-ssl.sh
```

脚本会自动：安装 certbot → 申请证书 → 替换 nginx 配置为 SSL → 设置自动续签。

### 方案 B：Cloudflare Tunnel（无需开放端口）

**前提**：域名托管在 Cloudflare。

```bash
# 1. 安装 cloudflared
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
sudo install cloudflared /usr/local/bin/cloudflared

# 2. 设置隧道
./setup-cf-tunnel.sh

# 3. 启动
docker compose -f docker-compose.yml -f docker-compose.cf-tunnel.yml up -d
```

---

## 4. 日常运维

### 查看日志

```bash
docker compose logs -f              # 所有服务
docker compose logs -f backend      # 只看后端
docker compose logs -f nginx        # 只看 nginx
```

### 重启服务

```bash
docker compose restart
```

### 停止服务

```bash
docker compose down                 # 停止但保留数据
docker compose down -v              # 停止并删除数据卷（⚠ 数据会丢失）
```

### 更新部署

```bash
git pull
docker compose build --pull
docker compose up -d
docker compose exec backend python scripts/seed_data.py  # 可选
```

---

## 5. 数据备份与恢复

### 手动备份

```bash
./backup.sh
```

备份文件保存在 `backups/` 目录。

### 自动每日备份

```bash
./backup.sh --install-cron
```

每天凌晨 4:00 自动备份，保留最近 7 天日备份 + 4 周周备份。

### 恢复数据

```bash
# 1. 停止服务
docker compose down

# 2. 替换数据库文件
cp backups/quiz-20260101.db data/quiz.db

# 3. 重新启动
docker compose up -d
```

---

## 6. 云服务器安全组配置

| 端口 | 用途 | 建议 |
|------|------|------|
| 22 | SSH | 仅允许你的 IP |
| 80 | HTTP（Let's Encrypt 验证） | 允许全网 |
| 443 | HTTPS | 允许全网 |
| 8001 | 后端直连 | ❌ 不开放（仅 nginx 内部访问） |

> 使用 Cloudflare Tunnel 方案时，80/443 都不需要开放。

---

## 7. 故障排查

### 服务无法启动

```bash
docker compose ps          # 查看容器状态
docker compose logs backend | tail -50  # 查看后端日志
```

### 数据库被锁

SQLite 在并发写入时可能锁表。重启后端即可恢复：

```bash
docker compose restart backend
```

### 前端页面 404

确保前端构建产物存在：

```bash
ls frontend/dist/index.html    # 应存在
```

如果不存在，重新构建：

```bash
cd frontend && npm run build
```

### AI 出题失败

检查 DeepSeek API Key 是否正确：

```bash
docker compose exec backend python -c "from app.config import settings; print('Key:', settings.DEEPSEEK_API_KEY[:10] + '...')"
```

### 修改默认密码

目前默认密码在种子数据中设定。修改方法：

```bash
docker compose exec backend python -c "
from app.db.engine import SessionLocal
from app.db.models import User
import bcrypt
db = SessionLocal()
user = db.query(User).filter_by(username='admin').first()
user.password_hash = bcrypt.hashpw(b'你的新密码', bcrypt.gensalt()).decode()
db.commit()
db.close()
print('Password updated')
"
```

---

## 8. 容器架构

```
┌──────────────────────────────────────────┐
│              互联网                       │
│    https://quiz.yourdomain.com            │
└──────────────┬───────────────────────────┘
               │
    ┌──────────▼──────────┐
    │  nginx (port 80/443)│  ← 静态文件 + 反向代理
    │  nginx:alpine       │
    └──────────┬──────────┘
               │ /api/ → proxy_pass
    ┌──────────▼──────────┐
    │  backend (port 8001)│  ← FastAPI + Uvicorn
    │  python:3.12-slim   │
    │  ┌────────────────┐ │
    │  │  SQLite quiz.db │ │  ← Docker volume 持久化
    │  │  DeepSeek API   │ │  ← 外部 AI 服务
    │  └────────────────┘ │
    └─────────────────────┘

可选（方案 B）：
    ┌──────────────────────┐
    │  cloudflared tunnel  │  ← Cloudflare Tunnel
    │  cloudflare/cloud-   │     （替代 nginx SSL）
    │  flared:latest       │
    └──────────────────────┘
```

---

## 9. 文件索引

| 文件 | 用途 |
|------|------|
| `Dockerfile` | 多阶段构建（Python 后端 + Node 前端构建） |
| `docker-compose.yml` | 服务编排（nginx + backend） |
| `nginx.conf` | HTTP 版本 nginx 配置 |
| `nginx-ssl.conf.template` | HTTPS 版本 nginx 模板 |
| `.env.production.example` | 生产环境变量模板 |
| `deploy.sh` | 一键部署脚本 |
| `setup-ssl.sh` | Let's Encrypt SSL 配置 |
| `setup-cf-tunnel.sh` | Cloudflare Tunnel 配置 |
| `backup.sh` | 数据库备份脚本 |
| `DEPLOY.md` | 本文件 |
