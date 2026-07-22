# 三一 · 学习 Agent 架构方案

> 终局目标：每个学生拥有一个**私有的、可生长的 AI 学习 Agent**。
> Agent 运行在云服务器上，拥有一套完整的认知文件系统（类似 Obsidian vault），
> 会自学习、会了解你、会在你每次打开网站时说"昨天你极限错了三道题，今天先练这个吧"。

---

## 一、核心架构理念

### 1.1 每个用户 = 一个迷你 Obsidian Vault

用户数据集不是数据库里的几条记录，而是一个**完整的文件系统**。

```
data/users/{user_id}/
├── .agent/                          # Agent 自身的配置和记忆
│   ├── system.md                    # Agent 的身份、职责、行为准则
│   ├── memory.md                    # Agent 对用户的长期认知（自动更新）
│   ├── journal.md                   # Agent 自身的工作日志
│   └── skills/                      # Agent 的专项技能模块
│       ├── diagnose.md              # 薄弱点深度诊断
│       ├── study-plan.md            # 多日学习计划生成
│       ├── explain.md               # 知识点深度讲解
│       ├── exam.md                  # 模拟考试生成
│       ├── report.md                # 学习报告（周报/月报）
│       └── motivate.md              # 学习动力激励
│
├── profile/                         # 用户身份层
│   ├── about.md                     # 基本信息：谁、什么专业、什么年级
│   ├── goals.md                     # 学习目标：期末90分、考研上岸、过四级
│   ├── preferences.md               # 偏好：喜欢题型、学习时段、讲解风格
│   └── context.md                   # 环境：这学期几门课、什么教材、考试时间
│
├── knowledge/                       # 知识层 — 最核心
│   ├── index.md                     # 所有科目的索引
│   └── {subject}/                   # 每个科目一个文件夹
│       ├── subject.md               # 科目元数据：教材、老师、考试日期
│       ├── chapters.md              # 章节树
│       ├── mastery.md               # 知识点 × 掌握度矩阵
│       └── weaknesses.md            # 薄弱点历史
│
├── practice/                        # 练习层
│   ├── sessions/                    # 每轮练习的详细记录
│   │   └── 2026-07-19-001.md       # 一次练习的完整记录
│   ├── wrong-book.md                # 错题汇总（Agent 自动维护）
│   ├── srs.md                       # 间隔复习排期
│   └── stats.md                     # 统计数据（周/月/学期）
│
├── materials/                       # 学习资料层
│   ├── index.md                     # 资料目录
│   ├── textbooks/                   # 教材 PDF + 提取后的 MD
│   ├── notes/                       # 课堂笔记
│   ├── slides/                      # 课件
│   └── summaries/                   # 用户自己写的总结
│
├── journal/                         # 学习日志层
│   ├── 2026-07-15.md               # 每天一篇，Agent 自动撰写
│   └── 2026-07-16.md
│
└── chat/                            # 对话历史
    ├── index.md                     # 对话索引
    └── 2026-07/                     # 按月归档
```

### 1.2 存储预算

每个用户分配 **1GB**（硬盘配额，先不做硬限制，用软监控）。

| 层 | 典型大小 | 说明 |
|------|---------|------|
| .agent/ | < 1MB | 纯文本 |
| profile/ | < 1MB | 纯文本 |
| knowledge/ | 1-5MB | 纯文本，随科目增加 |
| practice/ | 5-50MB | 练习记录是文本，长了自动压缩 |
| materials/ | 100-900MB | 教材 PDF + 课件 → 这是大头 |
| journal/ | 1-5MB | 每天一篇，纯文本 |
| chat/ | 5-50MB | 对话历史，旧的可压缩 |
| **合计** | **~200MB-1GB** | |

服务器现状：50GB 磁盘，42GB 空闲 → 可以支持 **20-40 个活跃用户**。

### 1.3 Agent 如何"思考"

