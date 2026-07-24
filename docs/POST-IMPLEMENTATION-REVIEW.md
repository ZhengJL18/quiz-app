# 🏆 高级专家团 · 系统实现锐评

> 日期：2026-07-19  
> 评审对象：三一学习 Agent · Phase 1-4 完整实现（56文件、7744行代码）  
> 模式：Squad(×3) → 互评 → E7α/β对抗双审 → 调度中枢合成

---

## Round 1：Squad 分裂 · 三视角独立评审

### E2 💻 代码工匠 · 评审

**优点：**

**1. 文件系统即数据库的决策在代码层面执行得很好。** `vault_manager.py` 的路径遍历防护（`resolve()` + `startswith` 检查）是安全基线，很多人会漏。跨平台文件锁（Linux `fcntl` + Windows `.lock` 文件）覆盖了主要场景。`_summary.md` 自动维护的逻辑简洁高效——不是每次写都重建，只在 write/append 时触发。

**2. Service 层职责分隔清晰。** `vault_manager` 管文件、`agent_context` 管 prompt 组装、`memory_writer` 管记忆更新、`skill_router` 管意图匹配、`model_router` 管 API 分发、`adaptive_difficulty` 管难度调整、`rag_engine` 管向量检索——7 个 service 各司其职，没有循环依赖。这在快速迭代的项目里不容易做到。

**不足：**

**1. 全局可变状态是定时炸弹。** `vault_manager.py` 第 163 行 `_managers: dict[int, VaultManager] = {}` 是一个模块级字典，存储了所有用户的 VaultManager 实例。在单 worker 下没问题，但如果未来加 worker —— 比如 `uvicorn --workers 4` —— 每个 worker 独立的内存空间意味着同一个用户的 VaultManager 会在多个 worker 中被创建，锁机制会被绕过。而且这个字典**从不清理**——一个用户如果半年不登录，VaultManager 仍然占着内存。

**2. 异常处理策略不统一。** `agent.py` 的 reflect 里有两层 try-except：外层捕获所有异常静默回退（"return basic result"），内层捕获 AI 分析异常后只写简单日志。这导致**AI 分析失败时用户完全不知道**——他们以为 reflect 成功了，但实际 memory.md 没有更新、journal 只写了一行模板。应该在 reflect 的 response 里加一个 `ai_analyzed: true/false` 字段（代码里已经有了但前端没读），并在 AI 失败时至少记录到 error log。

**3. Chroma 索引失败静默吞没。** `agent.py` 里 `_index_material_bg` 是一个 fire-and-forget 的 background task。如果 DeepSeek Embedding API 挂了、或者 Chroma 写入失败——用户上传了 PDF 但搜索不到，而且没有任何提示说"索引失败了"。

**两条建议：**

> **🔴 建议 1**：`vault_manager.py` 的 `_managers` 加 TTL 过期机制。每次 `get_vault()` 时记录时间戳，超过 30 分钟未访问的自动从字典移除。Phase 1 不需要多 worker，但加 5 行代码防未来。

> **🔴 建议 2**：所有 fire-and-forget 任务（RAG 索引、AI reflect 分析）写入 vault 的一个 `_tasks.json` 文件，记录任务状态（pending/completed/failed）。前端展示"索引中..."或"分析中..."，失败了用户能看到。

---

### E5 📊 分析参谋 · 评审

**优点：**

**1. 自学习闭环的数据流设计精良。** `reflect` 端点收集练习数据 → 调 DeepSeek 分析错误模式+趋势+新认知 → 写入 journal/memory/mastery。这个数据链路上每一步都有可观测的产出（vault 文件），便于调试和验证。

**2. 自适应难度的规则设计务实。** 不追求复杂的贝叶斯模型或 ML 算法，用最简单的"连对3次升、连错2次降"规则。对于 Beta 阶段足够了——重要的是规则**可理解**（用户能直觉理解"为什么题目变难了"），而非精确。

