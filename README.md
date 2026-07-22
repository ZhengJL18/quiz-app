

<p align="center">
  <img src="https://img.shields.io/badge/状态-活跃开发-brightgreen?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/许可证-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Vue-3.x-4FC08D?style=flat-square&logo=vue.js" alt="Vue">
  <img src="https://img.shields.io/badge/AI-DeepSeek-536DFE?style=flat-square" alt="DeepSeek">
  <img src="https://img.shields.io/badge/Android-APK-3DDC84?style=flat-square&logo=android" alt="Android">
</p>

<h1 align="center">三一 · 学而时习之</h1>
<h3 align="center">会出题的 AI 教练</h3>

<p align="center">
  <b>懂你哪里不会。在你遗忘之前提醒你。<br>以千年儒学为体，以学习科学为用。</b>
</p>

---

## 为什么做这个？

刷过题的同学都懂那种感觉——打开某题库 App，做来做去永远是那几百道题。题目背下来了，考试换一种问法还是不会。你想弄懂背后的原理，App 只会冷冰冰地告诉你「回答错误，正确答案是 C」。

**学习不应该是这样。**

「三一」的名字来自《论语》——「学而时习之，不亦说乎」。我们想做的，不是又一个题库，而是一个真正懂你的 **AI 学习教练**。它不会给你塞一套万年不变的题，而是根据你的薄弱点**按需生成**新题；它不会只告诉你对错，而是像私教一样**一步步讲到你懂为止**；它在你快遗忘的时候**主动提醒你复习**——因为最好的复习时机，就是「差一点就忘了」的那一刻。

---

## 它和普通题库 App 本质上的不同

> 三一的底层模型 = **精熟学习** + **检索练习** + **间隔重复** + **即时反馈** + **自适应难度**

这不是随口说的——这五个机制恰好是学习科学中效应量最大的一组策略组合（d ≈ 0.7–0.9）。我们做的事，是用 AI 让这些理论在真实学习场景中自动运转起来。

| 你想做什么 | 三一怎么帮你 |
|:---|:---|
| 🤖 **刷不完的题** | 选科目、定难度，AI 按需生成新题。按 Bloom 认知层次（识记→应用→分析）出题，每次都不一样 |
| 💬 **不懂就问** | 每道题旁边有 AI 助教。追问、换角度讲解、要更简单的例子——随便聊，像一对一私教 |
| 📊 **真正知道自己哪里弱** | 不是「正确率 70%」这种粗粒度统计。基于掌握度建模追踪每个知识点的掌握状态，错题自动收录 |
| 🧠 **遗忘前自动复习** | 自适应间隔复习调度——不是 Anki 式的固定间隔，而是根据你的实际遗忘曲线动态调整 |
| 📝 **课件变结构化笔记** | 上传老师的 PPT/PDF，AI 帮你搭好知识框架。你在这个框架上标注疑问、补充自己的理解——AI 是学习支架，不是替你做笔记 |
| 📱 **手机也能学** | 原生 Android APK。食堂排队、地铁通勤，打开就学 |

**底线**：不是 AI 替你学，是 AI 帮你学会怎么学。

---

## 📸 界面

> 截图正在赶来的路上 🙃（诚招会截图的同学帮忙贡献几张，PR 欢迎！）

| 页面 | 说明 |
|:---|:---|
| 🏠 首页 | 科目选择 + 学习进度概览 + 今日推荐 |
| 📝 答题 | AI 生成题目 + 即时判分 + 逐题对话讲解 |
| 📊 掌握度 | 按知识点/科目的掌握热力图 + 错题本 + 复习日历 |
| 💬 AI 助教 | 自由对话，上传课件自动生成笔记框架 |
| ⚙️ 设置 | API Key 管理 + 学习偏好 + 多用户管理 |

---

## 📂 项目结构

```
quiz-app/
├── backend/                  # Python FastAPI 后端
│   ├── app/
│   │   ├── ai_service/       # DeepSeek 客户端 & Prompt 模板
│   │   ├── db/               # SQLAlchemy 模型 & 引擎
│   │   ├── routers/          # API 路由（18 个文件）
│   │   ├── schemas/          # Pydantic 数据模型
│   │   └── services/         # 掌握度/SRS/记忆/RAG 等服务
│   ├── tests/                # pytest 测试
│   ├── migrations/           # Alembic 数据库迁移
│   └── requirements.txt
├── frontend/                 # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── api/              # axios 客户端
│   │   ├── components/       # 通用组件（聊天/笔记/管理）
│   │   ├── stores/           # Pinia 状态管理
│   │   ├── views/            # 页面（18 个视图）
│   │   └── router/           # Vue Router
│   ├── android/              # Capacitor Android 工程
│   └── package.json
├── docker-compose.yml        # Docker 一键部署
├── nginx.conf                # Nginx 配置
└── docs/                     # 设计文档 & 审查报告
```

---

## 🚀 5 分钟跑起来

### 你需要