```
用户打开网站 / 发消息
        │
        ▼
┌──────────────────────────────────────┐
│         Step 1: Skill 路由            │
│  分析用户意图 → 匹配 Skill            │
│  如 "期末怎么复习" → /study-plan     │
│  如 "帮我看看哪里弱" → /diagnose     │
│  如 无匹配 → 走默认 Agent 行为        │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         Step 2: 模型路由              │
│  根据任务类型选择模型：               │
│  - 对话/出题/解析 → DeepSeek (默认)  │
│  - 规划/深度诊断 → DeepSeek Reasoner │
│  - PDF/图片分析  → 豆包/Kimi(多模态) │
│  - Embedding     → DeepSeek Embedding│
│  - 用户未配多模态Key → 降级为文本提取 │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         Step 3: 上下文组装            │
│                                      │
│  1. 读取 .agent/system.md  ← 身份    │
│  2. 读取 .agent/memory.md  ← 长期记忆│
│  3. 读取 profile/ 全部     ← 用户是谁│
│  4. 读取 knowledge/{科目}/ ← 知识状态│
│  5. 读取 practice/stats.md ← 练习数据│
│  6. 读取 journal/ 最近7天  ← 近期动态│
│  7. 加载 Skill prompt (如有匹配)      │
│                                      │
│  组装成一个完整上下文 → 注入系统提示   │
└──────────────┬───────────────────────┘
               │
               ▼
         调用选定的模型 API
               │
               ▼
┌──────────────────────────────────────┐
│         Step 4: Agent 行为 + 自学习   │
│                                      │
│  执行用户请求（出题、讲解、规划...）   │
│        +                             │
│  更新记忆文件：                       │
│  - knowledge/mastery.md (掌握度变化)  │
│  - practice/sessions/ (记录本次练习)  │
│  - journal/今日.md (写学习日志)       │
│  - .agent/memory.md (如有新认知)      │
└──────────────────────────────────────┘
```

### 1.4 模型路由：一主多辅

**核心原则**：DeepSeek 是默认主力，其他模型是可选的专项补充。

```
                    用户请求
                        │
                  ModelRouter
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   DeepSeek Chat   多模态模型       DeepSeek
   (主力·免费)    (按需·可选)      Reasoner
        │               │               │
   对话/出题/       PDF分析/        深度诊断/
   解析/规划       图片理解        学习报告
```

**用户侧配置**（设置页）：

```
┌─ AI 模型设置 ──────────────────────────┐
│                                         │
│  DeepSeek API Key *                     │
│  [sk-xxxx················]  ✅ 已配置   │
│  (必填·默认主力模型)                    │
│                                         │
│  豆包 API Key               [可选]       │
│  [                        ]  未配置      │
│  (多模态·PDF/图片分析)                  │
│                                         │
│  千问 API Key               [可选]       │
│  [                        ]  未配置      │
│  (多模态·长文档理解)                    │
│                                         │
│  Kimi API Key               [可选]       │
│  [sk-················]  ✅ 已配置       │
│  (多模态·200K上下文)                    │
│                                         │
│  默认模型：[DeepSeek ▼]                 │
│  PDF/图片默认：[自动选择 ▼]             │
│                                         │
└─────────────────────────────────────────┘
```

**路由规则表**：

| 任务类型 | 默认模型 | 降级策略 |
|---------|---------|---------|
| 对话、闲聊 | DeepSeek Chat | — |
| 出题 (question_gen) | DeepSeek Chat | — |
| 解析 (explanation) | DeepSeek Chat | — |
| 学习规划、深度诊断 | DeepSeek Reasoner | → DeepSeek Chat（若未配 Reasoner） |
| PDF 分析 | 豆包 / Kimi（多模态） | → PyMuPDF 文本提取 + DeepSeek Chat |
| 图片理解 | 豆包 / Kimi（多模态） | → 提示用户"暂不支持图片分析" |
| Embedding | DeepSeek Embedding | — |
| 学习报告生成 | DeepSeek Reasoner | → DeepSeek Chat |

**Skill × 模型联动**：

| Skill | 推荐模型 | 原因 |
|-------|---------|------|
| `/diagnose` | DeepSeek Reasoner | 需要深度推理分析 |
| `/study-plan` | DeepSeek Reasoner | 需要结构化规划 |
| `/explain` | DeepSeek Chat | 标准讲解，Chat 足够 |
| `/exam` | DeepSeek Chat | 出题不需要强推理 |
| `/report` | DeepSeek Reasoner | 需要总结+分析 |
| PDF 资料分析 | 豆包/Kimi | 多模态理解 PDF 图文 |
| `/motivate` | DeepSeek Chat | 情感关怀，Chat 即可 |

**实现要点**：
- 路由逻辑在 `app/services/model_router.py`，独立于 Agent 主逻辑
- 用户配了可选 Key → 对应任务自动使用 → 没配 → 降级
- Skill 可以在自己的 prompt 中声明偏好的模型类型，Router 尊重 Skill 的选择

---

## 二、Agent 系统提示设计

### 2.1 `.agent/system.md` — Agent 的身份文件

