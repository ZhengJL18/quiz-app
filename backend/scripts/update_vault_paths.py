"""Batch-update all vault path references from English to Chinese."""
import os, re

base = os.path.join(os.path.dirname(__file__), '..', 'app')

MAP = {
    'knowledge': '讲义',
    'notes':     '笔记',
    'journal':   '日志',
    'profile':   '画像',
    'materials': '素材',
    '.agent':    '系统',
}

files = []
for root, dirs, filenames in os.walk(base):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
    for fn in filenames:
        if fn.endswith('.py'):
            files.append(os.path.join(root, fn))

changed = 0
for fp in files:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content

    for old_en, new_cn in MAP.items():
        # Match path prefix patterns in string literals
        for quote in ('"', "'"):
            # Exact prefix
            content = content.replace(f'{quote}{old_en}/', f'{quote}{new_cn}/')
            # f-string prefix
            content = content.replace(f'f{quote}{old_en}/', f'f{quote}{new_cn}/')

    # Special: vault.root / "journal"
    content = content.replace('vault.root / "journal"', 'vault.root / "日志"')
    content = content.replace("vault.root / 'journal'", "vault.root / '日志'")

    if content != original:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        rel = os.path.relpath(fp, base)
        print(f'  {rel}')
        changed += 1

print(f'\nChanged {changed} files')