**不足：**

**1. 用户行为数据未被充分利用。** 系统记录了练习时长（`time_spent_seconds`）、答题时间分布、每日学习时段——但这些数据从未被分析。Journal 只说"今天做了3道题"，但不知道"用户花了 45 分钟只做 3 道题"意味着什么（可能太难了、可能在走神、可能被打断了）。这些行为数据是诊断学习效率的关键。

**2. "Agent 认识学生"的验证指标缺失。** Phase 1-4 建立了一套认知文件系统，但没有定义"多深才算认识"。建议加一个简单的 self-check：每次对话后，Agent 在 memory.md 里追加一行 `confidence: 0.7`——表示"我对这个学生的理解置信度"。如果连续 10 次对话 confidence 都没涨，说明 Agent 没有在"学习"。

**两条建议：**

> **🔴 建议 3**：Journal 里增加行为数据摘要。不只是"做了3题，对2题"，而是"做了3题，平均每题4.2分钟，总时长12.6分钟，比上周同一章节慢了30%"。Agent 在生成每日计划时读这些数据，能发现"你可能需要降低难度"或"你可能注意力不集中"。

> **🟡 建议 4**：加一个 `GET /agent/student-insight` 端点，返回 Agent 对学生的"理解摘要"——从 memory.md 中提取最近的 high-weight 条目 + confidence 分数 + 最常出现的薄弱点关键词。这是给开发者看的"Agent 眼睛里的学生画像" Dashboard。

---

### E11 🏗️ 架构顾问 · 评审

**优点：**

**1. Vault-as-Brain 架构实现得比设计方案更好。** 原方案只设计了 profile/knowledge/practice/journal 四层，实现时自然地衍生出了 `difficulty_state.json`、`skill_routing_log.jsonl`、`_tasks.json`（待实现）——这些衍生文件证明了文件系统架构的**自生长能力**。如果用数据库，每加一种新数据就要 ALTER TABLE + migration，但文件系统里就是一个新文件，零摩擦。

**2. Skill × Model 双路由解耦经受住了实现的考验。** Skill 路由在 `assistant.py` 的 chat/chat_stream 两个端点里只增加了 5 行代码，Model 路由完全独立在 `model_router.py` 里。两者之间唯一的耦合点是 `agent.py` 的 upload-material 端点——先走 Model 路由（选多模态 AI 处理文件），再走文件系统存储。这个耦合是合理的（数据流从 Model → Vault，不是随意交叉）。

**不足：**

**1. Context Budget Manager 形同虚设。** `agent_context.py` 定义了完整的 token 预算分配器，但**没有任何一个端点调用它**。`assistant.py` 的 chat/chat_stream 仍然在用旧的 `_build_context()`，完全不经过 `build_agent_context()`。这就导致：Skill 路由加载了 skill prompt，但 vault 数据仍然全部注入（通过 `_build_context`），Context Budget 从未生效。这是一条死代码路径。

**2. Agent "自主决策"只是一个 prompt 指令，没有代码支撑。** system.md 写了"主动推动学习"，但 Agent 实际能"主动"做的事情只有 `reflect`（被动触发）和 `daily-plan`（用户打开首页触发）。Agent 不能主动推送通知、不能主动创建复习任务、不能在用户静默 3 天后主动发消息。prompt 里的"自主决策"在当前的 event-driven 架构下是无法实现的——Agent 每次对话都是 request-response，不存在持续运行的"Agent 进程"。

**两条建议：**

> **🔴 建议 5**：立即修复 Context Budget Manager 的集成。在 `assistant.py` 的 chat/chat_stream 中，用 `build_agent_context(vault, skill_prompt)` 替换现有的 `_build_context()` + 手动 skill 注入。这是 Phase 1 就设计好的功能，不应该停留在死代码状态。

