"""Quick deploy - sync code and rebuild."""
import paramiko, os, glob

SERVER = "43.139.179.58"
USER = "ubuntu"
PASS = "Aa@mingtiannihao"
REMOTE = "/home/ubuntu/quiz-app"
LOCAL_BACKEND = r"C:\Users\24368\Documents\知识库\quiz-app\backend"
LOCAL_FRONTEND = r"C:\Users\24368\Documents\知识库\quiz-app\frontend"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, username=USER, password=PASS, timeout=15)
sftp = client.open_sftp()

def ssh(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    rc = stdout.channel.recv_exit_status()
    if rc != 0: print(f"  rc={rc} {err[:200]}")
    return out.strip()

# ── 1. Backend: only the files we changed ──
changed_backend = [
    "app/routers/agent.py",
    "app/routers/assistant.py",
    "app/ai_service/generators.py",
    "app/ai_service/prompts/base.yaml",
    "app/ai_service/prompts/explanation.yaml",
    "app/ai_service/prompts/question_gen.yaml",
]
print("[1/4] Syncing backend...")
for f in changed_backend:
    local = os.path.join(LOCAL_BACKEND, f)
    remote = f"{REMOTE}/backend/{f}"
    sftp.put(local, remote)
    print(f"  OK  {f}")

# ── 2. Frontend: only the files we changed ──
changed_frontend = [
    "src/composables/useKaTeX.js",
    "src/App.vue",
    "src/components/chat/ChatPanel.vue",
    "src/stores/chat.js",
    "src/views/ReviewView.vue",
    "src/views/PracticeView.vue",
    "src/views/WrongBookView.vue",
    "src/views/HomeView.vue",
]
print("[2/4] Syncing frontend...")
for f in changed_frontend:
    local = os.path.join(LOCAL_FRONTEND, f)
    remote = f"{REMOTE}/frontend/{f}"
    try:
        sftp.put(local, remote)
        print(f"  OK  {f}")
    except Exception as e:
        print(f"  FAIL {f}: {e}")

sftp.close()

# ── 3. Restart backend ──
print("[3/4] Restarting backend...")
ssh("pkill -f 'uvicorn app.main' 2>/dev/null; sleep 2")
ssh(f"cd {REMOTE}/backend && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/quiz.log 2>&1 &")
import time; time.sleep(4)
code = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/api/v1/health")
print(f"  Health: HTTP {code}")

# ── 4. Rebuild frontend ──
print("[4/4] Rebuilding frontend...")
result = ssh(f"cd {REMOTE}/frontend && npm run build 2>&1")
print(result[:500] if result else "(no output)")

# Update nginx static
print("Updating nginx...")
ssh(f"docker cp {REMOTE}/frontend/dist/. quiz-nginx:/usr/share/nginx/html/ 2>&1 || echo 'nginx update skipped'")

client.close()
print("\nDone! https://quiz.312233.xyz")
