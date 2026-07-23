"""Vault Manager — per-user file system with cross-platform file locking.

Each user gets a private vault at data/users/{user_id}/.
All reads and writes go through this manager to ensure:
- Concurrent write safety (.lock files)
- _summary.md auto-maintenance
- Storage quota awareness
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# fcntl is Unix-only; imported lazily on Linux
_fcntl = None
def _get_fcntl():
    global _fcntl
    if _fcntl is None and os.name != "nt":
        import fcntl as _f
        _fcntl = _f
    return _fcntl

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "data" / "users"
VAULT_MAX_SIZE_MB = 1024  # 1 GB per user
LOCK_TIMEOUT_SEC = 10


class VaultLock:
    """Cross-platform file lock. Uses fcntl on Linux, .lock files on Windows."""

    def __init__(self, filepath: Path):
        self.lockfile = filepath.parent / f"{filepath.name}.lock"
        self.fd = None

    def acquire(self, timeout: float = LOCK_TIMEOUT_SEC) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if os.name == "nt":
                    # Windows: create lock file atomically
                    try:
                        fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        os.write(fd, str(os.getpid()).encode())
                        os.close(fd)
                        self.fd = True
                        return True
                    except FileExistsError:
                        # Check if stale (>30s old)
                        try:
                            mtime = os.path.getmtime(self.lockfile)
                            if time.time() - mtime > 30:
                                os.remove(self.lockfile)
                                continue
                        except OSError:
                            pass
                else:
                    # Linux: fcntl advisory lock
                    fcntl = _get_fcntl()
                    self.fd = open(self.lockfile, "w")
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
            except (OSError, IOError):
                pass
            time.sleep(0.1)
        return False

    def release(self):
        try:
            if os.name == "nt":
                if self.fd:
                    try:
                        os.remove(self.lockfile)
                    except OSError:
                        pass
            else:
                if self.fd:
                    fcntl = _get_fcntl()
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                    self.fd.close()
                    try:
                        os.remove(self.lockfile)
                    except OSError:
                        pass
        except (OSError, IOError):
            pass


class VaultManager:
    """Manages a single user's vault."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.root = VAULT_ROOT / str(user_id)
        self._ensure_dirs()

    # ── Initialization ──

    def _ensure_dirs(self):
        """Create the standard vault directory structure."""
        dirs = [
            self.root / ".agent" / "skills",
            self.root / "profile" / "api_keys",
            self.root / "knowledge",
            self.root / "notes",
            self.root / "practice" / "sessions",
            self.root / "materials",
            self.root / "journal",
            self.root / "chat",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # Create default files if missing
        defaults = {
            self.root / ".agent" / "system.md": _DEFAULT_SYSTEM_MD,
            self.root / ".agent" / "memory.md": f"---\ncreated: {datetime.now(timezone.utc).isoformat()}\n---\n\n# 长期记忆\n\n（Agent 会在使用过程中自动填充此文件）\n",
            self.root / ".agent" / "journal.md": "",
            self.root / "profile" / "about.md": "",
            self.root / "profile" / "goals.md": "",
            self.root / "profile" / "preferences.md": "",
            self.root / "profile" / "context.md": "",
            self.root / "knowledge" / "index.md": "# 科目索引\n\n（创建第一个科目后自动填充）\n",
            self.root / "materials" / "index.md": "# 资料目录\n\n",
        }
        for path, content in defaults.items():
            if not path.exists():
                self._write_file(path, content)

    # ── Structured path helpers ──

    def lesson_path(self, subject: str, chapter_path: list[str]) -> str:
        """Vault path for lesson content.

        Args:
            subject: Subject name like "高等数学"
            chapter_path: Hierarchy list like ["第一章", "第一节", "课时名"]

        Returns: "knowledge/高等数学/第一章/第一节/课时名.md"
        """
        safe_subj = "".join(c for c in subject if c.isalnum() or c in "._- ()（）")
        safe_parts = []
        for p in chapter_path:
            safe_parts.append("".join(c for c in p if c.isalnum() or c in "._- ()（）"))

        if len(safe_parts) == 1:
            # Flat: knowledge/高等数学/章节名.md
            return f"knowledge/{safe_subj}/{safe_parts[0]}.md"
        else:
            # Hierarchical: knowledge/高等数学/章/节/课时.md
            *parents, leaf = safe_parts
            return f"knowledge/{safe_subj}/{'/'.join(parents)}/{leaf}.md"

    def question_path(self, subject: str, chapter: str) -> str:
        """Vault path for question bank: knowledge/{科目}/questions/{章节}.json"""
        safe_subj = "".join(c for c in subject if c.isalnum() or c in "._- ()（）")
        safe_ch = "".join(c for c in chapter if c.isalnum() or c in "._- ()（）")
        return f"knowledge/{safe_subj}/questions/{safe_ch}.json"

    def review_path(self, subject: str, chapter: str) -> str:
        """Vault path for review reports: knowledge/{科目}/review/{章节}.md"""
        safe_subj = "".join(c for c in subject if c.isalnum() or c in "._- ()（）")
        safe_ch = "".join(c for c in chapter if c.isalnum() or c in "._- ()（）")
        return f"knowledge/{safe_subj}/review/{safe_ch}.md"

    def note_path(self, note_id: int) -> str:
        return f"notes/{note_id}.md"

    def conversation_path(self, conv_id: int) -> str:
        return f"chat/{conv_id}.json"

    def practice_session_path(self, session_id: int) -> str:
        return f"practice/sessions/{session_id}.json"

    # ── Read / Write ──

    def read(self, relative_path: str) -> str | None:
        """Read a file from the vault. Returns None if not found."""
        full = (self.root / relative_path).resolve()
        if not str(full).startswith(str(self.root.resolve())):
            raise ValueError(f"Path traversal detected: {relative_path}")
        if not full.exists():
            return None
        return full.read_text(encoding="utf-8", errors="replace")

    def write(self, relative_path: str, content: str) -> bool:
        """Write a file to the vault with locking. Returns False if over quota."""
        full = (self.root / relative_path).resolve()
        if not str(full).startswith(str(self.root.resolve())):
            raise ValueError(f"Path traversal detected: {relative_path}")
        # Quota check (skip for small files)
        if len(content.encode("utf-8")) > 100_000 and not self.within_quota():
            return False
        full.parent.mkdir(parents=True, exist_ok=True)

        lock = VaultLock(full)
        if not lock.acquire():
            return False
        try:
            self._write_file(full, content)
            self._update_summary(full.parent)
            return True
        finally:
            lock.release()

    def append(self, relative_path: str, content: str) -> bool:
        """Append content to a file with locking."""
        full = (self.root / relative_path).resolve()
        if not str(full).startswith(str(self.root.resolve())):
            raise ValueError(f"Path traversal detected: {relative_path}")
        full.parent.mkdir(parents=True, exist_ok=True)

        lock = VaultLock(full)
        if not lock.acquire():
            return False
        try:
            existing = full.read_text(encoding="utf-8", errors="replace") if full.exists() else ""
            self._write_file(full, existing.rstrip() + "\n" + content + "\n")
            self._update_summary(full.parent)
            return True
        finally:
            lock.release()

    def _write_file(self, path: Path, content: str):
        """Internal: write file without locking."""
        path.write_text(content, encoding="utf-8")

    def _update_summary(self, directory: Path):
        """Auto-maintain _summary.md for a directory."""
        summary_path = directory / "_summary.md"
        files = sorted([f for f in directory.iterdir() if f.is_file() and f.name != "_summary.md" and not f.name.endswith(".lock")])
        if not files:
            if summary_path.exists():
                summary_path.unlink()
            return

        lines = [f"# {directory.name} · 摘要", f"更新: {datetime.now(timezone.utc).isoformat()}", ""]
        total_chars = 0
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                preview = content[:300].replace("\n", " ").strip()
                size = len(content)
                total_chars += size
                lines.append(f"- **{f.name}** ({size}字): {preview}...")
            except Exception:
                lines.append(f"- **{f.name}**: (binary/unreadable)")
        lines.append(f"\n总计: {len(files)} 个文件, {total_chars} 字")
        self._write_file(summary_path, "\n".join(lines))

    # ── Quota ──

    def size_mb(self) -> float:
        """Total vault size in MB."""
        total = 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total / (1024 * 1024)

    def within_quota(self) -> bool:
        """Check if vault is under the size limit."""
        return self.size_mb() < VAULT_MAX_SIZE_MB

    # ── File listing ──

    def list_files(self, relative_dir: str = "") -> list[dict]:
        """List files in a vault directory."""
        d = (self.root / relative_dir).resolve() if relative_dir else self.root
        if not d.exists():
            return []
        results = []
        for f in sorted(d.iterdir()):
            if f.name.startswith(".") or f.name.endswith(".lock"):
                continue
            results.append({
                "name": f.name,
                "type": "dir" if f.is_dir() else "file",
                "size": f.stat().st_size if f.is_file() else 0,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        return results

    # ── Onboarding ──

    def onboard(self, subjects: list[str], goal: str, learning_style: str) -> dict:
        """Run the 3-step onboarding wizard and populate initial vault + DB."""
        from app.db.engine import SessionLocal
        from app.db.models import Subject
        
        results = {}

        # Step 1: Create knowledge structure + DB subjects
        idx_lines = ["# 科目索引\n"]
        db = SessionLocal()
        try:
            for i, subj_name in enumerate(subjects):
                subj_dir = self.root / "knowledge" / subj_name
                subj_dir.mkdir(parents=True, exist_ok=True)
                mastery_md = subj_dir / "mastery.md"
                if not mastery_md.exists():
                    self._write_file(mastery_md, f"---\nsubject: {subj_name}\nupdated: {datetime.now(timezone.utc).isoformat()}\n---\n\n# 掌握度矩阵\n\n（练习后自动填充）\n")
                idx_lines.append(f"- {subj_name}")
                
                # Create Subject record in DB (skip if already exists)
                existing = db.query(Subject).filter_by(
                    name=subj_name, user_id=self.user_id, is_active=True
                ).first()
                if not existing:
                    db.add(Subject(
                        user_id=self.user_id,
                        name=subj_name,
                        is_active=True,
                        order_index=i,
                    ))
                    results[subj_name] = "created"
                else:
                    results[subj_name] = "already_exists"
            db.commit()
        finally:
            db.close()

        self._write_file(self.root / "knowledge" / "index.md", "\n".join(idx_lines))

        # Step 2: Set goals
        self._write_file(self.root / "profile" / "goals.md", f"---\nupdated: {datetime.now(timezone.utc).isoformat()}\n---\n\n# 学习目标\n\n{goal}\n")
        results["goal"] = "saved"

        # Step 3: Set preferences
        self._write_file(self.root / "profile" / "preferences.md", f"---\nupdated: {datetime.now(timezone.utc).isoformat()}\n---\n\n# 学习偏好\n\n- 学习风格: {learning_style}\n")
        results["preferences"] = "saved"

        return results


_DEFAULT_SYSTEM_MD = """---
name: 三一学习助手
version: 1.0
model: deepseek-chat
---

# 你是三一学习 Agent

你的身份：一个认识学生、懂教育、会推动成长的 AI 学习 Agent。

## 核心职责

1. **认识学生**。每次对话前，你必须完整阅读学生的 profile/ 和 knowledge/ 文件。不了解学生就不要乱给建议。

2. **推动练习**。你的价值不是"回答一个问题"，而是"让学生真的学会"。这意味着：出题 > 讲解 > 闲聊。每次对话结束时，提案下一次做什么。

3. **自学习**。每次交互结束后，你必须更新相关记忆文件：
   - 发现新薄弱点 → 写入 knowledge/{科目}/weaknesses.md
   - 掌握度变化 → 更新 knowledge/{科目}/mastery.md
   - 今天的重要事件 → 追加到 journal/{今日}.md

4. **个性化**。读学生的 preferences.md，按他们喜欢的方式教学。

5. **顺便一提**。回答完用户问题后，自然地插入"顺便一提"（≤30字，相关，低压力）。

6. **自主决策**。你不仅是回答问题，还要**主动推动学习**：
   - 发现学生连续答错 → 主动提议"要不要换个方式讲？"
   - 检测到某个知识点3天没练 → 提醒"你已经3天没练XX了"
   - 学生完成一轮练习 → 主动分析趋势并报告进步
   - 每天第一次对话 → 自动调用 daily-plan 生成今日建议

## 行为准则

- 每次对话前，先读 profile/、knowledge/ 和最近 7 天 journal/
- 出题时，优先选择 mastery.md 中标薄弱的知识点
- 学生连续答对 3 次同一知识点 → 提高难度
- 学生连续答错 → 降级 + 换个角度讲解
- 每天第一次打开 → 主动生成今日学习建议

## 文件读写权限

你能读写的文件范围：data/users/{user_id}/。不要越界读取其他用户的数据。
"""


# ── Singleton per user ──
_managers: dict[int, tuple[VaultManager, float]] = {}
_MANAGER_TTL = 1800  # 30 minutes idle → expire


def get_vault(user_id: int) -> VaultManager:
    """Get or create a VaultManager for a user. Idle >30min → auto-expire."""
    now = time.time()
    # Purge expired
    expired = [uid for uid, (_, ts) in _managers.items() if now - ts > _MANAGER_TTL]
    for uid in expired:
        del _managers[uid]

    if user_id not in _managers:
        _managers[user_id] = (VaultManager(user_id), now)
    else:
        _managers[user_id] = (_managers[user_id][0], now)  # Refresh timestamp
    return _managers[user_id][0]
