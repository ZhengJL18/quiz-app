# 🏆 高级专家团 · 二轮锐评（P0 修复后复审）

> 日期：2026-07-19  
> 评审对象：三一学习 Agent · P0 修复后版本  
> 模式：Squad(×2) → 互评 → E7α/β 对抗双审 → 调度中枢合成  
> 前序报告：[[POST-IMPLEMENTATION-REVIEW.md]]

---

## 一、P0 修复验证

### Fix 1: Context Budget 接入 ✅ 已生效

`assistant.py` 的 chat/chat_stream 现在调用 `build_agent_context(vault, skill_prompt)`。token 预算管理器正式上线。

但发现一个**继承问题**：`build_agent_context()` 和旧的 `_build_context()` 都在系统 prompt 里注入了数据——导致 **双重注入**。`_build_context` 仍然从 SQLite 读取 subjects/chapters/questions 等元数据，`build_agent_context` 从 vault 读取 profile/knowledge/journal。两者内容有重叠但不完全一致，可能导致 prompt 里出现两份"用户数据"段落。

**建议**：Phase 1 的下一步应该把 `_build_context()` 的数据也迁入 vault，然后删掉这个函数，只保留 `build_agent_context()`。目前双重注入不致命但浪费 ~2K tokens。

### Fix 2: RAG Semaphore ✅ 已生效

`_upload_semaphore = asyncio.Semaphore(2)` 限制并发索引任务 ≤2。DeepSeek Embedding API 的 rate limit 问题解决。

**小问题**：semaphore 没有超时设置。如果某个 embedding 任务卡死（API 挂了但不报错），semaphore 的槽位会永久被占。建议给 `async with _upload_semaphore` 加 `asyncio.wait_for(..., timeout=120)`。

### Fix 3: 每日计划 Loading ✅ 已生效

HomeView 现在显示 "AI 正在为你生成今日学习建议..." 加载态。

**小问题**：如果 API 超时（deepseek 挂了），loading spinner 会转很久。建议加 15 秒超时 + 降级提示。

### Fix 4: VaultManager TTL ✅ 已生效

30 分钟无访问自动清理。2GB 服务器的内存泄露风险已解除。

### Fix 5: 任务状态追踪 ✅ 已生效

`_tasks.json` 记录所有 reflect + RAG 索引任务的状态。现在用户（和开发者）能看到哪些后台任务成功/失败了。

**验证**：`agent.py` reflect 的 `ai_analyzed` 字段从硬编码 `True` 变成了运行时决定的布尔值。

---

## 二、P1 建议逐条评审

### P1-6: streak 语义不一致 🔴 → 升级为 P0

**当前代码**：`adaptive_difficulty.py` 用一个 `streak` 变量同时表示"连对次数"和"连错次数"——正值是连对，负值是连错。判断阈值也不同（连对3次升、连错2次降）。

**问题案例**：
- 用户对3次 → streak=3 → 升级 ✅
- 用户错1次 → streak=-1
- 用户再对1次 → streak=1（从-1变成1，但应该从头计数！）
- 用户再对2次 → streak=3 → 错误地升级了（实际上只连对了2次就被"中间那一次错"打断）

**修复**：`correct_streak` 和 `wrong_streak` 分开计数，对错切换时对方归零。2行代码，0.5h。

### P1-7: Skill 假阳性 🟡 快速可修

"我不需要计划"会匹配到 `/study-plan`。加黑名单：

```python
def route_skill(user_message: str):
    msg = user_message.lower()
    # Skip if message starts with negation
    negations = ["不需要", "不是", "不要", "不想", "不用", "别"]
    for neg in negations:
        if msg.startswith(neg):
            return None, None
    # ... existing matching logic
```

0.5h，效果立竿见影。

### P1-8: 行为数据未被利用 🟡 保留建议

Journal 目前是 AI 写的自然语言，缺少结构化数据（每题用时、session 总时长）。这个需要改 memory_writer.py 的模板，约 2h。**建议 Phase 4.1 做。**

