"""Rename chapter dirs with order prefix based on Chinese numeral in name."""
import os, re, shutil

cn_num = {
    '一': '01', '二': '02', '三': '03', '四': '04', '五': '05',
    '六': '06', '七': '07', '八': '08', '九': '09', '十': '10',
    '十一': '11', '十二': '12', '十三': '13',
}

vault_root = '/home/ubuntu/quiz-app/data/users'
count = 0

for root, dirs, files in os.walk(vault_root):
    for d in list(dirs):
        # Match "第X章 ..." without existing 0X_ prefix
        m = re.match(r'^第([一二三四五六七八九十]+)章 (.+)', d)
        if m and not d.startswith('0'):
            cn, rest = m.group(1), m.group(2)
            num = cn_num.get(cn)
            if num:
                prefix = f"{num}_"
                old = os.path.join(root, d)
                new = os.path.join(root, prefix + d)
                if not os.path.exists(new):
                    shutil.move(old, new)
                    print(f"  {d}/ -> {prefix}{d}/")
                    count += 1

# Also fix DB pointers
sys.path.insert(0, '/home/ubuntu/quiz-app/backend')
from app.db.engine import SessionLocal
from app.db.models import Chapter

db = SessionLocal()
updated = 0
for ch in db.query(Chapter).all():
    desc = ch.description or ''
    if 'knowledge/' not in desc or '/第' not in desc:
        continue
    for cn, num in cn_num.items():
        old_seg = f"/第{cn}章"
        new_seg = f"/{num}_第{cn}章"
        if old_seg in desc and new_seg not in desc:
            desc = desc.replace(old_seg, new_seg)
            ch.description = desc
            updated += 1

db.commit()
db.close()
print(f"Renamed {count} directories, updated {updated} DB pointers")
