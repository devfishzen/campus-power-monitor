#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "错误：缺少 .env"
  exit 1
fi

# 只补新配置，不动 SMTP_PASS / ECODE_* 等已有内容
grep -q '^OVERRIDES_PATH=' .env || echo 'OVERRIDES_PATH=/data/overrides.json' >> .env
grep -q '^ADMIN_USER=' .env || echo 'ADMIN_USER=admin' >> .env

generated=""
if grep -qE '^ADMIN_PASSWORD=.+' .env; then
  echo "已存在 ADMIN_PASSWORD，保留不变"
else
  if command -v python3 >/dev/null 2>&1; then
    generated="$(python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(16)))")"
  else
    generated="$(openssl rand -hex 8)"
  fi
  sed -i '/^ADMIN_PASSWORD=/d' .env
  echo "ADMIN_PASSWORD=${generated}" >> .env
fi

chmod 600 .env
mkdir -p data
if [ "$(id -u)" -eq 0 ]; then
  chown -R 1000:1000 data
fi

echo "==> 构建镜像"
docker compose build

echo "==> 重启容器"
docker compose up -d --force-recreate

echo "==> 等待服务就绪"
ready=0
for _ in $(seq 1 60); do
  if docker compose exec -T dianfei python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

if [ "$ready" -ne 1 ]; then
  echo "服务未就绪，最近日志："
  docker compose logs --tail=80
  exit 1
fi

admin_user="$(grep '^ADMIN_USER=' .env | cut -d= -f2-)"
echo
echo "升级完成。"
echo "监控页：http://<服务器IP>:8080/"
echo "设置页：http://<服务器IP>:8080/settings"
echo "用户名：${admin_user}"
if [ -n "$generated" ]; then
  echo "密码：${generated}"
  echo "（已写入 .env，之后可用：grep ADMIN_PASSWORD .env）"
else
  echo "密码：沿用 .env 里现有的 ADMIN_PASSWORD"
fi