> **🟡 建议 6**：给"Agent 自主性"一个现实的 MVP 实现：在用户登录时，`GET /agent/vault` 检查 journal 目录——如果最近一次 .md 超过 48 小时，返回 `inactive: true`，前端弹一条"你已经 2 天没学习了，要不要来做 3 道题？"。这不是真正的"Agent 自主"，但在不需要后台进程的前提下，实现了"Agent 主动触达"的错觉——对 Beta 够用了。

---

## Round 1：相互评价

### [E2 → E5] 互评

1. 事实准确 [通过]：E5 对数据流的分析准确，reflect 确实缺少行为数据。
2. 逻辑完整 [通过]：建议 3（journal 加行为数据）和 E2 的建议 2（fire-and-forget 任务状态）互补——一个关注用户侧数据，一个关注系统侧数据。
3. 互补性 [E2 补充]：E5 提到 Confidence Score 但没说放在哪里。建议放在 `.agent/memory.md` 的 frontmatter 里：`--- confidence: 0.7 ---`，这样 Agent 每次读 memory 时都能看到自己的"自信程度"。

### [E2 → E11] 互评

1. 事实准确 [存疑]：E11 说 Context Budget Manager 是"死代码"。让我再确认——`agent_context.py` 的 `build_agent_context()` 确实只在文件内部定义，没有被任何 import 使用。E11 的判断成立。
2. 逻辑完整 [通过]：E11 指出的"Agent 自主性 = prompt 指令无代码支撑"是一针见血。这是设计方案和实现方案之间最严重的 gap。
3. 互补性 [E2 补充]：E11 的建议 6（48h 未登录提示）技术上是一个 cron job 而非 API 检查。建议用最简单的方式：cron 每天 8:00 检查所有活跃用户的 journal → 如果有超过 48h 的空窗 → 调 DeepSeek 生成一条推送消息 → 存到 vault → 前端下次登录时展示。

### [E5 → E2] 互评

1. 事实准确 [通过]：E2 发现的两个代码问题（全局 _managers 字典泄露、异常静默吞没）都是真实存在的。
2. 逻辑完整 [通过]：建议 1（TTL 过期）和建议 2（任务状态追踪）优先级正确。
3. 互补性 [E5 补充]：E2 的建议 2（_tasks.json）可以同时用于 E5 关注的"行为数据"——在 task 完成时记录耗时，长期积累就是系统性能基线。

### [E5 → E11] 互评

1. 事实准确 [通过]：E11 对架构的分析客观。Context Budget 确实是死代码。
2. 逻辑完整 [存疑]：E11 说 Agent 不能主动推送——技术上可以，微信桥就在本地运行。但 E11 的判断方向是对的：主动推送需要后台进程，而当前架构没有。微信桥可以作为 Phase 4.5 的"主动 Agent 通道"。
3. 互补性 [E5 补充]：E11 的建议 6（48h 未登录）可以复用现有的微信桥推送——不只是下次登录展示，而是直接发微信消息"你已经2天没学习了"。

### [E11 → E2] 互评

1. 事实准确 [通过]：全局状态和异常处理的批评合理。
2. 逻辑完整 [通过]：E2 的建议偏"防御性编程"，和 E11 的"架构完整性"互补。
3. 互补性 [E11 补充]：E2 提到的多 worker 问题——当前 uvicorn 单 worker 没问题，但建议在 `vault_manager.py` 顶部加一个 `assert` 检测如果有多个 VaultManager 实例访问同一个 user_id 就报警。

### [E11 → E5] 互评

1. 事实准确 [通过]：E5 的"行为数据未被利用"是真问题。Journal 里的 AI 反思太依赖 AI 自己的判断，缺少硬数据支撑。
2. 逻辑完整 [通过]：建议 3（行为数据摘要）实现成本低、收益高。
3. 互补性 [E11 补充]：行为数据不只用于 journal。应该作为"学习效率指标"（每分钟正确率、连续学习时长）单独存储，未来做"学习效率趋势图"。

