import paramiko, time, sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('43.139.179.58', username='ubuntu', password='Aa@mingtiannihao', timeout=15)

def run(cmd, desc='', wait=True):
    print(f'[{desc or cmd[:50]}]', flush=True)
    # Use transport.open_session to avoid hanging on nohup
    channel = client.get_transport().open_session()
    channel.exec_command(cmd)
    if wait:
        out = channel.recv(65536).decode(errors='replace')
        err = channel.recv_stderr(65536).decode(errors='replace')
        rc = channel.recv_exit_status()
        if out.strip(): print(' ', out.strip()[:200])
        if rc != 0: print('  rc=%d %s' % (rc, err[:100]))
        return rc
    else:
        # Fire and forget
        channel.close()
        return 0

# 1. Kill old + start new (fire & forget for nohup)
run('pkill -f uvicorn 2>/dev/null; echo "killed old"', 'kill')
time.sleep(1)
run('cd /home/ubuntu/quiz-app/backend && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 &>/tmp/quiz.log & echo "started"', 'start', wait=False)
time.sleep(3)

# 2. Health check
run('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/v1/health', 'health')

# 3. Build frontend (this will take time)
run('cd /home/ubuntu/quiz-app/frontend && npm run build 2>&1', 'npm-build')

# 4. Update nginx
run('docker cp /home/ubuntu/quiz-app/frontend/dist/. quiz-nginx:/usr/share/nginx/html/ 2>&1', 'nginx')

client.close()
print('Done -> https://quiz.312233.xyz', flush=True)