### P1-9: Agent 自主性 🟡 保留建议

48h 未登录 → 微信桥推送。但这个需要改微信桥代码，不在 quiz-app 范围内。**建议下次微信桥升级时一起做。**

### P1-10: 错误消息语言 🟡 快速可修

`client.py` 用英文 "DeepSeek API key is required"，其他地方用中文。全局统一改中文。1h。**今天就能做。**

### P1-11: Skill prompt 质量不均 🟡 保留建议

`exam` prompt 150 字太短，生成的模拟考质量不稳。建议补到 300+ 字。1h，但需要实际测试调优。**建议积累两周用户反馈后再改。**

---

## 三轮 Squad 评审（聚焦新增问题）

### E8 🐛 排错专家 · 新增评审

**发现 1**：`agent_context.py` 的 `build_agent_context()` 当 vault 为空（新用户刚 onboard 但还没做过练习）时，`_get_recent_journal` 返回空列表，`_filter_memory` 遇到空字符串返回空字符串，最终 context 里只有 system.md + profile 三行 + knowledge index 一行。**总共不到 500 tokens 的系统 prompt**——这意味着 Agent 在早期使用中是"裸奔"的，没有任何学生数据可以个性化。

**建议**：在 `build_agent_context` 开头加一个检查：如果总 token 数 < 2000，在 system prompt 末尾加一段"当前认知不足"提示，鼓励 Agent 主动问学生更多问题来建立认知。

**发现 2**：`practice.py` 的 `pure_practice` 在自适应难度中——如果用户是新章节第一次刷题，`get_adaptive_prompt_hint` 返回默认的"中等偏易"提示。但如果用户在其他章节已经是 difficulty 5 的水平，新章节应该从几开始？当前逻辑是"每章节独立开始"。更合理的是：新章节的初始难度 = 其他章节的平均难度。**实现只需 3 行 SQL/JSON 查询。**

**发现 3**：`assistant.py` 的 `SEARCH_MATERIALS` 工具返回值里包含 RAG 搜索结果，但 Agent 拿到结果后**没有在回复中标注来源**。比如 Agent 说"积分应用是重点"，但用户不知道这是从自己上传的"老师重点.pdf"里来的，还是 Agent 瞎编的。**需要在 skill_router 的 prompt 中要求 Agent 引用来源。**

### E12 🎯 管理学大师 · 新增评审

**发现 1**：产品缺少"啊哈时刻"。当前的使用路径是：注册 → onboarding → 看到章节列表 → 点一课一练 → 做题。**这和其他刷题 App 没区别**。Agent 的价值（认识学生、个性化建议）要在**第 2-3 天**才显现——但大部分用户会在第一天流失。

**建议**：在 onboarding 完成后，**立即**展示一次 Agent 的"预判"——比如 "根据你填的高数目标，我猜你接下来需要在极限和积分上花时间。要不要现在就来 3 道题？" 这是 Agent 的"第一句话"，必须是即时的、有价值的。可以用 `onboard` 的返回值触发一次即时 `daily-plan` 简版生成。

**发现 2**：用户对 Agent 的信任建立需要"小胜利"。当前 Agent 的 reflect 写了很多文件，但用户**看不到 Agent 在后台做了什么**。用户只看到"练习完成了"——他不知道 Agent 刚刚分析了错误模式、更新了记忆、写了日志。

**建议**：在练习完成页面（`phase === 'done'`）加一个折叠区 "Agent 刚刚做了什么"，展开后显示 reflect 的 `_tasks.json` 摘要——"分析了 3 道题的答题模式 / 发现你可能在换元后忘回代 / 已更新学习日志"。让 Agent 的工作**可见**，用户才会信任它。

---

## 二轮对抗双审

### E7-α 复审

**P0 修复验证**：5 项全部生效。Context Budget 接入是最大的改进——从死代码变成了实际运行。

