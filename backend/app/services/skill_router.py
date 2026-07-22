"""Skill Router — matches user intent to specialized Agent skills.

Each skill has:
- A prompt file (loaded from the vault's .agent/skills/ directory)
- A set of trigger keywords
- A set of required tools

On match failure, returns a structured fallback (A/B/C options) instead of silent degradation.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("uvicorn.error")

# ── Skill Registry ──

SKILL_REGISTRY = {
    "diagnose": {
        "name": "薄弱点诊断",
        "triggers": [
            "分析弱点", "诊断", "薄弱点", "哪里差", "水平如何",
            "帮我看看", "看看哪里", "哪里弱", "掌握度", "哪里不行",
            "分析一下", "帮我分析", "学得怎么样", "哪里不好",
        ],
        "tools": ["GET_PROFILE", "GET_KNOWLEDGE", "GET_WRONG_BOOK", "GET_RECENT_SESSIONS"],
        "description": "深度分析你的薄弱点，给出针对性改进方案",
    },
    "study-plan": {
        "name": "学习计划",
        "triggers": [
            "计划", "安排", "复习计划", "期末", "备考", "时间表",
            "怎么复习", "怎么安排", "规划", "日程", "接下来",
            "今天学什么", "明天", "这周", "下周",
        ],
        "tools": ["GET_PROFILE", "GET_KNOWLEDGE", "GET_SRS", "GET_GOALS"],
        "description": "根据你的目标和薄弱点，制定可执行的学习计划",
    },
    "explain": {
        "name": "知识点讲解",
        "triggers": [
            "解释", "什么意思", "讲讲", "什么是", "帮我理解",
            "不懂", "不明白", "为什么", "原理", "定义",
            "概念", "推导", "证明",
        ],
        "tools": ["GET_KNOWLEDGE", "SEARCH_MATERIALS"],
        "description": "用你喜欢的方式深度讲解一个概念或定理",
    },
    "exam": {
        "name": "模拟考试",
        "triggers": [
            "模拟考", "考试模拟", "来一场", "测试一下",
            "模拟", "仿真", "摸底", "考一下",
        ],
        "tools": ["GET_KNOWLEDGE", "GENERATE_QUESTIONS", "GRADE_ANSWER"],
        "description": "生成一套完整模拟考卷，考完给你分析和分数",
    },
    "report": {
        "name": "学习报告",
        "triggers": [
            "报告", "总结", "周报", "月报", "最近学得", "进步",
            "回顾", "复盘", "这段时间", "这一周", "这个月",
        ],
        "tools": ["GET_PROFILE", "GET_KNOWLEDGE", "GET_JOURNAL"],
        "description": "生成你的学习周报/月报，包含数据分析和建议",
    },
    "motivate": {
        "name": "学习激励",
        "triggers": [
            "不想学", "好累", "坚持不下", "放弃", "没动力",
            "焦虑", "学不动", "太难了", "烦", "崩溃",
            "鼓励", "打气", "加油",
        ],
        "tools": ["GET_PROFILE", "GET_JOURNAL", "GET_PROGRESS"],
        "description": "在你疲惫或焦虑时，给你鼓励和具体的小步骤",
    },
}


def route_skill(user_message: str) -> tuple[str | None, str | None]:
    """Match user message to a skill.

    Returns:
        (skill_name, matched_trigger) if matched, (None, None) if not.
    """
    msg = user_message.lower()
    for skill_name, config in SKILL_REGISTRY.items():
        for trigger in config["triggers"]:
            if trigger.lower() in msg:
                # Log the match for feedback loop
                logger.info(f"SkillRouter: matched '{skill_name}' via trigger '{trigger}' for message: {user_message[:80]}")
                return skill_name, trigger
    return None, None


def get_skill_prompt(skill_name: str, vault_root: Path) -> str | None:
    """Load a skill's prompt file from the vault's .agent/skills/ directory."""
    prompt_path = vault_root / ".agent" / "skills" / f"{skill_name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8", errors="replace")
    # Fallback: load built-in prompt
    builtin = _get_builtin_skill_prompt(skill_name)
    if builtin:
        # Cache it to the vault for future use
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(builtin, encoding="utf-8")
    return builtin


def get_fallback_message() -> str:
    """When no skill matches, return structured A/B/C options."""
    options = [
        ("diagnose", SKILL_REGISTRY["diagnose"]["description"]),
        ("study-plan", SKILL_REGISTRY["study-plan"]["description"]),
        ("explain", SKILL_REGISTRY["explain"]["description"]),
    ]
    lines = ["我不确定你想让我做什么，你可以试试：", ""]
    letters = "ABC"
    for i, (name, desc) in enumerate(options):
        lines.append(f"**{letters[i]}. {desc}** — 说「{SKILL_REGISTRY[name]['triggers'][0]}」即可")
    return "\n".join(lines)


def log_routing(user_message: str, matched_skill: str | None, user_followed_up: bool = False):
    """Log routing decisions for weekly review and trigger tuning."""
    entry = {
        "message": user_message[:200],
        "matched_skill": matched_skill,
        "followed_up": user_followed_up,
    }
    # Append to a simple JSONL log in the vault root
    log_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "skill_routing_log.jsonl"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Built-in skill prompts (used when vault doesn't have them yet) ──

def _get_builtin_skill_prompt(skill_name: str) -> str | None:
    prompts = {
        "diagnose": _DIAGNOSE_PROMPT,
        "study-plan": _STUDY_PLAN_PROMPT,
        "explain": _EXPLAIN_PROMPT,
        "exam": _EXAM_PROMPT,
        "report": _REPORT_PROMPT,
        "motivate": _MOTIVATE_PROMPT,
    }
    return prompts.get(skill_name)


_DIAGNOSE_PROMPT = """---
skill: diagnose
trigger: 分析弱点 | 诊断 | 薄弱点 | 哪里差 | 水平如何
tools: [GET_PROFILE, GET_KNOWLEDGE, GET_WRONG_BOOK, GET_RECENT_SESSIONS]
---