- Python 3.11+
- Node.js 18+
- 一个 [DeepSeek API Key](https://platform.deepseek.com/api_keys)（注册送额度，够用很久）

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev                     # → http://localhost:5173
```

打开浏览器访问 `http://localhost:5173`，注册账号，填入你的 DeepSeek API Key，开始学习。

> 💡 每个用户使用自己的 API Key，费用完全隔离。

---

## 🐳 Docker 部署

适合有服务器 / NAS 的同学：

```bash
# 在项目根目录执行
cp backend/.env.example backend/.env
# 编辑 backend/.env，至少填：
#   DEEPSEEK_API_KEY=sk-xxxx
#   SECRET_KEY=$(openssl rand -hex 32)
#   SUPERADMIN_EMAIL=admin@xxx.com

docker compose up -d
# → http://localhost:8080
```

| 变量 | 说明 | 必填 |
|:---|:---|:---:|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | ✅ |
| `SECRET_KEY` | JWT 签名密钥 | ✅ |
| `SUPERADMIN_EMAIL` | 超管邮箱（首次启动自动创建） | ✅ |
| `DATABASE_URL` | 数据库路径，默认 `sqlite:///./data/sanyi.db` | ❌ |
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare Tunnel token | ❌ |

> 服务端口：80 (Nginx → 前端静态文件 + API 反向代理)。FastAPI 不直接暴露。

---

## 🏗️ 架构 & 技术栈

```
                    ┌─────────────────────────────┐
                    │       Capacitor (Android)     │
                    │  ┌─────────────────────────┐  │
                    │  │      Vue 3 + Vite        │  │
                    │  │    TailwindCSS 4 + Pinia  │  │
                    │  └───────────┬─────────────┘  │
                    └──────────────┼────────────────┘
                                   │  HTTP/REST
                    ┌──────────────┼────────────────┐
                    │              ▼                 │
                    │   ┌─────────────────────┐     │
                    │   │   Nginx (反向代理)    │     │
                    │   └──────────┬──────────┘     │
                    │              ▼                 │
                    │   ┌─────────────────────┐     │
                    │   │  FastAPI              │     │
                    │   │  · AI 题目生成引擎    │     │
                    │   │  · 掌握度建模 & SRS   │     │
                    │   │  · JWT 认证 & 隔离    │     │
                    │   └──────────┬──────────┘     │
                    │              ▼                 │
                    │   ┌─────────────────────┐     │
                    │   │  SQLite (WAL 模式)   │     │
                    │   └─────────────────────┘     │
                    │              │                 │
                    │              ▼                 │
                    │   ┌─────────────────────┐     │
                    │   │   DeepSeek API       │     │
                    │   │   (用户自带 Key)      │     │
                    │   └─────────────────────┘     │
                    │                               │
                    │      Docker 一键部署           │
                    └───────────────────────────────┘
```

| 层 | 技术 | 为什么选它 |
|:---|:---|:---|
| **后端** | Python FastAPI | 异步高性能，自动生成 OpenAPI 文档 |
| **ORM** | SQLAlchemy | 成熟可靠，配合 SQLite WAL 支持并发读写 |
| **数据库** | SQLite (WAL) | 零配置，数据即文件。个人/小团队部署不用装 MySQL |
| **前端** | Vue 3 + Composition API | 响应式，组件化开发效率高 |
| **构建** | Vite | 秒级热更新 |
| **样式** | TailwindCSS 4 | 原子化 CSS，暗色模式内置 |
| **状态** | Pinia | Vue 3 官方推荐，比 Vuex 轻量 |
| **AI** | DeepSeek API | 国产模型中文理解最强，性价比极高 |
| **移动端** | Capacitor | 一套 Vue 代码 → Android APK |
| **部署** | Docker + Compose | 一键上线，环境一致 |
| **外网** | Cloudflare Tunnel | 无需公网 IP，免费内网穿透 |

---

## 🗺️ 路线图

| 状态 | 计划 | 预计 |
|:---:|:---|:---|
| ✅ | AI 出题引擎（科目/章节/认知层次三维生成） | 2025 Q4 |
| ✅ | AI 对话助教（上下文感知，流式输出） | 2026 Q1 |
| ✅ | 自适应间隔复习 + 掌握度追踪 | 2026 Q1 |
| ✅ | 课件上传 → AI 结构化笔记框架 | 2026 Q2 |
| ✅ | 多用户系统（超管 + 普通用户 + 数据隔离） | 2026 Q2 |
| ✅ | Capacitor Android APK | 2026 Q3 |
| ✅ | Docker 一键部署 | 2026 Q3 |
| ⏳ | 题目分享 & 社区 | 2026 Q4 |
| ⏳ | 学习小组 / 排行榜 | 2027 |
| ⏳ | iOS 支持 | 2027 |
| ⏳ | 多模型接入（Claude / GPT-4o / Qwen） | 2027 |
| ⏳ | 国际化 (i18n) | 2027 |

---

## 🤝 贡献

欢迎所有觉得「刷题 App 应该更智能」的同学。

```bash
git checkout -b feat/your-cool-idea
```

**开发环境**：
```bash
# 后端
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
# 测试
python -m pytest tests/ -v

# 前端
cd frontend && npm install && npm run dev
```

贡献方向：

- 🧪 **新科目 Prompt 模板**：把你专业的出题套路写成模板
- 🎨 **前端优化**：UI/UX 改进、移动端适配
- 🧠 **算法改进**：更聪明的掌握度模型、难度自适应
- 📸 **截图**：目前最缺的就是你手机上的几张界面截图
- 📖 **文档翻译**

> PR 欢迎直接开，不用先提 Issue 问能不能做——做了再说。AI 辅助开发的代码请在 PR 描述里标注，我们好奇你是怎么用 AI 的 😄

---

## 📄 许可证

MIT © 2024 SanYi Contributors

---

<p align="center">
  <i>「学而时习之，不亦说乎」—— 不是 AI 替你学，是 AI 帮你会学。</i>
</p>