```markdown
---
name: 三一学习助手
version: 1.0
model: deepseek-chat
---

# 你是三一学习 Agent

你的身份：一个认识学生、懂教育、会推动成长的 AI 学习 Agent。

## 核心职责

1. **认识学生**。每次对话前，你必须完整阅读学生的 profile/ 和 knowledge/ 文件。
   不了解学生就不要乱给建议。

2. **推动练习**。你的价值不是"回答一个问题"，而是"让学生真的学会"。
   这意味着：出题 > 讲解 > 闲聊。每次对话结束时，提案下一次做什么。

3. **自学习**。每次交互结束后，你必须更新相关记忆文件：
   - 发现新薄弱点 → 写入 knowledge/{科目}/weaknesses.md
   - 掌握度变化 → 更新 knowledge/{科目}/mastery.md
   - 今天的重要事件 → 追加到 journal/{今日}.md

4. **个性化**。读学生的 preferences.md，按他们喜欢的方式教学。
   有人喜欢例题先行，有人喜欢原理先行。不要用同一套方法教所有人。

## 行为准则

- 每次对话前，先读 profile/、knowledge/ 和最近 7 天 journal/
- 出题时，优先选择 mastery.md 中标 🔴 的知识点
- 学生连续答对 3 次同一知识点 → 提高难度
- 学生连续答错 → 降级 + 换个角度讲解
- 每天第一次打开 → 主动生成今日学习建议
- 每周末 → 总结本周进步和不足

## 文件读写权限

你能读写的文件范围：data/users/{user_id}/
不要越界读取其他用户的数据。
```

### 2.2 `.agent/memory.md` — Agent 的长期记忆

Agent 自动维护。每次对话中发现的新认知会追加进来。

```markdown
---
updated: 2026-07-19
---

# 关于郑俊林的长期记忆

## 我已经了解的
- 大二，计算机专业，这学期 4 门数学课
- 目标：高数期末 90 分
- 薄弱点：极限的无穷小比较、换元积分
- 喜欢先看例题再学原理，不喜欢干讲定义
- 晚上 9-11 点效率最高
- 对 LaTeX 公式接受度好，不畏惧数学符号
- 上次提到想参加数学建模比赛，但还没开始准备

## 我猜测但未确认的
- 可能对线性代数的几何意义缺乏直观理解
- 大学物理可能也需要帮助但还没问过我

## 对话风格适应
- 不用太正式的语气，可以轻松一点
- 但数学讲解要严谨，公式不能有错
- 在他连着错 3 道题时，主动问"要不要换个角度讲？"
- 他疲惫时会说"好累"，此时不要继续出题，给建议休息
```

---

## 三、Skill 模块：Agent 的专项技能

### 3.0 为什么需要 Skill

Agent 的 system.md 定义的是"我是谁、我怎么做"。但有些任务需要**不同的提示策略、不同的工具链、不同的输出格式**。

就像 Claude Code 的 `/deep-research` 和 `/code-review` 各自有独立的 prompt 和工作流，
学习 Agent 也需要：

- `/diagnose` — 不是随便说两句薄弱点，而是**系统性深度诊断**
- `/exam` — 不是出几道题，而是**完整模拟考试 + 评分 + 薄弱点报告**
- `/study-plan` — 不是给一个建议，而是**多日计划 + 每日检查点**

每个 Skill 是一个独立的 Markdown 文件，定义了该技能专用的 system prompt、工具集和输出规范。Agent 根据用户意图自动路由。

### 3.1 Skill 路由规则

```
用户说 → Agent 分析意图 → 匹配 Skill → 加载 Skill prompt → 执行
```

| 用户说 | 匹配 Skill | 加载文件 |
|--------|-----------|---------|
| "帮我看看我哪里最弱" "分析一下我的薄弱点" | `/diagnose` | skills/diagnose.md |
| "帮我制定一周的复习计划" "期末怎么安排" | `/study-plan` | skills/study-plan.md |
| "给我解释一下拉格朗日中值定理" "XX 是什么意思" | `/explain` | skills/explain.md |
| "来一场模拟考" "高数期末模拟" | `/exam` | skills/exam.md |
| "我最近学得怎么样" "给我个周报" | `/report` | skills/report.md |
| "不想学了" "好累" "坚持不下去了" | `/motivate` | skills/motivate.md |
| 其他 / 不清楚 | → 默认 Agent 行为 | system.md |

### 3.2 Skill 文件示例

#### `skills/diagnose.md` — 薄弱点深度诊断