---

## Round 2：对抗双审

### E7-α · 独立审校（事实 + 逻辑 + 安全）

> ⚠️ 隔离上下文：E7-α 只看到了代码文件，未看到 Round 1 评审。

**代码级审查发现**：

1. 🔴 `agent.py` 第 433 行：`asyncio.create_task(_index_material_bg(...))` —— 如果用户快速上传 10 个文件，会同时触发 10 个 embedding + Chroma 写入任务。DeepSeek Embedding API 有 rate limit，Chroma 的 SQLite 后端在高并发写入时可能锁死。建议加 semaphore（复用 `assistant.py` 的 `_bg_semaphore`）。

2. 🔴 `adaptive_difficulty.py` 第 28 行：`streak` 的语义不一致——正确时 streak 递增（+1），错误时 streak 递减（-1），但"连对3次"和"连错2次"的阈值不同。更清晰的实现：`correct_streak` 和 `wrong_streak` 分开计数，各自独立重置。

3. 🟡 `model_router.py` 第 84 行：`_call_qwen` 的响应解析用的是 `data["output"]["choices"]`，但其他两个 provider 用的是 `data["choices"]`。如果千问 API 的响应格式变了，这条路径会静默失败。建议统一用 OpenAI-compatible 格式（千问的 `/compatible-mode/v1` 路径已经暗示了兼容性）。

4. 🟡 `skill_router.py` 第 41 行：触发词匹配用的是 `if trigger.lower() in msg`——这会把"我不需要计划"匹配到 `/study-plan`（因为"计划"在消息中）。简单的关键词包含匹配会有假阳性。建议加一个黑名单：如果消息以"不要"、"不需要"、"不是"开头且包含触发词，跳过匹配。

**审查结论**：PASS（有条件），🔴 项必须修。

---

### E7-β · 独立审校（表达 + 完整性 + UX）

> ⚠️ 隔离上下文：E7-β 只看到了代码文件，未看到 Round 1 评审。

**表达/一致性审查发现**：

1. 🟡 错误消息语言不统一。`client.py` 用英文（"DeepSeek API key is required"），`practice.py` 用中文（"AI question generation failed"），`agent.py` 混用。用户看到的中英文混杂降低信任感。建议全局统一中文，英文仅保留 error code。

2. 🟡 Skill prompt 文件（`skill_router.py` 的内置 prompt）长度不均匀。`diagnose` 约 500 字但 `exam` 只有 150 字，`explain` 缺少具体的输出格式约束。这会导致不同 Skill 的响应质量差异大。

3. 🟡 `vault_manager.py` 的 `_DEFAULT_SYSTEM_MD` 在第 140 行之后还有内容，但文件末尾没有闭合。如果未来有人在这个字符串后加代码，可能破坏文件结构。建议把长字符串移到独立的 `.md` 资源文件。

4. 🔴 用户从 Onboarding → 首次进入 HomeView，daily-plan 在后台流式生成但**没有任何 loading 状态提示**。用户看到的是一个空白卡片区域然后突然出现文字——体验是"卡顿"而不是"AI在思考"。

**审查结论**：PASS（有条件），建议修 UX 相关项。

---

## Round 2：对抗双审 · 调度中枢裁决

### 双审对比

| 维度 | E7-α（事实+逻辑+安全） | E7-β（表达+UX） | 一致性 |
|------|----------------------|-----------------|--------|
| RAG 并发风险 | 🔴 semaphore 缺失 | — | α 单独发现 |
| streak 语义 | 🔴 逻辑不一致 | — | α 单独发现 |
| Qwen API 兼容 | 🟡 响应格式可能漂移 | — | α 单独发现 |
| Skill 假阳性 | 🟡 否定词误匹配 | — | α 单独发现 |
| 错误消息语言 | — | 🟡 中英文混杂 | β 单独发现 |
| Skill prompt 不均 | — | 🟡 质量差异大 | β 单独发现 |
| 长字符串可维护性 | — | 🟡 建议分离 | β 单独发现 |
| 每日计划 UX | — | 🔴 无 loading 提示 | β 单独发现 |