# 学习诊断 Agent

你是一个学习诊断专家。深度分析学生的薄弱点，找出根本原因，给出可执行的改进方案。

## 输出格式

### 掌握度总览
[列出各科目的掌握度]

### 需要立即关注的薄弱点（Top 3）
1. **[知识点]** — 掌握度 XX%
   - 错误模式：[具体描述]
   - 根本原因：[概念不清？练得少？记错公式？]
   - 改进方案：[明天练什么、怎么练、练几次]
   - 预计恢复：[X天/Y次练习后可达 Z%]

### 建议的近期行动计划
[具体到每天做什么]

## 原则
- 不要只说"多练练"，要说具体练什么
- 先肯定进步，再指出不足
"""

_STUDY_PLAN_PROMPT = """---
skill: study-plan
trigger: 计划 | 安排 | 复习计划 | 期末 | 备考
tools: [GET_PROFILE, GET_KNOWLEDGE, GET_SRS, GET_GOALS]
---

# 学习规划 Agent

根据学生目标、掌握度、可用时间，生成可执行的多日学习计划。

## 输出格式

### 目标回顾
[学生的目标]

### 每日安排
- **第1天**: 复习(SRS排期) + 主攻(最弱知识点·10题) + 辅练(次弱·5题) · 预计40分钟
- **第2天**: ...

### 风险提示
- 连续2天正确率<40% → 自动降级
- 第4天总进度<50% → 缩减计划
"""

_EXPLAIN_PROMPT = """---
skill: explain
trigger: 解释 | 什么意思 | 讲讲 | 什么是 | 帮我理解
tools: [GET_KNOWLEDGE, SEARCH_MATERIALS]
---

# 知识点讲解 Agent

用学生喜欢的方式深度讲解概念或定理。

## 输出
1. 一句话定义
2. 直观理解（类比/图示/例子）
3. 严格定义（如有公式用 LaTeX）
4. 经典例题
5. 常见误区
"""

_EXAM_PROMPT = """---
skill: exam
trigger: 模拟考 | 考试模拟 | 来一场 | 测试一下
tools: [GET_KNOWLEDGE, GENERATE_QUESTIONS, GRADE_ANSWER]
---

# 模拟考试 Agent

生成一套完整模拟考卷。

## 流程
1. 读取知识掌握度 → 按掌握度比例分配题目
2. 生成考卷（单选用数字索引，填空/计算自判）
3. 考完 → 自动评分 → 薄弱点分析
"""

_REPORT_PROMPT = """---
skill: report
trigger: 报告 | 总结 | 周报 | 月报 | 最近学得
tools: [GET_PROFILE, GET_KNOWLEDGE, GET_JOURNAL]
---

# 学习报告 Agent

生成学习周报/月报。

## 格式
- 本周数据（练习次数、题数、正确率）
- 对比上周（进步/退步TOP3）
- 本周亮点（从journal提取）
- 下周展望
"""

_MOTIVATE_PROMPT = """---
skill: motivate
trigger: 不想学 | 好累 | 坚持不下 | 放弃 | 没动力
tools: [GET_PROFILE, GET_JOURNAL, GET_PROGRESS]
---

# 学习激励 Agent

在学生疲惫时给鼓励和具体小步骤。

## 原则
- 先共情："我理解，数学确实累"
- 再提醒："但你上周极限从30%→60%，进步很大"
- 给最小步骤："今天就做1道题，做完就休息"
- 不讲大道理，给具体小行动
"""