```markdown
---
skill: diagnose
trigger: 分析弱点 | 诊断 | 薄弱点 | 哪里差 | 水平如何
tools: [GET_PROFILE, GET_KNOWLEDGE, GET_WRONG_BOOK, GET_RECENT_SESSIONS]
---

# 学习诊断 Agent

你是一个学习诊断专家。你的任务不是简单列出薄弱点，而是**找出根本原因并给出可执行的改进方案**。

## 诊断流程

1. 读取 profile/ 了解学生背景和目标
2. 读取 knowledge/{科目}/mastery.md 了解掌握度矩阵
3. 读取 practice/wrong-book.md 分析错误模式
4. 读取最近 7 天的 practice/sessions/ 逐日对比趋势
5. 读取最近 7 天的 journal/ 了解学生自述

## 输出格式

### 📊 掌握度总览
[表格：每个科目的掌握度、练习量、趋势箭头]

### 🔴 需要立即关注的薄弱点（Top 3）
1. **[知识点名]** — 掌握度 XX%
   - 错误模式：[具体描述，如"换元后忘回代"而非"计算粗心"]
   - 根本原因：[是概念不清？练得太少？还是公式记错？]
   - 改进方案：[具体到明天练什么、怎么练]
   - 预计恢复时间：[练 X 次 / Y 天后可达到 Z%]

2. ...

### 🟡 需要巩固的中等掌握点
[类似格式]

### 🟢 已稳定掌握
[认可学生的进步，具体指出哪些知识点已经过关]

### 📈 趋势分析
- 本周进步最快的知识点：[具体数据]
- 本周退步的知识点：[具体数据 + 可能原因]
- 和上周对比：[方向]

### 🎯 建议的近期行动计划
- 本周一三五：XXX
- 本周二四：XXX
- 周末：XXX

## 重要原则
- 不要只说"多练练"，要说"练什么、练几次、怎么练"
- 不要把"计算粗心"当成万能理由——分析具体是什么类型的计算错误
- 先肯定学生的进步，再指出不足
```

#### `skills/study-plan.md` — 多日学习计划

```markdown
---
skill: study-plan
trigger: 计划 | 安排 | 复习计划 | 期末 | 备考 | 时间表
tools: [GET_PROFILE, GET_KNOWLEDGE, GET_SRS, GET_GOALS]
---

# 学习规划 Agent

你是学习规划专家。根据学生的目标、当前掌握度、可用时间，生成可执行的多日学习计划。

## 输入
- 学生 profile（目标、每周可用时间、偏好）
- 知识掌握度矩阵
- SRS 复习排期
- 如果有考试日期，以考试日期为终点倒推

## 输出格式

### 🎯 目标回顾
[学生的目标，确保计划与之对齐]

### 📅 第 1 天 · 周一 · 7月20日
- 🔄 复习（SRS 自动排期的题）
- 🎯 主攻：[最薄弱知识点] — 10题专项
- 📐 辅练：[第二薄弱知识点] — 5题巩固
- ⏱ 预计：40分钟

### 📅 第 2 天 · 周二 · 7月21日
...

### 📊 计划概览
- 总天数：7天
- 总题量：~80题
- 重点覆盖：换元积分、无穷小比较、高阶导数
- 期中检查点：第4天（评估是否需要调整）

### ⚠️ 风险提示
- 如果连续2天某个知识点正确率 < 40%，自动降级难度
- 第4天如果总进度 < 50%，自动缩减计划
```

#### `skills/report.md` — 学习报告生成

```markdown
---
skill: report
trigger: 报告 | 总结 | 周报 | 月报 | 最近学得怎么样 | 进步
tools: [GET_PROFILE, GET_KNOWLEDGE, GET_PRACTICE_HISTORY, GET_JOURNAL]
---

# 学习报告 Agent

生成结构化的学习报告。

## 周报格式

### 📊 本周数据
- 总练习次数、总题数、总时长
- 正确率（总体 + 分科目）
- 新增掌握的知识点（掌握度 > 70%）
- 新发现的薄弱点（掌握度 < 30%）

### 📈 对比上周
- 进步最大的 3 个知识点（附数据）
- 退步的 1-2 个知识点（附可能原因）

### 🏆 本周亮点
[具体到某一道题、某一次突破、某个顿悟时刻 — 从 journal 中提取]

### 🎯 下周展望
[基于趋势预测 + 学习目标的建议]

## 月报额外包含
- 掌握度总览图（文字版柱状图或 ASCII art）
- 学习曲线（每周正确率变化）
- 距离目标的差距
- Agent 对学生的新认知（从 .agent/memory.md 提取本月新增的条目）
```

### 3.3 Skill 的技术实现

**后端 Skill 路由**：

