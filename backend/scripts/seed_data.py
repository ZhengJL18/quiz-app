"""Seed the database with subjects, 3-level chapter tree, and sample questions.

Usage:
    cd quiz-app/backend
    python scripts/seed_data.py          # seed into existing DB (idempotent for subjects/chapters)
    python scripts/seed_data.py --reset  # drop all tables and recreate
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.engine import engine, SessionLocal
from app.db.models import Base, User, Subject, Chapter, Question
import bcrypt as _bcrypt


def utcnow():
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────
# Chapter tree definitions
# ──────────────────────────────────────────────
# Structure: {subject: [(level1_name, [(level2_name, level3_name), ...]), ...]}

CHAPTER_TREES = {
    "高等数学": [
        ("第一章 函数与极限", [
            ("§1.1 映射与函数", "第01课 映射与函数"),
            ("§1.2 数列的极限", "第02课 数列的极限"),
            ("§1.3 函数的极限", "第03课 函数的极限"),
            ("§1.4 无穷小与无穷大", "第04课 无穷小与无穷大"),
            ("§1.5 极限运算法则", "第05课 极限运算法则"),
            ("§1.6 极限存在准则·两个重要极限", "第06课 极限存在准则"),
            ("§1.7 无穷小的比较", "第07课 无穷小的比较"),
        ]),
    ],
    "线性代数": [
        ("第一章 行列式", [
            ("§1.1 行列式的定义", "第01课 行列式"),
            ("§1.2 n阶行列式", "第02课 全排列与n阶行列式"),
            ("§1.3 行列式按行列展开", "第03课 行列式按行列展开"),
            ("§1.4 行列式计算技巧", "第04课 行列式计算技巧"),
        ]),
        ("第二章 矩阵及其运算", [
            ("§2.1 矩阵基本概念与运算", "第05课 矩阵基本概念与运算"),
            ("§2.2 矩阵乘法", "第06课 矩阵乘法"),
            ("§2.3 逆矩阵", "第07课 逆矩阵"),
        ]),
    ],
    "大学物理": [
        ("第一章 质点力学", [
            ("§1.1 质点运动学", "第01课 质点运动学"),
            ("§1.2 牛顿运动定律", "第02课 牛顿定律"),
            ("§1.3 动量定理与动量守恒", "第03课 动量定理"),
            ("§1.4 动能定理与机械能守恒", "第04课 动能定理"),
            ("§1.5 刚体的定轴转动", "第05课 刚体定轴转动"),
        ]),
        ("第二章 振动与波动", [
            ("§2.1 简谐振动", "第06课 简谐振动"),
            ("§2.2 机械波", "第07课 机械波"),
        ]),
    ],
    "英语四六级": [
        ("词汇与阅读", [
            ("Day 01 核心词汇", "第01天 核心词汇"),
            ("Day 02 教育", "第02天 教育话题"),
            ("Day 03 环保", "第03天 环保话题"),
            ("Day 04 科技AI", "第04天 科技AI话题"),
            ("Day 05 健康医疗", "第05天 健康医疗话题"),
            ("Day 06 社会文化", "第06天 社会文化话题"),
            ("Day 07 经济商业", "第07天 经济商业话题"),
            ("Day 08 政法社会", "第08天 政法社会话题"),
            ("Day 09 心理教育", "第09天 心理教育话题"),
            ("Day 10 传媒信息", "第10天 传媒信息话题"),
            ("Day 11 历史考古", "第11天 历史考古话题"),
        ]),
    ],
    "C++程序设计": [
        ("第一章 C++基础", [
            ("§1.1 入门与开发环境", "第01课 C++入门"),
            ("§1.2 条件与循环", "第02课 条件与循环"),
            ("§1.3 数组与字符串", "第03课 数组与字符串"),
            ("§1.4 函数基础", "第04课 函数基础"),
        ]),
    ],
}

# Subject metadata
SUBJECTS_META = [
    {"name": "高等数学", "description": "同济大学《高等数学》第七版 上册", "order_index": 1,
     "prompt_style": "贴合大学高等数学期末考试风格，注重计算与证明"},
    {"name": "线性代数", "description": "同济大学《线性代数》", "order_index": 2,
     "prompt_style": "注重矩阵运算与理论推导，贴合工科线代考试"},
    {"name": "大学物理", "description": "大学物理（力学、振动与波）", "order_index": 3,
     "prompt_style": "注重物理概念理解和计算应用"},
    {"name": "英语四六级", "description": "大学英语四六级词汇与阅读", "order_index": 4,
     "prompt_style": "词汇题+阅读理解，贴合四六级难度"},
    {"name": "C++程序设计", "description": "C++程序设计基础", "order_index": 5,
     "prompt_style": "基础语法题+简单编程题"},
]


def sample_questions_for_chapter(subject_name, chapter_name):
    """Return 2-4 sample seed questions for a given chapter.
    These avoid AI calls on cold start."""
    questions = []

    # Simple generic question templates
    if "高等数学" in subject_name:
        if "映射" in chapter_name:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "函数 $f(x)=\\frac{1}{x-1}$ 的定义域是？",
                    "options": {"A": "$(-\\infty,+\\infty)$", "B": "$(-\\infty,1)\\cup(1,+\\infty)$",
                                "C": "$(1,+\\infty)$", "D": "$(-\\infty,1)$"},
                    "correct_answer": "B", "tags": ["定义域", "基本函数"]
                }, "difficulty": 1},
                {"type": "fill_blank", "content": {
                    "question_text": "设 $f(x)=x^2+1$，则 $f(2)=$ ______。",
                    "correct_answers": ["5"], "tags": ["函数值"]
                }, "difficulty": 1},
                {"type": "single_choice", "content": {
                    "question_text": "下列函数中是奇函数的是？",
                    "options": {"A": "$f(x)=x^2$", "B": "$f(x)=x^3$",
                                "C": "$f(x)=\\cos x$", "D": "$f(x)=|x|$"},
                    "correct_answer": "B", "tags": ["奇偶性"]
                }, "difficulty": 2},
            ]
        elif "极限" in chapter_name and "数列" in chapter_name:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "数列 $\\{a_n\\}=\\{\\frac{1}{n}\\}$ 的极限是？",
                    "options": {"A": "1", "B": "0", "C": "$\\infty$", "D": "不存在"},
                    "correct_answer": "B", "tags": ["数列极限"]
                }, "difficulty": 1},
                {"type": "fill_blank", "content": {
                    "question_text": "$\\lim_{n\\to\\infty}\\frac{n}{n+1}=$ ______。",
                    "correct_answers": ["1"], "tags": ["极限计算"]
                }, "difficulty": 2},
            ]
        elif "极限" in chapter_name and "函数" in chapter_name:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "$\\lim_{x\\to 0}\\frac{\\sin x}{x}=$？",
                    "options": {"A": "0", "B": "1", "C": "$\\infty$", "D": "不存在"},
                    "correct_answer": "B", "tags": ["重要极限"]
                }, "difficulty": 1},
                {"type": "fill_blank", "content": {
                    "question_text": "$\\lim_{x\\to 1}(x^2+2x-1)=$ ______。",
                    "correct_answers": ["2"], "tags": ["极限计算"]
                }, "difficulty": 1},
            ]
        else:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "（种子题）本章的基础概念题。",
                    "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
                    "correct_answer": "A", "tags": ["基础"]
                }, "difficulty": 1},
                {"type": "fill_blank", "content": {
                    "question_text": "（种子题）$1+1=$ ______。",
                    "correct_answers": ["2"], "tags": ["基础"]
                }, "difficulty": 1},
            ]

    elif "线性代数" in subject_name:
        if "行列式" in chapter_name and "定义" in chapter_name:
            questions = [
                {"type": "fill_blank", "content": {
                    "question_text": "二阶行列式 $\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}=$ ______。",
                    "correct_answers": ["ad-bc"], "tags": ["行列式定义"]
                }, "difficulty": 1},
                {"type": "single_choice", "content": {
                    "question_text": "行列式 $\\begin{vmatrix}1&2\\\\3&4\\end{vmatrix}$ 的值是？",
                    "options": {"A": "-2", "B": "2", "C": "10", "D": "-10"},
                    "correct_answer": "A", "tags": ["行列式计算"]
                }, "difficulty": 1},
            ]
        elif "矩阵" in chapter_name and "乘法" in chapter_name:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "设 $A$ 是 $2\\times 3$ 矩阵，$B$ 是 $3\\times 2$ 矩阵，则 $AB$ 是？",
                    "options": {"A": "$2\\times 2$", "B": "$3\\times 3$", "C": "$2\\times 3$", "D": "无法相乘"},
                    "correct_answer": "A", "tags": ["矩阵乘法"]
                }, "difficulty": 1},
            ]
        else:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "（种子题）本章的基础概念题。",
                    "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
                    "correct_answer": "A", "tags": ["基础"]
                }, "difficulty": 1},
            ]

    elif "物理" in subject_name:
        if "运动学" in chapter_name:
            questions = [
                {"type": "fill_blank", "content": {
                    "question_text": "一质点沿直线运动，位移 $x=3t^2+2t$（SI），则 $t=1$s 时的速度为 ______ m/s。",
                    "correct_answers": ["8"], "tags": ["运动学", "速度"]
                }, "difficulty": 2},
                {"type": "single_choice", "content": {
                    "question_text": "质点做匀速圆周运动时，下列哪个量是恒定的？",
                    "options": {"A": "速度", "B": "加速度", "C": "角速度", "D": "合外力"},
                    "correct_answer": "C", "tags": ["圆周运动"]
                }, "difficulty": 1},
            ]
        else:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "（种子题）本章的基础概念题。",
                    "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
                    "correct_answer": "A", "tags": ["基础"]
                }, "difficulty": 1},
            ]

    elif "英语" in subject_name:
        questions = [
            {"type": "single_choice", "content": {
                "question_text": "The word \"ubiquitous\" most nearly means:",
                "options": {"A": "rare", "B": "everywhere", "C": "unique", "D": "underground"},
                "correct_answer": "B", "tags": ["词汇"]
            }, "difficulty": 2},
            {"type": "fill_blank", "content": {
                "question_text": "She has a strong ______ (prefer) for classical music. （用括号词的适当形式填空）",
                "correct_answers": ["preference"], "tags": ["词形变化"]
            }, "difficulty": 1},
        ]

    elif "C++" in subject_name:
        if "入门" in chapter_name:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "C++中，以下哪个是正确的main函数定义？",
                    "options": {"A": "void main() {}", "B": "int main() {}", "C": "Main() {}", "D": "function main() {}"},
                    "correct_answer": "B", "tags": ["语法基础"]
                }, "difficulty": 1},
                {"type": "fill_blank", "content": {
                    "question_text": "C++中输出\"Hello World\"的语句是 `std::______ << \"Hello World\";`",
                    "correct_answers": ["cout"], "tags": ["输出"]
                }, "difficulty": 1},
            ]
        elif "循环" in chapter_name:
            questions = [
                {"type": "fill_blank", "content": {
                    "question_text": "`for(int i=0; i<5; i++)` 循环体将执行 ______ 次。",
                    "correct_answers": ["5"], "tags": ["循环"]
                }, "difficulty": 1},
            ]
        else:
            questions = [
                {"type": "single_choice", "content": {
                    "question_text": "（种子题）本章的基础概念题。",
                    "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
                    "correct_answer": "A", "tags": ["基础"]
                }, "difficulty": 1},
            ]

    # Ensure at least one question
    if not questions:
        questions = [
            {"type": "fill_blank", "content": {
                "question_text": "（种子题）$1+1=$ ______。",
                "correct_answers": ["2"], "tags": ["基础"]
            }, "difficulty": 1},
        ]

    return questions


def seed(db, reset=False):
    """Main seed function."""
    if reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("Tables recreated.")

    # ── Create admin user ──
    existing_user = db.query(User).filter_by(username="admin").first()
    if not existing_user:
        user = User(
            username="admin",
            password_hash=_bcrypt.hashpw(b"admin123", _bcrypt.gensalt()).decode(),
            is_active=True,
        )
        db.add(user)
        db.flush()
        print("Created user: admin / admin123")
    else:
        print("User 'admin' already exists, skipping.")

    # ── Create subjects and chapters ──
    for meta in SUBJECTS_META:
        existing = db.query(Subject).filter_by(name=meta["name"]).first()
        if existing:
            print(f"Subject '{meta['name']}' already exists, skipping chapters too.")
            continue

        subject = Subject(
            name=meta["name"],
            description=meta["description"],
            order_index=meta["order_index"],
            prompt_style=meta.get("prompt_style"),
        )
        db.add(subject)
        db.flush()
        print(f"Created subject: {meta['name']}")

        # Create chapter tree for this subject
        tree = CHAPTER_TREES.get(meta["name"], [])
        for l1_idx, (l1_name, l2_list) in enumerate(tree):
            l1 = Chapter(
                subject_id=subject.id,
                name=l1_name,
                level=1,
                order_index=l1_idx + 1,
                is_leaf=False,
            )
            db.add(l1)
            db.flush()

            for l2_idx, (l2_name, l3_name) in enumerate(l2_list):
                l2 = Chapter(
                    subject_id=subject.id,
                    name=l2_name,
                    level=2,
                    order_index=l2_idx + 1,
                    parent_chapter_id=l1.id,
                    is_leaf=False,
                )
                db.add(l2)
                db.flush()

                l3 = Chapter(
                    subject_id=subject.id,
                    name=l3_name,
                    level=3,
                    order_index=1,
                    parent_chapter_id=l2.id,
                    is_leaf=True,
                    lesson_duration_minutes=20,
                )
                db.add(l3)
                db.flush()

                # Add sample questions for this leaf chapter
                samples = sample_questions_for_chapter(meta["name"], l3_name)
                for sq in samples:
                    has_latex = "$" in sq["content"].get("question_text", "")
                    q = Question(
                        subject_id=subject.id,
                        chapter_id=l3.id,
                        question_type=sq["type"],
                        content_json=json.dumps(sq["content"], ensure_ascii=False),
                        difficulty=sq.get("difficulty", 1),
                        has_latex=has_latex,
                        created_by="seed",
                    )
                    db.add(q)

        db.commit()
        print(f"  Created chapter tree with sample questions for '{meta['name']}'")

    print("\nSeed complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed quiz database")
    parser.add_argument("--reset", action="store_true", help="Drop all tables before seeding")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        seed(db, reset=args.reset)
    finally:
        db.close()
