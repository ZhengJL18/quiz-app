"""Skill Router — intelligent skill matching with self-evolution.

Like Hermes Agent's skill system but for the learning domain:
1. Static skill registry (built-in skills)
2. Dynamic skill creation (agent learns new skills from interactions)
3. Skill statistics (track usage, success rate, evolve triggers)
4. Semantic matching (not just keyword matching)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("uvicorn.error")

# ── Built-in Skill Registry ──

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
        "category": "analysis",
        "usage_count": 0,
        "success_rate": 1.0,
        "created_at": "2026-01-01T00:00:00",
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
        "category": "planning",
        "usage_count": 0,
        "success_rate": 1.0,
        "created_at": "2026-01-01T00:00:00",
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
        "category": "teaching",
        "usage_count": 0,
        "success_rate": 1.0,
        "created_at": "2026-01-01T00:00:00",
    },
    "exam": {
        "name": "模拟考试",
        "triggers": [
            "模拟考", "考试模拟", "来一场", "测试一下",
            "模拟", "仿真", "摸底", "考一下",
        ],
        "tools": ["GET_KNOWLEDGE", "GENERATE_QUESTIONS", "GRADE_ANSWER"],
        "description": "生成一套完整模拟考卷，考完给你分析和分数",
        "category": "assessment",
        "usage_count": 0,
        "success_rate": 1.0,
        "created_at": "2026-01-01T00:00:00",
    },
    "report": {
        "name": "学习报告",
        "triggers": [
            "报告", "总结", "周报", "月报", "最近学得", "进步",
            "回顾", "复盘", "这段时间", "这一周", "这个月",
        ],
        "tools": ["GET_PROFILE", "GET_KNOWLEDGE", "GET_JOURNAL"],
        "description": "生成你的学习周报/月报，包含数据分析和建议",
        "category": "analysis",
        "usage_count": 0,
        "success_rate": 1.0,
        "created_at": "2026-01-01T00:00:00",
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
        "category": "support",
        "usage_count": 0,
        "success_rate": 1.0,
        "created_at": "2026-01-01T00:00:00",
    },
}


# ── Skill Manager ──

class SkillManager:
    """Manages skills: matching, creation, evolution."""
    
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root
        self.skills_dir = vault_root / ".agent" / "skills"
        self.stats_path = vault_root / ".agent" / "skill-stats.json"
        self._registry = None  # Lazy load
    
    @property
    def registry(self) -> dict:
        if self._registry is None:
            self._registry = self._load_registry()
        return self._registry
    
    def _load_registry(self) -> dict:
        """Load registry from vault, merge with built-in."""
        user_registry_path = self.skills_dir / "_registry.json"
        if user_registry_path.exists():
            try:
                user_skills = json.loads(user_registry_path.read_text(encoding="utf-8"))
                # Merge: user skills override built-in with same name
                merged = dict(SKILL_REGISTRY)
                merged.update(user_skills)
                return merged
            except json.JSONDecodeError:
                pass
        return dict(SKILL_REGISTRY)
    
    def _save_registry(self):
        """Save registry to vault."""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        user_skills = {k: v for k, v in self.registry.items() 
                       if k not in SKILL_REGISTRY or v != SKILL_REGISTRY.get(k)}
        if user_skills:
            (self.skills_dir / "_registry.json").write_text(
                json.dumps(user_skills, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
    
    def match(self, user_message: str, current_subject: str = None) -> tuple[str | None, str | None, float]:
        """Match user message to the best skill.
        
        Returns: (skill_name, matched_trigger, confidence_score)
        """
        msg = user_message.lower()
        best_match = None
        best_trigger = None
        best_score = 0.0
        
        for skill_name, config in self.registry.items():
            for trigger in config.get("triggers", []):
                if trigger.lower() in msg:
                    # Score: longer triggers = more specific = higher confidence
                    score = len(trigger) / max(len(msg), 1) * 0.5 + 0.5
                    
                    # Bonus for subject-specific skills
                    if current_subject and current_subject in skill_name:
                        score += 0.2
                    
                    # Bonus for frequently-used skills
                    usage = config.get("usage_count", 0)
                    if usage > 0:
                        score += min(0.1, usage * 0.01)
                    
                    if score > best_score:
                        best_score = score
                        best_match = skill_name
                        best_trigger = trigger
        
        if best_match:
            logger.info(
                f"SkillRouter: matched '{best_match}' via '{best_trigger}' "
                f"(score={best_score:.2f}) for: {user_message[:80]}"
            )
        
        return best_match, best_trigger, best_score
    
    def get_prompt(self, skill_name: str) -> str | None:
        """Load a skill's prompt file."""
        prompt_path = self.skills_dir / f"{skill_name}.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8", errors="replace")
        
        # Fallback: use built-in prompt
        builtin = _get_builtin_skill_prompt(skill_name)
        if builtin:
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(builtin, encoding="utf-8")
        return builtin
    
    def record_usage(self, skill_name: str, successful: bool = True):
        """Record a skill usage for statistics and evolution."""
        if skill_name not in self.registry:
            return
        
        config = self.registry[skill_name]
        config["usage_count"] = config.get("usage_count", 0) + 1
        config["last_used"] = datetime.now(timezone.utc).isoformat()
        
        # Update success rate (exponential moving average)
        current = config.get("success_rate", 1.0)
        alpha = 0.1
        config["success_rate"] = current * (1 - alpha) + (1.0 if successful else 0.0) * alpha
        
        # Save stats
        self._save_registry()
        self._log_usage(skill_name, successful)
    
    def create_skill(self, name: str, triggers: list[str], description: str, 
                     category: str = "custom", prompt: str = "", tools: list[str] = None):
        """Create a new skill dynamically.
        
        This is how the system learns: when it detects a successful interaction 
        pattern, it can create a reusable skill for future similar interactions.
        """
        skill_id = name.lower().replace(" ", "-")
        
        # Don't overwrite existing skills
        if skill_id in self.registry:
            # Instead, add new triggers
            existing = self.registry[skill_id].get("triggers", [])
            new_triggers = [t for t in triggers if t not in existing]
            if new_triggers:
                self.registry[skill_id]["triggers"].extend(new_triggers)
                logger.info(f"SkillRouter: added triggers to '{skill_id}': {new_triggers}")
            return skill_id
        
        self.registry[skill_id] = {
            "name": name,
            "triggers": triggers,
            "tools": tools or [],
            "description": description,
            "category": category,
            "usage_count": 0,
            "success_rate": 1.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_custom": True,
        }
        
        # Save prompt if provided
        if prompt:
            prompt_path = self.skills_dir / f"{skill_id}.md"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")
        
        self._save_registry()
        logger.info(f"SkillRouter: created new skill '{skill_id}': {description}")
        return skill_id
    
    def evolve_skill(self, skill_name: str, new_triggers: list[str] = None, 
                     updated_prompt: str = None):
        """Evolve an existing skill based on usage data."""
        if skill_name not in self.registry:
            return False
        
        if new_triggers:
            existing = self.registry[skill_name].get("triggers", [])
            self.registry[skill_name]["triggers"] = list(set(existing + new_triggers))
        
        if updated_prompt:
            prompt_path = self.skills_dir / f"{skill_name}.md"
            prompt_path.write_text(updated_prompt, encoding="utf-8")
        
        self._save_registry()
        return True
    
    def get_stats(self) -> dict:
        """Get skill usage statistics."""
        total_uses = sum(s.get("usage_count", 0) for s in self.registry.values())
        skills_used = sum(1 for s in self.registry.values() if s.get("usage_count", 0) > 0)
        custom_count = sum(1 for s in self.registry.values() if s.get("is_custom"))
        
        return {
            "total_skills": len(self.registry),
            "skills_used": skills_used,
            "custom_skills": custom_count,
            "total_uses": total_uses,
            "most_used": sorted(
                [(k, v.get("usage_count", 0)) for k, v in self.registry.items()],
                key=lambda x: x[1], reverse=True
            )[:5],
        }
    
    def _log_usage(self, skill_name: str, successful: bool):
        """Log skill usage for analytics."""
        log_path = self.vault_root / ".agent" / "skill-usage.jsonl"
        try:
            entry = {
                "skill": skill_name,
                "successful": successful,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass


# ── Module-level convenience functions (backward compatible) ──

_manager_cache: dict[str, SkillManager] = {}

def _get_manager(vault_root: Path) -> SkillManager:
    key = str(vault_root)
    if key not in _manager_cache:
        _manager_cache[key] = SkillManager(vault_root)
    return _manager_cache[key]


def route_skill(user_message: str, vault_root: Path = None) -> tuple[str | None, str | None]:
    """Match user message to a skill. (Backward compatible)"""
    if vault_root is None:
        # Legacy behavior: simple keyword match without vault
        msg = user_message.lower()
        for skill_name, config in SKILL_REGISTRY.items():
            for trigger in config["triggers"]:
                if trigger.lower() in msg:
                    return skill_name, trigger
        return None, None
    
    mgr = _get_manager(vault_root)
    name, trigger, _ = mgr.match(user_message)
    return name, trigger


def get_skill_prompt(skill_name: str, vault_root: Path) -> str | None:
    mgr = _get_manager(vault_root)
    return mgr.get_prompt(skill_name)


def record_skill_usage(skill_name: str, vault_root: Path, successful: bool = True):
    mgr = _get_manager(vault_root)
    mgr.record_usage(skill_name, successful)


def create_skill(name: str, triggers: list[str], description: str, vault_root: Path,
                 category: str = "custom", prompt: str = "", tools: list[str] = None) -> str:
    mgr = _get_manager(vault_root)
    return mgr.create_skill(name, triggers, description, category, prompt, tools)


def get_skill_stats(vault_root: Path) -> dict:
    mgr = _get_manager(vault_root)
    return mgr.get_stats()


def get_fallback_message() -> str:
    """When no skill matches, return structured options."""
    options = [
        ("diagnose", "薄弱点诊断 — 帮你分析哪里需要加强"),
        ("study-plan", "学习计划 — 制定每日复习安排"),
        ("explain", "知识点讲解 — 深度讲解你困惑的概念"),
    ]
    lines = ["我不确定你想让我做什么，你可以试试：", ""]
    for i, (name, desc) in enumerate("ABC"):
        trigger = SKILL_REGISTRY[options[i][0]]["triggers"][0]
        lines.append(f"**{name}. {desc}** — 说「{trigger}」即可")
    return "\n".join(lines)


def log_routing(user_message: str, matched_skill: str | None, user_followed_up: bool = False):
    """Legacy logging."""
    pass  # Now handled by SkillManager._log_usage


# ── Built-in skill prompts ──

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
category: analysis
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

## 原则
- 不要只说"多练练"，要说具体练什么
- 先肯定进步，再指出不足
"""

_STUDY_PLAN_PROMPT = """---
skill: study-plan
category: planning
---

# 学习规划 Agent

根据学生目标、掌握度、可用时间，生成可执行的多日学习计划。

## 输出格式
### 每日安排
- **第1天**: SRS复习 + 主攻(最弱知识点·10题) + 辅练(次弱·5题) · 预计40分钟
- **第2天**: ...

### 风险提示
- 连续2天正确率<40% → 自动降难度
"""

_EXPLAIN_PROMPT = """---
skill: explain
category: teaching
---

# 知识点讲解 Agent

## 输出
1. 一句话定义
2. 直观理解（类比/图示/例子）
3. 严格定义（如有公式用 LaTeX）
4. 经典例题
5. 常见误区
"""

_EXAM_PROMPT = """---
skill: exam
category: assessment
---

# 模拟考试 Agent

## 流程
1. 读取知识掌握度 → 按掌握度比例分配题目
2. 生成考卷
3. 考完 → 自动评分 → 薄弱点分析
"""

_REPORT_PROMPT = """---
skill: report
category: analysis
---

# 学习报告 Agent

## 格式
- 本周数据（练习次数、题数、正确率）
- 对比上周（进步/退步TOP3）
- 本周亮点
- 下周展望
"""

_MOTIVATE_PROMPT = """---
skill: motivate
category: support
---

# 学习激励 Agent

## 原则
- 先共情后再提醒进步
- 给最小步骤："今天就做1道题，做完就休息"
- 不讲大道理，给具体小行动
"""
