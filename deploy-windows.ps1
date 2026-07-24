# ============================================================
# 三一 · 一键部署脚本 (Windows Server)
# RDP 登录后，打开 PowerShell，逐段粘贴执行
# ============================================================

# ═══ 第1步：安装 Chocolatey（包管理器） ═══
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 关闭这个窗口，重新打开一个PowerShell

# ═══ 第2步：安装 Git + Python + nssm（服务管理） ═══
choco install git python3 nssm -y
refreshenv

# ═══ 第3步：下载项目 ═══
cd C:\
git clone https://github.com/YOUR_USER/quiz-app.git  # 替换为你的仓库地址
# 或者如果还没推GitHub，手动把 quiz-app 文件夹复制到 C:\quiz-app

cd C:\quiz-app

# ═══ 第4步：安装依赖 ═══
cd backend
pip install -r requirements.txt
cd ..

# ═══ 第5步：配置环境 ═══
# 编辑 .env 文件（用记事本打开 C:\quiz-app\.env）
# 确认里面的 DEEPSEEK_API_KEY 和 JWT_SECRET 已填好

# ═══ 第6步：构建前端 ═══
cd frontend
npm install
npm run build
cd ..

# ═══ 第7步：初始化数据库 ═══
cd backend
python scripts/seed_data.py
cd ..

# ═══ 第8步：安装为Windows服务（开机自启） ═══
nssm install quiz-backend "C:\Python314\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8001"
nssm set quiz-backend AppDirectory "C:\quiz-app\backend"
nssm set quiz-backend Start SERVICE_AUTO_START
nssm start quiz-backend

# ═══ 第9步：安装 Nginx 做反向代理 ═══
choco install nginx -y

# 配置 Nginx
$nginxConf = @"
server {
    listen 80;
    server_name _;

    location / {
        root C:/quiz-app/frontend/dist;
        index index.html;
        try_files `$uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host `$host;
        proxy_set_header X-Real-IP `$remote_addr;
    }
    location /api/v1/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host `$host;
        proxy_set_header X-Real-IP `$remote_addr;
    }
}
"@
$nginxConf | Out-File -FilePath "C:\tools\nginx\conf\nginx.conf" -Encoding utf8

nssm install nginx "C:\tools\nginx\nginx.exe"
nssm set nginx AppDirectory "C:\tools\nginx"
nssm set nginx Start SERVICE_AUTO_START
nssm start nginx

# ═══ 完成！ ═══
Write-Host "部署完成！访问 http://43.139.179.58" -ForegroundColor Green
Write-Host "默认账户：admin / admin123" -ForegroundColor Yellow