**裁决：双 PASS（有条件）**。两位审查者完全独立，发现的 8 个问题零重叠——说明审查是真正独立的。🔴 项共 3 个，必须修。

---

## 调度中枢 · 最终合成

### 综合评分

| 维度 | 评分 | 一轮评审后 | 变化 |
|------|------|-----------|------|
| 代码质量 | 7/10 | — | 全局状态泄露、异常静默扣分 |
| 架构完整性 | 7/10 | — | Context Budget 死代码、Agent自主性无支撑 |
| 数据效能 | 6/10 | — | 行为数据未被利用、认知缺乏度量 |
| 安全性 | 7/10 | — | 路径遍历防护好、但 RAG 并发风险 |
| 用户体验 | 6/10 | — | 每日计划无loading、错误消息不统一 |
| 可维护性 | 7/10 | — | Service 分离好、但长字符串嵌入代码 |
| **综合** | **6.7/10** | | Beta 阶段合理，但需要打磨 |

### 修改意见汇总（按优先级）

| # | 严重度 | 来源 | 问题 | 修复 | 工时 |
|---|--------|------|------|------|------|
| 1 | 🔴 | E11 | Context Budget 死代码 | assistant.py 改用 build_agent_context() | 2h |
| 2 | 🔴 | E7-α | RAG 并发无 semaphore | agent.py upload-material 加 _bg_semaphore | 0.5h |
| 3 | 🔴 | E7-β | 每日计划无 loading | HomeView 加 loading spinner | 1h |
| 4 | 🔴 | E2 | 全局 _managers 内存泄露 | 加 TTL 过期机制 | 0.5h |
| 5 | 🔴 | E2 | 异常静默吞没（reflect + RAG索引） | 加 _tasks.json 状态追踪 | 2h |
| 6 | 🟡 | E7-α | streak 语义不一致 | correct_streak / wrong_streak 分开 | 1h |
| 7 | 🟡 | E7-α | Skill 假阳性（否定词匹配） | 黑名单：消息以"不要/不是"开头时跳过 | 0.5h |
| 8 | 🟡 | E5 | 行为数据未被利用 | journal 加每题用时、session 时长 | 2h |
| 9 | 🟡 | E11 | Agent 自主性无代码支撑 | 48h 未登录 → 微信桥推送 | 3h |
| 10 | 🟡 | E7-β | 错误消息语言不统一 | 全局改中文 | 1h |
| 11 | 🟡 | E7-β | Skill prompt 质量不均 | 统一 explain/exam 的 prompt 长度 | 1h |

**🔴 P0 必须修（5项，合计 6h）**
**🟡 P1 建议修（6项，合计 8.5h）**

### 最终评价

> 这套系统在 136h 内实现了从"刷题网站"到"AI 学习 Agent"的跨越——Vault-as-Brain、Skill 路由、RAG、自适应难度、自学习闭环——架构设计水平已经超过大多数本科毕业设计。
>
> 当前 Beta 版的**核心缺陷不是功能缺失，而是打磨不足**。5 个 P0 项全部是"代码写了但没接上"（Context Budget）、"能跑但没兜底"（RAG并发、异常静默）、"功能有但没体验"（loading状态）。这不是架构问题，是典型的技术债——快速迭代的必然产物。
>
> 修完 P0 后综合评分预计升至 **7.5/10**——一个可以交给朋友用的 Beta 产品。

---

*报告由 E2代码工匠 + E5分析参谋 + E11架构顾问 (Squad) + E7α/E7β对抗双审 + 调度中枢合成。*
*2026-07-19 · 🏆 高级专家团模式，2轮循环。*