```python
# app/services/skill_router.py

SKILL_REGISTRY = {
    "diagnose": {
        "file": "skills/diagnose.md",
        "triggers": ["分析弱点", "诊断", "薄弱点", "哪里差", "水平如何"],
        "tools": ["GET_PROFILE", "GET_KNOWLEDGE", "GET_WRONG_BOOK"],
    },
    "study-plan": {
        "file": "skills/study-plan.md",
        "triggers": ["计划", "安排", "复习计划", "期末", "备考", "时间表"],
        "tools": ["GET_PROFILE", "GET_KNOWLEDGE", "GET_SRS", "GET_GOALS"],
    },
    "explain": {
        "file": "skills/explain.md",
        "triggers": ["解释", "什么意思", "讲讲", "什么是", "帮我理解"],
        "tools": ["GET_KNOWLEDGE", "SEARCH_MATERIALS"],
    },
    "exam": {
        "file": "skills/exam.md",
        "triggers": ["模拟考", "考试模拟", "来一场", "测试一下"],
        "tools": ["GET_KNOWLEDGE", "GENERATE_QUESTIONS", "GRADE_ANSWER"],
    },
    "report": {
        "file": "skills/report.md",
        "triggers": ["报告", "总结", "周报", "月报", "最近学得", "进步"],
        "tools": ["GET_PROFILE", "GET_KNOWLEDGE", "GET_JOURNAL"],
    },
    "motivate": {
        "file": "skills/motivate.md",
        "triggers": ["不想学", "好累", "坚持不下", "放弃", "没动力"],
        "tools": ["GET_PROFILE", "GET_JOURNAL", "GET_PROGRESS"],
    },
}

def route_skill(user_message: str) -> str | None:
    """Match user message to a skill. Returns skill name or None (use default)."""
    for name, config in SKILL_REGISTRY.items():
        for trigger in config["triggers"]:
            if trigger in user_message:
                return name
    return None
```

**Skill 加载流程**：

```
用户发消息
  ↓
skill_router.route(message)
  ↓
匹配到 skill? 
  ├─ Yes → 加载 skills/{name}.md → 替换 Agent 的 system prompt
  └─ No  → 使用默认 system.md
  ↓
加载该 skill 需要的 tools
  ↓
调用 DeepSeek（带 skill prompt + 用户上下文 + tools）
  ↓
返回结果
  ↓
Agent 反思 → 更新记忆文件
```

### 3.4 Skill 和 Claude Code Skill 的对应

| Claude Code Skill | 三一学习 Agent Skill | 区别 |
|-------------------|---------------------|------|
| `/deep-research` 多源搜索+交叉验证+报告 | `/diagnose` 多源读取(掌握度+错题+日志)+诊断报告 | 数据源是用户自己的 vault |
| `dataviz` 图表生成 | `/report` 数据可视化+文字报告 | 不做图，做文字版数据呈现 |
| `code-review` 代码审查 | `/diagnose` 不是"审查"是"诊断" | 类似的深度分析模式 |
| `loop` 循环执行 | `/study-plan` 多日计划+自动检查点 | 计划的执行循环 |
| 无直接对应 | `/motivate` 学习动力激励 | 学习 Agent 独有 |

---

## 四、知识层设计

### 4.1 `knowledge/{科目}/mastery.md` — 掌握度矩阵

每次练习后自动更新的核心文件。

```markdown
---
subject: 高等数学
updated: 2026-07-19 23:15
---

# 掌握度矩阵

| 章节 | 知识点 | 掌握度 | 练习次数 | 最近正确率 | 状态 |
|------|--------|--------|---------|-----------|------|
| 函数与极限 | 函数概念 | 85% | 12 | 83% | ✅ |
| 函数与极限 | 极限定义 | 55% | 8 | 50% | ⚠️ |
| 函数与极限 | 无穷小比较 | 30% | 6 | 33% | 🔴 |
| 导数与微分 | 导数定义 | 75% | 10 | 80% | ✅ |
| 导数与微分 | 求导法则 | 90% | 15 | 93% | ✅ |
| 导数与微分 | 高阶导数 | 50% | 4 | 50% | ⚠️ |
| 积分 | 不定积分 | 60% | 8 | 63% | ⚠️ |
| 积分 | 定积分 | 40% | 3 | 33% | 🔴 |
| 积分 | 换元积分 | 20% | 2 | 0% | 🔴 |

## Agent 建议
本周重点关注：换元积分（20%）和无穷小比较（30%）。
这两个知识点有逻辑关联——都涉及"替换"思维，同一周训练有协同效应。
```

### 3.2 掌握度如何计算

不追求绝对精确的算法。用简单的加权公式：

```
掌握度 = 最近正确率 × 0.6 + 历史正确率 × 0.2 + (练习次数 / 目标次数) × 10 × 0.2

其中：
- 最近正确率 = 最近 10 次的正确比例
- 历史正确率 = 全部记录的正确比例  
- 目标次数 = 20（同一个知识点至少练 20 次才算"充分"）
- 结果裁剪到 0-100
```

**重要的是趋势**：Agent 每天对比今天的 mastery.md 和昨天的 — 看哪些上升了（鼓励）、哪些下降了（预警）、哪些没动（需要更多练习）。

---

## 五、练习层设计

### 5.1 `practice/sessions/2026-07-19-001.md`

每一轮练习存一份文件。Agent 之后可以回顾。