**新发现**：
- `agent_context.py` 的 `estimate_tokens()` 用 `'一' <= c <= '鿿'` 检测中文——这个范围包含了日文假名、韩文等非中文字符。虽然不影响功能（多算几个 token 只是更保守），但语义不准。建议用 `'一' <= c <= '鿿'`。
- `vault_manager.py` 的 TTL 清理在每次 `get_vault()` 时执行，如果同时有 100 个活跃用户，每次清理要遍历 100 个条目——O(n) 的清理在 getter 里不是最佳实践。建议改为惰性清理：`if len(_managers) > 50: purge_expired()`。

### E7-β 复审

**P0 修复验证**：前端 loading 状态改进明显。"AI 正在为你生成..." 这句话本身就有品牌价值——它告诉用户"有 AI 在工作"。

**新发现**：
- `HomeView.vue` 的 `loadDailyPlan` 在 catch 块里没有 set `dailyPlanLoading = false`——如果 fetch 本身抛异常（比如网络断开），loading 永远不会停止。虽然加了 `finally`，但 `finally` 在 `catch` 之后执行... 让我再确认一下。实际上 `finally` 覆盖了 `catch`，但这意味着即使抛异常 loading 也会停——正确。
- 确认：`finally { dailyPlanLoading.value = false }` 是正确的。但 `dailyPlanLoading` 的初始值 `false` 意味着：用户第一次打开时看到的是一个**空白卡片**，然后突然变成 loading spinner，然后再变成文字。体验跳跃了两次。建议 `dailyPlanLoading` 初始值设 `true`，打开即显示 spinner。

---

## 调度中枢 · 最终合成

### 二轮评分

| 维度 | 一轮 | 二轮 | 变化 |
|------|------|------|------|
| 代码质量 | 7.0 | 7.5 | +0.5（TTL + semaphore） |
| 架构完整性 | 7.0 | 7.5 | +0.5（Context Budget 激活） |
| 数据效能 | 6.0 | 6.5 | +0.5（_tasks.json 可观测） |
| 用户体验 | 6.0 | 7.0 | +1.0（loading状态） |
| 安全性 | 7.0 | 7.5 | +0.5（RAG并发控制） |
| 可维护性 | 7.0 | 7.5 | +0.5（任务追踪） |
| **综合** | **6.7** | **7.2** | **+0.5** |

### 新增修改建议

| # | 严重度 | 问题 | 修复 | 工时 |
|---|--------|------|------|------|
| 12 | 🔴 | streak 语义 bug（中间一次错打断连对计数） | correct_streak/wrong_streak 分开 | 0.5h |
| 13 | 🔴 | 新用户 vault 空→Agent 裸奔（<500 tokens prompt） | build_agent_context 加"认知不足"提示 | 1h |
| 14 | 🔴 | Onboarding 后无"Agent 第一句话" | onboard 返回时触发即时 daily-plan | 2h |
| 15 | 🟡 | 每日计划 loading 初始值应设 true | 首页打开即显 spinner | 0.1h |
| 16 | 🟡 | Skill 假阳性（否定词） | 黑名单 | 0.5h |
| 17 | 🟡 | 新章节难度应从其他章节继承 | get_difficulty 新章节 = avg(其他) | 0.5h |
| 18 | 🟡 | RAG 结果不标注来源 | skill prompt 加"引用来源"要求 | 0.5h |
| 19 | 🟡 | 用户看不到 Agent 后台工作 | 练习完成页展示 _tasks.json 摘要 | 2h |
| 20 | 🟡 | 错误消息中英文混杂 | 全局统一中文 | 1h |

### 最终评价

> P0 修复后评分从 6.7 → 7.2。最大的剩余问题是 **Agent 的价值在 Day 1 不可见**——用户注册后看到的是一个普通的刷题界面，Agent 的"认识你"要到 Day 2-3 才体现。🔴 建议 14（Onboarding 后即时"预判"）是解决这个问题的关键——让 Agent 的第一句话就惊艳用户。
>
> 修完 3 个新 P0（合计 3.5h）后，预计评分升至 **7.5/10** ——一个朋友愿意用、且能感受到 Agent "认识自己"的 Beta 产品。
