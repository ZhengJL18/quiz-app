"""
一键同步本地代码到云服务器并重启
用法: python sync-to-server.py
"""
import paramiko
import os
import sys
from pathlib import Path

SERVER_IP = "43.139.179.58"
SERVER_USER = "ubuntu"
SERVER_PASS = "Aa@mingtiannihao"
REMOTE_DIR = "/home/ubuntu/quiz-app"
LOCAL_DIR = Path(__file__).resolve().parent

# 不覆盖的文件/目录（保护数据库！）
EXCLUDE = {
    'data/',
    '__pycache__/',
    '.pytest_cache__/',
    '*.pyc',
    '.env',
    '*.db',
    '*.db-shm',
    '*.db-wal',
    'node_modules/',
    'dist/',
    '.git/',
}

def should_skip(path_parts):
    for part in path_parts:
        for ex in EXCLUDE:
            if ex.endswith('/') and part == ex[:-1]:
                return True
            if ex.startswith('*') and part.endswith(ex[1:]):
                return True
            if part == ex:
                return True
    return False

def upload_files(ssh, local_subdir, remote_subdir):
    """Upload all files in local_subdir to remote_subdir via SFTP."""
    sftp = ssh.open_sftp()
    local_path = LOCAL_DIR / local_subdir
    remote_path = f"{REMOTE_DIR}/{remote_subdir}"

    uploaded = 0
    for root, dirs, files in os.walk(local_path):
        rel_root = os.path.relpath(root, local_path)
        parts = rel_root.split(os.sep) if rel_root != '.' else []

        if should_skip(parts):
            continue

        remote_root = f"{remote_path}/{rel_root.replace(os.sep, '/')}" if rel_root != '.' else remote_path

        # Create remote directory
        try:
            sftp.stat(remote_root)
        except FileNotFoundError:
            try:
                sftp.mkdir(remote_root)
            except:
                pass  # directory might exist

        for f in files:
            if should_skip(list(parts) + [f]):
                continue
            local_file = os.path.join(root, f)
            remote_file = f"{remote_root}/{f}"
            try:
                sftp.put(local_file, remote_file)
                uploaded += 1
                print(f"  ↳ {local_subdir}/{rel_root}/{f}" if rel_root != '.' else f"  ↳ {local_subdir}/{f}")
            except Exception as e:
                print(f"  ✗ {f}: {e}")

    sftp.close()
    return uploaded

def main():
    print("🔁 连接服务器...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASS, timeout=15)
    print("✅ 已连接\n")

    # Upload backend
    print("📤 同步 backend/ ...")
    n = upload_files(ssh, 'backend', 'backend')
    print(f"   共 {n} 个文件\n")

    # Upload frontend (code only, no node_modules)
    print("📤 同步 frontend/ ...")
    n = upload_files(ssh, 'frontend', 'frontend')
    print(f"   共 {n} 个文件\n")

    # Restart backend
    print("🔄 重启后端服务...")
    ssh.exec_command('pkill -f "uvicorn app.main" 2>/dev/null')

    import time
    time.sleep(2)

    ssh.exec_command(
        'cd ~/quiz-app/backend && '
        'nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > /tmp/quiz.log 2>&1 &'
    )
    time.sleep(3)

    # Verify
    stdin, stdout, stderr = ssh.exec_command(
        'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/v1/health'
    )
    code = stdout.read().decode().strip()

    if code == '200':
        print("✅ 部署成功！")
        print("   https://quiz.312233.xyz")
    else:
        print(f"❌ 健康检查返回 {code}")
        stdin, stdout, stderr = ssh.exec_command('tail -20 /tmp/quiz.log')
        print(stdout.read().decode()[:500])

    ssh.close()

if __name__ == '__main__':
    main()