```markdown
---
session_id: 382
mode: 刷题
subject: 高等数学
chapter: 换元积分
started: 2026-07-19 22:15
duration: 18min
score: 2/3
---

# 换元积分 · 刷题记录

## Q1 · 单选题 · 正确 ✅
题目：∫ x·sin(x²) dx 使用什么换元？
选择：B（u = x²）
用时：2min
→ 知识点评级：已掌握，下次出更难

## Q2 · 计算题 · 错误 ❌
题目：∫ eˣ·cos(eˣ) dx
我的答案：∫ cos(u) du（没写完）
正确答案：sin(eˣ) + C
用时：5min
→ 错误分类：计算粗心（忘了换元后要回代）
→ Agent 建议：明后天再出一道同类型的

## Q3 · 填空题 · 正确 ✅
题目：∫ (2x+1)/(x²+x+1) dx = ?
答案：ln|x²+x+1| + C
用时：3min

## 本轮总结
- 正确率：67%（2/3）
- 平均用时：3.3min/题
- 薄弱点：换元后回代容易忘
- 下次建议：再练 3 道换元积分，做完立即检查回代
```

### 4.2 `practice/wrong-book.md` — Agent 自动维护

```markdown
---
updated: 2026-07-19
---

# 错题汇总

## 🔴 活跃错题（最近7天）

### Q1 · 换元积分 · 错误3次
- 题目：∫ eˣ·cos(eˣ) dx
- 错误模式：换元后忘回代
- 最近出错：2026-07-19
- 下次复习：2026-07-21（SRS 间隔2天）

### Q2 · 无穷小比较 · 错误2次
- 题目：比较 x→0 时 sin(x) 和 x 的阶
- 错误模式：记混了等阶和同阶的定义
- 最近出错：2026-07-18
- 下次复习：2026-07-20

## 🟢 已纠正（7天内未再错）
- 极限定义题（Q3-Q5）— 已连续做对4次，移出活跃列表
```

---

## 六、日志层设计

### 5.1 `journal/2026-07-19.md` — Agent 每天自动撰写

```markdown
---
date: 2026-07-19
day_of_week: 周日
total_practice_time: 52min
total_questions: 12
correct_rate: 67%
---

# 学习日志 · 7月19日

## 今日完成
- 09:30 · 复习昨日错题（3题，全部通过 ✅）
- 10:00 · 无穷小比较专项练习（5题，正确3题）
- 22:15 · 换元积分刷题（3题，正确2题）
- 22:30 · 和 Agent 讨论了数学建模比赛的准备计划

## 今日进步
- 无穷小比较正确率从上周的 33% → 今天 60%（+27%）
- 复习题全部通过，说明 SRS 复习策略有效

## 今日不足
- 换元积分还是容易忘回代（2次同样错误）
- 学习时段太晚（22:15），注意力下降导致计算粗心

## Agent 观察
郑俊林今天在无穷小比较上有明显进步。但换元积分出现了重复错误模式（忘回代），
明天应该在练习中加入"检查回代"的提示。另外他的学习时间偏晚，建议明早提醒。

## 明天建议
1. 换元积分专项 5 题（重点：回代检查）
2. 高阶导数 3 题（最近没练）
3. 有精力的话，开始定积分入门
```

---

## 七、实施路线图

### Phase 1：用户 Vault 底座 + Skill 路由 + 模型路由（~48h + 12h缓冲 = 60h）

**目标**：每个用户拥有完整的文件系统 + Agent 拥有 Skill 和模型路由能力 + 冷启动引导 + 上下文管理。

**数据库改动**：零。所有用户数据集都在文件系统里。

#### Sprint 1：Vault 底座 + 安全基础（~18h）

**后端改动**：
- `app/services/vault_manager.py`：管理用户 vault 的创建、读取、写入
  - 🔒 **文件写入锁（跨平台）**：Linux 使用 `fcntl.flock`，Windows 使用 `msvcrt.locking` + `.lock` 文件 fallback。所有 vault 写操作前获取锁，写入后释放。
  - 📋 `_summary.md` 自动维护：每个 vault 目录下维护 `_summary.md`（≤500字），Agent 日常只读摘要。
  - 💾 **Vault 定时备份**：`cron` 每日凌晨 rsync 整个 `data/users/` 到 `/backup/users/`，保留最近 7 天滚动备份。防止磁盘损坏导致 Agent 记忆丢失。
- `app/services/agent_context.py`：Context Budget Manager
- `app/services/memory_writer.py`：记忆权重 + 周归档
- `app/middleware/quota.py`：存储用量监控
- 🧙 **Onboarding Wizard**：3 步弹窗引导

