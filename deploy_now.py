"""Quick deploy: sync code to cloud server and rebuild."""
import paramiko
import os
import sys

SERVER = "43.139.179.58"
USER = "ubuntu"
PASS = "Aa@mingtiannihao"
REMOTE_DIR = "/home/ubuntu/quiz-app"
LOCAL = r"C:\Users\24368\Documents\知识库\quiz-app"

def run_ssh(client, cmd, desc=""):
    print(f"  [RUN] {desc}: {cmd[:80]}...")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0 and err:
        print(f"  [WARN]️  stderr: {err[:200]}")
    if out.strip():
        print(f"     {out.strip()[:300]}")
    return exit_code

def main():
    print("[CONNECT] Connecting to server...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, username=USER, password=PASS, timeout=15)

    sftp = client.open_sftp()

    # ── 1. Sync backend (exclude data, cache, env) ──
    print("\n[SYNC] 同步后端代码...")
    backend_local = os.path.join(LOCAL, "backend")
    backend_remote = f"{REMOTE_DIR}/backend"

    exclude_dirs = {'data', '__pycache__', '.pytest_cache', 'venv', '.env'}
    for root, dirs, files in os.walk(backend_local):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        rel = os.path.relpath(root, backend_local)
        remote_path = f"{backend_remote}/{rel}".replace('\\', '/')
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            run_ssh(client, f"mkdir -p {remote_path}", f"创建目录 {rel}")

        for f in files:
            if f.endswith(('.pyc', '.db', '.db-shm', '.db-wal')):
                continue
            local_file = os.path.join(root, f)
            remote_file = f"{remote_path}/{f}"
            try:
                sftp.put(local_file, remote_file)
                if 'prompts' in rel or 'generators' in rel or 'agent' in rel or 'assistant' in rel:
                    print(f"     [FILE] {rel}/{f}")
            except Exception as e:
                print(f"     [FAIL] {rel}/{f}: {e}")

    # ── 2. Sync frontend source ──
    print("\n[SYNC] 同步前端源码...")
    frontend_local = os.path.join(LOCAL, "frontend", "src")
    frontend_remote = f"{REMOTE_DIR}/frontend/src"

    for root, dirs, files in os.walk(frontend_local):
        dirs[:] = [d for d in dirs if d != 'node_modules']
        rel = os.path.relpath(root, frontend_local)
        remote_path = f"{frontend_remote}/{rel}".replace('\\', '/')
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            run_ssh(client, f"mkdir -p {remote_path}", f"创建目录 {rel}")

        for f in files:
            local_file = os.path.join(root, f)
            remote_file = f"{remote_path}/{f}"
            try:
                sftp.put(local_file, remote_file)
                print(f"     [FILE] {rel}/{f}")
            except Exception as e:
                print(f"     [FAIL] {rel}/{f}: {e}")

    sftp.close()

    # ── 3. Restart backend ──
    print("\n[RESTART] 重启后端...")
    run_ssh(client, "pkill -f 'uvicorn app.main' 2>/dev/null || true", "杀掉旧进程")
    run_ssh(client, "sleep 2", "等待")
    run_ssh(client, f"cd {REMOTE_DIR}/backend && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/quiz.log 2>&1 &", "启动后端")
    run_ssh(client, "sleep 4", "等待启动")

    # Health check
    code = run_ssh(client, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/api/v1/health", "健康检查")

    # ── 4. Rebuild frontend ──
    print("\n[BUILD] 重建前端...")
    run_ssh(client, f"cd {REMOTE_DIR}/frontend && npm run build 2>&1", "npm build")

    # ── 5. Update nginx static files ──
    print("\n[NGINX] 更新 Nginx 静态文件...")
    run_ssh(client, f"cp -r {REMOTE_DIR}/frontend/dist/* /usr/share/nginx/html/ 2>/dev/null || docker cp {REMOTE_DIR}/frontend/dist/. quiz-nginx:/usr/share/nginx/html/ 2>/dev/null || echo '[WARN]️ 请手动更新nginx静态文件'", "更新nginx")

    client.close()
    print("\n[OK] 部署完成！https://quiz.312233.xyz")

if __name__ == "__main__":
    main()
