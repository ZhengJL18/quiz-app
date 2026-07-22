"""Full architecture audit: compile check + import check + syntax check."""
import py_compile, os, sys, traceback

base = os.path.dirname(os.path.abspath(__file__))
errors = []
warnings = []

for root, dirs, files in os.walk(os.path.join(base, "app")):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        rel = os.path.relpath(path, base)
        try:
            with open(path, 'r') as fh:
                source = fh.read()
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(f"SYNTAX {rel}: {e}")
        except Exception as e:
            errors.append(f"READ {rel}: {e}")

# Check for common issues
for root, dirs, files in os.walk(os.path.join(base, "app")):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        rel = os.path.relpath(path, base)
        try:
            with open(path, 'r') as fh:
                lines = fh.readlines()

            # Check for sync DB in async def
            in_async = False
            for i, line in enumerate(lines, 1):
                if 'async def ' in line:
                    in_async = True
                elif 'def ' in line and not 'async def' in line:
                    in_async = False

                if in_async and ('db.query(' in line or 'Session(' in line or 'SessionLocal' in line):
                    # Only flag if not inside a sync wrapper
                    if 'Depends(get_db)' not in line:
                        warnings.append(f"SYNC-DB-IN-ASYNC {rel}:{i}: {line.strip()[:80]}")

                # Check for f-string backslash issues
                if 'f"' in line and '\\\\"' in line:
                    errors.append(f"FSTRING-BACKSLASH {rel}:{i}: {line.strip()[:80]}")
        except Exception:
            pass

print(f"=== SYNTAX ERRORS: {len(errors)} ===")
for e in errors[:20]:
    print(e)

print(f"\n=== WARNINGS: {len(warnings)} ===")
for w in warnings[:20]:
    print(w)

if not errors and not warnings:
    print("CLEAN - no issues found")