**Onboarding Wizard（3步入门）**：
```
Step 1：你最近在学什么？
  → [输入框：如"高等数学、线性代数"]
  → 自动创建 knowledge/{科目}/ 目录 + 初始化 mastery.md

Step 2：你的目标是什么？
  → [输入框：如"高数期末90分"]
  → 写入 profile/goals.md

Step 3：你喜欢怎么学？
  → [选择：先看例子再学原理 / 先学原理再做题 / 直接刷题 / 不确定]
  → 写入 profile/preferences.md
```
三步走完，vault 已有基本认知，Agent 第一句话就是个性的。

**验收**：用户注册 → Onboarding → vault 自动创建 → Agent 第一次对话已能说出用户目标和学习偏好。

#### Sprint 2：Skill 路由 + 上下文管理（~15h）

- `app/services/skill_router.py`：Skill 路由引擎
- 6 个 Skill prompt 文件（diagnose / study-plan / explain / exam / report / motivate）
- 🎯 **Skill fallback**：路由匹配失败时不静默降级，而是输出结构化选项："我不确定你想做哪种分析，你想让我帮你：A.诊断薄弱点 B.制定学习计划 C.生成学习报告？"
- 🔁 触发词反馈记录：每周 review 10 条路由日志
- Context Budget Manager 完整实现（reflect 调用也走 Budget 限制）

**验收**：说"帮我看看哪里弱"→ /diagnose。说"帮我看看哪里不行"→ fallback A/B/C。

#### Sprint 3：模型路由 + PDF 解析（~15h）

- `app/services/model_router.py`：模型路由引擎
- 🔖 **API 版本管理**：Phase 1 新接口使用 `/api/v2/` 前缀，旧 `/api/v1/` 保持兼容。每个 Sprint 的 API 变更向后兼容，支持独立回滚。
- 设置页新增可选模型 Key（豆包/千问/Kimi）
- 降级策略：缺 Key → PyMuPDF 文本提取 → DeepSeek
- 📄 **PDF 解析**：>20MB 异步处理 + 进度反馈。小文件同步解析。

**验收**：配 Kimi Key → PDF 多模态分析。没配 → 文本提取。大 PDF → "正在解析，预计 2 分钟"。

#### 缓冲与调优（~12h）

- 🔄 **数据迁移**：现有 SQLite 数据（practice_sessions、wrong_book）导出到 vault 文件系统。迁移脚本 + 验证。
- 🔙 **回滚测试**：每个 Sprint 独立回滚验证。
- 边界情况、bug 修复、Skill 触发词调优

**核心 API**：
- 现有 AI 助教 API 在 `_build_context()` 里改用 vault 读取 + skill 路由 + 模型路由 + Context Budget
- `POST /api/v1/agent/reflect` — 练习结束后 Agent 反思并更新记忆

**Phase 1 总验收**：
> 用户注册 → Onboarding → vault 有认知 → 做一轮练习 → mastery.md 更新 → 说"帮我分析薄弱点" → /diagnose → 诊断报告 → 上传 PDF → Kimi多模态分析 → 所有文件写入带锁保护 → 上下文不超预算。

### Phase 2：Agent 自学习闭环（~20h）

**目标**：Agent 能根据练习数据自动更新认知文件，产生"越来越了解学生"的效果。

**核心改动**：
- `POST /api/v1/agent/reflect` 端点的完整实现
- Agent 在每次练习后自动：
  1. 对比新旧 mastery.md → 发现趋势
  2. 更新 wrong-book.md → 归类错误模式
  3. 写 journal/今日.md → 总结今日
  4. 如有新认知 → 追加 .agent/memory.md
- 每日凌晨自动生成今日学习建议（`journal/` 下）

**自学习 Prompt 模板**：

```
你是三一学习 Agent 的反思模块。请基于以下数据更新用户记忆文件。

=== 本轮练习 ===
{session_file 内容}

=== 当前掌握度 ===
{mastery.md 内容}

=== 当前错题汇总 ===
{wrong-book.md 内容}

请输出以下更新：
1. mastery.md 中需要修改的行（知识点、新掌握度、新状态）
2. wrong-book.md 中需要新增或更新的条目
3. 今日日志追加内容（最多200字）
4. 如果有关于用户的重要新认知，追加到 .agent/memory.md

输出格式：JSON，每个部分的 key 对应要更新的文件路径。
```

**验收**：
> 用户连续使用 3 天 → Agent 在第三天打开时能准确说出"你前天错了换元积分，昨天又错了同一类型，今天建议换个讲法"。

### Phase 3：RAG 知识库集成（~15h）

**目标**：Agent 能检索用户上传的教材和笔记，在出题和讲解时引用原文。

