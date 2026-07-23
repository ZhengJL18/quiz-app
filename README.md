
<br>
<br>

<p align="center">
  <pre style="font-size: 12px; line-height: 1.2; color: #4a5a8a;">
    ███████╗ █████╗ ███╗   ██╗   ██╗   ██╗
    ╚══███╔╝██╔══██╗████╗  ██║   ╚██╗ ██╔╝
      ███╔╝ ███████║██╔██╗ ██║    ╚████╔╝
     ███╔╝  ██╔══██║██║╚██╗██║     ╚██╔╝
    ███████╗██║  ██║██║ ╚████║      ██║
    ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝      ╚═╝
  </pre>
</p>

<h1 align="center">三一 · 学而时习之</h1>

<p align="center">
  <a href="./releases/三一-latest.apk"><img src="https://img.shields.io/badge/📱_下载_APK-立即安装-3DDC84?style=for-the-badge&logo=android" alt="Download APK"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/状态-活跃开发-brightgreen?style=flat-square" alt="Status">
  <img src="https://img.shields.io/badge/许可证-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Vue-3.x-4FC08D?style=flat-square&logo=vue.js" alt="Vue">
  <img src="https://img.shields.io/badge/AI-DeepSeek-536DFE?style=flat-square" alt="DeepSeek">
  <img src="https://img.shields.io/badge/Android-APK-3DDC84?style=flat-square&logo=android" alt="Android">
</p>

<br>

> <p align="center"><b>会出题的 AI 教练</b><br>解决大学学习书多、书重、针对性弱、弱反馈问题。<br></p>

<br>

---

## 💡 为什么你应该在意这个项目

刷过题的同学都知道——题库 App 来来去去就那几百道题，要么太难要么太简单，要么一无所获，要么挫败感十足。但是光啃课本而不练习又往往缺乏反馈感————读了和读了一样。然而，现在是AI的时代了，**有些问题不再是鱼和熊掌不可得兼**，利用AI的针对性出题，基于长期记忆机制、skill机制，为大学学习赋能。

三一想做的不是「又一个题库」，而是一个**真的懂你在学什么的 AI 教练**：

- ⚡ **永不枯竭的题目** — AI 按科目 + 章节 + 认知层次实时生成，每次都不一样
- 🎯 **精准定位弱点** — 不是「正确率 70%」这种粗粒度数字，而是每个知识点的掌握状态
- ⏰ **遗忘前提醒你** — 自适应间隔复习，在你「差一点就忘了」的那一刻推送复习
- 💬 **问到懂为止** — AI 助教逐题对话讲解，换角度、给例子、追根溯源

> **三一的底层模型** = 精熟学习 + 检索练习 + 间隔重复 + 即时反馈 + 自适应难度
>
> 这五个机制恰好是学习科学中效应量最大的一组策略组合（d ≈ 0.7–0.9）——不是随口说的，有文献支撑。

---

## 📸 界面

| 页面 | 说明 |
|:---|:---|
| 🏠 **首页** | 科目选择 + 学习进度概览 + 今日推荐 |
| 📝 **答题** | AI 生成题目 + 即时判分 + 逐题对话讲解 |
| 📊 **掌握度** | 按知识点/科目的掌握热力图 + 错题本 + 复习日历 |
| 💬 **AI 助教** | 自由对话，上传课件自动生成笔记框架 |
| ⚙️ **设置** | API Key 管理 + 学习偏好 + 多用户管理 |

---

## 📂 项目结构

```
quiz-app/
├── backend/                  # Python FastAPI 后端（18 个路由模块）
├── frontend/                 # Vue 3 + Vite 前端（18 个视图）
│   └── android/              # Capacitor Android 工程
├── releases/                 # 📱 APK 下载
├── docker-compose.yml        # 一键 Docker 部署
├── nginx.conf                # 生产环境 Nginx 配置
└── docs/                     # 设计文档 & 审查报告
```

---

## 🚀 5 分钟跑起来

**方法一 ：打开网页311007.xyz**
**方法二：下载原生安卓应用（更新可能不及时）**
**方法三：自己部署此开源项目**

**你需要**：Python 3.11+ · Node.js 18+ · [DeepSeek API Key](https://platform.deepseek.com/api_keys)（免费额度管够）

```bash
# 后端
cd backend
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端（新终端）
cd frontend && npm install && npm run dev          # → http://localhost:5173
```

打开浏览器，注册账号，填入 DeepSeek API Key，开始学习。每个人用自己的 Key，费用隔离。

---

## 🐳 Docker 部署

```bash
cp backend/.env.example backend/.env   # 编辑填入 DEEPSEEK_API_KEY / SECRET_KEY
docker compose up -d                   # → http://localhost:8080
```

| 变量 | 说明 | 必填 |
|:---|:---|:---:|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | ✅ |
| `SECRET_KEY` | JWT 签名密钥（`openssl rand -hex 32`） | ✅ |
| `SUPERADMIN_EMAIL` | 超管邮箱（首次启动自动创建） | ✅ |

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
                                   │
                    ┌──────────────┼────────────────┐
                    │              ▼                 │
                    │   ┌─────────────────────┐     │
                    │   │   Nginx              │     │
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
                    │   └──────────┬──────────┘     │
                    │              ▼                 │
                    │   ┌─────────────────────┐     │
                    │   │   DeepSeek API       │     │
                    │   │   (用户自带 Key)      │     │
                    │   └─────────────────────┘     │
                    └───────────────────────────────┘
```

| 层 | 技术 | 选择理由 |
|:---|:---|:---|
| 后端 | FastAPI | 异步高性能，自动 OpenAPI 文档 |
| 数据库 | SQLite WAL | 零配置，单文件，个人部署不用装 MySQL |
| 前端 | Vue 3 + Vite | 响应式 + 秒级热更新 |
| 样式 | TailwindCSS 4 | 原子化 CSS，暗色模式内置 |
| AI | DeepSeek | 中文理解最强，性价比极高 |
| 移动端 | Capacitor | 一套 Vue 代码直接出 Android APK |
| 部署 | Docker | 一键上线，环境一致 |

---

## 🗺️ 路线图

| 状态 | 计划 | 预计 |
|:---:|:---|:---|
| ✅ | AI 出题引擎 | 2025 Q4 |
| ✅ | AI 对话助教 | 2026 Q1 |
| ✅ | 间隔复习 + 掌握度追踪 | 2026 Q1 |
| ✅ | 课件 → AI 笔记 | 2026 Q2 |
| ✅ | 多用户系统 | 2026 Q2 |
| ✅ | Android APK | 2026 Q3 |
| ✅ | Docker 部署 | 2026 Q3 |
| ⏳ | 题目分享 & 社区 | 2026 Q4 |
| ⏳ | 多模型接入 | 2027 |
| ⏳ | iOS + i18n | 2027 |

---

## 🤝 贡献

```bash
git checkout -b feat/your-cool-idea

# dev 环境
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python -m pytest tests/ -v       # 跑测试

cd frontend && npm install && npm run dev
```

> PR 直接开，不用先问——做了再说。

---

<p align="center">
  <i>「学而时习之，不亦说乎」—— 不是 AI 替你学，是 AI 帮你会学。</i>
</p>
