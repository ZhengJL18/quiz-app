"""Verify no leftover English vault paths."""
import os

base = os.path.join(os.path.dirname(__file__), '..', 'app')
files = ['routers/agent.py', 'routers/assistant.py', 'routers/study.py',
         'routers/notes.py', 'services/agent_context.py', 'services/memory_writer.py']

OLD_PATHS = ['knowledge/', '.agent/', 'journal/', 'profile/api', 'notes/', 'materials/']

for fn in files:
    fp = os.path.join(base, fn)
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    issues = []
    for old in OLD_PATHS:
        if old in content:
            issues.append(old)
    if issues:
        print(f'FAIL: {fn} still contains: {issues}')
    else:
        print(f'OK: {fn}')
print('Done')