**改动**：
- 文件上传存到 `materials/`
- PDF 解析（`PyMuPDF`）→ 存为同名 `.md`
- 可选：接入 Chroma 做向量检索（轻量，内存友好）
- Agent 工具：`SEARCH_MATERIALS` — 搜索用户资料中的相关内容

**验收**：
> 用户上传"老师期末复习重点.pdf" → Agent 在推荐练习时说"根据老师标注的重点，第4章积分的权重占30%，建议优先复习"。

### Phase 4：高级 Agent 能力（~30h，可选）

- 子 Agent 拆分（规划 / 出题 / 讲解 / 复习 四个专用 Agent）
- 自适应难度曲线（根据连续表现自动调整）
- 学习报告生成（周报、月报、学期总结）
- 同伴比较（匿名化，"同专业同学平均掌握了 65%，你目前 72%"）

### Phase 5：开源作品化（~10h）

- 清理代码、写 README、画架构图
- Docker 一键部署
- 示例 vault（预填好的 demo 学生数据）
- 录一个 3 分钟 Demo 视频

---

## 八、技术栈与约束

### 不做的事

- ❌ 不引入新的重型数据库（用户数据集全靠文件系统）
- ❌ 不本地跑模型（全部调 API）
- ❌ 不过早做多 Agent（Phase 4 再说）
- ❌ 不做实时向量检索（Phase 3 可选，先做关键词匹配也行）

### 要做的事

- ✅ 文件系统即数据库（JSON/MD/YAML 作为数据载体）
- ✅ Agent 上下文组装器（文件 → prompt 的管道）
- ✅ 磁盘配额监控（软限制，接近 1GB 时提醒）
- ✅ Agent 反思循环（练习后自动更新记忆）
- ✅ 模板化文件生成（mastery.md、journal 等用 Python 模板渲染）

### 服务器压力评估

| 操作 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 读取 vault 文件（~200KB） | 可忽略 | +2MB | — |
| Agent 上下文组装 | 可忽略 | +5MB | — |
| DeepSeek API 调用 | 网络等待 | 可忽略 | — |
| 写入 session 文件（~3KB） | 可忽略 | 可忽略 | +3KB |
| PDF 解析（10MB PDF） | 峰值 50% | +100MB | — |
| Chroma 向量检索（可选） | 轻量 | +50MB | +100MB |

**结论**：2C2G 完全够。瓶颈在 DeepSeek API 延迟，不在服务器。

---

## 九、实施优先级

| 阶段 | 工时 | 交付物 | 优先级 |
|------|------|--------|--------|
| **Phase 1** | 60h (48h+12h缓冲) | vault底座 + 文件锁(跨平台) + 备份 + ContextBudget + Onboarding + Skill路由(6个+fallback) + 模型路由(一主多辅) + API版本(/v2/) + 数据迁移 + Sprint回滚 | 🔴 立即 |
| **Phase 2** | 26h (20h+6h缓冲) | 自学习闭环 + 记忆权重归档 + 每日建议 | 🔴 立即 |
| Phase 3 | 15h | RAG 资料检索 | 🟡 1个月后 |
| Phase 4 | 30h | 多 Agent + 自适应 | 🟢 可选 |
| Phase 5 | 10h | 开源包装 | ⚪ 长期 |

**Phase 1+2 合计 45h**，完成后的效果：

> 每次打开网站，Agent 说出的第一句话就已经认识你了——知道你的目标、薄弱点、昨天学了什么、今天该练什么。你说"帮我分析弱点"→ Agent 路由到 `/diagnose` 出诊断报告。你上传 PDF → Agent 用你的 Kimi/豆包 Key 做多模态分析。做到这一步，就是一个完整的 AI 学习伙伴。

---

## 十、和 Claude Code 的对标

| Claude Code | 三一学习 Agent |
|-------------|---------------|
| `CLAUDE.md` → Agent 行为准则 | `.agent/system.md` → Agent 身份和行为准则 |
| `MEMORY.md` → 自动记忆 | `.agent/memory.md` → 对学生的长期认知 |
| `/deep-research`, `/code-review` 等 Skills | `.agent/skills/diagnose.md`, `study-plan.md` 等 6 个 Skill |
| Agent Cards → 子 Agent | Phase 4 的规划/出题/讲解/复习 Agent |
| Blackboard → 任务协作 | （未来多 Agent 间共享上下文） |
| 当前 vault → 用户的工作目录 | `data/users/{id}/` → 学生的完整数据集 |
| 工具调用 → 读写文件、执行命令 | Agent 工具 → 出题、分析、规划、检索 |

**本质相同**：都是 **Markdown 文件 + 系统 prompt + 工具调用 + 记忆更新** 的架构。
三一学习 Agent 只是把"代码助手"换成了"学习助手"，把"项目文件"换成了"学生认知文件"。
