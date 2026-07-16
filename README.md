# 一课一练 · 刷题网站

在线地址：[https://quiz.312233.xyz](https://quiz.312233.xyz)

---

## 云部署架构

```
手机 → quiz.312233.xyz → Cloudflare Pages (前端) → Railway (后端) → Railway 卷 (SQLite)
```

| 组件 | 平台 | 费用 |
|------|------|------|
| 前端 (Vue3 SPA) | Cloudflare Pages | 免费 |
| 后端 (FastAPI) | Railway | 免费额度 ($5/月) |
| 数据库 (SQLite) | Railway Volume | 免费 1GB |
| 域名 | Cloudflare DNS | 已有 |

---

## 部署步骤

### 1. 推送代码到 GitHub

```bash
cd quiz-app
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/quiz-app.git
git push -u origin main
```

### 2. 部署后端到 Railway

1. 打开 [railway.com](https://railway.com) → 用 GitHub 登录
2. New Project → Deploy from GitHub repo → 选 `quiz-app`
3. Root Directory 设为 `quiz-app/backend`
4. 添加 Volume：路径 `/data`
5. 添加环境变量：

```
DEEPSEEK_API_KEY=sk-your-real-key
JWT_SECRET=随机加密字符串
DATA_DIR=/data
```

6. Deploy → 记下分配的域名（如 `quiz-api.up.railway.app`）

### 3. 部署前端到 Cloudflare Pages

1. 打开 [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages
2. Create → Pages → Connect to Git → 选 GitHub repo
3. 构建设置：
   - **Framework preset**: Vue (Vite)
   - **Build command**: `cd quiz-app/frontend && npm install && npm run build`
   - **Output directory**: `quiz-app/frontend/dist`
4. 环境变量：
   - `VITE_API_BASE` = `https://你的railway域名`（末尾不加 `/api`）
5. Save and Deploy

### 4. 绑定域名

Cloudflare DNS 添加 CNAME：
- `quiz` → `quiz-app.pages.dev`（Cloudflare Pages 给的域名）

---

## 本地开发

```bash
# 后端
cd quiz-app/backend
cp .env.example ../.env  # 编辑填入 DEEPSEEK_API_KEY
pip install -r requirements.txt
python scripts/seed_data.py --reset
uvicorn app.main:app --port 8001

# 前端
cd quiz-app/frontend
npm install
npm run dev
```

访问 http://localhost:5173（Vite 代理会自动转发 API 到 localhost:8001）
